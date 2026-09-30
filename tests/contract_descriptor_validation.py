from __future__ import annotations

from typing import Any


class ContractDescriptorSemanticError(ValueError):
    pass


def contract_key(document: dict[str, Any]) -> str:
    return f"{document['contractId']}@{document['version']}"


def _artifact_refs(document: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for field in ("payloadSchema", "resultSchema"):
        ref = document[field]
        if ref["kind"] == "artifact":
            refs.append(ref["artifactId"])
    return refs


def validate_contract_descriptor_semantics(
    document: dict[str, Any],
    package_manifest: dict[str, Any] | None = None,
) -> None:
    category = document["category"]
    payload = document["payloadSchema"]
    result = document["resultSchema"]
    error = document["errorPolicy"]

    if category == "transform" and payload != result:
        raise ContractDescriptorSemanticError(
            "transform payloadSchema and resultSchema must be identical in v1"
        )

    if category == "service":
        if result["kind"] == "none" and error["invalidResult"] != "not-applicable":
            raise ContractDescriptorSemanticError(
                "service with no result must use invalidResult=not-applicable"
            )
        if result["kind"] == "artifact" and error["invalidResult"] != "fail-invocation":
            raise ContractDescriptorSemanticError(
                "service with an artifact result must use invalidResult=fail-invocation"
            )

    if package_manifest is not None:
        artifact_ids = {item["id"] for item in package_manifest["artifacts"]}
        for artifact_id in _artifact_refs(document):
            if artifact_id not in artifact_ids:
                raise ContractDescriptorSemanticError(
                    f"schema artifact is not declared by PackageManifest: {artifact_id!r}"
                )


def validate_contract_registry(descriptors: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for descriptor in descriptors:
        key = contract_key(descriptor)
        if key in seen:
            raise ContractDescriptorSemanticError(
                f"duplicate contract definition in resolved registry: {key!r}"
            )
        seen.add(key)


def combine_cancellable(
    policy: str,
    decisions: list[str],
    no_handlers_policy: str,
) -> tuple[str, int]:
    if policy not in {"deny-wins", "first-deny"}:
        raise ContractDescriptorSemanticError(f"invalid cancellable policy: {policy!r}")
    if no_handlers_policy not in {"allow", "deny"}:
        raise ContractDescriptorSemanticError(
            f"invalid cancellable noHandlers policy: {no_handlers_policy!r}"
        )
    for decision in decisions:
        if decision not in {"allow", "deny"}:
            raise ContractDescriptorSemanticError(f"invalid decision: {decision!r}")

    if not decisions:
        return no_handlers_policy, 0

    if policy == "deny-wins":
        return ("deny" if "deny" in decisions else "allow"), len(decisions)

    for index, decision in enumerate(decisions, start=1):
        if decision == "deny":
            return "deny", index
    return "allow", len(decisions)
