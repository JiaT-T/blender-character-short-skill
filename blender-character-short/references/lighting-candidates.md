# Scene-only lighting candidates

Use `scripts/scene_lighting_candidates.py` to propose three **review-only** scene-light layouts from explicit target bounds. It runs on the host, reads the source for a SHA256 check and writes a new JSON report. It never starts Blender, edits a scene, renders or applies a candidate. Do not use it to change a frozen character look.

```text
python -B scripts/scene_lighting_candidates.py --request REQUEST.json --report NEW_REPORT.json
```

Example request (supply the actual source hash and exact object names):

```json
{
  "schema": 1,
  "source": {"path": "scene-copy.blend", "sha256": "ACTUAL_SHA256"},
  "objects": ["StageWall", "StageFloor"],
  "collection": "StageReceivers",
  "protected_objects": ["CharacterMesh", "CharacterRig"],
  "target": {"center": [0, 0, 1.5], "dimensions": [4, 3, 3]},
  "forward": [0, -1, 0],
  "prefix": "StageOption",
  "mood": "neutral",
  "material_intent": "mixed",
  "base_energy": 100
}
```

The request source path is relative to the request file. Target bounds describe the **stage area to illuminate**, in Blender world units, not an automatically detected character. World Z is up; `forward` is a nonzero horizontal vector toward the intended viewing/front side. Dimensions must each be 0.01..50; the largest dimension is the placement/size scale. This bound avoids unbounded candidate values; it is not a restriction on the scene itself. A smaller local target area can be used in a large set.

`objects` and `protected_objects` must be nonempty, unique and disjoint. Every character object belongs outside the receiver scope. The helper cannot inspect actual scene membership or infer omitted character parts. Native refinement must still verify the collection contains exactly the named stage objects. `prefix` is 1..24 ASCII alphanumeric/underscore characters. All generated light names are new names; existing lights are never deleted or modified.

`mood` accepts `neutral`, `warm`, or `cool`; `material_intent` accepts `mixed`, `matte`, or `glossy`. These are the caller's declared intentions, not a material classifier. Glossy intent uses larger emitter sizes to suggest broader highlights; matte uses slightly smaller sizes. `base_energy` is a finite 0.01..400 starting power at unit target size. Power scales by the square of target size, while placement and emitter size scale linearly. Exposure, unit scale, existing illumination, toon thresholds and material response can all defeat that estimate. The three variants (`soft`, `separation`, `restrained`) vary fill/rim contribution and emitter size. Their names do not imply visual approval.

## Deliberate adoption

1. Inspect the candidates against the narrative atmosphere and unchanged character look. Choose **one**, not all three stacked together.
2. Review and adjust positions, color, power and size as appropriate. Confirm each light name is unused and the exact receiver collection excludes the character.
3. Copy only that candidate's `scene_patch` into the `scene` field of a separately authored, hash-bound [static refinement plan](static-refinement.md). Use the same source hash, a new output and backup, and the normal protection/reopen checks. Do not pass the report itself as a refinement plan: its schema is deliberately incompatible.
4. Render a cheap still of the new copy and compare contact shadows, readable room shape, highlight clipping, bloom and depth of field. The helper has no image-based scoring and does not choose a winning candidate.

No world, camera, material, existing lamp or character changes are generated. The candidate lights use the existing stage receiver-linking implementation when adopted. This is not a promise that every indirect/probe interaction is isolated; inspect the resulting image and preserve the protected character configuration. Tests cover request bounds, source identity, relative geometry, compatible patches, read-only behavior and report no-overwrite. They do not establish Blender execution, appearance or animation stability for new candidates.
