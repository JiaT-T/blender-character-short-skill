"""Source-derived weighted Bloom / curve / LUT. Arrays use bottom-up image rows.

No renderer equivalence is implied: input coverage/AOV must be validated separately.
SMAA is deliberately absent and is an explicit strict-render acceptance gap.
"""
from pathlib import Path
import argparse,json
import numpy as np

def encode(x):
    return np.float32(1.055)*np.maximum(x,0)**np.float32(1/2.4)-np.float32(.055)

def sample(a,u,v):
    """WebGL LINEAR CLAMP_TO_EDGE at normalized texel centers; bottom-up rows."""
    h,w=a.shape[:2];x=np.clip(u*w-.5,0,w-1);y=np.clip(v*h-.5,0,h-1)
    x0=np.floor(x).astype(np.int32);y0=np.floor(y).astype(np.int32)
    x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
    fx=(x-x0)[...,None];fy=(y-y0)[...,None]
    return ((a[y0,x0]*(1-fx)+a[y0,x1]*fx)*(1-fy)+(a[y1,x0]*(1-fx)+a[y1,x1]*fx)*fy).astype(np.float32)

def grid(w,h):
    return np.meshgrid((np.arange(w,dtype=np.float32)+.5)/w,(np.arange(h,dtype=np.float32)+.5)/h)

def resize(a,w,h):
    return sample(a,*grid(w,h))

def box(a,w,h,texel_size):
    u,v=grid(w,h);tx,ty=texel_size
    return sum(sample(a,u+sx*tx,v+sy*ty) for sx,sy in [(1,1),(1,-1),(-1,-1),(-1,1)])*.25

def quantize(a,mode):
    if mode=='float16':return a.astype(np.float16).astype(np.float32)
    if mode=='unorm8':return (np.rint(np.clip(a,0,1)*255)/255).astype(np.float32)
    if mode=='float32':return np.asarray(a,dtype=np.float32)
    raise ValueError('Unsupported render-target precision: '+mode)

def scene_target(a,mode):
    if mode!='unorm8':return quantize(a,mode)
    # Non-HDR S_ uses SRGB8_ALPHA8; shader sampling decodes RGB, never alpha.
    rgb=np.maximum(a[...,:3],0)
    encoded=np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)
    encoded=quantize(encoded,'unorm8')
    decoded=np.where(encoded<=.04045,encoded/12.92,((encoded+.055)/1.055)**2.4)
    return np.concatenate([decoded,quantize(a[...,3:4],'unorm8')],axis=2).astype(np.float32)

def blur(a,taps,axis,qmode):
    h,w=a.shape[:2];u,v=grid(w,h);out=np.zeros_like(a,dtype=np.float32)
    for tap in taps:
        d=tap['offset_normalized_uv'];out+=sample(a,u+(d if axis==0 else 0),v+(d if axis==1 else 0))*tap['weight']
    return quantize(out,qmode)

def lut_trilinear(c,lut):
    """LUT image is TOP-down data, N horizontal blue slices, no sRGB decode."""
    n=lut.shape[0]
    if lut.shape[1]!=n*n:raise ValueError('LUT must have width=height^2')
    q=np.clip(c,0,1)*(n-1);lo=np.floor(q).astype(np.int32);hi=np.minimum(lo+1,n-1);f=q-lo
    out=np.zeros_like(c,dtype=np.float32)
    for z in (0,1):
        for y in (0,1):
            for x in (0,1):
                ix=hi[...,0] if x else lo[...,0];iy=hi[...,1] if y else lo[...,1];iz=hi[...,2] if z else lo[...,2]
                weight=(f[...,0] if x else 1-f[...,0])*(f[...,1] if y else 1-f[...,1])*(f[...,2] if z else 1-f[...,2])
                out+=lut[iy,iz*n+ix,:3]*weight[...,None]
    return out

