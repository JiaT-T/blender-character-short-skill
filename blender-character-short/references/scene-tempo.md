# Coupled scene timing

Use a whole-scene time map when a completed greybox shows that an approach,
pause or recovery needs a different pace. State the story reason and compare
complete dynamic previews before choosing a version. Preserve the original.

This route resamples existing keyed performance, expression, prop, material and
camera animation together after the hand, elbow and gaze layers. It does not
acquire an action, retarget a skeleton, create a convincing gait or validate
naturalness. The separate [configured body approach](body-approach.md) covers a
narrow reviewed local-data/original-rig route; general action acquisition,
FBX/Mixamo and cross-character retargeting remain outside its verified scope.

## External plan

Supply exactly `schema` and `knots`. Each knot has integer `output` and `source`
frames. For example, a 120-frame source can become 96 output frames:

```json
{"schema":1,"knots":[{"output":1,"source":1},{"output":25,"source":25},{"output":49,"source":73},{"output":96,"source":120}]}
```

Input starts at frame1, contains2..1200 frames, and the map covers its complete
range. Output starts at1 and ends within1200. Output knots strictly increase;
source knots never decrease. Equal adjacent source values create a hold.
Linear mapping between integer knots can evaluate fractional source frames.
Backward playback, loops and scene truncation are outside this contract.

Camera cuts move to the first output frame at or after their source frame.
Multiple camera cuts collapsing onto one output frame are refused. Annotations
may share a frame. All timeline markers must lie inside the source range.

## Execute

Pass `--scene-tempo-plan PLAN.json` to `run_short.py` using a new output
directory. It applies this stage after gaze, binds input/producer hashes, and
uses the new count consistently for raw render, external post, encoding and
decode. Acting/gaze/contact plans still use the original source timeline.

Standalone:

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/bake_scene_tempo.py -- --blend INPUT.blend --plan PLAN.json --output NEW.blend --report NEW.json
```

The writer saves only after numeric and mapped-state checks pass. Existing
outputs or stale stage evidence must be preserved and require a new version.
The saved report binds scene, plan, writer and both validators by SHA256.

## Boundaries and verification

Supports one local scene with keyed single-slot Actions. Rejects drivers, NLA,
linked libraries, nonempty sequencer data, rigid-body worlds, simulation/cache
and geometry-node modifiers, particle systems, image sequences/movies, cached
source outlines, F-curve modifiers/sampled curves and motion-blur integration.
An empty sequence editor is permitted. Do not strip unsupported content merely
to get a success report; choose a separately reviewed bake or another route.

Every source integer frame and original in-range key time is sampled for finite
world matrices/curve values. Original keys and handles must also be finite.
This prevents a skipped original key from concealing a known numeric overflow.
Total source checks plus output capture/verification are capped at500000
matrix-frames and2000000 curve samples; original keys also cap at2000000.

Every output integer frame must match its mapped source bone/object world
matrices, F-curve values and active camera. Dense output keys are LINEAR,
creating a new interpolation between those samples. These checks do not prove
subframe safety or the entire continuous source interval is finite. Changed
velocity/acceleration, collision-free interpolated motion, foot timing and
naturalness require further observation. Recheck the saved scene, final contact
and whole preview. Preserve decode, sampled viewing and continuous viewing as
separate evidence.

`verify_scene_tempo.py --output NEW_DIRECTORY` constructs its own small assets
and exercises fractional timing, shape/material/property/camera preservation,
save/reopen, numeric overflow refusal and unsupported-data boundaries. It is
not production-character or independent-context acceptance.
