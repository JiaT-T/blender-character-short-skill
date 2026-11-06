# Short comic acting from reusable clips

Use this optional route when a small story needs readable intentions, repeated
gestures, a delayed reaction or a playful prop. Start with the character's wish,
the obstruction and a visible change at the end. A simple floating original prop
can be intentionally stylized. Choose contact diagnostics in proportion to the
shot: visible penetration or unexplained sliding warrants repair, while physical
force closure is optional for a cartoon gag.

Give each beat an action verb and an observable consequence. Repeat a gesture
with a different duration/amplitude to show a changed intention; leave enough
stillness to read the result. Eyes can notice first, the head follow several
frames later and the torso react last. Use independently placed tracks rather
than starting every body part on the same key. Keep blinks away from essential
visual information. A head turn can hide the expression and pull long weighted
hair; compare a three-quarter version before increasing the amplitude.

## External clip plan

`acting_clip_plan.py` is ordinary Python. `compile_plan(document)` validates an
external `schema:1`, `frames:[first,last]`, `fps`, `channels`, `clips` and
`instances`. `values(compiled, frame)` returns semantic values at integer or
fractional frames. Inputs stay unchanged.

- A channel has `width:1..4`, `base:[...]` and a finite inclusive `range:[lo,hi]`.
  Names/units are supplied by the consuming character mapping.
- A clip has `tracks:{channel:[[phase,[values...]],...]}` and optional
  `curve:"quintic"` (default) or `"linear"`. Each track includes phases 0 and 1
  with strictly ordered phases between them. Explicit repeated-value keys make
  a hold; extra keys can author anticipation and overshoot.
- An instance has unique `id`, known `clip`, integer `start/end` and optional
  `amplitude:0..2`. Its keys retime into that interval. Amplitude scales values
  about the channel's declared base. It does not scale world coordinates about
  the origin.
- Different channels can overlap. Two instances writing the same channel cannot
  overlap. At an entry, the first value must equal the preceding held value.
  Values before the first instance use the base; values after a clip hold its
  last value. Return a reusable gesture to its base when it should recover.

The compiler bounds 480 frames, 192 channels, 128 clips, 256 instances, 16,384
source keys and 200,000 scalar frame samples. These limits do not override a
consumer's tighter bone/skin or frame limit. Six pure tests in
`test_acting_clip_plan.py` exercise retiming, repeated/scaled gestures, holds,
continuity, independent tracks and refusal of conflicting/invalid inputs.

## Existing-rig body, gaze and finger composition

`bake_acting_clips.py` uses at most **240 frames** because it exports to the
existing [hand-control route](hand-controls.md). Supply an authorized source
scene, externally calibrated hand profile, semantic mapping and clip plan:

```text
blender --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python scripts/bake_acting_clips.py -- \
  --blend SOURCE.blend --mapping ACTING_MAPPING.json \
  --hand-profile BOUND_HAND_PROFILE.json --plan ACTING_PLAN.json \
  --output NEW_BODY.blend --hand-motion NEW_FINGERS.json \
  --report NEW_BODY_REPORT.json
```

The mapping owns `height`, `ground`, `reference_frame`, semantic `bones`, optional
`neutral_overrides` in local XYZ degrees, `rotation_channels`, world wrist-roll
axes, head forward/angle limit, optional existing binocular `gaze`, shape-name
mapping, `finger_groups`, own orb size/colour/name and camera. Targets/poles,
gaze targets, orb positions and camera positions use character-height world
coordinates with ground added to Z. Rotations use degrees. Finger and expression
channels use scalar fractions in 0..1. Orb scale is a three-vector.

The current consumer expects three-vectors `left_target`, `left_pole`,
`right_target`, `right_pole`, `look`, `eye_look`, `head_tilt`, `orb`, `orb_scale`,
`orb_rotation`, and scalar `left_roll`, `right_roll`. Each `finger_groups` entry
maps a channel to explicit `[joint_id,axis_id]` members from the hand profile.
Shape semantic channels map to original morph names. The prop is an owned sphere
with two simple eye primitives; it is not a downloaded character asset.

