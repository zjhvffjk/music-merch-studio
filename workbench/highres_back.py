"""Re-render an unchanged generated back insert for product-image export."""
import json
import os
import sys
from pathlib import Path

import design_service as s
from PIL import Image, ImageChops, ImageStat


def render(meta, dpi):
    cover = s._fetch_cover(meta.get('pic'))
    if cover is None:
        raise ValueError('原始封面不可用')
    design = s._read_design(cover, meta.get('mood', ''), meta.get('style', ''),
                            s._parse_bands(meta.get('safeBands')))
    settings = s.CT.normalize_copy_settings(meta)
    settings['resolvedLayout'] = s.CT.recommend_copy_layout(settings, design)
    token = s.TYPO.set_font_overrides(settings.get('typography'))
    try:
        return s.DP.design_back2(
            cover, s.mm(s.SP.BACK_SEGS[1], dpi), s.mm(s.SP.BACK_H, dpi),
            design, meta.get('album', ''), meta.get('artist', ''),
            s._norm_tracks(meta.get('tracks')), quote=meta.get('innerCopy') or None,
            company=meta.get('company', ''), barcode_code=meta.get('barcode', ''),
            copyright_text=meta.get('copyright', ''), release_year=meta.get('releaseYear', ''),
            back_layout=meta.get('backLayout', 'auto'), copy_settings=settings,
            elements=s._ai_elements(meta).get('back'),
            ink_override=s.part_ink_from_copy(settings).get('back'),
            text_scale=s.part_scale_from_copy(settings).get('back'),
            text_font=s.part_font_from_copy(settings).get('back'),
            text_style=s.part_style_from_copy(settings).get('back'))
    finally:
        s.TYPO.reset_font_overrides(token)


def main(jid):
    jid = s._safe_jid(jid)
    if not jid:
        raise ValueError('项目不存在')
    base = s.OUT_DIR / jid
    meta = json.loads((base / 'meta.json').read_text(encoding='utf-8'))
    if meta.get('kind') != 'minicd-design' or meta.get('hasAi') or not meta.get('pic'):
        raise ValueError('此项目不能安全地重建封底')
    original = Image.open(base / '封底.png').convert('RGB')
    source_dpi = round(original.width * 25.4 / s.SP.BACK_SEGS[1])
    rebuilt = render(meta, source_dpi).convert('RGB')
    if original.size != rebuilt.size or max(ImageStat.Stat(ImageChops.difference(original, rebuilt)).mean) > 6:
        raise ValueError('保存的封底与原设计不一致，保留现有图片')
    result = render(meta, 1800)
    target = base / '高清商品图封底-v1.png'
    tmp = base / ('highres-back-' + str(os.getpid()) + '.tmp')
    result.save(tmp, format='PNG')
    os.replace(tmp, target)


if __name__ == '__main__':
    main(sys.argv[1])
