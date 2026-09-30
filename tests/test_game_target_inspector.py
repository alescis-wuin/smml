from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from smml_reference.game_target_inspector import (  # noqa: E402
    EntryObservation,
    InspectorError,
    InventorySnapshot,
    _ensure_snapshot_stable,
    inspect_game_target,
    parse_vdf,
    read_steam_manifest,
    validate_inspection_plan,
)
from smml_reference.hashing import canonical_tree_summary, content_tree_summary, subtree_fingerprint  # noqa: E402
from validation import validate_semantics  # noqa: E402


def _write_manifest(path: Path, *, appid: str = "387990", buildid: str = "25442087", installdir: str = "Scrap Mechanic", beta: str | None = None) -> None:
    user_config = ""
    if beta is not None:
        user_config = f'\n    "UserConfig"\n    {{\n        "BetaKey" "{beta}"\n    }}'
    path.write_text(
        f'''"AppState"\n{{\n    "appid" "{appid}"\n    "name" "Scrap Mechanic"\n    "installdir" "{installdir}"\n    "buildid" "{buildid}"{user_config}\n}}\n''',
        encoding="utf-8",
    )


class GameTargetInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan_schema = json.loads((ROOT / "schemas" / "smml.game-target-inspection-plan-1.schema.json").read_text(encoding="utf-8"))
        cls.game_schema = json.loads((ROOT / "schemas" / "smml.game-target-1.schema.json").read_text(encoding="utf-8"))
        cls.plan = json.loads((ROOT / "policies" / "smml.game-target-inspection-plan-1.json").read_text(encoding="utf-8"))
        cls.canonical_policy = json.loads((ROOT / "policies" / "smml.canonical-game-policy-1.json").read_text(encoding="utf-8"))

    def _fixture(self):
        td = tempfile.TemporaryDirectory()
        base = Path(td.name)
        steamapps = base / "steamapps"
        root = steamapps / "common" / "Scrap Mechanic"
        (root / "Data").mkdir(parents=True)
        (root / "Survival" / "Scripts" / "game").mkdir(parents=True)
        (root / "Logs").mkdir(parents=True)
        (root / "Data" / "a.bin").write_bytes(b"abc")
        (root / "Survival" / "Scripts" / "game" / "SurvivalGame.lua").write_bytes(b"print('ok')\n")
        (root / "Logs" / "game.log").write_bytes(b"runtime\n")
        manifest = steamapps / "appmanifest_387990.acf"
        _write_manifest(manifest)
        plan = {
            "schema": "smml.game-target-inspection-plan/1",
            "steamAppId": 387990,
            "canonicalPolicy": "smml.canonical-game-policy/1",
            "builds": [
                {
                    "steamBuildId": "25442087",
                    "steamBranch": "public",
                    "gameVersion": "1.0.6",
                    "engineBuild": 889,
                    "gameOs": "windows",
                    "gameArch": "x86_64",
                    "rootFingerprints": ["Survival", "Data"],
                    "targetFingerprints": ["Survival/Scripts/game/SurvivalGame.lua"],
                }
            ],
        }
        return td, root, manifest, plan

    def test_plan_schema_and_reference_policy(self):
        Draft202012Validator.check_schema(self.plan_schema)
        Draft202012Validator(self.plan_schema).validate(self.plan)
        validate_inspection_plan(self.plan)
        build = self.plan["builds"][0]
        self.assertEqual(build["steamBuildId"], "25442087")
        self.assertEqual(build["gameVersion"], "1.0.6")
        self.assertEqual(build["engineBuild"], 889)
        self.assertIn("Survival/Scripts/game/SurvivalGame.lua", build["targetFingerprints"])

    def test_vdf_parser_supports_comments_and_public_branch(self):
        doc = parse_vdf('// header\n"AppState" { "appid" "387990" "buildid" "25442087" "installdir" "Scrap Mechanic" }')
        self.assertIn("AppState", doc)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "appmanifest.acf"
            _write_manifest(path)
            manifest = read_steam_manifest(path)
            self.assertEqual(manifest.branch, "public")

    def test_vdf_parser_rejects_duplicate_key(self):
        with self.assertRaises(InspectorError) as cm:
            parse_vdf('"AppState" { "appid" "1" "appid" "2" }')
        self.assertEqual(cm.exception.code, "GTI_APPMANIFEST_INVALID")

    def test_inspector_generates_schema_valid_identity(self):
        td, root, manifest, plan = self._fixture()
        try:
            identity = inspect_game_target(
                root,
                plan=plan,
                canonical_policy=self.canonical_policy,
                appmanifest_path=manifest,
                compatibility_layer="proton",
                host_os="linux",
                host_arch="x86_64",
            )
            Draft202012Validator(self.game_schema).validate(identity)
            validate_semantics(identity)
            self.assertEqual(identity["steamBuildId"], "25442087")
            self.assertEqual(identity["platform"]["compatibilityLayer"]["kind"], "proton")
        finally:
            td.cleanup()

    def test_exact_and_canonical_fingerprints_use_same_inventory(self):
        td, root, manifest, plan = self._fixture()
        try:
            identity = inspect_game_target(
                root,
                plan=plan,
                canonical_policy=self.canonical_policy,
                appmanifest_path=manifest,
                compatibility_layer="proton",
                host_os="linux",
                host_arch="x86_64",
            )
            records = []
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                rel = path.relative_to(root).as_posix()
                data = path.read_bytes()
                import hashlib
                records.append({"path": rel, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            exact = content_tree_summary(records)
            canonical = canonical_tree_summary(records, self.canonical_policy)
            self.assertEqual(identity["fingerprints"]["installationExactFingerprint"]["sha256"], exact["sha256"])
            self.assertEqual(identity["fingerprints"]["canonicalGameFingerprint"]["sha256"], canonical["sha256"])
            self.assertNotEqual(exact["sha256"], canonical["sha256"])
            root_map = {item["path"]: item["sha256"] for item in identity["fingerprints"]["rootFingerprints"]}
            self.assertEqual(root_map["Data"], subtree_fingerprint(records, "Data"))
        finally:
            td.cleanup()

    def test_unknown_steam_build_is_fail_closed(self):
        td, root, manifest, plan = self._fixture()
        try:
            _write_manifest(manifest, buildid="99999999")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "GTI_UNKNOWN_STEAM_BUILD")
        finally:
            td.cleanup()

    def test_branch_mismatch_is_fail_closed(self):
        td, root, manifest, plan = self._fixture()
        try:
            _write_manifest(manifest, beta="experimental")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "GTI_BRANCH_MISMATCH")
        finally:
            td.cleanup()

    def test_appid_and_installdir_are_verified(self):
        td, root, manifest, plan = self._fixture()
        try:
            _write_manifest(manifest, appid="1")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "GTI_APPID_MISMATCH")
            _write_manifest(manifest, installdir="Wrong Name")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "GTI_INSTALLDIR_MISMATCH")
        finally:
            td.cleanup()

    def test_cross_os_requires_explicit_compatibility_layer(self):
        td, root, manifest, plan = self._fixture()
        try:
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, host_os="linux")
            self.assertEqual(cm.exception.code, "GTI_COMPATIBILITY_LAYER_REQUIRED")
        finally:
            td.cleanup()

    def test_symlink_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        td, root, manifest, plan = self._fixture()
        try:
            os.symlink(root / "Data" / "a.bin", root / "Data" / "link.bin")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
        finally:
            td.cleanup()

    @unittest.skipIf(os.name == "nt", "case-collision fixture requires a case-sensitive test filesystem")
    def test_portable_case_collision_is_rejected(self):
        td, root, manifest, plan = self._fixture()
        try:
            (root / "Data" / "A.txt").write_bytes(b"1")
            (root / "Data" / "a.txt").write_bytes(b"2")
            with self.assertRaises(InspectorError) as cm:
                inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            self.assertEqual(cm.exception.code, "CASE_COLLISION")
        finally:
            td.cleanup()

    def test_snapshot_change_is_rejected(self):
        sig1 = (1, 2, 3, 4, 5, 6)
        sig2 = (1, 2, 3, 4, 5, 7)
        before = InventorySnapshot(sig1, {"Data/a.bin": EntryObservation("regular-file", sig1, 4, "a" * 64)}, ())
        after = InventorySnapshot(sig1, {"Data/a.bin": EntryObservation("regular-file", sig2, 4, None)}, ())
        with self.assertRaises(InspectorError) as cm:
            _ensure_snapshot_stable(before, after)
        self.assertEqual(cm.exception.code, "GTI_FILESYSTEM_CHANGED")

    def test_root_and_targets_are_emitted_in_canonical_order(self):
        td, root, manifest, plan = self._fixture()
        try:
            identity = inspect_game_target(root, plan=plan, canonical_policy=self.canonical_policy, appmanifest_path=manifest, compatibility_layer="proton", host_os="linux")
            roots = [item["path"] for item in identity["fingerprints"]["rootFingerprints"]]
            self.assertEqual(roots, ["Data", "Survival"])
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
