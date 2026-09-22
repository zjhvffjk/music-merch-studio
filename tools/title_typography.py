"""Title lettering direction and provider boundary.

Phase 1 deliberately has no synthetic lettering generator.  It keeps the data
contract that a real provider will use while clearly reporting unavailable
state instead of presenting a normal font as AI lettering.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

VARIANTS = ("closest-original", "editorial", "expressive", "minimal")
TITLE_MODES = ("cover-follow", "font", "artistic")


@dataclass(frozen=True)
class ArtisticTypographyRequest:
    album: str
    artist: str = ""
    language: str = ""
    visual_dna: dict | None = None
    title_direction: dict | None = None
    cover_title_reference: dict | None = None
    count: int = 4


@dataclass(frozen=True)
class TitleLetteringCandidate:
    id: str
    provider: str
    status: str = "ready"
    png_path: str | None = None
    svg_path: str | None = None
    width: int = 0
    height: int = 0
    transparent: bool = False
    prompt: str = ""
    title_direction: dict | None = None
    variant: str = "minimal"

    def to_dict(self):
        return asdict(self)


class ArtisticTypographyProvider(Protocol):
    provider_id: str

    def generate(self, request: ArtisticTypographyRequest) -> list[TitleLetteringCandidate]: ...


class UnavailableProvider:
    provider_id = "unavailable"

    def generate(self, request: ArtisticTypographyRequest) -> list[TitleLetteringCandidate]:
        return []


class ManualAssetProvider:
    provider_id = "local-upload"

    def generate(self, request: ArtisticTypographyRequest) -> list[TitleLetteringCandidate]:
        # Manual files are registered by title_assets; this provider never fabricates one.
        return []


def _contains_cjk(value: str) -> bool:
    return any("\u2e80" <= ch <= "\u9fff" for ch in value or "")


def normalize_title_settings(raw: dict | None) -> dict:
    raw = raw or {}
    mode = raw.get("titleMode") if raw.get("titleMode") in TITLE_MODES else "cover-follow"
    provider = str(raw.get("titleProvider") or "unavailable")
    selected = str(raw.get("selectedTitleAssetId") or "").strip()
    candidates = raw.get("titleCandidates") if isinstance(raw.get("titleCandidates"), list) else []
    return {
        "titleMode": mode,
        "titleProvider": provider,
        "titleDirection": raw.get("titleDirection") if isinstance(raw.get("titleDirection"), dict) else {},
        "titleCandidates": candidates[:4],
        "selectedTitleAssetId": selected or None,
        "titleReferenceUpload": str(raw.get("titleReferenceUpload") or "").strip() or None,
    }


def analyze_title_direction(visual_dna: dict | None, album: str | dict | None = None) -> dict:
    visual_dna = visual_dna or {}
    title = album.get("album", "") if isinstance(album, dict) else str(album or "")
    style = str(visual_dna.get("style") or "").lower()
    mood = str(visual_dna.get("mood") or "").lower()
    if any(k in style for k in ("hand", "calligraphy", "brush")) or _contains_cjk(title):
        category = "brush-calligraphy" if _contains_cjk(title) else "handwritten"
    elif "minimal" in style or "electronic" in mood:
        category = "geometric-sans"
    elif "retro" in style:
        category = "retro-display"
    elif "experimental" in style:
        category = "experimental"
    else:
        category = "editorial-serif"
    return {
        "category": category,
        "weight": "regular" if category in ("brush-calligraphy", "handwritten") else "light",
        "tracking": "normal" if len(title) <= 8 else "tight",
        "slantDeg": 3 if category in ("brush-calligraphy", "handwritten") else 0,
        "palette": ["#1f1b18"],
        "referenceSource": "cover-title-region" if visual_dna.get("coverTitleReference") else "manual",
        "mood": mood or "neutral",
    }


def coerce_request(request: ArtisticTypographyRequest | dict) -> ArtisticTypographyRequest:
    if isinstance(request, ArtisticTypographyRequest):
        return request
    request = request or {}
    album = str(request.get("album") or "")
    dna = request.get("visual_dna") or request.get("visualDna") or {}
    return ArtisticTypographyRequest(
        album=album,
        artist=str(request.get("artist") or ""),
        language=str(request.get("language") or ("zh" if _contains_cjk(album) else "en")),
        visual_dna=dna,
        title_direction=request.get("title_direction") or request.get("titleDirection") or analyze_title_direction(dna, album),
        cover_title_reference=request.get("cover_title_reference") or request.get("coverTitleReference"),
        count=4,
    )


def generate_artistic_typography(request: ArtisticTypographyRequest | dict, provider_id: str = "unavailable") -> dict:
    request = coerce_request(request)
    provider = ManualAssetProvider() if provider_id == "local-upload" else UnavailableProvider()
    candidates = provider.generate(request)
    return {
        "status": "ready" if candidates else "unavailable",
        "provider": provider.provider_id if provider_id in ("local-upload", "unavailable") else provider_id,
        "message": "尚未配置 AI 艺术字 Provider。可上传透明 PNG/SVG，或使用原封面标题。" if not candidates else "",
        "direction": request.title_direction or {},
        "variants": list(VARIANTS),
        "candidates": [c.to_dict() for c in candidates[:4]],
    }


def title_typography_state(raw: dict | None, visual_dna: dict | None, album: str, artist: str = "") -> dict:
    settings = normalize_title_settings(raw)
    direction = settings["titleDirection"] or analyze_title_direction(visual_dna, album)
    result = generate_artistic_typography({"album": album, "artist": artist, "visual_dna": visual_dna or {}, "title_direction": direction}, settings["titleProvider"])
    slots = []
    by_variant = {str(c.get("variant") or ""): c for c in settings["titleCandidates"]}
    for variant in VARIANTS:
        item = dict(by_variant.get(variant) or {})
        item.setdefault("variant", variant)
        item.setdefault("status", "unavailable" if result["status"] == "unavailable" else "empty")
        slots.append(item)
    return {**settings, "direction": direction, "providerStatus": result["status"], "providerMessage": result["message"], "slots": slots}
