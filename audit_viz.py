import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np, json
BASE=r"C:\Users\CH\WorkBuddy\迷你唱片机"
KDIR=os.path.join(BASE,"outputs","周杰伦-热门前5","keychain")
ODIR=os.path.join(BASE,"outputs","周杰伦-热门前5")
files=["01 晴天 - 周杰伦-钥匙扣.jpg","02 搁浅 - 周杰伦-钥匙扣.jpg",
       "03 红尘客栈 - 周杰伦-钥匙扣.jpg","04 夜曲 - 周杰伦-钥匙扣.jpg",
       "05 青花瓷 - 周杰伦-钥匙扣.jpg"]
# ring bbox from overlay analysis
RBOX=(754,280,1170,720)
RBX=RBOX
MARGIN=60
RCROP=(RBOX[0]-MARGIN, RBOX[1]-MARGIN, RBOX[2]+MARGIN, RBOX[3]+MARGIN)

def label(img,text):
    d=ImageDraw.Draw(img)
    try:
        fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
    except:
        fnt=ImageFont.load_default()
    d.text((8,6),text,fill=(255,0,0),font=fnt)
    return img

# full grid: 2 rows x 5 cols
ims=[Image.open(os.path.join(KDIR,f)) for f in files]
sz=380
thumbs=[im.resize((sz,sz),Image.Resampling.LANCZOS) for im in ims]
crops=[im.crop(RCROP).resize((sz,sz),Image.Resampling.LANCZOS) for im in ims]
for i,th in enumerate(thumbs): label(th,f"#0{i+1}")
for i,cr in enumerate(crops): label(cr,f"环区 #0{i+1}")
grid=Image.new('RGB',(sz*5,sz*2))
for i in range(5):
    grid.paste(thumbs[i],(i*sz,0))
    grid.paste(crops[i],(i*sz,sz))
grid.save(os.path.join(ODIR,"审计-子代理.jpg"),quality=95)

# ring-edge zoom 3x: crop top part of ring (the outer edge above cover)
edge_crop=(RBOX[0]-40, RBOX[1]-20, RBOX[2]+40, RBOX[1]+220)  # top of ring
def zoom_crop(im, box, scale=3):
    c=im.crop(box)
    return c.resize((c.width*scale, c.height*scale), Image.Resampling.LANCZOS)
zooms=[zoom_crop(im, edge_crop) for im in ims]
zw=zooms[0].width; zh=zooms[0].height
panel=Image.new('RGB',(zw*5,zh+50),(255,255,255))
for i,z in enumerate(zooms):
    panel.paste(z,(i*zw,50))
d=ImageDraw.Draw(panel)
try:
    fnt=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",24)
except:
    fnt=ImageFont.load_default()
for i in range(5):
    d.text((i*zw+10,10),f"#0{i+1}",fill=(255,0,0),font=fnt)
d.text((10,zh+55),"环外沿 3x 特写",fill=(0,0,0),font=fnt)
panel.save(os.path.join(ODIR,"审计-环外沿.jpg"),quality=95)

# detailed diagnostics
H=W=1920
def lum(a): return 0.299*a[:,:,0]+0.587*a[:,:,1]+0.114*a[:,:,2]
out=[]
for f,im in zip(files,ims):
    arr=np.array(im.convert('RGB'))
    L=lum(arr)
    # ring mean and per-quartile
    x0,y0,x1,y1=RBOX
    R=L[y0:y1+1,x0:x1+1]
    rmean=float(R.mean()); rmed=float(np.median(R)); rp95=float(np.percentile(R,95)); rp5=float(np.percentile(R,5))
    # ear mean
    ex0,ey0,ex1,ey1=(793,232,1133,319)
    E=L[ey0:ey1+1,ex0:ex1+1]
    emean=float(E.mean()); ep95=float(np.percentile(E,95))
    # inner window
    win=L[873:1628+1,732:1185+1]
    wmean=float(win.mean()); wp5=float(np.percentile(win,5))
    out.append({"f":f,"rmean":rmean,"rmed":rmed,"rp95":rp95,"rp5":rp5,
                "emean":emean,"ep95":ep95,"wmean":wmean,"wp5":wp5})
    print(f"{f}: ring mean/med/p95/p5 = {rmean:.1f}/{rmed:.1f}/{rp95:.1f}/{rp5:.1f}; ear mean/p95={emean:.1f}/{ep95:.1f}; win mean/p5={wmean:.1f}/{wp5:.1f}")
json.dump(out,open(os.path.join(ODIR,"audit_diag.json"),"w"),default=str)
print("saved diagnostics and images.")
