from __future__ import annotations

import hashlib
import json
import os
import platform as platform_module
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .hashing import (
    CONTENT_TREE_ALGORITHM,
    canonical_tree_summary,
    content_tree_summary,
    subtree_fingerprint,
)
from .path_policy import (
    PathPolicyError,
    portable_collision_key,
    validate_logical_path,
    validate_unique_paths,
)

INSPECTION_PLAN_SCHEMA = "smml.game-target-inspection-plan/1"
GAME_TARGET_SCHEMA = "smml.game-target/1"
CANONICAL_POLICY_ID = "smml.canonical-game-policy/1"


@dataclass(frozen=True)
class InspectorError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True)
class SteamManifest:
    app_id: int
    build_id: str
    branch: str
    install_dir: str


@dataclass(frozen=True)
class EntryObservation:
    kind: str
    signature: tuple[int, int, int, int, int, int]
    size: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class InventorySnapshot:
    root_signature: tuple[int, int, int, int, int, int]
    entries: dict[str, EntryObservation]
    records: tuple[dict[str, Any], ...]


def _raise(code: str, detail: str) -> None:
    raise InspectorError(code, detail)


def _stat_signature(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
        int(getattr(value, "st_ctime_ns", int(value.st_ctime * 1_000_000_000))),
    )


