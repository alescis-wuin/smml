from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from transaction_journal_validation import (  # noqa: E402
    TransactionJournalSemanticError,
    classify_commit_recovery,
    classify_rollback_safety,
    classify_current_state,
    validate_transaction_journal_semantics,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TransactionJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game_schema = load_json(ROOT / "schemas" / "smml.game-target-1.schema.json")
        cls.tx_schema = load_json(ROOT / "schemas" / "smml.transaction-journal-1.schema.json")
        registry = Registry().with_resource(
            cls.game_schema["$id"], Resource.from_contents(cls.game_schema)
        )
        cls.validator = Draft202012Validator(cls.tx_schema, registry=registry)
        cls.planned = load_json(ROOT / "examples" / "transaction-journal.valid.planned.json")
        cls.prepared = load_json(ROOT / "examples" / "transaction-journal.valid.prepared.json")
        cls.committing = load_json(ROOT / "examples" / "transaction-journal.valid.committing.json")
        cls.verifying = load_json(ROOT / "examples" / "transaction-journal.valid.verifying.json")
        cls.foreign = load_json(ROOT / "examples" / "transaction-journal.valid.foreign-modification.json")
        cls.recovery = load_json(
            ROOT / "examples" / "transaction-journal.valid.recovery-required-stale-status.json"
        )
        cls.committed = load_json(ROOT / "examples" / "transaction-journal.valid.committed.json")
        cls.recovery_vectors = load_json(ROOT / "tests" / "recovery_vectors.json")

    def test_schemas_are_well_formed(self):
        Draft202012Validator.check_schema(self.game_schema)
        Draft202012Validator.check_schema(self.tx_schema)

    def test_valid_examples(self):
        for document in [self.planned, self.prepared, self.committing, self.verifying, self.recovery, self.foreign, self.committed]:
            self.validator.validate(document)
            validate_transaction_journal_semantics(document)

    def test_mutation_kinds_cover_create_replace_delete(self):
        self.assertEqual(
            [op["kind"] for op in self.planned["operations"]],
            ["replace", "create", "delete"],
        )

    def test_recovery_classifier_replace(self):
        op = self.planned["operations"][0]
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": op["before"]["sha256"]}), "BEFORE")
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": op["after"]["sha256"]}), "AFTER")
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": "f" * 64}), "FOREIGN")
        self.assertEqual(classify_current_state(op, {"kind": "missing"}), "FOREIGN")

    def test_recovery_classifier_create(self):
        op = self.planned["operations"][1]
        self.assertEqual(classify_current_state(op, {"kind": "missing"}), "BEFORE")
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": op["after"]["sha256"]}), "AFTER")
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": "f" * 64}), "FOREIGN")

    def test_recovery_classifier_delete(self):
        op = self.planned["operations"][2]
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": op["before"]["sha256"]}), "BEFORE")
        self.assertEqual(classify_current_state(op, {"kind": "missing"}), "AFTER")
        self.assertEqual(classify_current_state(op, {"kind": "file", "sha256": "f" * 64}), "FOREIGN")

    def test_non_file_observation_is_foreign(self):
        op = self.planned["operations"][1]
        for kind in ["directory", "symlink", "reparsePoint", "other"]:
            self.assertEqual(classify_current_state(op, {"kind": kind}), "FOREIGN")


    def test_rollback_is_idempotently_classified(self):
        op = self.planned["operations"][0]
        self.assertEqual(
            classify_rollback_safety(op, {"kind": "file", "sha256": op["after"]["sha256"]}),
            "CAN_ROLLBACK",
        )
        self.assertEqual(
            classify_rollback_safety(op, {"kind": "file", "sha256": op["before"]["sha256"]}),
            "ALREADY_ROLLED_BACK",
        )
        self.assertEqual(
            classify_rollback_safety(op, {"kind": "file", "sha256": "f" * 64}),
            "FOREIGN",
        )

    def test_stale_pending_status_does_not_override_filesystem(self):
        op = self.recovery["operations"][1]
        self.assertEqual(op["status"], "PENDING")
        observed = self.recovery["incidents"][-1]["observed"]
        self.assertEqual(classify_current_state(op, observed), "AFTER")

    def test_replace_noop_is_rejected(self):
        doc = copy.deepcopy(self.planned)
        doc["operations"][0]["after"]["sha256"] = doc["operations"][0]["before"]["sha256"]
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)

    def test_committing_requires_applied_prefix(self):
        doc = copy.deepcopy(self.committing)
        doc["operations"][0]["status"] = "PENDING"
        doc["operations"][1]["status"] = "APPLIED"
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)

    def test_incident_phase_requires_matching_latest_incident(self):
        doc = copy.deepcopy(self.recovery)
        doc["incidents"][-1]["kind"] = "FOREIGN_MODIFICATION"
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)


    def test_embedded_game_target_semantics_are_revalidated(self):
        doc = copy.deepcopy(self.planned)
        doc["gameTarget"]["fingerprints"]["targetFingerprints"].append({
            "path": "survival/scripts/game/SurvivalGame.lua",
            "algorithm": "sha256",
            "sha256": "9" * 64,
        })
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)

    def test_recovery_vectors(self):
        operations = self.planned["operations"]
        for vector in self.recovery_vectors:
            with self.subTest(vector=vector["name"]):
                result = classify_commit_recovery(operations, vector["observations"])
                self.assertEqual(result["classifications"], vector["expectedClassifications"])
                self.assertEqual(result["decision"], vector["expectedDecision"])
                if "expectedNextSequence" in vector:
                    self.assertEqual(result.get("nextSequence"), vector["expectedNextSequence"])

    def test_incident_must_have_phase_history_entry(self):
        doc = copy.deepcopy(self.foreign)
        doc["phase"] = "RECOVERY_REQUIRED"
        doc["phaseHistory"][-1]["phase"] = "RECOVERY_REQUIRED"
        # Historical incident still claims FOREIGN_MODIFICATION but no such phase exists.
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)

    def test_terminal_phase_cannot_transition(self):
        doc = copy.deepcopy(self.committed)
        doc["phase"] = "FAILED"
        doc["journalRevision"] = 9
        doc["updatedAt"] = "2026-09-29T16:00:09Z"
        doc["phaseHistory"].append({"revision": 9, "at": "2026-09-29T16:00:09Z", "phase": "FAILED"})
        doc["incidents"].append({
            "incidentId": "inc-terminal",
            "kind": "FAILED",
            "reasonCode": "TEST",
            "detectedAt": "2026-09-29T16:00:09Z",
            "detectedRevision": 9,
        })
        with self.assertRaises(TransactionJournalSemanticError):
            validate_transaction_journal_semantics(doc)


if __name__ == "__main__":
    unittest.main()
