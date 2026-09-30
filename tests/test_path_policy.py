from __future__ import annotations

import json
import unicodedata
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from path_policy_validation import (
    MAX_PATH_UTF8_BYTES,
    MAX_SEGMENT_UTF8_BYTES,
    PathPolicyError,
    portable_collision_key,
    validate_filesystem_observation,
    validate_logical_path,
    validate_unique_paths,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VECTORS = json.loads((HERE / "path_policy_vectors.json").read_text(encoding="utf-8"))


class PathPolicyTests(unittest.TestCase):
    def test_policy_document_matches_schema(self):
        schema = json.loads((ROOT / "schemas" / "smml.path-policy-1.schema.json").read_text(encoding="utf-8"))
        policy = json.loads((ROOT / "policies" / "smml.path-policy-1.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(policy)

    def test_runtime_unicode_table_is_normative_version(self):
        self.assertEqual(unicodedata.unidata_version, "15.1.0")

    def test_valid_vectors(self):
        for path in VECTORS["validPaths"]:
            with self.subTest(path=path):
                self.assertEqual(validate_logical_path(path), path)

    def test_invalid_vectors(self):
        for item in VECTORS["invalidPaths"]:
            with self.subTest(path=item["path"]):
                with self.assertRaises(PathPolicyError) as cm:
                    validate_logical_path(item["path"])
                self.assertEqual(cm.exception.code, item["code"])

    def test_collision_vectors(self):
        for paths in VECTORS["collisionSets"]:
            with self.subTest(paths=paths):
                with self.assertRaises(PathPolicyError) as cm:
                    validate_unique_paths(paths)
                self.assertEqual(cm.exception.code, "CASE_COLLISION")

    def test_non_collision_vectors(self):
        for paths in VECTORS["nonCollisionSets"]:
            with self.subTest(paths=paths):
                validate_unique_paths(paths)

    def test_collision_key_is_stable_for_casefold_equivalent_strings(self):
        self.assertEqual(
            portable_collision_key("Straße.txt"),
            portable_collision_key("STRASSE.TXT"),
        )

    def test_path_byte_limit(self):
        path = "a" * (MAX_PATH_UTF8_BYTES + 1)
        with self.assertRaises(PathPolicyError) as cm:
            validate_logical_path(path)
        self.assertEqual(cm.exception.code, "PATH_TOO_LONG")

    def test_segment_byte_limit(self):
        path = "é" * ((MAX_SEGMENT_UTF8_BYTES // 2) + 1)
        with self.assertRaises(PathPolicyError) as cm:
            validate_logical_path(path)
        self.assertEqual(cm.exception.code, "SEGMENT_TOO_LONG")

    def test_symlink_ancestor_is_rejected(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=True,
                ancestor_kinds=["directory", "symlink"],
                leaf_kind="regular-file",
                expected_leaf="regular-file",
                intent="inspect",
            )
        self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

    def test_reparse_leaf_is_rejected(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=True,
                ancestor_kinds=["directory"],
                leaf_kind="reparse-point",
                expected_leaf="regular-file-or-missing",
                intent="inspect",
            )
        self.assertEqual(cm.exception.code, "REPARSE_POINT_FORBIDDEN")

    def test_mutating_hardlinked_file_is_rejected(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=True,
                ancestor_kinds=["directory"],
                leaf_kind="regular-file",
                expected_leaf="regular-file",
                intent="replace",
                leaf_link_count=2,
            )
        self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")

    def test_case_mismatch_is_rejected(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=True,
                ancestor_kinds=["directory"],
                leaf_kind="regular-file",
                expected_leaf="regular-file",
                intent="inspect",
                exact_case=False,
            )
        self.assertEqual(cm.exception.code, "CASE_MISMATCH")

    def test_untrusted_root_is_rejected(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=False,
                ancestor_kinds=[],
                leaf_kind="missing",
                expected_leaf="regular-file-or-missing",
                intent="inspect",
            )
        self.assertEqual(cm.exception.code, "ROOT_UNTRUSTED")

    def test_create_requires_missing_leaf(self):
        with self.assertRaises(PathPolicyError) as cm:
            validate_filesystem_observation(
                root_trusted=True,
                ancestor_kinds=["directory"],
                leaf_kind="regular-file",
                expected_leaf="regular-file-or-missing",
                intent="create",
            )
        self.assertEqual(cm.exception.code, "TYPE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
