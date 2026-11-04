# Optional measured ready stance and launch

Use only when the character must visibly notice the story target before
walking. A moving source fragment does not supply a convincing start by itself.
Keep the target, opening shot, travel direction and final interaction reachable.

Body plan schema1 retains its previous behavior. Schema2 requires exactly the
schema1 fields plus `launch` with these fields:

| Field | Meaning |
| --- | --- |
| `hold_frames` | Integer1..120, explicit ready hold. |
| `ramp_frames` | Integer3..48, intermediate acceleration frames. Ramp duration is `(ramp_frames+1)/fps`. |
| `reference_side` | `left` or `right`, matching the compose reference; source first frame must have an actual material stance on this side. |
| `crouch_H` | Finite0..0.08, character-height normalized ready root lowering. Choose by original leg reach, not appearance alone. |
| `free_lift_H` | Finite0..0.08, bounded free-ankle lift during launch. |

Set `compose.gait_start = hold_frames + ramp_frames + 1` exactly. The authored
timeline must already include this interval and retain a stationary actor root
before interaction. Shift prop, expression, hand/elbow, gaze, camera and tempo
plans together when introducing new story time. Do not silently replace an
existing moving author approach.

The helper measures source-first travel speed and computes the quadratic root
acceleration distance. It holds the actual reference shoe orientation and
selected skinned material point. The free ankle approaches the source-first
pose with a Hermite tangent measured from the first two source world states;
the declared lift is separate. Original two-bone lengths and evaluated shoe
vertices determine reach and ground clearance. Unreachable original legs or
excessive floor corrections reject the attempt before a composed scene is
saved. Never accept a clamped solution or stretch the original rig.

The selected reference shoe can use a different orientation from the author's
late stance. Both source and authored scene still require identical original
rest geometry, mesh, weights, morphs, actor-relative transform and constraints.
The compositor verifies original authored bone world states from stop end and
the entire authored prop trajectory; launch owns its declared pre-gait frames.

Run saved-output `audit_body_approach.py` after rendering. Launch anchor samples
and errors are reported separately from gait/stop, with explicit sample-presence
checks. Apply an integer-preserving tempo map through the whole ramp/gait/stop
if changing its speed; inspect actual output root increments at both joins.
Sparse poses or an unchanged source pose do not establish velocity continuity.

Current production evidence: one Nanami Q rig, a10second fresh-input story and
dense saved join inspection. This is not a general walk-start library, motion
matching, balance/friction simulation, full-body derivative continuity, subframe
clearance, cross-character or normal-speed naturalness acceptance. Hold duration,
attention, free-foot support and shot transitions still require actual film
review. Preserve failed reach attempts and the previous best output.
