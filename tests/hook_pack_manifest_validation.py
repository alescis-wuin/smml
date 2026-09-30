from __future__ import annotations

import json
from typing import Any

from path_policy_validation import PathPolicyError, portable_collision_key, validate_logical_path


class HookPackManifestSemanticError(ValueError):
    pass


def _validate_relative_path(value: str) -> None:
    try:
        validate_logical_path(value)
    except PathPolicyError as exc:
        raise HookPackManifestSemanticError(str(exc)) from exc


def _unique(items, key_fn, label: str) -> None:
    seen: set[str] = set()
    for item in items:
        key = str(key_fn(item))
        if key in seen:
            raise HookPackManifestSemanticError(f"duplicate {label}: {key!r}")
        seen.add(key)


def _target_key(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _contract_key(contract: dict[str, Any]) -> str:
    return f"{contract['contractId']}@{contract['version']}"


def _transformation_artifact_ids(hook: dict[str, Any]) -> set[str]:
    return {item["contentArtifactId"] for item in hook["transformations"]}


def validate_hook_pack_manifest_semantics(
    document: dict[str, Any],
    package_manifest: dict[str, Any] | None = None,
    contract_descriptors: dict[str, dict[str, Any]] | None = None,
) -> None:
    targets = document["targets"]
    _unique(targets, _target_key, "target selector")

    target_files = document["targetFiles"]
    _unique(target_files, lambda item: item["id"], "target file id")
    target_file_by_id = {item["id"]: item for item in target_files}
    target_path_casefold: dict[str, str] = {}
    for item in target_files:
        _validate_relative_path(item["path"])
        folded = portable_collision_key(item["path"])
        previous = target_path_casefold.get(folded)
        if previous is not None:
            raise HookPackManifestSemanticError(
                f"target file path collision: {previous!r} vs {item['path']!r}"
            )
        target_path_casefold[folded] = item["path"]

    adapters = document["adapters"]
    _unique(adapters, lambda item: item["id"], "adapter id")
    adapter_by_id = {item["id"]: item for item in adapters}

    hooks = document["hooks"]
    _unique(hooks, lambda item: item["hookId"], "hook id")
    hook_sequences = [item["sequence"] for item in hooks]
    expected_hook_sequences = list(range(len(hooks)))
    if hook_sequences != expected_hook_sequences:
        raise HookPackManifestSemanticError(
            f"hook sequence must be contiguous 0..N-1; got {hook_sequences!r}"
        )

    marker_owner: dict[str, str] = {}
    referenced_descriptor_artifacts: set[str] = set()
    referenced_fragment_artifacts: set[str] = set()

    for hook in hooks:
        hook_id = hook["hookId"]
        if hook["targetFileId"] not in target_file_by_id:
            raise HookPackManifestSemanticError(
                f"hook {hook_id!r} references unknown targetFileId {hook['targetFileId']!r}"
            )
        if hook["adapterId"] not in adapter_by_id:
            raise HookPackManifestSemanticError(
                f"hook {hook_id!r} references unknown adapterId {hook['adapterId']!r}"
            )

        anchors = hook["anchors"]
        _unique(anchors, lambda item: item["id"], f"anchor id in hook {hook_id}")
        anchor_by_id = {item["id"]: item for item in anchors}

        transformations = hook["transformations"]
        actual_sequences = [item["sequence"] for item in transformations]
        expected_sequences = list(range(len(transformations)))
        if actual_sequences != expected_sequences:
            raise HookPackManifestSemanticError(
                f"hook {hook_id!r} transformation sequence must be contiguous 0..N-1; "
                f"got {actual_sequences!r}"
            )

        for transformation in transformations:
            kind = transformation["kind"]
            if kind in {"insert-before", "insert-after", "wrap-prefix", "wrap-postfix", "conditional-short-circuit"}:
                anchor_id = transformation["anchorId"]
                anchor = anchor_by_id.get(anchor_id)
                if anchor is None:
                    raise HookPackManifestSemanticError(
                        f"hook {hook_id!r} transformation references unknown anchor {anchor_id!r}"
                    )
                if kind in {"wrap-prefix", "wrap-postfix", "conditional-short-circuit"} and anchor["kind"] != "lua-function":
                    raise HookPackManifestSemanticError(
                        f"hook {hook_id!r} transformation {kind!r} requires a lua-function anchor"
                    )
            elif kind == "replace-region":
                start_id = transformation["startAnchorId"]
                end_id = transformation["endAnchorId"]
                if start_id == end_id:
                    raise HookPackManifestSemanticError(
                        f"hook {hook_id!r} replace-region requires distinct start/end anchors"
                    )
                if start_id not in anchor_by_id or end_id not in anchor_by_id:
                    raise HookPackManifestSemanticError(
                        f"hook {hook_id!r} replace-region references an unknown anchor"
                    )
            else:
                raise HookPackManifestSemanticError(f"unsupported transformation kind: {kind!r}")

        referenced_descriptor_artifacts.add(hook["contract"]["descriptorArtifactId"])
        referenced_fragment_artifacts.update(_transformation_artifact_ids(hook))

        begin_marker = hook["verification"]["beginMarker"]
        end_marker = hook["verification"]["endMarker"]
        if begin_marker == end_marker:
            raise HookPackManifestSemanticError(
                f"hook {hook_id!r} begin/end markers must be distinct"
            )
        for marker in (begin_marker, end_marker):
            previous = marker_owner.get(marker)
            if previous is not None:
                raise HookPackManifestSemanticError(
                    f"verification marker is reused by hooks {previous!r} and {hook_id!r}: {marker!r}"
                )
            marker_owner[marker] = hook_id

    cache = document["cacheConsequences"]
    _unique(cache, lambda item: item["id"], "cache consequence id")
    cache_path_casefold: dict[str, str] = {}
    for item in cache:
        path = item["path"]
        _validate_relative_path(path)
        folded = portable_collision_key(path)
        previous = cache_path_casefold.get(folded)
        if previous is not None:
            raise HookPackManifestSemanticError(
                f"cache path collision: {previous!r} vs {path!r}"
            )
        if folded in target_path_casefold:
            raise HookPackManifestSemanticError(
                f"cache consequence path must not also be a target file: {path!r}"
            )
        cache_path_casefold[folded] = path

    if package_manifest is not None:
        artifacts = {item["id"]: item for item in package_manifest["artifacts"]}

        def require_type(artifact_id: str, expected_type: str, label: str) -> None:
            artifact = artifacts.get(artifact_id)
            if artifact is None:
                raise HookPackManifestSemanticError(
                    f"{label} artifact is not declared by PackageManifest: {artifact_id!r}"
                )
            if artifact["type"] != expected_type:
                raise HookPackManifestSemanticError(
                    f"{label} artifact {artifact_id!r} must have type {expected_type!r}, "
                    f"got {artifact['type']!r}"
                )

        for adapter in adapters:
            require_type(adapter["artifactId"], "smml.runtime-adapter/1", "adapter")
        for artifact_id in referenced_descriptor_artifacts:
            require_type(artifact_id, "smml.contract-descriptor/1", "contract descriptor")
        for artifact_id in referenced_fragment_artifacts:
            require_type(artifact_id, "smml.hook-patch-fragment/1", "patch fragment")

    if contract_descriptors is not None:
        for hook in hooks:
            artifact_id = hook["contract"]["descriptorArtifactId"]
            descriptor = contract_descriptors.get(artifact_id)
            if descriptor is None:
                raise HookPackManifestSemanticError(
                    f"ContractDescriptor content is unavailable for artifact {artifact_id!r}"
                )
            expected = _contract_key(hook["contract"])
            actual = f"{descriptor['contractId']}@{descriptor['version']}"
            if actual != expected:
                raise HookPackManifestSemanticError(
                    f"hook {hook['hookId']!r} references {expected!r} but descriptor defines {actual!r}"
                )


def target_selector_matches(selector: dict[str, Any], game_target: dict[str, Any]) -> bool:
    required_pairs = (
        ("steamAppId", game_target["steamAppId"]),
        ("gameVersion", game_target["gameVersion"]),
        ("engineBuild", game_target["engineBuild"]),
        ("steamBuildId", game_target["steamBuildId"]),
        ("steamBranch", game_target["steamBranch"]),
        ("canonicalGameFingerprint", game_target["fingerprints"]["canonicalGameFingerprint"]["sha256"]),
    )
    if any(selector[name] != actual for name, actual in required_pairs):
        return False

    optional_pairs = (
        ("hostOs", game_target["platform"]["hostOs"]),
        ("gameOs", game_target["platform"]["gameOs"]),
        ("compatibilityLayer", game_target["platform"]["compatibilityLayer"]["kind"]),
    )
    return all(name not in selector or selector[name] == actual for name, actual in optional_pairs)


def hook_pack_matches_game_target(document: dict[str, Any], game_target: dict[str, Any]) -> bool:
    return any(target_selector_matches(selector, game_target) for selector in document["targets"])


def validate_baseline_preconditions(
    document: dict[str, Any],
    observed: dict[str, dict[str, str]],
) -> None:
    for target in document["targetFiles"]:
        path = target["path"]
        actual = observed.get(path)
        if actual is None:
            raise HookPackManifestSemanticError(f"target file is missing: {path!r}")
        if actual.get("kind") != "regular-file":
            raise HookPackManifestSemanticError(
                f"target file is not a regular file: {path!r} ({actual.get('kind')!r})"
            )
        if actual.get("sha256") not in target["acceptedBaselineSha256"]:
            raise HookPackManifestSemanticError(
                f"target file baseline hash is unsupported: {path!r} ({actual.get('sha256')!r})"
            )


def to_logical_text(text: str) -> str:
    if "\r" in text.replace("\r\n", ""):
        raise HookPackManifestSemanticError("bare CR line ending is unsupported")
    has_crlf = "\r\n" in text
    has_lf = "\n" in text.replace("\r\n", "")
    if has_crlf and has_lf:
        raise HookPackManifestSemanticError("mixed LF/CRLF line endings are unsupported")
    return text.replace("\r\n", "\n")


def validate_exact_text_anchors(hook: dict[str, Any], baseline_text: str) -> None:
    logical = to_logical_text(baseline_text)
    for anchor in hook["anchors"]:
        if anchor["kind"] != "exact-text":
            continue
        count = logical.count(anchor["text"])
        if count != 1:
            raise HookPackManifestSemanticError(
                f"hook {hook['hookId']!r} anchor {anchor['id']!r} expected exactly one match, got {count}"
            )
