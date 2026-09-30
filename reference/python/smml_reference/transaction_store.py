from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .hashing import sha256_bytes
from .path_policy import portable_collision_key, validate_logical_path
from .transaction_journal import ALLOWED_TRANSITIONS, validate_transaction_journal_semantics

FaultInjector = Callable[[str], None]


@dataclass
class TransactionStoreError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InjectedTransactionFault(RuntimeError):
    pass


def _fail(code: str, detail: str) -> None:
    raise TransactionStoreError(code, detail)


def _inject(injector: FaultInjector | None, point: str) -> None:
    if injector is not None:
        injector(point)


def _is_reparse(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attrs & flag)


def _ensure_real_directory(path: Path, *, create: bool = False) -> Path:
    path = Path(path)
    if create and not path.exists() and not path.is_symlink():
        parent = path.parent
        if parent == path:
            _fail("TXS_DIRECTORY_UNAVAILABLE", f"cannot create directory root: {path}")
        _ensure_real_directory(parent, create=True)
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            _fail("TXS_DIRECTORY_UNAVAILABLE", f"cannot create directory {path}: {exc}")
        _fsync_directory(parent)
    try:
        st = path.lstat()
    except OSError as exc:
        _fail("TXS_DIRECTORY_UNAVAILABLE", f"cannot inspect directory {path}: {exc}")
    if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
        _fail("TXS_DIRECTORY_UNSAFE", f"directory is a symlink/reparse point: {path}")
    if not stat.S_ISDIR(st.st_mode):
        _fail("TXS_NOT_DIRECTORY", str(path))
    return path


def validate_state_root(state_root: str | os.PathLike[str]) -> Path:
    root = _ensure_real_directory(Path(state_root), create=False)
    return root.resolve(strict=True)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if os.name == "posix":
            _fail("TXS_DIRECTORY_FSYNC_FAILED", f"cannot open directory for fsync {path}: {exc}")
        return
    try:
        try:
            os.fsync(fd)
        except OSError as exc:
            if os.name == "posix":
                _fail("TXS_DIRECTORY_FSYNC_FAILED", f"cannot fsync directory {path}: {exc}")
            # Windows durability semantics are explicitly not yet claimed by v1.
            return
    finally:
        os.close(fd)


def _read_regular_bytes_nofollow(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        st = path.lstat()
    except FileNotFoundError:
        _fail("TXS_FILE_MISSING", str(path))
    except OSError as exc:
        _fail("TXS_READ_FAILED", f"cannot lstat {path}: {exc}")
    if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
        _fail("TXS_FILE_UNSAFE", f"refusing symlink/reparse point: {path}")
    if not stat.S_ISREG(st.st_mode):
        _fail("TXS_NOT_REGULAR_FILE", str(path))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        _fail("TXS_READ_FAILED", f"cannot open {path}: {exc}")
    try:
        opened = os.fstat(fd)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, getattr(opened, "st_mtime_ns", 0)) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            getattr(after, "st_mtime_ns", 0),
        ):
            _fail("TXS_UNSTABLE_READ", str(path))
        return b"".join(chunks)
    finally:
        os.close(fd)


def _cleanup_stale_temps(parent: Path, name: str) -> None:
    prefix = f".{name}.tmp-"
    for child in parent.iterdir():
        if child.name.startswith(prefix):
            try:
                st = child.lstat()
                if stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                    child.unlink()
            except OSError:
                pass


