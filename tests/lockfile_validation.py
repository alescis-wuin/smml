from __future__ import annotations

import json
from typing import Any, Mapping

from package_manifest_validation import (
    PackageManifestSemanticError,
    capability_key,
    parse_semver,
    parse_semver_range,
    semver_satisfies,
)
from profile_validation import profile_digest


class LockfileSemanticError(ValueError):
    pass


def _semver(value: str) -> None:
    try:
        parse_semver(value)
    except PackageManifestSemanticError as exc:
        raise LockfileSemanticError(str(exc)) from exc


def _range(value: str) -> None:
    try:
        parse_semver_range(value)
    except PackageManifestSemanticError as exc:
        raise LockfileSemanticError(str(exc)) from exc


def _target_selector_matches_stable(selector: dict[str, Any], target: dict[str, Any]) -> bool:
    if selector["steamAppId"] != target["steamAppId"]:
        return False
    checks = (
        ("gameVersions", target["gameVersion"]),
        ("engineBuilds", target["engineBuild"]),
        ("steamBuildIds", target["steamBuildId"]),
        ("steamBranches", target["steamBranch"]),
        ("canonicalGameFingerprints", target["canonicalGameFingerprint"]),
        ("hostOs", target["platform"]["hostOs"]),
        ("gameOs", target["platform"]["gameOs"]),
        ("compatibilityLayers", target["platform"]["compatibilityLayer"]),
    )
    for field, actual in checks:
        allowed = selector.get(field)
        if allowed is not None and actual not in allowed:
            return False
    return True


