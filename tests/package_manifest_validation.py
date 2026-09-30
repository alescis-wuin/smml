from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from typing import Any


class PackageManifestSemanticError(ValueError):
    pass


_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_COMPARATOR_RE = re.compile(r"^(<=|>=|<|>|=)(.+)$")


def _validate_relative_path(value: str) -> None:
    if not value:
        raise PackageManifestSemanticError("path must not be empty")
    if "\\" in value:
        raise PackageManifestSemanticError(f"backslash is forbidden in path: {value!r}")
    if "\x00" in value:
        raise PackageManifestSemanticError("NUL is forbidden in paths")
    if value.startswith("/"):
        raise PackageManifestSemanticError(f"absolute path is forbidden: {value!r}")
    if len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] == "/":
        raise PackageManifestSemanticError(f"drive-absolute path is forbidden: {value!r}")
    if "//" in value:
        raise PackageManifestSemanticError(f"empty path segment is forbidden: {value!r}")
    parts = PurePosixPath(value).parts
    if any(part in {".", ".."} for part in parts):
        raise PackageManifestSemanticError(f"dot segment is forbidden: {value!r}")


def parse_semver(value: str) -> tuple[int, int, int, tuple[str, ...], str | None]:
    match = _SEMVER_RE.fullmatch(value)
    if not match:
        raise PackageManifestSemanticError(f"invalid SemVer: {value!r}")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    build = match.group(5)
    return major, minor, patch, prerelease, build


def compare_semver_precedence(left: str, right: str) -> int:
    lmaj, lmin, lpatch, lpre, _ = parse_semver(left)
    rmaj, rmin, rpatch, rpre, _ = parse_semver(right)

    lcore = (lmaj, lmin, lpatch)
    rcore = (rmaj, rmin, rpatch)
    if lcore < rcore:
        return -1
    if lcore > rcore:
        return 1

    if not lpre and not rpre:
        return 0
    if not lpre:
        return 1
    if not rpre:
        return -1

    for litem, ritem in zip(lpre, rpre):
        if litem == ritem:
            continue
        lnum = litem.isdigit()
        rnum = ritem.isdigit()
        if lnum and rnum:
            return -1 if int(litem) < int(ritem) else 1
        if lnum != rnum:
            return -1 if lnum else 1
        return -1 if litem < ritem else 1

    if len(lpre) < len(rpre):
        return -1
    if len(lpre) > len(rpre):
        return 1
    return 0


def parse_semver_range(value: str) -> list[tuple[str, str]]:
    if not value or value != value.strip(" "):
        raise PackageManifestSemanticError("SemVer range must not have leading/trailing spaces")
    if any(ch.isspace() and ch != " " for ch in value):
        raise PackageManifestSemanticError("SMML v1 SemVer ranges use ASCII spaces only")
    if value == "*":
        return []

    try:
        parse_semver(value)
    except PackageManifestSemanticError:
        pass
    else:
        return [("=", value)]

    tokens = re.split(r" +", value)
    if not tokens:
        raise PackageManifestSemanticError("SemVer range must not be empty")

    comparators: list[tuple[str, str]] = []
    for token in tokens:
        match = _COMPARATOR_RE.fullmatch(token)
        if not match:
            raise PackageManifestSemanticError(
                f"unsupported SMML v1 SemVer range token: {token!r} in {value!r}"
            )
        operator, version = match.groups()
        parse_semver(version)
        comparators.append((operator, version))
    return comparators


def semver_satisfies(version: str, range_value: str) -> bool:
    parse_semver(version)
    for operator, expected in parse_semver_range(range_value):
        cmp = compare_semver_precedence(version, expected)
        if operator == "=" and cmp != 0:
            return False
        if operator == ">" and cmp <= 0:
            return False
        if operator == ">=" and cmp < 0:
            return False
        if operator == "<" and cmp >= 0:
            return False
        if operator == "<=" and cmp > 0:
            return False
    return True


def capability_key(item: dict[str, Any]) -> str:
    return f"{item['id']}@{item['version']}"


def _validate_unique_by(items: list[dict[str, Any]], key_fn, label: str) -> None:
    seen: set[str] = set()
    for item in items:
        key = str(key_fn(item))
        if key in seen:
            raise PackageManifestSemanticError(f"duplicate {label}: {key!r}")
        seen.add(key)


