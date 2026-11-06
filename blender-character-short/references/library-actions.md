# Recorded actions before authored body animation

Choose a readable story beat, then find a permitted captured performance that can
carry it. Inspect the source and its mapped result before committing to the
story. Preserve original motion, attribution, item-specific terms and every crop,
calibration, resample and retarget change. Keep all supplied/derived motion and
character mappings outside this skill. A library label does not establish usable
motion or correct retargeting.

Use authored keys for missing eyes, expressions, finger posing, prop contact and
small shot-specific corrections. Identify those additions separately. Do not
replace the captured body performance with a long authored FK sequence and call
the result a library-motion test.

## Local BVH source adapter

`sample_bvh_motion.py` runs inside Blender with its bundled `io_anim_bvh` enabled.
It imports a reviewed local BVH and writes a **new** directory containing:

- skeleton-only `motion.glb`, with LINEAR node TRS and no mesh or textures;
- `source-provenance.json`, retaining attribution, restrictions and changes;
- `native-witness.json`, evaluated source bone world matrices at every sample;
- `source-scene.blend`, a source skeleton checkpoint for independent inspection.

No network, plugin installation, character deformation or legal determination
occurs. Use an isolated background process, `--disable-autoexec`, one writer and
the shared execution lock. Record actual addon startup: a factory startup can
discard enabled addon preferences, while a normal startup can load installed
addons. Do not silently treat those modes as equivalent.

The sampling-plan schema is deliberately explicit:

```json
{
  "schema": 1,
  "source_sha256": "<reviewed lowercase SHA256>",
  "frames": [1, 120, 1],
  "fps": 30,
  "scale": 0.01,
  "axes": {"forward": "-Z", "up": "Y"},
  "reference": {"mode": "first-frame", "pelvis": "Hips"},
  "rights": {
    "source": "<original source URL>",
    "credit": "<required attribution>",
    "license": "<reviewed item license>",
    "modifications": "<crop and other changes>",
    "restrictions": "<all item-specific restrictions>"
  }
}
```

Frame indices here are **1-based imported BVH frames**, inclusive first/last,
followed by step. Store original raw crop indices separately. At most240 output
samples,128 bones,500000 imported bone-frames and1000000 input channel values are
allowed. Source files are bounded at16MB. The adapter refuses a sample cadence
that changes the supplied BVH tempo beyond1e-6seconds/frame rounding tolerance.
It standardizes the sampled output to the declared integer fps and records that
normalization. This is separate from deliberate later performance retiming.

Choose calibration from the actual source:

- `bind-rebased`: use a genuinely anatomical BVH bind pose, translated to the
  first captured pelvis position. Captured root displacement remains present.
- `first-frame`: use the first sampled captured pose as calibration. This handles
  BVH files whose unrotated joint offsets do not form an anatomical T-pose. Choose
  a usable neutral beginning; this calibration makes initial body rotation the
  target's neutral reference. Do not assume it preserves an arbitrary initial
  torso lean.
- `captured-horizontal`: provide an additional integer `frame` in `reference`.
  Use a separately inspected captured neutral/calibration pose even when the
  desired excerpt begins later in an active performance. Its pose and height
  remain the reference, while its horizontal position is moved to the first
  sampled pelvis. This keeps the cropped first pose's lean and vertical
  displacement instead of silently resetting them. The calibration frame may
  lie outside the excerpt, but must lie inside the original bounded BVH.

For example, an external reference can be
`{"mode":"captured-horizontal","pelvis":"Hips","frame":1}` while the
sampled `frames` start later. Inspect that calibration, the active first/last
pose and actual foot heights; a quiet interval or frame number alone does not
establish a neutral pose. Derive the source-facing basis from the exported
reference skeleton for this mode, not from an arbitrarily turned active first
frame. `native-witness.json` also records `reference_world_witness`; independently
decoded default skeleton worlds must match it in addition to the animated
sample comparisons. Original modes keep their earlier calibration behavior.

```text
blender --background --disable-autoexec --offline-mode --python scripts/sample_bvh_motion.py -- --source <motion.bvh> --plan <sampling-plan.json> --output <new-source-directory>
python scripts/convert_glb_motion.py --source <new-source-directory/motion.glb> --provenance <new-source-directory/source-provenance.json> --output <new-packed-directory>
```

