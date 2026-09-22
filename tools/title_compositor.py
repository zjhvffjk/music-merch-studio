from dataclasses import dataclass
from PIL import Image

@dataclass
class Placement:
    panel: str; x_mm: float; y_mm: float; width_mm: float; height_mm: float; rotation_deg: float = 0
    @property
    def bounds_mm(self): return {"x": self.x_mm, "y": self.y_mm, "w": self.width_mm, "h": self.height_mm}

def intersects(a, b):
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])

def resolve_title_placement(panel, spec, direction=None):
    if panel == "disc": return Placement(panel, 22, 5, 12, 5, 0)
    if panel == "back": return Placement(panel, 3.7, 2.0, 24, 3.2, 0)
    if panel == "cover-front": return Placement(panel, 23, 28, 14, 4, 0)
    if panel == "cover-inside": return Placement(panel, 3, 4, 12, 3, 0)
    if panel in ("left-spine", "left-spine-back", "right-spine"): return Placement(panel, 0.7, 5, 3, 25, 90)
    return Placement(panel, 30, 27, 14, 4, 0)

def place_title_asset(image, asset_image, placement, protected_rects, dpi):
    px = lambda v: int(round(v*dpi/25.4))
    out = image.convert("RGBA")
    ax0, ay0, ax1, ay1 = asset_image.getchannel("A").getbbox() or (0,0,asset_image.width,asset_image.height)
    crop = asset_image.crop((ax0, ay0, ax1, ay1))
    mw, mh = max(1, px(placement.width_mm)), max(1, px(placement.height_mm))
    scale = min(mw/crop.width, mh/crop.height)
    crop = crop.resize((max(1, int(crop.width*scale)), max(1, int(crop.height*scale))), Image.LANCZOS)
    if placement.rotation_deg: crop = crop.rotate(-placement.rotation_deg, expand=True, resample=Image.BICUBIC)
    x, y = px(placement.x_mm), px(placement.y_mm)
    bounds = {"x": placement.x_mm, "y": placement.y_mm, "w": crop.width*25.4/dpi, "h": crop.height*25.4/dpi}
    if any(intersects(bounds, r) for r in protected_rects):
        return out.convert(image.mode), {"placed": False, "warning": "标题资产与生产保护区相交", "boundsMm": bounds}
    out.alpha_composite(crop, (x, y))
    return out.convert(image.mode), {"placed": True, "boundsMm": bounds, "assetVisibleBounds": (ax0,ay0,ax1,ay1)}
