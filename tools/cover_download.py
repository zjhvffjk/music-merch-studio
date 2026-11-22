"""Download complete cover images, including recovery from a truncated NetEase response."""

import io
import re
import time
from collections import OrderedDict
from http.client import HTTPException, IncompleteRead
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib import request

from PIL import Image

_cache = OrderedDict()
_cache_lock = Lock()


def _netease_variants(url):
    parsed = urlsplit(url)
    if not re.fullmatch(r"p[1-4]\.music\.126\.net", parsed.netloc.lower()):
        return url, None
    mirror = "p2.music.126.net" if parsed.hostname == "p1.music.126.net" else "p1.music.126.net"
    alternate = parsed._replace(netloc=mirror)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    size = re.fullmatch(r"(\d+)y(\d+)", dict(pairs).get("param", ""))
    if size and max(map(int, size.groups())) <= 1600:
        return alternate.geturl(), None
    query = [(key, value) for key, value in pairs if key != "param"]
    query.append(("param", "1600y1600"))
    return alternate.geturl(), alternate._replace(query=urlencode(query)).geturl()


def fetch_cover_bytes(url, headers, *, minimum=1, attempts=3):
    """Keep original resolution on normal downloads and retry safely on transfer failure."""
    key = (url, headers.get("Referer"))
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic() and len(cached[1]) >= minimum:
            _cache.move_to_end(key)
            return cached[1]

    alternate, smaller = _netease_variants(url)
    candidates = [(url, 7), (alternate, 12)]
    if smaller:
        candidates.append((smaller, 12))
    error = None
    headers = {name: headers[name] for name in ("User-Agent", "Referer") if name in headers}
    for _ in range(max(1, attempts)):
        if not candidates:
            break
        target, timeout = candidates.pop(0)
        try:
            with request.urlopen(request.Request(target, headers=headers), timeout=timeout) as response:
                data = response.read()
            if len(data) < minimum:
                raise ValueError("封面响应为空或不完整")
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        except HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code not in (408, 429):
                raise
            error = exc
            continue
        except IncompleteRead as exc:
            error = exc
            if smaller and target != smaller:
                # The original response was cut short. Keep the image and use
                # the provider's 1600px variant to reduce the transfer size.
                candidates = [(smaller, 12)]
            continue
        except (OSError, HTTPException, ValueError) as exc:
            error = exc
            continue

        if len(data) <= 8 * 1024 * 1024:
            with _cache_lock:
                _cache[key] = (time.monotonic() + 600, data)
                _cache.move_to_end(key)
                while len(_cache) > 8:
                    _cache.popitem(last=False)
        return data
    raise error
