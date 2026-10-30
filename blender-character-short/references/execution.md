# Execution and recovery

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

Set the example path variables to your own files before running; `$Skill` is this extracted skill folder. Examples use PowerShell. The legacy jobs example uses paths relative to the process working directory. Copy external character/story/material/post profiles and authorized assets separately; the package intentionally contains none of those character assets.

```powershell
python "$Skill/scripts/run_short.py" --blender $Blender --asset $Pmx --mmd-source $MmdSource --dependencies $Deps --character $CharacterJson --story $StoryJson --post-config $PostJson --lut $LutPng --output $Output --variant A --width 640 --height 360 --samples 16
```

Tested dependencies: Blender 4.5.15 LTS, mmd_tools source 4.5.14 with bundled wheels, Python 3.14.7, NumPy 2.5.4, Pillow 13.0.0, imageio_ffmpeg 0.6.0 / FFmpeg 7.1. Add-on source contains mmd_tools/__init__.py. Import unpacks dependencies locally, not globally.

Products: import-baseline.blend, import-report.json, calibration.json, scene/scene.blend, scene/build-report.json, raw/frame_####.npz, frames/frame_####.png, preview.mp4, qa/, logs and input hashes. Scene textures are packed. Final-chain rerender still requires post profile, LUT and script version.

Add --max-render-seconds N for a frame-boundary pause. After pipeline status paused, repeat the identical command without that option. Existing baseline/scene and validated raw frames are retained. Changed tracked inputs/scripts require a new directory because pipeline identity hashes directly supplied top-level files and all scripts. This does not cover every transitive resource: mmd_tools source/wheels and material-config references such as blueprint, source GLB, manifests or images are not all included. Freeze and separately hash those resources before resume; do not reuse cached scenes after changing them.

NPZ resume verifies CRC, shape and finite rgba/weight. Corrupt frames regenerate. Post resume verifies PNG decoding and profile/LUT/raw-job/script identity. Preserve damaged outputs if needed as evidence; do not remove an asset tree to recover a frame.

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
