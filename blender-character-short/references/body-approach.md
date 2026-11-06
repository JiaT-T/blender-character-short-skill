# Configured local body approach

Use this narrow opt-in route when a reviewed local node-motion fragment fits
the story's approach, stance and stop. Begin with the goal, obstruction and
visible outcome. Build an open travel path, reachable interaction and matched
low-cost complete preview before increasing render quality.

This is proportional torso/limb FK fitting followed by configured contact and
an authored transition on the original rig. It is not general FBX/Mixamo
retargeting, automatic action acquisition, arbitrary-character compatibility or
naturalness acceptance. Historical approach cases use Nanami; the later [body motion remix](body-motion-remix.md) case separately fits an adult rig. These do not establish arbitrary-character compatibility. Schema1
starts already moving. Schema2 optionally prepares an explicit measured ready
stance and acceleration; read [grounded launch](grounded-launch.md) before use.

## Inputs outside the skill

Keep the PMX, character mapping, story, source motion, rights and lookup images
outside the generic package. Never upload the user's model to an online rigging
service without separate authorization. Retain source-specific usage,
modification, attribution and redistribution conditions with local inputs.

The body plan supplies these exact fields:

| Field | Required content |
| --- | --- |
| `schema` | Integer1, or integer2 with the exact additional `launch` object documented in grounded-launch.md. |
| `source.files`, `source.sha256` | Five matching keys: `clip`, `skeleton`, `conversion_report`, `source_glb`, `provenance`; local paths and reviewed lowercase SHA256 values. Relative paths resolve beside the plan. |
| `fps`, `basis` | Integer frame rate and proper orthonormal3x3 source-to-world basis. |
| `body`, `hips` | Ordered `{bone,source}` mappings for original torso/head controls, with the named hips in that body list. |
| `limbs` | `left_leg`, `right_leg`, `left_arm`, `right_arm`; each has `bones` and source-node indices. Legs have upper/knee/ankle/toe; arms have upper/elbow/wrist. Use real anatomical joint heads, not display tails. |
| `scale_reference` | `bones` and `source` for the first three joints of one mapped anatomical leg. |
| `feet` | `left` and `right`, each with actual weighted `deform_root` and ordered integer-frame `contacts` pairs. Inspect the original rig's deform dependencies; a control bone may not own shoe weights. |
| `weight_threshold` | Explicit value in(0,1] for selected skinned foot/feature vertices. |
| `travel` | Horizontal unit `direction`, `sole_height`, `maximum_vertical_change_H`, `fit_threshold_H`, `speed_range_H_per_second`, and `grounding_mode`. |
| `release_frames` | Integer1..12 for stance residual release. |
| `compose` | `gait_start`, `minimum_stop_frames`, `maximum_stop_frames`, `reference_side`, `landing_lift_H`, `target_object`. Current target is the actual `Story prop`. |

Use the existing [motion converter](motion-conversion.md) first. The fitting
stage checks all five byte identities, retains supported rights conditions and
recomputes the conversion from the local GLB. Its skeleton and packed clip must
match those recomputed data exactly. A provenance label alone is insufficient;
the tool does not grant or determine legal rights.

The story supplies an explicit integer `body_interaction_frame` on its original
source timeline. The measured stop must finish by that frame and before any
required held-prop contact. Keep actor root stationary before interaction in the
authored scene; existing root motion is not silently replaced. The character
must provide calibrated `stationary_support` on the original leg bones, with
the declared knee/ankle IK route already muted in the authored scene.

## Fit, travel, stance, stop

`run_short.py --body-approach-plan PLAN.json` performs four stages after the
ordinary story build, before optional hand recovery, elbow, gaze and whole-scene
tempo. Use a new pipeline output directory.

1. `body-fit`: fit torso rotation/root bob and limb joint directions from the
   reviewed fragment to original segment lengths. Ankle/toe orientation is
   transferred; wrist-relative orientation remains original. Fingers and
   story-specific palms remain separate acting inputs. Rest hierarchy, mesh
   vertices, weights and morph geometry are verified unchanged.