def process(scene,weight,lut,cfg):
    if scene.ndim!=3 or scene.shape[2]!=4:raise ValueError('scene must be HxWx4 premultiplied linear RGBA')
    if weight.ndim==2:weight=weight[...,None]
    if scene.shape[:2]!=weight.shape[:2]:raise ValueError('Bloom weight dimensions differ from color')
    if not np.all(np.isfinite(scene)) or not np.all(np.isfinite(weight)):raise ValueError('Non-finite render input')
    h,w=scene.shape[:2];qmode=cfg['target_precision'];stages={}
    scene=scene_target(scene,qmode);weight=quantize(weight,qmode)
    halfw=max(1,w//2);halfh=max(1,h//2)
    bc=box(scene[...,:3],halfw,halfh,[1/w,1/h]);bw=box(weight,halfw,halfh,[1/w,1/h])
    threshold,scale=cfg['threshold'];pre=np.maximum((np.maximum(encode(bc),0)-threshold)*scale,0)*np.maximum(bw,0)
    stages['prefilter']=quantize(pre,qmode)
    # Source b_ repeatedly reduces oversized prefilter targets before fixed levels.
    reduced=stages['prefilter'];rw,rh=halfw,halfh;reduction=0
    while max(rw,rh)>1024:
        nw,nh=max(1,rw//2),max(1,rh//2)
        reduced=quantize(box(reduced,nw,nh,[1/rw,1/rh]),qmode)
        rw,rh=nw,nh;stages[f'pre_reduce_{reduction}']=reduced;reduction+=1
    sizes=cfg['level_sizes'];cur=quantize(box(reduced,sizes[0],sizes[0],[1/rw,1/rh]),qmode)
    levels=[]
    for i,(size,kernel) in enumerate(zip(sizes,cfg['level_kernels'])):
        if i:cur=quantize(resize(cur,size,size),qmode)
        stages[f'level{i}_input']=cur
        cur=blur(cur,cfg['kernels'][kernel],0,qmode);stages[f'level{i}_horizontal']=cur
        cur=blur(cur,cfg['kernels'][kernel],1,qmode);stages[f'level{i}']=cur;levels.append(cur)
    bloom=quantize(sum(resize(level,sizes[0],sizes[0])*coeff for level,coeff in zip(levels,cfg['coefficients'])),qmode)
    stages['bloom']=bloom;bloom_full=resize(bloom,w,h)
    coverage=np.clip(scene[...,3:4],0,1);base=scene[...,:3]/np.maximum(coverage,np.float32(1e-4))
    x=cfg['blend'][0]*encode(base)+cfg['blend'][1]*bloom_full
    curved=np.clip(1-np.exp2(-cfg['curve'][0]*x),0,1)**(cfg['curve'][1]+.01)
    screen=lut_trilinear(curved,lut) if cfg.get('use_lut',True) else curved
    screen=np.where(coverage>0,screen,0);stages['curve']=curved;stages['lut_straight']=screen
    # The web target stores encoded premultiplied color; PNG stores straight color.
    web=quantize(np.concatenate([screen*coverage,coverage],axis=2),cfg.get('composite_precision','unorm8'))
    png_rgb=web[...,:3]/np.maximum(web[...,3:4],np.float32(1e-4));png_rgb=np.where(web[...,3:4]>0,png_rgb,0)
    stages['web_premultiplied']=web;stages['display_rgba']=np.concatenate([np.clip(png_rgb,0,1),web[...,3:4]],axis=2)
    return stages

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--config',required=True);p.add_argument('--lut',required=True);p.add_argument('--output',required=True);p.add_argument('--stages');a=p.parse_args()
    from PIL import Image
    cfg=json.loads(Path(a.config).read_text('utf-8'));data=np.load(a.input);lut=np.asarray(Image.open(a.lut).convert('RGB'),dtype=np.float32)/255
    stages=process(data['rgba'],data['weight'],lut,cfg);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(np.uint8(np.rint(stages['display_rgba'][::-1]*255)),'RGBA').save(out)
    if a.stages:
        d=Path(a.stages);d.mkdir(parents=True,exist_ok=True)
        for name,arr in stages.items():
            np.save(d/(name+'.npy'),arr)
            view=np.clip(arr,0,1);channels=view.shape[2];Image.fromarray(np.uint8(np.rint(view[::-1]*255)),'RGBA' if channels==4 else 'RGB').save(d/(name+'.png'))
        (d/'scope.json').write_text(json.dumps({'input':a.input,'config':a.config,'lut':a.lut,'stages':list(stages),'aa':'SMAA not implemented','stage_pngs':'diagnostic clipping of raw arrays; numerical evidence is NPY'},indent=2),encoding='utf-8')
    print('POST_DONE',out)

if __name__=='__main__':main()
