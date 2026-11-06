# Existing body asset to comic performance

Use this optional route for a reviewed local body fragment, an independently
prepared neutral scene of the **same original rig and mesh**, and an external
acting plan. Fit, travel and plant the permitted source first as described in
[configured body approach](body-approach.md). Preserve raw inputs and rejected
takes. This route starts already moving; it is not an automatic standing start,
general FBX/Mixamo retargeter, arbitrary-character adapter or physics solver.

## Calibrate before authoring

Inspect the original knee limits, bone-local hinge axes and actual weighted shoe
groups. A direction-only upper-leg fit can leave the knee bend plane wrong.
The body plan optionally supplies `limb_hinges.left_leg/right_leg` with unit
`axis_local`, explicit `bend_sign` (-1 or 1), and optional
`minimum_bend_degrees` (0..30). Determine these from the actual rig, not a
character-name assumption. A nonzero bend floor modifies source motion: retain
the per-frame adaptation record rather than describing it as unmodified reuse.
The limit rotation remains active; only the explicitly configured leg IK route
is muted in a separate adapted scene.

Rebuild fit/travel/plant after changing the plan or a bound dependency. The body
records bind sixteen producer/dependency files. Target rigs are bounded to
2048 bones and 500000 bone-frames; source-node and conversion limits remain
separate. Contact intervals must be measured for the new shoe and action.
Do not reuse another character's stance labels or plant a flight phase.

## Compose a readable large action

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/remix_body_motion.py -- --blend PLANTED.blend --source-report PLANTED.json --body-plan SOURCE_PLAN.json --neutral NEUTRAL.blend --mapping ROLE.json --acting-plan ACTING.json --output NEW_BODY.blend --report NEW_BODY.json
```

The external plan uses the existing [acting clip compiler](performance-clips.md)
and a `remix` object. It requires ordered integer `source_end < left_land <
stop_end < recover_start < recover_end < last`, right reference support and at
most 240 output frames. The implemented phase sequence is right-foot source
support, left landing, right landing, planted reaction, then right recovery
step. It is a deliberately narrow, inspected recipe. Choose a source ending
in the declared material stance; other phase orders need another implementation.

Keep source time, source/acting blend, crouch, spine, left/right wrist and elbow
targets, hand finger/normal frames, head/eye target, expressions and owned prop
trajectory in external tracks. The role mapping supplies actual bone and morph
names, calibrated palm frames, knee poles, neutral frame, height and ground.
The neutral scene must have identical original rest hierarchy, skin weights,
mesh and morph geometry. The remixer rejects a mismatched scene. Source travel
velocity and chosen stop duration determine the deceleration distance; contact
is solved on actual selected weighted material points. Hand controls are a
separate `bake_hand_controls.py` stage after body authoring.

For large arm changes, the external role may explicitly set
`transport_arm_frames: true` (default false preserves the earlier solver).
The optional route transports the previous evaluated upper/forearm orientation
onto each new anatomical segment direction, rather than repeatedly choosing a
rest-to-target shortest arc. It rejects an antipodal temporal direction step
and verifies the unblended hand endpoint within0.0001H. It does not alter rest
geometry, segment lengths or original constraints. The deterministic bake must
run sequentially; the saved keys remain ordinary random-access animation.
The saved scene's `arm_frame_transport` property records the option and maximum
unblended endpoint error. The mapping hash binds the explicit opt-in.

Transporting rotation does not cure an unstable elbow position: keep the
shoulder-to-hand direction away from a collinear pole during the **whole** arc.
When lowering a wide arm, an authored forward intermediate target can maintain
clearance and a readable curved path. Inspect actual half-frame angle changes
and nearby sleeve/hand images; speeds locate poses, not a universal naturalness
pass. Preserve the old route and failed pole probes for comparison.

Preserve flight when the source contains it. Compare native source timing with
retimed variants; interpolation can create shoe penetration between integer
samples. A fast original fragment can work as a playful chase without being
accepted as realistic walking. A good sole result can still coexist with a
skirt through the floor: inspect the **whole opaque costume** during braking.
Reduce or redesign the pose instead of hiding clothing or moving the floor.

## Save a lightweight stage and inspect the saved chain

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/stage_body_preview.py -- --blend FINGERS.blend --mapping STAGING_ROLE.json --output NEW_STAGE.blend --profile NEW_PREVIEW.json --report NEW_STAGE.json
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/inspect_body_remix.py -- --case CASE.json --report NEW_READBACK.json --substeps 2
```

Staging saves a separate simple floor/grid and fitted full-body camera, retaining
tagged owned story props and noncamera narrative markers. Preview settings and
key/face frames remain external. A saved F12 stage and the flat diagnostic
renderer are distinct render paths. Neither establishes source-shader parity.
The preview renderer supports object/bone-following views for feet and face;
retain a full-body view so a close-up cannot conceal the important landing.

`CASE.json` schema 1 binds paths `scene`, `body`, `fingers`, `remix_report`,
`finger_report`, `stage_report`, `body_plan`, `mapping`, `remix_producer`.
Relative paths resolve beside the case. Inspect the actual output report:
geometry/constraint/action identity, declared weighted sole/contact samples,
root/wrist/hip ranges, and a whole-skin floor diagnostic. The latter includes
transparent geometry; identify the worst vertex's real material before judging
a visible violation. Technical checks do not subsume that diagnosis. Sampling
is bounded to 500000 bone-frames and 25000000 evaluated vertex-frames. It does
not prove continuous safety, all self-collision, friction or naturalness.

Use [selected character regions](character-region-surfaces.md) for additional
triangle-surface warnings and actually inspect affected poses. Nested arm/torso
regions and layered original clothing can produce warnings; record scope and
baseline rather than declaring every hit a new visible defect. Encode a usable
normal-rate preview, check complete decoding, and separately record whether a
human/visual-capable surface actually watched it continuously at normal speed.

## Rights and reusable scope

Keep source byte hashes, credits and all supplied conditions beside the local
case. Rendering only a permitted animation's node TRS does not grant rights to
its mesh, logo, target model or derived motion. The generic skill contains no
character mapping, model, animation asset, video or .blend. Preserve previous
character configurations without claiming a new cross-character verification.

The first new full-body case uses one adult rig with 1191 bones and a CC-BY
fragment. It exercises limited hinge calibration, source modification and the
specific two-step stop above. Consult [validation](validation.md) and the paired
local reports for actual pass/fail/unverified results; mathematical execution
does not establish appealing performance.
