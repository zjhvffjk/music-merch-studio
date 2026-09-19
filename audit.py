import os, json
from PIL import Image
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
def nbr(mask):
    m=mask.astype(np.int16)
    up=np.zeros_like(m);dn=up.copy();lf=up.copy();rt=up.copy()
    up[1:,:]=m[:-1,:];dn[:-1,:]=m[1:,:];lf[:,1:]=m[:,:-1];rt[:,:-1]=m[:,1:]
    return up+dn+lf+rt
def blob_sizes(mask):
    h,w=mask.shape;seen=np.zeros_like(mask);out=[]
    for y in range(h):
        for x in range(w):
            if mask[y,x] and not seen[y,x]:
                q=deque([(y,x)]);seen[y,x]=1;c=0
                while q:
                    cy,cx=q.popleft();c+=1
                    for dy,dx in((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=cy+dy,cx+dx
                        if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                            seen[ny,nx]=1;q.append((ny,nx))
                out.append(c)
    return out
# metal from overlay (alpha-confined)
ova=np.array(Image.open(os.path.join(BASE,"assets","keychain","keychain_overlay.png")).convert("RGBA"))
ov=ova[:,:,:3];A=ova[:,:,3]
ovL=lum(ov);mx=ov.max(2);mn=ov.min(2);sat=mx-mn
key=(A>0);metal=key&(ovL>180)&(sat<45);ym=np.arange(H)[:,None]
ear_m=metal&(ym<320)
ebbox=(int(np.where(ear_m.any(0))[0].min()),int(np.where(ear_m.any(1))[0].min()),
       int(np.where(ear_m.any(0))[0].max()),int(np.where(ear_m.any(1))[0].max()))
rb_m=metal&(ym>=280)&(ym<=720)
rbox=(int(np.where(rb_m.any(0))[0].min()),int(np.where(rb_m.any(1))[0].min()),
      int(np.where(rb_m.any(0))[0].max()),int(np.where(rb_m.any(1))[0].max()))
print("RING",rbox,"EAR",ebbox)
res=[]
for f in files:
    im=np.array(Image.open(os.path.join(KDIR,f)).convert("RGB"))
    L=lum(im).astype(np.float64)
    edges={s:white_edge(im,s) for s in['left','right','top','bottom']}
    x0,y0,x1,y1=rbox
    R=L[y0:y1+1,x0:x1+1]
    nw=(R>230);sizes=blob_sizes(nw)
    ring_big=max(sizes) if sizes else 0
    ring_small=sum(1 for s in sizes if s<=8)
    # outer fuzz: expand ring bbox by 25, exclude body, count isolated near-white
    ax0,ay0,ax1,ay1=x0-25,y0-25,x1+25,y1+25
    ax0,ay0,ax1,ay1=max(0,ax0),max(0,ay0),min(W-1,ax1),min(H-1,ay1)
    Z=L[ay0:ay1+1,ax0:ax1+1]
    znw=(Z>230)
    # carve out inner body region (relative coords)
    bx0,by0,bx1,by1=x0-ax0,y0-ay0,x1-ax0,y1-ay0
    znw[by0:by1+1,bx0:bx1+1]=False
    zsizes=blob_sizes(znw)
    fuzz=sum(1 for s in zsizes if s<=8)      # number of small white speck clusters outside ring
    fuzz_px=sum(s for s in zsizes if s<=8)   # total speck pixels
    # EAR highlight
    ex0,ey0,ex1,ey1=ebbox
    E=L[ey0:ey1+1,ex0:ex1+1]
    eb=(E>230);ear_frac=float(eb.mean());ear_min=float(E[eb].min()) if eb.any() else 0
    # INNER cavity
    px0,py0,px1,py1=732,873,1185,1628
    win=L[py0:py1+1,px0:px1+1]
    win_mean=float(win.mean());win_p5=float(np.percentile(win,5))
    bg=L.copy();bg[214:1706,214:1706]=np.nan
    bg_mean=float(np.nanmean(bg))
    res.append(dict(f=f,edges=edges,ring_big=ring_big,ring_small=ring_small,
        fuzz=fuzz,fuzz_px=fuzz_px,ear_frac=ear_frac,ear_min=ear_min,
        win_mean=win_mean,win_p5=win_p5,bg_mean=bg_mean))
    print(f"\n=== {f} ===")
    print(" edges L,R,T,B:",edges)
    print(f" ring maxblob:{ring_big} small_blobs(<=8):{ring_small}")
    print(f" OUTER FUZZ: speck_clusters(<=8):{fuzz} speck_px:{fuzz_px}")
    print(f" ear whitefrac:{ear_frac:.3f} ear_minL:{ear_min:.1f}")
    print(f" win_mean:{win_mean:.1f} win_p5:{win_p5:.1f} bg_mean:{bg_mean:.1f}")
json.dump(dict(rbox=rbox,ebbox=ebbox,res=res),open(os.path.join(ODIR,"audit_data.json"),"w"),default=str)
print("\nsaved.")
