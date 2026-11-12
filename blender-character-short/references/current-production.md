# Current local production entry (v46.1, based on v45a)

Use the selected package's `scripts/short_project.py`. All commands require an
external reviewed project JSON except `version`. The host-only `workflow` stage uses only the brief/report contract and does not require a runtime receipt. A project owns its runtime,
baseline/role plans, look donor and output paths. Relative paths are based on
that project or the explicitly referenced plan, not the assistant's cwd.

```text
python -B scripts/short_project.py version
python -B scripts/short_project.py doctor --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py baseline --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py look --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py check-look --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py check-look --project EXTERNAL_PROJECT.json --reference
python -B scripts/short_project.py diagnostic --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py render --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py render --project EXTERNAL_PROJECT.json --complete --max-seconds 1800
python -B scripts/short_project.py encode --project EXTERNAL_PROJECT.json
python -B scripts/short_project.py tests --project EXTERNAL_PROJECT.json
```

`build` runs doctor, baseline preparation/fresh verification, then look transfer.
It does not author a story or generate an animated film. After adding reviewed
actions, expressions, scenery/cameras and required physics to a new saved copy,
declare that copy in `render.source` with its actual SHA256. Otherwise render
uses the saved look output, which can still be static. Baseline inputs with
existing armature/shape actions or NLA are refused; supplied drivers are allowed.

`diagnostic` optionally creates a separate, short head/blink/camera-cut fixture
from the verified static look. Its external `diagnostic` object declares new
output/report, frame count, fps and size. It never generates a story or substitutes
for a library action; it exists to test actual time/camera-dependent rendering.
Declare its saved output hash as `render.source` before the production check.

## External project contract

New videos default to **1280×720, 24 fps** unless the user explicitly asks for
higher specifications. `production_defaults.py` supplies that authoring preset;
the diagnostic builder uses it when size/fps are omitted. The saved renderer
defaults omitted dimensions to 1280×720 but always reads the scene's actual
fps/fps_base; it never retimes an existing project. Explicit current-job 1080p30
settings remain unchanged. Author a new saved 24 fps scene before rendering a
future standard video; do not relabel 30 fps frames as 24 fps.

Project schema1 has a short filename-safe `id`, `runtime`, `reports`,
`execution_lock`, `baseline_plan`, `look`, `render`, and `movie`.
`look_checks` is needed for `check-look`.

- Runtime declares an existing Blender executable, exact `blender_version`,
  enabled addon module→version arrays and a coordination thread count. Doctor
  reads ordinary addon metadata or an official extension manifest. It does not
  install addons, save preferences or start UI. Other stages require the matching
  runtime receipt and executable hash.
- `baseline_plan` is a relative path to an external plan with `mode:provided`
  or `generate`, hash-bound `source` and `profile`, new `output`, `report`,
  `verify_report`, and optional deliberate fps for this unanimated baseline.
  Generation additionally declares a hash-bound `mapping` and
  `generation_guidance_acknowledged:true`. It refuses an existing rig/metarig.
- Baseline profile declares actual `model`, `controller`, `mesh`, facing
  `towards`, and small probes. Each probe has `id`, control/model-bone names,
  `kind:rotate|translate`, axis, amount and optional explicit property switches.
  These probes inspect actual weighted skin and restore in-memory controls.
  Character calibration stays outside the skill.
- `look` has hash-bound `donor` and `profile`, new `output` and `report`.
  The profile maps donor scene/mesh to the target mesh, explicitly allowed look
  color attributes, object aliases, source-light names and a reviewed shadow
  budget. Geometry, UVs and material-index mapping must genuinely correspond.
  No arbitrary PMX/GLB UV conversion is implied.
- `look_checks` declares a hash-bound role profile, optional baseline profile
  for post-transfer skin probes, and a fresh output directory. Its cases name
  the actual cameras, head/shape controls, source head axes and HET helper
  attribute. Checks include camera change/return, closed eyes and head turns.
  Reference mode renders the donor, not a website screenshot. Image review is
  still required after technical checks.
