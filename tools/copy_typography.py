"""Mini CD 文案与字体设置：只决定方向与真实字体记录，不生成 Artwork 文字。"""
from __future__ import annotations

import re

ROLES = ("display", "artist", "chineseCopy", "englishCopy", "metadata", "spine")
# 字体 id 的形状约束：字母数字开头，允许 : _ . - 分隔（如 builtin:noto-serif-sc）。
_FONT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:.\-]{0,63}$")
# 可让用户手选「这一面文字用什么颜色」的印刷面（侧封另走 spineAppearance）。
PART_TEXT_COLOR_PARTS = ("disc", "fold", "back", "tray")
# 四个印面的加粗 / 斜体取值，与侧封 spineAppearance.style 完全一致
# （键是小写形式，值是存档里写的规范形式 —— 比较一律先 lower）。
PART_TEXT_STYLES = {"normal": "normal", "bold": "bold", "italic": "italic", "bolditalic": "boldItalic"}
# 三条物理侧封尺寸完全相同，因此共用一套模板库；位置只决定它贴在哪一条边。
SPINE_TEMPLATE_DEFAULTS = {"right": "title-artist-classic", "left": "title-artist-classic", "leftBack": "title-artist-classic"}
COMMON_SPINE_TEMPLATE_OPTIONS = {"title-artist-classic"}
SPINE_TEMPLATE_OPTIONS = {key: COMMON_SPINE_TEMPLATE_OPTIONS for key in SPINE_TEMPLATE_DEFAULTS}


def _spine_appearance(raw):
    raw = raw if isinstance(raw, dict) else {}
    font = str(raw.get("font") or "auto")
    try:
        size_mm = float(raw.get("sizeMm") or 1.7)
    except (TypeError, ValueError):
        size_mm = 1.7
    size_mm = max(0.8, min(2.6, size_mm))
    def size_value(key, fallback):
        try:
            value = float(raw.get(key) or fallback)
        except (TypeError, ValueError):
            value = fallback
        return max(0.8, min(2.6, value))
    # 旧项目只有一套字号：把它保留给专辑名，自然得到较小的歌手名，保证旧成品外观不跳变。
    title_size_mm = size_value("titleSizeMm", size_mm)
    artist_size_mm = size_value("artistSizeMm", round(size_mm * 0.74, 1))
    style = str(raw.get("style") or "normal")
    if style not in {"normal", "bold", "italic", "boldItalic"}:
        style = "normal"
    color = str(raw.get("color") or "auto").lower()
    if color != "auto" and not __import__("re").fullmatch(r"#[0-9a-f]{6}", color):
        color = "auto"
    return {"font": font, "sizeMm": size_mm, "titleSizeMm": title_size_mm,
            "artistSizeMm": artist_size_mm, "style": style, "color": color}


def _part_text_color(raw):
    """每个出版面的「用户手选文字颜色」：{"disc": "#ffffff", ...}。

    只允许 auto 或 #rrggbb，其它一律回落 auto（不让脏值渗进渲染层）。
    """
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for part in PART_TEXT_COLOR_PARTS:
        value = str(raw.get(part) or "auto").lower()
        if value != "auto" and not re.fullmatch(r"#[0-9a-f]{6}", value):
            value = "auto"
        out[part] = value
    return out


def _part_text_scale(raw):
    """每个出版面的「字号倍率」：{"disc": 1.15, ...}。

    超出范围的数字会被夹回边界（避免一个脏值把某面文字放大到糊成一团），
    非数字或缺失一律回落到 1.0（原始版式）。
    """
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for part in PART_TEXT_COLOR_PARTS:
        try:
            value = float(raw.get(part) or 1.0)
        except (TypeError, ValueError):
            value = 1.0
        out[part] = max(0.6, min(1.8, round(value, 2)))
    return out


def _part_text_font(raw):
    """每个出版面的「整面统一字体」：{"disc": "serif-cn-bold", ...}。

    只认形状合法的字体 id；形状不对的一律回落 auto（沿用各角色默认字体），
    免得一个脏值让某一面的文字全部掉帧。这里刻意**不去比字体库清单**：
    本机字体、私有字体的 id 是运行时才枚举出来的，拿静态清单比对会把它们误杀。
    """
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for part in PART_TEXT_COLOR_PARTS:
        value = str(raw.get(part) or "auto").strip()
        if value != "auto" and not _FONT_ID_RE.fullmatch(value):
            value = "auto"
        out[part] = value
    return out


