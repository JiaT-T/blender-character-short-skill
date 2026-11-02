# Blueprint dependency identity

`materials.dorm_blueprint` names an external local JSON blueprint. Its image
entries are resolved relative to that file, matching the actual builder.
The pipeline records the resolved blueprint path/hash and every declared image
path/hash before accepting an existing output directory. Changing one image's
bytes while keeping the character JSON and filenames unchanged requires a new
output version. A missing blueprint/image fails before creating the output.

Prefer explicit absolute paths in character input. For an input-only reuse
directory, actually point the configuration at its provided blueprint copy and
localize that copy's image paths to the supplied assets. Copying files without
updating the configuration does not prove that the copied assets were used.
Keep original graphs/settings and verify image hashes when rewriting paths.

This is a blueprint-specific guard. It is not a complete fingerprint of PMX
external textures, add-on binaries or the separate source-GLB/texture-manifest
route. Preserve those assets, versions and a full supplied-input manifest in
the evidence project. Existing source-motion clip/hierarchy hashes and post
profile/LUT/SMAA inputs remain separate pipeline identity fields.

The generic skill contains no blueprint images, model files or character maps.
These remain authorized user inputs with their own source and license records.
Hashing a file establishes identity, not usage or redistribution rights.
