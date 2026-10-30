# Source rendering contract

Record page/variant/coating, asset and source-bundle hashes, runtime parameters and matching conditions for each profile. [S] source code, [G] observed runtime, [B] Blender output and [A] adaptation are distinct. Node creation, formula tests, actual rendering, visual agreement and temporal stability are separate claims.

Use the same GLB first when PMX geometry/UV/normals differ. render_source_probe.py consumes an external Dorm blueprint; render_character_probe.py consumes a Character profile and extracted textures. Keep stage radiance, Bloom weight and useful AOVs. Numeric differences require genuinely matched inputs.

## Postprocessor

source_post.py consumes bottom-up scene-linear rgba and weight arrays, JSON profile and a 32³ LUT in a 1024×32 PNG. LUT is data, not sRGB color. The implemented profile supports half-float targets, 4-tap half-size box, no-toe encode, weighted threshold, oversized reduction, fixed 256/128/64/32 separable blur levels, configured kernel/level weights, base unpremultiplication, source curve, trilinear LUT, final premultiplication and RGBA8 storage.

Non-HDR scene storage is sRGB8_ALPHA8; weight/Bloom targets are linear8. verify_post.py checks algebraic inputs, zero alpha/weight, oversized reduction and nonfinite rejection. It does not prove source GPU rasterization or the applicability of a runtime profile to another model.

Optional source-derived SMAA is implemented and tested on two CPU sequences; see [antialiasing](antialiasing.md). Full website GPU numerical parity remains pending. Eevee transparency/AOV accumulation does not automatically reproduce source depth/stencil/MRT. These gaps cannot pass strict reproduction.

## Material adapters

Dorm: external blueprint describes known body math/channels. The source-GLB outline adapter uses skinned smooth normals/tangents, camera-space displacement and vertex-color discard. The integer-frame bake supports tested skin/camera animation on the source GLBs; see [outline](outline.md) for cache verification and unsupported cases. It is not automatically transferred to production PMX. Separate PMX face/eye geometry uses an explicit flat-texture adapter; it does not claim website FaceMap UV1 equivalence.

Character: character_material.py implements supplied main/mask/normal, linear first-shadow transition, second-shadow gate, Face alpha/mirror, rim, stocking and MatCap math. Face transition uses _SmoothFactor. Production bakes evaluated head Y/Z axes into named nodes every frame, avoiding unsaved handlers.

Environment cube fallback is diagnostic. HairHET/stencil, weight-only passes, shadow maps, custom transparent depth/MRT remain unresolved; source SMAA GPU equivalence is still pending. Blender Normal Map is an adaptation until tangent interpolation equivalence is proven. Test branch applicability per character.

Migration requires actual UV/channel/material checks. Similar filenames can have very different color layouts. Optional nearest-UV vertex-color transfer reports distances but does not establish geometric equivalence. Keep mappings/provenance in external character configs.

After baseline validation, separately test creative lights, backdrop and exposure. Do not cover wrong inputs with extra exposure, generic Shader-to-RGB ramps or arbitrary Fog Glow. Stage/prop shaders are creative adaptations.

## Formula fixtures

Run verify_character_formula.py inside isolated background Blender with --builder scripts/character_material.py, repeated --cases references/character-formula-cases.json and --cases references/character-formula-additional-cases.json, plus --output NEW_DIRECTORY. Eleven actual cases cover linear shadow transitions, second gate, Face alpha/mirror, specular, rim, SkinRamp and MatCap. Expected values are independently calculated from source formulas; fixed normal/view vectors exclude geometry-space validation. Default tolerance .001 accounts for observed Eevee half-storage; reports also retain a stricter .0002 check. Do not promote all shader/geometry behavior from these fixtures.

Outline attributes must be enabled by the verified shader variant, not attribute presence. Dorm outline has no vertex-color keyword; its control vector is one. Corrected static probe records vertex_color_enabled=false. Earlier probe wrongly used sparse vertex B and remains a failed diagnostic.
