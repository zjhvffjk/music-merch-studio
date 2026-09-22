# -*- coding: utf-8 -*-
"""迷你CD 专辑设计工作台（design_service）。

从「专辑列表」接进来：给定 歌手 / 专辑 / 封面URL / 曲目，
复用 design_parts v2 引擎（design_disc2 / design_inner2 / make_back_strip 里的
design_back2 / design_tray2）+ spec_minicd 尺寸真源，按 **111.2 固定结构** 出
①②③ 三件套 + 1:1 印刷版面总览；并导出打印文件（A4 300dpi PNG + PDF）+ ZIP。

AI 增强走「程序衍生打底 + 可选上传覆盖」：build 接口接受 aiDisc/aiFold/aiStrip
三个已上传图片路径（来自 /api/upload），给了就用它替代对应程序衍生件。

接口契约同 packaging_service.handle（handler 为 server 的 BaseHTTPRequestHandler）：
  GET  /api/design/album   ?artist=&album=&pic=&tracks=&company=&mood=&style=
        → 拉封面 + 读设计语言 + 返回 notes（不落盘）
  POST /api/design/build   body{artist,album,pic,tracks,company,mood,style,id,
                                aiDisc,aiFold,aiStrip}
        → 出三件套 + 总览 + A4 打印页，存 outputs/迷你CD设计/<jid>/
        → 返回 {ok, jid, parts, sheetUrl, printUrl, notes, design, zipUrl}
  POST /api/design/batch   body{artist,albums:[{album,artist,pic,company,date}],
                                mood,style,safeBands}
        → 多张专辑各出三件套 + 打印页，并合成「★多专辑对照图.png」（自带文字标注）
        → 返回 {ok, jid, count, failed, items[{no,album,parts[],printUrl}],
                sheetUrl, zipUrl}
  GET  /api/design/file?jid=&name=   → 该任务目录内文件（带越界校验）
  GET  /api/design/zip?jid=          → 打包下载
  GET  /api/design/state?jid=         → 任务 meta

作品库（`list_projects` / `trash_project`）**不单独开 HTTP 接口**：
workbench 工作台的「作品库」把商品图任务与迷你CD任务合并成一份列表
（server.py 的 `/api/jobs` 在进程内直接调 `list_projects()`），
移动/清理也统一走 `/api/jobs/delete`。这里只保留函数，避免出现第二套入口。

``safeBands``（build / album / batch 通用）：字符串 ``"0.30,1.0"`` = 封面顶部 30%
被自带标题占用，补件取景只落在下方可用带内（根治「字压两遍」）。不传 = 整幅取景。
"""
import io
import json
import os
import re
import shutil
import sys
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
for p in (TOOLS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = Path(ROOT) / "outputs" / "迷你CD设计"
OUT_DIR.mkdir(parents=True, exist_ok=True)
# 设计页的即时预览不属于正式作品，也不产出打印件。只保留短时的小图缓存，
# 让用户在按下「生成三件套」前就能确认三个实物部件的结构与取景。
PREVIEW_DIR = OUT_DIR / "_preview_cache"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

try:
    import noproxy  # noqa: F401  绕过本机代理（server 已 import；这里兜底）
except Exception:
    pass

import spec_minicd as SP
import make_minicd as MC
import design_parts as DP
import copy_typography as CT
import title_typography as TT
import title_assets as TA
import title_compositor as TC
import title_reference as TR
import make_minicd_sheet as MS
import qwen_minicd as QWEN

from PIL import Image, ImageDraw

DPI = 300
SHEET_DPI = 300
PREVIEW_DPI = 96


def _slog(*a):
    try:
        print("[design]", *a, flush=True)
    except Exception:
        pass


def _safe_jid(jid):
    jid = (jid or "").strip()
    if not jid or len(jid) > 64:
        return None
    for ch in jid:
        if not (ch.isascii() and (ch.isalnum() or ch == "-")):
            return None
    return jid


def mm(v, dpi):
    return int(round(v * dpi / 25.4))


def _fetch_cover(pic):
    """从封面 URL 拉图；本地路径直接打开；失败返回 None。"""
    if not pic:
        return None
    try:
        if os.path.isfile(pic):
            return Image.open(pic).convert("RGB")
    except Exception:
        pass
    try:
        req = Request(pic, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://music.163.com/",
        })
        with urlopen(req, timeout=25) as r:
            data = r.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        _slog("cover fetch failed:", type(e).__name__, e)
        return None


def _norm_tracks(v):
    """标准化曲目：保留搜索页给出的排名、歌名与时长，兼容手输的一行一首。"""
    if v is None:
        return None
    raw = v
    if isinstance(v, str):
        text = v.strip()
        if text.startswith("["):
            try:
                raw = json.loads(text)
            except Exception:
                raw = None
        if raw is None or isinstance(raw, str):
            raw = [t.strip() for t in text.replace("；", ";").replace("\n", ";").split(";")]
    if not isinstance(raw, (list, tuple)):
        return None
    items = []
    for i, item in enumerate(raw, 1):
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or item.get("song") or "").strip()
            dur = str(item.get("duration") or item.get("dur") or item.get("time") or "").strip()
            try: rank = int(item.get("rank") or i)
            except Exception: rank = i
        else:
            title, dur, rank = str(item).strip(), "", i
        if title:
            items.append({"rank": max(1, rank), "title": title, "duration": dur})
        if len(items) >= 10:
            break
    return items or None


def _parse_bands(v):
    """``safeBands`` → ``(top, bottom)``。

    接受 ``"0.30,1.0"`` / ``[0.3, 1.0]`` / ``(0.3, 1.0)`` 三种写法。
    🔴 这是「**可用横带**」不是「标题占的带」：标题在顶部 30% 就传 ``0.30,1.0``。
    非法值一律返回 None（= 整幅取景），不让坏参数把请求打成 500。
    """
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        if len(v) != 2:
            return None
        try:
            a, b = float(v[0]), float(v[1])
        except (TypeError, ValueError):
            return None
    else:
        parts = [p for p in str(v).replace("，", ",").split(",") if p.strip()]
        if len(parts) != 2:
            return None
        try:
            a, b = float(parts[0]), float(parts[1])
        except ValueError:
            return None
    if not (0.0 <= a < b <= 1.0):
        return None
    return (a, b)


