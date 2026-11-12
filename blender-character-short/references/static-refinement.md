# Saved-project static refinement (v46)

This executable route takes a reviewed saved Eevee project and an explicit JSON
plan, creates a verified byte-for-byte backup, applies bounded changes, saves a
new copy and reopens it. It never changes the source or chooses assets/style for
you. No private absolute paths, model names or materials are built into the code.

## Entry

Add `refine_plan` to an external production project JSON. Run the existing doctor
for that runtime, then `python -B scripts/short_project.py refine --project PROJECT.json`.
The canonical entry retains the shared execution lock and background/offline
Blender execution. For an already coordinated native process, the module can be
called with `blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python scripts/refine_saved_project.py -- --plan PLAN.json`.
Do not run concurrent scene writers. This command does not render or animate.
Use the saved project's actual output hash with the existing `render.source`
contract for subsequent rendering. Never reuse an old frame receipt after changes.

## Compositor example

```json
{
  "schema": 1,
  "source": {"path": "reviewed-character.blend", "sha256": "REPLACE_WITH_ACTUAL_SHA256"},
  "backup": "backups/character-before.blend",
  "output": "projects/character-refined.blend",
  "report": "reports/character-refine.json",
  "samples": 32,
  "compositor": {"gain": 0.025, "coverage": true, "device": "GPU", "precision": "FULL"}
}
```

All paths are relative to the plan unless explicitly absolute. Source, backup,
output and report must be distinct. Existing outputs/reports/backups are refused;
a failed candidate is kept with an unaccepted report, not silently retried.

The compositor adapter requires the reviewed Huaxu-style topology. Default
selectors are `HuaxuPost_Premultiplied to straight`,
`HuaxuPost_Approximate weighted Fog Glow` and the three
`HuaxuPost_Conservative Bloom gain 0/1/2` math nodes. Override `premultiply_node`,
`glare_node`, `gain_nodes` and `prefix` only for a reviewed equivalent graph.
It does not build a look from generic MMD materials.

Coverage-aware glow uses the tested approximation
`1.055 * max(premultiplied RGB, 0) ** (1/2.4) - 0.055` for the glow branch only.
It is not an exact website MRT or general sRGB implementation. The added Value
controls select the original versus coverage branch and the gain. The main
material formulas, curves and LUT remain intact. GPU/FULL changes compositor
execution, not the selected 3D renderer. A 32-sample choice is a tested local
tradeoff, not a universal quality guarantee. No high-contrast grade, Kuwahara,
second global bloom or reference fringe-shadow implementation is installed.

## Scene-only operations

A plan may instead contain `scene` (or combine it with `compositor`). Supply:

- `schema: 1`, `objects`: exact stage object names, `collection`: an existing
  receiver collection containing exactly those objects. Stage mesh, root empty
  and armature objects are allowed; their geometry and rig are protected.
- `materials`: explicit stage material rows with `name`, optional `inputs`,
  `quiet` and `contact` arrays. Shared materials used outside the stage are refused.
- `lights`: existing scene-only light rows (`name`, `energy`, optional `size` and
  `color`). They must already use that exact receiver collection and not share
  data with another light. Original character lights cannot be relinked here.
- `add_lights`: new area lights with unique `name`, `location`, `target`, `energy`,
  `size` and `color`, linked only to the stage receiver collection.

```json
{
  "schema": 1,
  "objects": ["ReviewedStage"],
  "collection": "StageOnly",
  "materials": [{
    "name": "ReviewedFloor",
    "inputs": [{"node": "Principled BSDF", "socket": "Roughness", "value": 0.88}],
    "quiet": [{"name": "QuietFloor", "source_node": "FloorTexture", "source_socket": "Color",
      "target_node": "Principled BSDF", "target_socket": "Base Color",
      "factor": 0.28, "color": [0.01, 0.006, 0.011, 1]}]
  }],
  "lights": [],
  "add_lights": [{"name": "RecessFill", "location": [-3, 2, 2],
    "target": [-3, 6, 2], "energy": 100, "size": 3.8, "color": [0.7, 0.78, 0.9]}]
}
```

`quiet` inserts a controlled color mix into an exact existing RGBA link.
`contact` uses the same name/source/target keys with `distance`, `strength`,
`minimum` and `samples`, inserting bounded AO multiplication. Distances are scene
units. Confirm scale and inspect the rendered sole contact; AO does not fix
floating geometry. Existing AO distances/mixes can use explicit `inputs` edits.
Do not combine multiple insertions into the same link. Connected inputs,
unsupported targets, nonfinite/out-of-range values and name collisions fail early.

## Validation and limits

Before and after saving, the wrapper compares protected geometry, rigs, actions,
cameras, character materials, world, source color management and timing. Only
explicit scene materials/lights and requested compositor/sample settings may
change. A complete post-edit state is compared again after reopening. Used or
fake-user image identities are protected; Blender may discard unused orphan
images on save. The original file remains unchanged and its full backup remains.

Reports include source/output/backup hashes, producer identity, plan identity,
changes and acceptance. Acceptance means static technical preservation, not
visual approval, frame-to-frame stability, collision resolution or physics.
Run static before/after comparisons at matched settings before adopting a plan.
For wide bloom/DOF and performance, separate whole-frame timings from isolated
node costs. Do not impose dynamic validation on a static-only request.

Local validation targets the existing character and stage described in the
[iteration notes](scene-render-iteration.md). A plan must be adapted to
other assets; this is parameterized execution, not automatic aesthetic judgement.
