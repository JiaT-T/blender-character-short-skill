# Narrative scenes and grounded interaction

Before polishing, establish which side of every signal surface the character
and audience see. A correct look-at point can sit behind an opaque backing.
Check [external blockers](target-occlusion.md), then separately verify the
actual character/iris and luminous face. A camera cut that reveals a signal
to the audience does not establish the character's sightline.

Use this for a scene that changes because of the character's action. Write the
goal, obstacle and result first. Give each shot a visible change to communicate.
For example, a dark socket, a spare module, a placement and a light route can
tell a complete small story without relying on captions or official lore.

## Moving prop components

A control handle may need a real shaft or carriage connecting it to the set.
Use optional `parent` on a story object to inherit another object's motion:

```json
{"name":"Control linkage","shape":"box","parent":"Story prop",
 "position":[0,0.05,0],"size":[0.01,0.10,0.01],"material":"mechanism"}
```

Define the material in `set.materials`. Parented position and dimensions use
normalized character height in the parent's local space, before inherited
scale. No world ground offset is added locally. Thus a parent scale of0.5
halves the child's world dimensions and offsets. Rotation is local; bevel
width is also inherited. Objects without `parent` keep the original world
coordinate/ground convention.

References can point to an existing scene object or another declared story
object, even if that parent is defined later. Missing parents, cycles and
ambiguous existing names are rejected before parented-scene construction.
This is object parenting only, not bone attachment, a rigid constraint or
contact physics. Audit the actual moving components: a visible handle, a real
shaft that stays engaged and a hand that does not intersect the guide are
separate conditions. Do not fix glove penetration by leaving a floating knob.

The geometry-only `verify_story_parenting.py` checks nonzero ground/height,
animated nonuniform parent transforms, out-of-order descendants, saved
hierarchy and invalid parent graphs. Supply an old `story_stage.py` through
`--reference-stage` for a default-scene comparison. It must run in its own
factory-startup background Blender process.

## Author an interaction space

Measure the actual shoulder, wrist reach, eye region and glove before placing
the pickup surface or destination. A chibi's total height is a poor estimate
of its reachable work area. Place the set around the tested reach, or change
the performance deliberately. Keep targets and choreography in the story input.

Check the hand, forearm, sleeve and nearby set together. In an actual trial,
positive hand/prop clearance still allowed a broad tray to pass through the
forearm. Redesigning the pickup support left an open approach; lifting the prop
farther from the palm would not fix that problem. Inspect entry, hold and release,
including frames between the authored keys. Directional palm raycasts do not
test cabinet collisions or certify whole-scene physical clearance.

Prefer appropriate licensed motion-library clips for common actions when they
are accessible, then retarget and correct for the actual proportions. Keep the
source, license and actual retargeting results. A library name or a logged-in
browser is not evidence that a clip was acquired or used. An unavailable library
can be recorded while a local manual blocking pass proceeds; do not label that
pass as library-motion reuse. Never upload the user's model to an auto-rigger
without the required authorization. Adobe's [animation workflow](https://helpx.adobe.com/si/creative-cloud/help/animate-characters-mixamo.html)
and [FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) describe the
service; the specific asset's usage conditions still belong in the project record.

## Optional data-authored set objects

`set.materials` is a dictionary. A material needs linear `color:[r,g,b]`;
optional fields are `roughness` (0..1), `metallic`, nonnegative `emission`,
`emission_color`, and `emission_keys:[{t,value}]`. Keys animate emission strength
and are saved in the material node tree. `t` uses the same story time and optional
duration scaling as the poses. Each material is shared by the objects using it.

Emission strength zero does **not** make a bright base color dark. For a visibly
off lamp, use a dark base `color` and separate bright `emission_color`. Check the
actual before/after render; node values alone do not establish a readable change.

`set.objects` is a list of:

```json
{"name":"Spare dock","shape":"box","position":[0.2,0.1,0.4],
 "size":[0.08,0.02,0.08],"material":"housing","bevel":0.004,
 "rotation":[0,0,0],"purpose":"Keep the spare within reach"}
```

`shape` is `box` or `cylinder`; cylinder size gives x/y diameter and z depth.
Positions and dimensions use character heights, with ground added to position z.
Rotations are XYZ degrees. Bevel is applied to actual mesh dimensions, and must
fit the smallest dimension. Names must be unique. These original primitives can
block or build a compact set. Reviewed self-contained static GLB pieces can use
the optional [scene asset workflow](scene-assets.md); complex environments,
animated sets, texture adaptation and arbitrary model formats remain outside it.

The `token` prop is a beveled box, width/height .075H in local XZ and depth .014H
along Y, before `prop.scale`. Its bottom-center contact point is `[0,0,-.0375]`
before scale/rotation. Derive other contact points from the actual geometry.

