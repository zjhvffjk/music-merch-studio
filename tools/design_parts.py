"""封面衍生设计引擎 —— 从一张专辑封面，长出配套的全部部件素材。

不搜网络图（耗时且被污染），改为**基于封面做编辑设计的衍生**：
    palette  ← 从封面提色板
    mood     ← 从封面饱和度/亮度推断（dreamy / energetic / melancholic）
    style    ← 从封面边缘密度推断（minimalist / retro / bold）或手动指定
    每个部件 ← 由上述设计语言驱动版式与质感

这是小红书「album cover + genre + mood + style」公式的工程化变体：
第 1 个词 album cover 从「生成目标」变成「参考源」。

依赖：PIL / numpy / fonts（可选，缺失则退回默认字体）
import 无副作用。
"""

import math
import os
import re
import time

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import spec_minicd as SP

try:
    from PIL import ImageFont

    import fonts

    def _font(size, bold=False):
        try:
            p = fonts.find_bold() if bold else fonts.find_regular()
            return ImageFont.truetype(p, max(8, int(size)))
        except Exception:
            return ImageFont.load_default()

except Exception:  # pragma: no cover
    from PIL import ImageFont

    def _font(size, bold=False):
        return ImageFont.load_default()


# ---------------- 设计语言提取 ----------------
def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def ink_on(color, dark=(24, 24, 26), light=(250, 250, 250)):
    return dark if lum(color) > 140 else light


def dim_ink(ink, bg, k=0.62):
    """次要文字色：主墨色与背景混合 —— 保证可读但不与标题抢戏。

    直接拿封面调色板的 accent 当序号色会出事：accent 可能很暗，
    落在深底上等于隐形（实测 Jay 深灰底上的序号几乎看不见）。
    """
    return tuple(int(ink[i] * k + bg[i] * (1 - k)) for i in range(3))


def palette(im, n=6):
    """提色板：量化取主要色，按占比降序。"""
    q = im.convert("RGB").resize((80, 80)).quantize(colors=n, method=2)
    pal = q.getpalette()
    cnt = sorted(q.getcolors(80 * 80) or [], reverse=True)
    out = []
    for c, i in cnt:
        out.append(tuple(pal[i * 3:i * 3 + 3]))
    return out or [(128, 128, 128)]


def _sat(c):
    mx, mn = max(c), min(c)
    return 0 if mx == 0 else (mx - mn) / mx


def read_design(cover_im, n=6, safe_bands=None):
    """读一张封面 -> 设计语言 dict。

    ``safe_bands=(top, bottom)``：配件取景的**可用横带**（归一化 y）。
    封面自带标题占了顶部 30% 就传 ``(0.30, 1.0)`` —— 取景只会落在带内，
    标题不会被裁进补件（见 ``safe_crop``；``overlay_bands`` 给建议值）。
    不传 = 整幅取景。
    """
    small = cover_im.convert("RGB").resize((120, 120))
    pal = palette(small, n)
    main = pal[0]

    arr = np.asarray(small).astype(float) / 255.0
    mx, mn = arr.max(2), arr.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    bright = arr.mean()

    # mood 三档
    if sat.mean() < 0.18 and bright < 0.45:
        mood = "melancholic"
    elif sat.mean() > 0.35 or bright > 0.62:
        mood = "energetic"
    else:
        mood = "dreamy"

    # style：边缘密度 -> 极简 or 密集
    edges = np.asarray(small.convert("L").filter(ImageFilter.FIND_EDGES)).astype(float)
    dens = (edges > 40).mean()
    if dens < 0.05:
        style = "minimalist"
    elif dens > 0.22:
        style = "bold"
    else:
        style = "retro"

    # 深浅两个主色，用于渐变
    dark = tuple(int(main[i] * 0.42) for i in range(3))
    deep = tuple(int(main[i] * 0.68 + 12) for i in range(3))
    accent = pal[1] if len(pal) > 1 else tuple(255 - main[i] for i in range(3))

    return {"palette": pal, "main": main, "dark": dark, "deep": deep,
            "accent": accent, "mood": mood, "style": style,
            "ink": ink_on(main), "bright": bright, "sat": float(sat.mean()),
            "safe_bands": tuple(safe_bands) if safe_bands else (0.0, 1.0)}


def vgrad(size, top, bottom):
    """垂直渐变底。"""
    w, h = size
    arr = np.zeros((h, w, 3), np.uint8)
    for y in range(h):
        t = y / max(1, h - 1)
        arr[y, :] = [int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)]
    return Image.fromarray(arr, "RGB")


def grain(im, amt=10, seed=0):
    """细颗粒（retro 质感）。"""
    rng = np.random.default_rng(seed)
    a = np.asarray(im).astype(np.int16)
    a = a + rng.normal(0, amt, a.shape).astype(np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def fit_font(d, text, box_w, start, bold=False, min_s=8):
    """在给定宽度内自动缩字号（先降号，再省略）。"""
    s = start
    while s > min_s:
        f = _font(s, bold)
        if d.textlength(text, font=f) <= box_w:
            return f, text
        s = max(min_s, int(s * 0.92))
    f = _font(min_s, bold)
    while text and d.textlength(text + "…", font=f) > box_w:
        text = text[:-1]
    return f, (text + "…" if text else "")


def vtext(im, text, xy, size, fill, bold=False, spacing=1.12):
    """竖排文字（中文/拉丁都按字排），返回占用高度。"""
    d = ImageDraw.Draw(im)
    f = _font(size, bold)
    x, y = xy
    step = int(size * spacing)
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        y += step
    return max(0, y - xy[1])


def barcode(d, x, y, w, h, seed=0):
    """画一个 EAN-13 风格的装饰条码（非真实可扫，但视觉正确）。"""
    rng = np.random.default_rng(abs(seed) % (2 ** 31))
    d.rectangle([x - 3, y - 3, x + w + 3, y + h + 3], fill=(255, 255, 255))
    cx, guard = x, max(1, int(w * 0.012))
    while cx < x + w - guard:
        bw = int(rng.integers(1, 4)) * guard
        if cx + bw > x + w:
            bw = x + w - cx
        if rng.random() > 0.42:
            d.rectangle([cx, y, cx + bw - 1, y + h], fill=(0, 0, 0))
        cx += bw + guard
    f = _font(max(7, int(h * 0.20)))
    tag = "%012d" % (rng.integers(1, 10 ** 12))
    d.text((x, y + h + 3), tag[:4], font=f, fill=(0, 0, 0))
    d.text((x + w * 0.30, y + h + 3), tag[4:8], font=f, fill=(0, 0, 0))
    d.text((x + w * 0.62, y + h + 3), tag[8:], font=f, fill=(0, 0, 0))


# ---------------- 部件：盘面 ----------------
def design_disc(cover, d_px, hole_px, D, album="", artist=""):
    """CD 碟面：封面裁圆 + 同心读取沟槽 + 扇形高光 + 内环 + 中心孔。

    三个关键判断（都是踩过坑换来的）：
    1. 沟槽必须是**乘性暗环**。用 ImageDraw 画白线会变成"白蜘蛛网"——
       浅色封面上尤其廉价。暗环才是真实 CD 读面的样子。
    2. 高光用 cos^8 窄峰做**两道扇形**，而不是 4 个宽扇区：宽扇区会把
       整个盘面糊成一片白，窄扇形才像灯光下的一道光带。
    3. 内圈与最外圈都要处理（透明内环 + 外沿暗边），否则圆片像贴纸。
    """
    ss = 3
    big = d_px * ss
    base = cover.convert("RGB").resize((big, big), Image.LANCZOS)

    cc = np.arange(big) - big / 2.0 + 0.5
    yy, xx = np.meshgrid(cc, cc, indexing="ij")
    rr = np.sqrt(xx ** 2 + yy ** 2)
    ang = np.arctan2(yy, xx)
    r0 = rr / (big / 2.0)

    arr = np.asarray(base).astype(np.float32) / 255.0

    # 1) 同心读取沟槽：乘性暗环。真实沟槽是**密而淡**的细纹，
    #    稀而深会变成"摩尔纹"（早期版本用白线画环，直接变成蜘蛛网）。
    gro = 0.5 + 0.5 * np.cos(2.0 * np.pi * r0 * 34.0)
    gmask = ((r0 > 0.30) & (r0 < 0.95)).astype(np.float32)
    arr *= (1.0 - 0.075 * gro * gmask)[..., None]

    # 2) 两道柔和的扇形高光（光带）
    fan = np.cos(2.0 * (ang - 0.9)) ** 8
    band = np.exp(-((r0 - 0.66) ** 2) / (2 * 0.30 ** 2))
    spec = (fan * band * 0.58)
    arr = arr + (1.0 - arr) * spec[..., None]

    # 3) 外沿暗边（CD 边缘高光/暗边）
    rim = np.exp(-((r0 - 0.965) ** 2) / (2 * 0.022 ** 2))
    arr *= (1.0 - 0.45 * rim)[..., None]

    # 4) 内圈：聚碳酸酯透明区，偏冷灰
    inner = np.clip((0.24 - r0) / 0.10, 0, 1)
    arr = arr * (1 - inner[..., None]) + np.array([0.62, 0.63, 0.66]) * inner[..., None]
    arr = np.clip(arr, 0, 1)

    im = Image.fromarray((arr * 255).astype(np.uint8), "RGB")

    # 圆形遮罩 + 抗锯齿
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).ellipse([0, 0, big - 1, big - 1], fill=255)
    im.putalpha(m)
    im = im.resize((d_px, d_px), Image.LANCZOS)

    out = Image.new("RGB", (d_px, d_px), (255, 255, 255))
    out.paste(im, (0, 0), im)

    # 中心孔（Ø5mm）
    c = d_px / 2.0
    ImageDraw.Draw(out).ellipse([c - hole_px / 2, c - hole_px / 2,
                                 c + hole_px / 2, c + hole_px / 2], fill=(255, 255, 255))
    return out