def _read_design(cover, mood="", style="", bands=None):
    D = DP.read_design(cover, safe_bands=bands)
    if mood:
        D["mood"] = mood
    if style:
        D["style"] = style
        D["ink"] = DP.ink_on(D["main"])
    return D


def _release_metadata(data, artist, album, company=""):
    """取得真实的专辑发行年份与发行公司。

    从专辑墙进入时 URL 已带 ``date/company``，无需二次请求；单曲或旧链接则
    用网易云专辑详情补齐。这里不以当前年份冒充发行年份。
    """
    company = str(company or "").strip()
    date = str(data.get("date") or data.get("releaseDate") or "").strip()
    found_company, found_date = company, date
    album_id = str(data.get("id") or "").strip()
    if album_id.isdigit() and (not found_company or not re.search(r"(?:19|20)\d{2}", found_date)):
        try:
            import fetch163
            detail, _songs = fetch163.album_detail(int(album_id))
            found_company = found_company or str(detail.get("company") or "").strip()
            found_date = found_date or str(detail.get("publishTime") or "")
            if found_date.isdigit() and len(found_date) >= 10:
                found_date = time.strftime("%Y-%m-%d", time.localtime(int(found_date) / 1000))
        except Exception as e:
            _slog("album metadata lookup skipped:", type(e).__name__)
    # 网易云有时只给日期、不给唱片公司；再用 QQ 专辑详情补齐。
    if not found_company or not re.search(r"(?:19|20)\d{2}", found_date):
        try:
            import fetch_qq
            qq = fetch_qq.album_metadata_q(album, artist)
            found_company = found_company or str(qq.get("company") or "").strip()
            found_date = found_date or str(qq.get("date") or "").strip()
        except Exception as e:
            _slog("qq album metadata lookup skipped:", type(e).__name__)
    year_match = re.search(r"(?:19|20)\d{2}", found_date)
    return found_company, (year_match.group(0) if year_match else ""), found_date


def build_parts(cover, album, artist, D, tracks, company, ai=None, dpi=DPI,
                inner_copy="", barcode_code="", copyright_text="", release_year="", back_layout="auto", copy_settings=None):
    """出 ①②③ 三件（override-aware）。返回 (disc, fold, strip)。"""
    MC._dpi[0] = dpi  # make_back_strip 用模块级 _dpi

    title_state = TT.title_typography_state(copy_settings or {}, D, album, artist)
    selected_title_asset = title_state.get("selectedTitleAssetId") if title_state.get("titleMode") == "artistic" else None
    title_asset_image = None
    if selected_title_asset:
        try:
            _asset, title_asset_image = TA.load_title_asset(selected_title_asset)
        except Exception:
            title_asset_image = None
    rendered_album = "" if title_asset_image is not None else album
    # ① 盘面
    disc_d = mm(SP.DISC_D, dpi)
    hole_d = mm(SP.DISC_HOLE, dpi)
    if ai and ai.get("disc"):
        disc = MC.cover_crop(ai["disc"], disc_d, disc_d)
    else:
        disc = DP.design_disc2((ai or {}).get("discArt") or cover, disc_d, hole_d, D, rendered_album, artist, company, copy_settings=copy_settings)

    # ② 封面折件（左内页 + 右封面）
    fold_w = mm(SP.COVER_W, dpi)
    fold_h = mm(SP.COVER_H, dpi)
    if ai and ai.get("fold"):
        inner_im = MC.cover_crop(ai["fold"], fold_w // 2, fold_h)
        fold = MC.make_cover_fold(inner_im, cover, fold_w, fold_h, D, copy_settings)
    else:
        inner_im = DP.design_inner2((ai or {}).get("insideArt") or cover, fold_w // 2, fold_h, D, rendered_album, artist,
                                    tracks, quote=(copy_settings or {}).get("conceptCopy", {}).get("primaryChinese") or inner_copy or None,
                                    copy_settings=copy_settings)
        fold = MC.make_cover_fold(inner_im, cover, fold_w, fold_h, D, copy_settings)

    # ③ 封底条（封底 + 内盘底 + 侧封边缘延展）
    strip_w = mm(SP.BACK_W, dpi)
    strip_h = mm(SP.BACK_H, dpi)
    if ai and ai.get("strip"):
        strip = MC.cover_crop(ai["strip"], strip_w, strip_h)
    else:
        strip = MC.make_back_strip((ai or {}).get("backArt"), (ai or {}).get("trayArt"), strip_w, strip_h, cover, rendered_album,
                                   artist, D, tracks, 0, company,
                                   barcode_code=barcode_code,
                                   copyright_text=copyright_text,
                                   release_year=release_year, back_layout=back_layout, copy_settings=copy_settings)
    if title_asset_image is not None:
        reports = {}
        disc, reports["disc"] = TC.place_title_asset(disc, title_asset_image, TC.resolve_title_placement("disc", SP), SP.title_protected_rects_mm("disc"), dpi)
        front = TC.resolve_title_placement("cover-front", SP); front.x_mm += SP.COVER_W / 2
        fold, reports["cover-front"] = TC.place_title_asset(fold, title_asset_image, front, [], dpi)
        inside = TC.resolve_title_placement("cover-inside", SP)
        fold, reports["cover-inside"] = TC.place_title_asset(fold, title_asset_image, inside, [], dpi)
        back = TC.resolve_title_placement("back", SP); back.x_mm += SP.BACK_SEGS[0]
        protected = [{**r, "x": r["x"] + SP.BACK_SEGS[0]} for r in SP.back_protected_rects_mm()]
        strip, reports["back"] = TC.place_title_asset(strip, title_asset_image, back, protected, dpi)
        tray = TC.resolve_title_placement("inner-tray", SP); tray.x_mm += sum(SP.BACK_SEGS[:4])
        strip, reports["inner-tray"] = TC.place_title_asset(strip, title_asset_image, tray, [], dpi)
        setattr(build_parts, "last_title_usage", {"assetId": selected_title_asset, "placements": reports})
    else:
        setattr(build_parts, "last_title_usage", {})
    return disc, fold, strip


UPLOAD_DIR = Path(ROOT) / "outputs" / "工作台" / "_uploads"


def _upload_path(uid):
    uid = str(uid or "").strip()
    if not uid or not all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in uid):
        return None
    hits = sorted(UPLOAD_DIR.glob(uid + ".*"))
    return str(hits[0]) if hits and hits[0].is_file() else None

