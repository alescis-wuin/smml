#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.5.2"
RUNTIME_VERSION = "0.5.2"
MARKER = "[SMML-RUNTIME] EVT"

TRANSPORT_EXPECTED = {
    "T-RPC-01": {"contract": "probe.echo@1", "dispatch": "ok", "accepted": "true", "code": "ok", "result": "remote-1"},
    "T-RPC-02": {"contract": "probe.unknown@1", "dispatch": "unknown_contract", "accepted": "false", "code": "unknown_contract", "result": "nil"},
    "T-RPC-03": {"contract": "probe.throw@1", "dispatch": "handler_error", "accepted": "false", "code": "handler_error", "result": "nil"},
    "T-RPC-04": {"contract": "probe.echo@1", "dispatch": "ok", "accepted": "true", "code": "ok", "result": "remote-2"},
}

TARGETS = {
    "Survival/Scripts/game/SurvivalGame.lua": "934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4",
    "Survival/Scripts/game/SurvivalPlayer.lua": "960d15b4a5f66e1fd9ea4af6bd81a6088893b9f71bd8c1ad9c6bafaa592ecf76",
    "Survival/Scripts/game/tools/CarryTool.lua": "ddbb727a8fb687f290f35ff359d626bdcf4983930c51ad24daadd26ee8702dbf",
    "Survival/Scripts/game/interactables/Chest.lua": "02f13e72b6542725eb8fe8a1b07bcf3984ac472781f6b46751ca8fef691bc8e7",
}
CACHE_PATH = "Cache/Bundle/core_data.cbo"
CACHE_SHA256 = "682efa4378e69f1a711e1d2147c302fbdd0dc8035f841c948d50c50964181351"
RUNTIME_DEST = "Survival/Scripts/SMML/Runtime.lua"
CONTRACT_REGISTRY_DEST = "Survival/Scripts/SMML/ContractRegistry.lua"
TRANSPORT_SERVICE_DEST = "Survival/Scripts/SMML/TransportService.lua"
STORAGE_SERVICE_DEST = "Survival/Scripts/SMML/StorageService.lua"
CARRY_ADAPTER_DEST = "Survival/Scripts/SMML/CarryAdapter.lua"
CONFIG_DEST = "Survival/Scripts/SMML/RuntimeConfig.lua"

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SOURCE = ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "Runtime.lua"
CONTRACT_REGISTRY_SOURCE = ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "ContractRegistry.lua"
TRANSPORT_SERVICE_SOURCE = ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "TransportService.lua"
STORAGE_SERVICE_SOURCE = ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "StorageService.lua"
CARRY_ADAPTER_SOURCE = ROOT / "runtime" / "Survival" / "Scripts" / "SMML" / "CarryAdapter.lua"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    override = os.environ.get("SMML_RUNTIME_SPINE_STATE")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "smml" / "runtime-spine-lab"
    return Path.home() / ".local" / "state" / "smml" / "runtime-spine-lab"


def state_path(state_dir: Path) -> Path:
    return state_dir / "state.json"


def load_state(state_dir: Path) -> dict:
    path = state_path(state_dir)
    if not path.is_file():
        raise SystemExit(f"Missing state: {path}")
    data = json.loads(path.read_text("utf-8"))
    if data.get("schema") != "smml-runtime-spine-lab-state/1":
        raise SystemExit(f"Unsupported state schema: {data.get('schema')!r}")
    return data