def _edge_detail_key(edge: dict[str, Any]) -> str:
    return json.dumps(edge["detail"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def edge_sort_key(edge: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (edge["from"], edge["to"], edge["reason"], edge["declaredBy"], _edge_detail_key(edge))


def validate_lockfile_semantics(document: dict[str, Any]) -> None:
    _semver(document["platformVersion"])

    packages = document["packages"]
    package_ids = [p["id"] for p in packages]
    if len(package_ids) != len(set(package_ids)):
        raise LockfileSemanticError("duplicate package id in lockfile")
    if package_ids != sorted(package_ids):
        raise LockfileSemanticError("packages must be sorted by id")

    package_by_id: dict[str, dict[str, Any]] = {}
    for package in packages:
        _semver(package["version"])
        package_by_id[package["id"]] = package

    artifacts = document["artifacts"]
    artifact_keys = [(a["packageId"], a["artifactId"]) for a in artifacts]
    if len(artifact_keys) != len(set(artifact_keys)):
        raise LockfileSemanticError("duplicate artifact key in lockfile")
    if artifact_keys != sorted(artifact_keys):
        raise LockfileSemanticError("artifacts must be sorted by packageId, artifactId")
    artifact_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for artifact in artifacts:
        if artifact["packageId"] not in package_by_id:
            raise LockfileSemanticError(
                f"artifact references unknown package: {artifact['packageId']!r}"
            )
        artifact_by_key[(artifact["packageId"], artifact["artifactId"])] = artifact

    components = document["components"]
    hook = components["hookPack"]
    hook_key = (hook["packageId"], hook["artifactId"])
    hook_artifact = artifact_by_key.get(hook_key)
    if hook_artifact is None:
        raise LockfileSemanticError("hookPack component references an unknown artifact")
    if hook_artifact["type"] != "smml.hook-pack-manifest/1":
        raise LockfileSemanticError("hookPack component must reference smml.hook-pack-manifest/1")
    for role in ("api", "sdk"):
        package_id = components[role]["packageId"]
        if package_id not in package_by_id:
            raise LockfileSemanticError(f"{role} component references unknown package: {package_id!r}")

    roots = document["roots"]
    root_ids = [r["id"] for r in roots]
    if len(root_ids) != len(set(root_ids)):
        raise LockfileSemanticError("duplicate root package")
    if root_ids != sorted(root_ids):
        raise LockfileSemanticError("roots must be sorted by id")
    for root in roots:
        package = package_by_id.get(root["id"])
        if package is None:
            raise LockfileSemanticError(f"root references unknown package: {root['id']!r}")
        _range(root["requestedRange"])
        _semver(root["resolvedVersion"])
        if package["version"] != root["resolvedVersion"]:
            raise LockfileSemanticError(
                f"root resolvedVersion does not match package record: {root['id']!r}"
            )
        if not semver_satisfies(root["resolvedVersion"], root["requestedRange"]):
            raise LockfileSemanticError(
                f"root resolvedVersion does not satisfy requestedRange: {root['id']!r}"
            )

    load_order = document["loadOrder"]
    if len(load_order) != len(set(load_order)):
        raise LockfileSemanticError("loadOrder contains duplicate package id")
    if set(load_order) != set(package_ids) or len(load_order) != len(package_ids):
        raise LockfileSemanticError("loadOrder must contain every package exactly once")
    position = {package_id: i for i, package_id in enumerate(load_order)}

    capability_records = document["capabilityProviders"]
    cap_keys = [capability_key(c) for c in capability_records]
    if len(cap_keys) != len(set(cap_keys)):
        raise LockfileSemanticError("duplicate capability provider record")
    if [(c["id"], c["version"]) for c in capability_records] != sorted(
        (c["id"], c["version"]) for c in capability_records
    ):
        raise LockfileSemanticError("capabilityProviders must be sorted by id, version")
    capability_by_key: dict[str, dict[str, Any]] = {}
    for cap in capability_records:
        providers = cap["providers"]
        if providers != sorted(providers):
            raise LockfileSemanticError(
                f"providers must be sorted for capability {capability_key(cap)!r}"
            )
        if len(providers) != len(set(providers)):
            raise LockfileSemanticError(
                f"duplicate provider for capability {capability_key(cap)!r}"
            )
        for provider in providers:
            if provider not in package_by_id:
                raise LockfileSemanticError(
                    f"capability provider references unknown package: {provider!r}"
                )
        capability_by_key[capability_key(cap)] = cap

    edges = document["edges"]
    if [edge_sort_key(e) for e in edges] != sorted(edge_sort_key(e) for e in edges):
        raise LockfileSemanticError("edges must be stored in canonical sort order")
    seen_edges: set[tuple[str, str, str, str, str]] = set()
    for edge in edges:
        key = edge_sort_key(edge)
        if key in seen_edges:
            raise LockfileSemanticError("duplicate graph edge")
        seen_edges.add(key)

        source = edge["from"]
        target = edge["to"]
        declared_by = edge["declaredBy"]
        if source not in package_by_id or target not in package_by_id or declared_by not in package_by_id:
            raise LockfileSemanticError("edge references unknown package")
        if source == target:
            raise LockfileSemanticError("self-edge is forbidden")
        if position[source] >= position[target]:
            raise LockfileSemanticError(
                f"edge contradicts loadOrder: {source!r} must precede {target!r}"
            )

        reason = edge["reason"]
        detail = edge["detail"]
        if reason in {"hardDependency", "softDependency"}:
            if declared_by != target:
                raise LockfileSemanticError(f"{reason} must be declared by the consumer (to)")
            _range(detail["range"])
            if not semver_satisfies(package_by_id[source]["version"], detail["range"]):
                raise LockfileSemanticError(
                    f"locked dependency version does not satisfy edge range: {source!r}"
                )
        elif reason == "capability":
            if declared_by != target:
                raise LockfileSemanticError("capability edge must be declared by the consumer (to)")
            cap_key = f"{detail['capabilityId']}@{detail['capabilityVersion']}"
            cap = capability_by_key.get(cap_key)
            if cap is None or source not in cap["providers"]:
                raise LockfileSemanticError(
                    f"capability edge provider is not locked for {cap_key!r}"
                )
        elif reason == "loadBefore":
            if declared_by != source:
                raise LockfileSemanticError("loadBefore must be declared by from")
        elif reason == "loadAfter":
            if declared_by != target:
                raise LockfileSemanticError("loadAfter must be declared by to")
        else:  # schema should prevent this
            raise LockfileSemanticError(f"unknown edge reason: {reason!r}")


def validate_lockfile_against_profile(
    lockfile: dict[str, Any],
    profile: dict[str, Any],
    raw_profile_bytes: bytes,
) -> None:
    if lockfile["profile"]["id"] != profile["id"]:
        raise LockfileSemanticError("lockfile profile id does not match source profile")
    expected_digest = profile_digest(raw_profile_bytes)
    if lockfile["profile"]["sha256"] != expected_digest:
        raise LockfileSemanticError("lockfile profile digest does not match source bytes")
    if not _target_selector_matches_stable(profile["target"], lockfile["target"]):
        raise LockfileSemanticError("lockfile target does not satisfy source profile")

    expected_roots = {item["id"]: item["range"] for item in profile["packages"]}
    actual_roots = {item["id"]: item["requestedRange"] for item in lockfile["roots"]}
    if expected_roots != actual_roots:
        raise LockfileSemanticError("lockfile roots do not match source profile package requests")

    locked_caps = {
        capability_key(item): item["providers"] for item in lockfile["capabilityProviders"]
    }
    for selection in profile["policies"]["capabilityProviders"]:
        key = capability_key(selection)
        if locked_caps.get(key) != sorted(selection["providers"]):
            raise LockfileSemanticError(
                f"lockfile does not honor explicit profile providers for {key!r}"
            )


def validate_lockfile_against_manifests(
    lockfile: dict[str, Any],
    package_manifests: Mapping[str, dict[str, Any]],
) -> None:
    packages = {item["id"]: item for item in lockfile["packages"]}
    caps = {
        capability_key(item): set(item["providers"])
        for item in lockfile["capabilityProviders"]
    }

    for package_id, record in packages.items():
        manifest = package_manifests.get(package_id)
        if manifest is None:
            raise LockfileSemanticError(f"missing manifest for locked package: {package_id!r}")
        if manifest["id"] != package_id or manifest["version"] != record["version"]:
            raise LockfileSemanticError(f"locked package identity/version mismatches manifest: {package_id!r}")
        if manifest["persistenceImpact"] != record["persistenceImpact"]:
            raise LockfileSemanticError(f"locked persistenceImpact mismatches manifest: {package_id!r}")

    for cap_key, providers in caps.items():
        cap_id, version_text = cap_key.rsplit("@", 1)
        version = int(version_text)
        for provider_id in providers:
            manifest = package_manifests[provider_id]
            provided = {capability_key(item) for item in manifest["capabilities"]["provides"]}
            if cap_key not in provided:
                raise LockfileSemanticError(
                    f"locked provider {provider_id!r} does not provide {cap_key!r}"
                )

    for edge in lockfile["edges"]:
        source, target, reason = edge["from"], edge["to"], edge["reason"]
        declaring = package_manifests[edge["declaredBy"]]
        if reason in {"hardDependency", "softDependency"}:
            expected_kind = "hard" if reason == "hardDependency" else "soft"
            matches = [
                dep for dep in declaring["dependencies"]
                if dep["id"] == source and dep["kind"] == expected_kind and dep["range"] == edge["detail"]["range"]
            ]
            if not matches:
                raise LockfileSemanticError(f"{reason} edge is not declared by manifest")
        elif reason == "capability":
            cap_key = f"{edge['detail']['capabilityId']}@{edge['detail']['capabilityVersion']}"
            required = {capability_key(item) for item in declaring["capabilities"]["requires"]}
            if cap_key not in required:
                raise LockfileSemanticError("capability edge consumer does not require capability")
            provided = {capability_key(item) for item in package_manifests[source]["capabilities"]["provides"]}
            if cap_key not in provided:
                raise LockfileSemanticError("capability edge source does not provide capability")
        elif reason == "loadBefore":
            if target not in declaring["loadBefore"]:
                raise LockfileSemanticError("loadBefore edge is not declared by manifest")
        elif reason == "loadAfter":
            if source not in declaring["loadAfter"]:
                raise LockfileSemanticError("loadAfter edge is not declared by manifest")
