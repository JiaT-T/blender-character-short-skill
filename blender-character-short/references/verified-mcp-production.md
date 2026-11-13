# Saved scene execution through MCP

The local companion runs the same allowlisted production stages as the CLI.
Keep its stdio session alive until the worker has finished. Use immutable source,
plan and producer identities for each output. An author script has its own
identity; a renderer hash alone does not identify how the acting or cameras were
created. Importing or authoring outside the service must be recorded as CLI work.

Run `doctor` for each project's configured `reports` directory before its other
production stages. A successful doctor in another project's directory does not
create the required `runtime.json` here. The runtime receipt must match the
declared runtime and Blender binary. If the directory is new, submit a new doctor
request first and inspect its completed process receipt before continuing.

## Installed addon activation

Declare the exact three-part `runtime.blender_version` and `runtime.addons`
versions. The background bootstrap checks all declarations before enabling
missing installed addons in that process. Allowed modules are MMD Tools and
MikuMikuRig. Duplicate JSON keys, conflicting MMD aliases, missing modules and
version disagreement fail. This route neither installs addons nor saves user
preferences. Existing blender-mcp interactive editing is a separate capability.

## Bind the saved cameras

An optional `render.shot_plan` is a declared path and SHA256. Its inclusive
display range and rate must match the render job and fit inside the saved scene.
Each shot start must have the declared scene camera marker; an extra switch
inside a shot fails. The contract is recorded in the frame signature and copied
into the encoded-video receipt. It does not create cameras or judge the story.

Optional asset-to-object bindings observe evaluated matrices at `[cut-1, cut]`.
The frame, subframe and active camera are restored afterwards. These observations
describe motion; they do not accept attachment, contact or continuity.

## Bake the declared actor

The physics stage requires a separately saved, assembled, unbaked input. Keep
that checkpoint. A scene may contain another MMD root, such as an imported set.
The cache helper resolves the actor through the declared native armature and
checks its existing controller bindings. An optional `mmd_root` must name that
same root; removing or hiding other roots is unnecessary.

If the world includes a passive floor, declare `physics_population` with exact
`joints`, `world_bodies`, `world_constraints` and `passive_bodies`. Every extra
body must be a named independent passive mesh; joint endpoints must belong to
the actor. Undeclared bodies and mismatched populations fail before baking.

Baking creates a new output. A second background process reopens that output
and checks the embedded cache, every integer-frame rigid/controller/native
matrix, and protected stored data. Existing solver values are preserved.
`is_frame_skip` fails; `is_outdated` is recorded as a diagnostic rather than
treated as proof of corruption. Neither flag alone certifies visible quality.

Record the bake process exit and the fresh reader process exit separately. Both
must be zero; a cache file or a report containing `cache_baked: true` cannot
overrule a failed process. Preserve failed outputs and inspect them before making
an explicit recovery decision. Do not automatically replay over those outputs.

## Interruptions and metadata

Submission binds the project bytes, external plans and shared resource together.
Durable `prepared` metadata proves worker launch was not reached. Repeating that
exact request records failure and cleans only its matching reservation; it does
not launch a stage. A queued, running or uncertain job is never replayed this way.

Windows metadata replacement retries only sharing/access errors, using the same
fsynced temporary file, at most six attempts and 0.31 seconds of total backoff.
This is metadata publication, not a retry of Blender or the stage. A failed read
returns a bounded diagnostic and retains the reservation for inspection.

Cancellation remains cooperative between stages or render batches. Verify the
actual worker and descendants have exited on the host, then inspect closed
receipts and frame hashes. Do not poll live JSON files with Windows readers that
deny replacement; use append logs or a read-only process handle while work runs.
An unexplained intermittent terminal `uncertain` test result remains unresolved.
Successful repeats and a completed cancellation exercise do not establish its
root cause or prove survival after a client kills the process tree.

## Evidence boundaries

Keep CPU fault injection, actual stdio execution, native cache checks, actual
skin/foot measurements and encoded visual review separate. All-frame decoding
and contact sheets are useful evidence but are not continuous normal-speed
viewing. A production may require further corrections even when every technical
check passes. Source models, textures, action libraries, indices and films stay
outside the distribution.