## Body offsets and stationary support

A pose can supply `translations:{semantic:[dx,dy,dz]}`. These are world-direction
offsets in character heights, relative to that pose's otherwise evaluated bone
position, not absolute targets or local-axis offsets. Add the intended controls
to the external character `bones` mapping. Locations are keyed along with rotations;
omitted translations return the configured controls to zero offset at that key.

Do not assume an imported leg IK will hold the feet after moving the hips.
An actual trial drifted about .0084H even though the IK constraints remained
enabled. Audit evaluated feet and visible soles before accepting body offsets.

An optional character `stationary_support` maps each side to existing bone names:

```json
{"left":{"upper":"leg.L","knee":"knee.L","ankle":"ankle.L",
 "target":[0.05,0.01,0.02],"pole":[0.05,-0.35,0.12]}}
```

Target and pole are normalized world positions, with ground added to z. The chain
must be directly parented upper -> knee -> ankle. Choose the target from the
inspected rest ankle head, not the bottom of the shoe. `support_motion.py` explicitly
mutes IK constraints on those knees/ankles in the **new candidate**, preserves the
original deform bones/weights and bakes an analytic FK solution at each integer
frame. It fixes ankle orientation to its rest orientation and rejects unreachable
targets. Constraint changes and maximum target error are recorded in the build
report. Source assets and baselines are not changed. Without this configuration,
the original IK remains as before.

This is a stationary support route, not walking, footstep retargeting, heel roll,
physics or subframe contact. Check knees, skinned soles, costume and the complete
performance. Six synthetic Blender cases cover saved/reopened origin and transformed
rigs, no-op preservation, unreachable targets, invalid topology and nonfinite inputs.
Run `verify_support_motion.py --output NEW_DIRECTORY` inside Blender to reproduce
them. Tests of one character do not establish cross-character artistic reuse.

## View and preserve evidence

The optional [scene matte style](scene-style.md) belongs to the story's set input.
Keep character-specific shader configuration in the character mapping. Compare
the original and styled environment under identical story/camera/light conditions.

Render a cheap complete board, compare distinct shot arrangements, then refine
the observed problems. Preserve failed versions with their scene/input pairs.
Check chibi headroom through the whole shot: orthographic `scale` is the **width**;
at 16:9, vertical coverage is only 9/16 of that value. A comfortable body framing
can still crop a tall bun when a close camera cuts in.

For an all-frame geometric check, run `audit_head_framing.py` inside Blender with
`--blend`, `--character`, `--output` and optional `--margin .02`. It projects actual
evaluated vertices weighted at least .1 to the mapped head or its descendants
through the active production camera, and reports cropped/low-margin frames.
It checks its projection against Blender's independent camera-view function.
Changed evaluated topology is rejected rather than guessing vertex correspondence.
In the tested 480-frame Nanami candidate, 6,159 selected vertices remained inside
the frame, with at least .076 of an image dimension to the nearest edge. This is
a weighted-geometry bound, not an occlusion test or a normal-speed viewing pass.
Intentional head crops still require an explicit editorial decision; do not turn
the diagnostic into a universal prohibition on closeups.

For macro diagnostics, clear timeline camera markers only in an unsaved disposable
copy, select the diagnostic camera and assert it remained active after rendering.
Resolve output paths to absolute paths before assigning Blender `render.filepath`;
relative native-render paths can land outside the intended working directory.
Macro views explain contact; they do not replace production-camera readability.
Native-raw previews bypass the external source postprocessor and must be labeled.

Decode and sample checks remain separate from continuous normal-speed viewing.
State which was actually done. A silent preview needs no implied audio acceptance.


## Interaction inserts and physical seating

A contact that reads in a macro diagnostic can still be too small in the final
shot. Compare the actual sequence with an intentional interaction insert. A
head-bound report may legitimately show cropping there: record the shot's focus
and inspect the hands/prop rather than presenting that crop as a full-character
framing pass. Keep discovery and reaction shots that establish the character.

Two adjacent inserts with nearly the same angle and size can produce an awkward
cut. Compare a visibly different angle or use one continuous shot; do not choose
an angle from coordinates alone. A Nanami side-view test exposed a gap behind a
released tile that a front view had hidden. Check the destination support surface
and visible seating after release, separately from palm contact while held.

Early v08-v10 build reports retained a legacy `control` string saying legs/IK
were preserved even when optional stationary FK was selected. Their detailed
`stationary_support` record correctly listed muted constraints. This reporting
correction makes the summary agree with that actual route; do not infer active
IK from the older summary. Historical output files remain unchanged.