def _load_ai(path):
    """AI 增强图：绝对/相对路径直接开；或 /api/upload 返回的 uid（12hex）
    → 在 UPLOAD_DIR 里按前缀解析（扩展名未知，upload 只回 uid）。"""
    if not path:
        return None
    path = str(path).strip().strip('"')
    cand = None
    if os.path.isfile(path):
        cand = path
    elif path and all(c.isascii() and (c.isalnum() or c in "-_") for c in path) \
            and "/" not in path and "\\" not in path and "." not in path:
        # 像 uid：在 uploads 目录找前缀匹配（防路径穿越——不含分隔符与点）
        hits = sorted(UPLOAD_DIR.glob(path + ".*"))
        if hits:
            cand = str(hits[0])
    if not cand:
        return None
    try:
        return Image.open(cand).convert("RGB")
    except Exception:
        return None


def _clean_preview_cache(max_age=60 * 60):
    """清理一小时前的临时预览；正式任务永远不放在这个目录。"""
    cutoff = time.time() - max_age
    for item in PREVIEW_DIR.iterdir():
        try:
            if item.is_dir() and item.stat().st_mtime < cutoff:
                shutil.rmtree(item, ignore_errors=True)
        except OSError:
            pass


def _title_state(data, design, album, artist, cover=None):
    """Return provider-ready title state without fabricating AI artwork."""
    dna = dict(design or {})
    if cover is not None:
        ref = TR.extract_cover_title_reference(cover, dna, album)
        if ref.get("status") == "detected":
            dna["coverTitleReference"] = ref
    state = TT.title_typography_state(data, dna, album, artist)
    state["coverTitleReference"] = dna.get("coverTitleReference") or {"status": "unavailable"}
    return state

def build_preview(data):
    """生成低分辨率临时三件套，用于设计页实时确认，不创建作品库任务。"""
    artist = str(data.get("artist") or "")
    album = str(data.get("album") or "")
    pic = data.get("pic") or ""
    company, release_year, _release_date = _release_metadata(
        data, artist, album, str(data.get("company") or ""))
    tracks = _norm_tracks(data.get("trackData") if data.get("trackData") is not None else data.get("tracks"))
    inner_copy = str(data.get("innerCopy") or "")
    barcode_code = str(data.get("barcode") or "")
    copyright_text = str(data.get("copyright") or "")
    copy_settings = CT.normalize_copy_settings(data)
    cover = _fetch_cover(pic)
    if cover is None:
        raise ValueError("封面拉取失败（URL 不可达或被代理拦截）：%s" % pic)
    D = _read_design(cover, str(data.get("mood") or ""),
                     str(data.get("style") or ""),
                     _parse_bands(data.get("safeBands")))
    if not any(copy_settings["conceptCopy"].values()):
        zh, en, short = CT.auto_concept_copy(album, D)
        copy_settings["conceptCopy"] = {"primaryChinese": zh, "secondaryEnglish": en, "shortEnglish": short}
    copy_settings["resolvedLayout"] = CT.recommend_copy_layout(copy_settings, D)
    title_state = _title_state(data, D, album, artist, cover)
    ai = {"disc": _load_ai(data.get("aiDisc")),
          "fold": _load_ai(data.get("aiFold")),
          "strip": _load_ai(data.get("aiStrip"))}
    token = "p-" + uuid.uuid4().hex[:16]
    dest = PREVIEW_DIR / token
    dest.mkdir(parents=True, exist_ok=True)
    disc, fold, strip = build_parts(cover, album, artist, D, tracks, company,
                                    ai if any(ai.values()) else None, PREVIEW_DPI,
                                    inner_copy, barcode_code, copyright_text, release_year, str(data.get("backLayout") or "auto"), copy_settings)
    for name, image in (("disc.png", disc), ("cover.png", fold), ("strip.png", strip)):
        image.save(str(dest / name), optimize=True)
    _clean_preview_cache()
    return {"ok": True, "token": token, "copySettings": copy_settings, "titleTypography": title_state,
            "parts": {name: "/api/design/preview-file?token=%s&name=%s" % (token, name)
                      for name in ("disc.png", "cover.png", "strip.png")}}