- `render` has optional hash-bound `source`, output directory, engine assertion,
  width/height, sample count, first/last frames, `post_mode:saved-native`,
  optional effective-fps assertion, `batch_frames`, `budget_seconds` and
  hash-bound dependencies. Dependencies include role/render profiles and any
  separately declared resources. `movie` is a new MP4 path.

Every file descriptor is `{path,sha256}` with the real file digest. Do not force
an old hash to match an edited artifact. Reports bind the newly saved file's
actual bytes; a repeat save is not assumed to have identical bytes.

Completed baseline reuse additionally requires the same bound source, role
profile, generation mapping/mode, optional baseline fps and output. A fresh
verification receipt is tied to that exact baseline and producer. Saved-look
reuse checks its target, donor, profile and output identity, not just the saved
file's existence. Legacy receipts without this binding require a new baseline
version; do not mark them compatible manually.

## Saved look and a single compositor

The h07 integration treats the approved packed donor as a restricted role asset.
Generic code transfers its materials, attributes, helper graph/driver references
and reviewed native compositor, while preserving the target rig/skin/action
state. It clones supported native nodes with input defaults and image/group IDs,
checks graph identity, and rejects unsupported effects instead of approximating
them. Existing target native post is replaced, not graded a second time.

Use **saved-native only** for that scene. Do not then call `post_sequence.py`
on its PNGs. The preserved raw source-AOV route is a different explicit path.
Rendering on a GPU does not require the compositor or encoder to run on a GPU.
Source-derived HET/receiver shadows/Bloom remain visual approximations; no
stencil/MRT/SMAA or source-website pixel equivalence is asserted.

## Render identity and recovery

`saved_project_render.py` and the updated `render_queue.py` preserve saved
fps/fps_base. The queue requires hash-bound jobs and explicit post mode; the
old size-only job/cache format is intentionally refused. `jobs.example.json`
illustrates the new shape; replace every example path/hash with reviewed inputs.

The identity covers .blend bytes, declared resources, all producer Python files,
version file, Blender binary, engine, dimensions/samples, frame-rate pair/range,
saved camera cuts and compositor mode. Images must be packed and linked
libraries/external simulation caches are refused by this route. Embedded
reviewed physics caches can be asserted with `require_cache:true`.

Before resuming, every receipted PNG is checked for name, dimensions, bytes and
hash. An unreceipted PNG, changed input/script, forged completion flag or edited
PNG fails. The output has an exclusive writer lock. Bounded runs stop after a
completed frame; rerun the same project to continue. A hard failure leaving an
unreceipted final/partial PNG requires inspection and a separately chosen
recovery/output version; it is not silently adopted.

The encoder accepts only a complete, input-verified sequence, rechecks producer
and input identities, derives fps from the render receipt, encodes silent H.264
with an explicit colour conversion, then checks actual decoded dimensions, fps,
frame count and duration. It never invokes external grading.
An added or removed producer script also invalidates encoding of an old frame
set. Keep the exact producer package paired with historical renders.

## Acceptance and reuse boundary

The local validation receipt, not inventory counts, identifies what passed for
this build. Tests cover contracts and API behavior; integration uses one real
MMD character and a short diagnostic timeline. It does not certify a fresh
story, arbitrary MMD rigs, every finger-IK control, physical grip, perfect
collision, continuous naturalness or another machine. Keep users' approvals
bound to the exact film/version they reviewed.

## Static refinement (v46 addition)

Declare an external `refine_plan`, run doctor for the current runtime, then use
`short_project.py refine --project PROJECT.json`. See the
[full refinement contract](static-refinement.md). Existing stages retain their
previous contracts; old producer-bound frame receipts must not be reused.

## New-short workflow

Follow [production workflow](production-workflow.md) before technical stages. `workflow` records readiness and stage evidence without changing assets or starting Blender. Story, retrieval, shader fallback and shot authoring remain explicit agent work, not an automatic `build` side effect.
