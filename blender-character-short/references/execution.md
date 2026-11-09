> v45 supplied-project production starts at [current production](current-production.md). The commands below retain the specialized original-PMX/source-AOV routes. The queue now requires source hashes and explicit saved-native mode; legacy size-only PNGs are not resume evidence.

# Execution and recovery

Record the actual native Blender exit code separately from its wrapper's
exit code. A wrapper can exit successfully after recording a failed child.
Keep the execution surface and any required per-command approval explicit;
one approved host invocation is not a permanent grant to leave a sandbox.

Classify a failed child from its actual log. An OS/application initialization
failure, a scene-open failure, a Python import error and a supported validation
refusal are different outcomes. Follow the user's explicit stopping condition;
do not silently broaden it to every script error or narrow it to ignore a real
application/scene failure. Preserve failed attempts and use new receipts/outputs
after an authorized repair. Blender entry points importing sibling modules must
insert their own `Path(__file__).resolve().parent` into `sys.path`; the Python
script directory is not guaranteed to be on Blender's import path.

## Shared execution lock

On Windows, wrap cooperating render commands with one shared lock path for the
task/GPU, even when their output directories differ:

```powershell
python "$Skill/scripts/execution_lock.py" --lock "$Work/render.lock" -- python "$Skill/scripts/run_short.py" --blender $Blender --asset $Pmx --mmd-source $MmdSource --dependencies $Deps --character $CharacterJson --story $StoryJson --post-config $PostJson --lut $LutPng --output $Output
```

The wrapper holds an OS byte-range lock until the child exits. A competing
wrapped command returns75 without starting its child. Child exit codes are
preserved; an unavailable executable returns127. Owner JSON is diagnostic,
not the lock. Metadata failure after launch and interruption during waiting
retain the lock while the child remains alive. Cancellation still requires
confirming and stopping only owned processes on their actual execution host.

This is cooperative exclusion, not detection of arbitrary existing Blender
instances. Force-killing the wrapper or losing the host can leave descendants
unverified; never infer that they stopped because the lock became available.
All task render launchers must share this path. Other operating systems are
explicitly unsupported by this wrapper until tested.

A restricted process view once reported no Blender while an authorized host
render was still active. Before recovery, query the same host surface used to
launch, match PID/executable/start time, and inspect frame/log changes. A missing
tool session is not a process-exit certificate. Preserve uncertain outputs and
freeze signatures; if overlapping writes occurred, isolate the affected frames
and resume only independently verified checkpoints. Do not kill unrelated
processes or remove original assets to resolve uncertainty.

## Pipeline

```powershell
python "$Skill/scripts/run_short.py" --blender $Blender --asset $Pmx --mmd-source $MmdSource --dependencies $Deps --character $CharacterJson --story $StoryJson --post-config $PostJson --lut $LutPng --output $Output --variant A --width 640 --height 360 --samples 16
```

Tested dependencies: Blender 4.5.15 LTS, mmd_tools source 4.5.14 with bundled wheels, Python 3.14.7, NumPy 2.5.4, Pillow, imageio_ffmpeg/FFmpeg 7.1. Add-on source contains mmd_tools/__init__.py. Import unpacks dependencies locally, not globally.

Products: import-baseline.blend, import-report.json, calibration.json, scene/scene.blend, scene/build-report.json, raw/frame_####.npz, frames/frame_####.png, preview.mp4, qa/, logs and input hashes. Scene textures are packed. Final-chain rerender still requires post profile, LUT and script version.

The optional `--body-approach-plan` adds `body-fit`, `body-travel`, `body-plant`
and `body-compose` before hand recovery/elbow/gaze/whole-scene tempo. Its five
local motion/rights files and body producer dependencies are bound to the
pipeline. Body plans require the original story duration and explicit
`body_interaction_frame`; changed inputs/producers require a clean output.
See [configured body approach](body-approach.md) for constraints and final audit.

Add --max-render-seconds N for a frame-boundary pause. After pipeline status paused, repeat the identical command without that option. Existing baseline/scene and validated raw frames are retained. Changed inputs/scripts require a new directory because pipeline identity hashes supplied inputs and all scripts.

### Frame-boundary budgets

`run_short.py --max-post-seconds N` pauses after committing a complete new post
frame and its SMAA edge/checkpoint state. It records pipeline `paused` with
`paused_stage: composite`; no video is encoded until post status is `complete`.
The standalone option is `post_sequence.py --max-new-seconds N`. Values must be
finite and positive. Budget timing includes only newly composited frame work;
cached prefix validation takes additional time, and the final frame may exceed
the budget. This is a frame-boundary limit, not a process timeout.

Repeat the same command with a different budget or omit the budget. Keep the
same frozen scripts, frame range, raw job, profile and lookup inputs. All cached
PNGs, edges and predecessor signatures are revalidated; the execution budget is
excluded from image identity. Preserve output and start a new directory when
any production script or image input changes. Never resume an old producer's
directory with the new budget implementation.

