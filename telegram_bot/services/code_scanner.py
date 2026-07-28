"""
فحص تحذيري بسيط (Static Pattern Scan) للملفات التي يرفعها المستخدم في مولّد المشاريع.
هذا الفحص إعلامي فقط لتنبيه المستخدم إلى أنماط شائعة قد تكون خطيرة في كوده الخاص —
وليس بديلاً عن أي عزل أو حماية، لأن الكود لا يُشغَّل على الخادم أصلاً.
"""
from __future__ import annotations

import re

RISKY_PATTERNS: list[tuple[str, str]] = [
    (r"os\.system\s*\(", "استدعاء أوامر نظام مباشرة (os.system)"),
    (r"subprocess\.(run|call|Popen)", "تشغيل عمليات نظام فرعية (subprocess)"),
    (r"\beval\s*\(", "استخدام eval() لتنفيذ نصوص كأكواد"),
    (r"\bexec\s*\(", "استخدام exec() لتنفيذ نصوص كأكواد"),
    (r"rm\s+-rf", "أمر حذف ملفات جماعي (rm -rf)"),
    (r"base64\.b64decode", "فك تشفير Base64 (قد يُستخدم لإخفاء كود)"),
    (r"socket\.socket", "فتح اتصال شبكة منخفض المستوى (socket)"),
    (r"curl\s+.*\|\s*sh", "تحميل وتشغيل سكربت من الإنترنت مباشرة"),
    (r"chmod\s+777", "صلاحيات ملفات مفتوحة بالكامل (chmod 777)"),
]


def scan_files_for_warnings(file_contents: dict[str, str]) -> list[str]:
    """يعيد قائمة تحذيرات نصية (اسم الملف + النمط المكتشف) دون حظر أي شيء."""
    warnings: list[str] = []
    for filename, content in file_contents.items():
        for pattern, description in RISKY_PATTERNS:
            if re.search(pattern, content):
                warnings.append(f"⚠️ {filename}: {description}")
    return warnings
