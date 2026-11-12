# Production workflow (v46.1)

This is the default agent workflow for a new short. It is not an unattended film generator. User instructions override creative defaults, not platform permissions. There is **no separate asset/license-check stage or license-approval prerequisite**. Do not redistribute restricted assets; publication remains separately scoped to the user's authorization.

## 1. Required and optional inputs

Require a character MMD model (PMX/PMD, or an existing Blender project retaining its MMD skeleton), a scene model, and a basic story prompt: **who, where, what happens?** Ask for missing essentials rather than silently creating a different character/set. An explicit user request to find, generate or omit a model is an exception; retain the request in the brief. Scene models need not use MMD skeletons. Prefer imported scenes; self-model only unimportant low-detail elements unless requested otherwise.

Optional: actions, cameras, props, music, atmosphere, lighting, duration, aspect ratio, pace and references. Use assets the user specifically asks to use. Otherwise supplement appropriate details yourself.

Missing auxiliary textures are not a production blocker: simplify with flat tangent-space normal (RGB 0.5, 0.5, 1.0, Non-Color) or no Normal Map connection, constant roughness/metallic and simplified masks. Never feed blue-purple directly into the surface normal socket. Preserve the **basic stylized toon/mobile-game look**: readable color regions, controlled light/shadow boundaries and highlights, coherent character/scene palette. Missing main color, facial detail or special-effect masks must be disclosed as effects that cannot be reliably restored; choose a simple palette rather than claiming equivalence. Work on copies and visually assess results. Existing frozen character materials remain protected; any fallback belongs in a new initial-look copy, not an unexplained change to a protected baseline.

## 2. Assess and complete the prompt

Record the original prompt and non-negotiable character, setting, event and tone. Assess whether it provides enough cause/action/result for a readable short. Add missing timing, motivation, reaction and small props without changing the user's intent. Ask only when a consequential contradiction or ambiguity cannot be resolved safely. Keep inferred details separate from user requirements; do not make all optional fields mandatory.

## 3. Initial look and motion search

Shade the character and scene and render cheap representative stills while searching online for suitable existing motions. Preserve the Huaxu-based character material target; use existing reviewed look/refine routes where their matching requirements hold. Do not copy the rejected distance-dependent fringe shadow. Prefer Eevee, restrained bloom and depth of field, and measured compositing cost. Do not run dynamic validation unless requested.

If motion retrieval requires login, **stop that dependent step and wait for user authorization**. Do not retry credentials, bypass authentication or claim a download. Independent local static-look work may continue. Use supplied suitable motions where available; internet search and style assessment are agent tasks, not features of the CLI.

## 4. Storyboard

Define every shot's narrative purpose, duration, action, expression, camera and transition. Respect available motion and scene scale. Make a low-cost preview before polishing. Do not require a new user approval for every routine shot choice unless the user reserved that decision.

## 5. Production

Save a new copy of the unanimated render/controller baseline -> import scene -> adjust render, lighting and compositing -> import/adapt motion and cameras -> enable supported physics -> preview -> fix major intersections, sliding/floating feet and important occlusions -> recalculate physics -> preview again. Repeat as needed, keeping rollback versions. Small unobvious intersections need not block a stylized short. Use documented MMD Tools/MMR routes; do not invent unavailable physics or controller automation. Preserve original assets and the character look.

Before render, check frame range, cameras, physics cache and output settings. New videos default to **1280 x 720, 24 fps**, Eevee on a compatible discrete GPU. Existing jobs retain explicit settings. Changed scene/settings/producer identities require a new frame output folder; never mix old frames. Use existing render/encode receipts and checks rather than rewriting their protections.

## 6. Delivery

Deliver the movie, saved project, required dependencies and actual validation limits within the requested delivery scope. Distinguish code tests, still-frame review, full playback and user acceptance. Do not call an asset-dependent visual target guaranteed. Push/upload only what the user authorized; don't bundle restricted model/texture files with the public skill.

## Executable brief/state helper

`python -B scripts/production_workflow.py --brief BRIEF.json --report NEW_REPORT.json`

Or use `short_project.py workflow --project PROJECT.json`, where the project declares `schema:1`, a filename-safe `id`, `workflow_brief`, and `workflow_report`. This host-only stage needs no Blender runtime/doctor and does not start rendering. Relative input paths are based on the brief; report paths are based on the project. Existing reports are never overwritten.

Brief example (replace filenames with real local inputs):

```json
{
  "schema": 1,
  "inputs": {"character_mmd": "assets/character.pmx", "scene": "assets/scene.blend"},
  "prompt": "A girl in a garden tries to catch a wind-blown ribbon.",
  "mood": "light-hearted",
  "intent": {"core": ["garden", "ribbon chase"], "additions": ["surprised ending"], "conflicts": []},
  "missing_textures": [{"material": "coat", "kind": "normal"}],
  "motion_search": {"status": "pending"},
  "completed": [],
  "evidence": {}
}
```

A saved character `.blend` additionally declares `inputs.saved_mmd_skeleton:true`; this is an input declaration, not bone inspection. `user_exceptions` maps `character_mmd` or `scene` to the user's explicit exception text. Optional `output` sets positive integer width/height/fps. Only record overrides the user requested.

The helper records missing essentials, defaults, optional requirements, fallback suggestions, login pause, conflicts and next stage. Completion IDs are the ordered prefix `intake`, `intent`, `look_and_motion`, `storyboard`, `production`, `delivery`; each requires a nonempty `evidence` list of existing local files. These evidence files are references, **not automatically verified semantic/visual acceptance**. `motion_search.status` is `pending|ready|login_required|not_needed`. The combined look/motion stage cannot complete with unresolved login. New CLI stages do not auto-create shaders, search websites, judge prompt quality or author animation. Those remain explicit agent steps using the documented tools. The helper does not mutate assets, execute a fallback, advance stages, or approve publication.
