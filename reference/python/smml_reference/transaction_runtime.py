from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .game_target_identity import validate_semantics as validate_game_target_semantics
from .path_policy import portable_collision_key, validate_logical_path
from .transaction_journal import (
    classify_commit_recovery,
    classify_current_state,
    classify_rollback_safety,
    validate_transaction_journal_semantics,
)


@dataclass(frozen=True)
class TransactionRuntimeError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _fail(code: str, detail: str) -> None:
    raise TransactionRuntimeError(code, detail)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_reparse(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attrs & flag)


def _stat_kind(st: os.stat_result) -> str:
    if _is_reparse(st):
        return "reparsePoint"
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def _segment_key(value: str) -> str:
    return unicodedata.normalize("NFC", value.casefold())


def _find_case_mismatch(names: list[str], wanted: str) -> str | None:
    key = _segment_key(wanted)
    for name in names:
        if name != wanted and _segment_key(name) == key:
            return name
    return None


def _same_file_snapshot(a: os.stat_result, b: os.stat_result) -> bool:
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


def _hash_fd(fd: int) -> tuple[str, os.stat_result, os.stat_result]:
    before = os.fstat(fd)
    h = hashlib.sha256()
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    after = os.fstat(fd)
    if not _same_file_snapshot(before, after):
        _fail("TXR_UNSTABLE_OBSERVATION", "file changed while being hashed")
    return h.hexdigest(), before, after


def _base_observation(kind: str, *, stable: bool = True) -> dict[str, Any]:
    return {
        "kind": kind,
        "stable": stable,
        "pathSafety": {"status": "SAFE", "issues": []},
    }


def _blocked_observation(kind: str, code: str, component: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "stable": True,
        "blockedAt": component,
        "pathSafety": {
            "status": "BLOCKED",
            "issues": [{"code": code, "component": component}],
        },
    }


def _observe_posix(game_root: Path, logical_path: str, operation_kind: str) -> dict[str, Any]:
    flags_dir = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags_file = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(game_root, flags_dir)
    except OSError as exc:
        _fail("TXR_ROOT_UNSAFE", f"cannot open game root without following links: {exc}")

    parts = logical_path.split("/")
    opened: list[int] = [root_fd]
    fd = root_fd
    prefix: list[str] = []
    try:
        for part in parts[:-1]:
            prefix.append(part)
            component = "/".join(prefix)
            try:
                names = os.listdir(fd)
            except OSError as exc:
                _fail("TXR_OBSERVATION_FAILED", f"cannot list ancestor {component!r}: {exc}")
            if part not in names:
                mismatch = _find_case_mismatch(names, part)
                if mismatch is not None:
                    return _blocked_observation("other", "CASE_MISMATCH", component)
                return _blocked_observation("missing", "ANCESTOR_MISSING", component)
            try:
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except OSError as exc:
                _fail("TXR_OBSERVATION_FAILED", f"cannot lstat ancestor {component!r}: {exc}")
            kind = _stat_kind(st)
            if kind == "symlink":
                return _blocked_observation(kind, "SYMLINK_FORBIDDEN", component)
            if kind == "reparsePoint":
                return _blocked_observation(kind, "REPARSE_POINT_FORBIDDEN", component)
            if kind != "directory":
                return _blocked_observation(kind, "ANCESTOR_NOT_DIRECTORY", component)
            try:
                next_fd = os.open(part, flags_dir, dir_fd=fd)
            except OSError as exc:
                _fail("TXR_OBSERVATION_FAILED", f"cannot open ancestor {component!r}: {exc}")
            opened.append(next_fd)
            fd = next_fd

        leaf = parts[-1]
        try:
            names = os.listdir(fd)
        except OSError as exc:
            _fail("TXR_OBSERVATION_FAILED", f"cannot list leaf parent for {logical_path!r}: {exc}")
        if leaf not in names:
            mismatch = _find_case_mismatch(names, leaf)
            if mismatch is not None:
                return _blocked_observation("other", "CASE_MISMATCH", logical_path)
            return _base_observation("missing")

        try:
            st = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as exc:
            _fail("TXR_OBSERVATION_FAILED", f"cannot lstat {logical_path!r}: {exc}")
        kind = _stat_kind(st)
        if kind == "symlink":
            return _blocked_observation(kind, "SYMLINK_FORBIDDEN", logical_path)
        if kind == "reparsePoint":
            return _blocked_observation(kind, "REPARSE_POINT_FORBIDDEN", logical_path)
        if kind != "file":
            return _base_observation(kind)

        try:
            file_fd = os.open(leaf, flags_file, dir_fd=fd)
        except OSError as exc:
            _fail("TXR_OBSERVATION_FAILED", f"cannot open {logical_path!r} without following links: {exc}")
        try:
            digest, before, _ = _hash_fd(file_fd)
        finally:
            os.close(file_fd)
        try:
            named_after = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as exc:
            _fail("TXR_UNSTABLE_OBSERVATION", f"file path changed after hashing {logical_path!r}: {exc}")
        if not _same_file_snapshot(before, named_after):
            _fail("TXR_UNSTABLE_OBSERVATION", f"file path changed while being hashed: {logical_path!r}")
        observation = _base_observation("file")
        observation.update({
            "sha256": digest,
            "size": int(before.st_size),
            "linkCount": int(before.st_nlink),
        })
        if operation_kind in {"replace", "delete"} and before.st_nlink != 1:
            observation["blockedAt"] = logical_path
            observation["pathSafety"] = {
                "status": "BLOCKED",
                "issues": [{"code": "HARDLINK_FORBIDDEN", "component": logical_path}],
            }
        return observation
    finally:
        for item in reversed(opened):
            try:
                os.close(item)
            except OSError:
                pass


