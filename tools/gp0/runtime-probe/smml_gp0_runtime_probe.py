#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import stat
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROBE_VERSION = "0.1.3"
MARKER = "[SMML-GP0-PROBE]"

TARGETS = {
    "Survival/Scripts/game/SurvivalGame.lua": "934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4",
    "Survival/Scripts/game/SurvivalPlayer.lua": "960d15b4a5f66e1fd9ea4af6bd81a6088893b9f71bd8c1ad9c6bafaa592ecf76",
    "Survival/Scripts/game/tools/CarryTool.lua": "ddbb727a8fb687f290f35ff359d626bdcf4983930c51ad24daadd26ee8702dbf",
    "Survival/Scripts/game/managers/QuestManager.lua": "f4f489f8213715ebd54c378ab816bffaf3eb71f98267bb45594267a42222b17f",
    "Survival/Scripts/game/interactables/Crafter.lua": "f58f5bfb91172bd9ea60a2a7e5b8a3e5eae52e0b0ce6e07e988c6c08866f541c",
}
CACHE_PATH = "Cache/Bundle/core_data.cbo"
CACHE_SHA256 = "682efa4378e69f1a711e1d2147c302fbdd0dc8035f841c948d50c50964181351"
RUNTIME_PATH = "Survival/Scripts/SMMLProbe/Runtime.lua"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def default_state_dir() -> Path:
    override = os.environ.get("SMML_GP0_PROBE_STATE")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "SMML" / "GP0RuntimeProbe"
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "smml" / "gp0-runtime-probe"
    return Path.home() / ".local" / "state" / "smml" / "gp0-runtime-probe"