Compare independently decoded GLB/packed worlds with the native witness at every
sample. Passing the shared converter's own comparison alone does not check the
BVH importer, coordinate conversion or source calibration. Keep first/last frame,
duration, joint names, forward/up direction and physical scale visible in the
review record.

## Character fit and wrists

Supply external original-bone mappings, unit-axis actor/armature transforms and
reviewed knee-hinge calibration to `fit_body_motion.py`. Preserve original rest,
weights and morph geometry. The proportional fit explicitly mutes declared leg
IK in its new copy; it must not be described as unchanged active IK.

For a clip with captured root displacement set `"root_motion": "recorded"` in the
body plan. The fit keeps captured hip movement under its configured basis and
scale. Do not run the legacy constant-speed travel stage afterward. The travel
function refuses this mode. Root preservation does not pin feet or establish
contact, and source/target proportions can still cause sliding or penetration.

For recorded-root fitting, `feet.<side>.contacts: []` explicitly means that
support timing has not been declared. It permits the measured FK preview, not
planting. Do not insert dummy intervals to satisfy legacy metadata. The legacy
travel route retains its required contact declarations; the planting function
also refuses empty intervals before it can report a material-contact result.

The optional `"wrist_rotation": "source-first-fitted"` calibrates each source
wrist against its first captured orientation and the target's first fitted wrist
orientation, then preserves the recorded world-rotation changes. The default
remains `original-relative`. Inspect palm facing, wrist bend, forearm twist,
fingers and sleeves in actual output. Source BVH without finger joints needs a
separately identified secondary finger layer, such as the weighted hand route.

```text
blender --background --disable-autoexec --offline-mode --python scripts/fit_body_motion.py -- --baseline <clean-import.blend> --character <external-character.json> --plan <external-body-plan.json> --output <new-fit.blend> --report <new-fit-report.json>
```

Use this source baseline directly for initial motion review. The older body
approach/remix tools are narrower optional adaptations and must not be applied
automatically to every newly captured clip. Keep source changes, target-rig
corrections, secondary acting and editorial cuts distinguishable in the record.

## Combining two captured actions

`compose_recorded_actions.py` takes an external schema1 plan with `fps`,
`transition_frames` and exactly two `clips`. Each clip declares a local scene,
its `sha256`, inclusive source `frames`, and nonempty `source`, `credit`,
`license`, `modifications` and `restrictions` strings. Preserve sources. Each
cut is bounded at240frames; overlap is2..48frames and at most half either cut.

The route requires identical original geometry/rest/weights/morph data,
constraints and static actor-root transforms. It refuses source physics, NLA,
extra animated objects and animated morphs; apply secondary face/scene acting
afterward. It samples the existing quaternion bone channels and mixes bone-local
translations, preserved near-unit scales and shortest-path quaternion SLERP with
quintic overlap weights. It rejects scale differences above1e-4; measured
float32-scale drift is retained rather than silently forced to1.

The output is reopened and every unmixed integer frame is compared against all
source bone worlds. This verifies preserved recorded poses outside the blend;
the blended interval still needs actual contact, costume and visual review.
The method does not invent replacement body poses or guarantee a natural join.

```text
blender --background --disable-autoexec --offline-mode --python scripts/compose_recorded_actions.py -- --plan <external-sequence.json> --output <new-sequence.blend> --report <new-sequence-report.json>
```

For an explicitly stationary sequence whose target shoes are slightly above or
below the intended floor, `ground_recorded_stance.py` can apply a separate
bounded root-height layer measured from actual weighted soles. Its external plan
declares schema1, input `source_sha256`, `mode: declared-stationary`, original
`root_bone`, character `height`, world `ground`, full `frames`, `fps`, two
`feet`/`deform_root` entries, `weight_threshold`, `maximum_correction_H` and
`maximum_step_H`. Only an unconstrained original ancestor-controller location is
changed. Recorded rotations, scales and horizontal movement remain; the report
records the exact global vertical change and actual integer sole error.

This is not a locomotion or per-foot planting solver. It puts the lowest
selected sole on the floor, not both feet independently, and does not pin
horizontal material points or establish forces/friction. Reject corrections or
steps outside declared bounds; do not use it to hide an unsuitable source or a
bad retarget. Apply before physics assembly/bake and inspect a separate copy.

### Matching different stationary stances

