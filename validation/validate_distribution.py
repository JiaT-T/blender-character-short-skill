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
    "calibrate_character.py", "compare_videos.py", "encode_video.py",
    "execution_lock.py", "post_sequence.py", "run_short.py", "smaa_cpu.py",
    "source_post.py", "verify_post.py", "verify_post_budget.py", "video_qa.py",
)


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

    forbidden = {".pmx", ".pmd", ".blend", ".glb", ".gltf", ".png", ".jpg", ".jpeg", ".bmp",
                 ".tga", ".dds", ".ktx", ".exr", ".hdr", ".npz", ".npy", ".mp4", ".mov",
                 ".webm", ".avi", ".wav", ".mp3", ".ogg", ".zip", ".whl", ".exe", ".dll", ".pyc"}
    patterns = {
        "credential": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,})"),
        "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "machine-path": re.compile(r"\b[A-Za-z]:[\\/](?:Users|Documents|Program Files|Python|project)[\\/]|/(?:root|home|Users|mnt|tmp)/[A-Za-z0-9_.-]+"),
        "session-uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    }
    reviewed = 0
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        assert path.suffix.lower() not in forbidden, f"Excluded artifact: {path.name}"
        assert path.suffix.lower() in {".py", ".md", ".json"} or path.name in {".gitignore", ".gitattributes"}, path.name
        text = path.read_text("utf-8-sig")
        for kind, pattern in patterns.items():
            content = text
            if kind == "email" and path.suffix == ".py":
                # Python's matrix operator can resemble an address; inspect literals and comments.
                content = "\n".join(t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                                    if t.type in (tokenize.STRING, tokenize.COMMENT))
            assert not pattern.search(content), f"Review required for {kind}: {path.relative_to(root)}"
        reviewed += 1

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    cli = []
    for name in HOST_CLI:
        proc = subprocess.run([sys.executable, "-B", str(skill / "scripts" / name), "--help"],
                              cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0 and "usage:" in proc.stdout.lower(), f"CLI help failed: {name} ({proc.returncode})"
        cli.append({"script": name, "returncode": proc.returncode})

    versions = {name: metadata.version(name) for name in ("numpy", "Pillow", "imageio-ffmpeg")}
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
        "skill_creator_quick_validate": "Not run for this update; required frontmatter fields checked locally without PyYAML",
        "files_reviewed_for_excluded_artifacts_and_sensitive_patterns": reviewed,
        "host_cli_help": cli,
        "blender_execution": "Not run; existing 0xC0000022 startup fault. No scene import, Blender help, rendering or runtime audit attempted",
        "scripts_modified": False,
        "independent_whole_package_v25_production": "not performed",
        "full_body_motion_reuse": "not completed",
        "naturalness_acceptance": "not completed",
        "continuous_visual_review": "not completed",
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
