# Optional post-contact arm recovery timing

Use this only when an already readable recovery happens too abruptly. Preserve
the contact performance first. Editing a later sparse pose key can change the
Bezier curve before that key, including the earlier grip and moving prop. A
lower peak angular step alone does not establish better acting.

Supply an external JSON plan, for example:

```json
{"side":"left","source_frames":[301,313],"output_frames":[301,333],"timing":"smoothstep"}
```

These example frames belong to one 24 fps story; derive new frames from the
actual plot and contact report. Both intervals must start at the same integer
frame, fall inside the saved scene and begin after every active prop-contact
transition in the build report. Timing may be `linear` or `smoothstep`. The plan
does not authorize rewriting a held interval or solving an unreachable hand.

`run_short.py --hand-retime-plan PLAN.json` applies the optional step after
ordinary building/contact baking, before optional gaze baking and raw rendering.
The original stays in `scene/scene.blend`; the new candidate is
`hand-retime/scene.blend`. If gaze baking follows, `gaze/scene.blend` is final.
Match the delivered scene hash against `raw/render-job.json`; never assume the
first built scene is the one that produced the video.

Standalone, invoke Blender factory startup with:

```text
scripts/bake_hand_retime.py -- --blend INPUT.blend --character CHARACTER.json
  --build-report BUILD.json --plan PLAN.json --output NEW.blend --report NEW.json
```

Keep the shared execution lock and choose distinct, new output paths. The writer
samples original source curves before any edits, follows the sampled wrist and
elbow world path with the original FK solver, and preserves the three configured
arm/elbow/wrist channels outside the interval at integer frames. Quaternions are
normalized and hemisphere continuous. The route requires one unit-world-scale
armature, quaternion target bones, unit target-bone scale and no active target
bone constraints. Other rig arrangements require separate evidence.

The pipeline binds the plan, character, build report, input/output scenes, solver,
validator and writer hashes before rendering or accepting a resumed stage.
Missing/stale evidence stops reuse; preserve the partial version and investigate.

Before adoption, compare all protected bone and noncamera object world matrices
throughout the saved film. Inspect hand/head, opposite hand, prop and scene
clearance throughout approach, held contact and release, not just the retimed
window. Recheck feet, gaze, shot framing, linkage engagement and prop footprint.
Render matched equal-time samples and a complete preview. Judge the intended
pause, arc and cut timing at normal speed, including the transition out of the
retimed interval. A successful write is only a new candidate.

This is an integer-frame timing adaptation of existing authored motion, not a
motion-library clip, full-body retargeter, physical contact or naturalness
certificate. Dense linear keys change subframe interpolation. Torso collision,
surface penetration depth, volume containment, subframes and continuous viewing
remain separate checks. Keep source-motion reuse claims tied to the original
verified source layers; do not call this a newly acquired action.


## Verification scope

The Nanami Q workshop case exercised fresh PMX import, the optional recovery
stage, complete source-style postprocessing, encoding/decoding, final-scene
matrix/geometry checks and representative reopened native views. A different
paper-plane plot exercised both the unchanged default route and recovery followed
by moving-target gaze baking in fresh input-only directories. The default route
retained all 240 final PNG bytes versus the prior stable producer; five raw Bloom
weight arrays differed by at most 0.00048828125 while radiance and final PNGs were
unchanged. These are same-author/context tests on one character. Normal-speed
continuous viewing, physical grasp, full-body library retargeting and strict
source-render equivalence remain separate/unpassed.

When isolating a source-motion layer after a fractional-time recovery bake, keep
its resampling contract equal in the control. Omitting the entire source stage
can compare sparse Bezier curves with dense linear curves and therefore change
fractional samples even outside active source intervals. A control with the same
mapped channels and zero layer strengths isolates the clip contribution. Preserve
any failed omit-stage comparison and describe this confound; do not relabel it as
a passing preservation test. The actual workshop zero-strength comparison kept
inactive/held motion and feet identical while demonstrating seven mapped source
rotation effects only in the declared noncontact intervals.
