from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


class SemanticValidationError(ValueError):
    pass


def _validate_relative_path(value: str) -> None:
    if not value:
        raise SemanticValidationError("path must not be empty")
    if "\\" in value:
        raise SemanticValidationError(f"backslash is forbidden in path: {value!r}")
    if "\x00" in value:
        raise SemanticValidationError("NUL is forbidden in paths")
    if value.startswith("/"):
        raise SemanticValidationError(f"absolute path is forbidden: {value!r}")
    if len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] == "/":
        raise SemanticValidationError(f"drive-absolute path is forbidden: {value!r}")
    if "//" in value:
        raise SemanticValidationError(f"empty path segment is forbidden: {value!r}")

    parts = PurePosixPath(value).parts
    if any(part in {".", ".."} for part in parts):
        raise SemanticValidationError(f"dot segment is forbidden: {value!r}")


def _validate_casefold_unique(items: list[dict[str, Any]], label: str) -> None:
    seen: dict[str, str] = {}
    for item in items:
        path = item["path"]
        _validate_relative_path(path)
        key = path.casefold()
        previous = seen.get(key)
        if previous is not None:
            raise SemanticValidationError(
                f"{label} contains a case-insensitive collision: {previous!r} vs {path!r}"
            )
        seen[key] = path


def validate_policy_semantics(policy: dict[str, Any]) -> None:
    seen_prefixes: dict[str, str] = {}
    for prefix in policy["excludedFilePrefixes"]:
        if not prefix.endswith("/"):
            raise SemanticValidationError(f"excluded prefix must end with '/': {prefix!r}")
        _validate_relative_path(prefix[:-1])
        key = prefix.casefold()
        previous = seen_prefixes.get(key)
        if previous is not None:
            raise SemanticValidationError(
                f"excludedFilePrefixes contains a case-insensitive collision: {previous!r} vs {prefix!r}"
            )
        seen_prefixes[key] = prefix

    seen_files: dict[str, str] = {}
    for path in policy["excludedExactFiles"]:
        _validate_relative_path(path)
        key = path.casefold()
        previous = seen_files.get(key)
        if previous is not None:
            raise SemanticValidationError(
                f"excludedExactFiles contains a case-insensitive collision: {previous!r} vs {path!r}"
            )
        seen_files[key] = path


def validate_semantics(document: dict[str, Any]) -> None:
    platform = document["platform"]
    host_os = platform["hostOs"]
    game_os = platform["gameOs"]
    layer = platform["compatibilityLayer"]["kind"]

    if host_os != game_os and layer == "none":
        raise SemanticValidationError(
            "compatibilityLayer.kind must not be 'none' when hostOs != gameOs"
        )
    if host_os == game_os and layer == "none":
        pass

    fps = document["fingerprints"]
    exact = fps["installationExactFingerprint"]
    canonical = fps["canonicalGameFingerprint"]

    if canonical["fileCount"] > exact["fileCount"]:
        raise SemanticValidationError(
            "canonicalGameFingerprint.fileCount must not exceed installationExactFingerprint.fileCount"
        )
    if canonical["totalFileBytes"] > exact["totalFileBytes"]:
        raise SemanticValidationError(
            "canonicalGameFingerprint.totalFileBytes must not exceed installationExactFingerprint.totalFileBytes"
        )

    _validate_casefold_unique(fps["rootFingerprints"], "rootFingerprints")
    _validate_casefold_unique(fps["targetFingerprints"], "targetFingerprints")


def content_tree_fingerprint(records: list[dict[str, Any]]) -> str:
    """Reference implementation for smml.content-tree-sha256/1 tests only."""
    import hashlib

    normalized = []
    for record in records:
        path = str(record["path"])
        _validate_relative_path(path)
        size = int(record["size"])
        sha256 = str(record["sha256"])
        if size < 0:
            raise SemanticValidationError("file size must be >= 0")
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise SemanticValidationError("sha256 must be 64 lowercase hex characters")
        normalized.append((path, size, sha256))

    normalized.sort(key=lambda row: (row[0].casefold(), row[0].encode("utf-8")))

    h = hashlib.sha256()
    for path, size, sha256 in normalized:
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        h.update(sha256.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def apply_canonical_policy(
    records: list[dict[str, Any]], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    prefixes = tuple(policy.get("excludedFilePrefixes", []))
    exact = set(policy.get("excludedExactFiles", []))

    result = []
    for record in records:
        path = str(record["path"])
        if path in exact:
            continue
        if any(path.startswith(prefix) for prefix in prefixes):
            continue
        result.append(record)
    return result
