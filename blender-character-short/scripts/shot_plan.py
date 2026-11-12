"""Original shot-table contract. Checks declarations, not rendered continuity."""
import argparse
import json
import math
from pathlib import Path


def validate(plan):
    if not isinstance(plan, dict) or type(plan.get("schema")) is not int or plan["schema"] != 1:
        raise ValueError("Shot plan schema 1 required")
    fps, base = plan.get("fps"), plan.get("fps_base", 1.0)
    if type(fps) is not int or not 1 <= fps <= 240 or isinstance(base, bool) or not isinstance(base, (int, float)) or not math.isfinite(base) or base <= 0:
        raise ValueError("Positive fps/fps_base required")
    if not math.isfinite(fps/base) or not 0.001 <= fps/base <= 1000:
        raise ValueError("Effective fps must be finite and within 0.001..1000")
    assets = plan.get("assets", {})
    if not isinstance(assets, dict) or any(not isinstance(k,str) or not k.strip() or not isinstance(v,str) or not v.strip() for k,v in assets.items()):
        raise ValueError("assets must map stable IDs to descriptions or paths")
    start, end = plan.get("start"), plan.get("end")
    if type(start) is not int or type(end) is not int or end < start or end-start+1 > 100000:
        raise ValueError("Inclusive integer range of at most 100000 frames required")
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots or len(shots) > 1000:
        raise ValueError("1..1000 shots required")
    ids, previous, cursor, warnings, cuts = set(), None, start, [], []
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError("Shot must be an object")
        for key in ("id", "beat", "camera", "framing", "action_start", "action_end"):
            if not isinstance(shot.get(key), str) or not shot[key].strip():
                raise ValueError("Shot requires nonempty " + key)
        if shot["id"] in ids:
            raise ValueError("Duplicate shot id")
        ids.add(shot["id"])
        refs = shot.get("asset_ids", [])
        if not isinstance(refs,list) or any(not isinstance(x,str) or x not in assets for x in refs) or len(set(refs))!=len(refs):
            raise ValueError("asset_ids must be unique known asset references")
        if type(shot.get("start")) is not int or type(shot.get("end")) is not int or shot["start"] != cursor or shot["end"] < cursor:
            raise ValueError("Shots must cover the range in order without gaps or overlaps")
        cursor = shot["end"] + 1
        for key in ("spatial_start", "spatial_end", "props_start", "props_end"):
            state = shot.get(key)
            if not isinstance(state, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip() for k,v in state.items()):
                raise ValueError("State fields require string-to-string objects: " + key)
        transition = shot.get("transition", "cut")
        if transition not in ("cut", "dissolve", "fade", "continuous"):
            raise ValueError("Unknown incoming transition")
        exceptions = shot.get("continuity_exceptions", [])
        if not isinstance(exceptions, list) or any(not isinstance(e, dict) or e.get("field") not in ("action", "spatial", "props") or not isinstance(e.get("reason"), str) or not e["reason"].strip() for e in exceptions):
            raise ValueError("Continuity exceptions require field and reason")
        exempt = {e["field"] for e in exceptions}
        if previous:
            if transition == "cut": cuts.append(shot["start"])
            for field in ("action", "spatial", "props"):
                if previous[field+"_end"] != shot[field+"_start"] and field not in exempt:
                    warnings.append({"kind":"declared_continuity_change", "shot":shot["id"], "frame":shot["start"], "field":field})
        previous = shot
    if cursor != end+1:
        raise ValueError("Shot coverage must equal plan range")
    if not isinstance(plan.get("review_exemptions", []), list):
        raise ValueError("review_exemptions must be a list")
    for row in plan.get("review_exemptions", []):
        if not isinstance(row, dict) or row.get("kind") not in ("flash", "jump", "freeze", "cut") or type(row.get("start")) is not int or type(row.get("end")) is not int or not start <= row["start"] <= row["end"] <= end or not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("Review exemptions require kind, in-range frames and reason")
    return {"valid_contract":True, "effective_fps":fps/base, "frame_count":end-start+1, "expected_cut_frames":cuts, "warnings":warnings, "visual_acceptance":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a=p.parse_args()
    report=validate(json.loads(a.plan.read_text("utf-8")))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open("x",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2)

if __name__ == "__main__":main()
