"""Artist biography and paged credits migrated from the local 8011 studio.

Independent of the legacy popular-song source selection. IDs here are always
resolved in NetEase's namespace; returned songs keep their actual performers.
"""
import copy
import hashlib
import json
import threading
import time

import requests

API = 'https://music.163.com/api'
ROLES = {1: '演唱', 2: '作词', 3: '作曲', 4: '编曲', 5: '制作', 6: '演奏'}
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://music.163.com/'}
_CACHE = {}
_LOCK = threading.Lock()


def _cached(key, fetch):
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[0] < 300:
            return copy.deepcopy(hit[1])
    result = fetch()  # Exceptions are deliberately not cached.
    with _LOCK:
        if len(_CACHE) >= 160:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (time.monotonic(), copy.deepcopy(result))
    return result


def _check(body):
    if not isinstance(body, dict) or body.get('code', 200) != 200 or 'verifyType' in body:
        raise RuntimeError('网易云资料接口暂时不可用，请稍后重试')
    return body


def _get(path, params=None):
    response = requests.get(API + path, params=params, headers=HEADERS, timeout=12)
    response.raise_for_status()
    return _check(response.json())


def resolve_artist(name):
    name = str(name).strip()[:100]
    if not name:
        raise ValueError('缺少歌手名')

    def fetch():
        body = _get('/search/get', {'s': name, 'type': 100, 'limit': 15, 'offset': 0})
        artists = (body.get('result') or {}).get('artists') or []
        for artist in artists:
            names = [artist.get('name', ''), *(artist.get('alias') or []), *(artist.get('transNames') or [])]
            if any(str(value).casefold() == name.casefold() for value in names):
                return artist
        raise RuntimeError('未找到名称匹配的网易云歌手，现有热门歌曲仍可使用')
    return _cached(('resolve', name.casefold()), fetch)


def song_brief(song):
    artists = song.get('ar') or song.get('artists') or []
    album = song.get('al') or song.get('album') or {}
    seconds = int(song.get('dt') or song.get('duration') or 0) // 1000
    return {'id': song.get('id'), 'name': song.get('name', ''),
            'artist': ' / '.join(a.get('name', '') for a in artists if isinstance(a, dict)),
            'album': album.get('name', ''), 'albumId': album.get('id'),
            'pic': album.get('picUrl', ''), 'dur': f'{seconds // 60:02d}:{seconds % 60:02d}',
            'source': '163'}


def profile(name):
    def fetch():
        resolved = resolve_artist(name)
        body = _get('/v1/artist/' + str(int(resolved['id'])))
        artist = body.get('artist') or {}
        if not artist:
            raise RuntimeError('未取到歌手资料，请重试')
        return {'artist': {'id': artist.get('id') or resolved['id'], 'name': artist.get('name', name),
            'aliases': artist.get('alias') or resolved.get('alias') or [],
            'brief': (artist.get('briefDesc') or '').strip(),
            'pic': artist.get('picUrl') or artist.get('img1v1Url') or '',
            'musicSize': artist.get('musicSize') or 0, 'albumSize': artist.get('albumSize') or 0,
            'mvSize': artist.get('mvSize') or 0}, 'source': '163'}
    return _cached(('profile', str(name).casefold()), fetch)


def _eapi(path, payload):
    # Same client protocol as 8011; AES is imported lazily so other studio
    # functions continue working even before the optional dependency is installed.
    from Crypto.Cipher import AES
    key = b'e82ckenh8dichen8'
    text = json.dumps(payload, separators=(',', ':'))
    digest = hashlib.md5(f'nobody{path}use{text}md5forencrypt'.encode()).hexdigest()
    raw = f'{path}-36cd479b6b5-{text}-36cd479b6b5-{digest}'.encode()
    n = 16 - len(raw) % 16
    encrypted = AES.new(key, AES.MODE_ECB).encrypt(raw + bytes([n]) * n).hex().upper()
    headers = dict(HEADERS, Cookie='os=pc; appver=3.1.19.204510;')
    response = requests.post('https://interface.music.163.com/eapi' + path,
        data={'params': encrypted}, headers=headers, timeout=15)
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError:
        plain = AES.new(key, AES.MODE_ECB).decrypt(response.content)
        body, _ = json.JSONDecoder().raw_decode(plain.decode('utf-8', 'ignore'))
    return _check(body)


def works(artist_id, work_type=1, limit=50, offset=0):
    artist_id, work_type, limit, offset = map(int, (artist_id, work_type, limit, offset))
    if artist_id <= 0 or work_type not in ROLES or not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise ValueError('歌手、作品分类或分页参数无效')

    def fetch():
        body = _check(_eapi('/api/v1/artist/songs', {
            'header': {'os': 'pc', 'appver': '3.1.19.204510', 'requestId': 0}, 'e_r': True,
            'id': str(artist_id), 'private_cloud': 'true', 'work_type': work_type,
            'order': 'hot', 'offset': offset, 'limit': limit}))
        if not isinstance(body.get('songs'), list):
            raise RuntimeError('作品接口没有返回有效列表，请重试')
        songs = [song_brief(s) for s in body['songs']]
        total = int(body.get('total') or len(songs))
        return {'songs': songs, 'total': total, 'more': bool(body.get('more', offset + len(songs) < total)),
                'offset': offset, 'limit': limit, 'role': ROLES[work_type], 'source': '163'}
    return _cached(('works', artist_id, work_type, limit, offset), fetch)
