# Production configuration and acting

## Character JSON

Use UTF-8. Input paths inside JSON currently must resolve from the process working directory; absolute paths are safest. inspect_character.py --blend BASELINE --output REPORT runs inside Blender and records bones/joints, UVs, material images, morphs and bounds.

Required fields:

| Field | Contract |
|---|---|
| id, height, ground | Project label, actual world-space height and ground |
| bones | Semantic keys head, spine, left_arm, left_elbow, left_wrist, right_arm, right_elbow, right_wrist, left_foot, right_foot |
| head_forward, head_angle_limit | Rest forward in armature coordinates; degree limit |
| palm_rest_normal | Per-side palm rest normals in armature coordinates |
| face_rest_y, face_rest_z | Source Face head axes after coordinate conversion |
| shapes, expression_scale | Optional semantic morph names and intensities |
| materials | Explicit slot mappings and external source resources; prepare_materials.py supports flat, dorm, character |
| neutral_pose | Optional calibrated resting pose used as an authoring seed |
| contact_anchors | Optional named palm calibrations; see below |
| performance | Legacy named pose arrays; omit for new story-owned poses |

A pose key has t in seconds; optional rotations maps semantic bones to XYZ Euler degrees; look is a normalized world target; left_hand/right_hand contain target and elbow pole, optionally finger, normal and contact. Position becomes (x*height,y*height,ground+z*height), then converts to armature coordinates. Palm vectors are armature directions. Test orientation per model.

reach_fraction defaults .96 to keep elbow bend. Reports separate requested and reachable targets. contact:true fails if endpoint error exceeds height*contact_tolerance (default .005). A clamped gesture is not a verified touch. A prop normally follows world keys; explicit contact intervals can bake a selected prop point onto a calibrated moving palm anchor.

Joint length uses shoulder→elbow and elbow→wrist heads because MMD display tails may point at twist helpers. Check shoulder shape, crossed elbows, wrist orientation and interstitial frames. This is not general retargeting.

## Story JSON

Required: title, duration, fps (24 expected), poses, set, prop, camera_variants. Optional synopsis, expressions and reference notes. `poses` is a nonempty array using the pose-key contract above. The old `performance` character-config key remains readable for historical inputs; new stories should own their choreography.

For optional `translations`, `stationary_support`, `set.materials`, `set.objects`, emission events and the `token` prop, read [narrative scenes](story-scenes.md). Those additions are opt-in; existing inputs retain their default behavior.

- set: linear RGB floor, panel, trim, world; optional stand with normalized x,y,height,radius. Creative set lights are separate from reference matching.
- prop: kind paper-plane or star; optional positive scale multiplier (default 1); linear color, optional emission; keys with t, normalized p and XYZ rotation degrees. Plane tail extends .025 heights below its origin; account for the landing surface.
- camera_variants: named shot arrays. Each needs start,end,location,target,scale,purpose; end_scale is a multiplier of the starting scale (for example .97 is a 3% push), not an absolute width. It optionally animates orthographic scale. Scale is ortho width / model height; at 16:9 the vertical view is smaller. Adjacent shots share boundaries; first starts 0 and last ends at duration.
- expressions: semantic names mapped to [seconds,value] pairs. Missing morphs are reported.

--duration proportionally rescales pose/story times. Frame mapping is round(seconds*fps)+1 clamped to final frame; 10 seconds is 1–240 at 24 fps. A new story requires new keys, not just renaming it. Both tested characters rebuilt from story-owned poses with identical evaluated pose, foot, contact, expression and camera reports to the legacy input placement.

### Creative set configuration

Optional `set.panels` replaces the two default architectural panels. Each item
has `position:[x,y,z]`, positive `size:[x,y,z]`, and optional nonnegative `bevel`.
Values are in character heights; position z adds character ground. An empty
array removes panels. Check the entire animated camera range: a panel that is
useful in the wide shot can become a distracting cropped strip in a close shot.

Optional `set.lights` replaces the default area lights. Each item has `name`,
`location`, `target` (default `[0,0,.65]`), `color`, positive `size`, and
nonnegative `energy_per_height_squared`. Locations/targets are world coordinates
in character-height units, with world origin unchanged; power is multiplied by
height squared and size by height. Optional `world_strength` defaults to `.35`.
The resolved values are recorded as `creative_set` in the build report.

These controls describe the creative set, not website character-light uniforms.
Compare under unchanged character material/post parameters. A lighting change
cannot validate a missing shader branch or compensate for an incorrect input.

## Moving palm contact

Character `contact_anchors` maps a semantic anchor to actual `start_bone` (wrist),
`end_bone` (middle-finger base), `fraction` between their heads, `normal_local`
in the wrist's local rest basis, and `normal_offset` in character heights.
Determine the palm side from the actual hand; names alone cannot identify it.
The tested calibration requires a unit-scale armature object and unchanged mesh
topology. Preserve original rig weights and finger poses.

Story `prop.contacts` is an optional list:

```json
[{"start":3.25,"end":5.3,"blend_in":0.45,"blend_out":0.55,
  "anchor":"active_palm","prop_point":[0,0,-0.0404508497]}]
```

`start`/`end` delimit **full** contact. Blend-in occurs before start; blend-out
after end. `prop_point` is a point in the primitive's local coordinates measured
in character heights; the prop's scale and rotation are applied to it. The
example is the midpoint between the star's two lower tips at zero rotation,
not a universal point for other shapes. Orient the prop and examine its footprint.
Overlapping contact transitions are rejected; handoff is not implemented.

