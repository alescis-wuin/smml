from __future__ import annotations

from typing import Any

from hashing_validation import sha256_bytes
from package_manifest_validation import (
    PackageManifestSemanticError,
    capability_key,
    parse_semver_range,
    target_selector_matches,
)


class ProfileSemanticError(ValueError):
    pass


def _translate_error(exc: Exception) -> ProfileSemanticError:
    return ProfileSemanticError(str(exc))


def validate_profile_semantics(document: dict[str, Any]) -> None:
    seen_packages: set[str] = set()
    for request in document["packages"]:
        package_id = request["id"]
        if package_id in seen_packages:
            raise ProfileSemanticError(f"duplicate package request: {package_id!r}")
        seen_packages.add(package_id)
        try:
            parse_semver_range(request["range"])
        except PackageManifestSemanticError as exc:
            raise _translate_error(exc) from exc

    seen_caps: set[str] = set()
    for selection in document["policies"]["capabilityProviders"]:
        key = capability_key(selection)
        if key in seen_caps:
            raise ProfileSemanticError(f"duplicate capability provider selection: {key!r}")
        seen_caps.add(key)
        providers = selection["providers"]
        if len(providers) != len(set(providers)):
            raise ProfileSemanticError(f"duplicate provider package in selection: {key!r}")


def profile_matches_game_target(document: dict[str, Any], game_target: dict[str, Any]) -> bool:
    return target_selector_matches(document["target"], game_target)


def profile_digest(raw_profile_bytes: bytes) -> str:
    return sha256_bytes(raw_profile_bytes)
