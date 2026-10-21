#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
酷狗音乐抓取工具  (fetch_kugou.py)

**为什么要第三个数据源**
  QQ音乐搜索接口偶发限流（code=0 但 0 条命中），网易云缺腾讯系版权，
  酷狗的 mobile 公开接口无需登录、限流宽松 —— 作为两家的补充与兜底：
  单曲搜索能补到 QQ/网易云没有的版本，酷狗侧的版权曲目（部分周杰伦
  翻唱源、独立音乐人）也只在酷狗有。

接口（公开 web 接口，无需登录）
  搜索单曲  mobiles.kugou.com/api/v3/search/song?keyword=&pagesize=
  搜索歌手  mobiles.kugou.com/api/v3/search/singer?keyword=
            ⚠️ 这个接口的 data 直接就是数组（不是 {info: []}），别套错层
  歌手歌曲  mobiles.kugou.com/api/v3/singer/song?singerid=
            ⚠️ 条目里没有 songname，只有 filename（"歌手 - 歌名"），要拆
  专辑封面  mobiles.kugou.com/api/v3/album/info?albumid=
            ⚠️ imgurl 里带 {size} 占位符，必须替换成 120/240/480 才能访问

用法:
  python fetch_kugou.py search "范特西"
  python fetch_kugou.py singer "周杰伦"
"""
import noproxy  # noqa: F401  必须在发请求之前：本地地址 + 国内音乐接口直连
import json
import sys
import urllib.parse
import urllib.request

UA = {
    "User-Agent": ("Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"),
    "Referer": "https://m.kugou.com/",
}
BASE = "https://mobiles.kugou.com/api/v3"

COVER_SIZES = (120, 240, 480)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def _j(url):
    return json.loads(_get(url))


def album_cover_url(album_id, size=480):
    """专辑封面直链。查不到返回空串（调用方按无封面处理）。"""
    if not album_id:
        return ""
    try:
        size = min((s for s in COVER_SIZES if s >= size), default=COVER_SIZES[-1])
        d = (_j(f"{BASE}/album/info?albumid={int(album_id)}").get("data") or {})
        u = d.get("imgurl") or ""
        return u.replace("{size}", str(size)) if u else ""
    except Exception:
        return ""


def _norm_song(it, default_singer=""):
    """把酷狗条目规范成与 fetch_qq.hot_songs_q 一致的结构。

    search/song 有 songname/singername；singer/song 只有
    filename（"歌手 - 歌名"），要在这一步拆开，调用方不用关心差异。
    """
    name = (it.get("songname") or "").strip()
    singer = (it.get("singername") or "").strip()
    if not name:
        fn = (it.get("filename") or "").strip()
        if " - " in fn:
            singer = singer or fn.split(" - ", 1)[0].strip()
            name = fn.split(" - ", 1)[1].strip()
        else:
            name = fn
    return {
        "source": "kugou",
        "id": it.get("album_audio_id") or it.get("audio_id"),
        "hash": it.get("hash") or "",
        "name": name,
        "artists": singer or default_singer,
        "album": (it.get("album_name") or "").strip(),
        "album_id": it.get("album_id"),
        "dur_ms": (it.get("duration") or 0) * 1000,
    }


def search_song(kw, n=15):
    """搜索单曲。返回统一结构列表（含 album_id，封面按需懒解析）。"""
    if not (kw or "").strip():
        return []
    q = urllib.parse.quote(kw.strip())
    j = _j(f"{BASE}/search/song?format=json&keyword={q}"
           f"&page=1&pagesize={min(max(n, 1), 100)}&signature=1")
    info = ((j.get("data") or {}).get("info")) or []
    return [_norm_song(s) for s in info if _norm_song(s)["name"]]


def search_album(kw, n=8):
    """搜索专辑。返回统一结构列表。

    专辑搜索接口的 imgurl 直接给封面（带 {size} 占位符），
    不需要像单曲那样再去 album/info 懒解析。
    """
    if not (kw or "").strip():
        return []
    q = urllib.parse.quote(kw.strip())
    j = _j(f"{BASE}/search/album?format=json&keyword={q}"
           f"&page=1&pagesize={min(max(n, 1), 100)}")
    info = ((j.get("data") or {}).get("info")) or []
    out = []
    for a in info:
        name = (a.get("albumname") or "").strip()
        if not name:
            continue
        img = (a.get("imgurl") or a.get("sizable_cover") or "")
        out.append({
            "source": "kugou",
            "id": a.get("albumid"),
            "name": name,
            "singer": (a.get("singername") or "").strip(),
            "date": (a.get("publishtime") or "")[:10],
            "count": a.get("songcount") or 0,
            "pic": img.replace("{size}", "480") if img else "",
        })
    return out


def search_singer(kw, n=5):
    """搜索歌手。返回 [{'id': singerid, 'name': singername}, ...]。

    注意：这个接口的 data 直接是数组，没有 info 包装层。
    """
    if not (kw or "").strip():
        return []
    q = urllib.parse.quote(kw.strip())
    j = _j(f"{BASE}/search/singer?format=json&keyword={q}"
           f"&page=1&pagesize={min(max(n, 1), 50)}")
    rows = j.get("data") or []
    if isinstance(rows, dict):          # 接口偶尔会包一层 info，兜一下
        rows = rows.get("info") or []
    out = []
    for r in rows or []:
        nm = (r.get("singername") or "").strip()
        if r.get("singerid") and nm:
            out.append({"id": r["singerid"], "name": nm})
    return out


def singer_hot_songs(singerid, n=30):
    """歌手热门歌曲（接口默认按热度排序）。"""
    if not singerid:
        return []
    j = _j(f"{BASE}/singer/song?singerid={int(singerid)}"
           f"&page=1&pagesize={min(max(n, 1), 100)}")
    info = ((j.get("data") or {}).get("info")) or []
    return [_norm_song(s) for s in info if _norm_song(s)["name"]]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="酷狗音乐抓取")
    ap.add_argument("cmd", choices=["search", "singer", "songs", "cover"])
    ap.add_argument("kw")
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "search":
        for s in search_song(a.kw, a.n):
            print(f"- {s['name']} | {s['artists']} | {s['album']} | "
                  f"album_id={s['album_id']}")
    elif a.cmd == "singer":
        for r in search_singer(a.kw, a.n):
            print(f"- {r['name']} | singerid={r['id']}")
    elif a.cmd == "songs":
        for s in singer_hot_songs(int(a.kw), a.n):
            print(f"- {s['name']} | {s['artists']} | {s['album']}")
    elif a.cmd == "cover":
        print(album_cover_url(int(a.kw)))