def build_job(data):
    """落盘一个设计任务：三件套 + 1:1 总览 + A4 打印页 + 打印 PDF + meta + ZIP。"""
    artist = str(data.get("artist") or "")
    album = str(data.get("album") or "")
    pic = data.get("pic") or ""
    company, release_year, release_date = _release_metadata(
        data, artist, album, str(data.get("company") or ""))
    mood = str(data.get("mood") or "")
    style = str(data.get("style") or "")
    tracks = _norm_tracks(data.get("trackData") if data.get("trackData") is not None else data.get("tracks"))
    inner_copy = str(data.get("innerCopy") or "")
    barcode_code = str(data.get("barcode") or "")
    copyright_text = str(data.get("copyright") or "")
    copy_settings = CT.normalize_copy_settings(data)
    bands = _parse_bands(data.get("safeBands"))
    cover = _fetch_cover(pic)
    if cover is None:
        raise ValueError("封面拉取失败（URL 不可达或被代理拦截）：%s" % pic)
    D = _read_design(cover, mood, style, bands)
    if not any(copy_settings["conceptCopy"].values()):
        zh, en, short = CT.auto_concept_copy(album, D)
        copy_settings["conceptCopy"] = {"primaryChinese": zh, "secondaryEnglish": en, "shortEnglish": short}
    copy_settings["resolvedLayout"] = CT.recommend_copy_layout(copy_settings, D)

    ai = {
        "disc": _load_ai(data.get("aiDisc")),
        "fold": _load_ai(data.get("aiFold")),
        "strip": _load_ai(data.get("aiStrip")),
    }
    title_state = _title_state(data, D, album, artist, cover)
    has_ai = any(ai.values())

    jid = _safe_jid(data.get("id")) or uuid.uuid4().hex[:16]
    d = OUT_DIR / jid
    d.mkdir(parents=True, exist_ok=True)

    # 本地单封面生图还没有达到生产质量，不能让它混入正式出件。
    # 仍支持用户手动上传已确认的底图；默认始终使用程序的稳定封面延展。
    use_local_ai = False

    disc, fold, strip = build_parts(cover, album, artist, D, tracks, company,
                                    ai if has_ai else None, DPI,
                                    inner_copy, barcode_code, copyright_text, release_year, str(data.get("backLayout") or "auto"), copy_settings)
    disc.save(str(d / "part-disc.png"))
    fold.save(str(d / "part-cover.png"))
    strip.save(str(d / "part-strip.png"))

    # 1:1 总览
    sheet_path = str(d / "★版面总览-1比1.png")
    rendered = {"rendered_disc": (disc, False), "rendered_fold": (fold, False),
                "rendered_strip": (strip, False)}
    MS.build_sheet(cover, album, artist, D, tracks, company, sheet_path, SHEET_DPI,
                   png=True, rendered_parts=rendered)

    # A4 打印参考页（程序衍生结构；与三件套同源引擎，无 AI 覆盖时完全一致）
    page_im, sets, _prev = MC.build_page({"cover": (cover, False), **rendered}, DPI, "a4l", 1,
                                          artist, album, D, tracks, 0, company)
    page_im.save(str(d / "打印拼版-A4.png"), quality=95)
    page_im.save(str(d / "打印拼版-A4.pdf"), "PDF", resolution=DPI)

    notes = DP.design_notes(D, album, artist, tracks, has_lyrics=False)
    meta = {
        "id": jid, "kind": "minicd-design", "artist": artist, "album": album,
        "company": company, "releaseYear": release_year, "releaseDate": release_date,
        "tracks": tracks or [], "innerCopy": inner_copy,
        "barcode": barcode_code, "copyright": copyright_text,
        "backLayout": str(data.get("backLayout") or "auto"),
        "copyLayout": copy_settings["copyLayout"], "conceptCopy": copy_settings["conceptCopy"],
        "typography": copy_settings["typography"],
        "titleTypography": title_state,
        "mood": D["mood"], "style": D["style"],
        "main": list(D["main"]), "hasAi": has_ai or use_local_ai,
        "localAi": use_local_ai,
        # 项目库回看要用的「原始输入」：没有 pic 就只能看出件图、不能重跑
        "pic": str(pic), "safeBands": str(data.get("safeBands") or ""),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "parts": {
            "disc": "part-disc.png", "cover": "part-cover.png",
            "strip": "part-strip.png", "sheet": "★版面总览-1比1.png",
            "print": "打印拼版-A4.png", "printPdf": "打印拼版-A4.pdf",
        },
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打包 ZIP
    zip_path = OUT_DIR / ("%s.zip" % jid)
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("part-disc.png", "part-cover.png", "part-strip.png",
                  "★版面总览-1比1.png", "打印拼版-A4.png", "打印拼版-A4.pdf", "meta.json"):
            p = d / f
            if p.is_file():
                z.write(str(p), f)

    return {
        "ok": True, "jid": jid,
        "parts": [
            {"name": "盘面", "file": "part-disc.png", "mm": "%g×%g" % (SP.DISC_D, SP.DISC_D)},
            {"name": "封面折件", "file": "part-cover.png", "mm": "%g×%g" % (SP.COVER_W, SP.COVER_H)},
            {"name": "封底条", "file": "part-strip.png", "mm": "%g×%g" % (SP.BACK_W, SP.BACK_H)},
        ],
        "sheetUrl": "/api/design/file?jid=%s&name=%s" % (jid, quote("★版面总览-1比1.png")),
        "printUrl": "/api/design/file?jid=%s&name=%s" % (jid, quote("打印拼版-A4.png")),
        "printPdfUrl": "/api/design/file?jid=%s&name=%s" % (jid, quote("打印拼版-A4.pdf")),
        "zipUrl": "/api/design/zip?jid=%s" % jid,
        "notes": notes,
        "titleTypography": title_state,
        "design": {"mood": D["mood"], "style": D["style"], "main": list(D["main"]),
                   "hasAi": has_ai or use_local_ai},
    }


# --------------------------------------------------------------------------
# 批量：一次为多张专辑各出三件套 + 多专辑对照图（每格自带文字标注）
# --------------------------------------------------------------------------
MAX_BATCH = 12

_INK = (38, 40, 44)
_DIM = (118, 122, 128)
_LINE = (224, 227, 231)
_MARK = (176, 40, 40)   # 序号/强调用的红


def _flat(im):
    """RGBA → 白底 RGB（盘面是圆的，直接 convert 会把透明区变黑）。"""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, (0, 0), im)
        return bg
    return im.convert("RGB")


def _fit(im, w, h):
    """按比例缩放到 (w,h) 内（contain，不裁切不拉伸）。"""
    s = min(w / im.width, h / im.height)
    nw, nh = max(1, int(round(im.width * s))), max(1, int(round(im.height * s)))
    return im.resize((nw, nh), Image.LANCZOS)


_MM_CAP = {
    "disc": "① 盘面 Ø40mm（中心孔 Ø5mm）",
    "cover": "② 封面折件 82×41mm（对折 41×41）",
    "strip": "③ 封底条 111.2×38mm",
}


