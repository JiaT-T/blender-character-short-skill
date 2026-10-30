"""Attach inspected rest-joint landmarks to an external character configuration."""
import argparse,copy,hashlib,json,math
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--inspection',required=True);p.add_argument('--character',required=True);p.add_argument('--output',required=True);a=p.parse_args();inspection=Path(a.inspection);cfg=copy.deepcopy(json.loads(Path(a.character).read_text('utf-8')));data=json.loads(inspection.read_text('utf-8'))
    if len(data['armatures'])!=1:raise ValueError('Calibration requires exactly one inspected armature')
    by_name={b['name']:b for b in data['armatures'][0]['bones']};h=float(cfg['height']);ground=float(cfg['ground'])
    if h<=0 or abs(h-data['height'])>h*.01:raise ValueError('Configured height differs by more than 1% from imported mesh; resolve scale before choreography')
    rest={}
    for semantic,name in cfg['bones'].items():
        if name not in by_name:raise ValueError('Mapped bone absent in imported skeleton: '+semantic+' / '+name)
        x,y,z=by_name[name]['head_world'];rest[semantic]=[x/h,y/h,(z-ground)/h]
    arms={}
    for side in ('left','right'):
        keys=[side+'_arm',side+'_elbow',side+'_wrist'];points=[rest[k] for k in keys];arms[side]=[math.dist(points[0],points[1]),math.dist(points[1],points[2])]
    cfg['landmarks']={'inspection_sha256':hashlib.sha256(inspection.read_bytes()).hexdigest(),'coordinate_system':'World x/height, y/height, (z-ground)/height; rest bone heads','rest_joints':rest,'arm_segments_height':arms,'caution':'Head joint is not the eye center. Shoulder uses upper-arm joint head. Inspect visible silhouette and costume clearance separately.'}
    out=Path(a.output)
    if out.exists():raise FileExistsError('Preserve the previous configuration; choose a new output file')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output':str(out),'shoulder_height':{s:rest[s+'_arm'][2] for s in ('left','right')},'arm_segments_height':arms},ensure_ascii=False))

if __name__=='__main__':main()
