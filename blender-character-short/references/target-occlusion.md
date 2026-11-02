# External blockers are separate from eye aiming

A character can aim exactly at a lamp center while an opaque board blocks the
lamp. Establish which side of the prop the character and audience can see.
Keep the real emitting surface, its support and the reaction coherent. An
open rack can expose two-sided lamps; an angled screen needs its own face and
sightline checks. Do not make a panel transparent merely to pass a diagnostic.

Run `scripts/audit_target_occlusion.py` through factory-startup Blender with
`-- --blend SCENE.blend --character CHARACTER.json --plan PLAN.json --output
NEW-REPORT.json`. It is read-only and requires a new report separate from all
inputs. Use the shared execution lock.

Use actual mesh names in a frame plan:

```json
{"ranges":[
  {"start":301,"end":361,"object":"Signal bar 0"},
  {"start":301,"end":361,"object":"Signal bar 1"}
]}
```

Ranges may overlap for different objects. This checks whether each target is
externally exposed throughout the interval, not simultaneous fixation.
Duplicate frame/object pairs are rejected. If a non-convex object's origin
lies in empty space, add `"triangle":0` to use an actual evaluated triangle's
centroid. Preserve that mesh/triangle version. A witness on one surface does
not prove every surface or the intended feature is visible.

At each integer frame the tool casts from the configured two-eye midpoint:

- `target-first`: the target has an exposed surface through eligible external
  blockers.
- `external-blocker`: another opaque object is first; inspect its name.
- `no-target-surface-hit`: no confirmed target surface; unpassed rather than
  evidence that nothing blocks the object.

All armature-deformed character meshes are excluded and listed. This avoids
mistaking an eye pivot inside its own geometry for an external blocker, but
also excludes hair, eyelids, face and hands. Do not call the result an iris ray
or a complete character-perception test.

The current route accepts supported opaque Principled, Diffuse or Emission
surfaces and mixtures of those opaque surfaces. Alpha and transmission are
checked at every requested frame. Transparency, transmission, backface
culling, unknown surface graphs and viewport/render modifier-visibility
differences return unsupported. It does not model hidden collections,
renderer-specific ray visibility, luminous face orientation, arbitrary shader
groups or different render/collision geometry.

Combine separate gates before accepting a critical look: reachable head/eye
controls, final bone axes, external blockers, actual character/iris and
luminous face, rendered framing/timing, then continuous normal-speed viewing.
Passing one does not imply the others. Recheck after moving a target, its
support, the observer or camera.