def validate_package_manifest_semantics(document: dict[str, Any]) -> None:
    package_id = document["id"]
    parse_semver(document["version"])

    dependencies = document["dependencies"]
    _validate_unique_by(dependencies, lambda item: item["id"], "dependency id")
    for dependency in dependencies:
        parse_semver_range(dependency["range"])
        if dependency["id"] == package_id:
            raise PackageManifestSemanticError("package must not depend on itself")

    provides = document["capabilities"]["provides"]
    requires = document["capabilities"]["requires"]
    _validate_unique_by(provides, capability_key, "provided capability")
    _validate_unique_by(requires, capability_key, "required capability")

    package_conflicts = document["conflicts"]["packages"]
    capability_conflicts = document["conflicts"]["capabilities"]
    _validate_unique_by(package_conflicts, lambda item: item["id"], "package conflict id")
    _validate_unique_by(capability_conflicts, capability_key, "capability conflict")
    for conflict in package_conflicts:
        parse_semver_range(conflict["range"])
        if conflict["id"] == package_id:
            raise PackageManifestSemanticError("package must not conflict with itself")

    provided_keys = {capability_key(item) for item in provides}
    conflicting_capability_keys = {capability_key(item) for item in capability_conflicts}
    self_conflicts = sorted(provided_keys & conflicting_capability_keys)
    if self_conflicts:
        raise PackageManifestSemanticError(
            f"package provides and conflicts with the same capability: {self_conflicts[0]!r}"
        )

    load_before = set(document["loadBefore"])
    load_after = set(document["loadAfter"])
    if package_id in load_before or package_id in load_after:
        raise PackageManifestSemanticError("loadBefore/loadAfter must not reference the package itself")
    overlap = sorted(load_before & load_after)
    if overlap:
        raise PackageManifestSemanticError(
            f"package id appears in both loadBefore and loadAfter: {overlap[0]!r}"
        )

    file_by_path: dict[str, dict[str, Any]] = {}
    casefold_paths: dict[str, str] = {}
    for item in document["files"]:
        path = item["path"]
        _validate_relative_path(path)
        if path == "smml.package.json":
            raise PackageManifestSemanticError("smml.package.json must not appear in files inventory")
        folded = path.casefold()
        previous = casefold_paths.get(folded)
        if previous is not None:
            raise PackageManifestSemanticError(
                f"files contains a case-insensitive collision: {previous!r} vs {path!r}"
            )
        casefold_paths[folded] = path
        file_by_path[path] = item

    entrypoints = document.get("entrypoints", {})
    for side, path in entrypoints.items():
        _validate_relative_path(path)
        if path not in file_by_path:
            raise PackageManifestSemanticError(
                f"entrypoint {side!r} references a path absent from files: {path!r}"
            )

    artifacts = document["artifacts"]
    _validate_unique_by(artifacts, lambda item: item["id"], "artifact id")
    artifact_paths: dict[str, str] = {}
    for artifact in artifacts:
        path = artifact["path"]
        _validate_relative_path(path)
        if path not in file_by_path:
            raise PackageManifestSemanticError(
                f"artifact {artifact['id']!r} references a path absent from files: {path!r}"
            )
        folded = path.casefold()
        previous = artifact_paths.get(folded)
        if previous is not None:
            raise PackageManifestSemanticError(
                f"multiple artifacts reference the same path: {previous!r} vs {path!r}"
            )
        artifact_paths[folded] = path


def target_selector_matches(selector: dict[str, Any], game_target: dict[str, Any]) -> bool:
    if selector["steamAppId"] != game_target["steamAppId"]:
        return False

    checks = (
        ("gameVersions", game_target["gameVersion"]),
        ("engineBuilds", game_target["engineBuild"]),
        ("steamBuildIds", game_target["steamBuildId"]),
        ("steamBranches", game_target["steamBranch"]),
        ("canonicalGameFingerprints", game_target["fingerprints"]["canonicalGameFingerprint"]["sha256"]),
        ("hostOs", game_target["platform"]["hostOs"]),
        ("gameOs", game_target["platform"]["gameOs"]),
        ("compatibilityLayers", game_target["platform"]["compatibilityLayer"]["kind"]),
    )
    for selector_field, actual in checks:
        allowed = selector.get(selector_field)
        if allowed is not None and actual not in allowed:
            return False
    return True


def manifest_matches_game_target(document: dict[str, Any], game_target: dict[str, Any]) -> bool:
    return any(
        target_selector_matches(selector, game_target)
        for selector in document["compatibility"]["targets"]
    )


def manifest_digest(raw_manifest_bytes: bytes) -> str:
    return hashlib.sha256(raw_manifest_bytes).hexdigest()


def package_digest(raw_package_bytes: bytes) -> str:
    return hashlib.sha256(raw_package_bytes).hexdigest()
