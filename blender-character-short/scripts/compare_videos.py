"""Create a labeled silent side-by-side review; freeze shorter input at its end."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg

def main():
    p=argparse.ArgumentParser();p.add_argument('--left',required=True);p.add_argument('--right',required=True);p.add_argument('--output',required=True);p.add_argument('--left-label',default='Earlier');p.add_argument('--right-label',default='Candidate');p.add_argument('--duration',type=float,required=True);p.add_argument('--fps',type=int,default=24);p.add_argument('--panel-width',type=int,default=480);p.add_argument('--panel-height',type=int,default=270);a=p.parse_args();left=Path(a.left).resolve();right=Path(a.right).resolve();out=Path(a.output).resolve()
    if not left.is_file() or not right.is_file():raise FileNotFoundError('Both review videos must exist')
    if out.exists():raise FileExistsError('Use a new review output version')
    w,h=a.panel_width,a.panel_height
    if w%2 or h%2 or a.duration<=0:raise ValueError('Even panel dimensions and positive duration required')
    out.parent.mkdir(parents=True,exist_ok=True);banner=Image.new('RGB',(w*2,36),(22,27,33));draw=ImageDraw.Draw(banner);font=ImageFont.load_default(size=18);draw.text((10,8),a.left_label,font=font,fill=(225,232,238));draw.text((w+10,8),a.right_label,font=font,fill=(225,232,238));label=out.with_suffix('.labels.png');banner.save(label)
    panel=lambda i: f'[{i}:v]fps={a.fps},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,tpad=stop_mode=clone:stop_duration={a.duration},setpts=PTS-STARTPTS[{"l" if i==0 else "r"}]'
    graph=panel(0)+';'+panel(1)+f';[l][r]hstack,pad={2*w}:{h+36}:0:36[v];[v][2:v]overlay=0:0[out]'
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-nostdin','-n','-i',str(left),'-i',str(right),'-loop','1','-i',str(label),'-filter_complex',graph,'-map','[out]','-an','-t',str(a.duration),'-r',str(a.fps),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
    with out.with_suffix('.encode.log').open('w',encoding='utf-8') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    check=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-nostdin','-v','error','-xerror','-i',str(out),'-f','null','-']
    with out.with_suffix('.decode.log').open('w',encoding='utf-8') as log:subprocess.run(check,stdout=log,stderr=subprocess.STDOUT,check=True)
    report={'left':str(left),'right':str(right),'duration':a.duration,'fps':a.fps,'output':str(out),'shorter_input':'Last frame held until requested review duration','audio':'omitted for visual review','warning':'Side-by-side comparison does not establish matched camera/pose or pixel parity','command':cmd,'full_decode_exit_code':0};out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('COMPARISON_CREATED',out)

if __name__=='__main__':main()