def _observe_fallback(game_root: Path, logical_path: str, operation_kind: str) -> dict[str, Any]:
    current = game_root
    parts = logical_path.split("/")
    prefix: list[str] = []
    for part in parts[:-1]:
        prefix.append(part)
        component = "/".join(prefix)
        try:
            names = os.listdir(current)
        except OSError as exc:
            _fail("TXR_OBSERVATION_FAILED", f"cannot list ancestor {component!r}: {exc}")
        if part not in names:
            if _find_case_mismatch(names, part) is not None:
                return _blocked_observation("other", "CASE_MISMATCH", component)
            return _blocked_observation("missing", "ANCESTOR_MISSING", component)
        current = current / part
        st = os.lstat(current)
        kind = _stat_kind(st)
        if kind == "symlink":
            return _blocked_observation(kind, "SYMLINK_FORBIDDEN", component)
        if kind == "reparsePoint":
            return _blocked_observation(kind, "REPARSE_POINT_FORBIDDEN", component)
        if kind != "directory":
            return _blocked_observation(kind, "ANCESTOR_NOT_DIRECTORY", component)

    leaf = parts[-1]
    names = os.listdir(current)
    if leaf not in names:
        if _find_case_mismatch(names, leaf) is not None:
            return _blocked_observation("other", "CASE_MISMATCH", logical_path)
        return _base_observation("missing")
    target = current / leaf
    st = os.lstat(target)
    kind = _stat_kind(st)
    if kind == "symlink":
        return _blocked_observation(kind, "SYMLINK_FORBIDDEN", logical_path)
    if kind == "reparsePoint":
        return _blocked_observation(kind, "REPARSE_POINT_FORBIDDEN", logical_path)
    if kind != "file":
        return _base_observation(kind)
    with target.open("rb") as fh:
        before = os.fstat(fh.fileno())
        h = hashlib.sha256()
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
        after = os.fstat(fh.fileno())
    if not _same_file_snapshot(before, after):
        _fail("TXR_UNSTABLE_OBSERVATION", f"file changed while being hashed: {logical_path!r}")
    try:
        named_after = os.lstat(target)
    except OSError as exc:
        _fail("TXR_UNSTABLE_OBSERVATION", f"file path changed after hashing {logical_path!r}: {exc}")
    if not _same_file_snapshot(before, named_after):
        _fail("TXR_UNSTABLE_OBSERVATION", f"file path changed while being hashed: {logical_path!r}")
    observation = _base_observation("file")
    observation.update({"sha256": h.hexdigest(), "size": before.st_size, "linkCount": before.st_nlink})
    if operation_kind in {"replace", "delete"} and before.st_nlink != 1:
        observation["blockedAt"] = logical_path
        observation["pathSafety"] = {
            "status": "BLOCKED",
            "issues": [{"code": "HARDLINK_FORBIDDEN", "component": logical_path}],
        }
    return observation


