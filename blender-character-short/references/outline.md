# Source GLB outline bake

Use this optional path for an algorithm baseline with the **same source GLB**.
It is not a PMX outline reconstruction. Supply an already matched probe scene,
the original GLB, an explicit global tint, a new output path and a contiguous
integer frame range. The scene must retain `source_mesh_index` and
`source_material_index` from `render_source_probe.import_glb`.

```powershell
& $Blender --background --factory-startup --python-exit-code 1 --python "$Skill/scripts/bake_source_outline.py" -- --scene INPUT.blend --glb SOURCE.glb --output NEW.blend --report BAKE.json --start 1 --end 48 --tint 1 1 1 --remove-legacy-outline
```

`--remove-legacy-outline` removes only the prior diagnostic hull named
`Source outline projected hull` in this newly loaded working scene. Historical
files are never saved over. Explicit source material `extras.passes` indices
select outline passes; names are not unique and must not establish bindings.

The bake restores source N/T, applies the linear bone transform even when
vertex positions are unchanged, forms B after skinning, and reconstructs the
smooth direction from the source attribute. The camera-space displacement uses
projection Y, view depth, distance scale, width and the effective vertex B
control. World-space absolute shape keys save every integer frame, including
camera changes, without handlers. Source-named relative POSITION-only morphs
are applied before linear skinning. Imported Basis and every active target delta
must agree with the source GLB, including sparse accessors. Absolute keys,
vertex-group masks, non-Basis relative keys, shape-key preview overrides,
NORMAL/TANGENT targets and unsupported deformation are rejected. A GLB without
verified target metadata retains the active-morph rejection.

Source `lf` converts outline color parameters to linear RGB. Multi-color ranges
are inclusive: `.5`, `.7` and `.9` add the adjoining bands. Effective B below
`.1` discards; B exactly `.1` remains. Brightness and global tint multiply RGB;
Bloom weight is an independent AOV. Uniform/keyword activation, not attribute
existence alone, enables the vertex control. The source color's alpha component
does not replace the fragment shader's opaque alpha.

Reopen and verify before use:

```powershell
& $Blender --background --factory-startup --python-exit-code 1 --python "$Skill/scripts/bake_source_outline.py" -- --scene NEW.blend --glb SOURCE.glb --report REOPEN.json --start 1 --end 48 --tint 1 1 1 --verify-only
```

Rebake after changes to pose, morph values, camera, projection, aspect, topology or outline
parameters. `render_performance.py` checks the original GLB hash and the entire
requested cache range before using or skipping frames. Its renderer script
hash is part of the raw-output identity. Preserve the original GLB at the
recorded source path for this validation; the saved mesh itself is self-contained.
This automatic check covers geometry and the original asset hash, not arbitrary
manual edits of material nodes or the cached control attribute. Keep those
frozen, or rebuild and inspect a new version; a geometry check does not certify
their unchanged values.
Use `--extra-aov SourceOutlineMask` to retain the actual mask in EXRs and NPZs.
Raw checkpoint Composite and source postprocessing remain separate stages.

## Evidence scope, 2026-10-29

Pinned source `C69G59uD2.js`, SHA-256
`172188ea0193106745299323b5b2e2ac9cc8b7d33535e6d538798b1685dd8d9e`:
`ug`, `dg`, `fg`, `pg`, `gs`, `lf`, `xs` establish parameters, geometry,
fragment bands, defines, skinning, color conversion and Bloom output [S].
The imported `B45uel9l.js` SHA
`5377cf3a4b90eb8c919d6e2f16125e56ca948a15f262713ec8a621515d964cd4`
contains `normalizeSkinWeights` at character offset 141502 [S]. Positive weights
are divided by their sum; zero weights fall back to (1,0,0,0). The two tested
assets have positive, nonzero sums.
The implementation's unweighted-vertex fallback has not reproduced the source
first-joint fallback; assets with zero weight sums are outside verified scope.

- Both source GLBs: 48-frame head/camera/lens bake, saved-scene reopen and every
  cached coordinate checked; maximum world error 1.1921e-7 [B]. Nanami Dorm has
  one pass; Nietiya coating 6005905 has nine explicit pass bindings. Nietiya's
  Cloth control B is zero throughout, so that pass discards; actual Cloth does
  not validate the visible multi-color branch.
- Ten geometry/negative-input checks include the stationary-position, rotating-
  tangent counterexample, varying depth/FOV/width, and active-morph rejection.
  Changing the saved camera was independently rejected for both characters [B].
- Twenty synthetic Eevee color/discard/Bloom AOV fixtures passed absolute
  tolerance .002. Maximum observed difference .0015625 includes render storage
  precision; do not relabel this as bit-exact shader parity [B]. Use
  `verify_source_outline.py --oracle CASES.json --output NEW_DIR` in factory
  Blender; the independent scalar oracle is a supplied test input.
- Both characters produced matched outline-on/off 48-frame, 24 fps, 640x360
  diagnostics and full-file decode. Frames 1/24/48 were sampled visually.
  In all 48 frames, every changed raw pixel was inside the positive outline AOV;
  off masks were zero. Q hair/silhouette separation increased; Nietiya's close
  hair silhouette change is subtler. This is an on/off implementation check,
  not website camera-matched appearance or continuous playback acceptance [B].
- Historical Q Dorm GPU draw 34/program39 supplies matching width, distance,
  offsets, brightness, Bloom and tint=1. Source uses reversed depth there;
  GEQUAL must not be interpreted without that convention [G, historical].
  Nietiya's runtime global tint remains unverified; input tint=1 is diagnostic [A].

Still unpassed: source GPU numerical equivalence, source depth/stencil/order and
transparent MRT coverage, subframe/motion-blur behavior, NORMAL/TANGENT or
nonrelative morphs, PMX smooth-attribute migration and continuous visual inspection. Front-cull
geometry is adapted as reversed winding plus backface culling [A]. Do not count
these gaps as strict rendering acceptance.

## Relative POSITION-only morph extension

The pinned source bundle's `ps/ms/hs/gs` vertex paths evaluate morph positions
before skinning; `au` shares the original morph influences with its outline.
The source GLTF loader uses relative targets and applies sparse accessor values
as overrides, including an implicit zero base [S]. `glb_morphs.py` reads only
unnormalized FLOAT VEC3 POSITION targets and rejects unsupported layouts.
Zero-weight targets do not alter the mesh. For POSITION-only targets, source
normal and tangent attributes remain unchanged before their skin transforms;
do not recompute smooth normals as an undocumented replacement.

Actual extension evidence: seven CPU accessor fixtures, seven Blender cases
(two weighted shapes, mute behavior and five rejection boundaries), a Nietiya
24-frame blink/mouth diagnostic, and both prior 48-frame outline regressions.
Changing a morph after bake was rejected as stale, without changing the saved
scene. The actual evaluated synthetic mesh differed from the independent
relative-key sum by at most 2.15e-8 world units [B].

Nietiya on/off outputs both decoded as 24 frames at24fps. All raw changed pixels
were inside the positive outline AOV; off masks were zero. Frames1/7/13/19/24
and enlarged face crops were actually inspected: eye narrowing and mouth
movement are visible, without an obvious detached contour in these samples.
The on/off contour difference is subtle at640x360. This is a source-GLB diagnostic,
not a PMX morph result, continuous viewing or website-GPU equivalence [B/A].
Q shares the old skin/camera regression; active Q morphs were not tested.
Evidence: project `lab-v06-01/outline-morph`, `outline-morph/research`, and the
read-only review record. Keep the same asset hash and explicit runtime scope.
