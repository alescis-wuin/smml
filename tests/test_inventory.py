from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

from smml_reference.hashing import canonical_tree_summary  # noqa: E402
from smml_reference.inventory import (  # noqa: E402
    build_file_inventory,
    compare_file_inventories,
    load_json_document,
    slice_inventory,
    validate_file_inventory,
)


class FileInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory_schema = json.loads(
            (ROOT / "schemas" / "smml.file-inventory-1.schema.json").read_text(encoding="utf-8")
        )
        cls.diff_schema = json.loads(
            (ROOT / "schemas" / "smml.file-inventory-diff-1.schema.json").read_text(encoding="utf-8")
        )
        cls.policy2 = json.loads(
            (ROOT / "policies" / "smml.canonical-game-policy-2.json").read_text(encoding="utf-8")
        )
        cls.baseline = load_json_document(
            ROOT / "evidence" / "gp0" / "baselines" / "b0-file-inventory.json.gz"
        )

    def test_schemas_are_valid(self):
        Draft202012Validator.check_schema(self.inventory_schema)
        Draft202012Validator.check_schema(self.diff_schema)

    def test_gp0_b0_inventory_is_self_consistent(self):
        Draft202012Validator(self.inventory_schema).validate(self.baseline)
        validate_file_inventory(self.baseline)
        self.assertEqual(self.baseline["summary"]["fileCount"], 61370)
        self.assertEqual(self.baseline["summary"]["totalFileBytes"], 20596856244)
        self.assertEqual(
            self.baseline["summary"]["sha256"],
            "6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964",
        )

    def test_gp0_cache_inventory_matches_root_fingerprint(self):
        cache = slice_inventory(self.baseline, "Cache/")
        self.assertEqual(cache["summary"]["fileCount"], 20119)
        self.assertEqual(cache["summary"]["totalFileBytes"], 5254624637)
        self.assertEqual(
            cache["summary"]["sha256"],
            "affd1530a458ac21782eabca281426fadf38b5de9a43f76ad1620462ca1d8cf1",
        )

    def test_policy_v2_recomputes_gp0_baseline(self):
        summary = canonical_tree_summary(self.baseline["files"], self.policy2)
        self.assertEqual(summary["fileCount"], 41251)
        self.assertEqual(summary["totalFileBytes"], 15342231607)
        self.assertEqual(
            summary["sha256"],
            "f8356e5f0b660320bdcd196bc553114d688aeff43f20872438cbac1e1bc9668c",
        )

    def test_policy_v2_makes_b1_log_delta_irrelevant(self):
        before = canonical_tree_summary(self.baseline["files"], self.policy2)
        after = canonical_tree_summary(
            self.baseline["files"]
            + [{"path": "Logs/game-gp0-b1.log", "size": 37744, "sha256": "a" * 64}],
            self.policy2,
        )
        self.assertEqual(before, after)

    def test_cache_diff_identifies_added_removed_modified_and_strict_target(self):
        target = self.baseline["target"]
        base = build_file_inventory(
            [
                {"path": "Cache/Bundle/core_data.cbo", "size": 2, "sha256": "1" * 64},
                {"path": "Cache/a.bin", "size": 3, "sha256": "2" * 64},
                {"path": "Cache/remove.bin", "size": 4, "sha256": "3" * 64},
            ],
            target=target,
            scope={"kind": "prefix", "path": "Cache/"},
        )
        current = build_file_inventory(
            [
                {"path": "Cache/Bundle/core_data.cbo", "size": 5, "sha256": "4" * 64},
                {"path": "Cache/a.bin", "size": 3, "sha256": "2" * 64},
                {"path": "Cache/add.bin", "size": 7, "sha256": "5" * 64},
            ],
            target=target,
            scope={"kind": "prefix", "path": "Cache/"},
        )
        diff = compare_file_inventories(
            base,
            current,
            classification="rebuildable-cache",
            strict_target_paths=["Cache/Bundle/core_data.cbo"],
        )
        Draft202012Validator(self.diff_schema).validate(diff)
        self.assertEqual(diff["summary"]["added"], 1)
        self.assertEqual(diff["summary"]["removed"], 1)
        self.assertEqual(diff["summary"]["modified"], 1)
        self.assertTrue(diff["changes"]["modified"][0]["strictTargetFingerprint"])

    def test_current_observation_preserves_core_data_strict_hash(self):
        current = json.loads(
            (ROOT / "evidence" / "gp1" / "game-target-observation-2026-09-30.json").read_text(encoding="utf-8")
        )
        targets = {item["path"]: item["sha256"] for item in current["fingerprints"]["targetFingerprints"]}
        self.assertEqual(
            targets["Cache/Bundle/core_data.cbo"],
            "682efa4378e69f1a711e1d2147c302fbdd0dc8035f841c948d50c50964181351",
        )


if __name__ == "__main__":
    unittest.main()
