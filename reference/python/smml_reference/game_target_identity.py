from __future__ import annotations

from typing import Any

from .hashing import apply_canonical_policy, content_tree_fingerprint
from .path_policy import (
    PathPolicyError,
    portable_collision_key,
    validate_logical_path,
    validate_logical_prefix,
)


class SemanticValidationError(ValueError):
    pass


def _validate_relative_path(value: str) -> None:
    try:
        validate_logical_path(value)
    except PathPolicyError as exc:
        raise SemanticValidationError(str(exc)) from exc


def _validate_casefold_unique(items: list[dict[str, Any]], label: str) -> None:
    seen: dict[str, str] = {}
    for item in items:
        path = item["path"]
        _validate_relative_path(path)
        key = portable_collision_key(path)
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
        try:
            validate_logical_prefix(prefix)
        except PathPolicyError as exc:
            raise SemanticValidationError(str(exc)) from exc
        key = portable_collision_key(prefix[:-1]) + "/"
        previous = seen_prefixes.get(key)
        if previous is not None:
            raise SemanticValidationError(
                f"excludedFilePrefixes contains a case-insensitive collision: {previous!r} vs {prefix!r}"
            )
        seen_prefixes[key] = prefix

    seen_files: dict[str, str] = {}
    for path in policy["excludedExactFiles"]:
        _validate_relative_path(path)
        key = portable_collision_key(path)
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


__all__ = [
    "SemanticValidationError",
    "apply_canonical_policy",
    "content_tree_fingerprint",
    "validate_policy_semantics",
    "validate_semantics",
]
