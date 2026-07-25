"""
خدمة توليد الأكواد عبر Claude API أو OpenAI API (قابلة للتبديل)
"""
from __future__ import annotations

import httpx

from config import config

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "أنت مهندس برمجيات محترف. عند استلام وصف مشروع، أنتج كودًا كاملاً وعمليًا "
    "بدون أخطاء، مع شرح مختصر وواضح لطريقة الاستخدام. لا تستخدم عبارات ناقصة أو "
    "تلميحات (TODO)، واكتب كودًا جاهزًا للتشغيل مباشرة."
)


class AIGenerationError(Exception):
    pass


class AIService:
    """واجهة موحدة لتوليد الأكواد بغض النظر عن المزود المستخدم."""

    def __init__(self, provider: str):
        self.provider = provider

    async def generate(self, prompt: str) -> str:
        if self.provider == "claude":
            return await self._generate_claude(prompt)
        if self.provider == "openai":
            return await self._generate_openai(prompt)
        if self.provider == "google":
            return await self._generate_gemini(prompt)
        raise AIGenerationError(f"مزود ذكاء اصطناعي غير مدعوم: {self.provider}")

    async def _generate_claude(self, prompt: str) -> str:
        if not config.claude_api_key:
            raise AIGenerationError("مفتاح Claude API غير مُعدّ من لوحة الأدمن.")

        headers = {
            "x-api-key": config.claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 4000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(CLAUDE_URL, headers=headers, json=payload)
        if response.status_code != 200:
            raise AIGenerationError(f"فشل الاتصال بـ Claude API: {response.status_code}")

        data = response.json()
        parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
        result = "\n".join(parts).strip()
        if not result:
            raise AIGenerationError("رد فارغ من Claude API")
        return result

    async def _generate_openai(self, prompt: str) -> str:
        if not config.openai_api_key:
            raise AIGenerationError("مفتاح OpenAI API غير مُعدّ من لوحة الأدمن.")

        headers = {
            "Authorization": f"Bearer {config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4000,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(OPENAI_URL, headers=headers, json=payload)
        if response.status_code != 200:
            raise AIGenerationError(f"فشل الاتصال بـ OpenAI API: {response.status_code}")

        data = response.json()
        try:
            result = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raise AIGenerationError("رد غير متوقع من OpenAI API")
        if not result:
            raise AIGenerationError("رد فارغ من OpenAI API")
        return result

    async def _generate_gemini(self, prompt: str) -> str:
        if not config.google_api_key:
            raise AIGenerationError("مفتاح Google (Gemini) API غير مُعدّ من لوحة الأدمن.")

        model = "gemini-2.0-flash"
        url = GEMINI_URL.format(model=model)
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]}
            ],
            "generationConfig": {"maxOutputTokens": 8000},
        }
        params = {"key": config.google_api_key}

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, params=params, json=payload)

        if response.status_code != 200:
            raise AIGenerationError(
                f"فشل الاتصال بـ Google Gemini API: {response.status_code} — {response.text[:200]}"
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "غير معروف")
            raise AIGenerationError(f"تم رفض الطلب من Gemini (السبب: {reason}).")

        try:
            parts = candidates[0]["content"]["parts"]
            result = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError):
            raise AIGenerationError("رد غير متوقع من Google Gemini API")

        if not result:
            raise AIGenerationError("رد فارغ من Google Gemini API")
        return result
