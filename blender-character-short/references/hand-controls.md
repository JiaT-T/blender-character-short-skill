# Hand controls and contact

## Bounded multi-axis FK clips

The optional original-rig route separates character-specific wrist/joint names,
calibrated local axes and gesture timing from generic code. It requires one
armature, unconstrained/undriven finger rotations and unchanged evaluated
topology. It preserves bones, weights and morphs; it does not reconstruct hands,
solve tendons or certify anatomical limits.

An external unbound profile has integer `schema: 1`, nonempty `id`, explicit
`hands` mapping `left`/`right` to wrist names, and `joints`. Each joint supplies
unique `id`, `bone`, configured `side`, nonreserved `digit`,
`max_total_degrees` and one to three ordered `axes`. Each axis supplies unique
`id`, calibrated unit `axis_local: [x,y,z]` and `limit_degrees`. These are
author-supplied limits, not universal safe angles. Thumb flexion and opposition
can use separate ordered axes; visually calibrate their directions.

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/probe_hand_controls.py -- \
  --blend BASELINE.blend --profile UNBOUND_PROFILE.json --report AXIS_REPORT.json
```

Read actual per-axis skin response and the exact inherited descendant set.
Inspect evaluated pose views before copying the report's `binding_sha256` into
a new bound profile. This identity covers mapped rest hierarchy and original
hand skin/weights, including its transform relative to the armature. Re-probe a
changed rig instead of forcing an old identity.

Motion JSON has integer `schema: 1`, `frames: [first,last]`, integer `fps`, and
`channels`. Each channel names a known `joint`/`axis` and ordered `keys` of
`[integer_frame, fraction_0_to_1]`, including both clip boundaries. Missing axes
remain zero. The target is a quintic ease with holds. Stagger digits/joints to
serve intent, then inspect their combined motion.

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/bake_hand_controls.py -- \
  --blend BASELINE.blend --profile BOUND_PROFILE.json --motion MOTION.json \
  --output NEW_CLIP.blend --report NEW_BAKE.json

blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python scripts/audit_hand_controls.py -- \
  --blend NEW_CLIP.blend --source BASELINE.blend --profile BOUND_PROFILE.json \
  --motion MOTION.json --bake-report NEW_BAKE.json --report NEW_AUDIT.json \
  --snapshots NEW_LOCAL_SKIN.npz --substeps 2 --max-subframe-error-degrees .25
```

Choose new output paths. The source fps/window must contain the clip. The saved
scene's playback range becomes that bounded clip, not the complete source story.
Full-story composition and contact need separate validation. The writer
copies the armature action and adds local quaternion deltas to source poses at
each integer frame, with linear component interpolation. Selected local
translation/scale, original rest bones, skin and morph data stay protected.
The guarantee covers the declared window, not selected finger curves outside it.
Source/candidate/profile/motion/producer hashes bind the independent reopen
audit; never patch evidence to fit an edited producer.

Reopening compares nonselected bone/object worlds, morph values, actual
nonfinger skin and requested rotations. Only selected bones and their exact
descendant closure inherit permitted world changes, plus identified
bone-parented attachments. Wrists, arms and the remaining body stay protected.
Another source body performance needs its own comparison and binding check.

Read **all audit booleans**: exit 0 means inspection finished and can include
failed acceptance checks. Half-frame checks measure approximation to the target;
discrete samples do not prove the whole continuous interval. A quintic target
does not imply the saved animation is continuously differentiable. The exported
evaluated geometry cache is a local derived asset, outside the installable skill.

Limits: 240 clip frames, 64 joints, 192 channels, 2,048 rig bones, 500,000
skinned vertices, 300,000 bone/object-frame comparisons and 20 million
vertex-frame samples. Start small; actual surface cost still varies by rig.
When sharing a host with rendering work, use a single low-priority thread for CPU work; apply the [render device policy](render-devices.md) to 3D rendering. Use modest resource bounds
and assess resources before any small diagnostic render.

