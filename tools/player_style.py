"""Map catalog references to original player artwork using the selected song."""
import colorsys
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1] / 'workbench/mini-mockup/player-skins'
THEMES = frozenset({
    'coast', 'collage', 'halo', 'pixel', 'cover', 'crystal', 'glow', 'moon',
    'cabinet', 'flora', 'tape', 'record', 'ornate', 'stage', 'landscape', 'illustrated',
})


class PlayerStyle(NamedTuple):
    top: tuple
    bottom: tuple
    disc: tuple
    groove: tuple
    theme: str
    lighting: tuple
    controls: 'ControlPalette'


class ControlPalette(NamedTuple):
    text: tuple
    muted: tuple
    accent: tuple
    track: tuple
    chip: tuple


def _mix(first, second, amount):
    return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(first, second))


def _luminance(rgb):
    channels = [c / 255 for c in rgb]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))


def _player_colors(upper, lower):
    if _luminance(lower) >= .32:
        # Maintain a light surface underneath the small print, tinted by the reference.
        bottom = _mix(lower, (249, 250, 252), .33)
        top = _mix(upper, bottom, .64)
        if _luminance(top) < .42:
            top = _mix(top, bottom, .62)
        ink = _mix(lower, (12, 19, 24), .93)
        muted = _mix(lower, (15, 24, 31), .79)
        return top, bottom, ControlPalette(ink, muted, ink, _mix(bottom, ink, .27), _mix(bottom, ink, .12))

    top, bottom = _shade(upper, .48, .08), _shade(lower, .27, .05)
    ink = (247, 248, 250)
    muted = _mix(bottom, ink, .67)
    return top, bottom, ControlPalette(ink, muted, _mix(upper, ink, .73), _mix(bottom, ink, .30), _mix(bottom, ink, .14))


@lru_cache(maxsize=1)
def _catalog():
    data = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    styles = {entry['id']: entry for entry in data['skins']}
    if len(styles) != len(data['skins']) or any(entry.get('outputTheme') not in THEMES for entry in styles.values()):
        raise ValueError('播放器装扮目录包含重复编号或无效版式')
    return styles


def renderable_style_count():
    return len(_catalog())


def _sample(image, y):
    # Sample both edges to keep the demonstration's cover and text out of the palette.
    pixels = [image.getpixel((x, row)) for x in (2, 3, 28, 29) for row in range(y, y + 7)]
    return tuple(sorted(pixel[c] for pixel in pixels)[len(pixels) // 2] for c in range(3))


def _shade(rgb, ceiling, floor=0):
    hue, saturation, value = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, saturation, floor + value * (ceiling - floor)))


@lru_cache(maxsize=117)
def resolve_player_style(style_id):
    if not style_id:
        return None
    entry = _catalog().get(style_id)
    if entry is None:
        raise ValueError('找不到选中的播放器样式，请重新选择')
    path = (ROOT / entry['preview']).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('播放器样式素材路径无效')
    with Image.open(path) as image:
        reference = image.convert('RGB').resize((32, 64), Image.Resampling.BOX)
    upper, lower = _sample(reference, 5), _sample(reference, 49)
    top, bottom, controls = _player_colors(upper, lower)
    lighting = tuple(reference.getpixel(point) for point in ((5, 8), (26, 8), (5, 30), (26, 30)))
    return PlayerStyle(top, bottom, _shade(upper, .42, .12), _shade(upper, .78, .28),
                       entry['outputTheme'], lighting, controls)


def _circle_cover(image, cover, center, diameter):
    artwork = ImageOps.fit(cover, (diameter, diameter), Image.Resampling.LANCZOS)
    mask = Image.new('L', artwork.size)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    image.paste(artwork, (round(center[0] - diameter / 2), round(center[1] - diameter / 2)), mask)