def build_contact_sheet(rows, out_path, artist="", title="多专辑设计对照图"):
    """多专辑对照图：每行 = 左列专辑信息 + 右侧三件（每格带文字标注）。

    ``rows`` 为 ``[{no, album, artist, date, mood, style, disc, cover, strip}, ...]``，
    图像项为 PIL Image。自带标注：每格写清「这一格是什么」，左→右即 ①②③。
    """
    import typo as T

    S = 2                       # 超采样倍数（文字锐利）
    M = 40 * S                  # 外边距
    PANEL = 430 * S             # 左列信息面板宽
    GAP = 26 * S
    CELL_H = 300 * S            # 三件的统一高度（按比例缩放）

    def sc(im, h):
        return _fit(_flat(im), int(im.width * h / im.height), h)

    discs = [sc(r["disc"], CELL_H) for r in rows]
    folds = [sc(r["cover"], CELL_H) for r in rows]
    strips = [sc(r["strip"], CELL_H) for r in rows]
    body_w = max(d.width + f.width + s.width + 2 * GAP
                 for d, f, s in zip(discs, folds, strips))
    CAP_H = 34 * S              # 标注行高
    ROW_H = CELL_H + CAP_H + 26 * S
    HEAD_H = 116 * S
    FOOT_H = 46 * S

    W = M * 2 + PANEL + GAP + body_w
    H = M * 2 + HEAD_H + ROW_H * len(rows) + FOOT_H
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)

    # ---- 页眉 ----
    f_t = T.font("serif", 40 * S, title)
    T.tracked(d, (M, M), title, f_t, _INK, 0.6)
    sub = "%s · 共 %d 张 · 尺寸真源 tools/spec_minicd.py" % (artist or "", len(rows))
    f_s = T.font("sans", 19 * S, sub)
    T.tracked(d, (M, M + 58 * S), sub, f_s, _DIM, 0.4)
    d.line([(M, M + HEAD_H - 18 * S), (W - M, M + HEAD_H - 18 * S)], fill=_LINE, width=2 * S)

    # ---- 每行 ----
    y = M + HEAD_H
    for i, r in enumerate(rows):
        top = y
        # 左列：序号 + 专辑名 + 歌手 + 设计语言
        f_no = T.font("num", 40 * S, "01")
        T.tracked(d, (M, top + 2 * S), str(r.get("no") or "%02d" % (i + 1)), f_no, _MARK, 0.0)
        f_nm = T.font("heavy", 28 * S, r.get("album") or "")
        ly = top + 56 * S
        for ln in T.wrap_tracked(d, r.get("album") or "", f_nm, PANEL - 8 * S, 0.3)[:2]:
            T.tracked(d, (M, ly), ln, f_nm, _INK, 0.3)
            ly += 36 * S
        f_ar = T.font("sans", 20 * S, r.get("artist") or "")
        T.tracked(d, (M, ly + 6 * S), r.get("artist") or "", f_ar, _DIM, 0.3,
                  limit=PANEL - 8 * S)
        ly += 36 * S
        bits = []
        if r.get("date"):
            bits.append(str(r["date"]))
        if r.get("mood"):
            bits.append(str(r["mood"]))
        if r.get("style"):
            bits.append(str(r["style"]))
        f_m = T.font("sans", 16 * S, " ".join(bits))
        T.tracked(d, (M, ly + 6 * S), " · ".join(bits), f_m, _DIM, 0.3,
                  limit=PANEL - 8 * S)

        # 右侧三件：底部对齐 + 每格下方标注
        x = M + PANEL + GAP
        for key, part, cap in (("disc", discs[i], _MM_CAP["disc"]),
                               ("cover", folds[i], _MM_CAP["cover"]),
                               ("strip", strips[i], _MM_CAP["strip"])):
            px, py = x, top + (CELL_H - part.height)
            im.paste(part, (px, py))
            d.rectangle([px, py, px + part.width - 1, py + part.height - 1],
                        outline=_LINE, width=2 * S)
            f_c = T.font("sans", 16 * S, cap)
            T.tracked(d, (px, top + CELL_H + 10 * S), cap, f_c, _INK, 0.2,
                      limit=part.width + GAP)
            x += part.width + GAP

        y += ROW_H
        if i < len(rows) - 1:
            d.line([(M, y - 14 * S), (W - M, y - 14 * S)], fill=_LINE, width=1 * S)

    # ---- 页脚 ----
    foot = "由「迷你CD 设计工作台」按封面衍生引擎自动生成 · 打印请选『实际大小 / 100%』"
    f_f = T.font("sans", 16 * S, foot)
    T.tracked(d, (M, H - M - 24 * S), foot, f_f, _DIM, 0.3)

    im.resize((W // S, H // S), Image.LANCZOS).save(out_path)
    return out_path


def build_batch(data):
    """一次为多张专辑各出三件套 + 打印页，再合成「多专辑对照图」与合并 ZIP。

    body: ``{artist, albums:[{album,artist,pic,company,tracks,date}, ...],
             mood, style, safeBands, company}``
    → ``{ok, jid, count, failed, items:[{no,album,artist,mood,style,parts[],printUrl}],
        sheetUrl, zipUrl}``
    """
    artist_all = str(data.get("artist") or "")
    company_all = str(data.get("company") or "")
    mood = str(data.get("mood") or "")
    style = str(data.get("style") or "")
    bands = _parse_bands(data.get("safeBands"))

    albs = data.get("albums")
    if isinstance(albs, str):
        try:
            albs = json.loads(albs)
        except Exception:
            albs = None
    if not isinstance(albs, list) or not albs:
        raise ValueError("albums 需要是非空数组")
    if len(albs) > MAX_BATCH:
        raise ValueError("一次最多 %d 张（当前 %d 张）" % (MAX_BATCH, len(albs)))

    jid = _safe_jid(data.get("id")) or uuid.uuid4().hex[:16]
    d = OUT_DIR / jid
    d.mkdir(parents=True, exist_ok=True)

    rows, items, failed = [], [], []
    written = []
    for i, alb in enumerate(albs, 1):
        name = ""
        try:
            if not isinstance(alb, dict):
                raise ValueError("条目不是对象")
            album = str(alb.get("album") or alb.get("name") or "")
            name = album
            artist = str(alb.get("artist") or artist_all)
            company, release_year, _release_date = _release_metadata(
                alb, artist, album, str(alb.get("company") or company_all))
            tracks = _norm_tracks(alb.get("tracks"))
            cover = _fetch_cover(alb.get("pic"))
            if cover is None:
                raise ValueError("封面拉取失败")
            D = _read_design(cover, mood, style, bands)

            ai = {"disc": _load_ai(alb.get("aiDisc")),
                  "fold": _load_ai(alb.get("aiFold")),
                  "strip": _load_ai(alb.get("aiStrip"))}
            has_ai = any(ai.values())
            disc, fold, strip = build_parts(cover, album, artist, D, tracks,
                                            company, ai if has_ai else None, DPI,
                                            release_year=release_year)

            tag = "%02d" % i
            fn = {"disc": tag + "-disc.png", "cover": tag + "-cover.png",
                  "strip": tag + "-strip.png"}
            disc.save(str(d / fn["disc"]))
            fold.save(str(d / fn["cover"]))
            strip.save(str(d / fn["strip"]))
            written += list(fn.values())

            page_im, _sets, _prev = MC.build_page(
                {"cover": (cover, False)}, DPI, "a4l", 1, artist, album, D,
                tracks, 0, company)
            pn = tag + "-打印拼版-A4.png"
            page_im.save(str(d / pn))
            written.append(pn)

            rows.append({"no": tag, "album": album, "artist": artist,
                         "date": str(alb.get("date") or ""),
                         "mood": D["mood"], "style": D["style"],
                         "disc": disc, "cover": fold, "strip": strip})

            def _u(f):
                return "/api/design/file?jid=%s&name=%s" % (jid, quote(f))

            items.append({
                "no": tag, "album": album, "artist": artist,
                "mood": D["mood"], "style": D["style"], "hasAi": has_ai,
                "parts": [_u(fn["disc"]), _u(fn["cover"]), _u(fn["strip"])],
                "printUrl": _u(pn),
            })
            _slog("batch %s ok: %s" % (tag, album))
        except Exception as e:
            _slog("batch item failed:", name, type(e).__name__, e)
            failed.append({"album": name, "error": "%s: %s" % (type(e).__name__, e)})

    if not items:
        raise ValueError("全部专辑都失败了：%s" % (failed[0]["error"] if failed else "未知原因"))

    sheet_name = BATCH_SHEET          # 与项目库共用同一个常量，改名不会只改一边
    build_contact_sheet(rows, str(d / sheet_name), artist_all or rows[0]["artist"])
    written.append(sheet_name)

    meta = {
        "id": jid, "kind": "minicd-design-batch", "artist": artist_all,
        "count": len(items), "failed": failed, "sheet": sheet_name,
        "albums": [{"no": r["no"], "album": r["album"], "artist": r["artist"],
                    "mood": r["mood"], "style": r["style"]} for r in rows],
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    written.append("meta.json")

    zip_path = OUT_DIR / ("%s.zip" % jid)
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as z:
        for f in written:
            p = d / f
            if p.is_file():
                z.write(str(p), f)

    return {
        "ok": True, "jid": jid, "count": len(items), "failed": failed,
        "items": items,
        "sheetUrl": "/api/design/file?jid=%s&name=%s" % (jid, quote(sheet_name)),
        "zipUrl": "/api/design/zip?jid=%s" % jid,
    }


# ---------------- 项目库（做过的项目留档） ----------------
# 每出一张，服务端已经在 OUT_DIR/<jid>/ 落了一整套（三件套 + 总览 + A4 + PDF
# + meta + ZIP）。以前这些文件只躺在磁盘上、界面上没有任何入口 —— 想再拿一次
# 只能重跑一遍。这里把它们铺出来：看得见 / 回得去 / 拿得回 / 能清理。
#
# 🔴 与折音的区别：折音把项目存在浏览器 IndexedDB（只存状态、存不住文件），
#    我们是服务端落盘 —— 换浏览器/换设备都在，而且文件本身就是交付物。
TRASH_DIR = OUT_DIR / "_trash"

# 项目里可供打开/下载的件（键 → 展示名 → 文件名），顺序即展示顺序
PROJ_FILES = (
    ("disc", "盘面", "part-disc.png"),
    ("cover", "封面折件", "part-cover.png"),
    ("strip", "封底条", "part-strip.png"),
    ("sheet", "1:1 版面总览", "★版面总览-1比1.png"),
    ("print", "A4 打印拼版", "打印拼版-A4.png"),
    ("printPdf", "印刷 PDF", "打印拼版-A4.pdf"),
)

# 批量任务：文件名带序号前缀（01-disc.png），且额外多一张总览对照图。
# 🔴 这张图的名字必须和 build_batch 里写盘时用的完全一致：原来是各写各的字面量，
#    改名时只改了一边 → 这边引用了一个**根本没定义的常量**，NameError 被
#    list_projects 的 per-item except 吞掉 → 三个批量项目整条从作品库消失
#    （不报错、只是"少了几条"，最难发现的那种）。所以统一成一个常量，两边共用。
BATCH_SHEET = "★多专辑对照图.png"
# 批量任务的 kind：`minicd-design-batch` 是现在的，`minicd-batch` 是更早版本落盘的，
# 磁盘上两者都有 —— 都按批量处理，否则老项目会走单张分支 → 显示「0 件」。
BATCH_KINDS = ("minicd-design-batch", "minicd-batch")


def _as_str(v, maxlen=200):
    """任何东西 → 有界字符串。meta.json 是磁盘文件，可能被人手改坏。"""
    if v is None or isinstance(v, (dict, list, tuple, set)):
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        # json.loads 接受 Infinity / NaN —— 落进 JSON 响应会让浏览器解析失败
        if v != v or v in (float("inf"), float("-inf")):
            return ""
    try:
        s = str(v)
    except Exception:
        return ""
    return s[:maxlen]


def _as_list(v, maxlen=200):
    """外部 JSON 数组 → 字符串表。🔴 不能用 `v or []`：truthy 非可迭代会炸。"""
    if isinstance(v, (str, bytes)) or not isinstance(v, (list, tuple)):
        return []
    out = []
    for x in v:
        s = _as_str(x, 120)
        if s:
            out.append(s)
        if len(out) >= maxlen:
            break
    return out


def _as_bool(v):
    """🔴 bool("false") 是 True —— 字符串必须显式认，不能直接 bool()。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    return _as_str(v, 8).strip().lower() in ("1", "true", "yes", "on")


def _proj_url(jid, fn):
    return "/api/design/file?jid=%s&name=%s" % (jid, quote(fn))


MAX_BATCH_PARTS = 8      # 回看面板最多铺前 8 张（张数本身照实数显示）


def _batch_tags(d):
    """批量任务目录 → 盘上真实存在的序号（"01" / "02" …），已排序。
    🔴 别写死 range(1, 4)：4 张以上的批量会少铺几件，而且**看不出少了**
       （页面上就是缺几格）。张数、件数都该以磁盘为准。"""
    tags = set()
    try:
        for fn in os.listdir(d):
            if len(fn) > 3 and fn[:2].isdigit() and fn[2] == "-":
                tags.add(fn[:2])
    except OSError:
        pass
    return sorted(tags)


def _project_files(jid, d, kind="minicd-design"):
    """只收录磁盘上真的存在的件 —— 不给出会 404 的地址。
    🔴 批量任务的文件名带序号前缀（01-disc.png / 01-打印拼版-A4.png），
       与单张的 part-disc.png 不同名；不分支处理会让批量项目在库里显示「0 件」。"""
    out = {}
    if kind in BATCH_KINDS:
        if (d / BATCH_SHEET).is_file():
            out["sheet"] = _proj_url(jid, BATCH_SHEET)
        # 按磁盘上的真实序号铺件（前 MAX_BATCH_PARTS 张够回看与核对，
        # 不必把几十个文件全列出来；张数由 _project_of 照实数写进 counts）
        for tag in _batch_tags(d)[:MAX_BATCH_PARTS]:
            for key, fn in (("disc", tag + "-disc.png"),
                            ("cover", tag + "-cover.png"),
                            ("strip", tag + "-strip.png"),
                            ("print", tag + "-打印拼版-A4.png")):
                if (d / fn).is_file():
                    out[key + tag] = _proj_url(jid, fn)
        return out
    for key, _label, fn in PROJ_FILES:
        try:
            if (d / fn).is_file():
                out[key] = _proj_url(jid, fn)
        except OSError:
            continue
    return out


def _project_of(jid, d):
    """一个任务目录 → 一条项目库条目。
    🔴 逐字段形状防御：一条坏 meta 只能让自己不出现在库里，
       绝不能让 /api/jobs（作品库）整个 500（那样整个作品库都打不开）。"""
    # 🔴 meta 缺失/损坏**不再整条丢掉**：出件本身就在磁盘上，回看/下载照样可用。
    #    只有「既没有 meta、又一件都没有」才认定它不是项目（见下面 files 那段）。
    m = {}
    try:
        _raw = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        if isinstance(_raw, dict):
            m = _raw
    except Exception:
        m = {}

    kind = _as_str(m.get("kind"), 40) or "minicd-design"
    # meta 没说批量、但文件名是 01-disc.png 这种带序号的 → 其实就是批量
    # （更早版本落盘的，或 meta 丢了）。不认出来就会走单张分支找
    # part-disc.png，结果在库里显示「0 件」。
    if kind not in BATCH_KINDS and (d / "01-disc.png").is_file():
        kind = "minicd-design-batch"
    # 🔴 必须把 kind 传下去：批量任务的文件名带序号前缀（01-disc.png），
    #    不传 kind 就永远走单张分支 → 批量项目在库里显示「0 件」（踩过一次，
    #    当时只测了 _project_files 本身、没测 _project_of 的调用点）。
    files = _project_files(jid, d, kind)
    # 缩略图优先盘面（方形、辨识度最高），依次退封件 / 总览；
    # 批量任务的键带序号（disc01），所以两边都要认，否则只能退到那张宽幅对照图。
    thumb = (files.get("disc") or files.get("disc01")
             or files.get("cover") or files.get("cover01")
             or files.get("sheet") or "")
    if not files and not m:
        return None          # 既没 meta 又一件都没有 → 不是项目，别列出来

    album = _as_str(m.get("album"), 120)
    artist = _as_str(m.get("artist"), 120)
    sub, count = "", 1
    if kind in BATCH_KINDS:
        names = []
        albums = m.get("albums")
        if isinstance(albums, list):
            for a in albums[:60]:
                if isinstance(a, dict):
                    n = _as_str(a.get("album"), 120)
                    if n:
                        names.append(n)
        sub = " / ".join(names[:3]) + ("…" if len(names) > 3 else "")
        c = m.get("count")
        # bool 是 int 的子类，得先排掉
        # 🔴 meta 没有 count（老版本落盘 / meta 丢了）时，数磁盘上的序号来定张数
        tag_n = len(_batch_tags(d))
        count = c if isinstance(c, int) and not isinstance(c, bool) \
            and 0 <= c <= 999 else (len(names) or tag_n or 1)
        if not album:
            album = "批量 · %d 张" % count

    tracks = _as_list(m.get("tracks"))
    try:
        ts = float(d.stat().st_mtime)
    except Exception:
        ts = 0.0
    if ts != ts or ts in (float("inf"), float("-inf")):
        ts = 0.0

    return {
        "jid": jid, "kind": kind,
        "album": album, "artist": artist, "sub": sub,
        "company": _as_str(m.get("company"), 80),
        "mood": _as_str(m.get("mood"), 40),
        "style": _as_str(m.get("style"), 40),
        "tracks": tracks, "trackCount": len(tracks),
        "hasAi": _as_bool(m.get("hasAi")),
        "count": count,
        "created": _as_str(m.get("created"), 24),
        "ts": round(ts, 3),
        "pic": _as_str(m.get("pic"), 600),
        "safeBands": _as_str(m.get("safeBands"), 40),
        "files": files, "fileCount": len(files), "thumb": thumb,
        "zipUrl": ("/api/design/zip?jid=%s" % jid) if files else "",
        "empty": not files,
    }


def list_projects(limit=240):
    """铺出全部历史项目（磁盘留档），新的在前。"""
    try:
        limit = int(str(limit))
    except Exception:
        limit = 240
    limit = max(1, min(limit, 1000))

    entries = []
    try:
        for d in OUT_DIR.iterdir():
            if not d.is_dir() or d.name.startswith("_"):
                continue          # 跳过 _trash 等内部目录
            if not _safe_jid(d.name):
                continue          # 非任务目录（防路径穿越 + 防误收）
            entries.append(d)
    except Exception as e:
        _slog("projects scan failed:", type(e).__name__, e)

    def _mtime(p):
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    entries.sort(key=_mtime, reverse=True)

    items, skipped, bad = [], 0, []
    for d in entries:
        try:
            it = _project_of(d.name, d)
        except Exception as e:      # 兜底：_project_of 已尽量不抛，但别赌
            _slog("project card failed:", d.name, type(e).__name__, e)
            it = None
            # 🔴 失败原因必须带出去。只写日志等于没写：界面上表现成
            #    "作品库少了几条"，而少几条肉眼根本看不出来（踩过一次：
            #    BATCH_SHEET 未定义 → 三个批量项目静默消失）。
            if len(bad) < 20:
                bad.append({"jid": d.name,
                            "error": "%s: %s" % (type(e).__name__, e)})
        if it is None:
            skipped += 1
            continue
        items.append(it)
        if len(items) >= limit:
            break

    return {"ok": True, "count": len(items), "skipped": skipped, "bad": bad,
            "total": len(entries), "dir": str(OUT_DIR), "items": items}


def trash_project(jid):
    """移入回收站 —— 是「移走」不是「删除」：
    整个任务目录连 ZIP 一起挪到 OUT_DIR/_trash/<时间戳>-<jid>/，
    想找回把里面的 <jid> 目录挪回 OUT_DIR 即可。"""
    jid = _safe_jid(jid)
    if not jid:
        raise ValueError("任务号不合法")
    src = OUT_DIR / jid
    if not src.is_dir():
        raise ValueError("项目不存在（可能已被清理）")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = TRASH_DIR / ("%s-%s" % (stamp, jid))
    try:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest / jid))
    except Exception as e:
        raise ValueError("移入回收站失败：%s" % e)

    z = OUT_DIR / ("%s.zip" % jid)
    if z.is_file():
        try:
            shutil.move(str(z), str(dest / z.name))
        except Exception as e:
            # ZIP 没挪走不算失败：目录已经进回收站，ZIP 留在原地不影响打开
            _slog("trash zip move failed:", type(e).__name__, e)

    _slog("trash", jid, "->", dest)
    return {"ok": True, "jid": jid, "trashDir": str(dest),
            "note": "已移入回收站（未删除）；把里面的 %s 目录移回 %s 即可恢复"
                    % (jid, OUT_DIR)}


def _serve_file(handler, jid, name):
    jid = _safe_jid(jid)
    if not jid:
        return handler._json({"error": "bad jid"}, 400)
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return handler._json({"error": "bad name"}, 400)
    base = (OUT_DIR / jid).resolve()
    fp = (base / name).resolve()
    if not fp.is_file():
        return handler._json({"error": "not found"}, 404)
    if str(fp) != str(base / name):
        return handler._json({"error": "forbidden"}, 403)
    return handler._file(str(fp))


def _serve_preview_file(handler, token, name):
    token = _safe_jid(token)
    if not token or not token.startswith("p-"):
        return handler._json({"error": "bad preview token"}, 400)
    name = (name or "").strip()
    if name not in {"disc.png", "cover.png", "strip.png"}:
        return handler._json({"error": "bad preview file"}, 400)
    base = (PREVIEW_DIR / token).resolve()
    fp = (base / name).resolve()
    if not fp.is_file() or fp.parent != base:
        return handler._json({"error": "preview expired"}, 404)
    return handler._file(str(fp))


def handle(handler, path, query, method):
    if not path.startswith("/api/design/"):
        return False

    def value(name, default=""):
        return (query.get(name) or [default])[0]

    try:
        if method == "POST":
            length = int(handler.headers.get("Content-Length", "0"))
            raw = handler.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            # query 作为兜底合入（个别前端习惯用 query 传参）
            for k, v in query.items():
                data.setdefault(k, v[0] if isinstance(v, list) and v else v)
            if path == "/api/design/title-assets":
                upload = _upload_path(data.get("upload"))
                if not upload:
                    handler._json({"error": "标题上传不存在"}, 400)
                    return True
                try:
                    asset = TA.save_title_asset(upload, data.get("album") or "")
                except ValueError as exc:
                    handler._json({"error": str(exc)}, 400)
                    return True
                handler._json({"ok": True, "asset": asset.to_dict()})
                return True
            if path == "/api/design/batch":
                handler._json(build_batch(data))
                return True
            if path == "/api/design/preview":
                handler._json(build_preview(data))
                return True
            handler._json(build_job(data))
            return True

        # ---------------- GET ----------------
        if path == "/api/design/spec":
            # 尺寸 / 分段语义 / 印刷规格快照（唯一真源 spec_minicd）
            # 前端实尺寸画布与「生产规格 JSON」导出共用同一份，杜绝尺寸写死后漂移
            handler._json({"ok": True, "spec": SP.spec_dict()})
            return True
        if path == "/api/design/album":
            artist = value("artist"); album = value("album"); pic = value("pic")
            company = value("company")
            tracks = _norm_tracks(value("tracks", ""))
            cover = _fetch_cover(pic)
            if cover is None:
                handler._json({"ok": False, "error": "封面拉取失败：%s" % pic}, 400)
                return True
            D = _read_design(cover, value("mood", ""), value("style", ""),
                             _parse_bands(value("safeBands", "")))
            notes = DP.design_notes(D, album, artist, tracks, has_lyrics=False)
            handler._json({
                "ok": True,
                "design": {"mood": D["mood"], "style": D["style"],
                           "main": list(D["main"]),
                           "palette": [list(c) for c in D["palette"][:6]]},
                "notes": notes, "coverSize": list(cover.size),
            })
            return True
        if path == "/api/design/file":
            _serve_file(handler, value("jid"), value("name"))
            return True
        if path == "/api/design/preview-file":
            _serve_preview_file(handler, value("token"), value("name"))
            return True
        if path == "/api/design/zip":
            jid = _safe_jid(value("jid"))
            if not jid:
                handler._json({"error": "bad jid"}, 400)
                return True
            zp = OUT_DIR / ("%s.zip" % jid)
            if not zp.is_file():
                handler._json({"error": "任务尚未生成或已清理"}, 404)
                return True
            handler._file(str(zp), name="迷你CD设计-%s.zip" % jid)
            return True
        if path == "/api/design/state":
            jid = _safe_jid(value("jid"))
            mp = (OUT_DIR / jid / "meta.json") if jid else None
            if not mp or not mp.is_file():
                handler._json({"error": "not found"}, 404)
                return True
            handler._json(json.loads(mp.read_text(encoding="utf-8")))
            return True
        handler._json({"error": "接口不存在"}, 404)
    except (ValueError, KeyError, TypeError) as e:
        handler._json({"error": str(e)}, 400)
    except Exception as e:
        _slog("handle error:", type(e).__name__, e)
        handler._json({"error": "处理失败：%s" % e}, 500)
    return True


class DesignService:
    """迷你CD 设计工作台后端（接口契约同 PackagingService.handle）。"""
    def handle(self, handler, path, query, method):
        return handle(handler, path, query, method)


SERVICE = DesignService()
