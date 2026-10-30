"""Small known-input checks for source_post, including observed branch regressions."""
import argparse,json,math,platform
from pathlib import Path
import numpy as np
import source_post as post

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--report',required=True);a=p.parse_args();cfg=json.loads(Path(a.config).read_text('utf-8'));cfg['use_lut']=False
    n=4;lut=np.zeros((n,n*n,3),np.float32)
    for y in range(n):
        for z in range(n):
            for x in range(n):lut[y,z*n+x]=[x/(n-1),y/(n-1),z/(n-1)]
    rng=np.random.default_rng(381);samples=rng.random((9,7,3),dtype=np.float32);identity_error=float(np.max(np.abs(post.lut_trilinear(samples,lut)-samples)));assert identity_error<3e-7
    rgba=np.ones((48,64,4),np.float32);rgba[...,:3]=[.02,.4,2];weight=np.full((48,64,1),.2,np.float32);stages=post.process(rgba,weight,lut,cfg)
    q=lambda x:float(np.float16(x));expected=[q(max((max(1.055*max(q(v),0)**(1/2.4)-.055,0)-cfg['threshold'][0])*cfg['threshold'][1],0)*q(.2)) for v in [.02,.4,2]];error=float(np.max(np.abs(stages['prefilter']-expected)));assert error<3e-7
    uniform=max(float(np.max(np.ptp(v,axis=(0,1)))) for v in stages.values());assert uniform<1e-6
    zero=post.process(rgba,np.zeros_like(weight),lut,cfg);assert np.max(zero['bloom'])==0
    empty=post.process(np.zeros_like(rgba),weight,lut,cfg);assert np.max(empty['display_rgba'])==0
    lo=cfg.copy();lo['target_precision']='unorm8';low=np.ones((4,4,4),np.float32);low[...,:3]=.0099;s=post.process(low,np.zeros((4,4,1),np.float32),lut,lo);low_code=int(np.rint(s['display_rgba'][0,0,0]*255));assert low_code==14,(low_code,'source sRGB8-alpha8 expected code 14')
    large=np.ones((4,2050,4),np.float32);big=post.process(large,np.zeros((4,2050,1),np.float32),lut,cfg);assert 'pre_reduce_0' in big
    invalid=rgba.copy();invalid[0,0,0]=np.nan;invalid_rejected=False
    try:post.process(invalid,weight,lut,cfg)
    except ValueError as exc:invalid_rejected='Non-finite' in str(exc)
    assert invalid_rejected
    report={'passed':True,'python':platform.python_version(),'numpy':np.__version__,'identity_lut_max_error':identity_error,'constant_prefilter_max_error':error,'constant_field_spatial_variation':uniform,'zero_weight_zero_bloom':True,'zero_alpha_zero_output':True,'non_hdr_dark_patch_code':low_code,'oversized_prefilter_reduction_executed':True,'nonfinite_input_rejected':True,'scope':'Known-input algebra and branch checks. Does not prove matching GPU rasterization, coverage, runtime uniforms or SMAA.'}
    path=Path(a.report);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
