"""Encode an existing numbered PNG sequence at 24 fps, then verify full decode."""
import argparse,pathlib,subprocess,json
import imageio_ffmpeg
p=argparse.ArgumentParser();p.add_argument('--frames',required=True);p.add_argument('--output',required=True);p.add_argument('--start',type=int,default=1);p.add_argument('--count',type=int,required=True);p.add_argument('--crf',type=int,default=18);p.add_argument('--pattern',default='%04d.png');p.add_argument('--fps',type=float,default=24);p.add_argument('--overwrite',action='store_true');a=p.parse_args()
frames=pathlib.Path(a.frames);output=pathlib.Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
if output.exists() and not a.overwrite:raise FileExistsError('Choose a new version or explicitly --overwrite: '+str(output))
if a.count<1 or a.fps<=0:raise ValueError('count and fps must be positive')
missing=[f for f in range(a.start,a.start+a.count) if not (frames/(a.pattern%f)).exists()]
if missing:raise RuntimeError(f'Missing frames: {missing}')
cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-y','-framerate',str(a.fps),'-start_number',str(a.start),'-i',str(frames/a.pattern),'-frames:v',str(a.count),'-c:v','libx264','-preset','medium','-crf',str(a.crf),'-pix_fmt','yuv420p','-movflags','+faststart','-an',str(output)]
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace');(output.parent/(output.stem+'-encode.log')).write_text(r.stderr,encoding='utf-8');r.check_returncode()
verify=subprocess.run([cmd[0],'-v','error','-xerror','-i',str(output),'-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace');verify.check_returncode()
(output.parent/(output.stem+'-encoding.json')).write_text(json.dumps({'command':cmd,'fps':a.fps,'frames':a.count,'duration':a.count/a.fps,'audio':'silent','full_decode_exit':verify.returncode},indent=2),encoding='utf-8')
print(str(output))