2. `body-travel`: fit constant forward speed from finite near-stance ankle
   motion. `raise-only` corrects floor penetration while retaining source flight.
   `lowest-sole` is a different, explicit signed-height adaptation; forcing a
   flight phase onto the floor can make the body jerk and is not a walk fix.
3. `body-plant`: constrain selected actual material vertices during reviewed
   stance intervals, with rolling pivot switches and bounded residual release.
   It preserves protected upper-body/world-root data. A too-long stance or
   tighter target that exceeds original reach is rejected before saving; do not
   force the solver or call a clamped result a passed contact.
4. `body-compose`: align a final material stance to the authored pose, fit a
   bounded deceleration and reference-foot stop, and land the free foot. Head
   attention uses the real prop and original limit. Original prop trajectory
   and every bone world pose from stop end onward are verified preserved.

The gait and author scene must share original rest/mesh/weight/morph data,
actor-relative rig transform and constraint configuration. Original constraints
are not replaced. Quaternion/location channels are supported; driven/NLA roots
and unhandled authored channels are refused. This route requires stable vertex
topology and unit-axis actor/unit-scale rig transforms.

Current limits:2..240 uniformly sampled source frames,256source nodes,
2048target bones,500000target bone-frames; source hierarchy/conversion work has
the converter's separate bounds. Source scale/shear/reflection and nonfinite
worlds are refused. Each body record binds16producer/dependency files; the
pipeline also binds all scripts and all five external source files.

Material solving stops iterating within.00003H and requires pivot error within
.0001H. Final saved-output audit uses its own declared tighter checks. These are
numeric tolerances, not a physical friction model or perceptual naturalness.

## Make the scene support the performance

Measure real head/hair and shoe clearance while traversing the complete path.
A decorative sill across the opening or a low lintel can invalidate a working
gait. Position the landing object and camera so the stopping feet and missed
reach remain visible. After the result is established, use a closer reaction
shot that still includes the hands needed to read it.

Distinguish the character's reference `ground` from the actual studio floor.
`set.floor_offset_H` explicitly offsets that plane, bounded to one percent of
character height; legacy default is-.003. For an aligned ground plane choose0
and calibrate a small positive sole margin from actual skinned geometry in the
character's stationary-support targets. Do not reuse one character's ankle or
sole offsets on another model without measurement.

## Verify the saved result

Run the actual frozen producer from raw inputs in a clean directory, then use:

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/audit_body_approach.py -- --pipeline OUTPUT --character CHARACTER.json --plan BODY_PLAN.json --gaze-plan GAZE_PLAN.json --framing-plan FRAMING_PLAN.json --report NEW_AUDIT.json
```

The audit binds the actual rendered scene and producer. It checks all output
integer frames for whole-character/external triangle surfaces, reference-ground
bounds and actual floor clearance separately, source-anchored stance/stop
positions, repeated-point drift, original head/eye bounds and required gaze.
An exit0 means inspection completed; read `technical_checks_pass` and every
check. Single-sample groups have an absolute anchor check but no drift
measurement. Fractional source contact mapping is explicitly unverified.

[Story framing](story-framing.md) adds data-authored in-frame requirements.
Neither it nor a clear triangle-surface test proves volume containment,
self-collision, visible irises, subframe safety, physics or normal-speed acting.
View the complete film and preserve sampled/continuous/listening limits.


## Inspect the supplied shoe and the visible action

A minimum weighted foot vertex at the ground and a fixed material point do not
prove a broad sole contact or natural support. Compare the original imported
rest geometry with the saved stop from side and front. A designed heel can
have separate front-sole and rear-heel supports; preserve that geometry rather
than flattening the foot to match an assumed shoe. Keep diagnostic clay/subset
views distinct from actual delivered-camera images and continuous playback.

Read support and flight phases in the complete intended action. A source clip
with obvious flight must not be reported as accepted steady walking merely
because the source label or import succeeded. Use a pace that serves the plot;
retain normal-speed naturalness as unverified until it has actually been viewed.

For a catch, inspect the prop silhouette against the palm, cheek and background
after the final camera/time map. Zero surface intersections and a valid chain
do not establish a readable catch. Preserve failed gaze/contact criteria; do
not loosen limits or move a nominal target just to obtain a passing report.