The source reference pose seeds the original rig. The new action changes the
configured upper body, analytic original-rig FK arms, head, existing eye control
and mapped morphs. Remaining bones stay at the reference pose, including legs;
this is stationary acting, not locomotion or preservation of the source story.
Unreachable required wrist targets fail; correct the authored target rather than
accepting a clamp. The writer hides old stage meshes/lights/cameras only in the
new copy. Original rest bones, skin weights and morph geometry remain unchanged.

Apply exported `NEW_FINGERS.json` to `NEW_BODY.blend` using
`bake_hand_controls.py`, then independently reopen with `audit_hand_controls.py`.
The finger layer must preserve the authored body, eyes, expressions and props.
For a long original rig, begin with integer-frame audit (`--substeps 1`) within
the documented work budget; declare this scope and inspect transitions visually.
Half-frame or contact tests may be added when a specific shot needs them.

## Low-cost complete-motion preview

`render_acting_preview.py` accepts `--blend`, external `--profile`, new `--out`,
`--mode keys|video` and `--budget` (at most 360 seconds per invocation). It uses
Cycles CPU, one thread and at most 640 pixels/4 samples; it never saves the
source scene. Its signature binds saved-scene/profile/producer hashes and
supports resuming matching completed frames. Use the shared execution lock and
recheck the actual host workload before rendering alongside another task.

The external preview profile supplies `size`, `samples`, `brightness`,
`background`, explicit material adapters, key views and optional close cameras.
Each `materials` entry names an actual source material and a declared
`image_node` with optional image alpha/opacity, or a constant colour. Explicit
`owned_material_prefixes` may map procedurally owned materials. An unmapped
visible material fails. `keys` lists `{frame,view}`; `views` maps custom view
names to metre-world camera location/target/orthographic scale. `wide` uses the
saved inspection camera.

This emissive image/UV adapter deliberately removes lighting and compositing
cost so expressions and silhouettes are readable. It does not reproduce the
original shader, normals, highlights, shadows, depth effects or source post chain.
Encode every rendered frame at the scene's actual fps and decode the complete
file. Review wide acting, face/gaze and hand silhouettes. Then watch the full
clip at normal speed when reliable observation is available. A contact sheet or
successful pose audit does not establish continuous naturalness or comedy.

If a wide shot hides expression or a small hand action, render a bounded range
of the same saved frames with a face/hand key-view profile. Keep preview material
and sampling settings identical. `compose_acting_preview.py --plan EDIT.json
--output NEW_EDIT.mp4 --report NEW_EDIT.json` selects these rendered frames at
their original times. The external schema-1 edit plan supplies `frames`, `fps`,
`sources:{id:{frames_report,profile}}` (paths relative to the plan) and ordered
`shots:[{first,last,source,view}]`. Shots cover the entire timeline exactly once.
The editor rejects unmatched scene/style/size/producer identities, stale image
hashes and missing frames. It copies a pinned numbered sequence and encodes/
decodes on one below-normal CPU thread. Retain the uninterrupted wide preview;
cuts help storytelling but do not demonstrate the body continuity they hide.

Save rejected takes and the selected take with their external plans and producer
versions. Record what the viewer can actually see, the unverified areas and the
next editorial decision. Favor the readable performance over accumulating small
numeric improvements that do not change the shot.


## Following inspection views

A preview view may supply ollow_object, or ollow_bone with rmature and one, plus camera_offset_m, 	arget_offset_m and ortho_scale_m. Its camera is recomputed from the evaluated target for each frame; keep character names and offsets in the external profile. This supports foot/face inspection during root travel. Preserve a full-body delivered view and inspect continuity separately. See [body motion remix](body-motion-remix.md) for the limited source-backed full-body route.
