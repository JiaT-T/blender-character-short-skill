---
name: blender-character-short
description: Build local Blender Eevee character shorts from authorized PMX assets, character mappings and a small story; develop reference-led acting, configurable shots, source-backed materials, staged compositing and reproducible video delivery. Strict shader equivalence requires separate evidence.
---

# Blender character short

Turn the story into a readable performance, then improve the procedure from actual output. Read [production inputs](references/production.md) before preparing a character/story, [rendering contract](references/rendering.md) for source reproduction, and [execution](references/execution.md) for commands and recovery. [Validation](references/validation.md) records verified scope and limitations.

## Establish evidence

Inspect current Blender processes/project and preserve unsaved work. Use one scene writer and one heavy render. Preserve asset/import baselines and save separate scene versions. Keep third-party assets, licenses and character-specific mappings outside this skill.

Verify processes on the same host/execution surface that launched them; an empty restricted process view is not proof that a host render exited. For cooperating Windows jobs use the [shared execution lock](references/execution.md#shared-execution-lock), then check owned host PIDs and output timestamps before any uncertain recovery.

Record renderer/add-on versions, output paths and budget. Prefer MCP only after a real scene read succeeds. Background Blender Python is a tested alternative; a configured MCP connection is not a live connection.

Actually view reference work and record links/time ranges. Separate sampled playback, continuous visual viewing and audio listening. Extract pose, timing, intent, material and compositing observations; turn major differences into checkable criteria rather than a self-score.

## Design and prepare

Write anticipation, action, contact/reaction and recovery beats. Give each shot a narrative purpose and visible focus. Compare two materially different dynamic shot arrangements. Use scale-aware character configurations for bones, proportions, UV/material mappings, expressions and pose targets. Before placing a prop relative to a shoulder, face or hand, derive rest-joint landmarks from the imported baseline; total height alone is insufficient across chibi and adult proportions.

Import PMX into a factory-startup process and inspect the saved baseline. Preserve original deform bones, weights and morphs. Verify actual deformation and support feet. The arm solver bakes targets as original-rig FK; existing leg IK remains. Joint-head distances, not display-bone tails, define arm length. Inspect reach clamps and reject unreachable required contact. MMR and full physics are unvalidated.

Use existing expressions after rendered verification. Separate body, shoulder/elbow/wrist, gaze and secondary timing. Check silhouette, pauses, arcs, support and prop visibility at normal speed. Executable poses are not necessarily convincing acting.

Keep new pose keys in the story input. For palm interactions, use the [contact workflow](references/production.md#moving-palm-contact): calibrate against the actual glove surface, bake the moving contact point, audit the prop footprint, then inspect visible clearance. Zero bone-to-prop error can still hide penetration.

## Validate rendering, then creative changes

Lock asset/pose/camera/light/background and source version. Keep a per-character source → implementation → output table: [S] code, [G] runtime, [B] Blender output, [A] adaptation. Distinguish different geometry/UVs from implementation errors. Validate known-input formulas and stage outputs before migrating to a different PMX.

Do not replace known formulas with generic color ramps or hide channel mistakes with exposure. The included postprocessor implements one documented Bloom/curve/LUT chain, not a universal look. Supply a verified profile per source version. Missing applicable stencil, depth, reflection or AA keeps strict reproduction unpassed.

Production scenes expose raw radiance and Bloom-weight AOV. Native Composite is a diagnostic checkpoint. Final source-style output requires render_performance.py followed by post_sequence.py; F12 alone does not execute the external chain. Preserve raw inputs, profile, LUT and script version with the scene. For source-derived SMAA, read [antialiasing](references/antialiasing.md), supply external lookup paths and preserve the edge history; CPU sequence success does not establish website GPU parity.

For a matched source GLB outline baseline, use the [outline bake](references/outline.md). Its saved integer-frame cache supports verified skin/camera changes and rejects stale geometry. Named relative POSITION-only morphs are supported when the imported basis and deltas match the supplied source GLB. Normal/tangent morphs, PMX attribute reconstruction and source depth/stencil coverage remain outside verified scope.

## Execute and iterate

Use scripts/run_short.py with explicit Blender, PMX, dependency, character, story, post-profile, LUT and output paths. It imports, inspects, builds, renders, composites, encodes and decodes sequentially. Start with a low-cost complete preview for every character before polishing.

Each iteration: inspect current output, choose up to three specific problems with character/shot/time, separate variables where practical, render and compare under matching conditions. Keep the better version. Write successful methods back to this skill and re-run them. Record failures and untested assumptions separately.

Use original or licensed sound when it serves a verified beat. Silent output is the automated default. Audio sourcing, editing and actual listening need separate evidence.

## Independent acceptance

- Rendering: applicable formulas, channels, spaces and passes have evidence; critical approximations remain failures.
- Performance: compare observed reference moments to output acting, gaze/contact, pauses, continuity and readability. Record remaining differences and viewing limits.
- Reuse: in a clean directory/context, provide only skill, authorized assets/configuration and a different story. Produce a new editable scene and complete preview for each required character. Repair missing knowledge and retry.

Decode videos and check fps, count, size and duration. Reopen the delivered scene, check resources and render a representative frame. Decode, sampled visual checks, continuous viewing and listening are distinct. Skill format validation proves none of these production gates.
