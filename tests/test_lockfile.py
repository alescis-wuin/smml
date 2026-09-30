from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXAMPLES = ROOT / "examples"
SCHEMAS = ROOT / "schemas"
sys.path.insert(0, str(HERE))

from lockfile_validation import (  # noqa: E402
    LockfileSemanticError,
    edge_sort_key,
    validate_lockfile_against_manifests,
    validate_lockfile_against_profile,
    validate_lockfile_semantics,
)
from package_manifest_validation import validate_package_manifest_semantics  # noqa: E402
from profile_validation import validate_profile_semantics  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class LockfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMAS / "smml.lockfile-1.schema.json")
        cls.validator = Draft202012Validator(cls.schema)
        cls.full = load_json(EXAMPLES / "lockfile.valid.full-example.json")
        cls.resolved = load_json(EXAMPLES / "lockfile.valid.resolved-only.json")
        cls.profile_path = EXAMPLES / "profile.valid.full-example.json"
        cls.profile = load_json(cls.profile_path)

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_full_fixture_schema_and_semantics(self):
        self.validator.validate(self.full)
        validate_lockfile_semantics(self.full)

    def test_resolved_only_lockfile_is_valid_before_content_finalization(self):
        self.validator.validate(self.resolved)
        validate_lockfile_semantics(self.resolved)
        self.assertNotIn("finalContentFingerprint", self.resolved)

    def test_packages_are_canonically_sorted(self):
        self.assertEqual(
            [p["id"] for p in self.full["packages"]],
            sorted(p["id"] for p in self.full["packages"]),
        )

    def test_load_order_contains_every_locked_package(self):
        self.assertEqual(
            set(self.full["loadOrder"]),
            {p["id"] for p in self.full["packages"]},
        )

    def test_every_edge_respects_load_order(self):
        pos = {p: i for i, p in enumerate(self.full["loadOrder"])}
        for edge in self.full["edges"]:
            self.assertLess(pos[edge["from"]], pos[edge["to"]])

    def test_edge_order_is_canonical(self):
        keys = [edge_sort_key(edge) for edge in self.full["edges"]]
        self.assertEqual(keys, sorted(keys))

    def test_edge_contradicting_load_order_is_rejected(self):
        doc = copy.deepcopy(self.full)
        doc["loadOrder"] = [
            "com.example.pallet64",
            "com.example.foundation",
            "org.smml.api",
            "org.smml.hooks.scrap-mechanic",
            "org.smml.sdk",
        ]
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_root_version_must_match_package_record(self):
        doc = copy.deepcopy(self.full)
        doc["roots"][0]["resolvedVersion"] = "1.5.0"
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_dependency_edge_range_must_match_locked_version(self):
        doc = copy.deepcopy(self.full)
        doc["packages"][0]["version"] = "2.1.0"
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_capability_edge_must_use_locked_provider(self):
        doc = copy.deepcopy(self.full)
        doc["edges"][1]["detail"]["capabilityId"] = "smml.storage"
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_hookpack_component_must_reference_hookpack_artifact(self):
        doc = copy.deepcopy(self.full)
        doc["artifacts"][0]["type"] = "smml.contract-descriptor/1"
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_unknown_component_package_is_rejected(self):
        doc = copy.deepcopy(self.full)
        doc["components"]["sdk"]["packageId"] = "org.smml.missing"
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_semantics(doc)

    def test_timestamp_is_forbidden_by_schema(self):
        doc = copy.deepcopy(self.full)
        doc["generatedAt"] = "2026-09-29T20:00:00+02:00"
        with self.assertRaises(ValidationError):
            self.validator.validate(doc)

    def test_cross_validation_with_profile_passes(self):
        validate_profile_semantics(self.profile)
        validate_lockfile_against_profile(self.full, self.profile, self.profile_path.read_bytes())

    def test_cross_validation_rejects_wrong_profile_digest(self):
        doc = copy.deepcopy(self.full)
        doc["profile"]["sha256"] = "0" * 64
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_profile(doc, self.profile, self.profile_path.read_bytes())

    def test_cross_validation_rejects_wrong_roots(self):
        doc = copy.deepcopy(self.full)
        doc["roots"] = []
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_profile(doc, self.profile, self.profile_path.read_bytes())

    def test_cross_validation_rejects_provider_override_drift(self):
        doc = copy.deepcopy(self.full)
        doc["capabilityProviders"][0]["providers"] = ["org.smml.sdk"]
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_profile(doc, self.profile, self.profile_path.read_bytes())

    def test_cross_validation_rejects_target_drift(self):
        doc = copy.deepcopy(self.full)
        doc["target"]["engineBuild"] = 888
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_profile(doc, self.profile, self.profile_path.read_bytes())

    def test_against_manifests_passes(self):
        manifests = self._reference_manifests()
        for manifest in manifests.values():
            validate_package_manifest_semantics(manifest)
        validate_lockfile_against_manifests(self.full, manifests)

    def test_against_manifests_rejects_false_capability_provider(self):
        manifests = self._reference_manifests()
        manifests["org.smml.api"]["capabilities"]["provides"] = []
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_manifests(self.full, manifests)

    def test_against_manifests_rejects_undeclared_dependency_edge(self):
        manifests = self._reference_manifests()
        manifests["com.example.pallet64"]["dependencies"] = []
        with self.assertRaises(LockfileSemanticError):
            validate_lockfile_against_manifests(self.full, manifests)

    @staticmethod
    def _base_manifest(package_id: str, version: str, persistence: str):
        return {
            "schema":"smml.package-manifest/1",
            "id":package_id,
            "name":package_id,
            "version":version,
            "authors":["SMML test"],
            "compatibility":{"targets":[{"steamAppId":387990}]},
            "dependencies":[],
            "capabilities":{"provides":[],"requires":[]},
            "conflicts":{"packages":[],"capabilities":[]},
            "loadBefore":[],"loadAfter":[],
            "persistenceImpact":persistence,
            "artifacts":[],"files":[]
        }

    @classmethod
    def _reference_manifests(cls):
        f=cls._base_manifest("com.example.foundation","1.2.0","runtimeState")
        p=cls._base_manifest("com.example.pallet64","1.4.0","worldContent")
        p["dependencies"]=[{"id":"com.example.foundation","range":">=1.2.0 <2.0.0","kind":"hard"}]
        p["capabilities"]["requires"]=[{"id":"smml.api","version":1,"cardinality":"exactlyOne"}]
        api=cls._base_manifest("org.smml.api","1.0.0","runtimeState")
        api["capabilities"]["provides"]=[{"id":"smml.api","version":1}]
        hp=cls._base_manifest("org.smml.hooks.scrap-mechanic","1.0.0","runtimeState")
        hp["files"]=[{"path":"hookpacks/build-889.json","size":1,"sha256":"b"*64}]
        hp["artifacts"]=[{"id":"hookpack.build-889","type":"smml.hook-pack-manifest/1","path":"hookpacks/build-889.json"}]
        sdk=cls._base_manifest("org.smml.sdk","1.0.0","runtimeState")
        return {m["id"]:m for m in [f,p,api,hp,sdk]}


if __name__ == "__main__":
    unittest.main()
