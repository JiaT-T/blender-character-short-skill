# Wrist-preserving elbow posing

Use this optional stage when the wrist choreography works but the upper arm,
forearm or sleeve needs a different silhouette or clearance. The tool captures
the original evaluated wrist and re-solves the existing three arm controls
around a chosen elbow pole. It does not edit rig rest data, weights or joint
limits, and it refuses active arm IK. It requires a positive uniform armature
world scale and an existing authored arm action.

Choose the pole from the actual character and shot. Lowering an elbow helped
one tested sleeve; it is not a universal pose rule. Keep the bones in the
external character mapping as `left_arm`, `left_elbow`, `left_wrist` or the
corresponding right-side roles. A chain may contain existing helper ancestors.

The external plan is frame-exact, without implicit duration scaling:

```json
{"schema":1,"side":"left","start":67,"blend_end":78,"end":336,
 "pole":[0.5,0.12,0.15]}
```

`pole` is a world position in character heights; ground is added to its z.
The pole blends from the original evaluated elbow position to that world
position, using smoothstep from `start` through `blend_end`. The chosen pole
then remains in use through `end`. Use a deliberate recovery or a suitable
end frame if the original elbow pose must resume; inspect that boundary.

For a temporary clearance correction, schema2 adds an explicit smooth return:

```json
{"schema":2,"side":"left","start":30,"blend_end":35,
 "release_start":55,"end":74,"pole":[0.4,0.0,0.08]}
```

Require `start<=blend_end<=release_start<end`. Entry uses the same smoothstep;
after `release_start` its weight multiplies a smoothstep falloff to zero at
`end`. The last frame exactly restores the originally evaluated arm direction,
while every wrist world pose remains protected. This avoids a hard return just
after the correction window. Poles below the floor are allowable direction
guides, not actual elbow targets or rendered objects. Inspect the real limb.
Sparse story FK key changes do not give the same guarantee between keys.

```powershell
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python "$Skill/scripts/bake_elbow_poles.py" -- --blend $BuiltScene --character $CharacterJson --plan $ElbowPlan --output $NewScene --report $NewReport
```

Existing outputs are refused. The saved report binds the source and output
scene, character, plan, writer, plan validator and base solver hashes. It
verifies original wrist world position and sign-invariant rotation, protected
bone matrices, all other object matrices and the changed arm outside the
requested window at every integer frame. Original segment lengths are used
to preserve an already evaluated wrist point; this does not enlarge authored
reach targets. Work is limited to1,200frames and500,000combined bone/object
frames. Nonfinite original/evaluated matrices, poses and quaternion angles fail
before a success report; they cannot be hidden as zero comparison error.

`run_short.py --elbow-pole-plan $ElbowPlan` runs this after optional hand recovery
retiming and before optional gaze baking. The renderer uses the resulting
scene. Cache identity includes the plan and all producer scripts; changed
inputs need a new output directory. Omitting the option preserves the ordinary
stage route.

To keep two separate arm corrections, append ordered
`--additional-elbow-pole-plan NEXT_PLAN.json` options after a primary
`--elbow-pole-plan`. Up to8total stages are supported. The first retains the
legacy `elbow-pole` path; later stages use `elbow-pole-2`, `elbow-pole-3`, etc.
Each plan identity, input/output scene and stage evidence is checked separately.
Reversing the order changes the identity. Duplicate plan paths and additional
stages without a primary are refused. All stages run before final gaze/tempo;
inspect their combined final scene, not just individual stage reports.

## Acceptance

Reopen the saved result. Check the wrist and the full arm against the prop,
head, peer hand, sleeve and destination geometry. Directional palm rays only
sample the hand; a supported tile can still intersect a sleeve. A destination
rim can block the approach even when the final resting tile fits. Design an
open loading edge where the action needs it, and inspect entry and withdrawal.

Re-sample the palm footprint after posing, then render the actual shot and a
complete preview. Preserved wrist geometry and successful decoding do not
establish natural acting or continuous viewing. This stage does not solve
sliding, friction, general collision or subframe motion.

`verify_elbow_poles.py --output NEW_DIRECTORY`, run inside factory-startup
Blender, generates its own small rigs for save/reopen, transformed moving
parents, wrist attachments, constraint dependencies, no-op, quaternion sign
equivalence and invalid-input/refusal checks. It uses no user asset. Synthetic
verification does not constitute cross-character artistic validation.
