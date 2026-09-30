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
from contract_descriptor_validation import validate_contract_descriptor_semantics  # noqa: E402
from hook_pack_manifest_validation import (  # noqa: E402
    HookPackManifestSemanticError,
    hook_pack_matches_game_target,
    target_selector_matches,
    to_logical_text,
    validate_baseline_preconditions,
    validate_exact_text_anchors,
    validate_hook_pack_manifest_semantics,
)
from package_manifest_validation import validate_package_manifest_semantics  # noqa: E402
from validation import validate_semantics  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class HookPackManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMAS / "smml.hook-pack-manifest-1.schema.json")
        cls.validator = Draft202012Validator(cls.schema)
        cls.valid = load_json(EXAMPLES / "hook-pack-manifest.valid.scrap-mechanic-1.0.6.889.json")
        cls.game_target = load_json(EXAMPLES / "game-target.valid.scrap-mechanic-1.0.6.889-b1.json")
        cls.contract = load_json(EXAMPLES / "contract-descriptor.valid.notification.json")

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_reference_fixture_is_valid(self):
        self.validator.validate(self.valid)
        validate_hook_pack_manifest_semantics(self.valid)

    def test_reference_target_matches_gp0_identity(self):
        validate_semantics(self.game_target)
        self.assertTrue(hook_pack_matches_game_target(self.valid, self.game_target))

    def test_target_rejects_other_build(self):
        target = copy.deepcopy(self.game_target)
        target["steamBuildId"] = "25442088"
        self.assertFalse(hook_pack_matches_game_target(self.valid, target))

    def test_target_rejects_other_canonical_fingerprint(self):
        target = copy.deepcopy(self.game_target)
        target["fingerprints"]["canonicalGameFingerprint"]["sha256"] = "f" * 64
        self.assertFalse(hook_pack_matches_game_target(self.valid, target))

    def test_optional_platform_constraint_is_exact(self):
        selector = copy.deepcopy(self.valid["targets"][0])
        selector["hostOs"] = "linux"
        selector["gameOs"] = "windows"
        selector["compatibilityLayer"] = "proton"
        self.assertTrue(target_selector_matches(selector, self.game_target))
        selector["compatibilityLayer"] = "none"
        self.assertFalse(target_selector_matches(selector, self.game_target))

    def test_unknown_target_file_is_rejected(self):
        doc = copy.deepcopy(self.valid)
        doc["hooks"][0]["targetFileId"] = "missing"
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_function_transformation_requires_lua_function_anchor(self):
        doc = copy.deepcopy(self.valid)
        doc["hooks"][0]["transformations"][0]["kind"] = "wrap-prefix"
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_lua_function_anchor_accepts_function_transformation(self):
        doc = copy.deepcopy(self.valid)
        hook = doc["hooks"][0]
        hook["anchors"] = [
            {
                "id": "server-on-create",
                "kind": "lua-function",
                "symbol": "SurvivalGame.server_onCreate",
                "cardinality": "exactly-one",
            }
        ]
        hook["transformations"] = [
            {
                "sequence": 0,
                "kind": "wrap-prefix",
                "anchorId": "server-on-create",
                "contentArtifactId": "fragment.game-server-created",
            }
        ]
        self.validator.validate(doc)
        validate_hook_pack_manifest_semantics(doc)

    def test_replace_region_requires_distinct_anchors(self):
        doc = copy.deepcopy(self.valid)
        hook = doc["hooks"][0]
        hook["transformations"] = [
            {
                "sequence": 0,
                "kind": "replace-region",
                "startAnchorId": "server-on-create-header",
                "endAnchorId": "server-on-create-header",
                "includeStart": False,
                "includeEnd": False,
                "contentArtifactId": "fragment.game-server-created",
            }
        ]
        self.validator.validate(doc)
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)


    def test_hook_sequences_are_contiguous_and_ordered(self):
        doc = copy.deepcopy(self.valid)
        second = copy.deepcopy(doc["hooks"][0])
        second["sequence"] = 2
        second["hookId"] = "game.client-created"
        second["contract"]["contractId"] = "game.clientCreated"
        second["verification"]["beginMarker"] = "-- SMML_HOOK_BEGIN:game.clientCreated@1"
        second["verification"]["endMarker"] = "-- SMML_HOOK_END:game.clientCreated@1"
        doc["hooks"].append(second)
        self.validator.validate(doc)
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_transformation_sequences_are_contiguous_and_ordered(self):
        doc = copy.deepcopy(self.valid)
        doc["hooks"][0]["transformations"][0]["sequence"] = 1
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_markers_are_globally_unique(self):
        doc = copy.deepcopy(self.valid)
        second = copy.deepcopy(doc["hooks"][0])
        second["sequence"] = 1
        second["hookId"] = "game.client-created"
        second["contract"]["contractId"] = "game.clientCreated"
        second["verification"]["endMarker"] = "-- SMML_HOOK_END:game.clientCreated@1"
        doc["hooks"].append(second)
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_cache_path_must_not_be_target_path(self):
        doc = copy.deepcopy(self.valid)
        doc["cacheConsequences"][0]["path"] = doc["targetFiles"][0]["path"]
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(doc)

    def test_baseline_precondition_accepts_known_hash(self):
        target = self.valid["targetFiles"][0]
        observed = {
            target["path"]: {
                "kind": "regular-file",
                "sha256": target["acceptedBaselineSha256"][0],
            }
        }
        validate_baseline_preconditions(self.valid, observed)

    def test_baseline_precondition_rejects_foreign_hash(self):
        path = self.valid["targetFiles"][0]["path"]
        observed = {path: {"kind": "regular-file", "sha256": "f" * 64}}
        with self.assertRaises(HookPackManifestSemanticError):
            validate_baseline_preconditions(self.valid, observed)

    def test_baseline_precondition_rejects_symlink(self):
        target = self.valid["targetFiles"][0]
        observed = {
            target["path"]: {
                "kind": "symlink",
                "sha256": target["acceptedBaselineSha256"][0],
            }
        }
        with self.assertRaises(HookPackManifestSemanticError):
            validate_baseline_preconditions(self.valid, observed)

    def test_exact_text_anchor_requires_exactly_one_match(self):
        hook = self.valid["hooks"][0]
        source = "prefix\nfunction SurvivalGame.server_onCreate( self )\nbody\nend\n"
        validate_exact_text_anchors(hook, source)
        with self.assertRaises(HookPackManifestSemanticError):
            validate_exact_text_anchors(hook, source + source)
        with self.assertRaises(HookPackManifestSemanticError):
            validate_exact_text_anchors(hook, "function Other.server_onCreate( self )\n")

    def test_crlf_is_normalized_logically_but_mixed_endings_fail(self):
        self.assertEqual(to_logical_text("a\r\nb\r\n"), "a\nb\n")
        with self.assertRaises(HookPackManifestSemanticError):
            to_logical_text("a\r\nb\n")

    def test_machine_readable_vectors(self):
        vectors = load_json(HERE / "hook_pack_manifest_vectors.json")
        for item in vectors["targetMatches"]:
            with self.subTest(kind="target", name=item["name"]):
                self.assertEqual(
                    target_selector_matches(item["selector"], self.game_target),
                    item["expected"],
                )

        target = self.valid["targetFiles"][0]
        for item in vectors["baselinePreconditions"]:
            observed = {
                target["path"]: {
                    "kind": item["kind"],
                    "sha256": item["sha256"],
                }
            }
            with self.subTest(kind="baseline", name=item["name"]):
                if item["expected"]:
                    validate_baseline_preconditions(self.valid, observed)
                else:
                    with self.assertRaises(HookPackManifestSemanticError):
                        validate_baseline_preconditions(self.valid, observed)

        hook = self.valid["hooks"][0]
        for item in vectors["anchorCardinality"]:
            with self.subTest(kind="anchor", name=item["name"]):
                if item["expected"]:
                    validate_exact_text_anchors(hook, item["text"])
                else:
                    with self.assertRaises(HookPackManifestSemanticError):
                        validate_exact_text_anchors(hook, item["text"])

    def test_package_artifact_types_are_checked(self):
        package = self._package_manifest_for_reference_hook_pack()
        validate_package_manifest_semantics(package)
        validate_hook_pack_manifest_semantics(self.valid, package_manifest=package)

        bad = copy.deepcopy(package)
        for artifact in bad["artifacts"]:
            if artifact["id"] == "adapter.survival-game":
                artifact["type"] = "smml.hook-patch-fragment/1"
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(self.valid, package_manifest=bad)

    def test_contract_descriptor_key_is_checked(self):
        package = self._package_manifest_for_reference_hook_pack()
        descriptors = {"contract.game-server-created": self.contract}
        validate_contract_descriptor_semantics(self.contract, package)
        validate_hook_pack_manifest_semantics(
            self.valid,
            package_manifest=package,
            contract_descriptors=descriptors,
        )

        bad_descriptor = copy.deepcopy(self.contract)
        bad_descriptor["version"] = 2
        with self.assertRaises(HookPackManifestSemanticError):
            validate_hook_pack_manifest_semantics(
                self.valid,
                package_manifest=package,
                contract_descriptors={"contract.game-server-created": bad_descriptor},
            )

    @staticmethod
    def _package_manifest_for_reference_hook_pack():
        files = [
            ("hookpacks/build-889.json", "0" * 64),
            ("runtime/SurvivalGameAdapter.lua", "1" * 64),
            ("contracts/game.serverCreated.json", "2" * 64),
            ("contracts/game.serverCreated.payload.json", "3" * 64),
            ("fragments/game.serverCreated.lua", "4" * 64),
        ]
        return {
            "schema": "smml.package-manifest/1",
            "id": "org.smml.hooks.scrap-mechanic",
            "name": "SMML Scrap Mechanic Hook Pack test fixture",
            "version": "0.1.0",
            "authors": ["SMML"],
            "compatibility": {
                "targets": [{"steamAppId": 387990, "gameVersions": ["1.0.6"]}]
            },
            "dependencies": [],
            "capabilities": {"provides": [], "requires": []},
            "conflicts": {"packages": [], "capabilities": []},
            "loadBefore": [],
            "loadAfter": [],
            "persistenceImpact": "runtimeState",
            "artifacts": [
                {
                    "id": "hookpack.build-889",
                    "type": "smml.hook-pack-manifest/1",
                    "path": "hookpacks/build-889.json",
                },
                {
                    "id": "adapter.survival-game",
                    "type": "smml.runtime-adapter/1",
                    "path": "runtime/SurvivalGameAdapter.lua",
                },
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
                {
                    "id": "fragment.game-server-created",
                    "type": "smml.hook-patch-fragment/1",
                    "path": "fragments/game.serverCreated.lua",
                },
            ],
            "files": [
                {"path": path, "size": 1, "sha256": digest} for path, digest in files
            ],
        }


if __name__ == "__main__":
    unittest.main()
