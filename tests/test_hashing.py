from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from hashing_validation import (  # noqa: E402
    CONTENT_TREE_ALGORITHM,
    HashingError,
    apply_canonical_policy,
    canonical_tree_summary,
    content_tree_payload,
    content_tree_summary,
    managed_output_summary,
    sha256_bytes,
    subtree_fingerprint,
    subtree_records,
)
from path_policy_validation import PathPolicyError  # noqa: E402


class HashingV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads(
            (HERE / "hashing_vectors.json").read_text(encoding="utf-8")
        )
        cls.policy = json.loads(
            (ROOT / "policies" / "smml.canonical-game-policy-1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_raw_sha256_vectors(self):
        for vector in self.vectors["rawBytes"]:
            with self.subTest(vector=vector["name"]):
                self.assertEqual(
                    sha256_bytes(bytes.fromhex(vector["hex"])),
                    vector["sha256"],
                )

    def test_sha256_bytes_requires_bytes(self):
        with self.assertRaises(HashingError) as ctx:
            sha256_bytes("abc")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.code, "HASH_BAD_INPUT")

    def test_tree_vectors(self):
        for vector in self.vectors["trees"]:
            with self.subTest(vector=vector["name"]):
                self.assertEqual(content_tree_summary(vector["records"]), vector["expected"])

    def test_tree_is_independent_of_input_order(self):
        records = self.vectors["trees"][1]["records"]
        self.assertEqual(
            content_tree_summary(records),
            content_tree_summary(list(reversed(records))),
        )

    def test_record_encoding_is_exact(self):
        records = [
            {
                "path": "Data/a.bin",
                "size": 3,
                "sha256": "a" * 64,
            }
        ]
        self.assertEqual(
            content_tree_payload(records),
            b"Data/a.bin\0" + b"3\0" + (b"a" * 64) + b"\n",
        )

    def test_duplicate_exact_path_is_rejected(self):
        record = {"path": "Data/a.bin", "size": 1, "sha256": "a" * 64}
        with self.assertRaises(HashingError) as ctx:
            content_tree_summary([record, dict(record)])
        self.assertEqual(ctx.exception.code, "HASH_DUPLICATE_PATH")

    def test_portable_path_collision_is_rejected(self):
        records = [
            {"path": "Data/A.bin", "size": 1, "sha256": "a" * 64},
            {"path": "data/a.bin", "size": 1, "sha256": "b" * 64},
        ]
        with self.assertRaises(HashingError) as ctx:
            content_tree_summary(records)
        self.assertEqual(ctx.exception.code, "HASH_PATH_COLLISION")

    def test_bad_sha256_is_rejected(self):
        with self.assertRaises(HashingError) as ctx:
            content_tree_summary(
                [{"path": "Data/a.bin", "size": 1, "sha256": "A" * 64}]
            )
        self.assertEqual(ctx.exception.code, "HASH_BAD_SHA256")

    def test_negative_size_is_rejected(self):
        with self.assertRaises(HashingError) as ctx:
            content_tree_summary(
                [{"path": "Data/a.bin", "size": -1, "sha256": "a" * 64}]
            )
        self.assertEqual(ctx.exception.code, "HASH_NEGATIVE_SIZE")

    def test_non_integer_size_is_rejected(self):
        with self.assertRaises(HashingError) as ctx:
            content_tree_summary(
                [{"path": "Data/a.bin", "size": "1", "sha256": "a" * 64}]
            )
        self.assertEqual(ctx.exception.code, "HASH_BAD_INPUT")

    def test_invalid_logical_path_is_rejected(self):
        with self.assertRaises(PathPolicyError):
            content_tree_summary(
                [{"path": "../Data/a.bin", "size": 1, "sha256": "a" * 64}]
            )

    def test_canonical_policy_excludes_only_exact_spelling(self):
        records = [
            {"path": "Data/a.bin", "size": 3, "sha256": "a" * 64},
            {"path": "Logs/runtime.log", "size": 2, "sha256": "b" * 64},
            {"path": "logs/other.log", "size": 4, "sha256": "c" * 64},
        ]
        filtered = apply_canonical_policy(records, self.policy)
        self.assertEqual(
            [record["path"] for record in filtered],
            ["Data/a.bin", "logs/other.log"],
        )

    def test_policy_cannot_hide_invalid_inventory(self):
        records = [
            {"path": "Logs/../escape.log", "size": 1, "sha256": "a" * 64}
        ]
        with self.assertRaises(PathPolicyError):
            apply_canonical_policy(records, self.policy)

    def test_policy_algorithm_must_match(self):
        policy = dict(self.policy)
        policy["contentTreeAlgorithm"] = "other"
        with self.assertRaises(HashingError) as ctx:
            apply_canonical_policy([], policy)
        self.assertEqual(ctx.exception.code, "HASH_POLICY_ALGORITHM_MISMATCH")

    def test_canonical_summary_counts_filtered_records(self):
        records = [
            {"path": "Data/a.bin", "size": 3, "sha256": "a" * 64},
            {"path": "Logs/runtime.log", "size": 12, "sha256": "c" * 64},
        ]
        summary = canonical_tree_summary(records, self.policy)
        self.assertEqual(summary["algorithm"], CONTENT_TREE_ALGORITHM)
        self.assertEqual(summary["fileCount"], 1)
        self.assertEqual(summary["totalFileBytes"], 3)

    def test_subtree_preserves_game_root_relative_paths(self):
        vector = self.vectors["subtree"]
        selected = subtree_records(vector["records"], vector["root"])
        self.assertEqual(
            [item["path"] for item in selected],
            ["Survival/a.lua", "Survival/sub/b.lua"],
        )
        self.assertEqual(
            subtree_fingerprint(vector["records"], vector["root"]),
            vector["sha256"],
        )

    def test_managed_output_uses_content_tree_algorithm(self):
        vector = next(item for item in self.vectors["trees"] if item["name"] == "managed-output")
        self.assertEqual(managed_output_summary(vector["records"]), vector["expected"])

    def test_exact_bytes_mean_reformatting_changes_digest(self):
        self.assertNotEqual(sha256_bytes(b"{}"), sha256_bytes(b"{\n}\n"))


if __name__ == "__main__":
    unittest.main()
