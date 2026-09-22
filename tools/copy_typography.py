"""Mini CD 文案与字体设置：只决定方向与真实字体记录，不生成 Artwork 文字。"""
from __future__ import annotations

ROLES = ("display", "artist", "chineseCopy", "englishCopy", "metadata", "spine")

FONT_LIBRARY = [
    {"id": "noto-serif-sc", "fontFamily": "Noto Serif SC", "path": r"C:\Windows\Fonts\NotoSerifSC-VF.ttf", "language": "CJK", "license": "SIL OFL", "commercialStatus": "verified-open", "usageRoles": ["display", "artist", "chineseCopy"]},
    {"id": "noto-sans-sc", "fontFamily": "Noto Sans SC", "path": r"C:\Windows\Fonts\NotoSansSC-VF.ttf", "language": "CJK", "license": "SIL OFL", "commercialStatus": "verified-open", "usageRoles": ["artist", "chineseCopy", "metadata", "spine"]},
    {"id": "windows-georgia", "fontFamily": "Georgia", "path": r"C:\Windows\Fonts\georgia.ttf", "language": "Latin", "license": "Windows system font", "commercialStatus": "license-review-required", "usageRoles": ["display", "englishCopy"]},
    {"id": "windows-bahnschrift", "fontFamily": "Bahnschrift", "path": r"C:\Windows\Fonts\bahnschrift.ttf", "language": "Latin", "license": "Windows system font", "commercialStatus": "license-review-required", "usageRoles": ["metadata", "spine"]},
]

def normalize_copy_settings(raw):
    raw = raw or {}; concept = raw.get("conceptCopy") or {}; typo = raw.get("typography") or {}
    return {"copyLayout": raw.get("copyLayout") if raw.get("copyLayout") in ("auto", "editorial", "minimal") else "auto",
            "conceptCopy": {k: str(concept.get(k) or "").strip() for k in ("primaryChinese", "secondaryEnglish", "shortEnglish")},
            "showBackChineseCopy": bool(raw.get("showBackChineseCopy", False)),
            "typographyStyle": str(raw.get("typographyStyle") or "auto"),
            "copyAngle": str(raw.get("copyAngle") or "none"),
            "typography": {k: str(typo.get(k) or "auto") for k in ROLES}}

def recommend_copy_layout(settings, design):
    if settings["copyLayout"] != "auto": return settings["copyLayout"]
    return "minimal" if (design or {}).get("style") == "minimalist" else "editorial"

def recommend_typography(design):
    style = (design or {}).get("style", "retro")
    direction = {"minimalist": "轻量 Serif + Neutral Sans", "bold": "Display Sans + Neutral Sans", "retro": "书写感 Display + Elegant Serif"}.get(style, "轻量 Serif + Neutral Sans")
    return {"direction": direction, "display": "书写/衬线", "chineseBody": "轻量中文", "englishDisplay": "Elegant Serif", "metadata": "Neutral Sans"}

def font_library(): return FONT_LIBRARY

def auto_concept_copy(album, design):
    """无模型阶段的稳定文案兜底：由封面情绪和专辑名派生，不复用参考图示例。"""
    mood = (design or {}).get("mood", "dreamy")
    bank = {
        "energetic": ("把这一刻的心跳，写进仍在前行的光里。", "KEEP MOVING WITH THE LIGHT.", "IN MOTION."),
        "melancholic": ("有些回声，不必抵达终点。", "SOME ECHOES NEVER LEAVE.", "AFTER THE ECHO."),
        "dreamy": ("让未说完的心事，慢慢落在时间里。", "LET THE QUIET STAY.", "IN SOFT LIGHT."),
    }
    return bank.get(mood, bank["dreamy"])
