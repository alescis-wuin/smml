from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXAMPLES = ROOT / "examples"
SCHEMAS = ROOT / "schemas"

sys.path.insert(0, str(HERE))
from package_manifest_validation import (  # noqa: E402
    PackageManifestSemanticError,
    compare_semver_precedence,
    manifest_digest,
    manifest_matches_game_target,
    package_digest,
    parse_semver,
    parse_semver_range,
    semver_satisfies,
    target_selector_matches,
    validate_package_manifest_semantics,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class PackageManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMAS / "smml.package-manifest-1.schema.json")
        cls.validator = Draft202012Validator(cls.schema)
        cls.full = load_json(EXAMPLES / "package-manifest.valid.full-example.json")
        cls.minimal = load_json(EXAMPLES / "package-manifest.valid.minimal.json")
        cls.target = load_json(EXAMPLES / "game-target.valid.scrap-mechanic-1.0.6.889-b1.json")

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_full_fixture_schema_and_semantics(self):
        self.validator.validate(self.full)
        validate_package_manifest_semantics(self.full)

    def test_minimal_fixture_schema_and_semantics(self):
        self.validator.validate(self.minimal)
        validate_package_manifest_semantics(self.minimal)

    def test_semver_strict_accepts_prerelease_and_build(self):
        parsed = parse_semver("1.2.3-alpha.1+linux.x86-64")
        self.assertEqual(parsed[:4], (1, 2, 3, ("alpha", "1")))

    def test_semver_strict_rejects_leading_zero(self):
        with self.assertRaises(PackageManifestSemanticError):
            parse_semver("01.2.3")

    def test_semver_build_metadata_does_not_change_precedence(self):
        self.assertEqual(compare_semver_precedence("1.2.3+one", "1.2.3+two"), 0)

    def test_semver_prerelease_is_lower_than_release(self):
        self.assertLess(compare_semver_precedence("1.2.3-rc.1", "1.2.3"), 0)

    def test_semver_numeric_prerelease_is_lower_than_text(self):
        self.assertLess(compare_semver_precedence("1.2.3-1", "1.2.3-alpha"), 0)

    def test_range_wildcard(self):
        self.assertTrue(semver_satisfies("99.0.0-alpha.1", "*"))

    def test_range_exact_ignores_build_metadata_for_precedence(self):
        self.assertTrue(semver_satisfies("1.2.3+local.2", "1.2.3+repo.1"))

    def test_range_comparator_and(self):
        self.assertTrue(semver_satisfies("1.5.0", ">=1.2.3 <2.0.0"))
        self.assertFalse(semver_satisfies("2.0.0", ">=1.2.3 <2.0.0"))

    def test_range_rejects_caret(self):
        with self.assertRaises(PackageManifestSemanticError):
            parse_semver_range("^1.2.3")

    def test_range_rejects_partial_version(self):
        with self.assertRaises(PackageManifestSemanticError):
            parse_semver_range(">=1.2")

    def test_reference_game_target_matches_full_fixture(self):
        self.assertTrue(manifest_matches_game_target(self.full, self.target))

    def test_target_selector_is_and(self):
        selector = copy.deepcopy(self.full["compatibility"]["targets"][0])
        selector["engineBuilds"] = [888]
        self.assertFalse(target_selector_matches(selector, self.target))

    def test_target_selectors_are_or(self):
        document = copy.deepcopy(self.full)
        wrong = copy.deepcopy(document["compatibility"]["targets"][0])
        wrong["steamBuildIds"] = ["1"]
        broad = {"steamAppId": 387990}
        document["compatibility"]["targets"] = [wrong, broad]
        self.assertTrue(manifest_matches_game_target(document, self.target))

    def test_game_version_is_exact_opaque_match(self):
        selector = {"steamAppId": 387990, "gameVersions": ["1.0.60"]}
        self.assertFalse(target_selector_matches(selector, self.target))

    def test_self_dependency_rejected(self):
        document = copy.deepcopy(self.minimal)
        document["dependencies"] = [{"id": document["id"], "range": "*", "kind": "hard"}]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_inventory_case_collision_rejected(self):
        document = copy.deepcopy(self.minimal)
        document["files"] = [
            {"path": "Runtime/A.lua", "size": 1, "sha256": "0" * 64},
            {"path": "runtime/a.lua", "size": 1, "sha256": "1" * 64},
        ]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_manifest_must_not_hash_itself_in_inventory(self):
        document = copy.deepcopy(self.minimal)
        document["files"] = [
            {"path": "smml.package.json", "size": 1, "sha256": "0" * 64}
        ]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_entrypoint_must_be_in_inventory(self):
        document = copy.deepcopy(self.minimal)
        document["entrypoints"] = {"server": "runtime/server.lua"}
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_artifact_must_be_in_inventory(self):
        document = copy.deepcopy(self.minimal)
        document["artifacts"] = [
            {"id": "contract", "type": "smml.contract-descriptor/1", "path": "contracts/a.json"}
        ]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_provided_capability_must_not_self_conflict(self):
        document = copy.deepcopy(self.minimal)
        cap = {"id": "smml.storage", "version": 1}
        document["capabilities"]["provides"] = [cap]
        document["conflicts"]["capabilities"] = [copy.deepcopy(cap)]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_order_constraints_must_be_disjoint(self):
        document = copy.deepcopy(self.minimal)
        document["loadBefore"] = ["com.example.other"]
        document["loadAfter"] = ["com.example.other"]
        with self.assertRaises(PackageManifestSemanticError):
            validate_package_manifest_semantics(document)

    def test_manifest_digest_is_over_exact_bytes(self):
        left = b'{"a":1}\n'
        right = b'{ "a": 1 }\n'
        self.assertNotEqual(manifest_digest(left), manifest_digest(right))
        self.assertEqual(manifest_digest(left), hashlib.sha256(left).hexdigest())

    def test_package_digest_is_over_exact_bytes(self):
        raw = b"SMML package bytes\x00\x01"
        self.assertEqual(package_digest(raw), hashlib.sha256(raw).hexdigest())

    def test_same_logical_version_can_have_different_package_digests(self):
        self.assertNotEqual(package_digest(b"archive-a"), package_digest(b"archive-b"))

    def test_machine_readable_vectors(self):
        vectors = load_json(HERE / "package_manifest_vectors.json")
        for item in vectors["semverRanges"]:
            with self.subTest(kind="semver", version=item["version"], range=item["range"]):
                self.assertEqual(semver_satisfies(item["version"], item["range"]), item["matches"])
        for value in vectors["invalidRanges"]:
            with self.subTest(kind="invalidRange", range=value):
                with self.assertRaises(PackageManifestSemanticError):
                    parse_semver_range(value)
        for item in vectors["targetSelectors"]:
            with self.subTest(kind="target", name=item["name"]):
                self.assertEqual(
                    target_selector_matches(item["selector"], self.target),
                    item["matchesReference"],
                )


if __name__ == "__main__":
    unittest.main()
