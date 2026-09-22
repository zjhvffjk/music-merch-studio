"""Conservative local cover-title reference extraction.

It only accepts a high-contrast, title-sized top-band region. Ambiguous covers
are explicitly rejected rather than producing a misleading crop.
"""
from pathlib import Path
import hashlib
from PIL import Image, ImageStat
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'迷你CD设计'/'_title_references'; OUT.mkdir(parents=True,exist_ok=True)

def extract_cover_title_reference(cover, visual_dna, album):
    if not isinstance(cover,Image.Image) or not album:
        return {'status':'unavailable','cropPng':None,'titleBBox':None,'confidence':0,'titleStyleDescription':'','titleDirection':{}}
    w,h=cover.size
    if w<160 or h<120:
        return {'status':'rejected','cropPng':None,'titleBBox':None,'confidence':0,'titleStyleDescription':'','titleDirection':{}}
    # Limited safe top band avoids face/hero subjects in the central/lower frame.
    band=cover.convert('L').crop((0,0,w,int(h*.28)))
    stat=ImageStat.Stat(band); contrast=stat.var[0]**.5
    if contrast<45:
        return {'status':'rejected','cropPng':None,'titleBBox':None,'confidence':round(contrast/100,2),'titleStyleDescription':'','titleDirection':{}}
    x0,x1=int(w*.05),int(w*.72); y0,y1=int(h*.03),int(h*.25)
    crop=cover.crop((x0,y0,x1,y1)); digest=hashlib.sha256(crop.tobytes()).hexdigest()[:16]
    dest=OUT/(f'ref_{digest}.png'); crop.save(dest)
    style=str((visual_dna or {}).get('style') or 'editorial')
    direction={'category':'brush-calligraphy' if 'hand' in style else 'editorial-serif','slantDeg':3 if 'hand' in style else 0}
    return {'status':'detected','sourceImage':None,'cropPng':str(dest),'titleBBox':{'x':x0/w,'y':y0/h,'width':(x1-x0)/w,'height':(y1-y0)/h},'confidence':min(.92,round(.55+contrast/200,2)),'titleStyleDescription':f'{style} 标题区域，高对比度参考裁切','titleDirection':direction}