def game_running() -> list[str]:
    hits: list[str] = []
    proc = Path("/proc")
    if proc.is_dir():
        for child in proc.iterdir():
            if not child.name.isdigit():
                continue
            try:
                cmd = (child / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
                comm = (child / "comm").read_text("utf-8", errors="ignore").strip()
            except OSError:
                continue
            hay = (comm + " " + cmd).lower()
            if "scrapmechanic.exe" in hay or "scrap mechanic/release/scrapmechanic" in hay:
                hits.append(f"pid={child.name} {comm} {cmd[:180]}")
    return hits


def require_game_stopped() -> None:
    hits = game_running()
    if hits:
        raise SystemExit("Scrap Mechanic appears to be running:\n" + "\n".join(hits))


def load_state(state_dir: Path) -> dict:
    path = state_dir / "state.json"
    if not path.is_file():
        raise SystemExit(f"Probe state not found: {path}")
    return json.loads(path.read_text("utf-8"))


def save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(state_dir / "state.json", (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def patch_prefix_visible(file_name: str) -> str:
    return f'''-- SMML_GP0_PROBE_BEGIN:file:{file_name}\nif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.mark ) == "function" then\n    __SMML_GP0_PROBE.mark( "file_eval", {{ file = "{file_name}", visible = true }} )\nelse\n    local __smml_msg = "[SMML-GP0-PROBE] FALLBACK|event=file_eval|file={file_name}|visible=false"\n    if type( sm ) == "table" and type( sm.log ) == "table" and type( sm.log.error ) == "function" then\n        sm.log.error( __smml_msg )\n    elseif type( print ) == "function" then\n        print( __smml_msg )\n    end\nend\n-- SMML_GP0_PROBE_END:file:{file_name}\n'''


def callback_snippet(class_name: str, method: str, side: str, extra: str = "") -> str:
    body = f'''\t-- SMML_GP0_PROBE_BEGIN:callback:{class_name}.{method}\n\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.mark ) == "function" then\n\t\t__SMML_GP0_PROBE.mark( "callback", {{ class = "{class_name}", method = "{method}", side = "{side}" }} )\n{extra}\tend\n\t-- SMML_GP0_PROBE_END:callback:{class_name}.{method}\n'''
    return body


def inject_after_once(text: str, anchor: str, insertion: str, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}: {anchor!r}")
    return text.replace(anchor, anchor + insertion, 1)


def apply_patch(rel: str, original: bytes) -> bytes:
    text = original.decode("utf-8")

    if rel == "Survival/Scripts/game/SurvivalGame.lua":
        prefix = '''-- SMML_GP0_PROBE_BEGIN:file:SurvivalGame.lua\nlocal function __smml_gp0_fallback( stage, detail )\n    local msg = "[SMML-GP0-PROBE] FALLBACK|event=runtime_unavailable|file=SurvivalGame.lua|stage=" .. tostring( stage )\n    if detail ~= nil then msg = msg .. "|detail=" .. tostring( detail ) end\n    if type( sm ) == "table" and type( sm.log ) == "table" and type( sm.log.error ) == "function" then\n        sm.log.error( msg )\n    elseif type( print ) == "function" then\n        print( msg )\n    end\nend\n\nlocal function __smml_gp0_load_runtime( stage )\n    if type( pcall ) ~= "function" then\n        __smml_gp0_fallback( stage, "pcall-unavailable" )\n        return false\n    end\n    local ok, err = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMMLProbe/Runtime.lua" )\n    if not ok then\n        __smml_gp0_fallback( stage, err )\n        return false\n    end\n    return true\nend\n\n__smml_gp0_load_runtime( "first-load" )\nif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.bootstrap ) == "function" and type( __SMML_GP0_PROBE.mark ) == "function" then\n    __SMML_GP0_PROBE.bootstrap( "SurvivalGame.file.begin" )\n    __SMML_GP0_PROBE.mark( "file_eval", { file = "SurvivalGame.lua", visible = true } )\nelse\n    __smml_gp0_fallback( "first-load-postcheck" )\nend\n-- Deliberate second load/bootstrap: proves idempotence without requiring dev refresh.\n__smml_gp0_load_runtime( "second-load" )\nif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.bootstrap ) == "function" then\n    __SMML_GP0_PROBE.bootstrap( "SurvivalGame.file.second" )\nelse\n    __smml_gp0_fallback( "second-load-postcheck" )\nend\n-- SMML_GP0_PROBE_END:file:SurvivalGame.lua\n'''
        text = prefix + text
        text = inject_after_once(
            text,
            "function SurvivalGame.server_onCreate( self )\n",
            callback_snippet("SurvivalGame", "server_onCreate", "server", "\t\tif type( __SMML_GP0_PROBE.runErrorIsolation ) == \"function\" then __SMML_GP0_PROBE.runErrorIsolation( \"server\" ) end\n"),
            rel,
        )
        refresh_extra = '''\t\tif type( __smml_gp0_load_runtime ) == "function" then __smml_gp0_load_runtime( "server_onRefresh" ) end\n\t\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.bootstrap ) == "function" then __SMML_GP0_PROBE.bootstrap( "SurvivalGame.server_onRefresh" ) end\n'''
        text = inject_after_once(
            text,
            "function SurvivalGame.server_onRefresh( self )\n",
            callback_snippet("SurvivalGame", "server_onRefresh", "server", refresh_extra),
            rel,
        )
        text = inject_after_once(
            text,
            "function SurvivalGame.client_onCreate( self )\n",
            callback_snippet("SurvivalGame", "client_onCreate", "client", "\t\tif type( __SMML_GP0_PROBE.runErrorIsolation ) == \"function\" then __SMML_GP0_PROBE.runErrorIsolation( \"client\" ) end\n"),
            rel,
        )

    elif rel == "Survival/Scripts/game/SurvivalPlayer.lua":
        text = patch_prefix_visible("SurvivalPlayer.lua") + text
        for method, side in [
            ("server_onCreate", "server"), ("server_onRefresh", "server"),
            ("client_onCreate", "client"), ("client_onRefresh", "client")
        ]:
            text = inject_after_once(text, f"function SurvivalPlayer.{method}( self )\n", callback_snippet("SurvivalPlayer", method, side), rel)

    elif rel == "Survival/Scripts/game/managers/QuestManager.lua":
        text = patch_prefix_visible("QuestManager.lua") + text
        for method, side in [("server_onCreate", "server"), ("client_onCreate", "client"), ("client_onRefresh", "client")]:
            text = inject_after_once(text, f"function QuestManager.{method}( self )\n", callback_snippet("QuestManager", method, side), rel)

    elif rel == "Survival/Scripts/game/interactables/Crafter.lua":
        text = patch_prefix_visible("Crafter.lua") + text
        for method, side in [
            ("server_onCreate", "server"), ("server_onRefresh", "server"),
            ("client_onCreate", "client"), ("client_onRefresh", "client")
        ]:
            text = inject_after_once(text, f"function Crafter.{method}( self )\n", callback_snippet("Crafter", method, side), rel)

    elif rel == "Survival/Scripts/game/tools/CarryTool.lua":
        text = patch_prefix_visible("CarryTool.lua") + text
        for method, side in [("server_onCreate", "server"), ("client_onCreate", "client"), ("client_onRefresh", "client")]:
            text = inject_after_once(text, f"function CarryTool.{method}( self )\n", callback_snippet("CarryTool", method, side), rel)

        hot_insert = '''\t-- SMML_GP0_PROBE_BEGIN:callback:CarryTool.cl_tryInsert\n\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.count ) == "function" and type( __SMML_GP0_PROBE.markLimited ) == "function" then\n\t\t__SMML_GP0_PROBE.count( "CarryTool.cl_tryInsert" )\n\t\tif primaryState == sm.tool.interactState.start then\n\t\t\t__SMML_GP0_PROBE.markLimited( "CarryTool.cl_tryInsert.start", 20, "carry", { method = "cl_tryInsert", side = "client", input = "start", carryUuid = carryUuid } )\n\t\telse\n\t\t\t__SMML_GP0_PROBE.markLimited( "CarryTool.cl_tryInsert.first", 1, "carry", { method = "cl_tryInsert", side = "client", input = "passive" } )\n\t\tend\n\tend\n\t-- SMML_GP0_PROBE_END:callback:CarryTool.cl_tryInsert\n'''
        text = inject_after_once(text, "function CarryTool.cl_tryInsert( self, character, primaryState, playerCarry, carryUuid, playerCarryColor )\n", hot_insert, rel)

        drop = '''\t-- SMML_GP0_PROBE_BEGIN:callback:CarryTool.cl_tryDrop\n\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.count ) == "function" and type( __SMML_GP0_PROBE.markLimited ) == "function" then\n\t\t__SMML_GP0_PROBE.count( "CarryTool.cl_tryDrop" )\n\t\t__SMML_GP0_PROBE.markLimited( "CarryTool.cl_tryDrop", 20, "carry", { method = "cl_tryDrop", side = "client", carryUuid = carryUuid } )\n\tend\n\t-- SMML_GP0_PROBE_END:callback:CarryTool.cl_tryDrop\n'''
        text = inject_after_once(text, "function CarryTool.cl_tryDrop( self, primaryState, secondaryState, playerCarry, carryUuid, characterShape, playerCarryColor )\n", drop, rel)

        sv_drop = '''\t-- SMML_GP0_PROBE_BEGIN:callback:CarryTool.sv_n_dropCarry\n\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.markLimited ) == "function" then\n\t\t__SMML_GP0_PROBE.markLimited( "CarryTool.sv_n_dropCarry", 20, "carry", { method = "sv_n_dropCarry", side = "server", player = player, hasShapePlacement = params ~= nil and params.shapePlacement ~= nil } )\n\tend\n\t-- SMML_GP0_PROBE_END:callback:CarryTool.sv_n_dropCarry\n'''
        text = inject_after_once(text, "function CarryTool.sv_n_dropCarry( self, params, player )\n", sv_drop, rel)

        sv_send = '''\t-- SMML_GP0_PROBE_BEGIN:callback:CarryTool.sv_n_sendItem\n\tif type( __SMML_GP0_PROBE ) == "table" and type( __SMML_GP0_PROBE.markLimited ) == "function" then\n\t\t__SMML_GP0_PROBE.markLimited( "CarryTool.sv_n_sendItem", 20, "carry", { method = "sv_n_sendItem", side = "server", player = player, hasTargetShape = params ~= nil and params.targetShape ~= nil } )\n\tend\n\t-- SMML_GP0_PROBE_END:callback:CarryTool.sv_n_sendItem\n'''
        text = inject_after_once(text, "function CarryTool.sv_n_sendItem( self, params, player )\n", sv_send, rel)
    else:
        raise RuntimeError(f"No patch recipe for {rel}")

    return text.encode("utf-8")


def verify_clean_root(root: Path) -> None:
    if not (root / "Survival").is_dir() or not (root / "Data").is_dir():
        raise SystemExit(f"Not a Scrap Mechanic root: {root}")
    problems = []
    for rel, expected in TARGETS.items():
        p = root / rel
        if not p.is_file():
            problems.append(f"MISSING {rel}")
            continue
        actual = sha256_file(p)
        if actual != expected:
            problems.append(f"MODIFIED {rel}\n  expected {expected}\n  actual   {actual}")
    cache = root / CACHE_PATH
    if not cache.is_file():
        problems.append(f"MISSING {CACHE_PATH}")
    else:
        actual = sha256_file(cache)
        if actual != CACHE_SHA256:
            problems.append(f"MODIFIED {CACHE_PATH}\n  expected {CACHE_SHA256}\n  actual   {actual}")
    if (root / RUNTIME_PATH).exists():
        problems.append(f"EXTRA {RUNTIME_PATH} already exists")
    if problems:
        raise SystemExit("Preflight failed:\n" + "\n".join(problems))


def install(args: argparse.Namespace) -> None:
    require_game_stopped()
    root = args.game_root.expanduser().resolve()
    state_dir = args.state_dir.expanduser().resolve()
    if (state_dir / "state.json").exists():
        old = json.loads((state_dir / "state.json").read_text("utf-8"))
        if old.get("installed"):
            raise SystemExit(f"Probe is already installed according to {state_dir / 'state.json'}")
    verify_clean_root(root)

    package_dir = Path(__file__).resolve().parent
    runtime_src = package_dir / "payload" / "Runtime.lua"
    if not runtime_src.is_file():
        raise SystemExit(f"Missing payload: {runtime_src}")

    backup_dir = state_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    records = {}

    # Prepare every patched file before writing anything.
    prepared = {}
    for rel, expected in TARGETS.items():
        src = root / rel
        original = src.read_bytes()
        if hashlib.sha256(original).hexdigest() != expected:
            raise SystemExit(f"Preflight changed during install: {rel}")
        patched = apply_patch(rel, original)
        prepared[rel] = patched
        backup = backup_dir / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, backup)
        records[rel] = {
            "before_sha256": expected,
            "after_sha256": hashlib.sha256(patched).hexdigest(),
            "backup": str(backup),
        }

    cache_src = root / CACHE_PATH
    cache_backup = backup_dir / CACHE_PATH
    cache_backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cache_src, cache_backup)

    runtime_data = runtime_src.read_bytes()
    runtime_target = root / RUNTIME_PATH

    # Commit.
    for rel, patched in prepared.items():
        atomic_write(root / rel, patched)
    atomic_write(runtime_target, runtime_data)
    cache_src.unlink()  # targeted invalidation; original is preserved in state dir

    installed_epoch = time.time()
    state = {
        "schema": "smml-gp0-runtime-probe/1",
        "probe_version": PROBE_VERSION,
        "installed": True,
        "installed_at_utc": utc_now(),
        "installed_epoch": installed_epoch,
        "game_root": str(root),
        "runtime": {
            "path": RUNTIME_PATH,
            "sha256": hashlib.sha256(runtime_data).hexdigest(),
        },
        "files": records,
        "cache": {
            "path": CACHE_PATH,
            "before_sha256": CACHE_SHA256,
            "backup": str(cache_backup),
            "invalidated": True,
        },
    }
    save_state(state_dir, state)
    print("[OK] SMML GP0 Runtime Probe installed")
    print(f"State: {state_dir}")
    print(f"Targeted cache invalidated: {CACHE_PATH}")
    print("Next: launch Scrap Mechanic normally (without -dev), load a Survival world, then close the game cleanly.")


def status(args: argparse.Namespace) -> None:
    state_dir = args.state_dir.expanduser().resolve()
    state = load_state(state_dir)
    root = Path(state["game_root"])
    print(f"Probe version: {state.get('probe_version')}")
    print(f"Installed: {state.get('installed')}")
    print(f"Game root: {root}")
    for rel, rec in state.get("files", {}).items():
        p = root / rel
        current = sha256_file(p) if p.is_file() else None
        label = "PATCHED" if current == rec.get("after_sha256") else "RESTORED" if current == rec.get("before_sha256") else "DRIFT"
        print(f"{label:8} {rel}")
    rp = root / state["runtime"]["path"]
    current = sha256_file(rp) if rp.is_file() else None
    label = "PRESENT" if current == state["runtime"]["sha256"] else "ABSENT" if current is None else "DRIFT"
    print(f"{label:8} {state['runtime']['path']}")
    cp = root / state["cache"]["path"]
    if cp.exists():
        print(f"CACHE    {state['cache']['path']} sha256={sha256_file(cp)}")
    else:
        print(f"CACHE    {state['cache']['path']} absent")


def parse_probe_line(line: str) -> dict | None:
    if MARKER not in line:
        return None
    payload = line[line.index(MARKER):].strip()
    parts = payload.split("|")
    result = {"raw": payload}
    if parts:
        result["record"] = parts[0].replace(MARKER, "").strip()
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def collect(args: argparse.Namespace) -> None:
    state_dir = args.state_dir.expanduser().resolve()
    state = load_state(state_dir)
    root = Path(state["game_root"])
    logs_dir = root / "Logs"
    installed_epoch = float(state.get("installed_epoch", 0))
    output = args.output.expanduser().resolve() if args.output else Path.cwd() / f"smml-gp0-runtime-probe-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

    candidates = []
    if logs_dir.is_dir():
        for p in sorted(logs_dir.glob("game-*.log")):
            try:
                if p.stat().st_mtime >= installed_epoch - 60:
                    candidates.append(p)
            except OSError:
                pass

    events = []
    event_logs = []
    diagnostics = []

    diagnostic_needles = (
        "[Lua] ERROR:",
        "Failed to load file:",
        "Load failed",
        "SMMLProbe",
        "SMML-GP0-PROBE",
    )

    for p in candidates:
        try:
            text = p.read_text("utf-8", errors="replace")
        except OSError:
            continue

        local_events = []
        for line_no, line in enumerate(text.splitlines(), 1):
            parsed = parse_probe_line(line)
            if parsed:
                parsed["source_log"] = p.name
                parsed["line"] = line_no
                events.append(parsed)
                local_events.append(parsed)

            if any(needle in line for needle in diagnostic_needles):
                diagnostics.append({
                    "source_log": p.name,
                    "line": line_no,
                    "text": line,
                })

        if local_events:
            event_logs.append(p)

    current = {}
    for rel, rec in state.get("files", {}).items():
        p = root / rel
        current[rel] = {
            "exists": p.is_file(),
            "sha256": sha256_file(p) if p.is_file() else None,
            "expected_patched_sha256": rec.get("after_sha256"),
        }

    rp = root / state["runtime"]["path"]
    cp = root / state["cache"]["path"]
    current[state["runtime"]["path"]] = {
        "exists": rp.is_file(),
        "sha256": sha256_file(rp) if rp.is_file() else None,
    }
    current[state["cache"]["path"]] = {
        "exists": cp.is_file(),
        "sha256": sha256_file(cp) if cp.is_file() else None,
    }

    event_counts = Counter(e.get("event", "") for e in events)
    runtime_counts = Counter(e.get("runtime", "") for e in events if e.get("runtime"))
    callback_counts = Counter(
        f"{e.get('class')}.{e.get('method')}:{e.get('side')}"
        for e in events
        if e.get("event") == "callback"
    )

    summary = {
        "schema": "smml-gp0-runtime-probe-results/1.2",
        "probe_version": state.get("probe_version"),
        "collected_at_utc": utc_now(),
        "candidate_logs": [p.name for p in candidates],
        "event_logs": [p.name for p in event_logs],
        "event_count": len(events),
        "diagnostic_line_count": len(diagnostics),
        "event_counts": dict(event_counts),
        "runtime_ids": dict(runtime_counts),
        "callback_counts": dict(callback_counts),
        "current_files": current,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("summary.json", json.dumps(summary, indent=2, sort_keys=True))
        zf.writestr("state.json", json.dumps(state, indent=2, sort_keys=True))
        zf.writestr(
            "probe-lines.txt",
            "\n".join(e["raw"] for e in events) + ("\n" if events else ""),
        )

        if diagnostics:
            zf.writestr(
                "diagnostic-lines.txt",
                "\n".join(
                    f"{d['source_log']}:{d['line']}: {d['text']}"
                    for d in diagnostics
                ) + "\n",
            )
        else:
            zf.writestr("diagnostic-lines.txt", "")

        if events:
            keys = sorted({k for e in events for k in e.keys() if k != "raw"})
            import io
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for e in events:
                w.writerow({k: e.get(k, "") for k in keys})
            zf.writestr("events.csv", buf.getvalue())

        # Always preserve candidate logs. This is essential when the probe fails
        # before it has a chance to emit its first marker.
        for p in candidates:
            zf.write(p, f"raw-logs/{p.name}")

    print(
        f"[OK] Collected {len(events)} probe events from "
        f"{len(candidates)} candidate log(s); {len(event_logs)} contained probe events"
    )
    print(output)


def uninstall(args: argparse.Namespace) -> None:
    require_game_stopped()
    state_dir = args.state_dir.expanduser().resolve()
    state = load_state(state_dir)
    if not state.get("installed"):
        raise SystemExit("State says the probe is not installed.")
    root = Path(state["game_root"])

    problems = []
    for rel, rec in state.get("files", {}).items():
        p = root / rel
        if not p.is_file():
            problems.append(f"MISSING patched file: {rel}")
            continue
        current = sha256_file(p)
        if current != rec.get("after_sha256"):
            problems.append(f"DRIFT {rel}\n  expected patched {rec.get('after_sha256')}\n  current          {current}")
    rp = root / state["runtime"]["path"]
    if not rp.is_file():
        problems.append(f"MISSING runtime: {state['runtime']['path']}")
    elif sha256_file(rp) != state["runtime"]["sha256"]:
        problems.append(f"DRIFT runtime: {state['runtime']['path']}")
    if problems:
        raise SystemExit("Uninstall preflight refused to modify files:\n" + "\n".join(problems))

    # Restore exact originals.
    for rel, rec in state.get("files", {}).items():
        backup = Path(rec["backup"])
        data = backup.read_bytes()
        if hashlib.sha256(data).hexdigest() != rec["before_sha256"]:
            raise SystemExit(f"Backup integrity failure: {backup}")
        atomic_write(root / rel, data)

    # Remove probe-owned runtime.
    rp.unlink()
    probe_dir = rp.parent
    try:
        probe_dir.rmdir()
    except OSError:
        pass

    # Quarantine any cache rebuilt while the probe was active, then restore the exact pre-probe cache.
    cp = root / state["cache"]["path"]
    if cp.exists():
        quarantine = state_dir / "quarantine" / f"core_data.cbo.probe-generated-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cp), str(quarantine))
    cache_backup = Path(state["cache"]["backup"])
    if sha256_file(cache_backup) != state["cache"]["before_sha256"]:
        raise SystemExit(f"Cache backup integrity failure: {cache_backup}")
    atomic_write(cp, cache_backup.read_bytes())

    # Verify exact restoration.
    failures = []
    for rel, rec in state.get("files", {}).items():
        if sha256_file(root / rel) != rec["before_sha256"]:
            failures.append(rel)
    if sha256_file(cp) != state["cache"]["before_sha256"]:
        failures.append(state["cache"]["path"])
    if failures:
        raise SystemExit("Restoration verification failed: " + ", ".join(failures))

    state["installed"] = False
    state["uninstalled_at_utc"] = utc_now()
    save_state(state_dir, state)
    print("[OK] Probe removed; patched files and core_data.cbo restored byte-for-byte.")
    print("Runtime logs are intentionally left untouched.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SMML GP0 passive runtime probe")
    p.add_argument("--state-dir", type=Path, default=default_state_dir(), help="Persistent probe state directory")
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("install", help="Validate and install the passive probe")
    i.add_argument("game_root", type=Path)
    i.set_defaults(func=install)

    s = sub.add_parser("status", help="Show current probe state")
    s.set_defaults(func=status)

    c = sub.add_parser("collect", help="Collect probe events and matching game logs")
    c.add_argument("--output", type=Path)
    c.set_defaults(func=collect)

    u = sub.add_parser("uninstall", help="Restore the exact pre-probe files")
    u.set_defaults(func=uninstall)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
