from __future__ import annotations

import copy
import os
import stat
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .path_policy import validate_logical_path
from .transaction_journal import classify_current_state, validate_transaction_journal_semantics
from .transaction_runtime import compare_game_target_binding, observe_operation_path, path_is_within, validate_game_root
from .transaction_store import FaultInjector, JournalStore, StagingStore, TransactionStoreError, validate_state_root


@dataclass
class TransactionEngineError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _fail(code: str, detail: str) -> None:
    raise TransactionEngineError(code, detail)


def _inject(injector: FaultInjector | None, point: str) -> None:
    if injector is not None:
        injector(point)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp_for_rewrite(current: dict[str, Any], supplied: str | None) -> str:
    if supplied is not None:
        return supplied
    now = _utc_now()
    return max(now, current["updatedAt"])


def _is_reparse(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attrs & flag)


def _same_snapshot(a: os.stat_result, b: os.stat_result) -> bool:
    return (
        a.st_dev,
        a.st_ino,
        a.st_size,
        getattr(a, "st_mtime_ns", int(a.st_mtime * 1_000_000_000)),
    ) == (
        b.st_dev,
        b.st_ino,
        b.st_size,
        getattr(b, "st_mtime_ns", int(b.st_mtime * 1_000_000_000)),
    )


def _segment_key(value: str) -> str:
    return unicodedata.normalize("NFC", value.casefold())


def _find_case_mismatch(names: list[str], wanted: str) -> str | None:
    wanted_key = _segment_key(wanted)
    for name in names:
        if name != wanted and _segment_key(name) == wanted_key:
            return name
    return None


@dataclass
class _OpenedLogicalFile:
    fd: int
    parent_fd: int | None
    leaf: str
    absolute_path: Path | None
    before: os.stat_result