Review front/back/edge or oblique views, then complete normal-speed playback.
Check thumb opposition, knuckle creases, silhouette, tension, easing and release.
If a cropped wrist looks cut or stretched, include actual forearm-weighted skin
in matched source/candidate views before diagnosing a rig tear; a selection
boundary can hide the connecting surface. Inspect full sleeve context separately.
Digit-colour geometry crops do not establish original shading or full-body
performance. Surface tests exclude triangles sharing original vertices and cover
only selected wrist/finger region pairs within each hand: no cross-hand test,
closed-volume, intrafinger self-collision, sleeve clearance, prop grip/friction
or naturalness certificate. Source timing must also be checked at its effective
`render.fps / render.fps_base`; the motion input's integer `fps` is nominal.

## Inventory and contact

Inventory the actual weighted rig before writing finger acting. A familiar finger
name or a long bone chain does not establish separately deforming fingers. Some
chibi gloves have one thumb group and one mitten group even when the skeleton
contains many unweighted finger descendants.

```text
blender --background --factory-startup --python-exit-code 1 \
  --python scripts/inspect_hand_controls.py -- \
  --blend BASELINE.blend --character CHARACTER.json --output HAND_INVENTORY.json
```

The character input supplies existing `bones.left_wrist` and `bones.right_wrist`.
The read-only report lists original descendant hierarchy, rest matrices, pose
constraints and assignments whose weights exceed `.01` (configurable with
`--min-weight`). It hashes the scene before/after and never saves it. Counts use
original mesh assignments, not evaluated pose response. Indirect or constrained
controls need inspection even when their own group has no counted vertices.

Keep any selected joint names in the external character `bones` map and its
local XYZ degree rotations in existing story `poses[].rotations`. Do not add
Nanami names, fixed hand geometry or a role-specific grasp table to generic code.
The builder converts these local Euler rotations to keyed quaternions. Derive
the intended bend in the inspected rest frame and confirm actual deformation in
matched views; copying a wrist/world axis into a finger's local Euler axis can
rotate the glove in the wrong direction.

Compare open, moderate and stronger static poses before animating. Preserve the
original deform bones and weights. Check the actual handle, shaft and nearby
guide surfaces, then test contact entry, the complete held range and release.
Recheck calibrated directional palm footprints after changing a glove pose.
A nonnegative directional gap and zero sampled triangle intersections do not
prove volume clearance, physical grip or convincing acting. Increasing clearance
can make a hand float. Keep the failed pose and diagnostic evidence when rejecting it.

For a controlled test, compare all other bone world transforms and every bone's
local translation/scale against the same source performance. A changed thumb's
unweighted children legitimately inherit its world rotation: record that exact
descendant set, verify its weights and compare its local rotations separately.
Do not exclude the whole hand, arm or body to obtain a passing regression.

The Nanami two-joint trial used 10 degrees at the thumb and 15 at the mitten
cluster, with existing 25 pose keys, delayed closure on arrival and reopening
after adjustment. All 480 nonfinger world transforms were unchanged; 156 held
frames had zero detected hand/handle or named-control surface intersections,
and the directional footprint passed unchanged thresholds. Three native frames
and a matched open/curl pair were actually viewed. This is a local input trial,
not a complete preview, continuous motion acceptance, universal angle preset,
five-finger grasp system or cross-character test.

## Sampling coverage in the current auditor

The report counts integer and subframe samples separately. With `--substeps 1`,
the subframe check is `null` and listed in `unexecuted_checks`; a zero recorded
subframe error does not mean a half-frame test ran. `requested_sampling_checks_pass`
covers executed checks only, while the broader `technical_scope_pass` remains
false when a check is unexecuted. Inspect both coverage and individual checks.
No technical field establishes normal-speed continuous viewing.
# Full-clip audits within existing work limits

`audit_hand_controls.py --window FIRST LAST` audits an explicit interval inside the original motion without changing the motion plan, bake report or source/candidate hashes. Bone/object/vertex work limits still apply to each audit; do not raise them to fit a long half-frame inspection. Reports and evaluated-skin cache metadata declare the original motion interval, actual sampling window and whether it covers the entire motion. A passing window is not a full-clip pass.

For a240-frame clip on a1191-bone rig, integer+half sampling can use windows1..121 and121..240. Verify identical inputs/producer/binding, exact coverage of all240integer and239half frames, matching overlap121 and every check boolean before combining the results. Keep separate reports/caches, original failures and explicit unexecuted checks. This is selected hand-surface/pose validation, not a complete costume collision or normal-speed acting review.

