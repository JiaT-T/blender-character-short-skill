# Experimental shoe geometry adaptation

Use this only after viewing the original captured motion and a fresh proportional fit. Different shoes and target proportions can leave an ankle-joint fit hovering even when joint directions agree. This bounded route consumes an explicitly reviewed external per-frame geometric heel/toe height proxy, original model mapping and source scene hash. It does **not** infer physical contacts, replace source performance with authored body poses, add controllers or generate MMR.

`calibrate_recorded_shoes.py --blend ORIGINAL_FIT --plan EXTERNAL_SHOE_PLAN --output NEW.blend --report NEW.json` temporarily solves exactly four existing original knee/ankle IK constraints without stretch, projects numerical IK rotations to proper rotations, bakes the original leg FK and restores the original constraint mute/stretch state. A bounded constant root-height offset can accommodate reach; relative captured body timing, horizontal root travel and protected upper motion remain. Original rest mesh/weights are retained. Inspect the actual changed silhouette, knees, robe hem, feet and hands before adoption.

The plan declares original four-bone legs, weighted shoe roots, existing IK targets/chain identities, model height/ground, frame range/fps, calibrated ankle pitch, iterations, geometric-height trajectory and error bounds. No role names or motion data belong in the skill. Source IDs are metadata for a reviewed external trajectory; the source scene hash is verified, but the tool does not independently reconstruct a license or guarantee that a proxy is a real contact label. Retain the actual source/witness, license and calibration evidence separately. Shared calibration across excerpts needs the same source BVH/reference and target geometry; do not cancel a new initial foot pose by recalibrating it as neutral.

Current envelope: up to240frames,500000original bone-frames,12iterations/frame,30degree shoe pitch, root lowering at most0.06character heights. Finite values, explicit original constraints, no stretch/leg-length changes, protected body, FK unit scale and actual weighted shoe heights are checked before a new save. Plans reject nonfinite constants, duplicate JSON keys, ambiguous IK mappings and increased limits. Failures have separate failed reports and do not turn an existing output into success. A saved result still awaits independent reopen and visual review.

`verify_recorded_shoes.py --source ORIGINAL_FIT --trial NEW.blend --plan SAME_PLAN --bake-report NEW.json --report REOPEN.json` checks every integer and half frame on fresh scene loads, original geometry, existing constraint state, protected body, leg lengths, unit scale and weighted shoes. It verifies the matching writer/validator/runtime helper versions. Integer/body results and half-frame proxy-height limits have separate booleans. Default exit0 means the inspection completed with integer/body guards satisfied; it does not mean every half-frame height limit passed. Add `--require-half-height` when that limit is required, and keep its failure visible rather than loosening the limit.

Local validation used only Nietiya and two excerpts from the same licensed Bandai capture. The main excerpt's previously amplified180degree near-straight knee flip was corrected separately in the source fitter. Both shoe trials retain open half-frame proxy-height differences; they are not general locomotion, material-point footpin/friction, collision, cross-character or normal-speed naturalness certification. Use the last good complete movie as fallback and keep both source and edited copies.
## Source points and schema2 marker-offset goals

Check the raw source hierarchy before deriving heights. A zero-length BVH leaf
End Site can be extended into a display bone by Blender's importer. Its `tail`
is then synthetic geometry, not a recorded toe-tip marker. Historical local
dance tests used such an extended tail. Their successful numeric sole checks
only show agreement with the configured virtual proxy; they do not establish
source-measured sole height or natural support. Keep those scenes/reports as
experimental history and disclose this assumption.

Prefer explicitly reviewed recorded joint positions when no source foot mesh or
sole markers exist. `marker_height_math.derive` takes2..240 ordered samples with
`frame`, `source_frame`, and both `feet` entries containing `ankle_y_m` and
`toe_joint_y_m`. `calibration` has the same two recorded heights for each foot.
Pass explicit target `scale`, `ground` and `height`. It subtracts each declared
reference height, takes the lower joint displacement, clamps negative offsets
to0, scales and adds ground. The returned detail rows retain negative clamps.
This is a joint-offset heuristic, not measured skin/toe-tip geometry, inferred
stance, force, friction, or complete continuous contact.

Bind source sampling plan/witness, raw-source identity, node names, calibration
frames, scale, the height-math producer and every resulting goal in a separate
local derivation report. Native reference coordinates may only represent an
actual declared capture frame; a synthesized bind reference is not a captured
calibration pose. Do not silently reuse another model, source or reference.

Schema2 keeps the original solver settings and limits but each per-foot row
contains only `target_lowest_sole_z_m`, avoiding a misleading toe-tip name.
It requires `height_proxy` with exactly `kind: recorded-joint-offsets` and
`derivation_report_sha256`. The digest links caller-reviewed evidence; the shoe
validator checks the contract, not the truth of arbitrary external metadata.
Schema1 remains supported for historical explicit proxies. Reports separate
the declared method, integer checks, half-frame failures and viewing limits.

Calibrate the source-to-model neutral foot frames **before** this height pass;
see [library actions](library-actions.md#use-a-real-neutral-foot-reference).
Fixing a source reference is distinct from adding a large arbitrary ankle bias.
Keep the30degree additional-pitch guard and all reach/length/scale limits.

After height correction, inspect the opaque costume as well as the shoes. A
constant body-height adaptation can lower a long hem through an ordinary visual
floor. Display geometry is not automatically a physics collider. Retain exact
floor/skin observations and actual rendered poses; a low sole error does not
validate clothing, physics or naturalness.

