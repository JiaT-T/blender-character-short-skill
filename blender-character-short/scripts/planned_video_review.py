"""Read-only, plan-aware image-change cues. Every finding needs human review."""
import argparse
import hashlib
import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path
import numpy as np
from shot_plan import validate

DEFAULTS = {"jump":0.20, "flash":0.28, "return_similarity":0.04, "freeze":0.001, "freeze_frames":12, "cut_tolerance":2}


def review_frames(frames, plan, settings=None):
    contract=validate(plan)
    cfg=dict(DEFAULTS);cfg.update(settings or {})
    if set(cfg) != set(DEFAULTS):raise ValueError("Unknown review threshold")
    for key in ("jump","flash","return_similarity","freeze"):
        if isinstance(cfg[key],bool) or not isinstance(cfg[key],(int,float)) or not math.isfinite(cfg[key]) or not 0<=cfg[key]<=1:raise ValueError("Threshold must be finite 0..1")
    for key in ("freeze_frames","cut_tolerance"):
        if type(cfg[key]) is not int or not (2 if key=="freeze_frames" else 0)<=cfg[key]<=1000:raise ValueError("Invalid frame threshold")
    flags=[];suppressed=[];truncated=False
    cuts=contract["expected_cut_frames"];seen_cuts={};near=cfg["cut_tolerance"]
    exemptions=plan.get("review_exemptions",[])
    def emit(kind,first,last=None,**extra):
        nonlocal suppressed,truncated
        last=first if last is None else last
        if any(r["kind"]==kind and r["start"]<=first and last<=r["end"] for r in exemptions):
            if len(suppressed)<2000:suppressed.append({"kind":kind,"start":first,"end":last,"reason":[r["reason"] for r in exemptions if r["kind"]==kind and r["start"]<=first and last<=r["end"]]})
            else:truncated=True
            return
        item={"kind":kind,"start":first,"end":last,"seconds":(first-plan["start"])/contract["effective_fps"],"needs_human_review":True,**extra}
        if len(flags)<2000:flags.append(item)
        else:truncated=True
    prev=prev2=None;prior_delta=0.;freeze_start=None;count=0;last_index=None
    for data in frames:
        count+=1
        if count>100000:raise ValueError("Review bound exceeded (100000 frames)")
        frame=np.asarray(data,dtype=np.float32)
        if frame.ndim!=2 or frame.size>320*180 or not np.isfinite(frame).all() or frame.min()<0 or frame.max()>1:raise ValueError("Expected normalized small grayscale frame")
        if prev is not None and frame.shape!=prev.shape:raise ValueError("Frame dimensions changed")
        index=plan["start"]+count-1;last_index=index
        if prev is not None:
            delta=float(np.abs(frame-prev).mean())
            matched=[c for c in cuts if abs(c-index)<=near]
            if delta>=cfg["jump"]:
                for cut in matched:
                    previous=seen_cuts.get(cut)
                    if previous is None or abs(index-cut)<abs(previous-cut):seen_cuts[cut]=index
                if not matched:emit("jump",index,score=delta)
            if prev2 is not None and prior_delta>=cfg["flash"] and delta>=cfg["flash"] and float(np.abs(frame-prev2).mean())<=cfg["return_similarity"]:
                if not any(abs(c-index)<=near or abs(c-(index-1))<=near for c in cuts):emit("flash",index-1,score=min(prior_delta,delta))
            if delta<=cfg["freeze"]:
                if freeze_start is None:freeze_start=index-1
            else:
                if freeze_start is not None and index-freeze_start>=cfg["freeze_frames"]:emit("freeze",freeze_start,index-1)
                freeze_start=None
            prior_delta=delta
        prev2,prev=prev,frame.copy()
    if freeze_start is not None and last_index-freeze_start+1>=cfg["freeze_frames"]:emit("freeze",freeze_start,last_index)
    for cut in cuts:
        if cut in seen_cuts and seen_cuts[cut]!=cut:emit("cut",cut,observed=seen_cuts[cut],offset_frames=seen_cuts[cut]-cut,detail="Nearby image-change candidate differs from planned cut")
        if cut not in seen_cuts:emit("cut",cut,detail="No strong image change near planned cut; similar views may be intentional")
    if count!=contract["frame_count"]:emit("frame_count",plan["start"],actual=count,expected=contract["frame_count"])
    return {"schema":1,"purpose":"Human-review cues, not quality acceptance", "visual_acceptance":False,"decoded_frames":count,"plan_contract":contract,"thresholds":cfg,"findings":flags,"suppressed_findings":suppressed,"findings_truncated":truncated,"limits":["Downsampled luminance cannot judge acting, contact, fine-line flicker or continuity", "CFR frame mapping assumed; use existing timestamp/decode QA for VFR", "Similar camera cuts can be missed; movement, flashes and holds can be intentional"]}


def review_video(video,plan,settings=None):
    import imageio_ffmpeg
    video=Path(video)
    with video.open("rb") as f:before=hashlib.file_digest(f,"sha256").hexdigest()
    stream=imageio_ffmpeg.read_frames(str(video),pix_fmt="gray",bits_per_pixel=8,output_params=["-vf","scale=160:90","-fps_mode","passthrough","-threads","1"])
    try:
        meta=next(stream)
        def frames():
            for data in stream:
                if len(data)!=160*90:raise ValueError("Unexpected decoded frame size")
                yield np.frombuffer(data,dtype=np.uint8).reshape(90,160).astype(np.float32)/255.
        result=review_frames(frames(),plan,settings)
    finally:stream.close()
    with video.open("rb") as f:after=hashlib.file_digest(f,"sha256").hexdigest()
    if before!=after:raise ValueError("Video changed while reviewing")
    result.update(video_sha256=before,plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),decoder_metadata=meta)
    from video_qa import parse_showinfo
    command=[imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-nostdin","-i",str(video),"-map","0:v:0","-vf","showinfo","-frames:v","1","-an","-threads","1","-f","null","-"]
    probe=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=20,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    _,rate=parse_showinfo(probe.stderr)
    expected=Fraction(plan["fps"])/Fraction(str(plan.get("fps_base",1)))
    result["reported_fps_rational"]=str(rate) if rate else None
    result["expected_fps_rational"]=str(expected)
    result["reported_fps_matches"]=probe.returncode==0 and rate==expected
    if not result["reported_fps_matches"]:result["findings"].append({"kind":"fps","needs_human_review":True,"detail":"Declared rational rate differs or could not be read; frame-to-time mapping is provisional"})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",type=Path,required=True);p.add_argument("--plan",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--settings",type=Path)
    a=p.parse_args()
    result=review_video(a.video,json.loads(a.plan.read_text("utf-8")),json.loads(a.settings.read_text("utf-8")) if a.settings else None)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open("x",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)

if __name__ == "__main__":main()
