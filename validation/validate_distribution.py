"""Check this distribution without loading assets or rendering a scene."""
from __future__ import annotations

import argparse
import io
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tokenize
from hashlib import sha256


HOST_CLI = (
    "calibrate_character.py", "compare_videos.py", "convert_glb_motion.py", "encode_video.py",
    "execution_lock.py", "post_sequence.py", "run_short.py", "smaa_cpu.py",
    "source_post.py", "verify_glb_motion.py", "verify_post.py", "verify_post_budget.py", "video_qa.py",
    "short_project.py", "encode_saved_project.py",
)


MEDIA_PATHS = {"docs/media/nietiya-demo-1080p30.mp4", "docs/media/nietiya-demo-poster.jpg"}

# Public SDK interface identifiers, checked against Microsoft's dxcore_interface.h.
PUBLIC_DXCORE_GUIDS = {
    "78ee5945-c36e-4b13-a669-005dd11c0f06", "526c7776-40e9-459b-b711-f32ad76dfc28",
    "f0db4c7f-fe5a-42a2-bd62-f2a6cf6fc83e", "b69eb219-3ded-4464-979f-a00bd4687006",
}
GUID_PATHS = {"blender-character-short/scripts/render_device_policy.py", "validation/validate_distribution.py"}


def validate_text_privacy(relative: str, text: str) -> None:
    patterns = {
        "credential": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,})"),
        "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "machine-path": re.compile(r"\b[A-Za-z]:[\\/](?:Users|Documents|Program Files|Python|project)[\\/]|(?<![A-Za-z0-9_])/(?:root|home|Users|mnt|tmp)/[A-Za-z0-9_.-]+"),
        "session-uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    }
    for kind, pattern in patterns.items():
        content = text
        if kind == "email" and relative.endswith(".py"):
            content = "\n".join(t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                                if t.type in (tokenize.STRING, tokenize.COMMENT))
        for match in pattern.finditer(content):
            if kind == "session-uuid" and relative in GUID_PATHS and match.group(0).lower() in PUBLIC_DXCORE_GUIDS:
                continue
            raise AssertionError(f"Review required for {kind}: {relative}")


def validate_demo_media(root: Path) -> set[str]:
    """Only the two explicitly reviewed demo outputs may accompany the skill."""
    path = root / "release/demo-media.json"
    if not path.exists():
        return set()
    media = json.loads(path.read_text("utf-8"))
    rows = media["files"]
    assert len(rows) == 2 and {r["path"] for r in rows} == MEDIA_PATHS, "Unexpected media allowlist"
    for row in rows:
        file = root / row["path"]
        assert file.is_file() and not file.is_symlink(), "Missing or linked demo media"
        data = file.read_bytes()
        assert 0 < len(data) <= 50_000_000 and len(data) == row["bytes"], "Demo media size differs"
        assert sha256(data).hexdigest() == row["sha256"], "Demo media hash differs"
        if file.suffix == ".mp4":
            assert data[4:8] == b"ftyp", "Expected MP4 container"
        else:
            assert data[:3] == b"\xff\xd8\xff", "Expected JPEG poster"
    return MEDIA_PATHS


