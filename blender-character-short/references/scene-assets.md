# Local static scene assets

Use an imported set piece only when it gives the character a needed route,
support, obstacle or visible consequence. Inspect its scale against the actual
reach and its surfaces against the complete action. A model that imports is not
an accepted scene. Acquire the file through an authorized source and review the
individual license, modification, credit and redistribution conditions first.
Record unavailable resources rather than substituting a download claim.

The optional `set.imports` route accepts a local, self-contained GLB v2 with
static triangle meshes. It excludes rigs, animation, cameras, lights, textures,
morph targets, external buffers and required extensions. Convert and review a
more complex licensed asset separately; do not silently discard its moving
parts or claim that this route handles them.

```json
{"name":"Workbench","file":"assets/workbench.glb",
 "sha256":"ACTUAL_REVIEWED_FILE_SHA256","height":0.56,
 "position":[0.34,-0.314,0],"rotation":[0,0,0],
 "materials":{"Source enamel":"ivory","Source frame":"slate"},
 "purpose":"Support the loose part and leave the catching approach open",
 "source":"Recorded publisher/file URL or original-geometry provenance",
 "license":"Recorded license evidence and required credit"}
```

`file` resolves relative to the story JSON. `height` is the imported mesh's
vertical extent in character heights. The importer finds the source meshes'
world bounds, moves their bottom-center to the origin, scales uniformly to that
height, applies XYZ degrees, then places that anchor at `position` in character
heights with the character ground added to Z. A rotated piece's final vertical
extent may differ. Inspect the imported bounds and contact surface; do not infer
that an arbitrary origin or a catalog's unit matches the story coordinates.

Map every distinct source material name to a key in `set.materials`. The imported
mesh uses those story shaders, so it can share the selected static
[matte treatment](scene-style.md). Original asset textures/shaders are outside
this route. Luminous or animated story materials retain their separate styling
restrictions. Character materials are not remapped.

An import name must fit 32 UTF-8 bytes and be unique. Source material names must
not collide with existing Blender material names; namespace them in a reviewed
asset copy if needed. Imported object names may be truncated by Blender; the
saved `scene_asset_source_name` custom property preserves the complete original
name. Use the report's mapping for diagnostics. Imported, replaced, unused
materials are removed, allowing another instance of the same asset under a
different import name.

The build report records hashes, provenance declarations, source bounds, scale,
objects and material bindings. `run_short.py` fingerprints actual GLB bytes
before using saved output. A changed file, declared hash or producer needs a new
output version. These checks establish identity, not legal permission. Keep
third-party binary assets and their license files outside the generic skill ZIP.

Validate the default no-import branch, imported placement under different scales
and rotations, unchanged character/prop/camera performance, actual palette and
shadow appearance, entry/hold/release clearance, reopening and full postprocessed
preview. Original self-created fixtures can test the mechanism; report them as
such. They do not establish third-party environment, motion-library, continuous
viewing or physics acceptance.
