from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from validation import (  # noqa: E402
    SemanticValidationError,
    apply_canonical_policy,
    content_tree_fingerprint,
    validate_policy_semantics,
    validate_semantics,
)


class GameTargetIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (ROOT / "schemas" / "smml.game-target-1.schema.json").read_text(encoding="utf-8")
        )
        cls.validator = Draft202012Validator(cls.schema)
        cls.policy_schema = json.loads((ROOT / 'schemas' / 'smml.canonical-game-policy-1.schema.json').read_text(encoding='utf-8'))
        cls.policy_validator = Draft202012Validator(cls.policy_schema)
        cls.valid = json.loads(
            (
                ROOT
                / "examples"
                / "game-target.valid.scrap-mechanic-1.0.6.889-b1.json"
            ).read_text(encoding="utf-8")
        )
        cls.policy = json.loads(
            (ROOT / "policies" / "smml.canonical-game-policy-1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_schemas_are_well_formed(self):
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator.check_schema(self.policy_schema)

    def test_reference_example_is_valid(self):
        self.validator.validate(self.valid)
        validate_semantics(self.valid)

    def test_reference_values_match_gp0_handoff(self):
        self.assertEqual(self.valid["steamAppId"], 387990)
        self.assertEqual(self.valid["gameVersion"], "1.0.6")
        self.assertEqual(self.valid["engineBuild"], 889)
        self.assertEqual(self.valid["steamBuildId"], "25442087")
        self.assertEqual(
            self.valid["fingerprints"]["installationExactFingerprint"]["sha256"],
            "9d5e06e5da64485218f8f9154097c1638719166c3e9d004adac77d01c2863ab4",
        )
        self.assertEqual(
            self.valid["fingerprints"]["canonicalGameFingerprint"]["sha256"],
            "6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964",
        )

    def test_policy_schema_and_semantics_are_valid(self):
        self.policy_validator.validate(self.policy)
        validate_policy_semantics(self.policy)

    def test_policy_rejects_traversal_prefix(self):
        bad = json.loads(json.dumps(self.policy))
        bad["excludedFilePrefixes"] = ["../Logs/"]
        with self.assertRaises(ValidationError):
            self.policy_validator.validate(bad)

    def test_policy_excludes_logs_only(self):
        self.assertEqual(self.policy["excludedFilePrefixes"], ["Logs/"])
        self.assertEqual(self.policy["excludedExactFiles"], [])
        self.assertTrue(self.policy["includeEverythingElse"])

    def test_root_and_target_algorithms_are_explicit(self):
        for item in self.valid['fingerprints']['rootFingerprints']:
            self.assertEqual(item['algorithm'], 'smml.content-tree-sha256/1')
        for item in self.valid['fingerprints']['targetFingerprints']:
            self.assertEqual(item['algorithm'], 'sha256')

    def test_canonical_policy_makes_runtime_log_irrelevant(self):
        base = [
            {
                "path": "Data/a.bin",
                "size": 3,
                "sha256": "a" * 64,
            },
            {
                "path": "Survival/b.lua",
                "size": 9,
                "sha256": "b" * 64,
            },
        ]
        after_launch = base + [
            {
                "path": "Logs/game-example.log",
                "size": 12,
                "sha256": "c" * 64,
            }
        ]

        self.assertNotEqual(
            content_tree_fingerprint(base),
            content_tree_fingerprint(after_launch),
        )
        self.assertEqual(
            content_tree_fingerprint(apply_canonical_policy(base, self.policy)),
            content_tree_fingerprint(apply_canonical_policy(after_launch, self.policy)),
        )

    def test_sort_has_deterministic_tie_breaker(self):
        records_a = [
            {"path": "A.txt", "size": 1, "sha256": "1" * 64},
            {"path": "a.txt", "size": 1, "sha256": "2" * 64},
        ]
        records_b = list(reversed(records_a))
        self.assertEqual(
            content_tree_fingerprint(records_a),
            content_tree_fingerprint(records_b),
        )

    def test_semantics_reject_case_collision(self):
        doc = json.loads(json.dumps(self.valid))
        doc["fingerprints"]["targetFingerprints"].append(
            {
                "path": "survival/scripts/game/SurvivalGame.lua",
                "algorithm": "sha256",
                "sha256": "934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4",
            }
        )
        with self.assertRaises(SemanticValidationError):
            validate_semantics(doc)

    def test_semantics_reject_cross_os_without_layer(self):
        doc = json.loads(json.dumps(self.valid))
        doc["platform"]["compatibilityLayer"] = {"kind": "none"}
        with self.assertRaises(SemanticValidationError):
            validate_semantics(doc)


if __name__ == "__main__":
    unittest.main()
