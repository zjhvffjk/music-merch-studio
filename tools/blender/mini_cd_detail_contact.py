"""Actual macro renders arranged for review; no reference texture compositing."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[2]
out=root/'blender/rebuild-20261119-v4'
canvas=Image.new('RGB',(1640,1740),'#f2f2ef')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',30)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',23)
draw.text((30,20),'第四版 · 实体几何细节近景',font=font,fill='#222222')
items=[('外框：双层凹槽与圆边','17-外框凹槽近景.png'),
       ('铰链：端面、凹腔与窗口座','18-铰链端座近景.png'),
       ('压纸卡舌：凹面、弧口和根脚','19-压纸卡舌近景.png'),
       ('双弹舌：中空扣头、定位点和浅槽','20-双弹舌盘扣近景.png')]
for i,(title,name) in enumerate(items):
    x=20+(i%2)*820
    y=85+(i//2)*800
    draw.text((x+10,y),title,font=small,fill='#222222')
    # Preserve the image aspect ratio in the contact sheet.
    im=Image.open(out/name).convert('RGB')
    im.thumbnail((780,740),Image.Resampling.LANCZOS)
    canvas.paste(im,(x+(800-im.width)//2,y+42+(740-im.height)//2))
draw.text((30,1700),'灰材质用于显示结构；均为模型实际渲染，尺寸细部仍按参考估算。',font=small,fill='#444444')
canvas.save(out/'细节近景总览.png')