@contextmanager
def _open_logical_regular_file(root: Path, logical_path: str) -> Iterator[_OpenedLogicalFile]:
    validate_logical_path(logical_path)
    root = validate_game_root(root)
    parts = logical_path.split("/")

    if os.name == "posix" and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd:
        flags_dir = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags_file = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        root_fd = os.open(root, flags_dir)
        opened_dirs = [root_fd]
        fd = root_fd
        file_fd = -1
        try:
            for index, part in enumerate(parts[:-1]):
                component = "/".join(parts[: index + 1])
                names = os.listdir(fd)
                if part not in names:
                    mismatch = _find_case_mismatch(names, part)
                    if mismatch is not None:
                        _fail("TXE_SOURCE_CASE_MISMATCH", f"{component!r} exists as {mismatch!r}")
                    _fail("TXE_SOURCE_MISSING", component)
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
                    _fail("TXE_SOURCE_UNSAFE", f"link/reparse ancestor: {component}")
                if not stat.S_ISDIR(st.st_mode):
                    _fail("TXE_SOURCE_UNSAFE", f"ancestor is not a directory: {component}")
                next_fd = os.open(part, flags_dir, dir_fd=fd)
                opened_dirs.append(next_fd)
                fd = next_fd

            leaf = parts[-1]
            names = os.listdir(fd)
            if leaf not in names:
                mismatch = _find_case_mismatch(names, leaf)
                if mismatch is not None:
                    _fail("TXE_SOURCE_CASE_MISMATCH", f"{logical_path!r} exists as {mismatch!r}")
                _fail("TXE_SOURCE_MISSING", logical_path)
            st = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
                _fail("TXE_SOURCE_UNSAFE", f"link/reparse source: {logical_path}")
            if not stat.S_ISREG(st.st_mode):
                _fail("TXE_SOURCE_NOT_FILE", logical_path)
            file_fd = os.open(leaf, flags_file, dir_fd=fd)
            before = os.fstat(file_fd)
            opened = _OpenedLogicalFile(file_fd, fd, leaf, None, before)
            yield opened
            after = os.fstat(file_fd)
            named_after = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if not _same_snapshot(before, after) or not _same_snapshot(before, named_after):
                _fail("TXE_SOURCE_CHANGED", logical_path)
        finally:
            if file_fd >= 0:
                try:
                    os.close(file_fd)
                except OSError:
                    pass
            for dir_fd in reversed(opened_dirs):
                try:
                    os.close(dir_fd)
                except OSError:
                    pass
        return

    current = root
    for index, part in enumerate(parts[:-1]):
        component = "/".join(parts[: index + 1])
        names = [entry.name for entry in os.scandir(current)]
        if part not in names:
            mismatch = _find_case_mismatch(names, part)
            if mismatch is not None:
                _fail("TXE_SOURCE_CASE_MISMATCH", f"{component!r} exists as {mismatch!r}")
            _fail("TXE_SOURCE_MISSING", component)
        current = current / part
        st = os.lstat(current)
        if stat.S_ISLNK(st.st_mode) or _is_reparse(st) or not stat.S_ISDIR(st.st_mode):
            _fail("TXE_SOURCE_UNSAFE", component)

    path = current / parts[-1]
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
        _fail("TXE_SOURCE_UNSAFE", logical_path)
    if not stat.S_ISREG(st.st_mode):
        _fail("TXE_SOURCE_NOT_FILE", logical_path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    file_fd = os.open(path, flags)
    try:
        before = os.fstat(file_fd)
        opened = _OpenedLogicalFile(file_fd, None, parts[-1], path, before)
        yield opened
        after = os.fstat(file_fd)
        named_after = os.lstat(path)
        if not _same_snapshot(before, after) or not _same_snapshot(before, named_after):
            _fail("TXE_SOURCE_CHANGED", logical_path)
    finally:
        os.close(file_fd)


def _static_plan_projection(journal: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": journal["schema"],
        "transactionId": journal["transactionId"],
        "createdAt": journal["createdAt"],
        "gameTarget": journal["gameTarget"],
        "operations": [
            {key: value for key, value in op.items() if key != "status"}
            for op in journal["operations"]
        ],
    }


def _build_prepared_journal(current: dict[str, Any], *, prepared_at: str | None) -> dict[str, Any]:
    prepared = copy.deepcopy(current)
    prepared["journalRevision"] = current["journalRevision"] + 1
    prepared["phase"] = "PREPARED"
    prepared["updatedAt"] = _timestamp_for_rewrite(current, prepared_at)
    prepared["phaseHistory"].append({
        "revision": prepared["journalRevision"],
        "at": prepared["updatedAt"],
        "phase": "PREPARED",
    })
    for op in prepared["operations"]:
        op["status"] = "PENDING"
    validate_transaction_journal_semantics(prepared)
    return prepared


def _state_with_size(state: dict[str, Any], size: int | None = None) -> dict[str, Any]:
    if not state["exists"]:
        return {"exists": False}
    if size is None:
        raise AssertionError("present staged state requires size")
    return {"exists": True, "sha256": state["sha256"], "size": size}


def _build_staging_manifest(
    prepared: dict[str, Any],
    staged_sizes: dict[tuple[str, str], int],
) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    blobs: dict[str, int] = {}
    for op in prepared["operations"]:
        binding: dict[str, Any] = {
            "operationId": op["operationId"],
            "sequence": op["sequence"],
            "path": op["path"],
        }
        for role in ("before", "after"):
            state = op[role]
            if state["exists"]:
                size = staged_sizes[(op["operationId"], role)]
                binding[role] = _state_with_size(state, size)
                existing = blobs.get(state["sha256"])
                if existing is not None and existing != size:
                    _fail("TXE_BLOB_SIZE_CONFLICT", state["sha256"])
                blobs[state["sha256"]] = size
            else:
                binding[role] = {"exists": False}
        operations.append(binding)

    return {
        "schema": "smml.transaction-staging-manifest/1",
        "transactionId": prepared["transactionId"],
        "journalRevision": prepared["journalRevision"],
        "contentAlgorithm": "sha256",
        "layout": "sha256-prefix-v1",
        "operations": operations,
        "blobs": [
            {"sha256": digest, "size": blobs[digest]}
            for digest in sorted(blobs)
        ],
    }


def _stage_expected_file(
    store: StagingStore,
    root: Path,
    logical_path: str,
    expected_sha256: str,
    *,
    fault_injector: FaultInjector | None,
) -> dict[str, Any]:
    with _open_logical_regular_file(root, logical_path) as opened:
        record = store.put_fd(opened.fd, expected_sha256, fault_injector=fault_injector)
    return record


def prepare_transaction(
    planned_journal: dict[str, Any],
    *,
    game_root: str | os.PathLike[str],
    current_game_target: dict[str, Any],
    state_root: str | os.PathLike[str],
    after_root: str | os.PathLike[str] | None = None,
    prepared_at: str | None = None,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    try:
        validate_transaction_journal_semantics(planned_journal)
    except Exception as exc:
        _fail("TXE_INVALID_PLAN", str(exc))
    if planned_journal["phase"] != "PLANNED":
        _fail("TXE_PLAN_NOT_PLANNED", planned_journal["phase"])

    live_root = validate_game_root(game_root)
    persistent_root = validate_state_root(state_root)
    if path_is_within(live_root, persistent_root):
        _fail("TXE_STATE_ROOT_IN_GAME", str(persistent_root))

    needs_after = any(op["after"]["exists"] for op in planned_journal["operations"])
    desired_root: Path | None = None
    if after_root is not None:
        desired_root = validate_game_root(after_root)
        if path_is_within(live_root, desired_root):
            _fail("TXE_AFTER_ROOT_IN_GAME", str(desired_root))
    elif needs_after:
        _fail("TXE_AFTER_ROOT_REQUIRED", "create/replace operation requires afterRoot")

    binding = compare_game_target_binding(planned_journal["gameTarget"], current_game_target)
    if binding["status"] != "MATCH":
        _fail("TXE_TARGET_MISMATCH", repr(binding["mismatches"]))

    journal_store = JournalStore(persistent_root, planned_journal["transactionId"])

    if journal_store.exists():
        persisted = journal_store.load()
        if _static_plan_projection(persisted) != _static_plan_projection(planned_journal):
            _fail("TXE_PERSISTED_PLAN_MISMATCH", "persistent journal does not match requested plan")
        if persisted["phase"] == "PREPARED":
            staging_store = StagingStore(persistent_root, planned_journal["transactionId"])
            manifest = staging_store.load_manifest(journal=persisted)
            return {
                "transactionId": persisted["transactionId"],
                "phase": "PREPARED",
                "journalRevision": persisted["journalRevision"],
                "idempotent": True,
                "blobCount": len(manifest["blobs"]),
                "totalStagedBytes": sum(item["size"] for item in manifest["blobs"]),
            }
        if persisted["phase"] != "PLANNED":
            _fail("TXE_PERSISTED_PHASE", persisted["phase"])
        current = persisted
    else:
        current = journal_store.initialize(planned_journal, fault_injector=fault_injector)
        _inject(fault_injector, "engine.after_planned_journal")

    # Staging layout is created only after a durable PLANNED journal exists.
    staging_store = StagingStore(persistent_root, planned_journal["transactionId"])

    observations: dict[str, dict[str, Any]] = {}
    for op in current["operations"]:
        observed = observe_operation_path(live_root, op)
        observations[op["operationId"]] = observed
        if observed["pathSafety"]["status"] != "SAFE":
            _fail("TXE_PATH_POLICY_BLOCKED", f"{op['operationId']}: {observed['pathSafety']['issues']}")
        classification = classify_current_state(op, observed)
        if classification != "BEFORE":
            _fail("TXE_PRECONDITION_FAILED", f"{op['operationId']} observed {classification}, expected BEFORE")

    prepared = _build_prepared_journal(current, prepared_at=prepared_at)
    staged_sizes: dict[tuple[str, str], int] = {}

    for op in current["operations"]:
        if op["before"]["exists"]:
            record = _stage_expected_file(
                staging_store,
                live_root,
                op["path"],
                op["before"]["sha256"],
                fault_injector=fault_injector,
            )
            staged_sizes[(op["operationId"], "before")] = record["size"]
        if op["after"]["exists"]:
            if desired_root is None:
                raise AssertionError("afterRoot already checked")
            record = _stage_expected_file(
                staging_store,
                desired_root,
                op["path"],
                op["after"]["sha256"],
                fault_injector=fault_injector,
            )
            staged_sizes[(op["operationId"], "after")] = record["size"]

    manifest = _build_staging_manifest(prepared, staged_sizes)
    staging_store.write_manifest(
        manifest,
        journal=prepared,
        fault_injector=fault_injector,
    )
    _inject(fault_injector, "engine.after_staging_manifest")
    _inject(fault_injector, "engine.before_prepared_journal")
    final_journal = journal_store.rewrite(prepared, fault_injector=fault_injector)
    _inject(fault_injector, "engine.after_prepared_journal")

    final_manifest = staging_store.load_manifest(journal=final_journal)
    return {
        "transactionId": final_journal["transactionId"],
        "phase": final_journal["phase"],
        "journalRevision": final_journal["journalRevision"],
        "idempotent": False,
        "blobCount": len(final_manifest["blobs"]),
        "totalStagedBytes": sum(item["size"] for item in final_manifest["blobs"]),
    }


__all__ = [
    "TransactionEngineError",
    "prepare_transaction",
]
