# Render device selection

Default to a compatible **discrete GPU** for 3D rendering. CPU rendering is
permitted only when a reliable hardware inventory positively identifies every
hardware GPU as integrated. An empty inventory, software adapters alone, unknown
classification, unavailable discrete backend, driver error or insufficient GPU
resources does not permit a CPU fallback. Stop the affected render and report
the device, engine/backend and actual error. Never change security settings or
interrupt another task to make the device available.

`scripts/render_device_policy.py` enforces this rule in documented actual render
entrypoints, including saved-project renders, acting previews, render queues,
source probes and verification renders. `prepare_render(scene)` discovers and
applies settings; `render_with_policy(...)` checks the settings before invoking
the operator, refuses mixed CPU/GPU use and propagates failure without retrying
on CPU. Use these functions in any new render entrypoint. Direct `blender -f/-a`
commands bypass the helper and are not the documented skill render route.

## Engine choice before device selection

**Eevee is preferred for new video production and previews.** This is separate
from the discrete-GPU-first device rule above. The available GPU never silently
determines the engine. `render_engine_policy.py` defaults new-scene planning to
`BLENDER_EEVEE_NEXT`; existing projects retain their saved engine.

- `render_acting_preview.py` preserves the input engine and applies the matching
  sampling options. Optional `--engine eevee|cycles` asserts the saved engine;
  it does not convert it. For a new routine preview, start with an Eevee project
  and use `--engine eevee`. A legacy Cycles project remains Cycles until the user
  chooses a separately validated conversion. The preview's simplified material
  adapter is still explicitly separate from final source-material rendering.
- `render_queue.py` preserves each saved project's engine. An optional job
  `engine` (`BLENDER_EEVEE_NEXT` or `CYCLES`) is also an assertion. A mismatch
  fails instead of overriding the saved engine. Sampling follows the engine.
- `build_performance.py` is an Eevee-specific shader/story builder. It requires
  an Eevee baseline and refuses a Cycles baseline before modifying scene data.
- `render_cached_project.py` remains an explicit Cycles-only preserved-look
  route. It is not the preferred engine for all new shorts. Existing Eevee
  projects should use the engine-preserving queue. `render_performance.py` is
  an explicit Eevee source-AOV route and refuses a saved Cycles project.
  `verify_scene.py` also applies sampling for the actual saved engine.
- Factory-created source/formula/outline probes remain Eevee, as required by
  their source-material formulas; they do not convert an existing scene.

For integrated-only hardware, an Eevee render is blocked by the device rule:
Eevee has no CPU mode. Report this limitation and **let the user decide**
whether to use a different machine or prepare a separate Cycles-compatible copy.
Do not automatically enable Cycles just because CPU rendering is permitted for
that hardware. Cycles' OpenImageDenoise is not an Eevee option: an Eevee preview
records that it was not applied rather than touching Cycles settings.

## Hardware and engines

The implemented hardware inventory is Windows DXCore GPU enumeration using
`IsHardware` and `IsIntegrated`. It does not infer integrated/discrete status
from manufacturer, marketing name or video RAM. Windows/DXCore failure and other
platforms currently fail closed; cross-machine expansion is deferred. Driver
changes, disabled or unreported hardware require a fresh inventory and review.

For Cycles, discover actual Blender devices, select one uniquely matched
discrete board, set its supported backend and `device.use`, disable all CPU and
other GPU entries, then set `scene.cycles.device = 'GPU'`. Preference changes
apply only to the running process; do not save user preferences. Supported
backend attempts are OptiX, CUDA, HIP, oneAPI and Metal as available in that
Blender build. A failed GPU backend can be followed by another compatible GPU
backend; there is no GPU-to-CPU retry. On positively integrated-only hardware,
set Cycles to CPU and disable GPU entries.

Eevee and Workbench use the graphics context. Cycles preferences do not select
their GPU, and neither engine has a CPU rendering mode. Confirm the actual
graphics renderer against the discrete hardware inventory. Blender defers GPU
initialization in background mode, so querying `gpu.platform.renderer_get()`
before a context exists can raise `SystemError` without a hardware failure.

For exactly one positively identified discrete hardware GPU, the helper now
handles this specific lazy-initialization error through the documented
`RenderEngine.bl_use_gpu_context` API (`gpu_context_probe.py`). A temporary
8x8 blank-result diagnostic engine initializes a real context and reads its
renderer/vendor/backend inside its callback; it draws no scene geometry and
writes no image. Query the actual renderer again outside the callback and
uniquely match it to the physical discrete board before any Eevee scene render.
The probe's reported identity alone is insufficient. Reject software/unknown or
mismatching results. Multi-GPU, integrated-only, unrelated driver errors or
failed initialization retain their explicit failure, with no CPU retry or UI.
No driver/security/preference changes, private symbol calls or simulated
hardware results are used. A fresh render process repeats actual verification.

This fixed the tested RTX5060 / Vulkan background route: actual identity was
read after initialization and a guarded synthetic Eevee frame rendered. It
supersedes the historical v44/v44b blocker, while their frozen reports remain
unchanged. Do not use the single-device inventory itself as context proof.
Integrated-only Eevee projects still require a user decision and separately
reviewed Cycles material/engine adaptation before CPU rendering.

CPU physics, scene preparation, image postprocessing, OpenImageDenoise and video
encoding are distinct from primary 3D render device selection. Limiting those
CPU threads does not select the rendering device. GPU occupancy must be checked
on the same host before a heavy job; occupancy is not permission to use CPU.

## Evidence boundary

The current RTX 5060 was positively classified as discrete by DXCore. In a fresh
Blender 4.5.15 process, an existing project reopened and Cycles selected that
board through OptiX with CPU use disabled. Device configuration is verified;
that historical Cycles configuration check did not render a GPU frame. The
subsequent v44c recovery verified actual RTX5060/Vulkan context identity and
rendered both a synthetic Eevee frame and actual-scene sample frames. Final
film acceptance remains a separate production result. Pure regression
tests cover integrated-only CPU, unknown hardware, incompatible backends,
unmatched/duplicate devices, failure propagation and prevention of CPU retries.
Historical preview videos were CPU-rendered before this rule; their saved
projects and evidence remain unchanged. New helper/settings hashes change render
signatures, so use fresh output directories instead of mixing new GPU frames
with those historical CPU frames.

Primary references: [Microsoft DXCore properties](https://learn.microsoft.com/en-us/windows/win32/api/dxcore_interface/ne-dxcore_interface-dxcoreadapterproperty),
[Microsoft DXCore interfaces](https://github.com/microsoft/DirectX-Headers/blob/main/include/directx/dxcore_interface.h),
[Blender Cycles GPU rendering](https://docs.blender.org/manual/en/4.5/render/cycles/gpu_rendering.html).


Background-context references: [Blender RenderEngine API](https://docs.blender.org/api/current/bpy.types.RenderEngine.html),
[4.5.15 GPU query initialization check](https://github.com/blender/blender/blob/v4.5.15/source/blender/python/gpu/gpu_py.cc),
[4.5.15 render GPU context lifecycle](https://github.com/blender/blender/blob/v4.5.15/source/blender/render/intern/engine.cc).