`verify_post_budget.py` accepts real raw inputs and the prior post script. It
compares default, repeated bounded and budget-to-unlimited runs byte-for-byte
for PNGs and exactly for SMAA edge arrays. A passing derived-sequence test is
CPU checkpoint evidence; it is not a forced-kill, whole-entrypoint or visual
continuity test. Record those separately.

NPZ resume verifies CRC, shape and finite rgba/weight. Corrupt frames regenerate. Post resume verifies PNG decoding and profile/LUT/raw-job/script identity. Preserve damaged outputs if needed as evidence; do not remove an asset tree to recover a frame.

Repeated entrypoint stages keep their first log and create numbered attempt
logs. Events record each real log path and child PID; prior progress is copied
before resume. A missing tool session handle is not a child exit receipt.
Inspect the recorded process and output before another attempt. On Windows,
avoid long-lived delete-blocking readers of atomically replaced progress files;
monitor append logs or use a reader sharing deletion. WinError5 alone neither
identifies its cause nor authorizes changing permissions.

For configured dorm material blueprints, the pipeline also binds the [blueprint
and each declared image](blueprint-inputs.md). Keep the evidence input manifest
for dependencies outside this specific guard. New frozen scripts still require
a new output directory; do not transplant them into an existing render cache.

## Standalone stages

```powershell
& $Blender --background --factory-startup --python-exit-code 1 --python "$Skill/scripts/render_performance.py" -- --blend $Scene --output $Raw --start 1 --end 240 --width 640 --height 360 --samples 16
python "$Skill/scripts/post_sequence.py" --raw $Raw --output $Frames --config $PostJson --lut $LutPng --end 240
python "$Skill/scripts/encode_video.py" --frames $Frames --pattern 'frame_%04d.png' --output $Video --count 240 --fps 24
python "$Skill/scripts/video_qa.py" $Video --output-dir $Qa --expected-fps 24 --expected-frames 240 --expected-duration 10
```

Encoding refuses existing video unless --overwrite is explicit. Defaults H.264 CRF18, yuv420p, faststart, silent. Dimensions must be even. Estimate full rendering from representative frames including AOV/post cost.

Reopen the saved delivery with verify_scene.py and inspect a real frame plus packed/missing images. Native Composite is raw; inspect a final postprocessed frame too. Record decode, timestamp samples, continuous viewing and listening separately.

Legacy render_queue.py remains for old PNG scenes. New source-style production uses render_performance.py/post_sequence.py; do not mix conventions or imply the legacy queue executes the new chain.

## Motion diagnostics

Run audit_motion.py inside background Blender with --blend, --character and --output. It reads every evaluated frame and reports support-foot drift, largest joint-position/rotation steps, camera/prop projections and quaternion-key hemisphere discontinuities. It does not save the scene or render. Use reported frame numbers to select real visual checks; speed metrics alone do not establish natural acting.

For isolated diagnostic cameras, timeline camera markers can replace a manually
assigned `scene.camera` during rendering. Clear those markers in the disposable
diagnostic copy, select the intended camera and assert its identity after the
render. Likewise, a keyed pose control may overwrite a manual test value at
render evaluation; freeze/key only the tested control and record the actual
before/after state. The repaired `probe_gaze.py` implements these checks and has
been run on both supplied original rigs. Never clear production shot markers or
whole-body animation merely to inspect a closeup.

## Labeled video comparisons

python scripts/compare_videos.py --left EARLIER --right CANDIDATE --output REVIEW.mp4 --duration SECONDS --left-label Earlier --right-label Candidate creates a silent side-by-side review and fully decodes it. Shorter inputs hold their last frame to the chosen duration; the JSON records this. Matched inputs support implementation comparisons; different stories/cameras are editorial comparisons, not pixel parity. Latin labels and Unicode file paths are tested; no audio comparison is implied.


## External project working directory

The external character `materials.dorm_blueprint` and body plan `source.files`
paths follow the process working directory. Each blueprint image `file` is
relative to that blueprint's parent. Launch the CLI from the external project's
root when using these relative paths; its children inherit that directory.
Supply the installed Blender/add-on/Python paths explicitly. Keep authorized
raw model, motion, lookup inputs and role mappings outside the generic skill.

For a relocation check, copy the immutable producer and authorized inputs into
a different clean directory with no old `.blend`, raw frames, post cache or
result folder. Run from that copy, inspect the collected motion/blueprint/image
paths, produce and decode a complete movie, and reopen its paired scene. Record
which installed dependencies remain external. This proves only the tested
same-machine directory/working-directory behavior, not cross-machine setup,
an independent agent context or another character.

When a receipt says running but stops advancing, check the original execution
session and exact owned processes on the launching surface before any recovery.
An empty restricted view alone is not host exit evidence. Preserve the stale
receipt, stage log and progress before a confirmed-gone job is resumed. Use
the same immutable producer/inputs in bounded stages, retain every new attempt
log, and keep an unknown interruption cause unknown. Successful continuation
is not proof that an OS/security root cause has been fixed. Never change host,
permissions or security controls to bypass an actual denial.
