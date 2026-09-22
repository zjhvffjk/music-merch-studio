import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "outputs" / "迷你CD设计" / "_title_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class TitleLetteringAsset:
    id: str
    album_key: str
    png_path: str | None
    svg_path: str | None
    width: int
    height: int
    transparent: bool
    visible_bounds: tuple
    source_filename: str
    source_mode: str
    def to_dict(self): return asdict(self)

def _visible_bounds(im):
    alpha = im.getchannel("A") if "A" in im.getbands() else None
    box = alpha.getbbox() if alpha else im.getbbox()
    return tuple(box or (0, 0, im.width, im.height))

def save_title_asset(upload_path, album_key):
    src = Path(upload_path)
    if src.suffix.lower() not in (".png", ".svg"):
        raise ValueError("标题资产只支持 PNG 或 SVG")
    if not src.is_file():
        raise ValueError("标题上传不存在")
    raw = src.read_bytes(); digest = hashlib.sha256(raw).hexdigest()[:16]
    aid = "ttl_" + digest
    dst = ASSET_DIR / aid; dst.mkdir(exist_ok=True)
    suffix = src.suffix.lower(); target = dst / ("source" + suffix)
    if not target.exists(): shutil.copyfile(src, target)
    png_path = None; svg_path = str(target) if suffix == ".svg" else None
    if suffix == ".svg":
        raise ValueError("SVG 预览需要本地光栅化器；请先上传透明 PNG")
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        png = dst / "asset.png"; rgba.save(png)
        alpha = rgba.getchannel("A")
        asset = TitleLetteringAsset(aid, str(album_key or ""), str(png), svg_path, rgba.width, rgba.height,
                                    alpha.getextrema()[0] < 255, _visible_bounds(rgba), src.name, im.mode)
    (dst / "meta.json").write_text(json.dumps(asset.to_dict(), ensure_ascii=False), encoding="utf-8")
    return asset

def load_title_asset(asset_id):
    base = ASSET_DIR / str(asset_id or "")
    data = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    return TitleLetteringAsset(**data), Image.open(data["png_path"]).convert("RGBA")

def title_asset_meta(asset_id):
    asset, _ = load_title_asset(asset_id); return asset
