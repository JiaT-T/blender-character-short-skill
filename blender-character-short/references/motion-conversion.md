# Convert permitted local GLB node motion

Use this before source-motion variation when the authorized local input is GLB2
instead of packed-v1 JSON. The converter exports numeric node motion and its
transform hierarchy only. It does not import appearance, infer a rig mapping,
retarget a body, repair foot contacts or prove natural performance.

## Local source and rights identity

Keep the asset and reviewed rights record outside the generic skill. For example,
`rights.json` contains these fields, filled from the actual item and permission:

```json
{"source":"PUBLISHER_ITEM_URL_OR_LOCAL_SOURCE",
 "credit":"ACTUAL_CREATOR_AND_REQUIRED_CREDIT",
 "license":"REVIEWED_ITEM_TERMS",
 "license_url":"TERMS_URL_IF_APPLICABLE",
 "restrictions":"ITEM_SPECIFIC_CONDITIONS_IF_APPLICABLE",
 "modifications":"INTENDED_EXTRACTION_AND_ADAPTATION",
 "source_sha256":"SHA256_OF_THE_REVIEWED_GLB"}
```

`license_url` and `restrictions` are optional nonempty strings; omit either when
not applicable. Unknown fields are refused instead of silently discarding extra
conditions. Preserve the original rights record outside the skill and accurately
carry its item-specific terms into `license`/`restrictions`; do not remove a
restriction merely to satisfy this schema. Duplicate JSON keys are refused in
both GLB JSON and rights records. The report also hashes the exact rights bytes
read once, so later edits cannot be confused with the retained declaration.

The source hash binds these declarations to the file being read. A declaration, successful
download or numerical conversion does not determine rights. Check modification,
use, credit, logo/trademark and redistribution conditions for the particular item.
An acquisition refusal remains stopped; this tool is not a downloader or another
channel for a refused asset. Converted animation can remain restricted even after
the mesh and textures are removed. Do not put raw or derived motion in the generic
skill or a public code release without the required permission.

Run in a Python environment with NumPy, using a new output directory:

```powershell
python "$Skill/scripts/convert_glb_motion.py" --source $ReviewedGlb --provenance $RightsJson --output $NewMotionDirectory
```

When a file has multiple animations, pass an explicit `--animation INDEX`.
Output is `motion-packed-v1.json`, `motion-skeleton.json` and
`conversion-report.json`. Existing output directories are refused. Source bytes
are never changed, and neither external buffer nor image URLs are fetched.

## Supported representation and preservation checks

The subset is GLB2 JSON plus one embedded BIN buffer, float32 tightly packed
ordinary node translation/rotation/scale accessors, and LINEAR interpolation.
Original node indices, child links and static TRS/matrix transforms are retained;
mesh, skin, material, image and logo references are omitted. Matrix nodes targeted
by animation require a separate verified decomposition and are refused here.

Channels may have different key times. Their union becomes the shared packed-v1
timeline; original LINEAR vectors and shortest quaternion arcs are sampled there,
with endpoint clamping. Vector quantization uses9decimal digits; rotations use
24bit smallest-three packing. The existing decoder is unchanged. Each conversion
checks original keys and sampled hierarchy matrices using independent LINEAR/SLERP
interpolation and the existing shared world evaluator. Every original union key
time is mandatory for world-matrix checks, in addition to uniform discrete probes;
keys are never downsampled to make a workload fit. Analytic parent/child
fixtures provide a narrower separate world-transform check; this is not a fully
independent geometry oracle. Every evaluated world matrix and error statistic must
remain finite. Overflow/invalid arithmetic fails before output creation, never as
a zero-error success. The report records original-key and additional-sample counts
and explicitly leaves `continuous_interval_verified` false. Discrete checks do not
prove finite/correct behavior at every time between keys, skin or visual quality.

Unsupported STEP/CUBICSPLINE, morph/extension targets, sparse/normalized animation
accessors, strided animation buffers, required extensions, external buffers,
invalid hierarchies and nonunit quaternions are refused rather than silently
discarded or reinterpreted. This bounded route also rejects values outside its
exact packed-delta integer range. Its explicit resource limits are:

| Area | Supported upper bound |
| --- | --- |
| Source / JSON chunk / BIN chunk / rights record | 64MiB / 8MiB / 56MiB / 256KiB |
| Nodes / hierarchy depth | 2048 / 128 |
| Channels / samples per accessor / decoded scalar components | 1024 / 100000 / 1000000 |
| Shared timeline / channel-times / resampled scalar components | 100000 / 250000 / 1000000 |
| Validation `(nodes + channels) × probe times` | 250000 |

Files are size-checked and read with a bound; only the two supported GLB chunks
are examined. Hierarchy depth/cycles are checked iteratively before the recursive
legacy evaluator. Cumulative accessor and resampling budgets are checked before
copying/sampling; validation traversal budgets every original key plus its extra
samples. If that exceeds the existing product bound, conversion is refused before
packing. Some previously accepted clips therefore no longer fit, rather than
losing key coverage or silently increasing the budget. These are
supported-input limits, not a universal wall-clock/memory guarantee. A larger
workflow needs a separately verified implementation or budget, not an unexplained
recursion-limit increase. This is not an arbitrary glTF/FBX animation importer.

The [Khronos glTF2 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
defines animation accessors, channel targets and interpolation, including the
shortest quaternion arc. The converter implements the supported subset in
original code; it does not bundle Khronos sample assets.

## Verify the converter, then the performance

```powershell
python "$Skill/scripts/verify_glb_motion.py" --output $NewCpuVerificationDirectory
```

The verifier generates its own tiny numeric GLBs. Tests cover an analytic parent
turn with a child on an independent timeline, clamped endpoints, antipodal
quaternions, explicit animation selection, appearance stripping, invalid hierarchy
and unsupported-format rejection, reviewed-file hash refusal, CLI output identity
and source preservation. Additional cases include finite local matrices that
overflow at rest or during animation, positive/reverse hierarchy-depth boundaries,
actual CLI product/accessor/node/validation-budget refusals, and contradictory or
extra rights fields. Refusals must leave no output directory or success report.
An isolated original-key scale peak in a200key track is checked even when the
older sparse probes missed it; a finite peak is checked as a positive control.
A supplied validation plan that omits any original key is refused.
It records a CPU result and log; no Blender, network,
third-party asset or character is required.

Converted indices can be mapped explicitly into the existing
[rotation-only variation](source-motion.md) route. Verify source facing, target
rest landmarks and the proper basis before choosing mappings. Translation tracks
in the exported data do not mean that rotation-only variation drives root travel.
Walking/full-body fitting, heel/toe contact, stop transitions, body/cloth clearance
and normal-speed viewing need separate real-character evidence.

In one local licensed-source check,57channels/22nodes/48samples converted with
original-key vector error below0.000001, quaternion error below0.0001degrees and
sampled world-matrix error below0.000001. Earlier separate Nanami FK/footplant
prototypes and a native8s story existed, but the new converter was not run through
Blender because automatic startup was blocked. No complete library-motion short,
natural stop, clean-context full-body reuse, another character or continuous
visual acceptance follows from this CPU result.

Adding these scripts changes the pipeline's script identity even though existing
Blender runtime scripts are unchanged. Keep each historical producer with its
scene/video; use a new directory for future pipelines rather than transplanting
the new scripts into an old render cache.