Two individually usable recorded actions can have different starting foot
spacing. A smooth quaternion blend can then slide both shoes across the floor.
Inspect actual weighted soles through the join, rather than declaring continuity
from upper-body transforms or an error-free decode.

The optional `match_recorded_stance.py` route is a narrowly declared stationary
asset adaptation. It matches the incoming ankle reference to an outgoing
reference through a short configured interval, then retains the incoming
captured ankle changes around that constant alignment. The original calibrated
knee plane is transported with the changed hip-to-ankle direction; the solver
does not pin the old knee point, which can cause unnecessary thigh roll near
extension. Original leg rotations are deliberately changed. Upper body, root,
hands, fingers, rest/skin/weights and other protected bone worlds must remain.

Its external schema1 plan declares `mode: declared-stationary-transition`,
`source_sha256`, full `frames`, `fps`, character `height`, `reference_frame`,
short `match_frames`, and two `limbs` with three original `bones`, calibrated
unit `axis_local` and `bend_sign`. Explicit bounds are `maximum_shift_H`,
`maximum_ankle_orientation_degrees`, `maximum_leg_rotation_degrees` and
`endpoint_tolerance_H`; `align_ankle_orientation` is a required boolean.
Full interval is at most480frames/500000bone-frames; the adaptation interval
is2..48frames. Unreachable or straight/ambiguous captured knee planes fail;
there is no guessed fallback. The saved output is reopened and all integer
endpoints and protected bone worlds are checked. A separate actual-sole and
visual check is still required, and a later bounded root-height pass may be
needed before physics. Do not relax a limit merely to manufacture a pass.

```text
blender --background --disable-autoexec --offline-mode --python scripts/match_recorded_stance.py -- --blend <stationary-sequence.blend> --plan <external-stance-plan.json> --output <new-matched.blend> --report <stance-report.json>
```

This does not synthesize a step, stabilize walking, establish friction/contact,
or certify naturalness. For a large stance change, choose a better source,
an actual recorded repositioning movement, or an explicitly reviewed cut.

## Preview and acceptance

`render_acting_preview.py` supports an explicit `video_view` from the configured
views. A following view can set `follow_axes` to three booleans; following only
horizontal axes keeps a constant camera height while the body bobs. Defaults
retain the earlier wide view and all-axis following behavior.

When recorded travel is on a bone while the outer model object stays still,
`stage_body_preview.py` can use an external `preview.follow_bone` and three
boolean `preview.follow_axes` (normally horizontal only). It measures sampled
skin bounds relative to that origin, configures body/side/feet following views,
and saves integer-frame camera-location keys in the staged copy. Original body
action and rest/skin identity must remain. Inspect actual framing separately;
sampled bounds do not prove every intervening frame fits. With no follow bone,
the earlier static stage and object-based diagnostic views remain.

For profiles whose jobs all declare explicit custom views, the renderer clears
the saved camera action in its unsaved working copy before applying those
views. Otherwise a saved following camera could interfere with a side/feet
diagnostic. Legacy wide jobs retain their previous camera-animation behavior.

Keep a complete uninterrupted full-body preview before cutting close-ups.
Inspect hands and feet at useful scale. Simplified texture-emission rendering
helps motion review but has limited shading and no useful contact shadow unless
separately supplied. It does not reproduce original MMD shaders. The encoder
defaults to one CPU thread and records full decode separately from viewing.

An explicit material `shader: diffuse` can provide a simple floor shadow
receiver while costume materials remain the default emission preview. Supply
actual light and floor geometry in the saved scene; this option is not a source
MMD-shader reproduction claim. Keep the ordinary default unchanged for older
inspection profiles.

An optional boolean `denoise` enables CPU OpenImageDenoise for a lightweight
preview (default false). The frame receipt records both sample count and
denoising choice. Inspect small finger/hair silhouettes separately; smoothing
noise does not repair motion, contact or geometry.

Review actual normal-speed motion when available: weight transfer, foot release,
support, whole-body rhythm, wrist/palm orientation, visible costume collisions,
stop/recovery and action joins. A still sheet, finite matrix test, full decode or
low angular peak does not establish naturalness. Record unavailable playback as
unverified; user rejection of an earlier video overrides a numeric self-score.

## Current evidence boundary