def _atomic_publish_bytes(
    path: Path,
    data: bytes,
    *,
    fault_injector: FaultInjector | None = None,
    fault_prefix: str = "publish",
) -> None:
    parent = _ensure_real_directory(path.parent, create=True)
    _cleanup_stale_temps(parent, path.name)
    _inject(fault_injector, f"{fault_prefix}.before_temp_create")

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=parent)
    temp = Path(temp_name)
    replaced = False
    try:
        os.fchmod(fd, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(fd, data[offset:])
        os.fsync(fd)
        _inject(fault_injector, f"{fault_prefix}.after_temp_fsync")
        os.close(fd)
        fd = -1
        os.replace(temp, path)
        replaced = True
        _inject(fault_injector, f"{fault_prefix}.after_replace")
        _fsync_directory(parent)
        _inject(fault_injector, f"{fault_prefix}.after_directory_fsync")
    except InjectedTransactionFault:
        # A deliberate injected failure models a crash: a sibling temp may remain, or
        # the final atomic replacement may already be visible. Neither state permits
        # partial JSON.
        raise
    except Exception:
        if not replaced and temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass
        raise
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if not replaced and temp.exists() and fault_injector is None:
            try:
                temp.unlink()
            except OSError:
                pass


def _journal_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _load_json_file(path: Path) -> dict[str, Any]:
    raw = _read_regular_bytes_nofollow(path)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("TXS_INVALID_JSON", f"{path}: {exc}")
    if not isinstance(value, dict):
        _fail("TXS_INVALID_JSON", f"top-level value must be an object: {path}")
    return value


def _operation_immutable_projection(op: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in op.items() if key != "status"}


def _validate_journal_rewrite(old: dict[str, Any], new: dict[str, Any]) -> None:
    if new["transactionId"] != old["transactionId"]:
        _fail("TXS_JOURNAL_ID_CHANGED", "transactionId is immutable")
    if new["journalRevision"] != old["journalRevision"] + 1:
        _fail("TXS_JOURNAL_REVISION", "journalRevision must increment by exactly one")
    if new["createdAt"] != old["createdAt"]:
        _fail("TXS_JOURNAL_IMMUTABLE", "createdAt is immutable")
    if new["updatedAt"] < old["updatedAt"]:
        _fail("TXS_JOURNAL_TIME_REGRESSION", "updatedAt must not move backwards")
    if new["gameTarget"] != old["gameTarget"]:
        _fail("TXS_JOURNAL_IMMUTABLE", "gameTarget is immutable")
    if len(new["operations"]) != len(old["operations"]):
        _fail("TXS_JOURNAL_IMMUTABLE", "operation count is immutable")

    allowed_status = {
        "PENDING": {"PENDING", "APPLIED"},
        "APPLIED": {"APPLIED", "VERIFIED", "ROLLED_BACK"},
        "VERIFIED": {"VERIFIED", "ROLLED_BACK"},
        "ROLLED_BACK": {"ROLLED_BACK"},
    }
    for old_op, new_op in zip(old["operations"], new["operations"]):
        if _operation_immutable_projection(old_op) != _operation_immutable_projection(new_op):
            _fail("TXS_JOURNAL_IMMUTABLE", f"operation changed: {old_op['operationId']}")
        if new_op["status"] not in allowed_status[old_op["status"]]:
            _fail(
                "TXS_JOURNAL_STATUS_REGRESSION",
                f"{old_op['operationId']}: {old_op['status']} -> {new_op['status']}",
            )

    old_phase = old["phase"]
    new_phase = new["phase"]
    if new_phase == old_phase:
        if new["phaseHistory"] != old["phaseHistory"]:
            _fail("TXS_JOURNAL_HISTORY", "same-phase rewrite must not alter phaseHistory")
    else:
        if new_phase not in ALLOWED_TRANSITIONS[old_phase]:
            _fail("TXS_JOURNAL_PHASE", f"invalid transition {old_phase} -> {new_phase}")
        if len(new["phaseHistory"]) != len(old["phaseHistory"]) + 1:
            _fail("TXS_JOURNAL_HISTORY", "phase transition must append exactly one history entry")
        if new["phaseHistory"][:-1] != old["phaseHistory"]:
            _fail("TXS_JOURNAL_HISTORY", "phaseHistory is append-only")
        tail = new["phaseHistory"][-1]
        if tail["revision"] != new["journalRevision"] or tail["phase"] != new_phase:
            _fail("TXS_JOURNAL_HISTORY", "appended history entry must match revision and phase")

    if new["incidents"][: len(old["incidents"])] != old["incidents"]:
        _fail("TXS_JOURNAL_INCIDENTS", "incidents are append-only")


class JournalStore:
    def __init__(self, state_root: str | os.PathLike[str], transaction_id: str):
        self.state_root = validate_state_root(state_root)
        if not isinstance(transaction_id, str) or not transaction_id.startswith("tx-"):
            _fail("TXS_BAD_TRANSACTION_ID", repr(transaction_id))
        self.transactions_root = _ensure_real_directory(self.state_root / "transactions", create=True)
        self.transaction_root = _ensure_real_directory(self.transactions_root / transaction_id, create=True)
        self.path = self.transaction_root / "journal.json"

    def exists(self) -> bool:
        return self.path.exists() or self.path.is_symlink()

    def load(self) -> dict[str, Any]:
        document = _load_json_file(self.path)
        try:
            validate_transaction_journal_semantics(document)
        except Exception as exc:
            _fail("TXS_INVALID_JOURNAL", str(exc))
        return document

    def initialize(
        self,
        document: dict[str, Any],
        *,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        try:
            validate_transaction_journal_semantics(document)
        except Exception as exc:
            _fail("TXS_INVALID_JOURNAL", str(exc))
        if document["transactionId"] != self.transaction_root.name:
            _fail("TXS_JOURNAL_ID_MISMATCH", "journal transactionId does not match store")
        if self.exists():
            current = self.load()
            if current != document:
                _fail("TXS_JOURNAL_ALREADY_EXISTS", "existing journal differs from requested initial document")
            return current
        _atomic_publish_bytes(
            self.path,
            _journal_bytes(document),
            fault_injector=fault_injector,
            fault_prefix="journal.initialize",
        )
        return self.load()

    def rewrite(
        self,
        document: dict[str, Any],
        *,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        old = self.load()
        try:
            validate_transaction_journal_semantics(document)
        except Exception as exc:
            _fail("TXS_INVALID_JOURNAL", str(exc))
        _validate_journal_rewrite(old, document)
        _atomic_publish_bytes(
            self.path,
            _journal_bytes(document),
            fault_injector=fault_injector,
            fault_prefix="journal.rewrite",
        )
        return self.load()


class StagingManifestSemanticError(ValueError):
    pass


def validate_staging_manifest_semantics(
    manifest: dict[str, Any],
    journal: dict[str, Any] | None = None,
) -> None:
    operations = manifest["operations"]
    blobs = manifest["blobs"]
    blob_sizes: dict[str, int] = {}
    previous_digest: str | None = None
    for blob in blobs:
        digest = blob["sha256"]
        if previous_digest is not None and digest <= previous_digest:
            raise StagingManifestSemanticError("blobs must be strictly ASCII-sorted by sha256")
        previous_digest = digest
        if digest in blob_sizes:
            raise StagingManifestSemanticError(f"duplicate blob: {digest}")
        blob_sizes[digest] = blob["size"]

    seen_ids: set[str] = set()
    path_keys: dict[str, str] = {}
    referenced: set[str] = set()
    for index, item in enumerate(operations):
        if item["sequence"] != index:
            raise StagingManifestSemanticError("operation sequence must equal array index")
        if item["operationId"] in seen_ids:
            raise StagingManifestSemanticError(f"duplicate operationId: {item['operationId']}")
        seen_ids.add(item["operationId"])
        validate_logical_path(item["path"])
        key = portable_collision_key(item["path"])
        previous = path_keys.get(key)
        if previous is not None:
            raise StagingManifestSemanticError(f"portable path collision: {previous!r} vs {item['path']!r}")
        path_keys[key] = item["path"]
        for role in ("before", "after"):
            state = item[role]
            if state["exists"]:
                digest = state["sha256"]
                referenced.add(digest)
                if blob_sizes.get(digest) != state["size"]:
                    raise StagingManifestSemanticError(
                        f"{item['operationId']} {role} state does not match blob inventory"
                    )

    if referenced != set(blob_sizes):
        raise StagingManifestSemanticError("blobs must equal the unique set referenced by operation states")

    if journal is not None:
        if manifest["transactionId"] != journal["transactionId"]:
            raise StagingManifestSemanticError("transactionId does not match journal")
        if manifest["journalRevision"] != journal["journalRevision"]:
            raise StagingManifestSemanticError("journalRevision does not match journal")
        if len(operations) != len(journal["operations"]):
            raise StagingManifestSemanticError("operation count does not match journal")
        for binding, op in zip(operations, journal["operations"]):
            for field in ("operationId", "sequence", "path"):
                if binding[field] != op[field]:
                    raise StagingManifestSemanticError(f"operation {field} does not match journal")
            for role in ("before", "after"):
                journal_state = op[role]
                staged_state = binding[role]
                if bool(journal_state["exists"]) != bool(staged_state["exists"]):
                    raise StagingManifestSemanticError(f"{op['operationId']} {role}.exists does not match journal")
                if journal_state["exists"] and journal_state["sha256"] != staged_state["sha256"]:
                    raise StagingManifestSemanticError(f"{op['operationId']} {role}.sha256 does not match journal")


class StagingStore:
    def __init__(self, state_root: str | os.PathLike[str], transaction_id: str):
        self.state_root = validate_state_root(state_root)
        self.transactions_root = _ensure_real_directory(self.state_root / "transactions", create=True)
        self.transaction_root = _ensure_real_directory(self.transactions_root / transaction_id, create=True)
        self.staging_root = _ensure_real_directory(self.transaction_root / "staging", create=True)
        self.sha_root = _ensure_real_directory(self.staging_root / "blobs" / "sha256", create=True)
        self.manifest_path = self.staging_root / "manifest.json"

    def blob_path(self, digest: str) -> Path:
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            _fail("TXS_BAD_DIGEST", repr(digest))
        prefix = _ensure_real_directory(self.sha_root / digest[:2], create=True)
        return prefix / digest

    def put_fd(
        self,
        source_fd: int,
        expected_sha256: str,
        *,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        if len(expected_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha256):
            _fail("TXS_BAD_DIGEST", repr(expected_sha256))
        path = self.blob_path(expected_sha256)
        final_exists = path.exists() or path.is_symlink()
        parent = path.parent
        temp: Path | None = None
        temp_fd = -1
        if not final_exists:
            _cleanup_stale_temps(parent, path.name)
            temp_fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=parent)
            os.fchmod(temp_fd, 0o600)
            temp = Path(temp_name)

        import hashlib

        h = hashlib.sha256()
        total = 0
        try:
            os.lseek(source_fd, 0, os.SEEK_SET)
        except OSError:
            pass
        try:
            while True:
                chunk = os.read(source_fd, 1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                total += len(chunk)
                if temp_fd >= 0:
                    offset = 0
                    while offset < len(chunk):
                        offset += os.write(temp_fd, chunk[offset:])
            actual = h.hexdigest()
            if actual != expected_sha256:
                _fail("TXS_STAGED_DIGEST_MISMATCH", f"expected {expected_sha256}, got {actual}")

            if final_exists:
                existing = _read_regular_bytes_nofollow(path)
                if len(existing) != total or sha256_bytes(existing) != expected_sha256:
                    _fail("TXS_STAGED_BLOB_CORRUPT", str(path))
                return {"sha256": expected_sha256, "size": total}

            os.fsync(temp_fd)
            _inject(fault_injector, "staging.blob.after_temp_fsync")
            os.close(temp_fd)
            temp_fd = -1
            os.replace(temp, path)
            temp = None
            _inject(fault_injector, "staging.blob.after_replace")
            _fsync_directory(parent)
            _inject(fault_injector, "staging.blob.after_directory_fsync")
            _inject(fault_injector, "staging.blob.after_publication")
            final = _read_regular_bytes_nofollow(path)
            if len(final) != total or sha256_bytes(final) != expected_sha256:
                _fail("TXS_STAGED_BLOB_CORRUPT", str(path))
            return {"sha256": expected_sha256, "size": total}
        except InjectedTransactionFault:
            raise
        except Exception:
            if temp is not None and temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
            raise
        finally:
            if temp_fd >= 0:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass
            if temp is not None and temp.exists() and fault_injector is None:
                try:
                    temp.unlink()
                except OSError:
                    pass

    def put_bytes(
        self,
        data: bytes,
        expected_sha256: str,
        *,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        actual = sha256_bytes(data)
        if actual != expected_sha256:
            _fail("TXS_STAGED_DIGEST_MISMATCH", f"expected {expected_sha256}, got {actual}")
        path = self.blob_path(actual)
        if path.exists() or path.is_symlink():
            existing = _read_regular_bytes_nofollow(path)
            if sha256_bytes(existing) != actual:
                _fail("TXS_STAGED_BLOB_CORRUPT", str(path))
            if existing != data:
                _fail("TXS_STAGED_BLOB_CORRUPT", f"same digest path has different bytes: {path}")
            return {"sha256": actual, "size": len(existing)}

        _atomic_publish_bytes(
            path,
            data,
            fault_injector=fault_injector,
            fault_prefix="staging.blob",
        )
        _inject(fault_injector, "staging.blob.after_publication")
        final = _read_regular_bytes_nofollow(path)
        if sha256_bytes(final) != actual:
            _fail("TXS_STAGED_BLOB_CORRUPT", str(path))
        return {"sha256": actual, "size": len(final)}

    def verify_blob(self, digest: str, size: int) -> None:
        path = self.blob_path(digest)
        data = _read_regular_bytes_nofollow(path)
        if len(data) != size or sha256_bytes(data) != digest:
            _fail("TXS_STAGED_BLOB_CORRUPT", digest)

    def write_manifest(
        self,
        manifest: dict[str, Any],
        *,
        journal: dict[str, Any] | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> dict[str, Any]:
        try:
            validate_staging_manifest_semantics(manifest, journal)
        except Exception as exc:
            _fail("TXS_INVALID_STAGING_MANIFEST", str(exc))
        for blob in manifest["blobs"]:
            self.verify_blob(blob["sha256"], blob["size"])
        data = _journal_bytes(manifest)
        _atomic_publish_bytes(
            self.manifest_path,
            data,
            fault_injector=fault_injector,
            fault_prefix="staging.manifest",
        )
        _inject(fault_injector, "staging.manifest.after_publication")
        return self.load_manifest(journal=journal)

    def load_manifest(self, *, journal: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = _load_json_file(self.manifest_path)
        try:
            validate_staging_manifest_semantics(manifest, journal)
        except Exception as exc:
            _fail("TXS_INVALID_STAGING_MANIFEST", str(exc))
        for blob in manifest["blobs"]:
            self.verify_blob(blob["sha256"], blob["size"])
        return manifest


__all__ = [
    "FaultInjector",
    "InjectedTransactionFault",
    "JournalStore",
    "StagingManifestSemanticError",
    "StagingStore",
    "TransactionStoreError",
    "validate_staging_manifest_semantics",
    "validate_state_root",
]