def _is_reparse_point(value: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attrs = int(getattr(value, "st_file_attributes", 0))
    return bool(attrs & flag)


def _classify_stat(value: os.stat_result) -> str:
    if _is_reparse_point(value):
        return "reparse-point"
    if stat.S_ISLNK(value.st_mode):
        return "symlink"
    if stat.S_ISREG(value.st_mode):
        return "regular-file"
    if stat.S_ISDIR(value.st_mode):
        return "directory"
    return "other"


def _validate_root(root: Path) -> tuple[int, int, int, int, int, int]:
    try:
        value = os.lstat(root)
    except OSError as exc:
        _raise("ROOT_UNTRUSTED", f"cannot inspect {root}: {exc}")
    kind = _classify_stat(value)
    if kind == "symlink":
        _raise("SYMLINK_FORBIDDEN", f"game root is a symlink: {root}")
    if kind == "reparse-point":
        _raise("REPARSE_POINT_FORBIDDEN", f"game root is a reparse point: {root}")
    if kind != "directory":
        _raise("ROOT_UNTRUSTED", f"game root is {kind}, expected directory: {root}")
    return _stat_signature(value)


def _hash_regular_file_stable(path: Path, observed: os.stat_result) -> tuple[int, str, tuple[int, int, int, int, int, int]]:
    expected_signature = _stat_signature(observed)
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    try:
        fd = os.open(path, flags)
    except OSError as exc:
        _raise("INSPECTION_FAILED", f"cannot open {path}: {exc}")

    try:
        before = os.fstat(fd)
        if _classify_stat(before) != "regular-file":
            _raise("TYPE_MISMATCH", f"{path} changed from regular-file")
        before_signature = _stat_signature(before)
        if before_signature != expected_signature:
            _raise("GTI_FILESYSTEM_CHANGED", f"{path} changed before hashing")

        digest = hashlib.sha256()
        read_bytes = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            read_bytes += len(chunk)

        after = os.fstat(fd)
        after_signature = _stat_signature(after)
        if after_signature != before_signature or read_bytes != int(before.st_size):
            _raise("GTI_FILESYSTEM_CHANGED", f"{path} changed while hashing")
    finally:
        os.close(fd)

    try:
        path_after = os.lstat(path)
    except OSError as exc:
        _raise("GTI_FILESYSTEM_CHANGED", f"{path} disappeared after hashing: {exc}")
    if _classify_stat(path_after) != "regular-file" or _stat_signature(path_after) != after_signature:
        _raise("GTI_FILESYSTEM_CHANGED", f"{path} changed after hashing")

    return read_bytes, digest.hexdigest(), after_signature


def _scan_tree(root: Path, *, hash_files: bool) -> InventorySnapshot:
    root_signature = _validate_root(root)
    entries: dict[str, EntryObservation] = {}
    records: list[dict[str, Any]] = []
    collision_keys: dict[str, str] = {}

    def visit(directory: Path, prefix: str) -> None:
        try:
            with os.scandir(directory) as iterator:
                children = sorted(list(iterator), key=lambda e: os.fsencode(e.name))
        except OSError as exc:
            _raise("INSPECTION_FAILED", f"cannot enumerate {directory}: {exc}")

        for entry in children:
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                validate_logical_path(rel)
                collision_key = portable_collision_key(rel)
            except PathPolicyError as exc:
                _raise(exc.code, f"{rel!r}: {exc.detail}")

            previous = collision_keys.get(collision_key)
            if previous is not None and previous != rel:
                _raise("CASE_COLLISION", f"{previous!r} vs {rel!r}")
            collision_keys[collision_key] = rel

            try:
                observed = entry.stat(follow_symlinks=False)
            except OSError as exc:
                _raise("INSPECTION_FAILED", f"cannot lstat {rel}: {exc}")
            kind = _classify_stat(observed)

            if kind == "symlink":
                _raise("SYMLINK_FORBIDDEN", rel)
            if kind == "reparse-point":
                _raise("REPARSE_POINT_FORBIDDEN", rel)
            if kind == "other":
                _raise("TYPE_MISMATCH", f"unsupported filesystem object: {rel}")

            if kind == "regular-file":
                if hash_files:
                    size, digest, signature = _hash_regular_file_stable(Path(entry.path), observed)
                    entries[rel] = EntryObservation(kind, signature, size, digest)
                    records.append({"path": rel, "size": size, "sha256": digest})
                else:
                    entries[rel] = EntryObservation(kind, _stat_signature(observed), int(observed.st_size), None)
            else:
                entries[rel] = EntryObservation(kind, _stat_signature(observed), None, None)
                visit(Path(entry.path), rel)

    visit(root, "")
    return InventorySnapshot(root_signature, entries, tuple(records))


def _ensure_snapshot_stable(before: InventorySnapshot, after: InventorySnapshot) -> None:
    if before.root_signature != after.root_signature:
        _raise("GTI_FILESYSTEM_CHANGED", "game root changed during inspection")
    if set(before.entries) != set(after.entries):
        added = sorted(set(after.entries) - set(before.entries))[:3]
        removed = sorted(set(before.entries) - set(after.entries))[:3]
        _raise("GTI_FILESYSTEM_CHANGED", f"inventory changed; added={added!r}, removed={removed!r}")
    for path, first in before.entries.items():
        second = after.entries[path]
        if first.kind != second.kind or first.signature != second.signature:
            _raise("GTI_FILESYSTEM_CHANGED", f"filesystem object changed: {path}")


def _index_portable(entries: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in entries:
        result[portable_collision_key(path)] = path
    return result


def _require_entry(
    path: str,
    *,
    expected_kind: str,
    entries: dict[str, EntryObservation],
    portable_index: dict[str, str],
    missing_code: str,
) -> EntryObservation:
    validate_logical_path(path)
    item = entries.get(path)
    if item is None:
        observed_spelling = portable_index.get(portable_collision_key(path))
        if observed_spelling is not None:
            _raise("CASE_MISMATCH", f"requested {path!r}, observed {observed_spelling!r}")
        _raise(missing_code, path)
    if item.kind != expected_kind:
        _raise("TYPE_MISMATCH", f"{path!r} is {item.kind}, expected {expected_kind}")
    return item


def _canonical_path_sort(paths: Iterable[str]) -> list[str]:
    return sorted(paths, key=lambda value: (portable_collision_key(value), value.encode("utf-8")))


def validate_inspection_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema") != INSPECTION_PLAN_SCHEMA:
        _raise("GTI_PLAN_INVALID", f"unexpected schema {plan.get('schema')!r}")
    app_id = plan.get("steamAppId")
    if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
        _raise("GTI_PLAN_INVALID", "steamAppId must be a positive integer")
    if plan.get("canonicalPolicy") != CANONICAL_POLICY_ID:
        _raise("GTI_PLAN_INVALID", "unsupported canonicalPolicy")
    builds = plan.get("builds")
    if not isinstance(builds, list) or not builds:
        _raise("GTI_PLAN_INVALID", "builds must be a non-empty array")

    seen_builds: set[tuple[str, str]] = set()
    for build in builds:
        if not isinstance(build, dict):
            _raise("GTI_PLAN_INVALID", "build record must be an object")
        key = (str(build.get("steamBuildId", "")), str(build.get("steamBranch", "")))
        if not key[0] or not key[1]:
            _raise("GTI_PLAN_INVALID", "build requires steamBuildId and steamBranch")
        if key in seen_builds:
            _raise("GTI_PLAN_INVALID", f"duplicate build {key!r}")
        seen_builds.add(key)
        roots = build.get("rootFingerprints")
        targets = build.get("targetFingerprints")
        if not isinstance(roots, list) or not roots or not isinstance(targets, list) or not targets:
            _raise("GTI_PLAN_INVALID", f"build {key!r} requires non-empty roots and targets")
        try:
            validate_unique_paths(roots)
            validate_unique_paths(targets)
        except PathPolicyError as exc:
            _raise("GTI_PLAN_INVALID", str(exc))


def _tokenize_vdf(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            newline = text.find("\n", i + 2)
            i = length if newline < 0 else newline + 1
            continue
        if ch in "{}":
            tokens.append(ch)
            i += 1
            continue
        if ch != '"':
            _raise("GTI_APPMANIFEST_INVALID", f"unexpected VDF character at offset {i}")
        i += 1
        value: list[str] = []
        while i < length:
            ch = text[i]
            if ch == '"':
                i += 1
                break
            if ch == "\\":
                i += 1
                if i >= length:
                    _raise("GTI_APPMANIFEST_INVALID", "unterminated VDF escape")
                escaped = text[i]
                value.append({"n": "\n", "r": "\r", "t": "\t"}.get(escaped, escaped))
                i += 1
                continue
            value.append(ch)
            i += 1
        else:
            _raise("GTI_APPMANIFEST_INVALID", "unterminated VDF string")
        tokens.append("".join(value))
    return tokens


def parse_vdf(text: str) -> dict[str, Any]:
    tokens = _tokenize_vdf(text)
    index = 0

    def parse_object(expect_close: bool) -> dict[str, Any]:
        nonlocal index
        result: dict[str, Any] = {}
        while index < len(tokens):
            if tokens[index] == "}":
                if not expect_close:
                    _raise("GTI_APPMANIFEST_INVALID", "unexpected closing brace")
                index += 1
                return result
            key = tokens[index]
            if key == "{":
                _raise("GTI_APPMANIFEST_INVALID", "unexpected opening brace")
            index += 1
            if index >= len(tokens):
                _raise("GTI_APPMANIFEST_INVALID", f"missing value for key {key!r}")
            token = tokens[index]
            if token == "{":
                index += 1
                value: Any = parse_object(True)
            elif token == "}":
                _raise("GTI_APPMANIFEST_INVALID", f"missing value for key {key!r}")
            else:
                value = token
                index += 1
            if key in result:
                _raise("GTI_APPMANIFEST_INVALID", f"duplicate key {key!r}")
            result[key] = value
        if expect_close:
            _raise("GTI_APPMANIFEST_INVALID", "missing closing brace")
        return result

    result = parse_object(False)
    if index != len(tokens):
        _raise("GTI_APPMANIFEST_INVALID", "trailing VDF tokens")
    return result


def _get_ci(mapping: dict[str, Any], key: str) -> Any | None:
    key_folded = key.casefold()
    matches = [value for name, value in mapping.items() if name.casefold() == key_folded]
    if len(matches) > 1:
        _raise("GTI_APPMANIFEST_INVALID", f"ambiguous key casing for {key!r}")
    return matches[0] if matches else None


def read_steam_manifest(path: Path) -> SteamManifest:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        _raise("GTI_APPMANIFEST_NOT_FOUND", f"{path}: {exc}")
    document = parse_vdf(raw)
    app_state = _get_ci(document, "AppState")
    if not isinstance(app_state, dict):
        _raise("GTI_APPMANIFEST_INVALID", "AppState object missing")

    appid_raw = _get_ci(app_state, "appid")
    build_id = _get_ci(app_state, "buildid")
    install_dir = _get_ci(app_state, "installdir")
    if not isinstance(appid_raw, str) or not appid_raw.isdecimal():
        _raise("GTI_APPMANIFEST_INVALID", "appid missing or invalid")
    if not isinstance(build_id, str) or not build_id.isdecimal():
        _raise("GTI_APPMANIFEST_INVALID", "buildid missing or invalid")
    if not isinstance(install_dir, str) or not install_dir:
        _raise("GTI_APPMANIFEST_INVALID", "installdir missing or invalid")

    beta_key: Any | None = None
    for section_name in ("UserConfig", "MountedConfig"):
        section = _get_ci(app_state, section_name)
        if isinstance(section, dict):
            candidate = _get_ci(section, "betakey")
            if isinstance(candidate, str) and candidate:
                beta_key = candidate
                break
    branch = "public" if beta_key in (None, "", "public") else str(beta_key)
    return SteamManifest(int(appid_raw), build_id, branch, install_dir)


def _detect_host_os() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    _raise("GTI_UNSUPPORTED_HOST", sys.platform)


def _normalize_arch(value: str) -> str:
    folded = value.casefold()
    aliases = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
    }
    return aliases.get(folded, value)


def _select_known_build(plan: dict[str, Any], manifest: SteamManifest) -> dict[str, Any]:
    matches = [
        build
        for build in plan["builds"]
        if build["steamBuildId"] == manifest.build_id and build["steamBranch"] == manifest.branch
    ]
    if not matches:
        same_build = [build for build in plan["builds"] if build["steamBuildId"] == manifest.build_id]
        if same_build:
            _raise(
                "GTI_BRANCH_MISMATCH",
                f"Steam build {manifest.build_id} observed on branch {manifest.branch!r}",
            )
        _raise("GTI_UNKNOWN_STEAM_BUILD", manifest.build_id)
    if len(matches) != 1:
        _raise("GTI_PLAN_INVALID", f"ambiguous build mapping for {manifest.build_id}/{manifest.branch}")
    return matches[0]


def discover_appmanifest(game_root: Path, steam_app_id: int) -> Path:
    return game_root.parent.parent / f"appmanifest_{steam_app_id}.acf"


def inspect_game_target(
    game_root: Path | str,
    *,
    plan: dict[str, Any],
    canonical_policy: dict[str, Any],
    appmanifest_path: Path | str | None = None,
    compatibility_layer: str | None = None,
    compatibility_version: str | None = None,
    host_os: str | None = None,
    host_arch: str | None = None,
) -> dict[str, Any]:
    validate_inspection_plan(plan)
    if canonical_policy.get("schema") != CANONICAL_POLICY_ID:
        _raise("GTI_PLAN_INVALID", f"unexpected canonical policy {canonical_policy.get('schema')!r}")
    root = Path(game_root).expanduser().absolute()
    _validate_root(root)

    manifest_path = Path(appmanifest_path).expanduser().absolute() if appmanifest_path else discover_appmanifest(root, int(plan["steamAppId"]))
    steam = read_steam_manifest(manifest_path)
    if steam.app_id != plan["steamAppId"]:
        _raise("GTI_APPID_MISMATCH", f"expected {plan['steamAppId']}, observed {steam.app_id}")
    if steam.install_dir != root.name:
        _raise("GTI_INSTALLDIR_MISMATCH", f"manifest {steam.install_dir!r}, root {root.name!r}")

    build = _select_known_build(plan, steam)
    observed_host_os = host_os or _detect_host_os()
    if observed_host_os not in {"linux", "windows", "macos"}:
        _raise("GTI_UNSUPPORTED_HOST", observed_host_os)
    observed_host_arch = _normalize_arch(host_arch or platform_module.machine() or "unknown")
    game_os = build["gameOs"]

    layer_kind = compatibility_layer
    if layer_kind is None:
        layer_kind = "none" if observed_host_os == game_os else None
    if observed_host_os != game_os and not layer_kind:
        _raise(
            "GTI_COMPATIBILITY_LAYER_REQUIRED",
            f"hostOs={observed_host_os!r}, gameOs={game_os!r}",
        )
    if layer_kind not in {"none", "proton", "wine", "other"}:
        _raise("GTI_COMPATIBILITY_LAYER_INVALID", repr(layer_kind))
    if observed_host_os != game_os and layer_kind == "none":
        _raise("GTI_COMPATIBILITY_LAYER_REQUIRED", "cross-OS execution cannot use layer 'none'")

    first = _scan_tree(root, hash_files=True)
    second = _scan_tree(root, hash_files=False)
    _ensure_snapshot_stable(first, second)

    records = list(first.records)
    exact_summary = content_tree_summary(records)
    canonical_summary = canonical_tree_summary(records, canonical_policy)
    portable_index = _index_portable(first.entries.keys())

    root_fingerprints: list[dict[str, Any]] = []
    for path in _canonical_path_sort(build["rootFingerprints"]):
        _require_entry(
            path,
            expected_kind="directory",
            entries=first.entries,
            portable_index=portable_index,
            missing_code="GTI_REQUIRED_ROOT_MISSING",
        )
        root_fingerprints.append(
            {
                "path": path,
                "algorithm": CONTENT_TREE_ALGORITHM,
                "sha256": subtree_fingerprint(records, path),
            }
        )

    records_by_path = {record["path"]: record for record in records}
    target_fingerprints: list[dict[str, Any]] = []
    for path in _canonical_path_sort(build["targetFingerprints"]):
        _require_entry(
            path,
            expected_kind="regular-file",
            entries=first.entries,
            portable_index=portable_index,
            missing_code="GTI_REQUIRED_TARGET_MISSING",
        )
        record = records_by_path[path]
        target_fingerprints.append(
            {"path": path, "algorithm": "sha256", "sha256": record["sha256"]}
        )

    platform: dict[str, Any] = {
        "hostOs": observed_host_os,
        "gameOs": game_os,
        "hostArch": observed_host_arch,
        "compatibilityLayer": {"kind": layer_kind},
    }
    if build.get("gameArch"):
        platform["gameArch"] = build["gameArch"]
    if compatibility_version:
        platform["compatibilityLayer"]["version"] = compatibility_version

    return {
        "schema": GAME_TARGET_SCHEMA,
        "steamAppId": steam.app_id,
        "gameVersion": build["gameVersion"],
        "engineBuild": build["engineBuild"],
        "steamBuildId": steam.build_id,
        "steamBranch": steam.branch,
        "platform": platform,
        "fingerprints": {
            "algorithm": CONTENT_TREE_ALGORITHM,
            "canonicalPolicy": canonical_policy["schema"],
            "installationExactFingerprint": {
                "sha256": exact_summary["sha256"],
                "fileCount": exact_summary["fileCount"],
                "totalFileBytes": exact_summary["totalFileBytes"],
            },
            "canonicalGameFingerprint": {
                "sha256": canonical_summary["sha256"],
                "fileCount": canonical_summary["fileCount"],
                "totalFileBytes": canonical_summary["totalFileBytes"],
            },
            "rootFingerprints": root_fingerprints,
            "targetFingerprints": target_fingerprints,
        },
    }


def load_json(path: Path | str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _raise("GTI_JSON_INVALID", f"{path}: {exc}")
    if not isinstance(data, dict):
        _raise("GTI_JSON_INVALID", f"{path}: top-level JSON value must be an object")
    return data
