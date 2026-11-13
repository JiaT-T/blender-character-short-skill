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
    "mcp_jobs.py", "mcp_service.py", "mcp_setup.py", "calibrate_character.py", "compare_videos.py", "convert_glb_motion.py", "encode_video.py",
    "execution_lock.py", "post_sequence.py", "run_short.py", "smaa_cpu.py",
    "source_post.py", "verify_glb_motion.py", "verify_post.py", "verify_post_budget.py", "video_qa.py",
    "short_project.py", "encode_saved_project.py", "refine_saved_project.py", "production_workflow.py", "shot_plan.py", "planned_video_review.py", "scene_lighting_candidates.py", "curve_native_fixture.py",
)


MEDIA_PATHS = {"docs/media/nietiya-demo-1080p30.mp4", "docs/media/nietiya-demo-poster.jpg"}

# Public SDK interface identifiers, checked against Microsoft's dxcore_interface.h.
PUBLIC_DXCORE_GUIDS = {
    "78ee5945-c36e-4b13-a669-005dd11c0f06", "526c7776-40e9-459b-b711-f32ad76dfc28",
    "f0db4c7f-fe5a-42a2-bd62-f2a6cf6fc83e", "b69eb219-3ded-4464-979f-a00bd4687006",
}
GUID_PATHS = {"blender-character-short/scripts/render_device_policy.py", "validation/validate_distribution.py"}


def validate_execution_counts(actual: dict) -> None:
    """Bind resumed frames to the current movie, independently of old rehearsals."""
    for key in ("retained_frames", "final_frames", "initial_rehearsal_frames"):
        assert type(actual[key]) is int and actual[key] > 0, "Positive integer execution counts required"
    assert actual["retained_frames"] < actual["final_frames"], "Retained frames must fit inside the current final render"
    assert actual["final_size"] == [1280, 720] and actual["fps"] == 24, "Declared native production size/rate differs"
    assert type(actual["full_encoded_decode_exit"]) is int and actual["full_encoded_decode_exit"] == 0, "Successful full decode required"


def validate_native_stage_exits(execution: dict) -> None:
    """A reported readable cache never replaces separate successful processes."""
    jobs = execution["independent_physics_native_stage_exits"]
    assert set(jobs) == {"physics-bake", "physics-fresh-verify"}, "Separate bake and reader receipts required"
    hashes = set()
    for name, exit_field in (("physics-bake", "bake_process_exitcode"),
                             ("physics-fresh-verify", "fresh_verify_process_exitcode")):
        row = jobs[name]
        assert row["status"] == "completed", "Native physics stage must complete"
        assert type(row["returncode"]) is int and row["returncode"] == 0, "Native physics stage must exit zero"
        value = execution["actual_existing_physics"][exit_field]
        assert type(value) is int and value == 0, "Independent reported native exit must be zero"
        digest = row["job_receipt_sha256"]
        assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "Valid receipt identity required"
        hashes.add(digest)
    assert len(hashes) == 2, "Bake and fresh reader must have distinct receipts"