# ---------------- 部件：封面背面（内页）----------------
def design_inner(cover, w, h, D, album="", artist="", tracks=None):
    """封面背面：封面去色压暗作底 + 专辑信息区块。

    真专辑的内页通常不是封面原图，而是**同一套视觉语言的弱化版** ——
    所以这里用封面做底再压暗降饱和，天然保持同源感。
    """
    base = ImageOps_like(cover, w, h)
    base = ImageEnhance.Color(base).enhance(0.35)
    base = ImageEnhance.Brightness(base).enhance(0.42)
    if D["style"] == "minimalist":
        base = base.filter(ImageFilter.GaussianBlur(w / 90))
    if D["style"] == "retro":
        base = grain(base, 9, seed=7)

    over = base.copy()
    d = ImageDraw.Draw(over)
    pad = max(8, int(w * 0.055))

    # 半透明信息板，保证文字可读（不依赖封面明暗）
    by = int(h * 0.40)
    plate = Image.new("RGBA", (w, h - by), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rectangle([0, 0, w, h - by],
                                    fill=(0, 0, 0, 122))
    over.paste(plate, (0, by), plate)

    fg = (248, 248, 248)
    if album:
        f, t = fit_font(d, album, w - pad * 2, int(h * 0.115), bold=True)
        d.text((pad, by + int(h * 0.025)), t, font=f, fill=fg)
    if artist:
        f, t = fit_font(d, artist, w - pad * 2, int(h * 0.068))
        d.text((pad, by + int(h * 0.155)), t, font=f, fill=(206, 206, 206))

    # 曲目列表（单列；左半只有 41mm 宽，排两列会挤）
    if tracks:
        tf = _font(max(9, int(h * 0.043)))
        lh = int(tf.size * 1.36)
        ty = by + int(h * 0.255)
        for i, s in enumerate(tracks[:9], 1):
            d.text((pad, ty), "%02d" % i, font=tf, fill=(176, 176, 182))
            f2, t2 = fit_font(d, s, w - pad * 2 - int(w * 0.11), tf.size)
            d.text((pad + int(w * 0.10), ty), t2, font=f2, fill=(232, 232, 232))
            ty += lh
            if ty + lh > h - pad // 2:
                break
    return over


def ImageOps_like(im, w, h):
    """等比填满后居中裁切（保证不变形）。"""
    r = max(w / im.width, h / im.height)
    nw, nh = max(1, int(im.width * r)), max(1, int(im.height * r))
    im = im.convert("RGB").resize((nw, nh), Image.LANCZOS)
    return im.crop(((nw - w) // 2, (nh - h) // 2, (nw - w) // 2 + w, (nh - h) // 2 + h))


# ---------------- 部件：封底 ----------------
def design_back(cover, w, h, D, album="", artist="", tracks=None, seed=0):
    """封底：主色渐变底 + 曲目双列 + 条码 + 版权行。

    这是信息量最大的一件，版式按 style 变：
      minimalist → 大量留白、细分隔线
      retro      → 颗粒 + 双线边框
      bold       → 顶部粗色块 + 高对比
    """
    if D["style"] == "minimalist":
        bg = Image.new("RGB", (w, h), (250, 250, 250))
    else:
        bg = vgrad((w, h), D["deep"], D["dark"])
    base = bg.copy()
    d = ImageDraw.Draw(base)
    pad = max(6, int(w * 0.045))
    ink = ink_on(palette(base, 4)[0])

    if D["style"] == "retro":
        d.rectangle([pad // 2, pad // 2, w - pad // 2, h - pad // 2],
                    outline=ink, width=1)
        d.rectangle([pad // 2 + 3, pad // 2 + 3, w - pad // 2 - 3, h - pad // 2 - 3],
                    outline=ink, width=1)

    # 顶部标题区
    if D["style"] == "bold":
        d.rectangle([0, 0, w, int(h * 0.20)], fill=D["dark"])
        top_ink = ink_on(D["dark"])
    else:
        top_ink = ink
    ty = int(h * 0.035)
    if album:
        f, t = fit_font(d, album, w - pad * 2, int(h * 0.115), bold=True)
        d.text((pad, ty), t, font=f, fill=top_ink)
    if artist:
        f, t = fit_font(d, artist, w - pad * 2, int(h * 0.065))
        d.text((pad, ty + int(h * 0.13)), t, font=f, fill=top_ink)

    # 曲目：双列
    if tracks:
        cols = 2 if len(tracks) > 6 else 1
        per = math.ceil(len(tracks) / cols)
        colw = (w - pad * 2 - int(w * 0.03)) // cols
        tf0 = max(8, int(h * 0.052))
        lh = int(tf0 * 1.42)
        y0 = int(h * 0.30)
        num_fill = dim_ink(ink, palette(base, 3)[0])
        for ci in range(cols):
            cx = pad + ci * (colw + int(w * 0.03))
            cy = y0
            for k in range(per):
                idx = ci * per + k
                if idx >= len(tracks):
                    break
                if cy + lh > int(h * 0.80):
                    break
                f2, tt = fit_font(d, tracks[idx], colw - int(w * 0.075), tf0)
                d.text((cx, cy), "%02d" % (idx + 1), font=_font(tf0), fill=num_fill)
                d.text((cx + int(w * 0.065), cy), tt, font=f2, fill=ink)
                cy += lh
    else:
        # 没曲目时别重复专辑名（顶部已经写过了），给一行版权小字 ——
        # 真 CD 封底都有这行，比空着或重复都自然。
        line = "℗ & © JVR Music International Ltd.   All rights reserved."
        f, t = fit_font(d, line, w - pad * 2, int(h * 0.046))
        d.text((pad, int(h * 0.44)), t, font=f,
               fill=dim_ink(ink, palette(base, 3)[0], 0.5))

    # 条码（右下）
    bw = int(w * 0.30)
    bh = int(h * 0.13)
    barcode(d, int(w - pad - bw), int(h - pad - bh - int(h * 0.055)),
            bw, bh, seed=seed)
    return base


# ---------------- 部件：内盘底 ----------------
def design_tray(cover, w, h, D, album="", artist=""):
    """内盘底：托盘 tleмин 面的那一版 —— 主色 + 大号排版 + 封面小图。"""
    base = vgrad((w, h), D["main"], D["dark"])
    if D["style"] == "retro":
        base = grain(base, 8, seed=3)
    d = ImageDraw.Draw(base)
    pad = max(6, int(w * 0.06))
    ink = ink_on(palette(base, 4)[0])

    # 封面小图（左上），让托盘一眼认出是哪张专辑
    ts = int(h * 0.42)
    th = ImageOps_like(cover, ts, ts)
    base.paste(th, (pad, pad))

    tx = pad
    ty = pad + ts + int(h * 0.07)
    if album:
        f, t = fit_font(d, album, w - pad * 2, int(h * 0.155), bold=True)
        d.text((tx, ty), t, font=f, fill=ink)
        ty += int(f.size * 1.15)
    if artist:
        f, t = fit_font(d, artist, w - pad * 2, int(h * 0.09))
        d.text((tx, ty), t, font=f, fill=ink)

    # 底部装饰条
    d.rectangle([pad, int(h * 0.90), pad + int(w * 0.26), int(h * 0.90) + max(2, int(h * 0.014))],
                fill=D["accent"])
    return base


# ---------------- 部件：书脊 / 侧标 ----------------
def design_spine(w, h, D, album="", artist=""):
    """书脊窄条：竖排专辑名 + 歌手，环绕 dado 色块。"""
    base = Image.new("RGB", (w, h), D["dark"])
    d = ImageDraw.Draw(base)
    ink = ink_on(D["dark"])
    fs = int(min(w * 0.62, h * 0.055))
    fs = max(7, fs)
    y = int(h * 0.10)

    txt = (album or "") + ("  " + artist if artist else "")
    if txt.strip():
        f = _font(fs, bold=True)
        # 逐字竖排，超长自动截断
        avail = int(h * 0.80)
        chars, used = [], 0
        for ch in txt:
            if used + fs * 1.12 > avail:
                chars.append("…")
                break
            chars.append(ch)
            used += fs * 1.12
        cy = y
        for ch in chars:
            cw = d.textlength(ch, font=f)
            d.text(((w - cw) / 2, cy), ch, font=f, fill=ink)
            cy += int(fs * 1.12)
    else:
        cy = 0

    # 底部色块（真书脊常见的出版社标记位）
    d.rectangle([0, int(h * 0.93), w, h], fill=D["accent"])
    return base


def design_flap(w, h, D, cover=None, seed=0):
    """左/右封（折进去的耳页）：纯色 + 细装饰。"""
    if cover is not None and D["style"] != "minimalist":
        base = ImageOps_like(cover, w, h)
        base = ImageEnhance.Color(base).enhance(0.5)
        base = ImageEnhance.Brightness(base).enhance(0.7)
        base = base.filter(ImageFilter.GaussianBlur(w / 12))
    else:
        base = vgrad((w, h), D["deep"], D["dark"])
    if D["style"] == "retro":
        base = grain(base, 7, seed=seed)
    d = ImageDraw.Draw(base)
    d.rectangle([0, int(h * 0.08), w, int(h * 0.08) + max(1, int(h * 0.006))],
                fill=(*ink_on(palette(base, 3)[0]), ))
    return base


# ==========================================================================
#  v2 —— 整案设计：对齐**实体唱片设计规范**
# ==========================================================================
# v1 的部件是「色块 + 文字」，像工程图/PPT；实体唱片设计的做法是：
#   ① 照片复用（同一个 MV 的别的镜头）而不是纯色块
#   ② 三种以上字体角色共存 + 大标题带字距
#   ③ 手写体引言 + 落款
#   ④ 真实版权的信息层（厂牌 / © 行 / 版权声明 / 带数字的 EAN-13）
# v2 把这四件事补齐。所有函数**只依赖封面 + 元信息 + 可选歌词**，无网络依赖。
# ==========================================================================

try:
    import typo as _typo
except Exception:  # pragma: no cover
    _typo = None


def _t(role, size, text=None):
    if _typo is None:
        return _font(size, bold=role in ("heavy", "serif"))
    return _typo.font(role, size, text)


def tracked(d, xy, text, f, fill, tracking=0.0, anchor_x="left", limit=None):
    if _typo is None:
        d.text(xy, text, font=f, fill=fill)
        return d.textlength(text, font=f)
    return _typo.tracked(d, xy, text, f, fill, tracking, anchor_x, limit)


def fit_tracked(d, text, box_w, start, role, tracking=0.0, min_s=7):
    if _typo is None:
        return fit_font(d, text, box_w, start)
    return _typo.fit_tracked(d, text, box_w, start, role, tracking, min_s)


def wrap_tracked(d, text, f, box_w, tracking=0.0):
    """按宽度折行（见 typo.wrap_tracked）。typo 缺失时退化为原样一行。"""
    if _typo is None:
        return [str(text)]
    return _typo.wrap_tracked(d, text, f, box_w, tracking)


def kinsoku(lines):
    """行首/行尾禁则（见 typo._kinsoku）。typo 缺失时原样返回。"""
    if _typo is None or not hasattr(_typo, "_kinsoku"):
        return list(lines)
    return _typo._kinsoku(list(lines))


def hairline(d, x1, y, x2, fill, width=1):
    d.rectangle([int(x1), int(y), int(x2), int(y) + max(1, int(width)) - 1], fill=fill)


def phonogram(d, x, y, size, fill, thickness=None):
    """画 ℗（录音版权符号）—— **矢量画，不用文字**。

    实测本机 msyh / msyhbd / NotoSerifSC / Bahnschrift / 楷体 **全部没有 U+2117 字形**，
    直接打字会变成豆腐块（□ & © 周杰伦）。真唱片封底必然有这行，
    所以自己画一个：圆圈 + 内嵌 P。返回占用宽度。
    """
    r = max(3, int(size * 0.42))
    tw = thickness or max(1, int(size * 0.075))
    cy = y + int(size * 0.56)
    cx = x + r
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=tw)
    f = _t("display", int(size * 0.66))
    pw = d.textlength("P", font=f)
    d.text((cx - pw / 2.0, cy - size * 0.36), "P", font=f, fill=fill)
    return r * 2 + int(size * 0.14)


# ---------------- 照片复用 ----------------

def _local_bg(g, k):
    """沿 **x 方向**的大核中值 = 横向缓慢变化的背景（字迹会被抹掉）。"""
    H, W = g.shape
    pad = max(1, int(k) // 2)
    row = np.pad(g, ((0, 0), (pad, pad)), mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(row, k, axis=1)   # (H, W+1, k)
    return np.median(win, axis=2)[:, :W]


def _ink_mask(small, k=71, thresh=34):
    """封面上的「叠加墨迹」掩膜：局部背景被打破的像素。"""
    g = np.asarray(small.convert("L")).astype(np.float32)
    res = np.abs(g - _local_bg(g, k))
    return res > thresh


def _thin_ratio(mask):
    """「细笔画」占比 —— **判别字与照片内容的关键**。

    字的笔画细：把掩膜腐蚀一下（MinFilter）就整根消失，剩下极少。
    照片主体（头发、花、书页）是一整块，腐蚀后还留一大片核心。
    所以 thin = 1 - 腐蚀后残留 / 原面积：
      笔画 ≈ 1.0；大块 ≈ 0.2 以下。
    """
    if mask.sum() == 0:
        return 0.0
    m = Image.fromarray((mask * 255).astype(np.uint8), "L")
    core = np.asarray(m.filter(ImageFilter.MinFilter(5))) > 128
    return float(1.0 - core.sum() / max(1, mask.sum()))


def overlay_bands(cover, n=200):
    """**建议**封面自带标题占的横带 —— 返回 ``(top, bottom)``，供**人工复核**。

    🔴 重要：这是**建议值，不是自动判据**。实测「这条带里有没有字」在统计上
    分不开：花的边缘/头发的轮廓和字的笔画，在「局部背景残差」「细笔画占比」
    「横向段数」这几个量上完全重叠（花 0.77~0.97 vs 字 0.88~1.00）。
    所以正确用法是：本函数给一个保守建议 → 用 ``tools/audit_covers.py``
    把掩膜叠在原图上**用眼睛确认** → 把结论写进 ``safe_bands``（CLI
    ``--safe-bands`` 或 albums.json 的 ``safe_bands`` 字段）。

    返回 ``(0.0, 1.0)`` 表示没检出／建议整幅取景。
    """
    S = cover.convert("RGB").resize((n, n), Image.LANCZOS)
    mask = _ink_mask(S, k=max(15, n * 36 // 100))
    top, bottom = 0.0, 1.0
    zones = (("top", 0.0, 0.42, "top"), ("bottom", 0.72, 1.0, "bottom"))
    for _name, lo, hi, side in zones:
        y0, y1 = int(lo * n), int(hi * n)
        sub = mask[y0:y1]
        if sub.sum() < 120:
            continue
        if _thin_ratio(sub) < 0.42:
            continue
        cols = np.where(sub.any(0))[0]
        if len(cols) == 0:
            continue
        span = (cols.max() - cols.min() + 1) / float(n)
        share = sub.mean()
        if span < 0.34 or not (0.008 <= share <= 0.55):
            continue
        rows = np.where(sub.any(1))[0]
        if len(rows) < 4:
            continue
        # 收紧到实际有墨迹的行范围，再留一点余量
        if side == "top":
            top = min(1.0, (y0 + rows.max() + 1) / float(n) + 0.015)
        else:
            bottom = max(0.0, (y0 + rows.min()) / float(n) - 0.015)
    if top >= bottom - 0.15:          # 上下都判成字，说明判据被骗了，退回整幅
        return 0.0, 1.0
    return round(top, 3), round(bottom, 3)


def safe_crop(cover, w, h, D=None, fx=0.5, fy=None, zoom=None, bands=None):
    """取景时**自动避开封面自带的标题带**（「字压两遍」的根治办法）。

    可用区 = 垂直方向 ``[safe_top, safe_bottom]``（来自 ``D["safe_bands"]``），
    在可用区里取**最大的**能放下 ``w:h`` 的窗口；``zoom`` / ``fy`` 只作偏好，
    绝不会突破可用区。
    """
    cov = cover.convert("RGB")
    cw, ch = cov.size
    if bands is None:
        bands = _bands_of(cover, D)
    t, b = bands
    avail = max(0.20, b - t)
    aspect = w / float(h)
    sy = min(avail, 1.0 / aspect)          # 最大可用高度（x 方向也要放得下）
    if zoom and zoom > 1.0:                # 偏好更紧的取景才采纳
        sy = max(0.18, min(sy, sy / float(zoom)))
    sx = min(1.0, sy * aspect)
    cy = (t + b) / 2.0 if fy is None else fy
    cy = min(max(cy, t + sy / 2.0), b - sy / 2.0)
    cy = min(max(cy, sy / 2.0), 1.0 - sy / 2.0)
    cx = min(max(fx, sx / 2.0), 1.0 - sx / 2.0)
    box = (int(round((cx - sx / 2) * cw)), int(round((cy - sy / 2) * ch)),
           int(round((cx + sx / 2) * cw)), int(round((cy + sy / 2) * ch)))
    box = (max(0, box[0]), max(0, box[1]), min(cw, box[2]), min(ch, box[3]))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        box = (0, 0, cw, ch)
    return cov.crop(box).resize((int(w), int(h)), Image.LANCZOS)


def _bands_of(cover, D=None):
    """从设计语言里取 ``(safe_top, safe_bottom)``；没收过就退回「整幅取景」。"""
    if isinstance(D, dict):
        got = D.get("safe_bands")
        if isinstance(got, (tuple, list)) and len(got) == 2:
            return (float(got[0]), float(got[1]))
    return (0.0, 1.0)


def focus_crop(cover, w, h, fx=0.5, fy=0.5, zoom=1.0):
    """从封面里取一个「别的镜头」：焦距点 + 放大倍数。

    ⚠️ 只看焦距点的老接口，**不避让封面自带标题**。新代码请用 ``safe_crop``；
    这个保留给明确知道自己在裁什么的场景。
    """
    cov = cover.convert("RGB")
    cw, ch = cov.size
    r = max(w / cw, h / ch) * max(1.0, float(zoom))
    nw, nh = max(w, int(round(cw * r))), max(h, int(round(ch * r)))
    im = cov.resize((nw, nh), Image.LANCZOS)
    left = int(round(fx * nw - w / 2.0))
    top = int(round(fy * nh - h / 2.0))
    left = max(0, min(nw - w, left))
    top = max(0, min(nh - h, top))
    return im.crop((left, top, left + w, top + h))


def grade(im, sat=1.0, bright=1.0, contrast=1.0, blur=0.0, tint=None, tint_k=0.0):
    """统一色阶。全套部件用同一组参数 → 整案像同一次调色。"""
    out = im.convert("RGB")
    if blur > 0:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    if sat != 1.0:
        out = ImageEnhance.Color(out).enhance(sat)
    if bright != 1.0:
        out = ImageEnhance.Brightness(out).enhance(bright)
    if contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(contrast)
    if tint is not None and tint_k > 0:
        a = np.asarray(out).astype(np.float32)
        a = a * (1.0 - tint_k) + np.array(tint, np.float32) * tint_k
        out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    return out


def scrim(im, bottom=0.0, top=0.0, left=0.0, right=0.0, power=1.7, veil=0.0):
    """边缘压暗（文字压在照片上时保证可读，同时保留照片感）。

    ``veil`` 是整体压暗量；四方向是渐变压暗，用来给文字让出对比度。
    """
    w, h = im.size
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    mask = np.full((h, w), float(veil), np.float32)
    if bottom:
        mask = np.maximum(mask, bottom * np.linspace(0, 1, h, dtype=np.float32)[:, None] ** power)
    if top:
        mask = np.maximum(mask, top * np.linspace(1, 0, h, dtype=np.float32)[:, None] ** power)
    if left:
        mask = np.maximum(mask, left * np.linspace(1, 0, w, dtype=np.float32)[None, :] ** power)
    if right:
        mask = np.maximum(mask, right * np.linspace(0, 1, w, dtype=np.float32)[None, :] ** power)
    a *= (1.0 - np.clip(mask, 0, 0.96))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def luma(im):
    a = np.asarray(im.convert("L").resize((64, 64))).astype(np.float32)
    return float(a.mean() / 255.0)


def normalize_bright(im, target=0.58, lo=0.55, hi=2.2):
    """把画面亮度归一到一个固定水平 —— 深色封面不发黑、浅色封面不糊。"""
    cur = max(1e-3, luma(im))
    k = float(np.clip(target / cur, lo, hi))
    return ImageEnhance.Brightness(im).enhance(k)


def normalize_gamma(im, target=0.60, lo=0.60, hi=2.60, sat=1.08):
    """用**伽马**提亮，而不是线性乘。

    🔴 线性乘会把「深色高饱和」封面推成黄绿：范特西（红蓝脸）实测提亮 1.45× 后
    红→橙黄，整个盘面色彩失真。伽马只抬中间调，色相基本不动，再补一点饱和度即可。
    """
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    cur = float(np.clip(a.mean(), 0.02, 1.0))
    # 🔴 指数方向：要「提亮」需要 1/g < 1 → g > 1。所以 g = log(cur)/log(target)
    #    （写反成 log(target)/log(cur) 时，暗图会算出 0.44 → 被夹到 1.0 → 一点都不亮）
    g = float(np.clip(math.log(cur) / math.log(target), lo, hi))
    a = np.power(a, 1.0 / g)
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGB")
    if sat != 1.0:
        out = ImageEnhance.Color(out).enhance(sat)
    return out


# ---------------- 真实 EAN-13 ----------------
_L_CODE = ["0001101", "0011001", "0010011", "0111101", "0100011",
           "0110001", "0101111", "0111011", "0110111", "0001011"]
_G_CODE = ["0100111", "0110011", "0011011", "0100001", "0011101",
           "0111001", "0000101", "0010001", "0001001", "0010111"]
_R_CODE = ["1110010", "1100110", "1101100", "1000010", "1011100",
           "1001110", "1010000", "1000100", "1001000", "1110100"]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
           "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_check(d12):
    s = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(d12))
    return str((10 - s % 10) % 10)


def make_ean(seed, prefix="697"):
    """由 seed 稳定生成 13 位 EAN（697 = 中国大陆前缀，与参考图一致）。"""
    import zlib
    h = zlib.crc32(str(seed).encode("utf-8"))
    d12 = (prefix + str(h).rjust(9, "0")[:9])[:12]
    return d12 + ean13_check(d12)


def ean13_bits(d13):
    """13 位 → 95 模块的 0/1 串（标准 EAN-13 编码）。"""
    bits = "101"
    for ch, p in zip(d13[1:7], _PARITY[int(d13[0])]):
        bits += (_L_CODE if p == "L" else _G_CODE)[int(ch)]
    bits += "01010"
    for ch in d13[7:13]:
        bits += _R_CODE[int(ch)]
    bits += "101"
    return bits


def ean13(d, x, y, w, h, code, ink=(0, 0, 0), paper=(255, 255, 255), quiet=0.06):
    """画**真实可编码**的 EAN-13（95 模块 + 数字分组），不是随机竖条。

    随机竖条一眼假；按标准编码画，配上数字分组，就有了「实体商品」的可信度。
    """
    code = "".join(c for c in str(code) if c.isdigit())
    if len(code) < 13:
        code = make_ean(code)
    code = code[:13]
    bits = ean13_bits(code)
    w, h = int(w), int(h)
    q = max(3, int(w * quiet))
    bw = w - 2 * q
    mw = bw / 95.0
    bh = int(h * 0.74)
    guard_extra = int(bh * 0.13)
    fs = max(7, int(h * 0.215))

    # 白底（静区）必须连数字行一起盖住，避免数字落在深色封底上。
    if paper is not None:
        d.rectangle([x - q, y - int(h * 0.06), x + w + q,
                     y + bh + int(fs * 1.55)], fill=paper)

    for i, b in enumerate(bits):
        if b != "1":
            continue
        x0 = int(round(x + q + i * mw))
        x1 = int(round(x + q + (i + 1) * mw))
        x1 = max(x1, x0 + 1)
        is_guard = i < 3 or 45 <= i <= 49 or i >= 92
        hh = bh + (guard_extra if is_guard else 0)
        d.rectangle([x0, y, x1 - 1, y + hh], fill=ink)

    # 数字分组 1-6-6（与参考图同款：左 1 位、中 6 位、右 6 位）
    f = _t("num", fs)
    dy = y + bh + int(h * 0.055)
    w1 = d.textlength(code[0], font=f)
    d.text((x + q - w1 - max(1, int(mw * 1.2)), dy), code[0], font=f, fill=ink)
    for grp, ctr in ((code[1:7], q + 24 * mw), (code[7:13], q + 71 * mw)):
        gw = d.textlength(grp, font=f)
        d.text((x + ctr - gw / 2.0, dy), grp, font=f, fill=ink)
    return code


# ---------------- 手写引言 / 落款 ----------------
_QUOTE_POOL = {
    "dreamy": ["把心事交给旋律，让它替我慢慢说",
               "月亮不睡，我也不睡",
               "云朵停在耳边，替我把话说完"],
    "energetic": ["把音量推到最大，世界就安静了",
                  "心跳是最诚实的节拍器",
                  "年轻的声音，盖不住也拦不下"],
    "melancholic": ["有些话说不出口，就唱成了歌",
                    "难过就放到 B 面，别占 A 面的轨",
                    "雨停之前，先把这首歌唱完"],
    "retro": ["老歌里的那束光，照到今天还没熄",
              "磁带会老，旋律不会",
              "旧时光转一圈，又回到副歌"],
    "minimalist": ["少一点声音，听懂的人自然会懂",
                   "留白不是空，是给耳朵留的位置",
                   "一首歌，记住一个字就够了"],
    "bold": ["不必解释，听见的人会明白",
             "不解释，是最响的宣言",
             "把颜色调到最满，把话说得最直"],
}

_BAD_LINE = ("作词", "作曲", "编曲", "制作人", "录音", "混音", "母带", "和声",
             "吉他", "贝斯", "鼓", "钢琴", "弦乐", "OP", "SP", "纯音乐",
             "未经", "版权", "出品", "监制", "统筹", "发行", "企划")


def pick_quote(lyric_lines, D=None):
    """从真实歌词里挑一句当「专辑金句」：取重复次数最多的那句（副歌记忆点）。

    取不到就按 mood/style 回退到通用句 —— 但宁可回退也不能空着，
    手写引言是整案里最提气的一件。
    """
    from collections import Counter
    pool = []
    for ln in (lyric_lines or []):
        t = str(ln).strip()
        if not (6 <= len(t) <= 22):
            continue
        if any(b in t for b in _BAD_LINE):
            continue
        if t.startswith("[") or ":" in t or "：" in t:
            continue
        pool.append(t)
    if pool:
        c = Counter(pool)
        top = c.most_common(3)
        top.sort(key=lambda kv: (-kv[1], len(kv[0])))
        return top[0][0]
    if D:
        key = D.get("mood") or D.get("style") or "dreamy"
        pool = _QUOTE_POOL.get(key) or _QUOTE_POOL["dreamy"]
        if isinstance(pool, str):     # 兼容旧的单句写法
            pool = [pool]
        # 无歌词回退以前固定取第一句 → 同 mood 的多张专辑批量时金句全部雷同。
        # 现在用封面主色亮度做种子在池内挑选：跨专辑自然错开，单专辑可复现。
        seed = sum(int(c) for c in (D.get("main") or (128, 128, 128))[:3])
        return pool[seed % len(pool)]
    return _QUOTE_POOL["dreamy"][0]


def hand_text(im, xy, text, size, fill, tracking=1.0, anchor_x="left",
              angle=0.0, shadow=(0, 0, 0, 120), offset=(1, 1), limit=None):
    """手写体文字（可带轻微倾斜与投影）。返回实际宽度。

    手写体（中文=楷体 / 纯拉丁=Inkfree）是「设计稿感」的关键零件：
    印刷体排不出「作者亲笔」的味道，而实体唱片内页几乎都有这么一句。
    """
    role = "hand" if any("\u2e80" <= c <= "\u9fff" for c in text) else "hand_latin"
    f = _t(role, size, text)
    x, y = xy
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    wd = tracked(measure, (x, y), text, f, fill, tracking, anchor_x, limit)
    sx = x if anchor_x == "left" else (x - wd if anchor_x == "right" else x - wd / 2.0)

    lay = Image.new("L", im.size, 0)
    tracked(ImageDraw.Draw(lay), (sx, y), text, f, 255, tracking, "left", limit)
    if angle:
        lay = lay.rotate(angle, resample=Image.BICUBIC, center=(sx, y))
        sx, y = sx + offset[0], y + offset[1]   # 视觉上仅作稳定化，不影响内容

    layers = []
    if shadow:
        sh = Image.new("RGBA", im.size, tuple(shadow[:3]) + (0,))
        a = lay.point(lambda v: int(v * (shadow[3] / 255.0)))
        sh.putalpha(a.transform(im.size, Image.AFFINE, (1, 0, -offset[0], 0, 1, -offset[1])))
        layers.append(sh)
    fg = Image.new("RGBA", im.size, tuple(fill[:3]) + (0,))
    fg.putalpha(lay)
    layers.append(fg)
    for L in layers:
        if im.mode == "RGBA":
            im.alpha_composite(L)
        else:
            im.paste(L, (0, 0), L)
    return wd


# ---------------- 版式零件 ----------------
def label_line(d, x, y, h, company, artist, ink, dim):
    """厂牌 / 版权信息行 —— 真封底必须有，缺了就是「设计稿」不是「唱片」。"""
    f = _t("heavy", max(7, int(h * 0.46)))
    cx = x
    word = (company or "JVR MUSIC").upper()[:14]
    d.text((cx, y + int(h * 0.24)), word, font=f, fill=ink)
    cx += d.textlength(word, font=f) + h * 0.5
    fs = max(7, int(h * 0.28))
    f2 = _t("sans", fs, artist)
    adv = phonogram(d, cx, y + int(h * 0.26), fs, dim)
    d.text((cx + adv, y + int(h * 0.30)), " & © " + (artist or ""), font=f2, fill=dim)
    return cx + adv


def _label_credit(artist="", company="", release_year=""):
    """封底版权归属的固定首行。

    厂牌名来自专辑数据或用户确认的厂牌字段；法律声明不由 AI 或自由文本决定。
    """
    label = (company or "发行公司待确认").strip()
    year = str(release_year or "").strip()
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        year = time.strftime("%Y")
    return "© %s %s." % (year, label)


def _copy_lines(d, w, artist="", company="", custom="", release_year=""):
    """封底固定的版权归属行与两行权利声明。"""
    # w 是版权区本身的 26mm 宽，不是整个 49mm 封底宽。按版权区的物理比例
    # 换算后，300DPI 为 8px（约 0.68mm），刚好让最长声明完整可读。
    fs = max(3, int(round((float(w) / SP.COPYRIGHT["widthMm"]) * 0.68)))
    f = _t("sans", fs, artist)
    # 归属始终来自专辑发行数据（或用户确认的厂牌），避免旧项目的自由文本污染生产信息。
    rest = _label_credit(artist, company, release_year)
    a = wrap_tracked(d, rest, f, w, 0.2)
    b = [
        "All rights reserved. Unauthorized copying, reproduction, hiring, lending,",
        "public performance and broadcasting prohibited.",
    ]
    return fs, f, a, b


def copyright_block(d, x, y, w, ink, dim, artist="", album="", company="", custom="", release_year=""):
    """固定版权归属行 + 两行英文权利声明。

    🔴 英文声明是**固定长句**，窄列里必须**折行**。用 ``tracked(limit=w)`` 是截断，
    印出来就是 "public p…" 这种半截话 —— 实体封底上真就是折两行的。
    返回整块实际高度，方便调用方从底部反推排版位置。
    """
    fs, f, l1, l2 = _copy_lines(d, w, artist, company, custom, release_year)
    step = max(4, int(round(fs * 1.55)))
    for i, ln in enumerate(l1):
        tracked(d, (x, y + i * step), ln, f, dim, 0.2, "left")
    yy = y + len(l1) * step
    for i, ln in enumerate(l2):
        tracked(d, (x, yy + i * step), ln, f, dim, 0.2, "left")
    return (yy - y) + len(l2) * step


def copyright_height(d, w, artist="", company="", custom="", release_year=""):
    fs, f, l1, l2 = _copy_lines(d, w, artist, company, custom, release_year)
    return (len(l1) + len(l2)) * max(4, int(round(fs * 1.55)))


def _track_record(value, fallback_rank):
    """统一曲目记录：程序可接收搜索结果的名次/名称/时长，也兼容旧版纯歌名。"""
    if isinstance(value, dict):
        title = str(value.get("title") or value.get("name") or value.get("song") or "").strip()
        duration = str(value.get("duration") or value.get("dur") or value.get("time") or "").strip()
        try:
            rank = int(value.get("rank") or fallback_rank)
        except Exception:
            rank = fallback_rank
        return {"rank": max(1, rank), "title": title, "duration": duration}
    return {"rank": fallback_rank, "title": str(value or "").strip(), "duration": ""}


def normalized_tracks(tracks):
    return [r for r in (_track_record(v, i) for i, v in enumerate(tracks or [], 1)) if r["title"]]


def choose_back_layout(requested, tracks, D=None):
    """封底排版的确定性推荐，绝不随机。

    单列为少曲目与横向留白服务；双列为 8 首以上、长歌名或极简留白视觉保留可读性。
    """
    requested = str(requested or "auto").strip().lower()
    if requested in ("single", "double"):
        return requested
    rows = normalized_tracks(tracks)
    count = len(rows)
    longest = max([len(r["title"]) for r in rows] or [0])
    average = sum(len(r["title"]) for r in rows) / max(1, count)
    minimalist = bool((D or {}).get("style") == "minimalist")
    return "double" if count >= 8 or longest >= 12 or (count >= 6 and (average >= 8 or minimalist)) else "single"


def tracklist(d, x, y, w, h, tracks, ink, dim, cols=1, lead=None, max_lines=None,
              max_lead=None, show_duration=True):
    """固定序号 / 歌名 / 时长三栏曲目表，支持单列和双列。"""
    tracks = normalized_tracks(tracks)
    if not tracks:
        return 0
    cols = max(1, int(cols))
    per = math.ceil(len(tracks) / cols)
    avail = h
    lh = int(min([v for v in (lead or h, avail / max(1, per), max_lead or h) if v]))
    fs = max(7, int(lh * 0.60))
    fn = _t("num", max(7, int(fs * 0.86)))
    gap = int(w * 0.045) if cols > 1 else 0
    colw = (w - gap * (cols - 1)) / cols
    duration_w = int(colw * 0.23) if show_duration else 0
    number_w = max(1, int(d.textlength("00", font=fn) * 1.7))
    used = 0
    for ci in range(cols):
        cx = int(x + ci * (colw + gap))
        cy = y
        for k in range(per):
            idx = ci * per + k
            if idx >= len(tracks) or (max_lines and k >= max_lines) or cy + lh > y + h:
                break
            row = tracks[idx]
            tracked(d, (cx, cy + int(lh * 0.10)), "%02d" % row["rank"], fn, dim, 0.4)
            title_x = cx + number_w
            title_w = int(colw - number_w - duration_w - (int(colw * 0.04) if show_duration else 0))
            f2, t2 = fit_tracked(d, row["title"], max(4, title_w), fs, "sans", 0.2)
            d.text((title_x, cy), t2, font=f2, fill=ink)
            if show_duration and row["duration"]:
                fd = _t("num", max(6, int(fs * 0.90)))
                tracked(d, (cx + int(colw), cy + int(lh * 0.10)), row["duration"], fd, dim, 0.15, "right")
            cy += lh
            used += 1
    return used


def back_cover_track_table(d, panel_w, panel_h, tracks, layout, ink):
    """Golden Reference 封底曲目表：以 49×38mm 封底为唯一坐标系。

    这不是通用的「把文字平均塞进一个盒子」的列表。两种预设共享同一套
    正文字体、墨色和基线；仅曲目的 x 坐标与列数不同：

    * single：01–10 一列，序号／歌名／时长三栏，右侧保留画面与金句。
    * double：01–05／06–10 两列，短中线只覆盖曲目行高，不延伸到标题或版权。

    这样无论封面是深色照片还是浅色插画，信息的印刷节奏都不会随封面或
    曲目数漂移。所有数值先以 mm 写出，再换算到实际输出像素。
    """
    rows = normalized_tracks(tracks)
    if not rows:
        return 0

    sx, sy = panel_w / SP.BACK_PANEL_W, panel_h / SP.BACK_PANEL_H
    px = lambda mm: int(round(mm * sx))
    py = lambda mm: int(round(mm * sy))

    # Golden Reference：歌曲正文、序号与时长为同一套常规印刷黑，
    # 数字仅用窄体以保持列对齐，不再为序号另取灰色。
    # 三栏（序号 / 歌名 / 时长）是同一张曲目表，不是三个文字层级：
    # 固定同一字号、同一字高、同一正文墨色。歌名过长只截短，不缩字号。
    track_size = max(9, py(1.28))
    song_font = _t("sans", track_size, "曲目")
    num_font = _t("sans", track_size, "00:00")
    text_y = py(10.0)

    def draw_row(row, x_mm, right_mm, y):
        num_x = px(x_mm)
        title_x = px(x_mm + 3.05)
        right_x = px(right_mm)
        # 预留给时长的宽度是固定的，歌名再长也只在自己的栏位内缩放。
        duration = row.get("duration") or ""
        duration_w = d.textlength(duration, font=num_font) if duration else 0
        title_w = max(px(5.0), int(right_x - title_x - duration_w - px(0.85)))
        title_font = song_font
        title = row["title"]
        # 不缩字号。只有原始歌名本身超过固定歌名栏时才截短加省略号；
        # 之前复用 fit_tracked 会拿“原文 + …”测试宽度，导致刚好放得下的
        # Always Online 也被错误截成 Always Online…。
        if d.textlength(title, font=title_font) > title_w:
            while title and d.textlength(title + "…", font=title_font) > title_w:
                title = title[:-1]
            title = (title + "…") if title else ""
        d.text((num_x, y + py(0.10)), "%02d" % row["rank"], font=num_font, fill=ink)
        d.text((title_x, y), title, font=title_font, fill=ink)
        if duration:
            tracked(d, (right_x, y + py(0.10)), duration, num_font, ink, 0.0, "right")

    if layout == "double":
        # 固定成 01–05 / 06–10；少于十首时仍按前后两组顺序排，不重新均分。
        left, right = rows[:5], rows[5:10]
        row_pitch = py(2.42)
        for index, row in enumerate(left):
            draw_row(row, 3.70, 21.70, text_y + index * row_pitch)
        for index, row in enumerate(right):
            draw_row(row, 25.20, 45.25, text_y + index * row_pitch)

        mid_x = px(23.20)
        d.line([(mid_x, text_y - py(0.35)),
                (mid_x, text_y + max(0, min(5, len(left))) * row_pitch - py(0.42))],
               fill=ink, width=1)
        return min(10, len(rows))

    # 单列版：标准三栏，右缘固定在 29mm；29–49mm 交给金句和装饰视觉。
    row_pitch = py(2.02)
    for index, row in enumerate(rows[:10]):
        draw_row(row, 3.70, 29.00, text_y + index * row_pitch)
    return min(10, len(rows))


def design_notes(D, album="", artist="", tracks=None, has_lyrics=False):
    """给展示板用的「设计思路」文案 —— 由设计语言真实推导，不是写死的套话。"""
    mood_cn = {"dreamy": "梦幻柔和", "energetic": "明亮有力", "melancholic": "内敛低沉"}
    style_cn = {"minimalist": "极简留白", "retro": "复古颗粒", "bold": "强对比大色块"}
    n = len([t for t in (tracks or []) if str(t).strip()])
    out = [
        "以封面主色系（%s）贯穿全套部件，保证摆在一起是同一套视觉语言。"
        % "#%02x%02x%02x" % tuple(D.get("main", (128, 128, 128))[:3]),
        "整体调性定为「%s + %s」：内页、封底沿用封面照片的不同裁切，"
        "不引入外来素材，天然同源。"
        % (mood_cn.get(D.get("mood"), "自然"), style_cn.get(D.get("style"), "规整")),
        "标题用衬线体加字距、曲目用无衬线、序号与条码数字用 DIN 窄体，"
        "手写金句与落款单独一层 —— 三种字体角色拉开层级。",
        "封底按实体唱片规范补齐厂牌、录音版权与著作权声明行、版权声明与可编码 EAN-13 条码%s。"
        % ("，歌词页内容取自该专辑真实歌词" if has_lyrics else ""),
    ]
    if n:
        out.append("本张专辑共 %d 首，曲目表按 %s列排布，行距随曲目数自适应。"
                   % (n, "两" if n > 8 else "单"))
    return out


# ==========================================================================
#  v2 部件
# ==========================================================================
def _key_grade(D, span=1.0):
    """把封面色阶折成「同一次调色」的公共参数（全套部件共用）。"""
    bright = D.get("bright", 0.5)
    if bright < 0.35:      # 深色封面：提亮 + 稍微降饱和，避免糊成一团黑
        return dict(sat=0.92, bright=1.30 * span, contrast=1.06)
    if bright > 0.68:      # 浅色封面：压一点，避免文字压不住
        return dict(sat=0.98, bright=0.86 * span, contrast=1.08)
    return dict(sat=1.0, bright=1.0 * span, contrast=1.05)


def design_back2(cover, w, h, D, album="", artist="", tracks=None, seed=0,
                 quote=None, company="", barcode_code="", copyright_text="", release_year="",
                 back_layout="auto", copy_settings=None):
    """封底（v2）：整幅照片做底 + 左侧压暗信息栏 + 曲目 + 金句 + 版权层 + EAN-13。

    版式取实体唱片的通用解法：**照片通铺、信息分区**。硬切左右两半会显得像
    两张图拼的；用「渐变压暗让出对比度」才能真正像一张封底。
    """
    w, h = int(w), int(h)
    g = _key_grade(D)
    key = D.get("main", (128, 128, 128))
    tracks = normalized_tracks(tracks)
    layout = choose_back_layout(back_layout, tracks, D)

    # 🔴 取景避开封面**自带的标题字**：封面标题/歌手名几乎都压在上缘，
    #    fy 偏小会把「周杰伦」这种字切一半带进来，看着像失误。压到画面中部取。
    base = grade(safe_crop(cover, w, h, D, fx=0.55, fy=0.53, zoom=1.30),
                 sat=g["sat"] * 1.0, bright=g["bright"], contrast=g["contrast"])
    base = scrim(base, left=0.70, bottom=0.46, top=0.08, power=1.6, veil=0.10)
    d = ImageDraw.Draw(base)

    # 封底是一个独立的印刷版面：所有生产文字共用同一墨色，不能让标题、
    # 序号、时长各自从封面色板取色。深色照片上用暖白墨，浅色封面会自然
    # 选择深墨；由统一的 scrim 保证可读性。
    local_luma = lum(tuple(np.asarray(base.convert("RGB").resize((1, 1)))[0, 0]))
    ink = (248, 247, 245) if local_luma < 142 else (28, 29, 31)
    pad = max(5, int(w * 0.048))
    sx, sy = w / SP.BACK_PANEL_W, h / SP.BACK_PANEL_H
    px = lambda mm: int(round(mm * sx))
    py = lambda mm: int(round(mm * sy))

    # 两个 Golden Reference 共用的标题块：左起 4mm，上距 2.45mm，
    # 标题／歌手／细线与曲目首行的关系固定。仅标题可因中英文字形变化。
    title_x, title_y, title_w = px(3.70), py(2.45), px(42.0)
    # 标题与歌手是两个独立的字体角色。不能因为内容是中文就绕过工作台选择，
    # 否则用户在字体库换了毛笔体，封底却仍然显示旧的默认字体。
    f, t = fit_tracked(d, album or "", title_w, py(2.82), "serif", 0.55,
                      min_s=max(10, py(1.60)))
    tracked(d, (title_x, title_y), t, f, ink, 0.55, "left", title_w)
    artist_y = title_y + py(3.50)
    f2, t2 = fit_tracked(d, artist or "", px(25.0), py(1.63), "artist", 0.15,
                         min_s=max(9, py(1.15)))
    tracked(d, (title_x, artist_y), t2, f2, ink, 0.15, "left", px(25.0))
    rule_y = py(8.42)
    hairline(d, title_x, rule_y, px(22.0), ink, 1)

    # 两套 Golden Reference 预设：仅信息区发生变化，49×38mm 封底和版权/条码坐标不变。
    # 单列保留右侧横向留白；双列将 10 首稳定拆为 01–05 / 06–10。
    if tracks:
        back_cover_track_table(d, w, h, tracks, layout, ink)
    else:
        # 🔴 以前这里再印一遍 artist：标题块 + 这行 + 金句落款 = 无曲目时歌手名
        #    出现三次（用户实测指出的重复）。实体封底这个位置通常印的是
        #    「COMPACT DISC DIGITAL AUDIO」格式标识 —— 印这个，不再重复人名。
        f3, t3 = fit_tracked(d, "COMPACT DISC DIGITAL AUDIO", px(25.0), py(1.30), "sans", 1.2)
        tracked(d, (title_x, py(10.0)), t3, f3, ink, 1.2, "left", px(25.0))

    # 版权区严格锁在封底局部坐标 (1.5, 31, 26, 5) mm；不参与封面构图运算。
    # 三行文字在这个区域内贴底对齐，和右侧条码的底边保持同一视觉基线。
    cr = SP.copyright_rect_px(w, h)
    copy_h = copyright_height(d, cr["w"], artist, company, copyright_text, release_year)
    copy_y = cr["y"] + max(0, cr["h"] - copy_h)
    copyright_block(d, cr["x"], copy_y, cr["w"], ink, ink, artist, album,
                    company, copyright_text, release_year)

    # 手写金句：压在右侧亮部的中下方（左上角留出照片的呼吸）
    # 双列预设把整块横向空间交给两组曲目，避免金句压住第 06–10 首。
    # 双列的左下英文概念区来自用户/Concept 数据，不再沿用 Golden Reference 示例句。
    concept = (copy_settings or {}).get("conceptCopy") or {}
    primary = str(concept.get("primaryChinese") or "").strip()
    tag = str(concept.get("secondaryEnglish") or concept.get("shortEnglish") or "").strip()
    # English editorial copy uses distinct safe zones for the two tracklist presets.
    # It is always wrapped as a compact two-line block; never one long line over tracks/copyright.
    if tag:
        if layout == "single":
            tag_x, tag_y, tag_w, tag_align = px(46.0), py(15.0), px(13.0), "right"
        else:
            tag_x, tag_y, tag_w, tag_align = px(3.7), py(26.3), px(18.0), "left"
        tag_lines = editorial_tag_lines(d, tag, tag_w, max(8, py(1.16)))
        for line_no, line in enumerate(tag_lines):
            _angled_tag(base, (tag_x, tag_y + line_no * py(1.52)), line, max(8, py(1.16)),
                        ink, tag_align, tag_w, angle=_copy_angle(copy_settings, D))
        d = ImageDraw.Draw(base)
    # Chinese primary copy is optional on the single-column back. Default leaves the right safe zone
    # to the English editorial block above the barcode, matching the approved Golden Reference.
    q = primary if (layout == "single" and bool((copy_settings or {}).get("showBackChineseCopy"))) else ""
    if q:
        qs = max(9, int(h * 0.058))
        # 单列曲目时，三栏列表固定占至 x=29mm；金句必须从约 33mm
        # 才开始，不能借由自动换行侵入时长列。
        qw = px(13.5)
        lines = _wrap_hand(d, q, qw, qs, 2)      # 限 2 行：多了会跟曲目栏抢视线
        step = int(qs * 1.34)
        y0 = int(h * 0.585) - len(lines) * step
        for i, ln in enumerate(lines):
            hand_text(base, (w - pad, y0 + i * step), ln, qs, ink, 1.2, "right",
                      angle=_copy_angle(copy_settings, D), shadow=(0, 0, 0, 170))
        d = ImageDraw.Draw(base)
        fq = _t("artist", max(8, int(qs * 0.56)), artist)
        tracked(d, (w - pad, y0 + len(lines) * step + int(h * 0.014)),
                "— %s" % (artist or album or ""), fq, ink, 1.0, "right")

    # 条码：由 Mini CD 规格真源以「封底 49×38mm」局部坐标固定定位。
    # 不从整条 111.2mm 展开图推坐标，亦不允许 AI 或构图逻辑自行挪动。
    rect = SP.barcode_rect_px(w, h)
    bx, by, bw, bh = rect["x"], rect["y"], rect["w"], rect["h"]
    code = "".join(c for c in str(barcode_code or "") if c.isdigit())
    if len(code) >= 12:
        code = code[:12] + ean13_check(code[:12])
    else:
        code = make_ean(seed)
    ean13(d, bx, by, bw, bh, code,
          quiet=0.075, paper=(250, 250, 250))

    return base


def _wrap_hand(d, text, box_w, size, max_lines=2):
    """手写引言按宽度手工折行（手写体没有 CJK 断行，得自己来）。

    🔴 折完要**重新配平**：按宽度贪心折总会把最后一行剩成单字
    （「把音量推到最大，世界就安静 / 了」—— 明信片上实测到的丑陋断行）。
    末行 ≤2 字时改成按字数均分。
    """
    f = _t("hand" if any("\u2e80" <= c <= "\u9fff" for c in text) else "hand_latin", size, text)
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > box_w and cur:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                return lines
        else:
            cur += ch
    if cur:
        lines.append(cur)
    if len(lines) > 1 and 0 < len(lines[-1]) <= 2:
        n, total = len(lines), len(text)
        per = (total + n - 1) // n
        bal = [text[i * per:(i + 1) * per] for i in range(n)]
        bal = [b for b in bal if b]
        if len(bal) <= max_lines and all(
                d.textlength(b, font=f) <= box_w for b in bal):
            lines = bal
    # 🔴 逐字断必须再过一遍行首禁则，否则金句会印成
    #    「把音量推到最大 / ，世界就安静了」（实测踩过）。
    return kinsoku(lines[:max_lines])


def _copy_text(copy_settings):
    """Extract one coherent concept copy set. Artwork never draws these words."""
    c = (copy_settings or {}).get("conceptCopy") or {}
    return (str(c.get("primaryChinese") or "").strip(),
            str(c.get("secondaryEnglish") or "").strip(),
            str(c.get("shortEnglish") or "").strip())


def _copy_preset(copy_settings):
    mode = str((copy_settings or {}).get("resolvedLayout") or
               (copy_settings or {}).get("copyLayout") or "editorial").lower()
    return "minimal" if mode in ("minimal", "b", "copy-b") else "editorial"


def _tag(draw, xy, text, size, color, align="left", width=None):
    """Small program-rendered English copy. Empty text deliberately stays empty."""
    if not text:
        return
    font, fitted = fit_tracked(draw, text.upper(), width or 99999, max(7, int(size)), "display", 1.15)
    tracked(draw, xy, fitted, font, color, 1.15, align, width)


def _copy_angle(copy_settings, D=None):
    """Angle is a chosen editorial treatment, never a substitute for a typeface."""
    setting = str((copy_settings or {}).get("copyAngle") or "none")
    # Reference direction: left side lower, right side higher (counter-clockwise in Pillow).
    if setting in ("upRight", "auto", "right"): return 3.0
    if setting in ("downRight", "left"): return -3.0
    return 0.0


def editorial_tag_lines(draw, text, width, size, max_lines=2):
    """将英文概念文案保持为参考版式中的紧凑两行 Editorial block。"""
    text = str(text or "").strip().upper()
    if not text:
        return []
    words = text.split()
    # 不能让 "KEEP MOVING WITH THE LIGHT" 这样的概念文案变成一根横条；
    # 优先按词数均衡拆分，画面比按剩余像素挤成 "...WITH THE / LIGHT" 更稳定。
    if len(words) > 2:
        mid = max(1, len(words) // 2)
        return [" ".join(words[:mid]), " ".join(words[mid:])]
    face = _t("editorial", max(7, int(size)), text)
    return wrap_tracked(draw, text, face, int(width), 0.85)[:max_lines]


def disc_tag_lines(draw, text, preset, width, size):
    """CD 盘面英文文案：A 是右下两行，B 是左下的窄列多行。"""
    text = str(text or "").strip().upper()
    if not text:
        return []
    words = text.split()
    if preset == "minimal" and len(words) > 2:
        # B 的英文是窄列标语，不允许变成一根横线。按 4 行以内均衡拆词。
        groups = min(4, len(words))
        base, rem = divmod(len(words), groups)
        lines, at = [], 0
        for i in range(groups):
            take = base + (1 if i < rem else 0)
            lines.append(" ".join(words[at:at + take])); at += take
        return lines
    return editorial_tag_lines(draw, text, width, size, max_lines=2)

def _angled_tag(im, xy, text, size, color, align="left", width=None, angle=-3.0):
    """Render English editorial copy with a real serif face and a small print-safe rotation."""
    if not text:
        return
    d = ImageDraw.Draw(im)
    font, fitted = fit_tracked(d, text.upper(), width or im.width, max(7, int(size)), "editorial", 1.05)
    x, y = xy
    # Measure on a disposable canvas: do not paint an upright copy before rotating it.
    measure = ImageDraw.Draw(Image.new("L", (1, 1), 0))
    measured = tracked(measure, (0, 0), fitted, font, 255, 1.05, "left", width)
    left = x if align == "left" else (x - measured if align == "right" else x - measured / 2)
    mask = Image.new("L", im.size, 0)
    tracked(ImageDraw.Draw(mask), (left, y), fitted, font, 255, 1.05, "left", width)
    mask = mask.rotate(angle, resample=Image.BICUBIC, center=(x, y))
    fg = Image.new("RGBA", im.size, tuple(color[:3]) + (0,))
    fg.putalpha(mask)
    if im.mode == "RGBA": im.alpha_composite(fg)
    else: im.paste(fg, (0, 0), fg)


def design_disc2(cover, d_px, hole_px, D, album="", artist="", company="", copy_settings=None):
    """盘面（v2）：先做**亮度归一**再去糊 —— v1 最大的毛病就是盘面发灰发闷。

    实体盘面的观感 = 主图够亮够透 + 银色聚碳酸酯内环 + 细密勾槽 +
    一道窄扇形高光 + 外沿暗边。缺了「银色内环」就会像贴纸；
    内环画得**太大太白**又会变成「白甜甜圈」（实测踩过）。
    """
    # 盘面沿用原封面的干净白底画面：不再人为加入磨砂、凹槽、高光或塑料膜效果。
    # 只裁到花与花瓶上半部，避开原封面下方已经烘焙的标题。
    ss = 3
    big = max(240, int(d_px) * ss)
    preset = _copy_preset(copy_settings)
    # 两套模板只改变主视觉的左右位置，纵向取景一致。
    art = safe_crop(cover, big, big, D,
                    fx=(0.66 if preset == "editorial" else 0.34), fy=0.45, zoom=1.75)
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).ellipse([0, 0, big - 1, big - 1], fill=255)
    art.putalpha(m)
    out = Image.new("RGB", (int(d_px), int(d_px)), (255, 255, 255))
    art = art.resize((int(d_px), int(d_px)), Image.LANCZOS)
    out.paste(art, (0, 0), art)

    # 两个盘面模板只固定构图位置；字体则分别读取工作台的标题、中文、英文选择。
    # A / Editorial：花材左、标题右、英文右下（两行以内）。
    # B / Minimal：花材右、标题左、英文左下（窄列多行）。
    preset = _copy_preset(copy_settings)
    dtext = ImageDraw.Draw(out)
    if preset == "editorial":
        title_x, title_y, title_w, title_align = int(d_px * 0.655), int(d_px * 0.405), int(d_px * 0.285), "left"
        tag_x, tag_y, tag_w, tag_align = int(d_px * 0.645), int(d_px * 0.715), int(d_px * 0.270), "left"
        artist_gap = 1.38
        tag = _copy_text(copy_settings)[2] or _copy_text(copy_settings)[1]
    else:
        title_x, title_y, title_w, title_align = int(d_px * 0.135), int(d_px * 0.395), int(d_px * 0.285), "left"
        # B 的窄英文列靠左但上移，保证每一行都留在圆盘安全区内。
        tag_x, tag_y, tag_w, tag_align = int(d_px * 0.100), int(d_px * 0.600), int(d_px * 0.205), "left"
        artist_gap = 1.38
        tag = _copy_text(copy_settings)[1] or _copy_text(copy_settings)[2]

    ink = (36, 33, 30)
    # serif -> 专辑标题选择；artist -> 歌手名字体选择；editorial -> 英文文案选择。
    fs, tt = fit_tracked(dtext, album or "", title_w, max(10, int(d_px * 0.095)),
                         "serif", 0.88, min_s=max(10, int(d_px * 0.050)))
    fs2, tt2 = fit_tracked(dtext, artist or "", title_w, max(8, int(d_px * 0.055)),
                           "artist", 0.45, min_s=max(8, int(d_px * 0.031)))
    tracked(dtext, (title_x, title_y), tt, fs, ink, 0.88, title_align, title_w)
    tracked(dtext, (title_x, title_y + int(fs.size * artist_gap)), tt2, fs2, ink, 0.45, title_align, title_w)

    tag_size = max(7, int(d_px * 0.030))
    for i, line in enumerate(disc_tag_lines(dtext, tag, preset, tag_w, tag_size)):
        ftag, fitted = fit_tracked(dtext, line, tag_w, tag_size, "editorial", 0.80,
                                   min_s=max(6, int(d_px * 0.020)))
        tracked(dtext, (tag_x, tag_y + i * int(tag_size * 1.34)), fitted, ftag, ink,
                0.80, tag_align, tag_w)

    # CD 格式标识固定在中心孔下方；它使用功能字体，不参与标题/文案字体选择。
    mark = "COMPACT\nDISC"
    mark_font = _t("num", max(6, int(d_px * 0.025)), mark)
    mark_y = int(d_px * 0.805)
    for i, line in enumerate(mark.splitlines()):
        tracked(dtext, (d_px / 2.0, mark_y + i * int(mark_font.size * 1.04)), line,
                mark_font, ink, 0.45, "center", int(d_px * 0.18))

    # 中心孔（Ø5mm，打穿）
    c = d_px / 2.0
    ring = max(1, int(d_px * 0.010))
    line = max(1, int(d_px * 0.0035))
    dout = ImageDraw.Draw(out)
    dout.ellipse([line, line, d_px - line - 1, d_px - line - 1], outline=(88, 84, 78), width=line)
    dout.ellipse([c - hole_px / 2 - ring, c - hole_px / 2 - ring,
                  c + hole_px / 2 + ring, c + hole_px / 2 + ring], outline=(105, 100, 94), width=line)
    dout.ellipse([c - hole_px / 2, c - hole_px / 2,
                  c + hole_px / 2, c + hole_px / 2], fill=(255, 255, 255), outline=(105, 100, 94), width=line)
    return out


def design_inner2(cover, w, h, D, album="", artist="", tracks=None, quote=None, copy_settings=None):
    """内页左半（折进盒里的那一面）：整幅写真 + 手写金句 + 落款。

    v1 这里是「压暗的封面 + 一坨曲目」，等于把封面又印了一遍；
    真唱片内页放的是**同一次拍摄的另一张照片**，所以这里改用高倍裁切。
    """
    g = _key_grade(D)
    # 内页有自己独立的主文案。取景上移并收紧，避开原封面下沿自带标题，
    # 防止源图文字和程序排出的文案重叠。
    base = grade(safe_crop(cover, w, h, D, fx=0.38, fy=0.31, zoom=1.72),
                 sat=g["sat"] * 0.86, bright=g["bright"] * 0.96,
                 contrast=g["contrast"] * 1.04,
                 tint=tuple(int(c * 0.55 + 26) for c in D.get("main", (90, 90, 90))),
                 tint_k=0.22)                       # 偏主色的冷调版本
    # 🔴 顶部压暗必须够狠：标题（白色衬线）落在 y≈0.075h 处，top 太小的话
    #    浅色封面（白背景写真）上标题直接隐形。0.24 实测只有 21% 压暗 → 提到 0.42
    #    （同 power 下标题行压暗 ~39%），压到中部才归零，不影响照片主体。
    base = scrim(base, bottom=0.62, top=0.42, power=1.5)
    d = ImageDraw.Draw(base)
    pad = max(4, int(w * 0.075))
    _primary, _secondary, _short = _copy_text(copy_settings)
    q = _primary or quote or pick_quote(None, D)
    if q:
        qs = max(9, int(h * 0.070))
        lines = _wrap_hand(d, q, w - pad * 2, qs, 3)
        y0 = int(h * 0.48)
        for i, ln in enumerate(lines):
            hand_text(base, (pad, y0 + int(i * qs * 1.35)), ln, qs,
                      (250, 250, 248), 1.2, "left", angle=_copy_angle(copy_settings, D), shadow=(0, 0, 0, 160))
        d = ImageDraw.Draw(base)
        if artist:                       # 没填歌手就别印一根孤零零的「—」
            fs = max(8, int(h * 0.062))
            # 内页落款也属于歌手名，跟随「歌手名字体」选择。
            fm = _t("artist", fs, artist)
            tracked(d, (pad, y0 + int(len(lines) * qs * 1.35) + int(h * 0.035)),
                    "— %s" % artist, fm, (222, 224, 228), 1.0, "left")
        # Editorial secondary copy is a separate true-font layer, never generated in artwork.
        # Keep the English tag as a separate baseline layer. Rotating a full-size
        # mask around this lower corner was pulling it up into the artist credit.
        tag_size = max(7, int(h * 0.029))
        tag_y = min(h - int(tag_size * 3.5), y0 + int(len(lines) * qs * 1.35) + int(h * 0.12))
        for i, line in enumerate(editorial_tag_lines(d, _secondary or _short, w - pad * 2, tag_size)):
            _angled_tag(base, (pad, tag_y + i * int(tag_size * 1.48)), line, tag_size,
                        (224, 226, 230), "left", w - pad * 2,
                        angle=_copy_angle(copy_settings, D))
        d = ImageDraw.Draw(base)

    # 顶部极细标题（内页也要能被认出来是哪张）
    fs2, tt = fit_tracked(d, album or "", w - pad * 2, int(h * 0.072), "serif", 1.4)
    tracked(d, (pad, pad), tt, fs2, (250, 250, 248), 1.4, "left", w - pad * 2)
    return base


def design_tray2(cover, w, h, D, album="", artist="", company="", copy_settings=None):
    """内盘底（v2）：浅色纸面 + 居中衬线标题 + 底部照片条。

    托盘不该跟封面抢戏 —— v1 用深色渐变把整块压成一坨糊，摆进盒里像脏了。
    """
    g = _key_grade(D)
    key = D.get("main", (120, 120, 120))
    tint = tuple(int(c * 0.20 + 196) for c in key)      # 由封面主色调出的浅纸色
    base = grade(safe_crop(cover, w, h, D, fx=0.5, fy=0.5, zoom=1.45),
                 sat=0.30, bright=1.0, contrast=1.0, blur=max(1.0, w / 34.0),
                 tint=tint, tint_k=0.66)
    base = scrim(base, veil=0.02, top=0.10, bottom=0.06)
    d = ImageDraw.Draw(base)
    sw = palette(base, 3)[0]
    ink = ink_on(sw)
    dim = dim_ink(ink, sw, 0.62)

    # 底部照片条（3:1 裁切，给块留口气）
    bh = int(h * 0.24)
    ph = grade(safe_crop(cover, w, bh, D, fx=0.5, fy=0.42, zoom=1.40),
               sat=g["sat"], bright=g["bright"], contrast=g["contrast"])
    base.paste(ph, (0, h - ph.height))
    d = ImageDraw.Draw(base)

    pad = max(6, int(w * 0.09))
    _primary, _secondary, _short = _copy_text(copy_settings)
    # Inner tray is a concept-copy panel: title stays a small identifier, copy has the visual lead.
    fs, tt = fit_tracked(d, album or "", w - pad * 2, int(h * 0.060), "serif", 1.4)
    tracked(d, (int(w * 0.5), int(h * 0.12)), tt, fs, dim, 1.4, "center", w - pad * 2)
    q = _primary or album or ""
    qs = max(9, int(h * 0.075))
    lines = _wrap_hand(d, q, int(w * 0.68), qs, 3)
    y0 = int(h * 0.34)
    for i, line in enumerate(lines):
        hand_text(base, (int(w * 0.74), y0 + int(i * qs * 1.34)), line, qs, ink, 1.1, "right", angle=_copy_angle(copy_settings, D))
    d = ImageDraw.Draw(base)
    tag_size = max(7, int(h * 0.032))
    tag_x, tag_y, tag_w = int(w * 0.84), int(h * 0.67), int(w * 0.42)
    for i, line in enumerate(editorial_tag_lines(d, _secondary or _short, tag_w, tag_size)):
        _angled_tag(base, (tag_x, tag_y + i * int(tag_size * 1.48)), line,
                    tag_size, dim, "right", tag_w, angle=_copy_angle(copy_settings, D))
    d = ImageDraw.Draw(base)
    if company:
        # 厂牌是功能信息，固定在底部照片条上方；此前引用了未定义的 ty/fs2，
        # 填写厂牌时会让内盘底渲染失败。
        fL = _t("num", max(6, int(h * 0.038)), company)
        tracked(d, (int(w * 0.5), int(h * 0.735)), company.upper(), fL,
                dim, 1.2, "center", w - pad * 2)
    return base


def design_lyrics(cover, w, h, D, album="", artist="", song="", lines=None,
                  page=1, total=1, company=""):
    """歌词页：浅色纸面 + 衬线标题 + 歌词正文（版面留白按行数自适应）。"""
    g = _key_grade(D)
    key = D.get("main", (128, 128, 128))
    paper = tuple(int(c * 0.18 + 232) for c in key)
    base = Image.new("RGB", (w, h), paper)
    d = ImageDraw.Draw(base)
    ink = (34, 34, 38)
    dim = tuple(int(ink[i] * 0.55 + paper[i] * 0.45) for i in range(3))
    pad = max(6, int(w * 0.075))

    # 顶部：右侧一条照片（同一视觉语言），左侧标题
    ps = int(h * 0.20)
    ph = grade(safe_crop(cover, int(w * 0.30), ps, D, fx=0.48, zoom=1.45),
               sat=g["sat"], bright=max(g["bright"], 0.9), contrast=g["contrast"])
    base.paste(ph, (w - pad - ph.width, pad))
    fs, tt = fit_tracked(d, ("%02d " % page) + (song or album or ""),
                         w - pad * 2 - ph.width - int(w * 0.05),
                         int(h * 0.095), "serif", 1.2)
    tracked(d, (pad, pad + int(h * 0.012)), tt, fs, ink, 1.2, "left")
    f2, t2 = fit_tracked(d, "%s · %s" % (artist or "", album or ""),
                         w - pad * 2 - ph.width, int(h * 0.048), "sans", 0.8)
    tracked(d, (pad, pad + int(h * 0.115)), t2, f2, dim, 0.8, "left")
    y = pad + ph.height + int(h * 0.055)
    hairline(d, pad, y - int(h * 0.028), w - pad, dim, 1)

    body = [l.strip() for l in (lines or []) if l and l.strip()]
    avail = h - y - int(h * 0.11)
    if body:
        # 🔴 关键：行高有**下限**。按 avail/len 均分会把 88 行压到 7px 全糊成一片灰，
        # 宁可只印得下前十几行（真歌词本也是一页一页翻的）。
        lh = int(max(max(9, int(h * 0.040)), min(avail / max(1, len(body)), int(h * 0.085))))
        fs3 = max(8, int(lh * 0.64))
        f3 = _t("sans", fs3)
        for i, ln in enumerate(body):
            yy = y + i * lh
            if yy + lh > h - int(h * 0.09):
                break
            d.text((pad, yy), ln, font=f3, fill=ink)
    else:
        # 🔴 无歌词（单曲 / 纯音乐）时**不能留一大片空白** —— 实测《Six Degrees》
        #    这一格几乎全白，看着像没做完。改成「金句页」：
        #    手写金句（按宽度折行，不截断）+ 落款 + 底部一条同源照片 + 版权行。
        q = pick_quote(None, D) or ""
        qs = max(10, int(h * 0.072))
        fq = _t("hand", qs, q)
        ql = wrap_tracked(d, q, fq, w - pad * 2, 1.5)
        qy = y + int(h * 0.018)
        for i, ln in enumerate(ql[:3]):
            tracked(d, (pad, qy + int(i * qs * 1.36)), ln, fq, ink, 1.5, "left",
                    w - pad * 2)
        qy += int(len(ql[:3]) * qs * 1.36) + int(h * 0.022)
        # 底部一条同源照片，补齐下半个版面
        strip_h = int(h * 0.24)
        st = grade(safe_crop(cover, w - pad * 2, strip_h, D, fx=0.5, zoom=1.5),
                   sat=g["sat"], bright=max(g["bright"], 0.94), contrast=g["contrast"])
        base.paste(st, (pad, h - pad - int(h * 0.055) - strip_h))
        # 🔴 落款（左）与 INSTRUMENTAL 标签（右）同处一条横带：长艺人名会撞上
        #    右侧标签（实测 Jay Chou & Patrick Brasca 叠成「Bra…NSTRUMENTAL」）
        #    —— 先量标签宽，落款 fit 进剩余宽度（字号缩到底才截断）。
        fL0 = _t("num", max(6, int(h * 0.032)))
        tag = ("INSTRUMENTAL / %s" % ("%02d" % total)) if total else ""
        tag_w = (d.textlength(tag, font=fL0) + 1.2 * max(0, len(tag) - 1)) if tag else 0
        fsa, ta = fit_tracked(d, "— %s" % (artist or album or ""),
                              w - pad * 2 - tag_w - int(w * 0.05),
                              max(8, int(h * 0.042)), "sans", 1.4)
        tracked(d, (pad, qy), ta, fsa, dim, 1.4, "left")
        tracked(d, (w - pad, h - pad - int(h * 0.055) - strip_h - int(h * 0.050)),
                tag, fL0, dim, 1.2, "right")
    fL = _t("num", max(6, int(h * 0.032)))
    tracked(d, (pad, h - int(h * 0.065)), "%s / %s" % (page, total), fL, dim, 1.0)
    tracked(d, (w - pad, h - int(h * 0.065)), (company or "JVR MUSIC").upper()[:12],
            _t("sans", fL.size, company), dim, 1.4, "right")
    return base


def design_sleeve(cover, w, h, D, album="", artist="", quote=None, company=""):
    """内封套展开（跨页）：左页写真、右页手写金句 + 落款。

    这是「整案」里最能体现设计完整度的一件，参考图里排第 07/06 位。
    """
    g = _key_grade(D)
    half = w // 2
    left = grade(safe_crop(cover, half, h, D, fx=0.36, fy=0.45, zoom=1.35),
                 sat=g["sat"] * 1.04, bright=g["bright"] * 1.02,
                 contrast=g["contrast"], tint=(58, 68, 94), tint_k=0.12)
    left = scrim(left, bottom=0.30, left=0.10)
    right = grade(safe_crop(cover, w - half, h, D, fx=0.60, fy=0.50, zoom=1.35),
                  sat=g["sat"] * 0.60, bright=g["bright"] * 0.86, contrast=g["contrast"],
                  blur=max(1.0, w / 220.0))
    right = scrim(right, top=0.30, bottom=0.30, right=0.14, veil=0.50)
    base = Image.new("RGB", (w, h))
    base.paste(left, (0, 0))
    base.paste(right, (half, 0))
    d = ImageDraw.Draw(base)

    q = quote or pick_quote(None, D)
    ink = (250, 250, 248)
    if q:
        qs = max(10, int(h * 0.088))
        lines = _wrap_hand(d, q, half - int(w * 0.09), qs, 4)
        y0 = int(h * 0.30)
        for i, ln in enumerate(lines):
            hand_text(base, (half + int(w * 0.045), y0 + int(i * qs * 1.42)), ln,
                      qs, ink, 1.4, "left", shadow=(0, 0, 0, 170))
        d = ImageDraw.Draw(base)
        fs = max(9, int(h * 0.062))
        tracked(d, (half + int(w * 0.045), y0 + int(len(lines) * qs * 1.42) + int(h * 0.05)),
                "— %s" % (artist or album or ""), _t("sans", fs, artist), (216, 218, 222), 1.2, "left")
    fsT, tT = fit_tracked(d, album or "", half - int(w * 0.09), int(h * 0.105), "serif", 1.4)
    tracked(d, (half + int(w * 0.045), int(h * 0.78)), tT, fsT, ink, 1.4, "left")
    hairline(d, half + int(w * 0.045), int(h * 0.755), half + int(w * 0.045) + int(w * 0.10),
             (255, 255, 255), 1)
    fL = _t("sans", max(7, int(h * 0.034)), company)
    tracked(d, (half + int(w * 0.045), int(h * 0.895)),
            (company or "JVR MUSIC").upper()[:14], fL, (190, 192, 198), 1.6, "left")
    return base


def design_postcard(cover, w, h, D, album="", artist="", quote=None):
    """明信片：整幅照片 + 底部白卡条（标题/落款），手写金句压在照片右下。

    🔴 金句**不能画进白卡条**：白条里标题（左）与金句（右）同一行域，
    标题一长就叠字/出界（《Six Degrees》《Something Great》《你是迟来的欢喜》
    三张实测板全部翻车）。白卡条只放 标题+落款，金句归照片区（scrim 压底 + 投影）。
    """
    g = _key_grade(D)
    bw = int(h * 0.30)                        # 白卡条高度
    ph = grade(safe_crop(cover, w, h - bw, D, fx=0.5, zoom=1.28),
               sat=g["sat"] * 1.06, bright=max(g["bright"], 1.0) * 1.06,
               contrast=g["contrast"] * 1.03, tint=(238, 226, 206), tint_k=0.10)
    ph = scrim(ph, bottom=0.30, top=0.06)     # 底部压暗：给手写金句让对比度
    base = Image.new("RGB", (w, h), (246, 245, 243))
    base.paste(ph, (0, 0))
    d = ImageDraw.Draw(base)
    ink = (38, 38, 42)
    dim = (140, 142, 148)
    pad = max(5, int(w * 0.045))
    fs, tt = fit_tracked(d, album or "", w * 0.82, int(bw * 0.34), "serif", 1.4)
    tracked(d, (pad, h - bw + int(bw * 0.22)), tt, fs, ink, 1.4, "left", w * 0.82)
    f2, t2 = fit_tracked(d, artist or "", w * 0.82, int(bw * 0.20), "sans", 1.0)
    tracked(d, (pad, h - bw + int(bw * 0.64)), t2, f2, dim, 1.0, "left", w * 0.82)
    q = quote or pick_quote(None, D)
    if q:
        qs = max(9, int(h * 0.055))
        step = int(qs * 1.34)
        qlines = _wrap_hand(d, q, int(w * 0.56), qs, 2)
        y0 = (h - bw) - int(h * 0.035) - len(qlines) * step
        for i, ln in enumerate(qlines):
            hand_text(base, (w - pad, y0 + i * step), ln, qs,
                      (252, 252, 250), 1.0, "right", shadow=(0, 0, 0, 160))
    return base


def _vertical_spine_text(draw, x, y, text, font, fill, max_h, leading=1.08, bold=False, italic=False,
                         char_styles=None, pixels_per_mm=0):
    """在 4.4mm 窄封内逐字竖排，超出安全高度时以省略号收束。"""
    text = str(text or "").strip()
    if not text:
        return y
    step = max(1, int(font.size * leading))
    limit = int(y + max_h)
    for index, char in enumerate(text):
        char_style = (char_styles or {}).get(str(index), {})
        char_font = font
        if char_style and pixels_per_mm:
            char_font = _spine_font(char_style.get("font"), max(6, int(float(char_style.get("sizeMm") or 1.7) * pixels_per_mm)), char)
        char_fill = _spine_fill(char_style.get("color"), fill) if char_style else fill
        char_bold = str(char_style.get("style") or "") in {"bold", "boldItalic"} if char_style else bold
        char_italic = str(char_style.get("style") or "") in {"italic", "boldItalic"} if char_style else italic
        step = max(1, int(char_font.size * leading))
        if y + step > limit:
            char = "…"
        width = draw.textlength(char, font=char_font)
        px = x - width / 2.0
        if char_italic:
            # 在没有对应 italic 字形的个人字体上保留可见的倾斜效果。
            px += max(1, int(char_font.size * 0.12))
        draw.text((px, y), char, font=char_font, fill=char_fill)
        if char_bold:
            draw.text((px + 1, y), char, font=char_font, fill=char_fill)
        y += step
        if char == "…":
            break
    return y


def _spine_font(font_id, size, text):
    if _typo is not None and font_id and font_id != "auto" and hasattr(_typo, "font_from_id"):
        return _typo.font_from_id(font_id, size, text, "spine")
    return _t("spine", size, text)


def _spine_fill(value, automatic):
    value = str(value or "auto").lower()
    if value == "auto":
        return automatic
    try:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    except (TypeError, ValueError):
        return automatic


def _rotated_spine_label(base, x, y, text, font, fill, max_h):
    """在窄封内放置旋转的英文姓名，保留摄影唱片常用的书脊读法。"""
    text = str(text or "").strip()
    if not text:
        return y
    # 英文横排旋转后沿书脊阅读；过长时缩小到指定安全高度内。
    f = font
    while f.size > 6 and ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(text, font=f) > max_h:
        f = _t("artist", f.size - 1, text)
    width = max(1, int(ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(text, font=f)) + 6)
    layer = Image.new("RGBA", (width, f.size + 8), (0, 0, 0, 0))
    color = tuple(fill[:3]) + (255,)
    ImageDraw.Draw(layer).text((3, 2), text, font=f, fill=color)
    label = layer.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(label, (int(x - label.width / 2), int(y)), label)
    return int(y + label.height)


def spine_overlay(base, variant, album="", artist="", company="", copy_settings=None):
    """给三条 4.4mm 窄封分配不同职责，不生成独立的小海报。

    ``right`` 是外侧识别边：标题和歌手名；``left`` 只保留相邻画面的延续；
    ``left-back`` 面向盒内，以标题或短英文连接内盘底。所有底图由调用方从相邻
    面板延展而来，文字只是最后一层，不会破坏整条展开图的同源关系。
    """
    if base is None:
        return base
    d = ImageDraw.Draw(base)
    w, h = base.size
    swatch = palette(base.convert("RGB"), 3)[0]
    ink = ink_on(swatch)
    dim = dim_ink(ink, swatch, 0.68)
    x = w / 2.0
    top = int(h * 0.075)
    usable = int(h * 0.89)
    templates = (copy_settings or {}).get("spineTemplates") or {}
    zone_key = {"right": "right", "left": "left", "left-back": "leftBack"}.get(variant, "")
    # 格式工具针对当前整条物理侧封：无论沿用固定模板还是改成自定义文字，字体、字号、
    # 加粗、斜体和颜色都必须进入最终成品，不能只在输入了自定义文字时才生效。
    appearance = ((copy_settings or {}).get("spineAppearance") or {}).get(zone_key) or {}
    size_mm = max(0.8, min(2.6, float(appearance.get("sizeMm") or 1.7)))
    size_px = max(7, int(w * size_mm / 4.4))
    title_size_mm = max(0.8, min(2.6, float(appearance.get("titleSizeMm") or size_mm)))
    artist_size_mm = max(0.8, min(2.6, float(appearance.get("artistSizeMm") or round(size_mm * 0.74, 1))))
    title_size_px = max(7, int(w * title_size_mm / 4.4))
    artist_size_px = max(6, int(w * artist_size_mm / 4.4))
    style = str(appearance.get("style") or "normal")
    custom_fill = _spine_fill(appearance.get("color"), ink)
    has_custom_fill = str(appearance.get("color") or "auto").lower() != "auto"
    custom_text = str(((copy_settings or {}).get("spineText") or {}).get(zone_key) or "").strip()
    character_styles = ((copy_settings or {}).get("spineCharacterStyles") or {}).get(zone_key) or {}
    if custom_text:
        # 自定义文字始终保持用户选定的字号，向下使用延长后的侧封可用区域。
        custom_font = _spine_font(appearance.get("font"), size_px, custom_text)
        _vertical_spine_text(d, x, top, custom_text, custom_font, custom_fill, usable, 1.10,
                              bold=style in {"bold", "boldItalic"},
                              italic=style in {"italic", "boldItalic"})
        return base

    # 三条 4.4×38mm 物理侧封共用模板库。这是第一套基准：参考白色植物封面的
    # 标题+歌手排法，标题更黑、更大，歌手较小，顶部和底部保留给延展画面。
    template = templates.get(zone_key, "title-artist-classic")
    if template == "title-artist-classic":
        # 固定模板只固定标题与歌手的位置；文字外观完全服从当前侧封工具栏。
        title_font = _spine_font(appearance.get("font"), title_size_px, album)
        after_title = _vertical_spine_text(d, x, int(h * 0.29), album, title_font, custom_fill,
                                            int(h * 0.27), 1.06,
                                            bold=style in {"bold", "boldItalic"},
                                            italic=style in {"italic", "boldItalic"},
                                            char_styles=character_styles.get("title"), pixels_per_mm=w / 4.4)
        artist_font = _spine_font(appearance.get("font"), artist_size_px, artist)
        artist_fill = custom_fill if has_custom_fill else dim
        _vertical_spine_text(d, x, max(int(h * 0.62), after_title + int(h * 0.06)),
                              artist, artist_font, artist_fill, int(h * 0.20), 1.04,
                              bold=style in {"bold", "boldItalic"},
                              italic=style in {"italic", "boldItalic"},
                              char_styles=character_styles.get("artist"), pixels_per_mm=w / 4.4)
        return base

    if variant == "right":
        template = templates.get("right", "white-poetry")
        _primary, secondary, short = _copy_text(copy_settings)
        english_tag = (short or secondary or company or "").upper().replace(" ", "")[:10]

        if template == "photo-artist":
            # 参考的蓝色摄影版：人物与风景是底图，歌手名成为唯一的大识别信息。
            artist_font = _t("artist", max(7, int(min(w * 0.56, h * 0.050))), artist)
            if artist and artist.isascii():
                _rotated_spine_label(base, x, int(h * 0.20), artist.upper(), artist_font, ink, int(h * 0.54))
            else:
                _vertical_spine_text(d, x, int(h * 0.20), artist, artist_font, ink,
                                      int(h * 0.54), 1.12)
            return base

        if template == "dark-editorial":
            # 深色油画/隧道类封面：细规则、标题、歌手、英文收尾四层，保持克制。
            hairline(d, int(w * 0.22), int(h * 0.17), int(w * 0.78), dim, 1)
            title_font = _t("serif", max(7, int(min(w * 0.62, h * 0.052))), album)
            after_title = _vertical_spine_text(d, x, int(h * 0.27), album, title_font, ink,
                                                int(h * 0.26), 1.10)
            hairline(d, int(w * 0.35), min(int(h * 0.57), after_title + int(h * 0.025)),
                     int(w * 0.65), dim, 1)
            artist_font = _t("artist", max(6, int(min(w * 0.46, h * 0.036))), artist)
            after_artist = _vertical_spine_text(d, x, max(int(h * 0.60), after_title + int(h * 0.07)),
                                                 artist, artist_font, dim, int(h * 0.17), 1.05)
            if english_tag:
                tag_font = _t("spine", max(6, int(min(w * 0.36, h * 0.023))), english_tag)
                _vertical_spine_text(d, x, max(int(h * 0.82), after_artist + int(h * 0.02)),
                                      english_tag, tag_font, dim, int(h * 0.11), 1.00)
            return base

        if template == "bold-title":
            # 夜景/烟花海报版保留顶端画面，只在中下段压入高对比的大标题。
            title_font = _t("serif", max(8, int(min(w * 0.70, h * 0.060))), album)
            after_title = _vertical_spine_text(d, x, int(h * 0.29), album, title_font,
                                                (210, 42, 32), int(h * 0.34), 1.05)
            artist_font = _t("artist", max(6, int(min(w * 0.46, h * 0.035))), artist)
            after_artist = _vertical_spine_text(d, x, max(int(h * 0.69), after_title + int(h * 0.05)),
                                                 artist, artist_font, ink, int(h * 0.13), 1.02)
            if english_tag:
                tag_font = _t("spine", max(6, int(min(w * 0.34, h * 0.022))), english_tag)
                _vertical_spine_text(d, x, max(int(h * 0.84), after_artist + int(h * 0.015)),
                                      english_tag, tag_font, dim, int(h * 0.09), 1.00)
            return base

        # 白色植物/手写封面：中段标题、下段歌手，顶部和底部留给花瓣与画面呼吸。
        title_font = _t("serif", max(7, int(min(w * 0.56, h * 0.047))), album)
        after_title = _vertical_spine_text(d, x, int(h * 0.31), album, title_font, ink,
                                            int(h * 0.25), 1.12)
        artist_font = _t("artist", max(6, int(min(w * 0.42, h * 0.034))), artist)
        _vertical_spine_text(d, x, max(int(h * 0.62), after_title + int(h * 0.05)),
                              artist, artist_font, dim, int(h * 0.19), 1.05)
        return base

    if variant == "left":
        template = templates.get("left", "artwork")
        if template == "artwork":
            return base
        if template == "tag":
            _primary, secondary, short = _copy_text(copy_settings)
            tag = (short or secondary or "").upper().replace(" ", "")[:12]
            if tag:
                tag_font = _t("sans", max(6, int(min(w * 0.54, h * 0.038))), tag)
                _vertical_spine_text(d, x, top, tag, tag_font, ink, usable, 1.03)
            return base
        title_font = _t("serif", max(7, int(min(w * 0.62, h * 0.050))), album)
        _vertical_spine_text(d, x, top, album, title_font, ink, usable, 1.10)
        return base

    # 面向内侧：标题或短英文，而不是再复制完整的歌手信息。
    template = templates.get("leftBack", "inner-title")
    if template == "copy":
        primary, _secondary, _short = _copy_text(copy_settings)
        phrase = primary.replace("，", "").replace("。", "")[:10]
        copy_font = _t("hand", max(7, int(min(w * 0.62, h * 0.048))), phrase)
        _vertical_spine_text(d, x, top, phrase, copy_font, ink, usable, 1.08)
        return base
    if template == "title-artist":
        title_font = _t("serif", max(7, int(min(w * 0.62, h * 0.050))), album)
        after_title = _vertical_spine_text(d, x, top, album, title_font, ink,
                                            int(usable * 0.58), 1.10)
        artist_font = _t("artist", max(6, int(min(w * 0.48, h * 0.037))), artist)
        _vertical_spine_text(d, x, max(after_title + int(h * 0.025), int(h * 0.64)),
                              artist, artist_font, dim, int(h * 0.22), 1.04)
        return base
    title_font = _t("serif", max(7, int(min(w * 0.61, h * 0.048))), album)
    after_title = _vertical_spine_text(d, x, top, album, title_font, ink,
                                        int(usable * 0.60), 1.10)
    _primary, secondary, short = _copy_text(copy_settings)
    tag = (short or secondary or "").upper().replace(" ", "")[:10]
    if tag:
        tag_font = _t("sans", max(6, int(min(w * 0.46, h * 0.030))), tag)
        _vertical_spine_text(d, x, max(after_title + int(h * 0.025), int(h * 0.66)),
                              tag, tag_font, dim, int(h * 0.22), 1.00)
    return base


def design_spine2(w, h, D, album="", artist="", company="", copy_settings=None):
    """侧标 / 书脊（v2）：竖排 + 字距 + 底部厂牌块（真书脊的排法）。"""
    w, h = int(w), int(h)
    key = D.get("main", (120, 120, 120))
    base = Image.new("RGB", (w, h), tuple(int(c * 0.34) for c in key))
    d = ImageDraw.Draw(base)
    ink = ink_on(palette(base, 3)[0])
    dim = dim_ink(ink, palette(base, 3)[0], 0.66)

    txt = " ".join(x for x in ((album or ""), (artist or "")) if x)
    fs = max(7, int(min(w * 0.60, h * 0.048)))
    f = _t("serif", fs, txt)
    avail = int(h * 0.84)
    chars, used = [], 0.0
    for ch in txt:
        adv = fs * 1.18
        if used + adv > avail:
            chars.append("…")
            break
        chars.append(ch)
        used += adv
    used = len(chars) * fs * 1.18
    cy = int(h * 0.07 + max(0.0, (int(h * 0.78) - used) / 2.0))   # 垂直居中
    for ch in chars:
        cw = d.textlength(ch, font=f)
        d.text(((w - cw) / 2, cy), ch, font=f, fill=ink)
        cy += int(fs * 1.18)
    hairline(d, int(w * 0.22), int(h * 0.90), int(w * 0.78), ink, 1)
    lab = (company or artist or "").strip()
    fL, lab = fit_tracked(d, lab, w * 0.82, max(7, int(w * 0.40)), "sans", 0.4)
    tracked(d, (w / 2.0, int(h * 0.925)), lab, fL, dim, 0.4, "center", w * 0.82)
    # Narrow back-spine copy: compact, vertical and kept out of the product title area.
    _primary, _secondary, _short = _copy_text(copy_settings)
    tag = (_short or _secondary).upper()[:18]
    if tag:
        tf = _t("sans", max(6, int(w * 0.36)), tag)
        ty = int(h * 0.69)
        for ch in tag:
            cw = d.textlength(ch, font=tf)
            d.text(((w - cw) / 2, ty), ch, font=tf, fill=dim)
            ty += max(6, int(tf.size * 1.03))
            if ty > int(h * 0.88):
                break
    return base
