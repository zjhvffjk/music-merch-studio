import os, numpy as np
from PIL import Image
B=r"C:\Users\CH\WorkBuddy\迷你唱片机"
K=os.path.join(B,"outputs","周杰伦-热门前5","keychain")
files=["01 晴天 - 周杰伦-钥匙扣.jpg","02 搁浅 - 周杰伦-钥匙扣.jpg",
       "03 红尘客栈 - 周杰伦-钥匙扣.jpg","04 夜曲 - 周杰伦-钥匙扣.jpg",
       "05 青花瓷 - 周杰伦-钥匙扣.jpg"]
def lum(a):return 0.299*a[:,:,0]+0.587*a[:,:,1]+0.114*a[:,:,2]
def inner_edge(arr,side,white=254):
    L=lum(arr);h,w=L.shape
    if side=='left':
        for x in range(214,0,-1):
            if np.mean(L[:,x]>=white)>0.5: return x
    if side=='right':
        for x in range(1705,w):
            if np.mean(L[:,x]>=white)>0.5: return x
    if side=='top':
        for y in range(214,0,-1):
            if np.mean(L[y,:]>=white)>0.5: return y
    if side=='bottom':
        for y in range(1705,h):
            if np.mean(L[y,:]>=white)>0.5: return y
    return -1
print("filename left right top bottom")
for f in files:
    im=np.array(Image.open(os.path.join(K,f)).convert("RGB"))
    e={s:inner_edge(im,s) for s in ['left','right','top','bottom']}
    print(f"{f}: {e['left']} {e['right']} {e['top']} {e['bottom']}")