def validate_text_privacy(relative: str, text: str) -> None:
    patterns = {
        "credential": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,})"),
        "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "machine-path": re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]+|(?<![A-Za-z0-9_])/(?:root|home|Users|mnt|tmp)/[A-Za-z0-9_.-]+"),
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
    producer_hash = sha256(json.dumps({p.name:sha256(p.read_bytes()).hexdigest() for p in scripts},sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
    if manifest["distribution_version"] in ("v46", "v46.1", "v47-candidate", "v47", "v48", "v48.1", "v48.2"):
        assert manifest["current_producer_sha256"] == producer_hash
        current_evidence = json.loads((root / manifest["refinement_evidence"]).read_text("utf-8"))
        if manifest["distribution_version"] == "v46":
            assert current_evidence["producer_sha256"] == producer_hash
        else:
            assert current_evidence["producer_sha256"] == manifest["historical_v46_producer_sha256"]
        assert current_evidence["static_only"] and current_evidence["source_assets_distributed"] is False
        if manifest["distribution_version"] in ("v48.1", "v48.2"):
            curve = json.loads((root / manifest["curve_smoothing_evidence"]).read_text("utf-8"))
            curve_producer = producer_hash if manifest["distribution_version"] == "v48.1" else manifest["previous_producer_sha256"]
            assert curve["distribution_version"] == "v48.1" and curve["producer_sha256"] == curve_producer
            assert curve["source_assets_distributed"] is False
            assert curve["host_regressions"]["passed"] and curve["host_regressions"]["tests_run"] >= 12
            fixture = curve["native_fixture"]
            assert fixture["author_completed"] and fixture["fresh_reader_completed"] and fixture["different_processes"]
            assert fixture["passed"] and all(fixture["checks"].values())
            for name, expected in fixture["module_sha256"].items():
                assert sha256((skill / "scripts" / name).read_bytes()).hexdigest() == expected
            assert sha256((skill / "scripts/curve_native_fixture.py").read_bytes()).hexdigest() == fixture["entry_sha256"]
            assert curve["continuous_normal_speed_acceptance"] is False
            if manifest["distribution_version"] == "v48.1" and manifest.get("publication_guard_evidence"):
                guards = json.loads((root / manifest["publication_guard_evidence"]).read_text("utf-8"))
                assert guards["passed"] and guards["tests_run"] >= 8
                assert guards["production_scripts_changed"] is False and guards["source_assets_distributed"] is False
                assert guards["producer_sha256"] == producer_hash
                assert set(guards["validated_files_sha256"]) == {"validation/validate_distribution.py", "validation/test_distribution_guards.py"}
                for name, expected in guards["validated_files_sha256"].items():
                    assert sha256((root / name).read_bytes()).hexdigest() == expected
        if manifest["distribution_version"] == "v48.2":
            execution = json.loads((root / manifest["mcp_production_evidence"]).read_text("utf-8"))
            assert execution["distribution_version"] == "v48.2" and execution["producer_sha256"] == producer_hash
            assert execution["frozen_execution_producer_sha256"] == producer_hash
            assert execution["production_version_sha256"] == sha256((skill / "version.json").read_bytes()).hexdigest()
            assert execution["source_assets_distributed"] is False
            expected_modules = {"mcp_jobs.py", "runtime_addons.py", "short_project.py", "saved_shot_contract.py",
                                "saved_project_render.py", "encode_saved_project.py", "cache_existing_physics.py"}
            assert set(execution["changed_production_modules"]) == expected_modules
            for name, expected in execution["changed_production_modules"].items():
                assert sha256((skill / "scripts" / name).read_bytes()).hexdigest() == expected
            assert execution["host_regressions"]["passed"] and execution["host_regressions"]["tests_run"] >= 113
            native = execution["native_regressions"]
            assert native["passed"] and native["tests_run"] >= 214 and native["skips"] == 0
            actual_execution = execution["actual_mcp"]
            assert all(actual_execution[k] is True for k in ("doctor", "render", "encode", "cooperative_cancel_and_identity_bound_resume"))
            validate_execution_counts(actual_execution)
            validate_native_stage_exits(execution)
            physical = execution["actual_existing_physics"]
            assert all(physical[k] is True for k in ("bake_completed", "fresh_process_reopen_verified",
                       "all_integer_rigid_controller_native_finite", "stored_assets_actions_and_rig_unchanged",
                       "separate_appearance_comparison_passed"))
            assert physical["scene_mmd_root_count"] >= 2 and physical["passive_body_count"] >= 1
            assert physical["collision_or_naturalness_acceptance"] is False
            assert execution["intermittent_uncertain_root_cause_resolved"] is False
            assert execution["normal_speed_continuous_viewing"] is False
            assert execution["client_process_tree_survival_verified"] is False
    else:
        assert manifest["all_scripts_byte_identical_to_frozen_v45a"]
        assert evidence["native_producer_sha256"] == producer_hash
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
        "skill_creator_quick_validate": "Standalone quick validator unavailable (PyYAML missing); publication validates required frontmatter fields and links",
        "files_reviewed_for_excluded_artifacts_and_sensitive_patterns": reviewed,
        "demo_media_verified": sorted(demo_media),
        "host_cli_help": cli,
        "blender_execution": "This distribution checker does not run Blender; historical v46 static integration evidence and historical v45a suites are separately identified; v46.1 adds host workflow checks; v47 adds synthetic planning/review tests; v48 job/setup and native doctor evidence is separate",
        "skill_scripts_modified_for_publication": manifest["distribution_version"] == "v46",
        "historical_v46_refinement_evidence": manifest.get("refinement_evidence"),
        "publication_validator_updated": True,
        "historical_v45a_native_suite": evidence["recorded_native_suite"],
        "historical_v45a_host_suite": evidence["recorded_host_suite"],
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