def validate_game_root(game_root: str | os.PathLike[str]) -> Path:
    root = Path(game_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    root = Path(os.path.abspath(root))
    try:
        st = os.lstat(root)
    except OSError as exc:
        _fail("TXR_ROOT_UNSAFE", f"cannot lstat game root: {exc}")
    kind = _stat_kind(st)
    if kind == "symlink":
        _fail("TXR_ROOT_UNSAFE", "game root is a symlink")
    if kind == "reparsePoint":
        _fail("TXR_ROOT_UNSAFE", "game root is a reparse point")
    if kind != "directory":
        _fail("TXR_ROOT_UNSAFE", f"game root is {kind}, expected directory")
    return root


def observe_operation_path(game_root: str | os.PathLike[str], operation: dict[str, Any]) -> dict[str, Any]:
    logical_path = operation["path"]
    validate_logical_path(logical_path)
    root = validate_game_root(game_root)
    if os.name == "posix" and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd:
        return _observe_posix(root, logical_path, operation["kind"])
    return _observe_fallback(root, logical_path, operation["kind"])


def compare_game_target_binding(expected: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    validate_game_target_semantics(expected)
    validate_game_target_semantics(current)
    mismatches: list[dict[str, Any]] = []

    def compare(field: str, exp: Any, cur: Any) -> None:
        if exp != cur:
            mismatches.append({"field": field, "expected": exp, "actual": cur})

    for field in ("steamAppId", "gameVersion", "engineBuild", "steamBuildId", "steamBranch"):
        compare(field, expected[field], current[field])
    for field in ("hostOs", "gameOs", "hostArch", "gameArch"):
        compare(f"platform.{field}", expected["platform"][field], current["platform"][field])
    compare(
        "platform.compatibilityLayer.kind",
        expected["platform"]["compatibilityLayer"]["kind"],
        current["platform"]["compatibilityLayer"]["kind"],
    )

    efp = expected["fingerprints"]
    cfp = current["fingerprints"]
    compare("fingerprints.algorithm", efp["algorithm"], cfp["algorithm"])
    compare("fingerprints.canonicalPolicy", efp["canonicalPolicy"], cfp["canonicalPolicy"])
    compare(
        "fingerprints.canonicalGameFingerprint",
        efp["canonicalGameFingerprint"],
        cfp["canonicalGameFingerprint"],
    )

    current_targets = {item["path"]: item for item in cfp["targetFingerprints"]}
    for expected_target in efp["targetFingerprints"]:
        path = expected_target["path"]
        actual_target = current_targets.get(path)
        if actual_target is None:
            mismatches.append({"field": f"targetFingerprints[{path}]", "expected": expected_target, "actual": None})
        elif actual_target != expected_target:
            mismatches.append({"field": f"targetFingerprints[{path}]", "expected": expected_target, "actual": actual_target})

    return {"status": "MATCH" if not mismatches else "MISMATCH", "mismatches": mismatches}


def assess_journal_status(status: str, classification: str) -> str:
    if classification == "FOREIGN":
        return "FOREIGN"
    if status == "PENDING":
        return "MATCHES_OBSERVED_STATE" if classification == "BEFORE" else "STALE_STATUS"
    if status in {"APPLIED", "VERIFIED"}:
        return "MATCHES_OBSERVED_STATE" if classification == "AFTER" else "STATE_REGRESSED"
    if status == "ROLLED_BACK":
        return "MATCHES_OBSERVED_STATE" if classification == "BEFORE" else "STATE_REGRESSED"
    return "FOREIGN"


def _decision_for_phase(journal: dict[str, Any], observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    phase = journal["phase"]
    operations = journal["operations"]
    classifications = [classify_current_state(op, observations[op["operationId"]]) for op in operations]

    if any(obs["pathSafety"]["status"] == "BLOCKED" for obs in observations.values()):
        return {"decision": "PATH_POLICY_BLOCKED"}
    if "FOREIGN" in classifications:
        return {"decision": "FOREIGN_MODIFICATION"}

    if phase in {"PLANNED", "PREPARED"}:
        if all(state == "BEFORE" for state in classifications):
            return {"decision": "NO_RECOVERY_NEEDED"}
        return {"decision": "RECOVERY_REQUIRED"}

    if phase in {"COMMITTING", "RECOVERY_REQUIRED"}:
        result = classify_commit_recovery(operations, observations)
        decision = {"decision": result["decision"]}
        if "nextSequence" in result:
            decision["nextSequence"] = result["nextSequence"]
        return decision

    if phase == "VERIFYING":
        if all(state == "AFTER" for state in classifications):
            return {"decision": "READY_TO_VERIFY"}
        return {"decision": "RECOVERY_REQUIRED"}

    if phase == "ROLLBACK_REQUIRED":
        rollback = [classify_rollback_safety(op, observations[op["operationId"]]) for op in operations]
        if "FOREIGN" in rollback:
            return {"decision": "FOREIGN_MODIFICATION"}
        sequences = [op["sequence"] for op, state in zip(operations, rollback) if state == "CAN_ROLLBACK"]
        if not sequences:
            return {"decision": "ROLLBACK_COMPLETE"}
        return {"decision": "ROLLBACK_REQUIRED", "rollbackSequences": sorted(sequences, reverse=True)}

    if phase == "FOREIGN_MODIFICATION":
        return {"decision": "RECOVERY_REQUIRED"}

    if phase == "COMMITTED":
        return {"decision": "TERMINAL_COMMITTED" if all(s == "AFTER" for s in classifications) else "FOREIGN_MODIFICATION"}

    if phase == "FAILED":
        return {"decision": "TERMINAL_FAILED"}

    return {"decision": "RECOVERY_REQUIRED"}


def inspect_transaction_recovery(
    journal: dict[str, Any],
    game_root: str | os.PathLike[str],
    current_game_target: dict[str, Any],
    *,
    inspected_at: str | None = None,
) -> dict[str, Any]:
    validate_transaction_journal_semantics(journal)
    validate_game_target_semantics(current_game_target)
    root = validate_game_root(game_root)
    target_binding = compare_game_target_binding(journal["gameTarget"], current_game_target)

    observations: dict[str, dict[str, Any]] = {}
    operation_reports: list[dict[str, Any]] = []
    before_count = after_count = foreign_count = unsafe_count = 0

    for op in journal["operations"]:
        observed = observe_operation_path(root, op)
        observations[op["operationId"]] = observed
        classification = classify_current_state(op, observed)
        if classification == "BEFORE":
            before_count += 1
        elif classification == "AFTER":
            after_count += 1
        else:
            foreign_count += 1
        if observed["pathSafety"]["status"] == "BLOCKED":
            unsafe_count += 1
        operation_reports.append({
            "operationId": op["operationId"],
            "sequence": op["sequence"],
            "path": op["path"],
            "kind": op["kind"],
            "journalStatus": op["status"],
            "observation": observed,
            "classification": classification,
            "journalStatusAssessment": assess_journal_status(op["status"], classification),
        })

    if target_binding["status"] == "MISMATCH":
        recovery = {"decision": "TARGET_MISMATCH"}
    else:
        recovery = _decision_for_phase(journal, observations)

    return {
        "schema": "smml.transaction-recovery-report/1",
        "mode": "read-only",
        "transactionId": journal["transactionId"],
        "journalRevision": journal["journalRevision"],
        "journalPhase": journal["phase"],
        "inspectedAt": inspected_at or _utc_now(),
        "gameTargetBinding": target_binding,
        "summary": {
            "operationCount": len(operation_reports),
            "beforeCount": before_count,
            "afterCount": after_count,
            "foreignCount": foreign_count,
            "unsafePathCount": unsafe_count,
        },
        "operations": operation_reports,
        "recovery": recovery,
    }


def path_is_within(root: Path, candidate: Path) -> bool:
    try:
        root_abs = Path(root).resolve(strict=True)
    except OSError:
        root_abs = Path(os.path.abspath(root))
    candidate_abs = Path(candidate).resolve(strict=False)
    try:
        candidate_abs.relative_to(root_abs)
        return True
    except ValueError:
        return False


def dump_report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=False) + "\n").encode("utf-8")


class TransactionRecoveryReportSemanticError(ValueError):
    pass


def validate_transaction_recovery_report_semantics(report: dict[str, Any]) -> None:
    operations = report["operations"]
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_path_keys: dict[str, str] = {}
    counts = {"BEFORE": 0, "AFTER": 0, "FOREIGN": 0}
    unsafe = 0
    for index, item in enumerate(operations):
        if item["sequence"] != index:
            raise TransactionRecoveryReportSemanticError(
                f"operation sequence must equal array index: expected {index}, got {item['sequence']}"
            )
        if item["operationId"] in seen_ids:
            raise TransactionRecoveryReportSemanticError(f"duplicate operationId: {item['operationId']!r}")
        seen_ids.add(item["operationId"])
        validate_logical_path(item["path"])
        if item["path"] in seen_paths:
            raise TransactionRecoveryReportSemanticError(f"duplicate operation path: {item['path']!r}")
        seen_paths.add(item["path"])
        key = portable_collision_key(item["path"])
        previous = seen_path_keys.get(key)
        if previous is not None:
            raise TransactionRecoveryReportSemanticError(
                f"portable path collision: {previous!r} vs {item['path']!r}"
            )
        seen_path_keys[key] = item["path"]
        counts[item["classification"]] += 1
        if item["observation"]["pathSafety"]["status"] == "BLOCKED":
            unsafe += 1

    summary = report["summary"]
    expected = {
        "operationCount": len(operations),
        "beforeCount": counts["BEFORE"],
        "afterCount": counts["AFTER"],
        "foreignCount": counts["FOREIGN"],
        "unsafePathCount": unsafe,
    }
    if summary != expected:
        raise TransactionRecoveryReportSemanticError(
            f"summary does not match operation reports: expected {expected!r}, got {summary!r}"
        )

    binding = report["gameTargetBinding"]["status"]
    decision = report["recovery"]["decision"]
    if binding == "MISMATCH" and decision != "TARGET_MISMATCH":
        raise TransactionRecoveryReportSemanticError("target mismatch must force TARGET_MISMATCH")
    if binding == "MATCH" and decision == "TARGET_MISMATCH":
        raise TransactionRecoveryReportSemanticError("TARGET_MISMATCH requires a mismatched target binding")

    recovery = report["recovery"]
    if decision == "RESUME_COMMIT" and recovery["nextSequence"] >= len(operations):
        raise TransactionRecoveryReportSemanticError("nextSequence must reference an operation")
    if decision == "ROLLBACK_REQUIRED":
        seq = recovery["rollbackSequences"]
        if seq != sorted(seq, reverse=True):
            raise TransactionRecoveryReportSemanticError("rollbackSequences must be in descending order")
        if any(value >= len(operations) for value in seq):
            raise TransactionRecoveryReportSemanticError("rollbackSequences must reference operations")
