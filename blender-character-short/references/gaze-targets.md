# Final evaluated gaze on static feedback objects

Use `audit_gaze_targets.py` after saving a candidate when plot-critical looks
target real static objects created by `story.set.objects`. It reads a saved
scene, changes only the in-memory frame, and writes a separate JSON report.
It never renders, saves the scene, downloads resources or changes eye controls.

Mark each required pose with boolean `gaze_required: true` and
`gaze_target_object: "ACTUAL_OBJECT_NAME"`. Its `eye_look` must equal that object's
authored normalized center. Supply the same character/story used to build the
scene. Keep original per-character limits; do not raise them to obtain a pass.

```powershell
blender --background --factory-startup --python scripts/audit_gaze_targets.py -- --blend SAVED.blend --character CHARACTER.json --story STORY.json --output NEW/gaze-targets.json
```

The diagnostic uses actual evaluated original eye-bone forward axes, a mapped
head and binocular control, and actual feedback-object centers at all integer
frames from the first required key to the last. Between static targets it uses
linear world-center interpolation, which was exercised for a row on one feedback
plane. It reports the inferred middle-eye angular error, total head deformation,
control-basis angle and actual material emission at required keys. The declared
middle-axis tolerance is 5 degrees; head/eye limits come from the character.
This is a bounded diagnostic criterion, not a universal eye-physiology standard.

Verified case: one Nanami Q front-side feedback scene, seven required keys and
61 final evaluated frames; maximum inferred middle-axis error about1.21 degrees,
head31.94 and control12.77 with unchanged35/15 character limits. Native samples
showed five visible light steps and the turn. Continuous normal-speed viewing,
actual iris sight rays, complete occlusion and timing quality remain unaccepted.

The successful change moved the actual feedback board with its targets and
synchronized the light keys. It did not move an invisible eye target away from
the visible result. Source spine variation was moved outside the required glance
interval; final graph checks followed all baked layers. Keep control-key bounds,
final evaluated axes, rendered iris appearance and continuous viewing separate.

Supported scope is one configured armature and static data-authored set objects
with the existing Principled emission contract. Moving props, arbitrary imported
materials, transitions between very different target depths and other characters
are unvalidated. This command does not certify undeclared/non-required looks.
The separate v12 build-time gate/state-snapshot proposal remains isolated and is
not included here; this verified read-only audit does not establish its runtime.
