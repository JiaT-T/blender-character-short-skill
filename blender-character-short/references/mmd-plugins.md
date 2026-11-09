> v45 update: the user supplied the direct original-MMD → Extras/Finger options → Build a controller workflow. It has one-model background generation and real-skin evidence when the external bone-name preset matches. See [current production](current-production.md). Earlier metarig-branch failures and denied attempts below remain historical; they are not blanket failures of the newly tested direct route.

# MMD Tools and MikuMikuRig: verified setup, limited production evidence

An addon used through project-local `sys.path` imports is not necessarily installed
or enabled in the user's Blender. A `.blend` file does not install its addons.
Record binary version, module identity, installation location and fresh-start
operator/panel registration separately from actual feature tests. Preserve
preferences and unsaved interactive work. Installation authorization does not
authorize unrelated downloads, model uploads or security changes.

The local development environment verified Blender4.5.15 LTS with MMD Tools4.5.14,
MikuMikuRig4.5-3.86 and bundled Rigify. Official-source package hashes and preference
backup belong in the external installation report. Do not bundle addon binaries,
third-party source trees or preferences with this skill.

## Original PMX physics

Read the linked MMD Tools manual and the installed version's interface/operator
definitions before acting. If instructions or original data are unavailable,
defer this portion. Do not invent physics parameters or install another tool to
hide a failed route.

1. Inspect the original PMX for rigid bodies and joints. A previously imported
   baseline may have deliberately omitted `PHYSICS`. Reimport original physics
   into a new local scene with the same verified model scale and import options;
   preserve original files. Check counts and original rest/skin identity.
2. In a separate saved copy, use Scene Setup / Rigid Body Physics / Update World
   when needed, then Model Setup / Assembly / Physics. Installed4.5.14 operators
   are `mmd_tools.rigid_body_world_update` and `mmd_tools.build_rig`.
3. Retain original author physics data and plugin defaults for the first test.
   The tested world update selected6 substeps and10 solver iterations. This is an
   observed plugin default, not a universal recommendation for every model.
4. Choose a bounded frame/cache range and Object mode, then the documented Bake
   operation (`mmd_tools.ptcache_rigid_body_bake`). Verify the cache is actually
   baked. Operator return alone is insufficient.
5. Save, reopen and verify cache state and actual skin. Inspect hair, cloth and
   collisions in motion. Keep bake success, finite bounds, static visual samples
   and normal-speed acceptance separate.

For a recorded-action integration, verify identical target rest/skin data and
copied action poses before assembly. Keep any settling pre-roll separate from
the displayed motion interval. Do not change recorded body performance merely
to obtain a passing cache statistic. A static settling test alone does not
validate animated physics.

Original author data can expand into many additional noncollision constraints;
the local933-body model produced16748 world constraints. Use one low-priority
CPU job and review resources before larger tests. The local round baked and
reopened a60-frame settling test and a150-frame recorded-walk test including
30frames of settling. Sampled native views showed hair changes without a gross
explosion in those samples. This is one-model evidence; collision quality,
continuous stability/naturalness and MMD-equivalent simulation are not certified.

