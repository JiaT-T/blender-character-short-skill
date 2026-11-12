"""Explicit, idempotent setup of the optional local stdio MCP companion.

Never replaces an existing service/client configuration. Only explicit
bridge-launch --apply starts a separate empty Blender session.
Use --apply only after installation/configuration is authorized.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

PIN = "1.30.0"
PACKAGES = {"mcp": PIN, "numpy": "2.5.4", "Pillow": "13.0.0", "imageio-ffmpeg": "0.6.0"}
BRIDGE_PIN = "2.2.4"
OWNER = ".short-mcp-setup.json"
SCRIPTS = Path(__file__).resolve().parent


def absolute(value: str | Path) -> Path:
    p = Path(value).expanduser()
    if not p.is_absolute():
        raise ValueError("Use an explicit absolute path")
    return p.resolve()


def run(command: list[str]) -> subprocess.CompletedProcess:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, creationflags=flags)


def python_at(folder: Path) -> Path:
    return folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def inspect_environment(folder: str | Path) -> dict:
    folder = absolute(folder)
    python = python_at(folder)
    data = {"venv": str(folder), "python": str(python), "exists": python.is_file(), "required_mcp": PIN, "status": "missing"}
    if not python.is_file():
        return data
    probe = "import importlib.metadata as m,json;from mcp.server.fastmcp import FastMCP;print(json.dumps({k:m.version(k) for k in " + repr(list(PACKAGES)) + "}))"
    try:
        data.update(json.loads(run([str(python), "-I", "-c", probe]).stdout.strip().splitlines()[-1]))
        data["status"] = "ready" if all(data[k] == v for k, v in PACKAGES.items()) else "version_mismatch"
    except (subprocess.CalledProcessError, ValueError, IndexError) as exc:
        data.update(status="dependency_unavailable", error=str(exc))
    return data


def install(folder: str | Path, apply: bool = False) -> dict:
    folder = absolute(folder)
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12+ is required")
    if folder.is_relative_to(SCRIPTS.parent):
        raise ValueError("Keep installation state outside the skill package")
    if folder == Path(folder.anchor):
        raise ValueError("A filesystem root is not a venv directory")
    marker = folder / OWNER
    if folder.exists() and not marker.is_file():
        raise ValueError("Existing directory is not owned by this setup; select a new venv")
    expected = {"schema": 1, "component": "short-mcp-companion", "packages": PACKAGES}
    if marker.exists() and json.loads(marker.read_text("utf-8")) != expected:
        raise ValueError("Existing setup identity differs; select a new venv")
    command = [str(python_at(folder)), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--retries", "1", "--timeout", "30", "--index-url", "https://pypi.org/simple", *[k + "==" + v for k, v in PACKAGES.items()]]
    if not apply:
        return {"status": "planned", "venv": str(folder), "command": command, "authorization_required": True}
    folder.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        with marker.open("x", encoding="utf-8") as f:
            json.dump(expected, f, indent=2)
    if not python_at(folder).exists():
        venv.EnvBuilder(with_pip=True).create(folder)
    current = inspect_environment(folder)
    if current["status"] != "ready":
        try:
            run(command)
        except subprocess.CalledProcessError as exc:
            return {"status": "installation_failed", "error": str(exc), "stderr": exc.stderr[-4000:], "automatic_retry": False}
    return inspect_environment(folder)


def write_new_or_same(path: Path, value: dict) -> bool:
    if path.exists():
        if json.loads(path.read_text("utf-8")) == value:
            return False
        raise ValueError("Refusing to replace different existing configuration: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


def configuration(folder: str | Path, config: str | Path, state: str | Path, roots: list[str], snippet: str | Path, apply: bool = False, with_bridge: bool = False) -> dict:
    folder, config, state, snippet = map(absolute, (folder, config, state, snippet))
    if any(p.is_relative_to(SCRIPTS.parent) for p in (config, state, snippet)):
        raise ValueError("Keep setup and runtime state outside the skill package")
    resolved = [absolute(p) for p in roots]
    if not resolved or any(not p.is_dir() or p == Path(p.anchor) for p in resolved):
        raise ValueError("Declare existing, narrowly scoped project directories, not filesystem roots")
    if config == snippet:
        raise ValueError("Service config and client snippet must be different files")
    payload = {"schema": 1, "state_dir": str(state), "project_roots": [str(p) for p in resolved]}
    client = {"mcpServers": {"blender-short-jobs": {"command": str(python_at(folder)), "args": [str(SCRIPTS / "mcp_service.py"), "--config", str(config)]}}}
    if with_bridge:
        client["mcpServers"]["blender-mcp"] = bridge_client(folder)
    # Validate both targets before creating either to avoid partial conflicting setup.
    for path, content in ((config, payload), (snippet, client)):
        if path.exists() and json.loads(path.read_text("utf-8")) != content:
            raise ValueError("Existing config differs; no changes made: " + str(path))
    if apply:
        if inspect_environment(folder)["status"] != "ready":
            raise ValueError("Install the pinned companion dependency before configuring")
        if not (SCRIPTS / "mcp_service.py").is_file():
            raise ValueError("Companion service entry is missing")
        write_new_or_same(config, payload)
        write_new_or_same(snippet, client)
    return {"status": "configured" if apply else "planned", "service_config": payload, "client_snippet": client,
            "client_registration": "not_applied", "next": "Register the generated command in the authorized MCP client; it starts the service on demand via stdio."}


def stage_bridge(source: str | Path, digest: str, addon_dir: str | Path, apply: bool = False) -> dict:
    """Stage an explicitly reviewed local Blender bridge without replacing it.

    Hash provenance/authorization is supplied by the caller, not invented here.
    This does not trust arbitrary third-party instructions to install code.
    """
    import re
    source, addon_dir = absolute(source), absolute(addon_dir)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("A reviewed SHA256 is required")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Source hash does not match the reviewed bridge")
    compile(data, str(source), "exec")
    dest = addon_dir / "blender_mcp.py"
    if dest.exists() and dest.read_bytes() != data:
        raise ValueError("A different bridge exists; refusing replacement")
    if apply and not dest.exists():
        addon_dir.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as f:
            f.write(data)
    return {"status": "staged" if apply else "planned", "destination": str(dest), "sha256": digest,
            "enabled": False, "next": "Enable the reviewed add-on in the intended Blender profile and validate its localhost connection; do not overwrite active preferences."}


def health(folder: str | Path, config: str | Path | None = None) -> dict:
    data = inspect_environment(folder)
    data["server_entry_exists"] = (SCRIPTS / "mcp_service.py").is_file()
    data["stdio_session_verified"] = False
    data["blender_bridge_connection_verified"] = False
    if not data["server_entry_exists"] and data["status"] == "ready":
        data["status"] = "invalid_configuration"
    if config:
        cfg = json.loads(absolute(config).read_text("utf-8"))
        data["config_schema"] = cfg.get("schema")
        data["roots_available"] = bool(cfg.get("project_roots")) and all(absolute(p).is_dir() for p in cfg.get("project_roots", []))
        if cfg.get("schema") != 1 or not data["roots_available"] or not data["server_entry_exists"]:
            data["status"] = "invalid_configuration"
        if data["status"] == "ready" and data["server_entry_exists"]:
            try:
                checked = run([str(python_at(absolute(folder))), str(SCRIPTS / "mcp_service.py"), "--config", str(absolute(config)), "--check"])
                data["service_check"] = {"passed": True, "output": checked.stdout.strip()}
            except (subprocess.CalledProcessError, ValueError) as exc:
                data.update(status="service_check_failed", error=str(exc))
    return data


def install_bridge_package(folder: str | Path, apply: bool = False) -> dict:
    folder = absolute(folder)
    if not (folder / OWNER).is_file():
        raise ValueError("First create an owned companion venv; never modify unrelated environments")
    command = [str(python_at(folder)), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--retries", "1", "--timeout", "30", "--index-url", "https://pypi.org/simple", "mcp-for-blender==" + BRIDGE_PIN, *[k + "==" + v for k, v in PACKAGES.items()]]
    if not apply:
        return {"status": "planned", "command": command}
    run(command)
    probe = "import importlib.metadata as m,json,pathlib;d=m.distribution('mcp-for-blender');p=d.locate_file('blender_mcp/bundled/addon.py');print(json.dumps({'version':d.version,'addon':str(p)}))"
    result = json.loads(run([str(python_at(folder)), "-I", "-c", probe]).stdout.strip().splitlines()[-1])
    if result["version"] != BRIDGE_PIN or not Path(result["addon"]).is_file():
        raise ValueError("Pinned bridge bundle is unavailable")
    if inspect_environment(folder)["status"] != "ready":
        raise ValueError("Companion dependency pins changed during bridge install")
    result["status"] = "package_ready"
    return result


def bridge_bundle(folder: str | Path) -> Path:
    folder = absolute(folder)
    probe = "import importlib.metadata as m,json;d=m.distribution('mcp-for-blender');print(json.dumps({'version':d.version,'addon':str(d.locate_file('blender_mcp/bundled/addon.py'))}))"
    info = json.loads(run([str(python_at(folder)), "-I", "-c", probe]).stdout.strip().splitlines()[-1])
    if info["version"] != BRIDGE_PIN:
        raise ValueError("Bridge version mismatch")
    addon = Path(info["addon"]).resolve()
    if not addon.is_relative_to(folder) or not addon.is_file():
        raise ValueError("Bundle must belong to the selected environment")
    return addon


def launch_bridge(folder: str | Path, blender: str | Path, session: str | Path, apply: bool = False) -> dict:
    """Start a separate empty GUI Blender profile; never touch a live project.

    The localhost bridge is available only while that process is alive. Client
    registration and a real handshake remain separate checks.
    """
    import socket
    folder, blender, session = map(absolute, (folder, blender, session))
    if not blender.is_file() or blender.name.lower() not in ("blender", "blender.exe"):
        raise ValueError("Specify the reviewed official Blender executable")
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", 9876)) == 0:
            return {"status": "port_in_use", "started": False, "next": "Verify the existing bridge; never assume a listening port is the expected service."}
    if session.exists():
        raise ValueError("Session directory already exists; inspect its receipt before any retry")
    source = bridge_bundle(folder)
    license_probe = "import importlib.metadata as m,json;d=m.distribution('mcp-for-blender');print(json.dumps([str(d.locate_file(p)) for p in d.files if str(p).endswith('/LICENSE')]))"
    licenses = [Path(p).resolve() for p in json.loads(run([str(python_at(folder)), "-I", "-c", license_probe]).stdout.strip().splitlines()[-1])]
    if not licenses or any(not p.is_file() or not p.is_relative_to(folder) for p in licenses):
        raise ValueError("Bundled bridge license missing")
    data = source.read_bytes()
    fingerprint = hashlib.sha256(data).hexdigest()
    command = [str(blender), "--factory-startup", "--disable-autoexec", "--python", str(session / "enable_bridge.py")]
    if not apply:
        return {"status": "planned", "command": command, "addon_sha256": fingerprint, "uses_gui_event_loop": True}
    session.mkdir(parents=True)
    (session / "blender-mcp-LICENSE.txt").write_bytes(licenses[0].read_bytes())
    addon_dir = session / "scripts" / "addons"
    stage_bridge(source, fingerprint, addon_dir, True)
    startup = "import bpy\nbpy.ops.preferences.addon_enable(module='blender_mcp')\n"
    (session / "enable_bridge.py").write_text(startup, encoding="utf-8")
    env = dict(os.environ, BLENDER_USER_CONFIG=str(session / "config"), BLENDER_USER_SCRIPTS=str(session / "scripts"))
    kwargs = {}
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs.update(startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    receipt = {"status": "launching", "command": command, "addon_sha256": fingerprint, "session": str(session), "connection_verified": False}
    write_new_or_same(session / "launch.json", receipt)
    with (session / "blender.log").open("xb") as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kwargs)
    receipt.update(status="launched_unverified", pid=child.pid)
    (session / "launch.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt

def bridge_health() -> dict:
    """Read-only bounded protocol handshake with the localhost bridge."""
    import socket
    import time
    data = bytearray()
    deadline = time.monotonic() + 5
    try:
        with socket.create_connection(("127.0.0.1", 9876), timeout=2) as sock:
            sock.sendall(json.dumps({"type": "get_addon_info", "params": {}}).encode())
            while time.monotonic() < deadline and len(data) < 65536:
                sock.settimeout(max(0.05, deadline - time.monotonic()))
                chunk = sock.recv(8192)
                if not chunk: break
                data.extend(chunk)
                try: reply = json.loads(data)
                except (ValueError, UnicodeDecodeError): continue
                info = reply.get("result", {})
                valid = reply.get("status") == "success" and info.get("protocol_version") == 15
                return {"status": "bridge_ready" if valid else "unexpected_bridge", "verified_protocol": valid, "reply": reply}
    except (OSError, TimeoutError) as exc:
        return {"status": "bridge_unavailable", "verified_protocol": False, "error": str(exc), "automatic_restart": False}
    return {"status": "incomplete_handshake", "verified_protocol": False, "automatic_restart": False}

def bridge_client(folder: Path) -> dict:
    probe = "import importlib.metadata as m,json;d=m.distribution('mcp-for-blender');print(json.dumps({'version':d.version,'entries':[(e.name,e.value) for e in d.entry_points if e.group=='console_scripts']}))"
    info = json.loads(run([str(python_at(folder)), "-I", "-c", probe]).stdout.strip().splitlines()[-1])
    if info.get("version") != BRIDGE_PIN or ["mcp-for-blender", "blender_mcp.server:main"] not in info.get("entries", []):
        raise ValueError("Pinned bridge console entrypoint was not verified")
    command = folder / ("Scripts/mcp-for-blender.exe" if os.name == "nt" else "bin/mcp-for-blender")
    if not command.is_file():
        raise ValueError("Bridge console launcher is missing")
    return {"command": str(command), "args": [], "env": {"BLENDER_HOST": "127.0.0.1", "BLENDER_PORT": "9876"}}


def register_codex(codex: str | Path, snippet: str | Path, apply: bool = False) -> dict:
    """Use the supported Codex CLI to add only absent, explicitly named entries."""
    codex, snippet = absolute(codex), absolute(snippet)
    if not codex.is_file() or codex.name.lower() not in ("codex", "codex.exe"):
        raise ValueError("An explicit reviewed Codex CLI executable is required")
    payload = json.loads(snippet.read_text("utf-8"))
    entries = payload.get("mcpServers", {})
    if not entries or not set(entries) <= {"blender-short-jobs", "blender-mcp"}:
        raise ValueError("Only the two scoped MCP entries may be registered")
    existing_rows = json.loads(run([str(codex), "mcp", "list", "--json"]).stdout)
    if not isinstance(existing_rows, list):
        raise ValueError("Unsupported Codex list response; no changes")
    existing = {row["name"]: row for row in existing_rows}
    commands = []
    for name, cfg in entries.items():
        if set(cfg) - {"command", "args", "env"} or not isinstance(cfg.get("args", []), list) or not isinstance(cfg.get("env", {}), dict):
            raise ValueError("Unsupported client entry")
        command = absolute(cfg["command"])
        if not command.is_file():
            raise ValueError("Configured launcher is missing")
        if name in existing:
            t = existing[name].get("transport", {})
            if (t.get("type"), t.get("command"), t.get("args", []), t.get("env") or {}) != ("stdio", str(command), cfg.get("args", []), cfg.get("env", {})):
                raise ValueError("Existing client entry differs; refusing replacement: " + name)
            continue
        argv = [str(codex), "mcp", "add", name]
        for key, value in sorted(cfg.get("env", {}).items()):
            argv += ["--env", str(key) + "=" + str(value)]
        commands.append(argv + ["--", str(command), *cfg.get("args", [])])
    if apply:
        for command in commands:
            try:
                run(command)
            except subprocess.CalledProcessError as exc:
                return {"status": "registration_uncertain", "error": str(exc), "automatic_retry": False,
                        "next": "Read Codex MCP list again before retrying; earlier entries may already be registered."}
        # Reconciliation reads the exact transport fields again; it makes no writes.
        verification = register_codex(codex, snippet, False)
        if verification["commands"]:
            return {"status": "registration_incomplete", "automatic_retry": False}
    return {"status": "registered" if apply else "planned", "commands": commands, "connected": False,
            "next": "Initialize the configured MCP session and verify tools before claiming it is connected."}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("inspect", "install", "health"):
        q = sub.add_parser(action); q.add_argument("--venv", required=True)
        if action == "install": q.add_argument("--apply", action="store_true")
        if action == "health": q.add_argument("--config")
    q = sub.add_parser("configure")
    for name in ("venv", "config", "state", "snippet"): q.add_argument("--" + name, required=True)
    q.add_argument("--project-root", action="append", required=True); q.add_argument("--apply", action="store_true"); q.add_argument("--with-bridge", action="store_true")
    q = sub.add_parser("bridge-stage")
    for name in ("source", "sha256", "addon-dir"): q.add_argument("--" + name, required=True)
    q.add_argument("--apply", action="store_true")
    q = sub.add_parser("bridge-install"); q.add_argument("--venv", required=True); q.add_argument("--apply", action="store_true")
    q = sub.add_parser("bridge-launch")
    for name in ("venv", "blender", "session"): q.add_argument("--" + name, required=True)
    q.add_argument("--apply", action="store_true")
    sub.add_parser("bridge-health")
    q = sub.add_parser("register-codex"); q.add_argument("--codex", required=True); q.add_argument("--snippet", required=True); q.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.action == "inspect": result = inspect_environment(a.venv)
    elif a.action == "install": result = install(a.venv, a.apply)
    elif a.action == "health": result = health(a.venv, a.config)
    elif a.action == "configure": result = configuration(a.venv, a.config, a.state, a.project_root, a.snippet, a.apply, a.with_bridge)
    elif a.action == "register-codex": result = register_codex(a.codex, a.snippet, a.apply)
    elif a.action == "bridge-health": result = bridge_health()
    elif a.action == "bridge-install": result = install_bridge_package(a.venv, a.apply)
    elif a.action == "bridge-launch": result = launch_bridge(a.venv, a.blender, a.session, a.apply)
    else: result = stage_bridge(a.source, a.sha256, a.addon_dir, a.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") in ("installation_failed", "missing", "dependency_unavailable", "version_mismatch", "service_check_failed", "invalid_configuration", "bridge_unavailable", "unexpected_bridge", "incomplete_handshake", "registration_uncertain", "registration_incomplete"):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())










