# Continue from a provided rendering project and controllers

Use this route when the user has already generated controllers in a saved render
project. Preserve that file and an exact hash-bound snapshot. Do **not** regenerate
controllers or overwrite the user's baseline. Keep all model names, bone mappings,
motions, camera plans and source/license evidence outside this generic package.

## Inspect before animating

Record original model/controller armatures, original rest hierarchy, weighted
meshes, custom shapes, action/driver state, packed dependencies and actual
model-to-controller constraints. A visible Rigify/MMR control does not establish
skin deformation. On a working copy, separately probe FK arm, hand IK, finger and
torso controls, measure actual weighted skin response, restore each probe, and
check the saved baseline again. Preserve existing user constraints and drivers.

If instructions and actual constraints establish that specific bindings are
missing, the optional `bind_existing_controller.py` repairs **only** an explicit
one-to-one missing mapping in an unassembled backup. It adds nondeforming offset
helpers parented to existing observed control targets and original-model WORLD
copy-rotation constraints. It does not generate a rig or adjust the user's rest
pose, weights, controller lengths, drivers or existing constraints.

The external schema1 plan has exactly: `source_sha256`, `controller_object`,
`model_armature`, `mesh_object`, `existing_controller_bones`, `pairs`,
`maximum_baseline_skin_difference_m`, and `schema`. Each pair has `model_bone`
and `controller_bone`. Supply 1..128 unique pairs and a finite positive tolerance
no greater than 0.0001m. Use explicit actual names and a reviewed source hash.
File images must already be packed before relocating the source. This is not an
automatic universal rig repair: review applicable instructions and bone targets.

```text
blender --background --disable-autoexec --offline-mode --threads 1 --python scripts/bind_existing_controller.py -- --source PACKED_USER_COPY.blend --plan REVIEWED_MISSING_BINDINGS.json --output NEW_BOUND_COPY.blend --report NEW_BOUND_COPY.json
```

The producer checks original rest/geometry, all pre-existing original-model
constraints and evaluated baseline skin before saving. Its report explicitly
does **not** claim saved reopen or response success. Independently reopen the
saved file in a **fresh process**, repeat protected-data checks and dynamic
control probes, then test an actual action. Rotation-only copying preserves the
original model's joint spacing when generated controller lengths differ; full
position copying can visibly stretch or collapse fingers and limbs.

Set a helper EditBone's nonzero length **before** its matrix: assigning orientation
to a zero-length bone can lose the intended rest rotation. Orientation metrics
must use the shortest quaternion distance, treating q and -q as equivalent.
`existing_controller_plan.shortest_quaternion_angle_degrees` refuses zero or
nonfinite inputs; a raw 359-degree difference can mean less than one degree.

## Adapt recorded actions and import cameras

Keep captured source data, calibration and license/credit outside the package.
Fit to the original deform skeleton first. Transfer reviewed body matrices and
calibrated limb rotations to existing FK controls while retaining their native
local translations/scales; do not force every native controller to captured world
joint positions. Preserve captured root/wrist motion and clearly label authored
finger/gaze additions. Validate actual original-model joints, not controls alone.

When joining two clips, blend coherent **local bone basis** TRS and evaluate the
source hierarchy before transferring the resulting pose. Independently blending
each joint's world position/matrix can make a hierarchy inconsistent at the join.
Check the complete overlap and first/last poses after saving, then view the action.

`import_existing_controller_action.py` accepts an already fitted, reviewed
target NPZ plus an external schema1 plan; it is not an arbitrary BVH/FBX importer.
The NPZ contains only `frames` (1..N), ordered Unicode `names`, and finite affine
`worlds` shaped N×mapped-bones×4×4. The plan contains exactly `schema`,
`source_sha256`, `goals_sha256`, `controller_object`, `model_armature`, `mapping`,
`fk_switches`, `fps`, `frames`, `maximum_position_difference_m` and
`maximum_orientation_difference_degrees`. Each mapping names `model_bone`,
`controller_bone`, keyed `control`, calibration `helper`, and explicit Boolean
`preserve_local_translation_scale`. An FK switch has `bone`, `property`, `value`.
Keep the actual names/targets, captured license, fitting and modification evidence
outside the skill. It refuses existing controller actions and assembled physics;
use a preserved unanimated controller copy before that stage.

The controller and original model must be **different armature objects**. The
model must have real positive-weight skin linked to that armature; an empty rig
or merely matching bone matrices is insufficient. Existing actions/NLA on either
armature are refused so imported controls do not silently combine with a prior
original-model action. Native saved-fixture regressions cover these refusals and
a valid distinct weighted target.

```text
blender --background --disable-autoexec --offline-mode --threads 1 --python scripts/import_existing_controller_action.py -- --source REVIEWED_BOUND_COPY.blend --plan ROLE_ACTION_PLAN.json --goals REVIEWED_FITTED_TARGETS.npz --output NEW_CONTROLLER_ACTION.blend --report NEW_CONTROLLER_ACTION.json
```

It retains native limb translation/scale when specified, keys coherent mapped FK
controls in hierarchy order, avoids quaternion sign flips, and checks every
integer original-model position/orientation against explicit bounded tolerances
before saving. Original rest/skin identity must remain. Saved-file reopen and
between-frame/visual acceptance remain separate. Choose tolerances from the
story and model; the permitted upper bounds are not recommended quality targets.

