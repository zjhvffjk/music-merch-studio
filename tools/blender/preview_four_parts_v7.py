from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path('D:/MusicMerchStudio/blender/rebuild-20261119-v7')
canvas = Image.new('RGB', (1400, 1500), 'white')
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 32)
parts = [('22-左盖独立正投影.png', '① 左盖'), ('26-右底壳独立结构.png', '② 右底壳'), ('14-独立盘托灰模.png', '③ 透明盘托'), ('15-独立光盘灰模.png', '④ 光盘')]
for i, (file, label) in enumerate(parts):
    image = Image.open(out / file).convert('RGB')
    image.thumbnail((690, 690))
    x, y = (i % 2) * 700, (i // 2) * 750
    canvas.paste(image, (x + (700-image.width)//2, y))
    draw.text((x+350, y+715), label, font=font, fill='#333333', anchor='mm')
canvas.save(out / '四个独立组件预览.png')
