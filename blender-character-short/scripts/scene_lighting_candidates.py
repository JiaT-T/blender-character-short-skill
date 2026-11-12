"""Create review-only, scene-linked lighting candidates without importing Blender."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from refine_scene import validate_config


def _num(value, low, high, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label}: expected finite number in [{low}, {high}]")
    return float(value)


def _vec(value, low, high, label):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label}: expected three numbers")
    return [_num(v, low, high, label) for v in value]


def _names(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{label}: explicit names required")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in value):
        raise ValueError(f"{label}: invalid name")
    if len(set(value)) != len(value):
        raise ValueError(f"{label}: duplicate name")
    return value


def generate(config, base):
    """Return candidates bound to verified source bytes. Never applies a scene patch."""
    allowed = {"schema", "source", "objects", "collection", "protected_objects", "target", "forward", "prefix", "mood", "material_intent", "base_energy"}
    required = {"schema", "source", "objects", "collection", "protected_objects", "target"}
    if not isinstance(config, dict) or set(config) - allowed or required - set(config):
        raise ValueError("Unknown or missing lighting request fields")
    if type(config["schema"]) is not int or config["schema"] != 1:
        raise ValueError("Lighting request schema 1 required")
    objects = _names(config["objects"], "objects")
    protected = _names(config["protected_objects"], "protected_objects")
    if set(objects) & set(protected):
        raise ValueError("Scene receivers must exclude declared character/protected objects")
    collection = config["collection"]
    validate_config({"schema": 1, "objects": objects, "collection": collection})
    src = config["source"]
    if not isinstance(src, dict) or set(src) != {"path", "sha256"} or not isinstance(src["path"], str) or not src["path"].strip():
        raise ValueError("Source requires path and sha256")
    if not isinstance(src["sha256"], str) or len(src["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in src["sha256"]):
        raise ValueError("Source SHA256 must be lowercase hex")
    path = (Path(base) / src["path"]).resolve()
    if path.suffix.lower() != ".blend" or not path.is_file():
        raise ValueError("Existing source .blend required")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != src["sha256"]:
        raise ValueError("Source SHA256 mismatch")
    target = config["target"]
    if not isinstance(target, dict) or set(target) != {"center", "dimensions"}:
        raise ValueError("Target requires center and dimensions in Blender world units")
    center = _vec(target["center"], -100000, 100000, "center")
    dimensions = _vec(target["dimensions"], 0.01, 50, "dimensions")
    scale = max(dimensions)
    forward = _vec(config.get("forward", [0, -1, 0]), -1, 1, "forward")
    if abs(forward[2]) > 1e-8 or math.hypot(forward[0], forward[1]) < 1e-6:
        raise ValueError("Forward must be a nonzero horizontal world-space vector; Z is up")
    norm = math.hypot(forward[0], forward[1])
    forward = [forward[0]/norm, forward[1]/norm, 0]
    right = [-forward[1], forward[0], 0]
    prefix = config.get("prefix", "StageCandidate")
    if not isinstance(prefix, str) or not prefix or not prefix.isascii() or any(not (c.isalnum() or c == "_") for c in prefix) or len(prefix) > 24:
        raise ValueError("Prefix must be 1..24 ASCII letters, digits or underscores")
    mood = config.get("mood", "neutral")
    material = config.get("material_intent", "mixed")
    if mood not in ("neutral", "warm", "cool") or material not in ("mixed", "matte", "glossy"):
        raise ValueError("Mood is neutral|warm|cool; material_intent is mixed|matte|glossy")
    base_energy = _num(config.get("base_energy", 100), 0.01, 400, "base_energy")
    key_color = {"neutral": [1, 1, 1], "warm": [1, .84, .68], "cool": [.72, .85, 1]}[mood]
    fill_color = {"neutral": [1, 1, 1], "warm": [.82, .9, 1], "cool": [1, .91, .8]}[mood]
    # Positions are authored from the target dimensions, not a universal photographic rule.
    layouts = [("soft", .65, .35, 1.0), ("separation", .3, .65, .75), ("restrained", .45, .2, 1.3)]
    size_factor = {"mixed": 1., "matte": .9, "glossy": 1.35}[material]
    candidates = []
    for tag, fill_ratio, rim_ratio, softness in layouts:
        rows = []
        for role, offset, ratio, color in (("Key", [-1, 1.4, 1.1], 1., key_color), ("Fill", [1.2, .8, .5], fill_ratio, fill_color), ("Rim", [.6, -1.1, 1.3], rim_ratio, key_color)):
            location = [center[i] + scale*(right[i]*offset[0] + forward[i]*offset[1] + (offset[2] if i == 2 else 0)) for i in range(3)]
            rows.append({"name": f"{prefix}_{tag}_{role}", "location": location, "target": list(center), "energy": base_energy*scale*scale*ratio, "size": scale*softness*size_factor, "color": list(color)})
        patch = {"schema": 1, "objects": list(objects), "collection": collection, "materials": [], "lights": [], "add_lights": rows}
        validate_config(patch)
        candidates.append({"id": tag, "reviewed": False, "scene_patch": patch})
    return {"kind": "scene-lighting-candidates", "schema": 1, "review_only": True, "applied": False,
            "source": dict(src), "source_verified": True,
            "request_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "protected_objects": list(protected), "scale": scale, "mood": mood, "material_intent": material,
            "candidates": candidates,
            "adoption": "Choose and review exactly one candidate; copy its scene_patch into a separately authored hash-bound refine plan. Never apply this whole report.",
            "limits": ["Source bytes verified, not Blender contents or material interpretation", "World Z-up and explicitly declared receiver/protected names are assumptions", "Actual collection membership and name collisions must pass native refinement guards", "No world, existing light, material, camera or character mutation", "Energy scales by dimension squared only as a starting estimate; exposure and toon response require a still preview", "No render, visual approval, indirect illumination isolation or temporal validation is implied"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    result = generate(json.loads(a.request.read_text("utf-8")), a.request.resolve().parent)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with a.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print("REVIEW_ONLY: three candidates; no scene modified")


if __name__ == "__main__":
    main()
