"""
مولّد المشاريع بالذكاء الاصطناعي: اختيار قالب، توليد مشروع كامل، معالج إعداد المتغيرات،
وتعديل مشروع موجود يرفعه المستخدم.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import config
from database.repository import (
    GeneratedProjectRepository,
    ProjectTemplateRepository,
    SettingsRepository,
)
from services.ai_service import AIGenerationError, AIService
from services.code_packager import build_project_zip, extract_code_blocks
from services.vip_service import get_vip_status
from services.config_wizard import (
    OPTIONAL_VARIABLES,
    REQUIRED_VARIABLES,
    build_env_content,
    validate_value,
)
from states.user_states import ProjectGeneratorStates

router = Router(name="project_generator")

TEXT_EXTENSIONS = {".py", ".txt", ".md", ".env", ".json", ".yaml", ".yml", ".cfg", ".ini"}


@router.callback_query(F.data == "feat:project_generator")
async def show_templates(callback: CallbackQuery, session, user) -> None:
    is_vip, _ = await get_vip_status(session, user.id)

    if not is_vip and user.project_free_credits <= 0:
        await _show_project_payment_options(callback, session)
        return

    repo = ProjectTemplateRepository(session)
    templates = await repo.list_active()

    rows = [
        [InlineKeyboardButton(text=f"📦 {t.name}", callback_data=f"tpl:{t.id}")] for t in templates
    ]
    rows.append([InlineKeyboardButton(text="🆕 وصف حر بدون قالب", callback_data="tpl:0")])
    rows.append([InlineKeyboardButton(text="📤 تعديل مشروع موجود (رفع ملف)", callback_data="edit_existing")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="nav:main")])

    if is_vip:
        status_line = "👑 عضويتك VIP تمنحك استخدامًا غير محدود لمولّد المشاريع."
    else:
        status_line = f"🆓 عدد مرات الاستخدام المجانية المتبقية لك: {user.project_free_credits}"

    await callback.message.edit_text(
        f"🧠 <b>مولّد المشاريع بالذكاء الاصطناعي</b>\n\n{status_line}\n\nاختر قالبًا جاهزًا أو ابدأ بوصف حر:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML",
    )
    await callback.answer()


async def _show_project_payment_options(callback: CallbackQuery, session) -> None:
    from database.repository import PaymentMethodRepository

    settings_repo = SettingsRepository(session)
    price = await settings_repo.get_float("project_generator_price", 20)
    methods_repo = PaymentMethodRepository(session)
    methods = await methods_repo.list_active()

    if not methods:
        await callback.answer("⚠️ لا توجد طرق دفع مفعّلة حاليًا.", show_alert=True)
        return

    rows = [
        [InlineKeyboardButton(text=f"{m.name} — {price} {m.currency}", callback_data=f"projgenpay:{m.id}")]
        for m in methods
    ]
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="nav:main")])

    await callback.message.edit_text(
        f"⚠️ استنفدت مرات الاستخدام المجانية لمولّد المشاريع.\n\n💰 سعر الاستخدام الآن: {price}\n\nاختر طريقة الدفع:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("projgenpay:"))
async def choose_project_payment(callback: CallbackQuery, state: FSMContext, session, user) -> None:
    method_id = int(callback.data.split(":")[1])
    from database.repository import PaymentMethodRepository

    methods_repo = PaymentMethodRepository(session)
    method = await methods_repo.get(method_id)
    settings_repo = SettingsRepository(session)
    price = await settings_repo.get_float("project_generator_price", 20)

    if not method:
        await callback.answer("⚠️ طريقة الدفع غير متاحة.", show_alert=True)
        return

    if method.code == "stars":
        from services.stars_payment import send_stars_invoice

        await send_stars_invoice(
            callback.bot, callback.from_user.id,
            title="استخدام مولّد المشاريع", description="دفع لاستخدام مولّد المشاريع بالذكاء الاصطناعي",
            payload=f"projectgen:{user.id}", amount_stars=int(price),
        )
        await callback.answer()
        return

    await state.update_data(method_id=method_id, price=price)
    await callback.message.answer(
        f"{method.instructions}\n\n💰 المبلغ المطلوب: {price} {method.currency}"
    )
    await callback.message.answer("📎 أرسل الآن صورة إثبات التحويل أو رقم العملية.")
    await state.set_state(ProjectGeneratorStates.waiting_payment_proof)
    await callback.answer()


@router.message(ProjectGeneratorStates.waiting_payment_proof)
async def receive_project_payment_proof(message: Message, state: FSMContext, session, user) -> None:
    from database.repository import PaymentRepository

    data = await state.get_data()
    method_id = data.get("method_id")
    price = data.get("price", 0.0)
    if not method_id:
        return

    proof_file_id = message.photo[-1].file_id if message.photo else None
    reference = message.caption if message.photo else message.text

    payment_repo = PaymentRepository(session)
    await payment_repo.create(
        user_id=user.id, method_id=method_id, amount=price, purpose="projectgen",
        reference=reference, proof_file_id=proof_file_id,
    )
    await message.answer("⏳ تم استلام طلبك، سيتم مراجعته من الإدارة وسنبلغك فور التأكيد.")
    await state.clear()

    from config import config as bot_config
    from database.repository import AdminRepository

    admins = await AdminRepository(session).list_all()
    admin_ids = {*bot_config.super_admins, *(a.telegram_id for a in admins)}
    for admin_id in admin_ids:
        try:
            await message.bot.send_message(
                admin_id, f"🧱 طلب دفع مولّد مشاريع جديد\nالمستخدم: {user.telegram_id}\nالمبلغ: {price}"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("tpl:"))
async def choose_template(callback: CallbackQuery, state: FSMContext, session) -> None:
    template_id = int(callback.data.split(":")[1])
    await state.update_data(template_id=template_id or None)
    await callback.message.answer(
        "✍️ اكتب الآن وصف المشروع الذي تريد إنشاءه بالتفصيل (كلما كان الوصف أوضح كانت النتيجة أفضل):"
    )
    await state.set_state(ProjectGeneratorStates.waiting_description)
    await callback.answer()


@router.message(ProjectGeneratorStates.waiting_description)
async def handle_description(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    if data.get("editing_existing"):
        await _apply_existing_project_edit(message, state, session, user)
    else:
        await _generate_project(message, state, session, user)


async def _generate_project(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    template_id = data.get("template_id")
    description = message.text.strip()

    from database.repository import UserRepository

    user_repo = UserRepository(session)
    if user.project_free_credits > 0:
        await user_repo.decrement_project_free_credit(user)

    prompt_prefix = ""
    if template_id:
        tpl_repo = ProjectTemplateRepository(session)
        template = await tpl_repo.get(template_id)
        if template:
            prompt_prefix = template.prompt_prefix + "\n\n"

    full_prompt = (
        prompt_prefix + description + "\n\n"
        "أنتج المشروع كاملاً بصيغة كتل كود منفصلة، وضع اسم الملف كتعليق أول سطر داخل كل كتلة "
        "بالشكل: # اسم_الملف.امتداد، بحيث يشمل الكود المصدري، هيكل المجلدات، قاعدة البيانات، "
        "ملف README.md، وملف requirements.txt، وملف .env.example. لا تستخدم عبارات ناقصة (TODO)."
    )

    project_repo = GeneratedProjectRepository(session)
    project = await project_repo.create(user.id, description, template_id)

    status_msg = await message.answer("⏳ جاري توليد مشروعك بالكامل، قد يستغرق هذا بعض الوقت...")

    settings_repo = SettingsRepository(session)
    provider = await settings_repo.get("default_ai_provider", "claude")
    ai_service = AIService(provider)

    try:
        response = await ai_service.generate(full_prompt)
    except AIGenerationError as exc:
        await project_repo.set_status(project.id, "failed", error_message=str(exc))
        await status_msg.edit_text(f"❌ فشل توليد المشروع: {exc}")
        await state.clear()
        return

    blocks = extract_code_blocks(response)
    if not blocks:
        await project_repo.set_status(project.id, "failed", error_message="لم يتم استخراج أي ملفات")
        await status_msg.edit_text("⚠️ لم أتمكن من استخراج ملفات مشروع من الرد. حاول بوصف أكثر تفصيلاً.")
        await state.clear()
        return

    await state.update_data(project_id=project.id, blocks=blocks, collected={}, pending_index=0)
    await status_msg.edit_text(
        "✅ تم توليد الكود بنجاح!\n\nقبل تسليم المشروع النهائي، أحتاج بعض البيانات الأساسية لإعداده."
    )
    await _ask_next_variable(message, state)


async def _ask_next_variable(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    index = data.get("pending_index", 0)
    all_vars = REQUIRED_VARIABLES + OPTIONAL_VARIABLES

    if index >= len(all_vars):
        await _finalize_project(message, state)
        return

    variable = all_vars[index]
    await message.answer(variable.prompt)
    await state.set_state(ProjectGeneratorStates.collecting_variable)


@router.message(ProjectGeneratorStates.collecting_variable)
async def collect_variable(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    index = data.get("pending_index", 0)
    all_vars = REQUIRED_VARIABLES + OPTIONAL_VARIABLES
    variable = all_vars[index]

    is_valid, result = validate_value(variable.validator, message.text or "")
    if not is_valid:
        await message.answer(result)
        return

    collected = data.get("collected", {})
    collected[variable.key] = result
    await state.update_data(collected=collected, pending_index=index + 1)
    await _ask_next_variable(message, state)


async def _finalize_project(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    blocks: dict[str, str] = data.get("blocks", {})
    collected: dict[str, str] = data.get("collected", {})
    project_id = data.get("project_id")

    env_content = build_env_content(collected)
    zip_path = config.generated_dir / f"project_{project_id}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, code in blocks.items():
            zf.writestr(filename, code)
        zf.writestr(".env", env_content)

    from database.engine import async_session_maker
    from database.repository import GeneratedProjectRepository as _Repo

    async with async_session_maker() as session:
        repo = _Repo(session)
        await repo.set_status(project_id, "completed", zip_path=str(zip_path))

    await message.answer("📦 مشروعك جاهز بالكامل!")
    await message.answer_document(FSInputFile(zip_path), caption="✅ تم حقن الإعدادات وبناء المشروع النهائي.")
    await state.clear()


# ------------------------------------------------------ تعديل مشروع موجود --
@router.callback_query(F.data == "edit_existing")
async def ask_existing_project(callback: CallbackQuery, state: FSMContext, session, user) -> None:
    is_vip, _ = await get_vip_status(session, user.id)
    if not is_vip:
        rows = [
            [InlineKeyboardButton(text="👑 عرض باقات VIP", callback_data="feat:vip")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="feat:project_generator")],
        ]
        await callback.message.answer(
            "🔒 ميزة رفع وتعديل مشروع موجود حصرية لأعضاء VIP فقط.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    await callback.message.answer("📤 أرسل الآن ملف مشروعك (ZIP يحتوي على الأكواد، أو ملف كود واحد):")
    await state.set_state(ProjectGeneratorStates.waiting_existing_project)
    await callback.answer()


@router.message(ProjectGeneratorStates.waiting_existing_project, F.document)
async def receive_existing_project(message: Message, state: FSMContext) -> None:
    file = await message.bot.get_file(message.document.file_id)
    local_path = config.generated_dir / f"upload_{message.document.file_unique_id}_{message.document.file_name}"
    await message.bot.download_file(file.file_path, destination=local_path)

    file_contents: dict[str, str] = {}

    if local_path.suffix == ".zip":
        with zipfile.ZipFile(local_path) as zf:
            for name in zf.namelist():
                if Path(name).suffix in TEXT_EXTENSIONS:
                    try:
                        file_contents[name] = zf.read(name).decode("utf-8", errors="ignore")[:4000]
                    except Exception:
                        continue
    elif local_path.suffix in TEXT_EXTENSIONS:
        file_contents[local_path.name] = local_path.read_text(encoding="utf-8", errors="ignore")[:4000]
    else:
        await message.answer("⚠️ صيغة الملف غير مدعومة للتحليل. أرسل ملف ZIP أو ملف كود نصي.")
        return

    if not file_contents:
        await message.answer("⚠️ لم أجد ملفات نصية قابلة للتحليل داخل الملف المرفوع.")
        await state.clear()
        return

    await state.update_data(existing_files=file_contents, existing_path=str(local_path))

    from services.code_scanner import scan_files_for_warnings

    warnings = scan_files_for_warnings(file_contents)
    if warnings:
        warning_text = "\n".join(warnings[:15])
        await message.answer(
            f"⚠️ <b>تنبيه فحص تلقائي (إعلامي فقط):</b>\nتم رصد أنماط التالية في ملفاتك، راجعها قبل النشر:\n\n{warning_text}",
            parse_mode="HTML",
        )

    await message.answer(
        f"✅ تم تحليل المشروع ({len(file_contents)} ملف نصي).\n\n"
        "✍️ اكتب الآن وصفًا للتعديل المطلوب (سيتم تعديل الأجزاء المطلوبة فقط دون إعادة كتابة كل شيء):"
    )
    await state.set_state(ProjectGeneratorStates.waiting_description)
    await state.update_data(template_id=None, editing_existing=True)


async def _apply_existing_project_edit(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    existing_files: dict[str, str] = data.get("existing_files", {})
    instruction = message.text.strip()

    summary = "\n\n".join(f"### {name}\n```\n{content}\n```" for name, content in existing_files.items())
    prompt = (
        "لديك مشروع برمجي حالي بالملفات التالية. عدّل فقط الأجزاء المطلوبة أدناه دون إعادة كتابة "
        "الملفات غير المرتبطة بالتعديل، وأعد كل ملف تم تعديله كاملاً بصيغة كتلة كود مع اسم الملف "
        "كتعليق أول سطر بالشكل: # اسم_الملف.\n\n"
        f"الملفات الحالية:\n{summary}\n\n"
        f"التعديل المطلوب: {instruction}"
    )

    status_msg = await message.answer("⏳ جاري تحليل وتعديل المشروع...")

    settings_repo = SettingsRepository(session)
    provider = await settings_repo.get("default_ai_provider", "claude")
    ai_service = AIService(provider)

    try:
        response = await ai_service.generate(prompt)
    except AIGenerationError as exc:
        await status_msg.edit_text(f"❌ فشل التعديل: {exc}")
        await state.clear()
        return

    updated_blocks = extract_code_blocks(response)
    if not updated_blocks:
        await status_msg.edit_text("⚠️ لم يتم استخراج أي تعديل. حاول توصيف التعديل بشكل أوضح.")
        await state.clear()
        return

    merged_files = {**existing_files, **updated_blocks}
    project_repo = GeneratedProjectRepository(session)
    project = await project_repo.create(user.id, f"تعديل مشروع: {instruction}")

    zip_path = build_project_zip(project.id, response) or (config.generated_dir / f"project_{project.id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, code in merged_files.items():
            zf.writestr(filename, code)

    await project_repo.set_status(project.id, "completed", zip_path=str(zip_path))
    await status_msg.edit_text(f"✅ تم تعديل {len(updated_blocks)} ملف بنجاح.")
    await message.answer_document(FSInputFile(zip_path), caption="📦 مشروعك بعد التعديل")
    await state.clear()
