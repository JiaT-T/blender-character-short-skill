---
name: blender-character-short
description: Build local Blender character shorts from authorized PMX assets, character mappings and a small story; prioritize permitted recorded actions, then adapt body/wrist movement and weighted hand acting, inspect documented MMD physics and deliver reproducible local previews. Strict shader and naturalness acceptance require separate evidence.
---

# Blender character short

Turn the story into a readable performance, then improve the procedure from actual output. Read [production inputs](references/production.md) before preparing a character/story, [rendering contract](references/rendering.md) for source reproduction, and [execution](references/execution.md) for commands and recovery. [Validation](references/validation.md) records verified scope and limitations.

For new full-body acting, start with [recorded library actions](references/library-actions.md). Preview permitted captured motion, calibrate its actual source skeleton, retain captured root travel and wrist changes, then add missing eyes, fingers and story-specific details. Preserve failed user visual reviews; numeric success cannot overturn them. Do not use a long authored FK sequence as a substitute for a library-motion route.

Before correcting shoes, inspect the raw source joint/End Site semantics and each foot’s neutral reference. A cropped first pose may already point one foot down, and an importer-generated display tail is not a recorded toe tip. Use explicit [neutral foot references](references/library-actions.md#use-a-real-neutral-foot-reference) and preserve the source/calibration evidence.

When a reviewed captured fit has visibly floating shoes, the optional [experimental geometric shoe adaptation](references/recorded-shoes.md) uses explicit source-height proxies and existing original IK/FK. Preserve upper performance and old versions, measure actual shoes after reopen, separate integer/half-frame failures and inspect costume/silhouette changes. It does not generate controllers or establish physical contact/naturalness.

For installed MMD Tools physics or MikuMikuRig controllers, read [documented plugin workflows and limits](references/mmd-plugins.md). Check matching instructions, versions and model data before trying a backup. Missing instructions mean defer that portion; installation is separate from feature success.

When the user supplies a rendering project with existing controllers, use [existing controller projects](references/existing-controller-projects.md). Preserve the original, verify actual skin response, retain the provided rig, adapt permitted recorded motion and follow saved-project scene/camera/physics/preview checkpoints. Missing binding repair, controller generation, cache baking and visual acceptance are separate claims.

For a plot-driven environment, data-authored scene changes, body offsets or stationary support, read [narrative scenes](references/story-scenes.md). Build the reachable interaction space and visible consequence around the character's intent before adding decoration.

For a reviewed local static GLB set piece, use [scene asset imports](references/scene-assets.md). Bind its size, purpose and material palette to the story, retain source/license evidence, and verify the complete interaction after import.

For a moving handle and physical linkage, use the [prop component parent contract](references/story-scenes.md#moving-prop-components), then verify actual contact, clearance and engagement separately.

For an optional theme-matched matte environment, read [scene surface style](references/scene-style.md). Select explicit static scene materials and compare their shadow, feedback readability and temporal behavior with the original before adoption.

When an existing local packed node clip and matching hierarchy are supplied, [source-motion variation](references/source-motion.md) can add explicitly mapped rotation variation over authored acting. It is a limited reuse route, not full-body action retargeting; preserve the remaining library-motion gap and verify contact separately.

For a reviewed locally converted body fragment and matching original rig, use the optional [configured body approach](references/body-approach.md). Fit proportions, measured travel, actual material stances and a bounded stop into the story, then inspect the entire performance. This narrow route starts already moving and does not establish general FBX/Mixamo or cross-character retargeting.

For a broader comic performance adapted from a permitted existing body asset, read [body motion remix](references/body-motion-remix.md). Calibrate the original knee hinge, edit timing and full-body acting in external tracks, preserve the source, and inspect both the feet and opaque costume during the stop.

For permitted local GLB2 animation, [motion conversion](references/motion-conversion.md) extracts supported LINEAR node TRS into that existing external format. Keep reviewed source/credit/license identity with the converted data; conversion does not fit a character or validate walking.

## Establish evidence

Inspect current Blender processes/project and preserve unsaved work. Use one scene writer and one heavy render. Preserve asset/import baselines and save separate scene versions. Keep third-party assets, licenses and character-specific mappings outside this skill.

Pack local image dependencies before relocating an input `.blend`. A filesystem copy preserves bytes while changing the base of relative texture paths. Use `pack_blend_resources.py` at the known original location, require the reviewed input hash, preserve original files, and verify the new packed copy after reopening. Missing paths must fail; do not guess another asset directory. See [production inputs](references/production.md#relocating-local-project-inputs).

Verify processes on the same host/execution surface that launched them; an empty restricted process view is not proof that a host render exited. For cooperating Windows jobs use the [shared execution lock](references/execution.md#shared-execution-lock), then check owned host PIDs and output timestamps before any uncertain recovery.

Record renderer/add-on versions, output paths and budget. Prefer MCP only after a real scene read succeeds. Background Blender Python is a tested alternative; a configured MCP connection is not a live connection.

Actually view reference work and record links/time ranges. Separate sampled playback, continuous visual viewing and audio listening. Extract pose, timing, intent, material and compositing observations; turn major differences into checkable criteria rather than a self-score.

## Design and prepare

Write anticipation, action, contact/reaction and recovery beats. Give each shot a narrative purpose and visible focus. Compare two materially different dynamic shot arrangements. Use scale-aware character configurations for bones, proportions, UV/material mappings, expressions and pose targets. Before placing a prop relative to a shoulder, face or hand, derive rest-joint landmarks from the imported baseline; total height alone is insufficient across chibi and adult proportions.

For a short comic performance, read [reusable acting clips](references/performance-clips.md). Prioritize a readable wish, obstruction and payoff; compose independently timed hands, eyes, head, torso and reactions. Retimed repeated gestures and simple original props can establish character intent with modest rendering. Choose geometric precision to suit the visible shot, and retain complete-motion visual acceptance as its own step.

Import PMX in an isolated process and inspect the saved baseline. Record whether factory startup with explicit project dependencies or normal startup with installed addons is used. Preserve original deform bones, weights and morphs. Verify actual deformation and support feet. The arm solver bakes targets as original-rig FK; existing leg IK remains by default. Joint-head distances, not display-bone tails, define arm length. Inspect reach clamps and reject unreachable required contact. Earlier automated MMR full generation failed; later user-provided controllers were retained and tested without regeneration. Original-data physics has narrow bake/reopen and sampled visual evidence, not general simulation or continuous naturalness acceptance.

Existing leg IK is the default. The opt-in stationary support route explicitly mutes the configured knee/ankle IK in a new candidate and bakes the original bones; it requires its own evaluated and visual checks. Do not describe that route as unchanged active IK or locomotion.

Use existing expressions after rendered verification. Separate body, shoulder/elbow/wrist, gaze and secondary timing. Check silhouette, pauses, arcs, support and prop visibility at normal speed. Executable poses are not necessarily convincing acting.

Keep new pose keys in the story input. For palm interactions, use the [contact workflow](references/production.md#moving-palm-contact): calibrate against the actual glove surface, bake the moving contact point, audit the prop footprint, then inspect visible clearance. Zero bone-to-prop error can still hide penetration.

When an otherwise readable noncontact recovery is too abrupt, use the optional [post-contact recovery timing](references/recovery-retime.md) route. Preserve held performance and props, then judge complete playback before adoption.

When the complete story needs a different approach, pause or recovery pace, use the optional [coupled scene timing](references/scene-tempo.md) route. Keep expressions, props, materials and camera cuts on the same external time map, then judge the complete motion again.

For finger or mitten acting, first inspect [actual weighted hand controls](references/hand-controls.md). The optional bounded multi-axis FK route uses external rest/skin-bound profiles and gesture channels, then independently reopens the saved clip to compare actual skin and protected source motion. Confirm thumb opposition, contact and normal-speed acting separately.

For a small spherical prop, use the optional [geometric sphere grip](references/sphere-grasp.md) route. Fit actual finger surfaces, preserve support before release, inspect the closing path and noncontact fingers, then measure saved contact, material-point sliding and wrist/arm transitions. This does not establish friction or continuous naturalness.

When a sleeve blocks an otherwise supported palm interaction, use the optional [wrist-preserving elbow pose](references/elbow-poles.md) route. Inspect the complete forearm and nearby set before changing the contact point: a passing palm footprint can coexist with a sleeve intersection.

## Validate rendering, then creative changes

Lock asset/pose/camera/light/background and source version. Keep a per-character source → implementation → output table: [S] code, [G] runtime, [B] Blender output, [A] adaptation. Distinguish different geometry/UVs from implementation errors. Validate known-input formulas and stage outputs before migrating to a different PMX.

Do not replace known formulas with generic color ramps or hide channel mistakes with exposure. The included postprocessor implements one documented Bloom/curve/LUT chain, not a universal look. Supply a verified profile per source version. Missing applicable stencil, depth, reflection or AA keeps strict reproduction unpassed.

Production scenes expose raw radiance and Bloom-weight AOV. Native Composite is a diagnostic checkpoint. Final source-style output requires render_performance.py followed by post_sequence.py; F12 alone does not execute the external chain. Preserve raw inputs, profile, LUT and script version with the scene. For source-derived SMAA, read [antialiasing](references/antialiasing.md), supply external lookup paths and preserve the edge history; CPU sequence success does not establish website GPU parity.

For a matched source GLB outline baseline, use the [outline bake](references/outline.md). Its saved integer-frame cache supports verified skin/camera changes and rejects stale geometry. Named relative POSITION-only morphs are supported when the imported basis and deltas match the supplied source GLB. Normal/tangent morphs, PMX attribute reconstruction and source depth/stencil coverage remain outside verified scope.

## Execute and iterate

Use scripts/run_short.py with explicit Blender, PMX, dependency, character, story, post-profile, LUT and output paths. It imports, inspects, builds, renders, composites, encodes and decodes sequentially. Start with a low-cost complete preview for every character before polishing.

For bounded foreground work, use the [frame-boundary execution budgets](references/execution.md#frame-boundary-budgets). Resume the same frozen producer and inputs; a completed raw stage does not mean postprocessing or encoding completed.

Each iteration: inspect current output, choose up to three specific problems with character/shot/time, separate variables where practical, render and compare under matching conditions. Keep the better version. Write successful methods back to this skill and re-run them. Record failures and untested assumptions separately.

When the story needs a visible start from rest, the opt-in [grounded launch](references/grounded-launch.md) prepares a measured ready stance and acceleration before the configured source-body approach. Reject original-leg reach failures, inspect actual saved joins and keep continuous naturalness unverified until viewed.

Use [story-purpose framing](references/story-framing.md) when a changed camera risks cropping the hair, hands, stopping feet or plot prop. Declare required features per beat, check actual saved geometry, and still review visibility in rendered output.

For large hair, sleeves or hands that may overlap during a reach or head turn, use [weighted character-region surfaces](references/character-region-surfaces.md). External scene clearance does not inspect these pairs. Keep bone/weight selections outside the skill, retain warnings inherited from authored acting, and validate the full relevant interval after any pose correction.

Use original or licensed sound when it serves a verified beat. Silent output is the automated default. Audio sourcing, editing and actual listening need separate evidence.

When a scene should acknowledge successful placement, use [scene feedback](references/scene-feedback.md). Confirm real seating before a restrained response that preserves the original material style. Review the complete shot and retain any failed movement or gaze checks separately.

## Independent acceptance

- Rendering: applicable formulas, channels, spaces and passes have evidence; critical approximations remain failures.
- Performance: compare observed reference moments to output acting, gaze/contact, pauses, continuity and readability. Record remaining differences and viewing limits.
- Reuse: in a clean directory/context, provide only skill, authorized assets/configuration and a different story. Produce a new editable scene and complete preview for each required character. Repair missing knowledge and retry.

Decode videos and check fps, count, size and duration. Reopen the delivered scene, check resources and render a representative frame. Decode, sampled visual checks, continuous viewing and listening are distinct. Skill format validation proves none of these production gates.

For plot-critical static feedback, read [final evaluated gaze](references/gaze-targets.md). Keep the real object, eye target and response timing together; test the saved graph after all layers and preserve the viewing limitations.

For a moving prop that loses fixation between authored keys, read [real-target gaze baking](references/moving-gaze.md). That route also supports an explicit bounded return to authored gaze for a deliberate change of attention, separately from required fixation. Use explicit integer-frame ranges after the ordinary build, preserve original eye limits, and render the separately saved scene only after final evaluated and visual checks.

For critical feedback, also check [external target blockers](references/target-occlusion.md). Correct bone axes do not establish a visible object. Keep external opaque geometry, own-character/iris checks and rendered viewing as distinct gates.
