"""Encode only complete, reviewed-identity native frames at their actual fps."""
from pathlib import Path
import argparse,json,subprocess,math,re,os
import imageio_ffmpeg
from production_contract import sha,validate_frames,write_json,require_saved_producer
def encode(root,output):
    root=Path(root).resolve();output=Path(output).resolve();state=json.loads((root/'progress.json').read_text('utf-8'));sig=state['signature'];first,last=sig['range'];rows=validate_frames(root,sig,first,last)
    if not state['complete'] or not state['inputs_verified'] or len(rows)!=last-first+1:raise ValueError('Complete identity-verified frame sequence required')
    for row in [sig['source'],*sig['dependencies']]:
        if sha(row['path'])!=row['sha256']:raise ValueError('Source input changed since rendering')
    scripts=Path(__file__).parent
    require_saved_producer(sig,scripts)
    if output.exists():raise FileExistsError('Choose a new encoded output')
    fps=sig['effective_fps'];ff=imageio_ffmpeg.get_ffmpeg_exe();output.parent.mkdir(parents=True,exist_ok=True)
    command=[ff,'-hide_banner','-nostdin','-framerate',str(fps),'-start_number',str(first),'-i',str(root/'%04d.png'),'-frames:v',str(len(rows)),'-an','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-threads','2','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-map_metadata','-1','-movflags','+faststart',str(output)]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags);output.with_suffix('.encode.log').write_text(proc.stderr,'utf-8');proc.check_returncode()
    decode=subprocess.run([ff,'-hide_banner','-nostdin','-xerror','-i',str(output),'-map','0:v:0','-an','-f','framemd5','-'],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags);output.with_suffix('.decode.log').write_text(decode.stderr,'utf-8');decode.check_returncode();decoded=[r for r in decode.stdout.splitlines() if r and not r.startswith('#')]
    count,seconds=imageio_ffmpeg.count_frames_and_secs(str(output));stream=imageio_ffmpeg.read_frames(str(output));meta=next(stream);stream.close()
    if count!=len(rows) or len(decoded)!=len(rows) or tuple(meta['size'])!=(sig['width'],sig['height']) or not math.isclose(meta['fps'],fps,abs_tol=.005) or abs(seconds-len(rows)/fps)>.06:raise ValueError('Decoded movie specifications differ')
    result={'accepted':True,'movie':str(output),'sha256':sha(output),'size':list(meta['size']),'fps':meta['fps'],'saved_fps_numerator':sig['fps_numerator'],'saved_fps_base':sig['fps_base'],'frames':count,'duration':seconds,'full_decode_exit':decode.returncode,'framemd5_rows':len(decoded),'frame_signature':state['signature_sha256'],'normal_speed_visual_acceptance':False,'audio':'silent','post_mode':sig['post_mode']};write_json(output.with_suffix('.verification.json'),result);return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frames',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(encode(a.frames,a.output),indent=2))
if __name__=='__main__':main()
