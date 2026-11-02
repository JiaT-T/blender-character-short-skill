# Reuse existing node-motion rotation variation

Use this route only when a permitted local clip, its matching node hierarchy and
an explicit character mapping are available. Prefer suitable motion-library
actions for common movements. This implementation supports one packed node JSON
format; it is not a Mixamo FBX importer or a full-body retargeter.

`source_motion.py` reads version-1 component-major delta vectors and smallest-three
quaternions, normalizes sampled quaternion interpolation, and evaluates a glTF node
hierarchy. A current-project trial decoded all 47 tracks of an existing `Stand02`
file exactly against the original client decoder (maximum float32 difference 0).
That verifies this format and file, not arbitrary future formats or usage rights.

`source_motion_layer.py` adds **rotation variation** relative to a source sample
over the authored pose. The source's starting pose is not a target rest pose.
Root translation, walking, heel roll, face/texture events, morphs and automatic
bone matching are not implemented. Those gaps must remain explicit even when the
upper-body variation looks useful.

## Inputs

An optional story `source_motion_layers` list contains entries like:

```json
{"clip":"ABSOLUTE_CLIP.json","skeleton":"ABSOLUTE_NODES.json",
 "basis":[[1,0,0],[0,1,0],[0,0,1]],"mapping":{"spine":3},
 "start":0,"end":3.4,"blend_in":0.5,"blend_out":0.6,
 "duration":2,"loop":true,"speed":1,"phase":0,"reference_time":0,
 "strength":0.35}
```

- The skeleton JSON contains `nodes` with glTF TRS or static matrix transforms and
  child indices. Node indices must match the clip; names alone are insufficient.
- `mapping` maps external character semantic bone keys to source node indices.
  Derive and verify the correspondence from the actual rest landmarks and axes.
- `basis` converts source world rotations to the target world basis. It must be
  a proper orthonormal rotation, not a guessed sign flip or reflection. glTF Y-up
  conversion alone can be insufficient when the imported PMX faces the opposite
  direction. Verify both the axis algebra and an actual pose before acceptance.
- `start`, `end` and fades use story seconds and follow `--duration` scaling.
  Source `speed`, `phase`, `reference_time` and `duration` use clip seconds.
  `strength` weights the shortest quaternion change from the reference sample.
  Overlapping layers compose in list order.

The layer snapshots the authored matrices for **all** frames before adding dense
keys. Sampling and writing in the same loop can otherwise let earlier inserted
keys change later base samples. Resulting keys are saved with the scene and need
no runtime handler. Original source files are read only.

For nested mappings, convert each requested world rotation against its current
parent while retaining the target bone's authored local translation and scale.
Do not pin a mapped child's head to its old world position after rotating its
parent: that changes local offsets and can disconnect a rig whose bones are not
marked connected. The current implementation preserves those channels, including
outside the active interval. Earlier freezes were tested on one mapped spine;
their world-position conversion is not safe evidence for nested mappings.

The pipeline hashes every nested clip and skeleton along with the story and
scripts. Changed external bytes require a new output version, even if the story
still refers to the same filename. A real one-frame paused pipeline was used to
check that changing a fixture clip rejects resume without changing the raw frame
checkpoint. Do not bypass that guard to reuse frames from another performance.

## Preserve interactions and verify actual use

Choose the source variation's role in the story. A useful limited case is adding
small upper-body movement to an idle introduction or held reaction while keeping
precise pickup/placement beats authored separately. Do not apply a breathing or
arm-swing overlay blindly across a required touch.

An actual Nanami trial used one mapped spine node during two non-contact windows.
It affected 217 frames and at most about 1.41 degrees. Comparing all 156 held-contact
frames found hand/prop differences below 0.000002 in the matrix components; three
skinned contact frames differed below 0.000001 world units. All-frame foot matrices
were unchanged. These are numeric boundaries plus sampled pose evidence, not a
normal-speed acting pass or full-clip reproduction.

Run `verify_source_motion.py --output NEW_DIRECTORY` inside Blender for nine
synthetic cases: a known 90-degree source at half weight, transformed-world
save/reopen, absent-layer no-op, reflected basis, missing node and nonfinite phase.
The nested cases add an unconnected zero-offset chain, a transformed uniform-scale
rig with Euler posing and nonzero local offset/scale, and an inactive interval.
They check saved/reopened joint distances, local offsets/scales and world rotations.
Nonuniform/sheared rigs, constraints beyond the supplied cases and arbitrary
retargeting still require their own actual checks.
Then run actual motion/contact/sole diagnostics, view the source and output,
compare under the same camera, and record what was retained or rejected.

Keep clips, skeletons and their rights/source records outside the generic skill.
A successful decoder or public URL does not grant redistribution permission.
If a requested motion returns 403, stop that acquisition; using another already
present permitted file is independent work, not proof that the blocked motion
was acquired. Record partial reuse and the remaining action-library gap honestly.
