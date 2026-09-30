from __future__ import annotations

import copy
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
from package_manifest_validation import validate_package_manifest_semantics  # noqa: E402
from contract_descriptor_validation import (  # noqa: E402
    ContractDescriptorSemanticError,
    combine_cancellable,
    contract_key,
    validate_contract_descriptor_semantics,
    validate_contract_registry,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ContractDescriptorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMAS / "smml.contract-descriptor-1.schema.json")
        cls.validator = Draft202012Validator(cls.schema)
        cls.notification = load_json(EXAMPLES / "contract-descriptor.valid.notification.json")
        cls.cancellable = load_json(EXAMPLES / "contract-descriptor.valid.cancellable.json")
        cls.transform = load_json(EXAMPLES / "contract-descriptor.valid.transform.json")
        cls.query = load_json(EXAMPLES / "contract-descriptor.valid.query.json")
        cls.service = load_json(EXAMPLES / "contract-descriptor.valid.service-no-result.json")
        cls.package_minimal = load_json(EXAMPLES / "package-manifest.valid.minimal.json")
        cls.package_schema = load_json(SCHEMAS / "smml.package-manifest-1.schema.json")
        cls.package_validator = Draft202012Validator(cls.package_schema)

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_valid_fixtures_schema_and_semantics(self):
        for document in (
            self.notification,
            self.cancellable,
            self.transform,
            self.query,
            self.service,
        ):
            with self.subTest(key=contract_key(document)):
                self.validator.validate(document)
                validate_contract_descriptor_semantics(document)

    def test_contract_key_is_id_at_integer_version(self):
        self.assertEqual(contract_key(self.cancellable), "carry.beforeServerDrop@1")

    def test_versions_are_exact_and_distinct(self):
        other = copy.deepcopy(self.cancellable)
        other["version"] = 2
        self.assertNotEqual(contract_key(self.cancellable), contract_key(other))

    def test_cancellable_must_be_server_side(self):
        document = copy.deepcopy(self.cancellable)
        document["side"] = "client"
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_transform_must_be_endomorphic(self):
        document = copy.deepcopy(self.transform)
        document["resultSchema"] = {
            "kind": "artifact",
            "artifactId": "schema.other-context",
        }
        self.validator.validate(document)
        with self.assertRaises(ContractDescriptorSemanticError):
            validate_contract_descriptor_semantics(document)

    def test_service_without_result_requires_not_applicable(self):
        document = copy.deepcopy(self.service)
        document["errorPolicy"]["invalidResult"] = "fail-invocation"
        self.validator.validate(document)
        with self.assertRaises(ContractDescriptorSemanticError):
            validate_contract_descriptor_semantics(document)

    def test_service_with_result_requires_fail_invocation(self):
        document = copy.deepcopy(self.service)
        document["resultSchema"] = {
            "kind": "artifact",
            "artifactId": "schema.storage-save.result",
        }
        document["errorPolicy"]["invalidResult"] = "not-applicable"
        self.validator.validate(document)
        with self.assertRaises(ContractDescriptorSemanticError):
            validate_contract_descriptor_semantics(document)

    def test_package_manifest_can_bind_descriptor_and_schema_artifact(self):
        package = copy.deepcopy(self.package_minimal)
        package["files"] = [
            {"path": "contracts/game.serverCreated.json", "size": 1, "sha256": "0" * 64},
            {"path": "contracts/game.serverCreated.payload.json", "size": 1, "sha256": "1" * 64},
        ]
        package["artifacts"] = [
            {
                "id": "contract.game-server-created",
                "type": "smml.contract-descriptor/1",
                "path": "contracts/game.serverCreated.json",
            },
            {
                "id": "schema.game-server-created.payload",
                "type": "smml.contract-schema/1",
                "path": "contracts/game.serverCreated.payload.json",
            },
        ]
        self.package_validator.validate(package)
        validate_package_manifest_semantics(package)
        validate_contract_descriptor_semantics(self.notification, package)

    def test_artifact_schema_refs_must_exist_in_package_manifest(self):
        package = {
            "artifacts": [
                {
                    "id": "schema.game-server-created.payload",
                    "type": "example.schema/1",
                    "path": "contracts/game-server-created.payload.json",
                }
            ]
        }
        validate_contract_descriptor_semantics(self.notification, package)

        missing = copy.deepcopy(self.notification)
        missing["payloadSchema"]["artifactId"] = "schema.missing"
        with self.assertRaises(ContractDescriptorSemanticError):
            validate_contract_descriptor_semantics(missing, package)

    def test_duplicate_contract_key_rejected_in_registry(self):
        duplicate = copy.deepcopy(self.notification)
        with self.assertRaises(ContractDescriptorSemanticError):
            validate_contract_registry([self.notification, duplicate])

    def test_same_id_different_versions_can_coexist(self):
        v2 = copy.deepcopy(self.notification)
        v2["version"] = 2
        validate_contract_registry([self.notification, v2])

    def test_cancellable_deny_wins_evaluates_all(self):
        decision, evaluated = combine_cancellable(
            "deny-wins", ["allow", "deny", "allow"], "allow"
        )
        self.assertEqual((decision, evaluated), ("deny", 3))

    def test_cancellable_first_deny_short_circuits(self):
        decision, evaluated = combine_cancellable(
            "first-deny", ["allow", "deny", "allow"], "allow"
        )
        self.assertEqual((decision, evaluated), ("deny", 2))

    def test_cancellable_no_handlers_policy_is_explicit(self):
        self.assertEqual(combine_cancellable("first-deny", [], "allow"), ("allow", 0))
        self.assertEqual(combine_cancellable("first-deny", [], "deny"), ("deny", 0))

    def test_machine_readable_vectors(self):
        vectors = load_json(HERE / "contract_descriptor_vectors.json")
        for item in vectors["contractKeys"]:
            with self.subTest(kind="key", contractId=item["contractId"]):
                document = {
                    "contractId": item["contractId"],
                    "version": item["version"],
                }
                self.assertEqual(contract_key(document), item["expected"])

        for item in vectors["cancellable"]:
            with self.subTest(kind="cancellable", policy=item["policy"], decisions=item["decisions"]):
                actual = combine_cancellable(
                    item["policy"], item["decisions"], item["noHandlers"]
                )
                self.assertEqual(
                    actual,
                    (item["expectedDecision"], item["expectedEvaluated"]),
                )


if __name__ == "__main__":
    unittest.main()