def _part_text_style(raw):
    """每个出版面的「加粗 / 斜体」：{"disc": "bold", ...}。

    只认 normal / bold / italic / boldItalic 四个值（与侧封 spineAppearance.style
    同一套写法），其它一律回落 normal。
    """
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for part in PART_TEXT_COLOR_PARTS:
        out[part] = PART_TEXT_STYLES.get(str(raw.get(part) or "").strip().lower(), "normal")
    return out


def _spine_character_styles(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for zone in SPINE_TEMPLATE_DEFAULTS:
        zone_raw = raw.get(zone) if isinstance(raw.get(zone), dict) else {}
        result[zone] = {}
        for role in ("title", "artist"):
            entries = zone_raw.get(role) if isinstance(zone_raw.get(role), dict) else {}
            result[zone][role] = {str(index): _spine_appearance(value)
                                  for index, value in entries.items()
                                  if str(index).isdigit() and 0 <= int(index) < 18 and isinstance(value, dict)}
    return result

FONT_LIBRARY = [
    {"id": "noto-serif-sc", "fontFamily": "Noto Serif SC", "path": r"C:\Windows\Fonts\NotoSerifSC-VF.ttf", "language": "CJK", "license": "SIL OFL", "commercialStatus": "verified-open", "usageRoles": ["display", "artist", "chineseCopy"]},
    {"id": "noto-sans-sc", "fontFamily": "Noto Sans SC", "path": r"C:\Windows\Fonts\NotoSansSC-VF.ttf", "language": "CJK", "license": "SIL OFL", "commercialStatus": "verified-open", "usageRoles": ["artist", "chineseCopy", "metadata", "spine"]},
    {"id": "windows-georgia", "fontFamily": "Georgia", "path": r"C:\Windows\Fonts\georgia.ttf", "language": "Latin", "license": "Windows system font", "commercialStatus": "license-review-required", "usageRoles": ["display", "englishCopy"]},
    {"id": "windows-bahnschrift", "fontFamily": "Bahnschrift", "path": r"C:\Windows\Fonts\bahnschrift.ttf", "language": "Latin", "license": "Windows system font", "commercialStatus": "license-review-required", "usageRoles": ["metadata", "spine"]},
]

def normalize_copy_settings(raw):
    raw = raw or {}; concept = raw.get("conceptCopy") or {}; typo = raw.get("typography") or {}
    spine_raw = raw.get("spineTemplates") or {}
    spine_text_raw = raw.get("spineText") or {}
    spine_appearance_raw = raw.get("spineAppearance") or {}
    spine_character_styles_raw = raw.get("spineCharacterStyles") or {}
    spine_templates = {
        key: (str(spine_raw.get(key) or SPINE_TEMPLATE_DEFAULTS[key])
              if str(spine_raw.get(key) or SPINE_TEMPLATE_DEFAULTS[key]) in allowed
              else SPINE_TEMPLATE_DEFAULTS[key])
        for key, allowed in SPINE_TEMPLATE_OPTIONS.items()
    }
    return {"copyLayout": raw.get("copyLayout") if raw.get("copyLayout") in ("auto", "editorial", "minimal") else "auto",
            "conceptCopy": {k: str(concept.get(k) or "").strip() for k in ("primaryChinese", "secondaryEnglish", "shortEnglish")},
            "showBackChineseCopy": bool(raw.get("showBackChineseCopy", False)),
            "typographyStyle": str(raw.get("typographyStyle") or "auto"),
            "copyAngle": str(raw.get("copyAngle") or "none"),
            "spineTemplates": spine_templates,
            # 侧封保持用户所选字号，并使用延长后的可用高度容纳一段完整短文。
            "spineText": {key: str(spine_text_raw.get(key) or "").replace("\n", "").strip()[:18]
                          for key in SPINE_TEMPLATE_DEFAULTS},
            "spineAppearance": {key: _spine_appearance(spine_appearance_raw.get(key))
                               for key in SPINE_TEMPLATE_DEFAULTS},
            "partTextColor": _part_text_color(raw.get("partTextColor")),
            "partTextScale": _part_text_scale(raw.get("partTextScale")),
            "partTextFont": _part_text_font(raw.get("partTextFont")),
            "partTextStyle": _part_text_style(raw.get("partTextStyle")),
            "spineCharacterStyles": _spine_character_styles(spine_character_styles_raw),
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
