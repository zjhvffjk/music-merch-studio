import os, json
from PIL import Image, ImageFilter
import numpy as np
from collections import deque
BASE=r"C:\Users\CH\WorkBuddy\迷你唱片机"
KDIR=os.path.join(BASE,"outputs","周杰伦-热门前5","keychain")
ODIR=os.path.join(BASE,"outputs","周杰伦-热门前5")
files=["01 晴天 - 周杰伦-钥匙扣.jpg","02 搁浅 - 周杰伦-钥匙扣.jpg",
       "03 红尘客栈 - 周杰伦-钥匙扣.jpg","04 夜曲 - 周杰伦-钥匙扣.jpg",
       "05 青花瓷 - 周杰伦-钥匙扣.jpg"]
H=W=1920
def lum(a): return 0.299*a[:,:,0]+0.587*a[:,:,1]+0.114*a[:,:,2]
def white_edge(arr,side,white=254):
    L=lum(arr)
    if side=='left':
        for x in range(W):
            if np.mean(L[:,x]>=white)>0.5: return x
    if side=='right':
        for x in range(W-1,-1,-1):
            if np.mean(L[:,x]>=white)>0.5: return x
    if side=='top':
        for y in range(H):
            if np.mean(L[y,:]>=white)>0.5: return y
    if side=='bottom':
        for y in range(H-1,-1,-1):
            if np.mean(L[y,:]>=white)>0.5: return y
    return -1

def dilate(mask, r=3):
    # repeated MaxFilter r times approximates radius ~r
    img=Image.fromarray((mask*255).astype(np.uint8))
    for _ in range(r):
        img=img.filter(ImageFilter.MaxFilter(3))
    return np.array(img)>127

def blob_stats(mask):
    h,w=mask.shape;seen=np.zeros_like(mask);out=[]
    for y in range(h):
        for x in range(w):
            if mask[y,x] and not seen[y,x]:
                q=deque([(y,x)]);seen[y,x]=1;c=0;xs=[];ys=[]
                while q:
                    cy,cx=q.popleft();c+=1;xs.append(cx);ys.append(cy)
                    for dy,dx in((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=cy+dy,cx+dx
                        if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                            seen[ny,nx]=1;q.append((ny,nx))
                out.append({'size':c,'cx':int(np.mean(xs)),'cy':int(np.mean(ys)),'maxx':int(max(xs)),'maxy':int(max(ys))})
    return out

ova=np.array(Image.open(os.path.join(BASE,"assets","keychain","keychain_overlay.png")).convert("RGBA"))
ov=ova[:,:,:3];A=ova[:,:,3]
ovL=lum(ov);ym=np.arange(H)[:,None]
ring_metal=(A==255)&(ovL>150)&(ym>=280)&(ym<=720)
ear_metal=(A==255)&(ovL>150)&(ym<320)
outer_band=dilate(ring_metal,4) & ~dilate(ring_metal,1)
print("outer_band count",int(outer_band.sum()))

res=[]
for f in files:
    im=np.array(Image.open(os.path.join(KDIR,f)).convert("RGB"))
    L=lum(im).astype(np.float64)
    edges={s:white_edge(im,s) for s in['left','right','top','bottom']}
    fuzz_mask=outer_band&(L>230)
    stats=blob_stats(fuzz_mask)
    small=[s for s in stats if s['size']<=4]
    eL=L[ear_metal]
    ear_med=float(np.median(eL));ear_p95=float(np.percentile(eL,95))
    win=L[873:1628+1,732:1185+1]
    win_mean=float(win.mean());win_p5=float(np.percentile(win,5))
    res.append({'f':f,'edges':edges,'fuzz_n':len(small),'fuzz_px':sum(s['size'] for s in small),
                'coords':[(s['cx'],s['cy']) for s in small[:20]],
                'ear_med':ear_med,'ear_p95':ear_p95,'win_mean':win_mean,'win_p5':win_p5})
    print(f"\n=== {f} ===")
    print(" edges:",edges)
    print(f" ring-edge fuzz clusters<=4:{len(small)} px:{sum(s['size'] for s in small)}")
    if small: print(" coords:",[(s['cx'],s['cy']) for s in small[:20]])
    print(f" ear metal med/p95:{ear_med:.1f}/{ear_p95:.1f}")
    print(f" win mean/p5:{win_mean:.1f}/{win_p5:.1f}")
json.dump(res,open(os.path.join(ODIR,"audit_report.json"),"w"),default=str)
print("saved audit_report.json")
