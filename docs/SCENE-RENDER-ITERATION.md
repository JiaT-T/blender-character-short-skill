# Scene and render iteration notes (2026-11-12)

These notes originally recorded reusable workflow lessons from local projects. The subsequent v46 [executable refinement stage](../blender-character-short/references/static-refinement.md) now implements the bounded compositor and scene-only operations described there. The historical statements below refer to the earlier documentation-only publication. The initial documentation-only publication retained the v45a producer. Version v46 now adds bounded, plan-driven static refinement; it still does not claim automatic scene generation or animation validation. Private projects, models, textures and reference
images are not distributed. The original v45a runtime evidence remains historical.

## Select and protect the baseline

Keep the pure-character MMD/MMR render baseline separate from stage projects and
pre-optimization backups. Record source hashes, copy before editing, and reopen
the saved candidate. Protect geometry, weights, controller relationships, morphs,
character materials and the approved source-look chain during scene-only work.
An improved character project must not silently replace a stage's frozen look.

## External scenes first

Prefer authorized external scenes whose style, scale and level of detail fit the
character and intended film. Reserve custom modeling for low-detail, secondary
items. Record author, original URL, modification permission, commercial and
redistribution restrictions before adopting assets. Permission to show a render
is not permission to distribute the source model or its textures.

Import into a copy. Compare full-body, face, feet/contact and room frames. Reduce
competing texture contrast and distracting objects before adding more lights.
Bring out useful structure in dark architectural areas without flattening the
image. Adjust scene-only materials and lights while protecting the approved
character look. A broad dark patch below the feet does not prove convincing
contact: inspect its width, softness and attachment to the actual soles.

Review depth of field and practical-light bloom explicitly. Keep face and costume
details readable. Static occlusion and frame-boundary checks support inspection,
but are not aesthetic acceptance or animation validation. If the requested scope
is static, do not add dynamic or temporal validation without a new reason.

## Borrow compositing selectively

Treat a supplied older project as a reference, not a replacement visual target.
Trace only branches that reach the active Composite output. A node's presence does
not establish that its effect is enabled. Check missing images, AOV registration,
object properties and color management before attributing a look to postprocessing.

Useful patterns include separately controllable effect branches, explicit masks,
highlight extraction and restrained bloom mixed with the clear original. Preserve
the approved material formulas, source curves and LUT unless a change is requested.
Avoid stacking a complete reference look on top of the existing look. Strong global
bloom can obscure white fabric and metallic trim; a small Kuwahara filter can soften
fine lines without enough benefit to justify adoption. A reference's known
camera-distance-dependent fringe-shadow defect must not be copied as a technique.

Keep sampling changes separate from compositing changes. Test GPU compositing and
precision on the actual supported Blender version; do not assume every node or
project follows the same execution path. Measure repeated warmed runs at the
same resolution, samples, camera and output settings. Record cold-start results
separately. Whole-frame timings and log-derived compositor tails are not isolated
per-node costs. A faster compositor does not guarantee a faster final frame when
sampling increases, nor does a still-image test certify real-time playback.

## Portable private handoff

Inventory external Blender libraries, file images, fonts, sounds, volumes and
geometry/simulation caches. Pack supported dependencies into a copy and retain
license notices. Reopen an extracted archive from another directory; verify image
decoding, required dependency resolution and protected scene data. Do not assume
an archive is portable merely because it opens on the source machine. Add-on
requirements and unresolved dependencies still need explicit documentation.

Private return of an owner's project is not a public redistribution grant. Keep
character archives, raw assets and local file paths out of this repository.

## Recorded local scope and remaining limits

- The pure-character optimization retained the approved Huaxu material/curve/LUT
  look, used controllable effect branches and GPU full-precision compositing, and
  reduced bloom. A reopened saved project passed 18 controller response checks.
  This is one local model, not cross-character certification.
- The scene V05 pass reviewed seven 720p stills, preserved 13 character/look
  protection checks and retained 100 packed images. Dark room structure and
  texture competition improved; broad soft contact shadows and a character/scene
  detail mismatch remain unresolved. User acceptance is not asserted.
- A separate portable character package reopened from another directory with
  88 packed file images verified. That private package is not included here.
- No continuous animation or temporal-stability acceptance was performed for
  these latest revisions. Physics operation remains separately scoped.

These notes describe local outcomes; use the v46 refinement contract for the precise automated subset and required inputs. Default new-video output remains 1280x720 at 24 fps unless
higher specifications are explicitly requested; preserve existing project timing.
