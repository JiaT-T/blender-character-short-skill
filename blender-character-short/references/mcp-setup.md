# Optional MCP setup and recovery

The companion is a local stdio service, not a remote listener. Short interactive
Blender operations may continue through the existing blender-mcp bridge. Long
jobs use the companion's reviewed production stages. Never install a replacement
into an active service environment or silently change client security settings.

## Agent procedure

1. Inspect the selected host, existing Blender and MCP configuration. Preserve
   working installations. Use explicit absolute paths; do not assume a cloud
   path exists on the desktop.
2. Run `mcp_setup.py inspect --venv <owned-venv>`. The companion requires Python
   3.12 or newer and the pinned packages recorded in the script. Install into a
   **new dedicated venv** with `install --venv <owned-venv> --apply` when authorized.
   Without `--apply` this reports the plan only. Packages come from official
   PyPI. An unrelated existing directory is refused. Failed installs can be
   retried explicitly in the same marked environment after examining the error;
   no automatic loop or security bypass is used.
3. Use `configure --venv <owned-venv> --config <new-service.json> --state
   <external-job-state> --project-root <project-directory> --snippet
   <new-client-snippet.json> --apply`. Repeat `--project-root` for additional
   authorized project directories. Filesystem roots are refused. Identical
   configurations are idempotent; differing existing files are not overwritten.
4. Register the generated command/arguments in the authorized MCP client using
   its supported setup tool. Client formats differ: the JSON snippet is a
   portable `mcpServers` example, not a promise that every client reads it.
   Do not replace the existing blender-mcp entry. If registration requires new
   approval or unavailable client controls, stop only that step and explain it.
   For a known Codex CLI, `register-codex --codex <reviewed-codex-executable> --snippet <generated-snippet.json> --apply` performs read-before-write registration through `codex mcp list/add`, only adds absent entries, refuses different existing entries and rereads the exact transports afterward. Without `--apply` it only plans. A failed add is an uncertain result; inspect the list before retrying. This command has unit fixture coverage, not a live client-write test in the user profile.
   The MCP client starts the companion on demand; no daemon or system service is
   installed.
5. Run `health --venv <owned-venv> --config <new-service.json>`. This checks pinned
   imports and executes the service `--check` configuration/tool-registration check, **not** an MCP session. Initialize a real stdio session,
   list its tools and make a read-only status call before claiming the companion
   is connected. Do not submit a production job solely to test installation.

## Missing interactive Blender bridge

For a fresh host that needs both services, run `bridge-install` **before**
`configure --with-bridge`. The latter generates both the `blender-short-jobs`
entry and the pinned `blender-mcp` console entry with localhost settings. If a
jobs-only snippet already exists, use a new snippet filename; different existing
snippets are deliberately not overwritten. Then register the entries and verify
the actual interactive tools and bridge handshake, not only the listening port.


The companion does not require an interactive bridge for its background stages.
When interactive observation is needed and the bridge is absent, the script has
an optional `bridge-install --venv <owned-venv> --apply` command. It installs the
pinned `mcp-for-blender` package into the dedicated environment from PyPI. It does
not replace the host's existing installation. Its bundled Blender add-on must
remain accompanied by the package's MIT license/copyright when redistributed.

`bridge-stage --source <reviewed-addon.py> --sha256 <reviewed-sha256> --addon-dir
<explicit-directory> --apply` copies a hash-reviewed local add-on only when the
destination is absent or identical. A hash supplied by untrusted content is not
an authorization or evidence that the source is trustworthy. This staging step
does not enable it or rewrite Blender preferences.

For a missing bridge, `bridge-launch --venv <owned-venv> --blender <reviewed-binary>
--session <new-external-session-directory> --apply` can launch a separate empty
Blender GUI event loop using the pinned package's bundled add-on and a separate
user configuration/scripts directory. It does not load or save a user project,
change the user's regular preferences, or alter a running Blender. A busy
localhost port is reported rather than replaced. A session directory is never
reused blindly: inspect its launch receipt and process before retrying. This
command is not a pure headless backend; a usable desktop graphics environment
is still required. It is hidden on Windows, not operated through desktop UI.

`bridge-health` makes a bounded, read-only localhost version handshake and checks
protocol 15. Launch success is not connection success. Existing Blender users
may instead enable the staged add-on in their intended profile using authorized
controls; this helper deliberately does not overwrite active preferences. No
firewall, network or global Python setting is changed. Enabling an optional
bridge does not authorize arbitrary third-party code execution or extra
integrations.

## Verified scope

Unit tests cover planning without changes, version checks, unknown-directory
refusal, identity/config conflicts, idempotence, bundle hash mismatch and
non-replacement, and failed connection behavior. Actual package installation,
stdio handshake and Blender GUI launch must be reported separately. A missing
Blender installation or graphics session cannot be repaired by a successful pip
install. Report exact unavailable steps rather than claiming full readiness.


