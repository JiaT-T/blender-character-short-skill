# Bounded geometric sphere grips

Use this optional route for an authorized original weighted hand and a simple
spherical prop. It checks actual finger surfaces, a supported prop and saved
motion; it does not solve arbitrary-object retargeting, mass, friction or force
closure. Keep model/mesh data, calibrated frames, bone names, parameter poses,
motion and material choices outside the generic skill.

First read [hand controls](hand-controls.md). Confirm actual deformation and
visually identify the intended pads. Bone-weight regions alone cannot identify
anatomical palm polarity or distinguish a pad from a nail/back surface.

## Fit, then inspect a path

The external fit spec supplies `side`, `hand_frame_from_wrist`, `groups`,
`contacts`, a bounded `center_grid`/`center_bounds`, `radius_range_m`, clearance
and contact-gap limits, `opposition_pairs` and `max_radial_dot`. Each group has
an `id`, known `[joint_id, axis_id]` channels and candidate fractions. Each
contact has explicit existing `bones` and `min_weight`. The frame transforms
wrist coordinates into the calibrated hand frame: `H_world = W_world *
inverse(hand_frame_from_wrist)`. Confirm its orientation from actual skin.

```text
blender --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python scripts/fit_sphere_grasp.py -- \
  --blend BASELINE.blend --profile BOUND_HAND_PROFILE.json \
  --spec FIT_SPEC.json --report NEW_FIT.json
```

The fitter evaluates original skin, nearest complete triangles and exterior
normals. It seeks bounded sphere clearance and contact regions on opposing sides,
not zero bone-to-prop distance. It refuses more than 256 pose combinations or
512 center combinations before allocating the Cartesian grid, and checks the
shared bone/object/vertex work budget. Time bounds stop between candidate poses.
Read every static-candidate boolean; exit 0 only means the inspection finished.

A held pose can fit while its closing trajectory cuts through the sphere.
Inspect explicit intermediate parameters against the actual supported sphere:

```text
blender --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python scripts/probe_sphere_grasp_path.py -- \
  --blend BODY_PROP_BASE.blend --profile BOUND_HAND_PROFILE.json \
  --spec FIT_SPEC.json --body-report BODY_REPORT.json \
  --poses PARAMETER_POSES.json --report NEW_PATH_PROBE.json
```

`PARAMETER_POSES` supplies one `frame` and at most 256 `poses`, each with a label
and fractions for every configured group. This is a static parameter sweep,
not a continuous-path proof. Use it to find a small joint-order or clearance
detour, then audit the actual saved motion. Contact fit alone does not choose
natural poses for noncontact fingers: inspect and relax those independently,
then repeat sphere and same-hand checks.

## Prepare a supported scene and finger layer

When a new controlled gesture is needed, `bake_sphere_grasp_scene.py` accepts an
external scene plan and passing fit. It creates a **new** bounded clip, using one
source reference pose, three original FK arm controls, a sphere and fixed-anchor
cord. The rest of the armature is held at the reference pose; the old armature
action is replaced only in the copy. This is new acting, not preservation of the
source story. Original geometry, deform bones, weights and morph data remain.
Existing noncharacter stage meshes/curves are hidden in this study copy.

The plan supplies integer `schema:1`, `frames`, `fps`, `reference_frame`, `side`,
`arm_bones.arm/elbow/wrist`, the calibrated frame, metre approach/lift vectors,
a unit inspection axis and degree limit, normalized `approach_keys`/`lift_keys`,
ordered `close_frames`/`held_frames`/`release_frames`, prop/cord names and sizes,
colours, fit SHA256 and explicit metric tolerances. Before scene load/allocation,
it validates finite data, rigid frame, ordered timing and 2..32 cord segments.
It supports 2..120 frames, integer effective fps, a unit world rig, and a simple
unconstrained original arm chain without active NLA. Unreachable required wrist
targets fail instead of being silently clamped. It uses joint-head lengths,
not MMD display-tail lengths.

```text
blender --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python scripts/bake_sphere_grasp_scene.py -- \
  --blend SOURCE_BODY.blend --plan SCENE_PLAN.json --fit NEW_FIT.json \
  --output NEW_BODY_PROP_BASE.blend --report NEW_BODY_REPORT.json
```

The sphere is stationary and supported before/after the hold, follows the actual
wrist during the declared hold, and is sampled at half frames. The cord's
fixed endpoint, sphere attachment and length are separately inspectable. It is
an analytic kinematic support, not a dynamic rope simulation. Keep another
support's actual geometry and collision checks if choosing a different setup.

Apply `bake_hand_controls.py` to that new baseline using an external gesture.
Keep the sphere/wrist relationship, release support and full transition together.
A faster local turn may require denser keys or more time; a successful integer
pose is insufficient when the half-frame approximation exceeds its declared
tolerance. Do not change a failed threshold merely to accept a pose.

## Reopen and measure

```text
blender --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python scripts/audit_sphere_grasp.py -- \
  --blend GRASP.blend --source NEW_BODY_PROP_BASE.blend \
  --profile BOUND_HAND_PROFILE.json --motion GESTURE.json \
  --spec FIT_SPEC.json --fit NEW_FIT.json --plan SCENE_PLAN.json \
  --body-report NEW_BODY_REPORT.json --bake-report HAND_BAKE.json \
  --report NEW_GRASP_AUDIT.json --snapshots NEW_PRIVATE_SKIN.npz
```

This fresh process checks integer/half frames, source/candidate hashes, preserved
nonfinger skin, protected worlds and morphs, original geometry identity, requested
finger rotations, wrist targets, actual primitive radius, full skinned-character
sphere/cord surface intersections, selected same-hand region pairs, held pad gaps
and opposing directions. Barycentric material points track actual skin against
the prop to detect sliding; parenting or matching a bone alone cannot establish
contact. It measures supported rest states, real lift, cord length and endpoints.
Read all booleans and individual tolerances; exit 0 can contain failed checks.

Cord mesh topology can change from taut to slack. Snapshots retain each evaluated
cord frame's own vertices and triangles rather than assuming a fixed index cache.
All skin snapshots are local derived assets, excluded from the generic package.

Actually view matched source-texture and diagnostic views at entry, hold, lift,
return and release. Include the complete wrist/forearm when a cropped cuff looks
cut. Low-cost CPU diffuse-image adapters preserve only specified source images/UV,
not original shader, normal, lighting, bloom or whole-scene equivalence. Then
review normal-speed continuous playback. Decode success, surface samples and
contact-sheet viewing remain separate from continuous naturalness acceptance.

The tests `test_hand_control_plan.py` run in ordinary Python; the 12 geometry and
allocation/preflight tests in `test_sphere_grasp_math.py` require Blender's Python.
Neither establishes artistic quality, untested time intervals, closed-volume
containment or dynamics/friction. Reject and retain failed motion evidence.