Import an independent reviewed camera asset or camera motion and retain its
provenance. A locally authored camera asset is not an external camera-library
test. Follow actual root travel, inspect bow/reach silhouettes and avoid allowing
foreground seats, sleeves or hair to obscure the story's decisive action.

## Assemble and preview physics

Check actual MMD rigid bodies/joints first. A rendering-only project may contain
neither even though its original PMX has both. Importing known matching original
physics requires source identity and correspondence checks; matching names alone
does not establish matching model geometry, rest pose or weights. Preserve the
provided controller and model instead of importing a second animated character.

Follow matching [MMD Tools instructions](mmd-plugins.md). A rigid-body world can
exist while the MMD root remains unbuilt; distinguish world allocation, actual
assembly and actual cache bake. Record solver settings before/after each operation.
MMD Build/cache baking is separate from MMR world update, assign/remove, and
physics bake-to-bones; the last can alter actions and constraints.

Use enough explicit preroll, shift **all** involved action tracks and camera cuts
together, and keep cache range separate from the visible range. Save a built,
unbaked checkpoint before baking, then save the baked file and exit the producer.
For complex physics, verify that saved result in a **new Blender process**. One
local producer saved a valid file then crashed during same-process reload in
rigid-body constraint cleanup. Preserve that nonzero producer exit and crash
evidence even if a fresh process verifies the artifact. Do not call that a root
cause repair or uninterrupted producer success.

For an **already assembled** reviewed existing-controller checkpoint, the narrow
`cache_existing_physics.py` route supports separate `bake` and `verify` modes.
Its exact external schema1 plan contains `schema`, `source_sha256`, `module`,
`addon_version`, `instructions_url`, `controller_object`, `model_armature`,
`controller_bones`, `rigid_bodies` and `frames`. Use the reviewed installed MMD
Tools4.5.14 module and the manual URL above; all counts/ranges must match the
actual scene. It refuses already-baked producer inputs and never clears a cache,
retunes the world, builds controllers, or invokes MMR operations.

```text
blender --background --disable-autoexec --offline-mode --threads 1 --python scripts/cache_existing_physics.py -- --mode bake --source ASSEMBLED_UNBAKED.blend --plan BAKE_PLAN.json --output NEW_BAKED.blend --report NEW_PRODUCER.json
blender --background --disable-autoexec --offline-mode --threads 1 --python scripts/cache_existing_physics.py -- --mode verify --source NEW_BAKED.blend --plan VERIFY_PLAN.json --report NEW_FRESH_CHECK.json
```

Create the verify plan with the **actual newly saved output hash**, retain the
producer/verify reports and exit codes, and compare their populations/settings.
Each invocation opens only one physical scene. The narrow new route avoids the
same-process reload performed by the older `mmd_physics.py` bake command; use the
separate route for these existing-controller projects. Neither route proves
normal-speed naturalness or exact MMD physics.

Render a low-cost complete preview; inspect normal-speed timing, silhouette,
support, hair/skirt/arm intersections and readable intent. Correct obvious large
penetrations on a new unbaked version, clear/rebuild cache through documented
operations, then rebake and preview again. Minor unobvious intersections may be
accepted at the user's chosen quality target. Camera-only changes can reuse an
unchanged verified cache after checking representative cached transforms; do
not describe camera changes as a new physical bake. If no large correction was
made, report that the correction/rebake cycle was **not** exercised.

## Preserve the saved look in bounded renders

`render_cached_project.py` renders a saved Cycles scene using its existing
materials, lights, compositor and marker cameras. It sets bounded CPU render
settings, leaves the input file unchanged, hashes every PNG and resumes only
matching producer/source/settings. It refuses silently replacing an unrecorded
frame. Use the shared execution lock and a fresh process for each batch.

```text
blender --background --disable-autoexec --offline-mode --threads 1 --python scripts/render_cached_project.py -- --source REVIEWED_BAKED_PROJECT.blend --output NEW_FRAMES --start 31 --end 391 --width 640 --height 360 --samples 4 --batch-frames 90 --budget-seconds 240 --require-cache
```

The example numbers are a bounded illustration, not a character configuration.
`progress.json` records actual completed frames/camera/hash, FPS and `complete`;
an interrupted batch is not a complete movie. Require every intended frame and
matching hashes before encoding. Encode, probe and fully decode the final video,
then separately view the whole film at normal speed. Integer transform checks,
still inspection, successful decoding and actual continuous viewing are different
evidence. Preserve every unavailable or failed acceptance item.

## Evidence boundary of the local existing-controller trial

One user-provided rig needed 46 missing arm/leg/finger bindings; its 724 existing
controller bones and five existing body bindings were retained. Four dynamic
probes confirmed response. Two permitted captured clips were joined through local
TRS and transferred over 361 integer frames; maximum original-joint position
difference was about0.293mm and shortest rotation difference about1.665degrees.
These are one-model technical checks, not cross-character or normal-speed proof.
Original physical data (933 bodies/1615 joints), plus one owned floor, baked and
reopened in a fresh process. Integer shoe-floor penetration peaked around4.4mm;
half-frame, force contacts, sliding and all body-pair penetration were not thereby
accepted. Controller generation itself was not rerun or repaired.
