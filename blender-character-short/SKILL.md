---
name: blender-character-short
description: Build local Blender Eevee character shorts from authorized PMX assets, character mappings and a small story; develop reference-led acting, configurable shots, source-backed materials, staged compositing and reproducible video delivery. Strict shader equivalence requires separate evidence.
---

# Blender character short

Turn the story into a readable performance, then improve the procedure from actual output. Read [production inputs](references/production.md) before preparing a character/story, [rendering contract](references/rendering.md) for source reproduction, and [execution](references/execution.md) for commands and recovery. [Validation](references/validation.md) records verified scope and limitations.

For a plot-driven environment, data-authored scene changes, body offsets or stationary support, read [narrative scenes](references/story-scenes.md). Build the reachable interaction space and visible consequence around the character's intent before adding decoration.

For a reviewed local static GLB set piece, use [scene asset imports](references/scene-assets.md). Bind its size, purpose and material palette to the story, retain source/license evidence, and verify the complete interaction after import.

For a moving handle and physical linkage, use the [prop component parent contract](references/story-scenes.md#moving-prop-components), then verify actual contact, clearance and engagement separately.

For an optional theme-matched matte environment, read [scene surface style](references/scene-style.md). Select explicit static scene materials and compare their shadow, feedback readability and temporal behavior with the original before adoption.

When an existing local packed node clip and matching hierarchy are supplied, [source-motion variation](references/source-motion.md) can add explicitly mapped rotation variation over authored acting. It is a limited reuse route, not full-body action retargeting; preserve the remaining library-motion gap and verify contact separately.

## Establish evidence

Inspect current Blender processes/project and preserve unsaved work. Use one scene writer and one heavy render. Preserve asset/import baselines and save separate scene versions. Keep third-party assets, licenses and character-specific mappings outside this skill.

Verify processes on the same host/execution surface that launched them; an empty restricted process view is not proof that a host render exited. For cooperating Windows jobs use the [shared execution lock](references/execution.md#shared-execution-lock), then check owned host PIDs and output timestamps before any uncertain recovery.

Record renderer/add-on versions, output paths and budget. Prefer MCP only after a real scene read succeeds. Background Blender Python is a tested alternative; a configured MCP connection is not a live connection.

Actually view reference work and record links/time ranges. Separate sampled playback, continuous visual viewing and audio listening. Extract pose, timing, intent, material and compositing observations; turn major differences into checkable criteria rather than a self-score.

## Design and prepare

Write anticipation, action, contact/reaction and recovery beats. Give each shot a narrative purpose and visible focus. Compare two materially different dynamic shot arrangements. Use scale-aware character configurations for bones, proportions, UV/material mappings, expressions and pose targets. Before placing a prop relative to a shoulder, face or hand, derive rest-joint landmarks from the imported baseline; total height alone is insufficient across chibi and adult proportions.

Import PMX into a factory-startup process and inspect the saved baseline. Preserve original deform bones, weights and morphs. Verify actual deformation and support feet. The arm solver bakes targets as original-rig FK; existing leg IK remains by default. Joint-head distances, not display-bone tails, define arm length. Inspect reach clamps and reject unreachable required contact. MMR and full physics are unvalidated.

Existing leg IK is the default. The opt-in stationary support route explicitly mutes the configured knee/ankle IK in a new candidate and bakes the original bones; it requires its own evaluated and visual checks. Do not describe that route as unchanged active IK or locomotion.

Use existing expressions after rendered verification. Separate body, shoulder/elbow/wrist, gaze and secondary timing. Check silhouette, pauses, arcs, support and prop visibility at normal speed. Executable poses are not necessarily convincing acting.

Keep new pose keys in the story input. For palm interactions, use the [contact workflow](references/production.md#moving-palm-contact): calibrate against the actual glove surface, bake the moving contact point, audit the prop footprint, then inspect visible clearance. Zero bone-to-prop error can still hide penetration.

When an otherwise readable noncontact recovery is too abrupt, use the optional [post-contact recovery timing](references/recovery-retime.md) route. Preserve held performance and props, then judge complete playback before adoption.

For finger or mitten acting, first inspect [actual weighted hand controls](references/hand-controls.md). Keep selected existing joints and timing in external character/story inputs, then repeat the full contact and release checks after deformation changes.

## Validate rendering, then creative changes

Lock asset/pose/camera/light/background and source version. Keep a per-character source → implementation → output table: [S] code, [G] runtime, [B] Blender output, [A] adaptation. Distinguish different geometry/UVs from implementation errors. Validate known-input formulas and stage outputs before migrating to a different PMX.

Do not replace known formulas with generic color ramps or hide channel mistakes with exposure. The included postprocessor implements one documented Bloom/curve/LUT chain, not a universal look. Supply a verified profile per source version. Missing applicable stencil, depth, reflection or AA keeps strict reproduction unpassed.

Production scenes expose raw radiance and Bloom-weight AOV. Native Composite is a diagnostic checkpoint. Final source-style output requires render_performance.py followed by post_sequence.py; F12 alone does not execute the external chain. Preserve raw inputs, profile, LUT and script version with the scene. For source-derived SMAA, read [antialiasing](references/antialiasing.md), supply external lookup paths and preserve the edge history; CPU sequence success does not establish website GPU parity.

For a matched source GLB outline baseline, use the [outline bake](references/outline.md). Its saved integer-frame cache supports verified skin/camera changes and rejects stale geometry. Named relative POSITION-only morphs are supported when the imported basis and deltas match the supplied source GLB. Normal/tangent morphs, PMX attribute reconstruction and source depth/stencil coverage remain outside verified scope.

## Execute and iterate

Use scripts/run_short.py with explicit Blender, PMX, dependency, character, story, post-profile, LUT and output paths. It imports, inspects, builds, renders, composites, encodes and decodes sequentially. Start with a low-cost complete preview for every character before polishing.

For bounded foreground work, use the [frame-boundary execution budgets](references/execution.md#frame-boundary-budgets). Resume the same frozen producer and inputs; a completed raw stage does not mean postprocessing or encoding completed.

Each iteration: inspect current output, choose up to three specific problems with character/shot/time, separate variables where practical, render and compare under matching conditions. Keep the better version. Write successful methods back to this skill and re-run them. Record failures and untested assumptions separately.

Use original or licensed sound when it serves a verified beat. Silent output is the automated default. Audio sourcing, editing and actual listening need separate evidence.

## Independent acceptance

- Rendering: applicable formulas, channels, spaces and passes have evidence; critical approximations remain failures.
- Performance: compare observed reference moments to output acting, gaze/contact, pauses, continuity and readability. Record remaining differences and viewing limits.
- Reuse: in a clean directory/context, provide only skill, authorized assets/configuration and a different story. Produce a new editable scene and complete preview for each required character. Repair missing knowledge and retry.

Decode videos and check fps, count, size and duration. Reopen the delivered scene, check resources and render a representative frame. Decode, sampled visual checks, continuous viewing and listening are distinct. Skill format validation proves none of these production gates.

For plot-critical static feedback, read [final evaluated gaze](references/gaze-targets.md). Keep the real object, eye target and response timing together; test the saved graph after all layers and preserve the viewing limitations.

For a moving prop that loses fixation between authored keys, read [real-target gaze baking](references/moving-gaze.md). That route also supports an explicit bounded return to authored gaze for a deliberate change of attention, separately from required fixation. Use explicit integer-frame ranges after the ordinary build, preserve original eye limits, and render the separately saved scene only after final evaluated and visual checks.

For critical feedback, also check [external target blockers](references/target-occlusion.md). Correct bone axes do not establish a visible object. Keep external opaque geometry, own-character/iris checks and rendered viewing as distinct gates.