def save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(state_path(state_dir), (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def game_running() -> list[str]:
    hits: list[str] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return hits
    for child in proc.iterdir():
        if not child.name.isdigit():
            continue
        try:
            cmd = (child / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
            comm = (child / "comm").read_text("utf-8", errors="ignore").strip()
        except OSError:
            continue
        hay = (comm + " " + cmd).lower()
        if "scrapmechanic" in hay or "scrapmechanic.exe" in hay:
            hits.append(f"pid={child.name} {comm}")
    return hits


def reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise SystemExit(f"Refusing symlink for {label}: {path}")


def validate_game_root(root: Path) -> None:
    if not root.is_dir() or not (root / "Survival").is_dir() or not (root / "Data").is_dir():
        raise SystemExit(f"Not a Scrap Mechanic root: {root}")
    reject_symlink(root, "game root")
    for rel, expected in TARGETS.items():
        path = root / rel
        reject_symlink(path, rel)
        if not path.is_file():
            raise SystemExit(f"Missing target: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise SystemExit(
                f"Preflight failed for {rel}: expected clean 1.0.6.889 baseline\n"
                f"  expected {expected}\n  actual   {actual}"
            )


def render_config(role: str, run_id: str) -> bytes:
    if role not in {"host", "client"}:
        raise ValueError(role)
    if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", run_id) is None:
        raise ValueError("run_id must match [A-Za-z0-9._:-]{1,80}")
    text = (
        "-- Generated by smml_runtime_spine_lab.py.\n"
        "__SMML_RUNTIME_CONFIG = {\n"
        "    enabled = true,\n"
        f"    role = \"{role}\",\n"
        f"    runId = \"{run_id}\"\n"
        "}\n"
        "return __SMML_RUNTIME_CONFIG\n"
    )
    return text.encode("utf-8")


def bootstrap_prefix(file_name: str, with_lifecycle_helpers: bool) -> str:
    base = f'''-- SMML_RUNTIME_SPINE_BEGIN:bootstrap:{file_name}\nlocal function __smml_runtime_spine_fallback( stage, detail )\n    local line = "[SMML-RUNTIME] FALLBACK|stage=" .. tostring( stage )\n    if detail ~= nil then line = line .. "|detail=" .. tostring( detail ) end\n    if type( sm ) == "table" and type( sm.log ) == "table" and type( sm.log.error ) == "function" then\n        sm.log.error( line )\n    elseif type( print ) == "function" then\n        print( line )\n    end\nend\n\nlocal function __smml_runtime_spine_ensure( source )\n    if type( __SMML_RUNTIME ) ~= "table" or __SMML_RUNTIME.version ~= "{RUNTIME_VERSION}" then\n        if type( pcall ) ~= "function" then\n            __smml_runtime_spine_fallback( source, "pcall-unavailable" )\n            return false\n        end\n        local ok, err = pcall( dofile, "$SURVIVAL_DATA/Scripts/SMML/Runtime.lua" )\n        if not ok then\n            __smml_runtime_spine_fallback( source, err )\n            return false\n        end\n    end\n    if type( __SMML_RUNTIME ) == "table" and type( __SMML_RUNTIME.bootstrap ) == "function" then\n        local ok, err = pcall( __SMML_RUNTIME.bootstrap, source )\n        if not ok then\n            __smml_runtime_spine_fallback( source, err )\n            return false\n        end\n        return true\n    end\n    __smml_runtime_spine_fallback( source, "runtime-missing-after-load" )\n    return false\nend\n\n__smml_runtime_spine_ensure( "{file_name}.file" )\n'''
    if with_lifecycle_helpers:
        base += '''\nlocal function __smml_runtime_spine_lifecycle( eventName, side, fields )\n    if type( __SMML_RUNTIME ) ~= "table" or type( __SMML_RUNTIME.lifecycle ) ~= "function" then\n        return false\n    end\n    local ok, err = pcall( __SMML_RUNTIME.lifecycle, eventName, side, fields )\n    if not ok then\n        if type( __SMML_RUNTIME.emit ) == "function" then\n            pcall( __SMML_RUNTIME.emit, "hook.error", { hook = eventName, detail = err } )\n        else\n            __smml_runtime_spine_fallback( eventName, err )\n        end\n        return false\n    end\n    return true\nend\n\nlocal function __smml_runtime_spine_isHostPlayer( player )\n    if player == nil or type( sm ) ~= "table" or type( sm.player ) ~= "table" or type( sm.player.getHostPlayer ) ~= "function" then\n        return false\n    end\n    local ok, hostPlayer = pcall( sm.player.getHostPlayer )\n    if not ok or hostPlayer == nil then\n        return false\n    end\n    return player.id == hostPlayer.id\nend\n\nlocal function __smml_runtime_spine_transportCall( method, a, b, c )\n    if type( __SMML_RUNTIME ) ~= "table" or type( __SMML_RUNTIME.transport ) ~= "table" then\n        return false\n    end\n    local fn = __SMML_RUNTIME.transport[method]\n    if type( fn ) ~= "function" then\n        return false\n    end\n    local ok, err = pcall( fn, a, b, c )\n    if not ok then\n        if type( __SMML_RUNTIME.emit ) == "function" then\n            pcall( __SMML_RUNTIME.emit, "hook.error", { hook = "transport." .. tostring( method ), detail = err } )\n        else\n            __smml_runtime_spine_fallback( "transport." .. tostring( method ), err )\n        end\n        return false\n    end\n    return true\nend\n\nlocal function __smml_runtime_spine_storageCall( method, a, b )\n    if type( __SMML_RUNTIME ) ~= "table" or type( __SMML_RUNTIME.storage ) ~= "table" then\n        return false\n    end\n    local fn = __SMML_RUNTIME.storage[method]\n    if type( fn ) ~= "function" then\n        return false\n    end\n    local ok, err = pcall( fn, a, b )\n    if not ok then\n        if type( __SMML_RUNTIME.emit ) == "function" then\n            pcall( __SMML_RUNTIME.emit, "hook.error", { hook = "storage." .. tostring( method ), detail = err } )\n        else\n            __smml_runtime_spine_fallback( "storage." .. tostring( method ), err )\n        end\n        return false\n    end\n    return true\nend\n'''
    base += f'''-- SMML_RUNTIME_SPINE_END:bootstrap:{file_name}\n'''
    return base

def inject_after_once(text: str, anchor: str, insertion: str, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}: {anchor!r}")
    return text.replace(anchor, anchor + insertion, 1)


def patch_survival_player(original: bytes) -> bytes:
    use_crlf = b"\r\n" in original and original.count(b"\r\n") == original.count(b"\n")
    text = original.decode("utf-8")
    if use_crlf:
        text = text.replace("\r\n", "\n")
    text = bootstrap_prefix("SurvivalPlayer.lua", False) + text
    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def patch_survival_game(original: bytes) -> bytes:
    use_crlf = b"\r\n" in original and original.count(b"\r\n") == original.count(b"\n")
    text = original.decode("utf-8")
    if use_crlf:
        text = text.replace("\r\n", "\n")
    text = bootstrap_prefix("SurvivalGame.lua", True) + text

    hooks = [
        (
            "function SurvivalGame.server_onCreate( self )\n",
            '\t__smml_runtime_spine_lifecycle( "server.create", "server", { source = "SurvivalGame.server_onCreate" } )\n\t__smml_runtime_spine_transportCall( "onServerCreate", self )\n\t__smml_runtime_spine_storageCall( "onServerCreate", self )\n',
        ),
        (
            "function SurvivalGame.server_onUnload( self )\n",
            '\t__smml_runtime_spine_lifecycle( "server.unload", "server", { source = "SurvivalGame.server_onUnload" } )\n',
        ),
        (
            "function SurvivalGame.client_onCreate( self )\n",
            '\t__smml_runtime_spine_lifecycle( "client.create", "client", { source = "SurvivalGame.client_onCreate" } )\n\t__smml_runtime_spine_transportCall( "onClientCreate", self )\n',
        ),
        (
            "function SurvivalGame.server_onPlayerJoined( self, player, newPlayer )\n",
            '\t__smml_runtime_spine_lifecycle( "player.join", "server", { source = "SurvivalGame.server_onPlayerJoined", isHostPlayer = __smml_runtime_spine_isHostPlayer( player ), newPlayer = newPlayer == true } )\n',
        ),
        (
            "function SurvivalGame.server_onPlayerLeft( self, player )\n",
            '\t__smml_runtime_spine_lifecycle( "player.left", "server", { source = "SurvivalGame.server_onPlayerLeft", isHostPlayer = __smml_runtime_spine_isHostPlayer( player ) } )\n',
        ),
    ]
    for anchor, insertion in hooks:
        text = inject_after_once(text, anchor, insertion, "SurvivalGame.lua")

    text = inject_after_once(
        text,
        "function SurvivalGame.client_onUpdate( self, dt )\n",
        '\t__smml_runtime_spine_transportCall( "onClientUpdate", self, dt )\n',
        "SurvivalGame.lua",
    )

    text = inject_after_once(
        text,
        "function SurvivalGame.server_onFixedUpdate( self, timeStep )\n",
        '\t__smml_runtime_spine_storageCall( "onServerFixedUpdate", self, timeStep )\n',
        "SurvivalGame.lua",
    )

    text += '''
-- SMML_RUNTIME_SPINE_BEGIN:transport_network_methods
function SurvivalGame.sv_smmlRuntimeEnvelope( self, envelope, player )
\t__smml_runtime_spine_transportCall( "onServerEnvelope", self, envelope, player )
end

function SurvivalGame.cl_smmlRuntimeReply( self, params )
\t__smml_runtime_spine_transportCall( "onClientReply", self, params )
end
-- SMML_RUNTIME_SPINE_END:transport_network_methods
'''

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")

def patch_carry_tool(original: bytes) -> bytes:
    use_crlf = b"\r\n" in original and original.count(b"\r\n") == original.count(b"\n")
    text = original.decode("utf-8")
    if use_crlf:
        text = text.replace("\r\n", "\n")

    text = bootstrap_prefix("CarryTool.lua", False) + text

    hook_anchor = "\n\treturn false\nend\n\nfunction CarryTool.cl_tryDrop"
    hook = (
        "\n\t-- SMML_RUNTIME_SPINE_BEGIN:carry.resolveInsertTarget@1\n"
        "\tif type( __SMML_RUNTIME ) == \"table\" and type( __SMML_RUNTIME.carry ) == \"table\" and type( __SMML_RUNTIME.carry.resolveInsertTarget ) == \"function\" then\n"
        "\t\tlocal __smml_ok, __smml_matched, __smml_targetShape, __smml_resolverId = pcall( __SMML_RUNTIME.carry.resolveInsertTarget, {\n"
        "\t\t\ttool = self, character = character, playerCarry = playerCarry, carryUuid = carryUuid, carryColor = playerCarryColor,\n"
        "\t\t\tprimaryState = primaryState, isStart = primaryState == sm.tool.interactState.start,\n"
        "\t\t\traycastSuccess = success == true, resultType = result and result.type or \"nil\", raycastResult = result\n"
        "\t\t} )\n"
        "\t\tif not __smml_ok then\n"
        "\t\t\tif type( __SMML_RUNTIME.emit ) == \"function\" then\n"
        "\t\t\t\tpcall( __SMML_RUNTIME.emit, \"hook.error\", { hook = \"carry.resolveInsertTarget@1\", detail = __smml_matched } )\n"
        "\t\t\tend\n"
        "\t\telseif __smml_matched == true and __smml_targetShape ~= nil then\n"
        "\t\t\tshowInsertInteraction()\n"
        "\t\t\tif primaryState == sm.tool.interactState.start then\n"
        "\t\t\t\tlocal fromPosition = character:getTpBonePos( CarryConfig[self.cl.carryType].transform.primaryBone )\n"
        "\t\t\t\tlocal fromRotation = character:getTpBoneRot( CarryConfig[self.cl.carryType].transform.primaryBone )\n"
        "\t\t\t\tlocal params = { containerA = playerCarry, itemA = carryUuid, quantityA = 1, targetShape = __smml_targetShape, fromPosition = fromPosition, fromRotation = fromRotation, color = playerCarryColor, __smmlResolverId = __smml_resolverId }\n"
        "\t\t\t\tif type( __SMML_RUNTIME.carry.onResolverClientSend ) == \"function\" then\n"
        "\t\t\t\t\tlocal __smml_send_ok, __smml_send_err = pcall( __SMML_RUNTIME.carry.onResolverClientSend, params )\n"
        "\t\t\t\t\tif not __smml_send_ok and type( __SMML_RUNTIME.emit ) == \"function\" then\n"
        "\t\t\t\t\t\tpcall( __SMML_RUNTIME.emit, \"hook.error\", { hook = \"carry.resolverClientSend\", detail = __smml_send_err } )\n"
        "\t\t\t\t\tend\n"
        "\t\t\t\tend\n"
        "\t\t\t\tself.network:sendToServer( \"sv_n_sendItem\", params )\n"
        "\t\t\tend\n"
        "\t\t\treturn true\n"
        "\t\tend\n"
        "\tend\n"
        "\t-- SMML_RUNTIME_SPINE_END:carry.resolveInsertTarget@1\n"
    )
    count = text.count(hook_anchor)
    if count != 1:
        raise RuntimeError(f"CarryTool.lua: expected exactly one final cl_tryInsert anchor, found {count}")
    text = text.replace(hook_anchor, hook + hook_anchor, 1)

    relay_anchor = "function CarryTool.sv_n_sendItem( self, params, player )\n\tparams.player = player\n"
    relay = (
        "\tif type( __SMML_RUNTIME ) == \"table\" and type( __SMML_RUNTIME.carry ) == \"table\" and type( __SMML_RUNTIME.carry.onVanillaServerRelay ) == \"function\" then\n"
        "\t\tlocal __smml_ok, __smml_err = pcall( __SMML_RUNTIME.carry.onVanillaServerRelay, params, player )\n"
        "\t\tif not __smml_ok and type( __SMML_RUNTIME.emit ) == \"function\" then\n"
        "\t\t\tpcall( __SMML_RUNTIME.emit, \"hook.error\", { hook = \"carry.vanillaRelay\", detail = __smml_err } )\n"
        "\t\tend\n"
        "\tend\n"
    )
    text = inject_after_once(text, relay_anchor, relay, "CarryTool.lua")

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def patch_chest(original: bytes) -> bytes:
    use_crlf = b"\r\n" in original and original.count(b"\r\n") == original.count(b"\n")
    text = original.decode("utf-8")
    if use_crlf:
        text = text.replace("\r\n", "\n")

    if "function Chest.sv_e_receiveItem" in text:
        raise RuntimeError("Chest.lua: refusing to overwrite an existing Chest.sv_e_receiveItem")

    class_matches = list(re.finditer(r"^Chest\s*=\s*class[^\n]*\n", text, re.MULTILINE))
    if len(class_matches) != 1:
        raise RuntimeError(f"Chest.lua: expected exactly one Chest class declaration, found {len(class_matches)}")

    receiver = (
        "-- SMML_RUNTIME_SPINE_BEGIN:carry.customReceiver@1\n"
        "function Chest.sv_e_receiveItem( self, params )\n"
        "\tif type( __SMML_RUNTIME ) ~= \"table\" or type( __SMML_RUNTIME.carry ) ~= \"table\" or type( __SMML_RUNTIME.carry.onCustomReceiverServer ) ~= \"function\" then\n"
        "\t\treturn\n"
        "\tend\n"
        "\tlocal __smml_ok, __smml_result = pcall( __SMML_RUNTIME.carry.onCustomReceiverServer, self, params )\n"
        "\tif not __smml_ok and type( __SMML_RUNTIME.emit ) == \"function\" then\n"
        "\t\tpcall( __SMML_RUNTIME.emit, \"hook.error\", { hook = \"carry.customReceiver\", detail = __smml_result } )\n"
        "\tend\n"
        "end\n"
        "-- SMML_RUNTIME_SPINE_END:carry.customReceiver@1\n"
    )
    class_end = class_matches[0].end()
    text = text[:class_end] + receiver + text[class_end:]
    text = bootstrap_prefix("Chest.lua", False) + text

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def patched_bytes(rel: str, original: bytes) -> bytes:
    if rel.endswith("SurvivalPlayer.lua"):
        return patch_survival_player(original)
    if rel.endswith("SurvivalGame.lua"):
        return patch_survival_game(original)
    if rel.endswith("CarryTool.lua"):
        return patch_carry_tool(original)
    if rel.endswith("Chest.lua"):
        return patch_chest(original)
    raise ValueError(rel)


def install(args: argparse.Namespace) -> None:
    running = game_running()
    if running:
        raise SystemExit("Scrap Mechanic appears to be running; stop it before install:\n" + "\n".join(running))

    root = args.game_root.expanduser().resolve()
    state_dir = args.state_dir.expanduser().resolve()
    validate_game_root(root)

    if state_path(state_dir).exists():
        raise SystemExit(f"State already exists: {state_path(state_dir)}. Uninstall or choose another state dir.")
    if not RUNTIME_SOURCE.is_file():
        raise SystemExit(f"Missing runtime source: {RUNTIME_SOURCE}")
    if not CONTRACT_REGISTRY_SOURCE.is_file():
        raise SystemExit(f"Missing ContractRegistry source: {CONTRACT_REGISTRY_SOURCE}")
    if not TRANSPORT_SERVICE_SOURCE.is_file():
        raise SystemExit(f"Missing TransportService source: {TRANSPORT_SERVICE_SOURCE}")
    if not STORAGE_SERVICE_SOURCE.is_file():
        raise SystemExit(f"Missing StorageService source: {STORAGE_SERVICE_SOURCE}")
    if not CARRY_ADAPTER_SOURCE.is_file():
        raise SystemExit(f"Missing CarryAdapter source: {CARRY_ADAPTER_SOURCE}")

    runtime_dest = root / RUNTIME_DEST
    contract_registry_dest = root / CONTRACT_REGISTRY_DEST
    transport_service_dest = root / TRANSPORT_SERVICE_DEST
    storage_service_dest = root / STORAGE_SERVICE_DEST
    carry_adapter_dest = root / CARRY_ADAPTER_DEST
    config_dest = root / CONFIG_DEST
    for path, label in (
        (runtime_dest, RUNTIME_DEST),
        (contract_registry_dest, CONTRACT_REGISTRY_DEST),
        (transport_service_dest, TRANSPORT_SERVICE_DEST),
        (storage_service_dest, STORAGE_SERVICE_DEST),
        (carry_adapter_dest, CARRY_ADAPTER_DEST),
        (config_dest, CONFIG_DEST),
    ):
        reject_symlink(path, label)
        if path.exists():
            raise SystemExit(f"Refusing to overwrite pre-existing runtime file: {path}")

    cache = root / CACHE_PATH
    reject_symlink(cache, CACHE_PATH)
    cache_before = None
    if cache.is_file():
        cache_before = sha256_file(cache)
        if cache_before != CACHE_SHA256:
            raise SystemExit(
                f"Preflight failed for {CACHE_PATH}: expected known clean cache or absence\n"
                f"  expected {CACHE_SHA256}\n  actual   {cache_before}"
            )

    state_dir.mkdir(parents=True, exist_ok=False)
    backup_dir = state_dir / "backup"
    backup_dir.mkdir(parents=True)

    records: dict[str, dict] = {}
    try:
        for rel, expected in TARGETS.items():
            src = root / rel
            before = src.read_bytes()
            after = patched_bytes(rel, before)
            backup = backup_dir / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(backup, before)
            atomic_write(src, after)
            records[rel] = {
                "before_sha256": expected,
                "after_sha256": sha256_bytes(after),
                "backup": str(backup),
            }

        runtime_data = RUNTIME_SOURCE.read_bytes()
        contract_registry_data = CONTRACT_REGISTRY_SOURCE.read_bytes()
        transport_service_data = TRANSPORT_SERVICE_SOURCE.read_bytes()
        storage_service_data = STORAGE_SERVICE_SOURCE.read_bytes()
        carry_adapter_data = CARRY_ADAPTER_SOURCE.read_bytes()
        config_data = render_config(args.role, args.run_id)
        atomic_write(runtime_dest, runtime_data)
        atomic_write(contract_registry_dest, contract_registry_data)
        atomic_write(transport_service_dest, transport_service_data)
        atomic_write(storage_service_dest, storage_service_data)
        atomic_write(carry_adapter_dest, carry_adapter_data)
        atomic_write(config_dest, config_data)

        cache_backup = None
        if cache.is_file():
            cache_backup = backup_dir / CACHE_PATH
            cache_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache, cache_backup)
            cache.unlink()

        state = {
            "schema": "smml-runtime-spine-lab-state/1",
            "version": VERSION,
            "installed_at_utc": utc_now(),
            "installed_epoch": time.time(),
            "game_root": str(root),
            "role": args.role,
            "run_id": args.run_id,
            "targets": records,
            "runtime": {
                "path": RUNTIME_DEST,
                "sha256": sha256_bytes(runtime_data),
            },
            "contract_registry": {
                "path": CONTRACT_REGISTRY_DEST,
                "sha256": sha256_bytes(contract_registry_data),
            },
            "transport_service": {
                "path": TRANSPORT_SERVICE_DEST,
                "sha256": sha256_bytes(transport_service_data),
            },
            "storage_service": {
                "path": STORAGE_SERVICE_DEST,
                "sha256": sha256_bytes(storage_service_data),
            },
            "carry_adapter": {
                "path": CARRY_ADAPTER_DEST,
                "sha256": sha256_bytes(carry_adapter_data),
            },
            "config": {
                "path": CONFIG_DEST,
                "sha256": sha256_bytes(config_data),
            },
            "cache": {
                "path": CACHE_PATH,
                "before_sha256": cache_before,
                "backup": str(cache_backup) if cache_backup else None,
                "invalidated": cache_before is not None,
            },
        }
        save_state(state_dir, state)
    except Exception:
        for rel in TARGETS:
            backup = backup_dir / rel
            if backup.is_file():
                atomic_write(root / rel, backup.read_bytes())
        if runtime_dest.exists():
            runtime_dest.unlink()
        if contract_registry_dest.exists():
            contract_registry_dest.unlink()
        if transport_service_dest.exists():
            transport_service_dest.unlink()
        if storage_service_dest.exists():
            storage_service_dest.unlink()
        if carry_adapter_dest.exists():
            carry_adapter_dest.unlink()
        if config_dest.exists():
            config_dest.unlink()
        cache_backup = backup_dir / CACHE_PATH
        if cache_backup.is_file():
            atomic_write(cache, cache_backup.read_bytes())
        shutil.rmtree(state_dir, ignore_errors=True)
        raise

    print("[OK] Runtime Spine lab installed")
    print(f"Role: {args.role}")
    print(f"Run ID: {args.run_id}")
    print(f"State: {state_dir}")
    print(f"Cache invalidated: {CACHE_PATH if cache_before is not None else 'cache already absent'}")


def runtime_file_keys(state: dict) -> tuple[str, ...]:
    return tuple(
        key for key in ("runtime", "contract_registry", "transport_service", "storage_service", "carry_adapter", "config")
        if isinstance(state.get(key), dict) and state.get(key, {}).get("path")
    )


def verify_installed(state: dict) -> list[str]:
    root = Path(state["game_root"])
    problems: list[str] = []
    for rel, rec in state.get("targets", {}).items():
        path = root / rel
        if not path.is_file():
            problems.append(f"missing patched target: {rel}")
        elif sha256_file(path) != rec.get("after_sha256"):
            problems.append(f"patched target changed: {rel}")
    for key in runtime_file_keys(state):
        rec = state.get(key, {})
        path = root / rec.get("path", "")
        if not path.is_file():
            problems.append(f"missing {key}: {rec.get('path')}")
        elif sha256_file(path) != rec.get("sha256"):
            problems.append(f"{key} changed: {rec.get('path')}")
    return problems


def status(args: argparse.Namespace) -> None:
    state = load_state(args.state_dir.expanduser().resolve())
    problems = verify_installed(state)
    print(f"Version: {state.get('version')}")
    print(f"Role: {state.get('role')}")
    print(f"Run ID: {state.get('run_id')}")
    print(f"Game root: {state.get('game_root')}")
    print("Installed state: " + ("OK" if not problems else "CHANGED"))
    for problem in problems:
        print(f"- {problem}")


def decode_value(value: str) -> str:
    replacements = {
        "%0A": "\n",
        "%0D": "\r",
        "%3D": "=",
        "%7C": "|",
        "%25": "%",
    }
    out = value
    for encoded, decoded in replacements.items():
        out = out.replace(encoded, decoded)
    return out


def parse_event_line(line: str) -> dict | None:
    if MARKER not in line:
        return None
    payload = line[line.index(MARKER):].strip()
    parts = payload.split("|")
    if not parts or parts[0] != MARKER:
        return None
    result: dict[str, str] = {"raw": payload}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = decode_value(value.strip())
    return result


def summarize(events: list[dict], state: dict) -> dict:
    counts = Counter(e.get("event", "") for e in events)
    runtimes: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        runtimes[event.get("runtimeId", "unknown")].append(event)

    runtime_checks = {}
    for runtime_id, runtime_events in sorted(runtimes.items()):
        first_init = [
            e for e in runtime_events
            if e.get("event") == "runtime.bootstrap" and e.get("firstInitialization") == "true"
        ]
        contract_probe = [
            e for e in runtime_events
            if e.get("event") == "contract.probe.complete"
        ]
        local_dispatches = [
            e for e in runtime_events
            if e.get("event") == "contract.dispatch" and e.get("contextSource") == "local-probe"
        ]
        echo_dispatches = [
            e for e in local_dispatches if e.get("contract") == "probe.echo@1"
        ]
        unknown_dispatches = [
            e for e in local_dispatches if e.get("contract") == "probe.unknown@1"
        ]
        throw_dispatches = [
            e for e in local_dispatches if e.get("contract") == "probe.throw@1"
        ]

        contract_probe_ok = (
            len(contract_probe) == 1 and
            contract_probe[0].get("ok") == "true" and
            len(echo_dispatches) == 2 and
            all(e.get("result") == "ok" for e in echo_dispatches) and
            len(unknown_dispatches) == 1 and
            unknown_dispatches[0].get("result") == "unknown_contract" and
            len(throw_dispatches) == 1 and
            throw_dispatches[0].get("result") == "handler_error"
        )

        transport_probe = [
            e for e in runtime_events if e.get("event") == "transport.probe.complete"
        ]
        client_reply_checks: dict[str, bool] = {}
        for request_id, expected in TRANSPORT_EXPECTED.items():
            client_reply_checks[request_id] = any(
                e.get("event") == "transport.reply.client" and
                e.get("requestId") == request_id and
                e.get("accepted") == expected["accepted"] and
                e.get("code") == expected["code"] and
                e.get("result") == expected["result"]
                for e in runtime_events
            )
        transport_client_ok = (
            len(transport_probe) == 1 and
            transport_probe[0].get("ok") == "true" and
            all(client_reply_checks.values())
        )

        runtime_checks[runtime_id] = {
            "event_count": len(runtime_events),
            "first_initialization_count": len(first_init),
            "bootstrap_sources": sorted({
                e.get("source", "") for e in runtime_events if e.get("event") == "runtime.bootstrap"
            }),
            "contract_probe_complete_count": len(contract_probe),
            "contract_probe_ok": contract_probe_ok,
            "contract_echo_ok_count": sum(e.get("result") == "ok" for e in echo_dispatches),
            "contract_unknown_rejected_count": sum(
                e.get("result") == "unknown_contract" for e in unknown_dispatches
            ),
            "contract_throw_isolated_count": sum(
                e.get("result") == "handler_error" for e in throw_dispatches
            ),
            "transport_probe_complete_count": len(transport_probe),
            "transport_client_ok": transport_client_ok,
            "transport_client_reply_checks": client_reply_checks,
        }

    remote_joins = [
        e for e in events
        if e.get("event") == "lifecycle.player.join" and e.get("isHostPlayer") == "false"
    ]
    remote_left = [
        e for e in events
        if e.get("event") == "lifecycle.player.left" and e.get("isHostPlayer") == "false"
    ]
    errors = [
        e for e in events
        if e.get("event") in {"hook.error", "runtime.load.error", "runtime.module.error"}
    ]

    server_request_checks: dict[str, dict[str, bool]] = {}
    for request_id, expected in TRANSPORT_EXPECTED.items():
        envelope_ok = any(
            e.get("event") == "transport.envelope.server" and
            e.get("requestId") == request_id and
            e.get("contract") == expected["contract"] and
            e.get("senderIsHost") == "false" and
            e.get("result") == "received"
            for e in events
        )
        dispatch_ok = any(
            e.get("event") == "contract.dispatch" and
            e.get("contextSource") == "transport" and
            e.get("requestId") == request_id and
            e.get("contract") == expected["contract"] and
            e.get("result") == expected["dispatch"]
            for e in events
        )
        reply_ok = any(
            e.get("event") == "transport.reply.server" and
            e.get("requestId") == request_id and
            e.get("accepted") == expected["accepted"] and
            e.get("code") == expected["code"] and
            e.get("result") == "sent"
            for e in events
        )
        server_request_checks[request_id] = {
            "envelope": envelope_ok,
            "dispatch": dispatch_ok,
            "reply": reply_ok,
            "ok": envelope_ok and dispatch_ok and reply_ok,
        }

    role = state.get("role")
    transport_server_passed = all(
        item["ok"] for item in server_request_checks.values()
    ) if role == "host" else False
    transport_client_passed = (
        bool(runtimes) and all(item["transport_client_ok"] for item in runtime_checks.values())
    ) if role == "client" else False

    storage_error_events = [
        e for e in events
        if e.get("event") in {
            "storage.error", "storage.load.error", "storage.save.error",
            "storage.phase.error", "storage.load.foreign", "storage.load.unknown_schema"
        }
    ]
    namespace_checks = [e for e in events if e.get("event") == "storage.namespace.check"]
    storage_phase_events = [e for e in events if e.get("event") == "storage.probe.complete"]
    phase_names = [e.get("phase") for e in storage_phase_events if e.get("ok") == "true"]
    storage_server_checks = {
        "load_absent_once": counts.get("storage.load.absent", 0) == 1,
        "save_schema1_once": counts.get("storage.save.schema1", 0) == 1,
        "load_schema1_once": counts.get("storage.load.schema1", 0) == 1,
        "migration_1to2_once": counts.get("storage.migration.1to2", 0) == 1,
        "save_schema2_once": counts.get("storage.save.schema2", 0) == 1,
        "load_schema2_once": counts.get("storage.load.schema2", 0) == 1,
        "namespace_checks_three": len(namespace_checks) == 3 and all(e.get("success") == "true" for e in namespace_checks),
        "phase_sequence": phase_names == ["schema1_saved", "schema2_migrated", "schema2_stable"],
        "no_storage_errors": len(storage_error_events) == 0,
    }
    storage_server_passed = all(storage_server_checks.values()) if role == "host" else False
    storage_client_quiet = not any(
        e.get("event", "").startswith("storage.") and e.get("event") != "storage.service.loaded"
        for e in events
    ) if role == "client" else False
    storage_passed = storage_server_passed if role == "host" else storage_client_quiet

    carry_errors = [
        e for e in events
        if (e.get("event") == "hook.error" and str(e.get("hook", "")).startswith("carry."))
        or e.get("event") == "carry.resolve.error"
    ]
    carry_empty_count = counts.get("carry.resolve.empty", 0)
    carry_resolver_register_count = counts.get("carry.resolver.register", 0)
    carry_resolver_match_count = counts.get("carry.resolve.match", 0)
    carry_resolver_client_rpc_count = counts.get("carry.resolver.rpc.client", 0)
    carry_vanilla_server_count = counts.get("carry.vanilla.rpc.server", 0)
    carry_resolver_server_rpc_count = counts.get("carry.resolver.rpc.server", 0)
    carry_receiver_accept_count = counts.get("carry.receiver.accept", 0)
    carry_receiver_reject_count = counts.get("carry.receiver.reject", 0)
    receiver_counts = [
        int(e.get("receivedCount", "0"))
        for e in events
        if e.get("event") == "carry.receiver.accept" and str(e.get("receivedCount", "0")).isdigit()
    ]
    carry_receiver_received_max = max(receiver_counts, default=0)
    carry_client_passed = (
        carry_resolver_register_count >= 1 and
        carry_resolver_match_count >= 1 and
        carry_resolver_client_rpc_count >= 1 and
        len(carry_errors) == 0
    ) if role == "client" else False
    carry_server_passed = (
        carry_vanilla_server_count >= 1 and
        carry_resolver_server_rpc_count >= 1 and
        carry_receiver_accept_count >= 1 and
        carry_resolver_server_rpc_count == carry_receiver_accept_count and
        len(carry_errors) == 0
    ) if role == "host" else False
    carry_passed = carry_server_passed if role == "host" else carry_client_passed

    return {
        "schema": "smml-runtime-spine-lab-observation/1",
        "tool_version": VERSION,
        "run_id": state.get("run_id"),
        "role": role,
        "collected_at_utc": utc_now(),
        "event_count": len(events),
        "event_counts": dict(sorted(counts.items())),
        "runtime_count": len(runtimes),
        "runtimes": runtime_checks,
        "server_create_count": counts.get("lifecycle.server.create", 0),
        "server_unload_count": counts.get("lifecycle.server.unload", 0),
        "client_create_count": counts.get("lifecycle.client.create", 0),
        "remote_join_count": len(remote_joins),
        "remote_left_count": len(remote_left),
        "error_event_count": len(errors),
        "bootstrap_idempotent": bool(runtimes) and all(
            item["first_initialization_count"] == 1 for item in runtime_checks.values()
        ),
        "contract_registry_passed": bool(runtimes) and all(
            item["contract_probe_ok"] for item in runtime_checks.values()
        ),
        "transport_server_request_checks": server_request_checks,
        "transport_server_passed": transport_server_passed,
        "transport_client_passed": transport_client_passed,
        "transport_passed": transport_server_passed if role == "host" else transport_client_passed,
        "storage_server_checks": storage_server_checks,
        "storage_server_passed": storage_server_passed,
        "storage_client_quiet": storage_client_quiet,
        "storage_passed": storage_passed,
        "storage_probe_phases": phase_names,
        "storage_error_event_count": len(storage_error_events),
        "carry_empty_resolve_count": carry_empty_count,
        "carry_resolver_register_count": carry_resolver_register_count,
        "carry_resolver_match_count": carry_resolver_match_count,
        "carry_resolver_client_rpc_count": carry_resolver_client_rpc_count,
        "carry_vanilla_server_relay_count": carry_vanilla_server_count,
        "carry_resolver_server_rpc_count": carry_resolver_server_rpc_count,
        "carry_receiver_accept_count": carry_receiver_accept_count,
        "carry_receiver_reject_count": carry_receiver_reject_count,
        "carry_receiver_received_max": carry_receiver_received_max,
        "carry_error_event_count": len(carry_errors),
        "carry_client_passed": carry_client_passed,
        "carry_server_passed": carry_server_passed,
        "carry_passed": carry_passed,
    }

def is_diagnostic_line(line: str, event: dict | None) -> bool:
    if event is not None:
        return False
    return any(
        token in line
        for token in ("[Lua] ERROR:", "Failed to load file:", "[SMML-RUNTIME] FALLBACK")
    )


def collect(args: argparse.Namespace) -> None:
    state_dir = args.state_dir.expanduser().resolve()
    state = load_state(state_dir)
    root = Path(state["game_root"])
    logs_dir = root / "Logs"
    since = float(state.get("installed_epoch", 0))
    run_id = state.get("run_id")

    candidates: list[Path] = []
    if logs_dir.is_dir():
        for path in sorted(logs_dir.glob("game-*.log")):
            try:
                if path.stat().st_mtime >= since - 60:
                    candidates.append(path)
            except OSError:
                pass

    events: list[dict] = []
    diagnostics: list[dict] = []
    for path in candidates:
        text = path.read_text("utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            event = parse_event_line(line)
            if event is not None and event.get("runId") == run_id:
                event["source_log"] = path.name
                event["line"] = line_no
                events.append(event)
            if is_diagnostic_line(line, event):
                diagnostics.append({"source_log": path.name, "line": line_no, "text": line})

    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    with (output / "events.jsonl").open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")

    summary = summarize(events, state)
    summary["candidate_logs"] = [p.name for p in candidates]
    atomic_write(output / "summary.json", (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    diagnostics_text = "\n".join(
        f"{item['source_log']}:{item['line']}: {item['text']}" for item in diagnostics
    )
    atomic_write(output / "diagnostics.txt", (diagnostics_text + ("\n" if diagnostics_text else "")).encode("utf-8"))

    installation = {
        "schema": "smml-runtime-spine-lab-installation/1",
        "run_id": state.get("run_id"),
        "role": state.get("role"),
        "targets": {
            rel: {
                "before_sha256": rec.get("before_sha256"),
                "after_sha256": rec.get("after_sha256"),
            }
            for rel, rec in sorted(state.get("targets", {}).items())
        },
        "runtime_sha256": state.get("runtime", {}).get("sha256"),
        "contract_registry_sha256": state.get("contract_registry", {}).get("sha256"),
        "transport_service_sha256": state.get("transport_service", {}).get("sha256"),
        "storage_service_sha256": state.get("storage_service", {}).get("sha256"),
        "carry_adapter_sha256": state.get("carry_adapter", {}).get("sha256"),
        "config_sha256": state.get("config", {}).get("sha256"),
    }
    atomic_write(output / "installation.json", (json.dumps(installation, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print(f"[OK] Collected {len(events)} events")
    print(f"Summary: {output / 'summary.json'}")
    print(f"JSONL: {output / 'events.jsonl'}")


def uninstall(args: argparse.Namespace) -> None:
    running = game_running()
    if running:
        raise SystemExit("Scrap Mechanic appears to be running; stop it before uninstall:\n" + "\n".join(running))

    state_dir = args.state_dir.expanduser().resolve()
    state = load_state(state_dir)
    root = Path(state["game_root"])
    problems = verify_installed(state)
    if problems and not args.force:
        raise SystemExit(
            "Refusing restoration because installed files changed. Inspect first or pass --force if intentional:\n"
            + "\n".join(f"- {p}" for p in problems)
        )

    for rel, rec in state.get("targets", {}).items():
        backup = Path(rec["backup"])
        if not backup.is_file():
            raise SystemExit(f"Missing backup: {backup}")
        if sha256_file(backup) != rec.get("before_sha256"):
            raise SystemExit(f"Backup hash mismatch: {backup}")
        atomic_write(root / rel, backup.read_bytes())

    for key in runtime_file_keys(state):
        path = root / state[key]["path"]
        if path.exists():
            path.unlink()

    runtime_dir = (root / RUNTIME_DEST).parent
    try:
        runtime_dir.rmdir()
    except OSError:
        pass

    cache_rec = state.get("cache", {})
    cache = root / cache_rec.get("path", CACHE_PATH)
    backup_value = cache_rec.get("backup")
    if backup_value:
        backup = Path(backup_value)
        if not backup.is_file():
            raise SystemExit(f"Missing cache backup: {backup}")
        atomic_write(cache, backup.read_bytes())
    elif cache.exists():
        cache.unlink()

    restored = {
        rel: sha256_file(root / rel) == rec.get("before_sha256")
        for rel, rec in state.get("targets", {}).items()
    }
    state["uninstalled_at_utc"] = utc_now()
    state["restoration_verified"] = restored
    save_state(state_dir, state)

    if not all(restored.values()):
        raise SystemExit("Restoration hash verification failed")
    print("[OK] Runtime Spine lab removed; target files restored byte-for-byte")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SMML Runtime Spine laboratory installer and collector")
    parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install the Runtime Spine laboratory")
    install_p.add_argument("game_root", type=Path)
    install_p.add_argument("--role", choices=("host", "client"), required=True)
    install_p.add_argument("--run-id", required=True)
    install_p.set_defaults(func=install)

    status_p = sub.add_parser("status", help="Check installed files against recorded hashes")
    status_p.set_defaults(func=status)

    collect_p = sub.add_parser("collect", help="Extract SMML events from Scrap Mechanic logs")
    collect_p.add_argument("--output", type=Path, required=True)
    collect_p.set_defaults(func=collect)

    uninstall_p = sub.add_parser("uninstall", help="Restore target files and original cache state")
    uninstall_p.add_argument("--force", action="store_true")
    uninstall_p.set_defaults(func=uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
