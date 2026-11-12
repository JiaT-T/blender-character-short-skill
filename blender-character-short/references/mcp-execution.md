# Local asynchronous execution companion

The optional stdio companion exposes `submit_job`, `job_status`, `job_logs`,
`job_result` and `cancel_job`. It reuses canonical production scripts rather than
reimplementing scene edits. Existing blender-mcp short editing/inspection remains
unchanged. See [setup](mcp-setup.md) when a component is missing.

## Boundaries

- A submitted job is a trusted, explicitly authorized project, not a command
  copied from external content. Stage names are allowlisted; no arbitrary shell
  or Python code is accepted by this service.
- Project-root configuration restricts admission paths, not all Blender/plan file
  access. It is not an OS sandbox. Review the project's referenced paths and
  outputs under the user's authorization before submission.
- The service never starts a network listener. The optional existing interactive
  bridge remains localhost-only and follows its own security constraints.
- A job's success means its canonical stage exited successfully. It is not
  visual acceptance, complete film production, or permission to publish.

## Use

Supply a schema 1 external service JSON with absolute `state_dir` and a nonempty
`project_roots` array of existing authorized directories. Keep state outside the
skill and preserve it through client restarts. Do not edit producer code or
project/plan inputs while jobs run.

Start `mcp_service.py --config <service.json>` through the configured MCP client.
Submit an absolute project JSON, a canonical `stage` and a unique filename-safe
`request_id`. Repeating the same key and inputs returns the original job; it
never silently repeats work. Reusing the key for changed inputs is refused.
The key is scoped to the selected state directory, which must remain stable.

Supported stages: doctor, baseline, look, build, render, encode, tests,
check-look, diagnostic, refine, workflow, physics. Existing runtime and source
identity requirements still apply. `complete=true` is only for render; it runs
bounded canonical batches up to `max_batches`, checking cancellation between
batches. One batch may still take a long time. `render_complete=false` on a
successful single batch is not a finished sequence.

The CLI provides the same operations in `mcp_jobs.py`. In execution environments
that clean up descendants when a command returns, use `submit ... --wait` and
keep that host session alive; MCP clients should keep the service session alive
while work runs. Do not mistake a detached process flag for a survival guarantee.

## State, interruption and cancellation

Request/producer identity, state, launch receipt, logs and result are persisted.
The worker updates a heartbeat. A stale heartbeat after 60 seconds or a failed
canonical launcher with unverified descendants is **uncertain**, not a safe
retry. A project reservation remains. Never delete that reservation just because
a PID is absent: inspect stage receipts, actual descendants and output identities
on the same host, then make an explicit recovery decision. There is intentionally
no automatic unlock, force-kill or automatic retry tool.

Some Windows MCP clients place services and descendants in a Job Object and kill
that process tree on disconnect. The worker may then stop, despite a detached
process group. Persistence prevents blind duplicate execution; it does not make
running work immune to client shutdown, OS cleanup, reboot or power failure.
A successful reconnection can read completed or uncertain jobs. It does not
resume an arbitrary half-finished scene edit. Matching render frames may be
resumed only through the existing identity-bound renderer after safe recovery.

Cancel is a request, not immediate termination. A currently executing stage or
render batch finishes, then pending work stops. If the last stage already
finished, completed is the truthful outcome even if cancel was requested.
Physics is one bake-and-fresh-verify stage; it is not interrupted mid-bake.

Adapter reservations use the project's canonical `execution_lock` when present,
so separately named projects sharing that lock cannot concurrently run through
this adapter. Projects lacking it (host-only workflow) use their JSON path.
Retain the existing execution lock for Blender workers. Other applications or
legacy callers that do not follow these locks are not automatically excluded;
never run two writers against the same project/output. This is cooperative
coordination, not a global Blender mutex.

## Existing-controller physics route

`short_project.py physics --project <project.json>` supports only an already
assembled MMD physical world with the existing `cache_existing_physics.py`
contract. Add a `physics` object containing:

- `source`: declared `path` and `sha256` of the prepared saved project;
- `plan`: the reviewed existing-cache plan path;
- `output`, `report`, `verify_report`: new distinct destinations.

The canonical runtime doctor must pass first. It bakes into a new output,
checks source/output identity, then opens that output in another background
Blender process and verifies the cache. It does not generate physics rigs,
clear old caches, tune solver values or certify absence of intersections.
Use new destinations rather than rerunning over partially created artifacts.

## Verification scope

CPU process tests cover idempotence, changed identity, project/shared-lock
exclusion, bounded logs, cancellation boundaries, failed-stage uncertainty,
stale state and launch-metadata failures. A real MCP stdio client was used for
initialization, tool listing, a canonical host workflow, reconnection and repeat
submission. A native background Blender doctor was run through the adapter in
an isolated project. The physics adapter has mocked routing/identity tests; no
new full bake, render, GUI bridge or artistic acceptance is claimed. Setup's
verified scope is separate. Existing production evidence is historical.