def _catalog_artwork(image, cover, center, size, style):
    """Create the artwork window and decor without pasting the reference screenshot."""
    scale = size / 240
    theme = style.theme
    canvas = Image.new('RGBA', (320, 320))
    brush = ImageDraw.Draw(canvas)
    for (x, y), rgb in zip(((55, 60), (265, 60), (55, 255), (265, 255)), style.lighting):
        shade = _shade(rgb, .9, .35)
        brush.ellipse((x-78, y-78, x+78, y+78), fill=(*shade, 150))
    canvas = canvas.filter(ImageFilter.GaussianBlur(42))
    # Fade the lighting before its canvas ends so it blends into the controls area.
    edge = Image.new('L', (320, 320))
    edge_draw = ImageDraw.Draw(edge)
    for inset in range(32):
        edge_draw.rectangle((inset, inset, 319-inset, 319-inset), fill=round(inset * 255 / 31))
    canvas.putalpha(ImageChops.multiply(canvas.getchannel('A'), edge))
    brush = ImageDraw.Draw(canvas)
    accent = style.groove
    light = tuple(round(115 + channel * .55) for channel in accent)
    center_xy = (160, 160)
    diameter = 146

    def ring(radius, color, width=1):
        brush.ellipse((160-radius, 160-radius, 160+radius, 160+radius), outline=color, width=width)

    if theme in ('cover', 'pixel', 'cabinet'):
        edge = 46 if theme == 'cover' else 55
        brush.rounded_rectangle((edge,edge,320-edge,320-edge), radius=12, fill=(*style.disc,245), outline=(*light,210), width=3)
        if theme == 'pixel':
            for n in range(13):
                x = 55+n*17
                for y in (49,263):
                    brush.rectangle((x,y,x+9,y+9), fill=(*(light if n%2 else accent),230))
        if theme == 'cabinet':
            brush.rounded_rectangle((65,44,255,276), radius=13, outline=(*light,200), width=3)
            for y in (60,255):
                for x in (83,237):
                    brush.ellipse((x-3,y-3,x+3,y+3), fill=(*light,230))
        if theme != 'cabinet':
            side = 210 if theme == 'cover' else 174
            canvas.paste(ImageOps.fit(cover, (side, side), Image.Resampling.LANCZOS), ((320-side)//2,(320-side)//2))
            diameter = 0
    elif theme == 'tape':
        brush.rounded_rectangle((36,101,284,219),radius=12,fill=(*style.disc,245),outline=(*light,255),width=3)
        brush.rounded_rectangle((63,129,257,190),radius=8,fill=(22,25,31,245),outline=(*accent,255),width=2)
        for x in (99,221):
            brush.ellipse((x-22,137,x+22,181),outline=(*light,240),width=6)
        center_xy, diameter = (160, 160), 73
    elif theme in ('landscape', 'moon', 'stage'):
        if theme == 'stage':
            for x in range(39,130,15):
                brush.line((x,32,x+11,267),fill=(*accent,130),width=5)
                brush.line((320-x,32,309-x,267),fill=(*accent,130),width=5)
            brush.arc((39,35,281,280),180,360,fill=(*light,210),width=3)
        else:
            for i, line in enumerate((222, 247, 272)):
                points = [(x,line + 14*math.sin(x/42+i) + 7*math.sin(x/19+i)) for x in range(0,321,5)]
                brush.polygon(points+[(320,312),(0,312)],fill=(*(accent if i==0 else style.disc), 160-i*22))
        if theme == 'moon':
            ring(103, (*light,155), 7)
        diameter = 137
    else:
        body = (*style.disc,200)
        if theme == 'crystal':
            body = (*light,105)
        brush.ellipse((44,44,276,276),fill=body,outline=(*light,230),width=2)
        for index, radius in enumerate((80,88,98,107,114)):
            ring(radius, (*light, 120-index*13), 2 if theme=='crystal' else 1)
        if theme in ('ornate','flora','illustrated'):
            for index in range(14):
                angle = index * math.tau / 14
                x, y = 160+114*math.cos(angle), 160+114*math.sin(angle)
                a = 9 if theme=='ornate' else 13
                brush.ellipse((x-a,y-a,x+a,y+a),fill=(*accent,190),outline=(*light,210),width=2)
        if theme in ('glow','illustrated'):
            for i, radius in enumerate((90,108,124)):
                brush.arc((160-radius,160-radius,160+radius,160+radius), i*82, i*82+213, fill=(*light,235-i*30), width=4-i)
        if theme == 'record':
            diameter = 120
            brush.line((253,70,225,122), fill=(*light,240), width=5)

    side = round(320 * scale)
    x, y = (round(center[0] - side / 2), round(center[1] - side / 2))
    # Keep most lighting above the information and controls even on the 3:5 card.
    image.alpha_composite(canvas.resize((side, side), Image.Resampling.LANCZOS), (x, y))
    if diameter:
        artwork_center = (x + center_xy[0]*scale, y + center_xy[1]*scale)
        _circle_cover(image, cover, artwork_center, round(diameter * scale))


def draw_player_theme(image, cover, x, y, size, style):
    """Draw the theme around the current song's artwork, above its controls."""
    width, height = image.size
    center = (x + size / 2, y + size / 2)
    unit = width / 400
    layer = Image.new('RGBA', (400, round(height / unit)))
    draw = ImageDraw.Draw(layer)
    cx, cy = (value / unit for value in center)
    radius = size / unit / 2
    if style.theme == 'coast':
        horizon = cy + radius * .21
        shore = cy + radius * .65
        bottom = min(layer.height - 1, round(cy + radius * 1.42))
        for row in range(bottom):
            if row < horizon:
                t = row / max(1, horizon)
                color = (48 + round(111*t), 121 + round(72*t), 184 + round(22*t))
            elif row < shore:
                t = (row - horizon) / (shore - horizon)
                color = (27 + round(48*t), 108 + round(63*t), 152 + round(22*t))
            else:
                color = (196, 142, 73)
            alpha = round(255 * min(1, (bottom - row) / max(1, bottom - shore)))
            draw.line((0, row, 400, row), fill=(*color, alpha))
        for shift, color in [(0, (240, 232, 192, 210)), (10, (245, 196, 124, 235)), (19, (215, 158, 82, 190))]:
            wave = [(column, shore + shift + 9 * math.sin(column / 70)) for column in range(0, 401, 4)]
            draw.line(wave, fill=color, width=4)
        r = radius * .61
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(255, 238, 190, 220), width=5)
    elif style.theme == 'collage':
        tile_size = round(size / 3)
        for row in range(3):
            for column in range(3):
                tile = ImageOps.fit(cover, (tile_size, tile_size), Image.Resampling.LANCZOS,
                                    centering=(column / 2, row / 2)) if (row + column) % 2 == 0 else None
                if tile is None:
                    palette = ((39, 100, 64), (131, 155, 77), (77, 124, 90), (89, 76, 57))
                    tile = Image.new('RGB', (tile_size, tile_size), palette[(row * 3 + column) % len(palette)])
                    leaf = ImageDraw.Draw(tile)
                    s = tile_size
                    leaf.polygon([(0,s), (s*.48,s*.2), (s*.72,s*.38), (s*.55,s*.75)], fill=(183, 198, 114))
                    leaf.line((0,s,s*.67,s*.3), fill=(226, 218, 168), width=max(1,s//35))
                edge = max(1, round(width / 500))
                image.paste(tile.crop((edge, edge, tile_size-edge, tile_size-edge)),
                            (x + column * tile_size + edge, y + row * tile_size + edge))
        return
    elif style.theme == 'halo':
        for scale, color in [(.96,(31,72,255,145)),(.79,(102,69,255,185)),(.65,(156,146,255,235))]:
            r = radius * scale
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=17)
        layer = layer.filter(ImageFilter.GaussianBlur(10))
        draw = ImageDraw.Draw(layer)
        for scale, start, color in [(.58,20,(202,204,255,225)),(.67,105,(99,148,255,210)),(.74,240,(210,118,245,200))]:
            r = radius * scale
            draw.arc((cx-r, cy-r, cx+r, cy+r), start, start+244, fill=color, width=3)
        for dx, dy, r in [(-.67,-.36,2),(.72,.27,2),(.42,-.66,3),(-.46,.63,2)]:
            px, py = cx + radius*dx, cy + radius*dy
            draw.ellipse((px-r,py-r,px+r,py+r),fill=(228,214,255,225))
    else:
        _catalog_artwork(image, cover, center, size, style)
        return
    image.alpha_composite(layer.resize(image.size, Image.Resampling.LANCZOS))
    _circle_cover(image, cover, center, round(size * (.57 if style.theme == 'coast' else .49)))