`contact_motion.py` samples the original free trajectory before adding keys,
then bakes every integer frame with smooth transition weights. This avoids
earlier inserted keys changing later free-curve samples. Full-contact point gap
is reported separately from transitional gap. The prop must be unparented.
There is no physics, collision response or subframe/motion-blur guarantee.

**A bone-center anchor can lie inside a thick glove.** Measure actual evaluated
hand geometry before accepting it:

```powershell
& $Blender --background --factory-startup --python-exit-code 1 --python "$Skill/scripts/calibrate_contact_surface.py" -- --blend CANDIDATE.blend --character CHARACTER.json --frames 80,100,124 --output PALM_REPORT.json
```

The script raycasts only faces influenced by the configured wrist/descendants,
reports material, surface normal and measured height offset, and suggests the
maximum sampled surface offset plus explicit clearance. Inspect the hit and
copy a justified value into a **new** character config. Rebuild and compare
fixed-camera close views before/after, including the prop's lower corners,
fingers and contact entry/exit. One anchor ray does not prove whole-mesh clearance.

The two actual glove models needed different offsets; the initial `.004H`
bone-center estimate penetrated both despite zero numeric attachment error.
This failure is why the surface check is a production step rather than an
optional numeric score. New poses, changed gloves or a different prop footprint
require fresh checks.

For a wider directional check, use `audit_contact_footprint.py` with `--blend`,
`--character`, semantic `--anchor`, `--frames` and `--output`; optional `--prop`
defaults to the generic `Story prop` object. It samples actual prop vertices,
triangle centers and edge midpoints against weighted hand faces along the
configured palm normal. A negative clearance is a warning to inspect that point
in fixed-camera views. Misses and grazing/reversed hits remain unverified.
An object entirely below the hand can also produce a negative result: this is
not a general 3D collision test, inside/outside classifier, or automatic solver.
Keep the full report and check real visible contact, not just the lowest number.
The single-ray suggestion may be lower than a subsequently verified footprint
offset. Do not blindly overwrite the latter on a rerun. Record why the chosen
offset differs, remeasure after pose/prop changes, and compare against the glove
in fixed-camera views. An offset that clears sampled tips may instead make the
prop visibly hover; numeric clearance is only one diagnostic.


Existing morph names also need a visual contract. For the tested chibi,
`笑い` at a partial value looked drowsy, while value 1 produced a readable
closed-eye smile. It is an eye expression, not proof of a mouth smile. Prefer
semantic names such as `eye_smile` and `mouth_open`; do not infer meaning solely
from a translated model label. Retain separate gaze and expression controls.

## Review

Annotate reference timestamps for anticipation, gaze, held reaction and recovery. Design new shots to serve the new story. Inspect pre-action, peak, stop/contact, reaction, cut±1 and final pose. Keep prop clear of the eyes at emotional beats. Large chibi heads and adult costumes need different camera scales and hand targets.

Compare complete A/B boards before refining poses. Board colors bypass the external source postprocessor and are diagnostic. A better still can have worse continuity; contact sheets do not establish continuous motion quality.

## Calibrate anatomical story targets

Run inspect_character.py on the fresh import, then run python scripts/calibrate_character.py --inspection REPORT --character CONFIG --output NEW_CONFIG. It adds normalized rest-joint landmarks and actual arm segment lengths without changing supplied choreography. Use landmarks.rest_joints.left_arm/right_arm as shoulder anchors. The head joint is not an eye center; eye avoidance still needs explicit eye landmarks or image calibration. Compare prop paths to these anchors before rendering. A tested chibi shoulder was only .447 of full height, while the adult shoulder was .815; a universal .60–.65-height orbit changed the chibi story into a head-side orbit. Those numbers are observations, not defaults for other characters.

After a successful build, render key poses and verify the prop actually occupies the named anatomical region. If it does not, change character/story configuration and rerun in a new version directory. Technical pipeline completion and story fidelity remain separate.

Prop-axis contract: the star is built in local XZ with thickness along Y, so local Y rotation spins its five-point silhouette in-plane. Local Z rotation turns it edge-on. The paper plane is principally in local XY. Choose rotations from the actual primitive axes and camera; inspect the final silhouette instead of assuming every prop spins around Z.

## Existing eye-control route

Optional character `gaze` contains `control`, `left`, `right` bone names, rest `forward` in armature coordinates, and an explicit `max_angle` in degrees. It uses the midpoint of the real eye bones; MMD binocular control bones can sit above the head and are unsuitable as gaze pivots. Existing constraints remain intact. Pose `eye_look` overrides the normalized `look` target for the eyes; otherwise the eyes follow `look`. Control rotations are baked into the saved action.

Verify paired renders with the eye route disabled/enabled at discovery, interaction and recovery. Inspect actual irises and white-of-eye limits; numeric control rotation alone proves neither deformation nor gaze accuracy. Fifteen degrees was visually useful on one chibi case but too strong on the adult case; an eight-degree adult test was more restrained. These are per-asset observations, not universal defaults. Aim clamps and residual mismatch must be disclosed. The current route supports an existing binocular control, not arbitrary independent eye rigs or automatic eye constraints.

For a matched eye-control diagnostic, run scripts/probe_gaze.py inside Blender with --blend SAVED_SCENE --config GAZE_JSON --output NEW_DIR --frames 72,100. The config is the standalone gaze mapping object. Optional --face-close uses the same diagnostic face camera for both states. These PNGs bypass external source post and must only be compared to each other.
