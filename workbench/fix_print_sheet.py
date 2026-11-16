"""Regenerate the annotations around saved parts without changing artwork."""
import json
import os
import sys
import design_service as s
from PIL import Image


def main(jid, prefix=''):
    jid = s._safe_jid(jid)
    if not jid or (prefix and (not prefix.isdigit() or len(prefix) > 3)):
        raise ValueError('项目不存在')
    base = s.OUT_DIR / jid
    meta = json.loads((base / 'meta.json').read_text(encoding='utf-8'))
    if prefix:
        row = next((a for a in meta.get('albums', []) if str(a.get('no')) == prefix), None)
        if not row:
            raise ValueError('专辑不存在')
        names = {k: prefix + '-' + v for k, v in {'disc':'disc.png', 'fold':'cover.png', 'strip':'strip.png', 'cover':'封面.png'}.items()}
    else:
        row = meta
        names = {'disc':'part-disc.png', 'fold':'part-cover.png', 'strip':'part-strip.png', 'cover':'封面.png'}
    images = {}
    for key, name in names.items():
        with Image.open(base / name) as im:
            images[key] = im.copy()
    dpi = round(images['fold'].width * 25.4 / s.SP.COVER_W)
    if dpi < 500:
        raise ValueError('旧版无需修复')
    design = s._read_design(images['cover'], row.get('mood', ''), row.get('style', ''), None)
    target = base / ('sheet-fixed-v2-' + (prefix or 'single') + '.png')
    tmp = base / ('sheet-fixed-' + str(os.getpid()) + '.png')
    s.MS.build_sheet(images['cover'], row.get('album', ''), row.get('artist', ''), design,
                     s._norm_tracks(row.get('tracks')), row.get('company', ''), str(tmp), dpi, png=True,
                     rendered_parts={'rendered_disc': (images['disc'], False),
                                     'rendered_fold': (images['fold'], False),
                                     'rendered_strip': (images['strip'], False)})
    os.replace(tmp, target)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '')
