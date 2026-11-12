"""Evaluate a production brief; no downloads, rendering, or semantic invention."""
import argparse
import json
from pathlib import Path
from production_defaults import new_video_settings

STAGES = ("intake", "intent", "look_and_motion", "storyboard", "production", "delivery")
OPTIONAL = ("actions", "cameras", "props", "music", "mood", "lighting", "duration", "aspect", "pace", "references")

def evaluate(brief, base):
    if brief.get("schema") != 1:
        raise ValueError("Workflow brief schema 1 required")
    base = Path(base)
    missing, notes, fallbacks = [], [], []
    exceptions = brief.get("user_exceptions", {})
    assets = brief.get("inputs", {})
    for key in ("character_mmd", "scene"):
        exception = exceptions.get(key)
        if exception is not None:
            if not isinstance(exception, str) or not exception.strip():
                raise ValueError("Exceptions require the user's explicit request text")
            notes.append({"exception": key, "request": exception})
            continue
        value = assets.get(key)
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
            continue
        path = (base / value).resolve()
        if not path.is_file():
            missing.append(key + ":file_not_found")
        if key == "character_mmd" and path.suffix.lower() not in (".pmx", ".pmd", ".blend"):
            missing.append("character_mmd:expected_pmx_pmd_or_saved_mmd_blend")
        if key == "character_mmd" and path.suffix.lower() == ".blend" and assets.get("saved_mmd_skeleton") is not True:
            missing.append("character_mmd:declare_saved_mmd_skeleton")
    prompt = brief.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        missing.append("prompt:who_where_what_happens")
    for row in brief.get("missing_textures", []):
        if not isinstance(row, dict) or not isinstance(row.get("material"), str) or not row["material"].strip():
            raise ValueError("Missing textures require an explicit material name")
        kind = row.get("kind")
        if kind not in ("normal", "roughness", "metallic", "base_color", "mask", "other"):
            raise ValueError("Unknown missing texture kind")
        replacement = {"normal": "flat tangent normal (0.5, 0.5, 1.0), Non-Color; or disconnect normal map", "roughness": "reviewed constant roughness", "metallic": "reviewed constant metallic; default nonmetal"}.get(kind)
        fallbacks.append({**row, "strategy": replacement or "simplified palette/toon regions; disclose lost detail", "limitation": "Cannot reliably reproduce texture-dependent " + kind + " detail", "applied": False})
    decisions = brief.get("intent", {})
    blockers = decisions.get("conflicts", [])
    if not isinstance(blockers, list):
        raise ValueError("intent.conflicts must be a list")
    completed = brief.get("completed", [])
    if not isinstance(completed, list) or any(x not in STAGES for x in completed):
        raise ValueError("Unknown completed stage")
    # Completion is external evidence, never inferred from file existence.
    evidence = brief.get("evidence", {})
    for stage in completed:
        rows = evidence.get(stage, [])
        if not isinstance(rows, list) or not rows or any(not isinstance(x, str) or not (base / x).is_file() for x in rows):
            raise ValueError("Completed stage requires existing evidence files: " + stage)
    if completed != list(STAGES[:len(completed)]):
        raise ValueError("Completed stages must form an ordered prefix")
    motion = brief.get("motion_search", {})
    search_state = motion.get("status", "pending")
    if search_state not in ("pending", "ready", "login_required", "not_needed"):
        raise ValueError("Unknown motion search status")
    if search_state == "login_required" and any(x in completed for x in STAGES[2:]):
        raise ValueError("Unresolved login cannot mark the combined look/motion stage complete")
    if search_state == "pending" and any(x in completed for x in STAGES[2:]):
        raise ValueError("Resolve motion search before completing look_and_motion")
    if missing and completed:
        raise ValueError("Missing required inputs cannot have completed stages")
    if blockers and any(x in completed for x in STAGES[1:]):
        raise ValueError("Unresolved intent conflicts cannot complete intent")
    next_stage = STAGES[len(completed)] if len(completed) < len(STAGES) else "complete"
    status = "needs_inputs" if missing else "needs_clarification" if blockers else "awaiting_login_authorization" if search_state == "login_required" else "ready_for_agent"
    return {"schema": 1, "status": status, "missing": missing, "conflicts": blockers,
            "original_prompt": prompt, "intent": decisions, "exceptions": notes,
            "optional_inputs": {k: brief[k] for k in OPTIONAL if k in brief},
            "new_video_settings": new_video_settings(brief.get("output")),
            "fallback_plan": fallbacks, "next_stage": next_stage, "completed": completed,
            "motion_search": {"status": search_state, "paused": search_state == "login_required"},
            "independent_work_allowed": ["static_look_on_copies"] if search_state == "login_required" and not missing and not blockers else [],
            "agent_tasks": ["Assess intent and fill non-conflicting detail", "Apply and visually review basic toon mobile-game style on copies", "Search/adapt existing motion; stop login-dependent work for authorization", "Author shot list then low-cost preview and production"],
            "verification": "Input/state validation only; no semantic, rig, artistic, render or evidence-content acceptance implied"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.brief.read_text("utf-8")), args.brief.resolve().parent)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(result["status"])

if __name__ == "__main__":
    main()
