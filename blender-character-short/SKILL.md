---
name: blender-character-short
description: Make local Blender shorts for MMD PMX/PMD characters, preferably from existing MMR controllers. Prepare a skin-verified baseline, transfer a reviewed packed look, use Eevee and the saved frame rate with identity-bound render resumes, then encode and report actual acceptance.
---

# Blender character short · v45a

Use `scripts/short_project.py` as the local production entry. Read
[current production](references/current-production.md) for the external project
contract, stages and recovery. `version.json` preserves the tested producer
identity (`v45a-local`); the public distribution manifest records this publication.
The source build metadata is not an upload authorization. Git history and the
release history retain older versions. Local projects select their own external
configuration and output directories.

Target MMD PMX/PMD deform skeletons. Prefer a supplied **unanimated** MMR project
and preserve its original file, skin, shape keys, controllers and constraints.
An existing control shape is insufficient: test FK, IK, wrists, fingers, torso
and head against actual weighted skin, then reopen in a fresh process.

The user-guided MMR route selects the original MMD armature, enables
Extras/Finger options and executes Build a controller directly. Only apply it
to a separate, unrigged copy, with matching instructions/version, facing and
actual bone-name mapping. Use the plugin's external preset interface when the
names differ. Do not repeat generation on a supplied rig or use a metarig
follow-up as if it were this tested route. One-model success is not universal.

Keep role names, mappings, action plans, shader profiles and restricted assets
outside this generic folder. The reviewed h07 route transfers the packed saved
look to matching geometry/UVs while protecting the target rig. It copies the
native compositor once. It does not reconstruct that look from a website or
grant permission to redistribute the donor. [Rendering modes](references/rendering.md)
separate this route from the preserved raw-AOV/external postprocessor route.

Prefer Eevee and a compatible discrete GPU. Preserve the saved engine; do not
silently convert materials or fall back to CPU. Eevee has no CPU mode. Follow
[device policy](references/render-devices.md), including actual GPU-context
verification. CPU compositing/encoding is separate from the 3D render device.

Design a readable wish, obstacle and payoff before choosing assets. Prefer
permitted [recorded actions](references/library-actions.md), then add missing
eyes, expression, hand and prop details. Render a cheap complete board before
polishing; repair visible large intersections and rebake changed physics.
Small unobvious intersections may meet the user's chosen quality target.

The current entry covers baseline → saved look → authored saved scene →
identity-bound render → encode/decode. Story/action authoring stays an explicit
step; it is not silently invented by the build command. For the specialized
acting, contact, imported scenery, original-PMX and source-AOV tools, read only
the relevant [preserved routes](references/legacy-routes.md). Their separate
scope and prior failures still apply.

Use one scene writer and the shared execution lock. Preserve snapshots and new
output versions. Inspect exact job receipts before resuming an uncertain job;
an empty restricted process list is not a host-process guarantee. Never restart
an uncertain or denied operation automatically.

For newly authored videos, default to **1280×720 at 24 fps**. Only raise those
defaults when the user explicitly requests a higher specification. Preserve
explicit settings for a current in-progress job. Existing saved fps/fps_base
are authoritative; retiming requires a separately authored saved copy.
A requested fps is an assertion, not a
retime command. The saved-project renderer binds the scene, declared resources,
Blender binary, producer scripts and settings, then verifies every PNG receipt.
Changed identity, edited frames or unreceipted legacy PNGs require a new output
directory. Batches can stop at frame boundaries and resume the same identity.

Verify output size, rate, frame count, full decode, paired-project reopen and
representative images. Keep unit tests, real-material integration, sampled
images, normal-speed viewing and user acceptance separate. Do not infer a
complete new-story or cross-machine pass from a technical diagnostic clip.

Do not use foreground UI or browser automation unless the user explicitly
authorizes it. This workflow works through background Blender Python/API.
No upload, public push or third-party asset redistribution is part of a local
build. Review the individual licenses and publication scope separately.

## Latest scene and compositing workflow notes

For external-scene matching, frozen character protection, selective reference
compositing, performance measurement and portable private handoff, read
[scene/render iteration notes](references/scene-render-iteration.md). These are
workflow lessons from local projects, not new executable producer capabilities.

## Executable static refinement (v46)

Use the [saved-project refinement stage](references/static-refinement.md) to apply reviewed compositor and stage-only material/light plans, with a source hash, backup, separate output and fresh-reopen protection checks. This updates existing saved projects; it does not automatically select assets, judge style, or certify animation.
