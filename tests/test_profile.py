from __future__ import annotations

import copy
import hashlib
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

from profile_validation import (  # noqa: E402
    ProfileSemanticError,
    profile_digest,
    profile_matches_game_target,
    validate_profile_semantics,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMAS / "smml.profile-1.schema.json")
        cls.validator = Draft202012Validator(cls.schema)
        cls.full_path = EXAMPLES / "profile.valid.full-example.json"
        cls.full = load_json(cls.full_path)
        cls.minimal = load_json(EXAMPLES / "profile.valid.minimal.json")
        cls.target = load_json(EXAMPLES / "game-target.valid.scrap-mechanic-1.0.6.889-b1.json")

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_full_fixture_schema_and_semantics(self):
        self.validator.validate(self.full)
        validate_profile_semantics(self.full)

    def test_minimal_profile_can_request_no_user_packages(self):
        self.validator.validate(self.minimal)
        validate_profile_semantics(self.minimal)
        self.assertEqual(self.minimal["packages"], [])

    def test_reference_target_matches_gp0_identity(self):
        self.assertTrue(profile_matches_game_target(self.full, self.target))

    def test_target_constraints_are_and(self):
        doc = copy.deepcopy(self.full)
        doc["target"]["engineBuilds"] = [888]
        self.assertFalse(profile_matches_game_target(doc, self.target))

    def test_profile_digest_is_over_exact_bytes(self):
        raw = self.full_path.read_bytes()
        self.assertEqual(profile_digest(raw), hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(profile_digest(raw), profile_digest(raw + b"\n"))

    def test_duplicate_package_request_is_semantic_error(self):
        doc = copy.deepcopy(self.full)
        doc["packages"].append(copy.deepcopy(doc["packages"][0]))
        self.validator.validate(doc)
        with self.assertRaises(ProfileSemanticError):
            validate_profile_semantics(doc)

    def test_unsupported_range_is_semantic_error(self):
        doc = copy.deepcopy(self.full)
        doc["packages"][0]["range"] = "^1.0.0"
        self.validator.validate(doc)
        with self.assertRaises(ProfileSemanticError):
            validate_profile_semantics(doc)

    def test_duplicate_capability_selection_is_semantic_error(self):
        doc = copy.deepcopy(self.full)
        doc["policies"]["capabilityProviders"].append(
            copy.deepcopy(doc["policies"]["capabilityProviders"][0])
        )
        self.validator.validate(doc)
        with self.assertRaises(ProfileSemanticError):
            validate_profile_semantics(doc)

    def test_provider_selection_may_reference_non_root_package(self):
        validate_profile_semantics(self.full)
        roots = {p["id"] for p in self.full["packages"]}
        provider = self.full["policies"]["capabilityProviders"][0]["providers"][0]
        self.assertNotIn(provider, roots)

    def test_unknown_provider_ambiguity_policy_is_schema_error(self):
        doc = copy.deepcopy(self.full)
        doc["policies"]["providerAmbiguity"] = "pick-first"
        with self.assertRaises(ValidationError):
            self.validator.validate(doc)

    def test_machine_readable_target_vectors(self):
        vectors = load_json(HERE / "profile_vectors.json")
        from package_manifest_validation import target_selector_matches
        for item in vectors["targetMatches"]:
            with self.subTest(item["name"]):
                self.assertEqual(target_selector_matches(item["selector"], self.target), item["expected"])


if __name__ == "__main__":
    unittest.main()
