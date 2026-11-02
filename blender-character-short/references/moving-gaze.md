# Optional gaze baking against real objects

Use this route when authored gaze keys miss a moving prop between keys. First
make the object reachable and visible, calibrate the original head/eye mapping,
and inspect the pose. Baking cannot make an unreachable look natural. A nearer
target can need a smaller head tilt; derive the actual eye origin after the
posed hierarchy rather than assuming the head pivot is the eye pivot.

Supply a JSON plan with non-overlapping **integer frame** ranges:

```json
{"ranges":[{"start":51,"end":120,"object":"Story prop"}]}
```

The named object must already exist in the built scene. Its evaluated world
origin must be the intended physical fixation point. An explicitly calibrated
anchor on the object is also possible; never substitute an unseen point merely
to obtain a passing angle. Omit a saccade between different objects from a
continuous fixation range. Partial contact/release frames still use the actual
evaluated prop, not an assumed free or fully held position.

`run_short.py --gaze-plan PLAN.json` applies this optional stage after the
ordinary build and before raw rendering. The original built scene remains in
`scene/scene.blend`; the renderer uses the new `gaze/scene.blend`. Deliver the
latter together with its bake report, plan, character mapping and pinned
producer. Do not replace a scene in an existing raw-frame cache.

For an existing scene, call Blender in factory startup with
`scripts/bake_gaze_targets.py -- --blend INPUT.blend --character CHARACTER.json
--plan PLAN.json --output NEW.blend --report NEW.json`. Both outputs must be
new and distinct from the inputs. Keep the shared execution lock around the
whole operation.

This route currently requires one armature and an existing quaternion binocular
control. It samples the original action, aims that control at actual evaluated
object positions inside the ranges, then keys only its quaternion curves at
every integer frame. Original control values outside the ranges are preserved
at integer frames. Head, arms, prop, cameras and expression curves are not
authored by this stage.

Without an explicit return, range boundaries are not automatically blended. A baked fixation can jump back
to the original eye control on the next frame outside its range. Inspect the
last fixation frames and the first original-control frames with the actual
expression and head motion. Author a transition when needed; a planned blink
only conceals a return if the evaluated eyelids visibly cover it. Keep head/eye
bounds checked across the whole clip even when fixation is required for only
part of the story. Declare fixation ranges from the action's meaning before
accepting them: securing an object and then looking ahead is different from
maintaining fixation. Do not shorten required visible tracking to hide a limit
failure. Record the actual range rather than claiming whole-film tracking.

An optional `returns` list can interpolate from the last fixation control back
to the original authored per-frame control, while the existing head motion
continues:

```json
{"ranges":[{"start":1,"end":69,"object":"Story prop"}],
 "returns":[{"start":70,"end":82,"easing":"smoothstep"}]}
```

Each return starts immediately after a fixation range, contains at least two
integer frames and fits the scene. Returns cannot overlap fixation or one
another. `easing` is `smoothstep` by default or `linear`. The last fixation has
interpolation weight0; the return end has weight1, equal in orientation to that
frame's original control. Shortest-path quaternion interpolation and hemisphere
continuity are used; every other animation curve remains unchanged. Head/control
limits are checked on the returned saved graph before saving. The named target
is not tracked during these return frames: this is a deliberate change of
attention, not softened evidence for a required fixation. Inspect actual iris
movement and the complete performance before selecting it. Omit `returns` to
preserve the prior boundary behavior. Plan-validator bytes join the stage's
hash-bound evidence; a different helper or missing report requires a new output.

Eye constraints can drive their existing helper bones;
identify that dependency graph before judging a bone-matrix comparison.

Any required correction over the configured eye limit stops before saving a
new scene and preserves a failure report. The final evaluated integer-frame
middle eye-bone axis must also stay within5° of the actual object, with head
and control angles inside the original mapping. These are inferred axes, not
iris rays. Correct the pose/layout in a new
version; do not widen the limit to make it pass. A saved scene is still pending
independent saved-graph and visual checks. Inspect eye axes, control/head bounds, object
timing and visibility; compare unaffected motion and render the final saved
scene. Keep failed numeric and visual candidates separately.

The pipeline binds the plan, character, writer, original built scene and baked
scene by hash before rendering or reusing the baked scene. Missing or changed
evidence rejects reuse. A failed report or partial scene requires a new output
version, not an overwrite.

The numerical contract covers integer frames and the configured bone axes.
Subframes, actual iris rays, skin/prop occlusion, continuous viewing, natural
acting, arbitrary rigs and full-body motion retargeting need separate evidence.