def validate(root: Path) -> dict:
    skill = root / "blender-character-short"
    scripts = sorted((skill / "scripts").glob("*.py"))
    manifest = json.loads((root / "release/distribution-manifest.json").read_text("utf-8"))
    actual = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
              for p in skill.rglob("*") if p.is_file()}
    assert actual == manifest["files"], "Skill file set or hashes differ from the distribution manifest"
    assert len(actual) == manifest["source_file_count"]
    assert len(scripts) == manifest["script_count"]

    validation_scripts = sorted((root / "validation").glob("*.py"))
    for script in scripts + validation_scripts:
        compile(script.read_bytes(), script.name, "exec", dont_inherit=True)

    json_files = sorted(skill.rglob("*.json"))
    for path in json_files:
        json.loads(path.read_text("utf-8"))

    entry = (skill / "SKILL.md").read_text("utf-8")
    assert entry.startswith("---\n")
    front = entry.split("---", 2)[1]
    assert re.search(r"^name: blender-character-short$", front, re.MULTILINE)
    assert re.search(r"^description: .+", front, re.MULTILINE)

    links = 0
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text("utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            dest = target.split("#", 1)[0]
            assert (path.parent / dest).is_file(), f"Broken document link: {path.name}: {target}"
            links += 1

    demo_media = validate_demo_media(root)

    forbidden = {".pmx", ".pmd", ".blend", ".glb", ".gltf", ".png", ".jpg", ".jpeg", ".bmp",
                 ".tga", ".dds", ".ktx", ".exr", ".hdr", ".npz", ".npy", ".mp4", ".mov",
                 ".webm", ".avi", ".wav", ".mp3", ".ogg", ".zip", ".whl", ".exe", ".dll", ".pyc"}
    reviewed = 0
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.relative_to(root).as_posix() in demo_media:
            continue  # Exact paths, bytes, hashes and media headers checked above.
        assert path.suffix.lower() not in forbidden, f"Excluded artifact: {path.name}"
        assert path.suffix.lower() in {".py", ".md", ".json"} or path.name in {".gitignore", ".gitattributes"}, path.name
        text = path.read_text("utf-8-sig")
        validate_text_privacy(path.relative_to(root).as_posix(),text)
        reviewed += 1

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    cli = []
    for name in HOST_CLI:
        proc = subprocess.run([sys.executable, "-B", str(skill / "scripts" / name), "--help"],
                              cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0 and "usage:" in proc.stdout.lower(), f"CLI help failed: {name} ({proc.returncode})"
        cli.append({"script": name, "returncode": proc.returncode})

    versions = {name: metadata.version(name) for name in ("numpy", "Pillow", "imageio-ffmpeg")}
    evidence = json.loads((root / manifest["runtime_evidence"]).read_text("utf-8"))
    assert evidence["source_generic_zip_sha256"] == manifest["source_archive_sha256"]
    assert manifest["all_scripts_byte_identical_to_frozen_v45a"]
    assert evidence["native_producer_sha256"] == sha256(json.dumps({p.name:sha256(p.read_bytes()).hexdigest() for p in scripts},sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
    return {
        "passed": True,
        "distribution_version": manifest["distribution_version"],
        "scope": "Distribution checks only; no PMX import, Blender render, video production, continuous viewing or listening",
        "python": platform.python_version(),
        "dependencies": versions,
        "skill_files": len(actual),
        "skill_scripts_compiled_without_bytecode": len(scripts),
        "validation_scripts_compiled": len(validation_scripts),
        "json_fixtures_parsed": len(json_files),
        "internal_markdown_file_links_checked": links,
        "frontmatter_required_fields_checked": True,
        "skill_creator_quick_validate": "Passed for the local frozen source; publication validates required frontmatter fields and links",
        "files_reviewed_for_excluded_artifacts_and_sensitive_patterns": reviewed,
        "demo_media_verified": sorted(demo_media),
        "host_cli_help": cli,
        "blender_execution": "Not run for publication. Recorded v45a native202 and local integration evidence are separate, with exact frozen script identities",
        "skill_scripts_modified_for_publication": False,
        "publication_validator_updated": True,
        "recorded_native_suite": evidence["recorded_native_suite"],
        "recorded_host_suite": evidence["recorded_host_suite"],
        "public_api_guid_review": "Only four exact DXCore GUID constants in their two declared source files; all other UUIDs still rejected",
        "historical_user_V04_acceptance": True,
        "assistant_normal_speed_continuous_viewing": False,
        "new_story_production": False,
        "continuous_interval_verified": False,
        "recorded_raw_PMX_reuse": "v45a direct MMR generation plus fresh reopen/skin response tested on one raw MMD baseline; no new complete story from raw input",
        "main_film_raw_PMX_rebuild": False,
        "general_finger_or_cross_character_retargeting": "not certified; one model and bounded actual skin probes only, not all fingertip IK controls",
        "naturalness_acceptance": "Not certified for the new diagnostics; historical V04 user acceptance is separate",
        "continuous_visual_review": "Sampled images only; no new normal-speed continuous acceptance",
        "audio_review": "not completed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("release/validation.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = validate(root)
    report = args.report if args.report.is_absolute() else root / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