This candidate was developed against one adult MMD character, using permitted
100STYLE and Bandai Namco Research recorded BVH sources. The former's motion is
CC-BY4.0; the latter's datasets are CC-BY-NC4.0. Read the actual source/item terms;
their motion licenses do not grant rights to a character model. No motion assets,
model files or derived character scenes belong in the generic skill archive.

Sources: [100STYLE author page](https://www.ianxmason.com/100style/),
[Bandai Namco Research repository](https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset).
Local native/decode/visual reports must accompany any claimed validation. This
does not establish cross-character, general FBX/Mixamo, full-volume collision or
normal-speed continuous acceptance.
# Near-straight knee continuity

An explicitly configured minimum knee bend changes captured joint directions. Below that floor, a nearly straight source knee can change its plane normal sign because of tiny capture noise; treating the sign literally can create a180degree thigh roll. The fitter chooses the hemisphere consistent with the preceding calibrated knee plane only below the declared floor. It retains the observed plane, records the actual source-direction change and any hemisphere stabilization, and leaves source bends at or above the floor unchanged. Preserve the old fit and compare actual target rotation steps, weighted shoes, subframes and images in a new output. Direction alignment alone does not establish temporal quality.

## Preserve captured upper and forearm roll

Direction fitting aligns joint positions but does not determine rotation around
the segment. It can therefore preserve the hand endpoint while changing sleeve
and forearm deformation. An external body plan may explicitly set
`"arm_rotation": "source-first-fitted"` together with
`"wrist_rotation": "source-first-fitted"`. The default `direction-fit` keeps
the previous route. Unsupported modes, or captured arms without captured wrist
orientation, are rejected.

The opt-in route first uses the original direction fit to calibrate each of the
four upper/forearm bones. At subsequent samples it transports the captured
source world rotation relative to that first source pose onto the calibrated
first target rotation. The report records both reference matrices and maximum
evaluated world-rotation error; the original one-degree anatomical direction
guard remains active. It does not generate controllers, change rest hierarchy
or weights, or distribute twist across a model's special auxiliary bones.

Keep the previous fitted scene. Independently reopen both scenes and check
actual source rotations, arm joint positions, protected torso/legs/wrists and
weighted shoe geometry over the complete interval. Then compare matched actual
skin views, including raised and folded arms. Rest-pose offsets, clothing,
original twist helpers and source capture can still produce poor deformation;
passing directions or source-rotation checks alone does not make this option
the better performance. Inspect subframes and normal-speed motion separately.

If the independently checked original root/leg poses and actual weighted shoe
vertices are unchanged, an existing shoe-height trajectory for that **same
model and source excerpt** can be re-bound to the new scene's hash. Preserve
the explicit comparison and calibration chain beside the new plan. A matching
character name or a different first pose is not sufficient. Re-run shoe, hand
and physics preservation after integration; never copy a previous success
report onto the new scene.

## Use a real neutral foot reference

A cropped captured pose is not necessarily neutral for both feet. In the local
dance source, one foot was already pointed down in captured frame1. Using that
single pose as both foot references put the other foot's declared flat pose at
about48degrees of shoe-support pitch. A bounded post-fit pitch correction could
not repair the reference mismatch. Do not increase its limit to force a pass.

The body plan may supply `foot_orientation_references` with exact keys
`source_glb_sha256`, `review_sha256`, and `feet`. Both `left` and `right` entries
have `source_frame`, proper3x3 `ankle_rotation` and `toe_rotation`, and unit
`forward`: the recorded ankle-to-toe **joint-head** direction in source world
coordinates. The digest must match the current source GLB; the review digest
links the caller's separately inspected source/calibration evidence. The fitter
does not establish contact truth from that label.

Inspect the actual model's neutral-rest sole before using this option. The
fitter yaw-aligns its original-rest foot/toe frames to the recorded horizontal
marker direction, then transfers source rotation relative to each explicitly
declared reference. A nearly vertical reference direction is rejected. Existing
rest/weights/bone lengths remain; source upper/lower-leg joint-direction checks
stay active. The saved report records the actual source/target references and
evaluated rotation error. This is an explicit retarget calibration, independent
of the additional shoe-pitch adjustment; its30degree bound is unchanged.

Keep default legacy references for reproducing historical cases. New reference
choices change the performance and need fresh fitting, actual shoe/front/rear
views, full leg/body checks, hand preservation and recomputed physics. Declared
flat poses remain assumptions unless the source provides reliable contact data.

