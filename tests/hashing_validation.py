from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from path_policy_validation import (
    PathPolicyError,
    portable_collision_key,
    validate_logical_path,
    validate_logical_prefix,
)

CONTENT_TREE_ALGORITHM = "smml.content-tree-sha256/1"


@dataclass(frozen=True)
class HashingError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _raise(code: str, detail: str) -> None:
    raise HashingError(code, detail)


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        _raise("HASH_BAD_INPUT", "sha256_bytes requires bytes")
    return hashlib.sha256(data).hexdigest()


def _validate_sha256(value: Any) -> str:
    if not isinstance(value, str):
        _raise("HASH_BAD_SHA256", "sha256 must be a string")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _raise("HASH_BAD_SHA256", "sha256 must be 64 lowercase hex characters")
    return value


def _normalize_records(records: Iterable[dict[str, Any]]) -> list[tuple[str, int, str, str]]:
    normalized: list[tuple[str, int, str, str]] = []
    seen_paths: set[str] = set()
    seen_keys: dict[str, str] = {}

    for record in records:
        if not isinstance(record, dict):
            _raise("HASH_BAD_INPUT", "content record must be an object")

        path = record.get("path")
        try:
            validate_logical_path(path)
            key = portable_collision_key(path)
        except PathPolicyError:
            raise

        if path in seen_paths:
            _raise("HASH_DUPLICATE_PATH", repr(path))
        seen_paths.add(path)

        previous = seen_keys.get(key)
        if previous is not None:
            _raise("HASH_PATH_COLLISION", f"{previous!r} vs {path!r}")
        seen_keys[key] = path

        size = record.get("size")
        if isinstance(size, bool) or not isinstance(size, int):
            _raise("HASH_BAD_INPUT", f"size for {path!r} must be an integer")
        if size < 0:
            _raise("HASH_NEGATIVE_SIZE", f"{path!r}: {size}")

        digest = _validate_sha256(record.get("sha256"))
        normalized.append((path, size, digest, key))

    normalized.sort(key=lambda row: (row[3], row[0].encode("utf-8")))
    return normalized


def content_tree_payload(records: Iterable[dict[str, Any]]) -> bytes:
    payload = bytearray()
    for path, size, digest, _ in _normalize_records(records):
        payload.extend(path.encode("utf-8"))
        payload.append(0)
        payload.extend(str(size).encode("ascii"))
        payload.append(0)
        payload.extend(digest.encode("ascii"))
        payload.append(0x0A)
    return bytes(payload)


def content_tree_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    normalized = _normalize_records(records)
    h = hashlib.sha256()
    total = 0
    for path, size, digest, _ in normalized:
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
        total += size
    return {
        "algorithm": CONTENT_TREE_ALGORITHM,
        "sha256": h.hexdigest(),
        "fileCount": len(normalized),
        "totalFileBytes": total,
    }


def content_tree_fingerprint(records: Iterable[dict[str, Any]]) -> str:
    return str(content_tree_summary(records)["sha256"])


def _validate_policy_paths(policy: dict[str, Any]) -> None:
    if policy.get("contentTreeAlgorithm") != CONTENT_TREE_ALGORITHM:
        _raise(
            "HASH_POLICY_ALGORITHM_MISMATCH",
            repr(policy.get("contentTreeAlgorithm")),
        )
    for prefix in policy.get("excludedFilePrefixes", []):
        validate_logical_prefix(prefix)
    for path in policy.get("excludedExactFiles", []):
        validate_logical_path(path)


def apply_canonical_policy(
    records: Iterable[dict[str, Any]], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    _validate_policy_paths(policy)

    # Validate the complete input set before filtering. A policy must not be able
    # to hide an invalid/ambiguous inventory entry.
    record_list = list(records)
    _normalize_records(record_list)

    prefixes = tuple(policy.get("excludedFilePrefixes", []))
    exact = set(policy.get("excludedExactFiles", []))

    result: list[dict[str, Any]] = []
    for record in record_list:
        path = record["path"]
        if path in exact:
            continue
        if any(path.startswith(prefix) for prefix in prefixes):
            continue
        result.append(record)
    return result


def canonical_tree_summary(
    records: Iterable[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    return content_tree_summary(apply_canonical_policy(records, policy))


def subtree_records(
    records: Iterable[dict[str, Any]], root_path: str
) -> list[dict[str, Any]]:
    validate_logical_path(root_path)
    record_list = list(records)
    _normalize_records(record_list)
    prefix = root_path + "/"
    return [
        record
        for record in record_list
        if record["path"] == root_path or record["path"].startswith(prefix)
    ]


def subtree_fingerprint(
    records: Iterable[dict[str, Any]], root_path: str
) -> str:
    return content_tree_fingerprint(subtree_records(records, root_path))


def managed_output_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return content_tree_summary(records)
