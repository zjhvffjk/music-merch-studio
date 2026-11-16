"""Rebuild a saved, unmodified design's A4 print page at 600 DPI."""
import json
import os
import sys
import design_service as s
from PIL import Image, ImageChops, ImageStat


def main(jid):
    jid = s._safe_jid(jid)
    if not jid:
        raise ValueError('项目不存在')
    base = s.OUT_DIR / jid
    meta = json.loads((base / 'meta.json').read_text(encoding='utf-8'))
    if meta.get('kind') != 'minicd-design' or meta.get('hasAi') or not meta.get('pic'):
        raise ValueError('无法安全重建自定义素材')
    cover = s._fetch_cover(meta['pic'])
    if cover is None:
        raise ValueError('原始封面不可用')
    design = s._read_design(cover, meta.get('mood', ''), meta.get('style', ''),
                            s._parse_bands(meta.get('safeBands')))
    settings = s.CT.normalize_copy_settings(meta)
    settings['resolvedLayout'] = s.CT.recommend_copy_layout(settings, design)
    token = s.TYPO.set_font_overrides(settings.get('typography'))
    try:
        def parts(dpi):
            return s.build_parts(cover, meta.get('album', ''), meta.get('artist', ''),
                design, s._norm_tracks(meta.get('tracks')), meta.get('company', ''), None, dpi,
                meta.get('innerCopy', ''), meta.get('barcode', ''), meta.get('copyright', ''),
                meta.get('releaseYear', ''), meta.get('backLayout', 'auto'), settings,
                ai_elements=s._ai_elements(meta))
        disc, fold, strip = parts(300)
        for name, rebuilt in (('part-cover.png', fold), ('part-strip.png', strip)):
            with Image.open(base / name) as src:
                original = src.convert('RGB')
            rebuilt = rebuilt.convert('RGB')
            if original.size != rebuilt.size or max(ImageStat.Stat(ImageChops.difference(original, rebuilt)).mean) > 6:
                raise ValueError('原设计与保存的素材不一致')
        del disc, fold, strip
        disc, fold, strip = parts(600)
        del disc
        page = s.MC.build_page_portrait7(fold, strip, 600, meta.get('artist', ''), meta.get('album', ''), sets=7)
        for suffix in ('png', 'pdf'):
            target = base / ('高清打印拼版-A4竖版7套-v1.' + suffix)
            temp = base / ('highres-print-' + str(os.getpid()) + '.' + suffix)
            if suffix == 'png':
                page.save(temp, format='PNG', dpi=(600, 600))
            else:
                page.save(temp, format='PDF', resolution=600)
            os.replace(temp, target)
    finally:
        s.TYPO.reset_font_overrides(token)


if __name__ == '__main__':
    main(sys.argv[1])
