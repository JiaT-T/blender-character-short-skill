# Weighted character-region surface checks

Use `scripts/audit_character_regions.py` when large hair, sleeves or hands can
intersect during story-specific reaching, head attention or recovery. An
external scene-contact pass does not inspect character self-contact. Start
with the actual saved low-cost complete preview and keep the last good scene.

Keep bone names and thresholds in a local external plan. The generic package
contains no character profile or motion data. Schema1 has exactly:

```json
{
  "schema": 1,
  "regions": {
    "head": {"root_bone": "EXISTING_HEAD_BONE", "weight_threshold": 0.35},
    "arm": {"root_bone": "EXISTING_ARM_BONE", "weight_threshold": 0.35}
  },
  "pairs": [["head", "arm"]],
  "ranges": [[1, 120]]
}
```

Each region includes the named original bone and descendants. A complete
triangle belongs only if every vertex's summed weight for those bones meets
the configured threshold. Region roots must be distinct. The scene must have
one armature with at most2048bones; original vertex and triangle topology must
remain unchanged. Meshes are selected by their armature modifier and
object-level `hide_render=false`, without alpha masking or collection-visibility
interpretation. Inspect region triangle counts to confirm the intended body
parts were selected. Unsupported/empty selections fail rather than pass.

Run with the normal approved Blender execution route:

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/audit_character_regions.py -- --blend SCENE.blend --plan REGION_PLAN.json --report NEW_REPORT.json
```

The command reads the saved scene, preserves its bytes and writes a new report.
Reports are bound to scene, plan, writer and validator hashes. Existing reports
are not overwritten. Exit0 means the inspection completed: read
`no_nonadjacent_surface_pairs_in_selected_scope`, warning rows and the exact
requested ranges. `unrequested_scene_integer_frames` remains explicit.

The tool splits selected triangles into chunks of at most512, so an overlap
query cannot allocate an unbounded full-mesh cross product. Work is limited to
1200saved integer frames,50million selected triangle-frames,1million possible
chunk-pair-frames and200000reported surface pairs per frame. Shared-original-
vertex pairs on the same mesh are counted separately and excluded as adjacent
geometry. This exclusion must not be mistaken for mathematical disjointness.

When a warning appears, inspect a matched image and its plot purpose. A
wrist-preserving elbow-direction probe can redirect a sleeve while retaining
an empty reaching hand or a contact target. Compare the entire relevant time
window, original head/eye limits, actual prop gaze, protected transforms and
external surfaces again after changing the story's poles. A single clear probe
does not validate the whole motion. Preserve failed trials and the original
source scene; never stretch bones, edit user weights or loosen limits to hide
a failed reach.

This is triangle-surface evidence for selected weighted regions only. It does
not establish penetration depth, closed-volume containment, cloth physics,
unselected body-part clearance, subframe safety, natural motion, transparency-
aware visibility or normal-speed continuous viewing. An old authored
intersection remains a warning even when a new action layer adds none.

Region descendants can overlap: an upper-body root may contain both hand
regions. Such a pair also reports a hand against geometry inside its own
descendant region, including layered glove surfaces. Inspect the original
neutral scene with the same plan and disclose the overlap. Counts alone do not
separate hand-to-torso penetration from hand self-surface warnings. Do not call
that plan a pure torso test or use a nonzero baseline to dismiss new warnings.
