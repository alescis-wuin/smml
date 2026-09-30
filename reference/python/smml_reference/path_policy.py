from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

UNICODE_VERSION = "15.1.0"
MAX_PATH_UTF8_BYTES = 4096
MAX_SEGMENT_UTF8_BYTES = 255
MAX_SEGMENTS = 256

_RESERVED_CHARS = set('<>:"|?*')
_RESERVED_DEVICE_BASES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
    "com¹", "com²", "com³",
    "lpt¹", "lpt²", "lpt³",
}
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class PathPolicyError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def _raise(code: str, detail: str) -> None:
    raise PathPolicyError(code, detail)


def require_unicode_version() -> None:
    if unicodedata.unidata_version != UNICODE_VERSION:
        raise RuntimeError(
            "PathPolicy reference implementation requires Unicode "
            f"{UNICODE_VERSION}, got {unicodedata.unidata_version}"
        )


def validate_logical_path(value: str) -> str:
    if not isinstance(value, str):
        _raise("TYPE_MISMATCH", "logical path must be a string")
    if not value:
        _raise("PATH_EMPTY", "logical path must not be empty")

    if value.startswith("/") or value.startswith("\\\\") or _DRIVE_PREFIX_RE.match(value):
        _raise("ABSOLUTE_OR_NAMESPACED_PATH", repr(value))
    if "\\" in value:
        _raise("BACKSLASH_FORBIDDEN", repr(value))

    if unicodedata.normalize("NFC", value) != value:
        _raise("PATH_NOT_NFC", repr(value))

    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        _raise("PATH_NOT_UTF8", f"logical path is not encodable as UTF-8: {exc}")
    if len(encoded) > MAX_PATH_UTF8_BYTES:
        _raise("PATH_TOO_LONG", f"{len(encoded)} UTF-8 bytes")

    parts = value.split("/")
    if len(parts) > MAX_SEGMENTS:
        _raise("TOO_MANY_SEGMENTS", str(len(parts)))

    for index, part in enumerate(parts):
        if part == "":
            _raise("EMPTY_SEGMENT", f"segment {index}")
        if part in {".", ".."}:
            _raise("DOT_SEGMENT", repr(part))

        try:
            part_bytes = part.encode("utf-8")
        except UnicodeEncodeError as exc:
            _raise("PATH_NOT_UTF8", f"segment {index} is not encodable as UTF-8: {exc}")
        if len(part_bytes) > MAX_SEGMENT_UTF8_BYTES:
            _raise("SEGMENT_TOO_LONG", f"segment {index}: {len(part_bytes)} UTF-8 bytes")

        for ch in part:
            cp = ord(ch)
            if cp <= 0x1F or cp == 0x7F:
                _raise("CONTROL_CHARACTER", f"U+{cp:04X} in segment {index}")
            if ch in _RESERVED_CHARS:
                _raise("RESERVED_CHARACTER", f"{ch!r} in segment {index}")

        if part.endswith(" ") or part.endswith("."):
            _raise("TRAILING_DOT_OR_SPACE", repr(part))

        device_base = part.split(".", 1)[0].casefold()
        if device_base in _RESERVED_DEVICE_BASES:
            _raise("RESERVED_DEVICE_NAME", repr(part))

    return value


def portable_collision_key(value: str) -> str:
    require_unicode_version()
    validate_logical_path(value)
    folded = value.casefold()
    return unicodedata.normalize("NFC", folded)


def validate_unique_paths(paths: Iterable[str]) -> None:
    seen: dict[str, str] = {}
    for path in paths:
        key = portable_collision_key(path)
        previous = seen.get(key)
        if previous is not None and previous != path:
            _raise("CASE_COLLISION", f"{previous!r} vs {path!r}")
        seen[key] = path


def validate_logical_prefix(value: str) -> str:
    if not value.endswith("/"):
        _raise("TYPE_MISMATCH", "logical prefix must end with '/'")
    validate_logical_path(value[:-1])
    return value


def validate_filesystem_observation(
    *,
    root_trusted: bool,
    ancestor_kinds: Iterable[str],
    leaf_kind: str,
    expected_leaf: str,
    intent: str,
    exact_case: bool = True,
    leaf_link_count: int | None = None,
) -> None:
    if not root_trusted:
        _raise("ROOT_UNTRUSTED", "root is not trusted")

    if not exact_case:
        _raise("CASE_MISMATCH", "existing component spelling differs from logical path")

    for kind in ancestor_kinds:
        if kind == "symlink":
            _raise("SYMLINK_FORBIDDEN", "ancestor is a symlink")
        if kind == "reparse-point":
            _raise("REPARSE_POINT_FORBIDDEN", "ancestor is a reparse point")
        if kind != "directory":
            _raise("TYPE_MISMATCH", f"ancestor kind is {kind!r}, expected 'directory'")

    if leaf_kind == "symlink":
        _raise("SYMLINK_FORBIDDEN", "leaf is a symlink")
    if leaf_kind == "reparse-point":
        _raise("REPARSE_POINT_FORBIDDEN", "leaf is a reparse point")

    allowed_by_expectation = {
        "regular-file": {"regular-file"},
        "regular-file-or-missing": {"regular-file", "missing"},
        "directory": {"directory"},
        "directory-or-missing": {"directory", "missing"},
    }
    allowed = allowed_by_expectation.get(expected_leaf)
    if allowed is None:
        _raise("TYPE_MISMATCH", f"unknown expected leaf kind: {expected_leaf!r}")
    if leaf_kind not in allowed:
        _raise("TYPE_MISMATCH", f"leaf kind {leaf_kind!r} not in {sorted(allowed)!r}")

    if intent not in {"inspect", "create", "replace", "delete"}:
        _raise("TYPE_MISMATCH", f"unknown intent: {intent!r}")

    if intent == "create" and leaf_kind != "missing":
        _raise("TYPE_MISMATCH", "create requires a missing leaf")
    if intent in {"replace", "delete"} and leaf_kind != "regular-file":
        _raise("TYPE_MISMATCH", f"{intent} requires a regular-file leaf")

    if intent in {"replace", "delete"} and leaf_link_count is not None and leaf_link_count != 1:
        _raise("HARDLINK_FORBIDDEN", f"linkCount={leaf_link_count}")