Sources: [MMD Tools linked manual](https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual),
[official physics limitations](https://github.com/MMD-Blender/blender_mmd_tools#rigid-body-physics-limitations).
In this environment the manual web fetch returned402; the parent supplied its
steps and installed official UI/operator source was checked against them. Do not
claim the complete web manual was retrieved or exact MMD physical equivalence.

## Reusable isolated preparation and bake commands

`mmd_physics.py` implements only the reviewed4.5.14 operations above. It requires
an enabled declared MMD Tools module and a new output/report for each stage.
It never installs addons or fetches instructions. The caller must first review
matching instructions, source rights and actual model physics data.

Preparation takes an original unassembled physics-model scene and a recorded
motion scene on identical original rest/skin/root data. The external schema1
plan declares `module`, `addon_version`, `instructions_url`, both
`model_sha256`/`motion_sha256`, `pre_roll_frames`, explicit original `mute_ik`
entries (`bone` and `constraint`), sorted source `probe_frames` and boolean
`pack_resources`. Only the declared IK entries are muted in the new copy, and
sampled transferred original-bone poses must match before assembly. Recorded
motion lives on the original armature action; synchronized extra-object or
separate facial actions are not transferred by this narrow route.

```text
blender --background --disable-autoexec --offline-mode --python scripts/mmd_physics.py -- --mode prepare --model <original-physics-import.blend> --motion <recorded-action.blend> --plan <prepare-plan.json> --output <new-ready.blend> --report <prepare-report.json>
```

Bake uses a separate schema1 plan with `module`, `addon_version`,
`instructions_url`, prepared `source_sha256`, exact cache `frames` and sorted
`probe_frames`. It checks every cached integer rigid-body transform for finite
values, checks actual skin at the declared probes, saves and reopens the result,
and requires the saved baked cache/range to survive. Bounds are480cache frames,
1024rigid bodies,4096original joints,50000assembled constraints and500000rigid
body-frames; preparation also bounds target bone-frame work. These are practical
lightweight limits, not an assurance that every allowed model is stable.

```text
blender --background --disable-autoexec --offline-mode --python scripts/mmd_physics.py -- --mode bake --blend <new-ready.blend> --plan <bake-plan.json> --output <new-baked.blend> --report <bake-report.json>
```

The local recorded bow/goodbye sequence used349motion frames plus30settling
frames,933original bodies and16748assembled constraints. Bake and cache reopen
passed; full motion quality still requires actual rendered review. Never replace
that review with finite transforms or cache flags. After adding scenery or face
cues, recheck body animation/cache integrity and actual saved frames.

## Optional passive story floor before baking

A visible stage plane is not automatically a physics collider. If the actual
opaque costume crosses it, preserve a no-ground simulation as a control before
testing one additional passive floor in an unbaked backup. Do not hide clothing
or move the visible floor merely to manufacture clearance.

Review matching authoritative instructions first. In the tested installed
Blender4.5.15 API help, `bpy.ops.rigidbody.object_add.__doc__` documents the
active-object operation; the `RigidBodyObject.type` RNA enum describes PASSIVE
as animation-controlled, and its `collision_shape` BOX enum explicitly includes
ground planes. These local official operator/property instructions were read;
the web manual fetch returned402 and was not retrieved by another route. If
matching usage cannot be established in another environment, defer this step.

`add_passive_ground.py` supports only one original character, a Z-up unbaked
world, and a new static BOX in a separate scene copy. Its external schema1 plan
has `source_sha256`, `instructions_review_sha256`, exact integer-list
`blender_version`, `center_xy`, `size_xy`, `top_z` and `thickness`. Review actual
scale and floor extent; these dimensions are story geometry, not universal
physical settings. The caller's instruction-review digest is evidence linkage,
not automatic verification of an arbitrary text file's authority.

```text
blender --background --disable-autoexec --offline-mode --python scripts/add_passive_ground.py -- --blend PREPARED_UNBAKED.blend --plan GROUND_PLAN.json --output NEW_GROUND_READY.blend --report NEW_GROUND_READY.json
```

The tool applies the new box's scale, adds PASSIVE and BOX using the reviewed
native interface, retains default friction/restitution/margin settings, checks
membership and geometry/default-margin bounds, then saves and reopens. Original
rigid-body properties, solver/gravity/cache range, character action and original
rest/skin must remain. Existing owned floors or baked inputs are refused;
1024body/480frame/500000body-frame limits remain. There is no addon patch,
controller generation, automatic cache freeing or security-setting change.

Rebuild the bake plan against the **new** prepared scene hash. Align the later
visible floor with the actual box top and distinguish original model bodies
from the added collider. In one local270frame dance test this was933original
bodies plus one owned floor; solver defaults remained6substeps/10iterations.
Controlled motion was preserved, while the worst sampled opaque-costume vertex
height below the display plane reduced from about65.8mm without the floor to
about2.84mm with it. The old virtual-tail/foot-reference version was about114mm.
These are one-model integer-vertex diagnostics plus actual matched still views,
not complete cloth collision, exact MMD simulation or normal-speed acceptance.

## MikuMikuRig controller boundary

Resolve which MMR project/version the user means. The tested package was
[XiaoFFGe/MikuMikuRig4.5-3.86](https://github.com/XiaoFFGe/MikuMikuRig/releases/tag/MikuMikuRig-4.5-3.86),
not an assumed original0.56 or a newer incompatible Blender build. The author's
README links the [controller tutorial](https://www.bilibili.com/opus/1167803398842482693).
Read it and the matching installed settings before testing a backup.

The tutorial describes original-bone mapping through an external JSON preset,
metarig-only generation for alignment, then generating controllers from the
selected metarig. Keep role-specific names and mapping outside the skill; do not
rename the user's original model to force a default preset. Verify metarig
alignment, generated controls, original deformation, pose transitions and saved
reopen separately. A registered `object.mmr_rig` operator proves installation,
not a usable character controller.

Local metarig-only generation completed with54 mapped bones on a backup. Full
generation from that metarig then raised `ReferenceError: StructRNA of type
Object has been removed` in installed `operators/RIG.py:1683` during cleanup.
No usable completed controller checkpoint was saved. A proposed alternate
generation attempt was rejected by automatic approval review because its
documented applicability was not established under the user's instruction.
That action did not execute; no retry, installed-code patch or security workaround
was used. Full MMR controller generation remains **blocked/unvalidated** pending
appropriate guidance or a documented remedy. Do not mark it passed because
Rigify objects briefly existed before the exception.

Later, the user supplied an original rendering project containing already
generated controllers. That changes the available input, not the result of the
earlier generation attempt. See [existing controller projects](existing-controller-projects.md)
for inspection, explicit missing-binding repair, captured FK action import and
the separate MMD Tools physics route. No generation operator was rerun. Keep
fresh-process physics verification separate from producer exit: same-process
reload after saving a baked world crashed in constraint cleanup in this trial.


## Historical controller-generation TODO (superseded for the qualified direct route)

MMR controller generation itself is deferred until the user provides guidance.
Use the supplied, already-generated controller project and the
[existing-controller workflow](existing-controller-projects.md); do not rerun
generation to address a missing binding or to prepare a new scene. Historical
failed generation evidence above remains historical.
