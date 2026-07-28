"""
تحويل رد الذكاء الاصطناعي إلى ملفات مشروع أو ملف ZIP عند الحاجة
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from config import config

CODE_BLOCK_RE = re.compile(
    r"```(?:[\w+\-.]*\n)?(?:#\s*(?P<filename>[\w./\-]+)\n)?(?P<code>.*?)```", re.DOTALL
)


def extract_code_blocks(text: str) -> dict[str, str]:
    """استخراج كتل الكود من رد النموذج، مع تخمين اسم ملف عند غياب التسمية."""
    blocks: dict[str, str] = {}
    counter = 1
    for match in CODE_BLOCK_RE.finditer(text):
        filename = match.group("filename")
        code = match.group("code").strip("\n")
        if not filename:
            filename = f"file_{counter}.py"
            counter += 1
        blocks[filename.strip()] = code
    return blocks


def build_project_zip(request_id: int, ai_response: str) -> Path | None:
    """
    ينشئ ملف ZIP يحتوي على كل ملفات الكود المستخرجة بالإضافة لشرح كامل.
    يعيد None إذا لم يتم العثور على أي كتلة كود (رد نصي بسيط فقط).
    """
    blocks = extract_code_blocks(ai_response)
    if not blocks:
        return None

    zip_path = config.generated_dir / f"project_{request_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, code in blocks.items():
            zf.writestr(filename, code)
        zf.writestr("README.txt", ai_response)

    return zip_path
