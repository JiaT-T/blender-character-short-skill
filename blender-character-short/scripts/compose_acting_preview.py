"""Cut matched verified CPU preview frames, keeping source time and one CPU thread."""
from pathlib import Path
import argparse,datetime,hashlib,json,math,shutil,subprocess
import imageio_ffmpeg

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['plan','output','report']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();base=a.plan.resolve().parent;load=lambda p:json.loads(p.read_text('utf-8'));plan=load(a.plan);frames=plan.get('frames');fps=plan.get('fps');sources=plan.get('sources');shots=plan.get('shots')
    if plan.get('schema')!=1 or not isinstance(frames,list) or len(frames)!=2 or any(type(x) is not int for x in frames) or not 1<=frames[0]<frames[1] or frames[1]-frames[0]+1>480 or type(fps) not in (int,float) or not math.isfinite(fps) or not 1<=fps<=60:raise ValueError('Bounded schema1 timeline/fps required')
    if not isinstance(sources,dict) or not 1<=len(sources)<=8 or not isinstance(shots,list) or not 1<=len(shots)<=32:raise ValueError('Bounded sources/shots required')
    output=a.output.resolve();report=a.report.resolve();stage=output.parent/(output.stem+'-frames')
    if output.suffix.lower()!='.mp4' or report.suffix.lower()!='.json' or any(p.exists() for p in [output,report,stage]) or len({output,report,a.plan.resolve()})!=3:raise ValueError('Choose distinct new output/report/frame paths')
    loaded={};scene_identity=None;style_identity=None;size=None;producer=None;evidence=[]
    for name,src in sources.items():
        rp=(base/src['frames_report']).resolve();profile=(base/src['profile']).resolve();r=load(rp);cfg=load(profile);signature=r['signature'];style={k:cfg.get(k) for k in ['size','samples','brightness','background','materials','owned_material_prefixes']};style_hash=hashlib.sha256(json.dumps(style,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if not r['complete'] or signature['profile_sha256']!=sha(profile) or abs(r['fps']-fps)>1e-7:raise ValueError('Stale/incomplete source or mismatched fps')
        if scene_identity is None:scene_identity=signature['scene_sha256'];style_identity=style_hash;size=r['size'];producer=signature['writer_sha256']
        if (signature['scene_sha256'],style_hash,r['size'],signature['writer_sha256'])!=(scene_identity,style_identity,size,producer):raise ValueError('Cuts must share saved scene, preview style, dimensions and producer')
        records={}
        for row in r['frames']:
            key=(row['frame'],row['view'])
            if key in records:raise ValueError('Duplicate source frame/view')
            file=(rp.parent/row['file']).resolve()
            if not file.is_relative_to(rp.parent) or not file.is_file() or file.suffix.lower()!='.png':raise ValueError('Source frame must be a local PNG under its report directory')
            records[key]=(file,row['sha256'])
        loaded[name]=records;evidence.append({'id':name,'frames_report':str(rp),'frames_report_sha256':sha(rp),'profile_sha256':sha(profile),'signature':signature})
    selected=[];next_frame=frames[0]
    for shot in shots:
        first,last=shot.get('first'),shot.get('last');source=shot.get('source');view=shot.get('view')
        if any(type(x) is not int for x in [first,last]) or first!=next_frame or not first<=last<=frames[1] or source not in loaded or not isinstance(view,str):raise ValueError('Shots must cover the complete timeline once, in order')
        for f in range(first,last+1):
            if (f,view) not in loaded[source]:raise ValueError('Missing shot frame/view')
            file,digest=loaded[source][(f,view)]
            if sha(file)!=digest:raise ValueError('Source frame hash mismatch')
            selected.append({'frame':f,'source':source,'view':view,'path':str(file),'sha256':digest})
        next_frame=last+1
    if next_frame!=frames[1]+1:raise ValueError('Shot timeline has an uncovered tail')
    stage.mkdir(parents=True)
    for i,row in enumerate(selected,1):
        destination=stage/(str(i).zfill(4)+'.png');shutil.copyfile(row['path'],destination)
        if sha(destination)!=row['sha256']:raise ValueError('Copied edit frame hash mismatch')
    ff=imageio_ffmpeg.get_ffmpeg_exe();flags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0);cmd=[ff,'-hide_banner','-nostdin','-n','-threads','1','-filter_threads','1','-framerate',str(fps),'-start_number','1','-i',str(stage/'%04d.png'),'-frames:v',str(len(selected)),'-c:v','libx264','-threads','1','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(output)];r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags);output.with_name(output.stem+'-encode.log').write_text(r.stderr,'utf-8');r.check_returncode();decode=[ff,'-hide_banner','-nostdin','-v','error','-xerror','-threads','1','-i',str(output),'-f','null','-'];r=subprocess.run(decode,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags);output.with_name(output.stem+'-decode.log').write_text(r.stderr,'utf-8');r.check_returncode();report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scene_sha256':scene_identity,'style_sha256':style_identity,'plan_sha256':sha(a.plan),'writer_sha256':sha(Path(__file__)),'video_sha256':sha(output),'frames':len(selected),'fps':fps,'duration_seconds':len(selected)/fps,'size':size,'shots':shots,'sources':evidence,'selected_frames':selected,'command':cmd,'full_decode_command':decode,'full_decode_exit':r.returncode,'normal_speed_continuous_viewing':False,'audio':'silent','scope':'Same saved motion and exact scene frame times; shot selection only. Keep the uninterrupted wide version for body continuity review.'},ensure_ascii=False,indent=2),'utf-8');print(json.dumps({'video':str(output),'sha256':sha(output),'frames':len(selected),'shots':len(shots)}))

if __name__=='__main__':main()
