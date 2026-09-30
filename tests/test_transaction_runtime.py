from __future__ import annotations

import copy
import json
import os
import subprocess
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

from smml_reference.hashing import sha256_bytes  # noqa: E402
from smml_reference.transaction_runtime import (  # noqa: E402
    compare_game_target_binding,
    inspect_transaction_recovery,
    observe_operation_path,
    validate_transaction_recovery_report_semantics,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


BEFORE_A = b"alpha-before\n"
AFTER_A = b"alpha-after\n"
AFTER_B = b"bravo-created\n"
BEFORE_C = b"charlie-before\n"
FOREIGN = b"foreign\n"


class TransactionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_json(ROOT / "examples" / "transaction-journal.valid.planned.json")
        cls.report_schema = load_json(ROOT / "schemas" / "smml.transaction-recovery-report-1.schema.json")
        Draft202012Validator.check_schema(cls.report_schema)
        cls.report_validator = Draft202012Validator(cls.report_schema)

    def make_journal(self, phase: str = "PLANNED"):
        doc = copy.deepcopy(self.base)
        doc["transactionId"] = "tx-runtime-test"
        doc["operations"] = [
            {
                "operationId": "op-replace-a",
                "sequence": 0,
                "path": "Data/a.txt",
                "kind": "replace",
                "owner": "test",
                "before": {"exists": True, "sha256": sha256_bytes(BEFORE_A)},
                "after": {"exists": True, "sha256": sha256_bytes(AFTER_A)},
                "status": "PENDING",
            },
            {
                "operationId": "op-create-b",
                "sequence": 1,
                "path": "Data/b.txt",
                "kind": "create",
                "owner": "test",
                "before": {"exists": False},
                "after": {"exists": True, "sha256": sha256_bytes(AFTER_B)},
                "status": "PENDING",
            },
            {
                "operationId": "op-delete-c",
                "sequence": 2,
                "path": "Data/c.txt",
                "kind": "delete",
                "owner": "test",
                "before": {"exists": True, "sha256": sha256_bytes(BEFORE_C)},
                "after": {"exists": False},
                "status": "PENDING",
            },
        ]
        history = [{"revision": 0, "at": "2026-09-29T16:00:00Z", "phase": "PLANNED"}]
        incidents = []
        revision = 0
        updated = "2026-09-29T16:00:00Z"

        if phase in {"PREPARED", "COMMITTING", "VERIFYING", "COMMITTED", "RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED"}:
            history.append({"revision": 1, "at": "2026-09-29T16:00:01Z", "phase": "PREPARED"})
            revision = 1
            updated = "2026-09-29T16:00:01Z"
        if phase in {"COMMITTING", "VERIFYING", "COMMITTED", "RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED"}:
            history.append({"revision": 2, "at": "2026-09-29T16:00:02Z", "phase": "COMMITTING"})
            revision = 2
            updated = "2026-09-29T16:00:02Z"
        if phase == "VERIFYING" or phase == "COMMITTED":
            history.append({"revision": 3, "at": "2026-09-29T16:00:03Z", "phase": "VERIFYING"})
            revision = 3
            updated = "2026-09-29T16:00:03Z"
            for op in doc["operations"]:
                op["status"] = "APPLIED"
        if phase == "COMMITTED":
            history.append({"revision": 4, "at": "2026-09-29T16:00:04Z", "phase": "COMMITTED"})
            revision = 4
            updated = "2026-09-29T16:00:04Z"
            for op in doc["operations"]:
                op["status"] = "VERIFIED"
        if phase in {"RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED"}:
            history.append({"revision": 3, "at": "2026-09-29T16:00:03Z", "phase": phase})
            revision = 3
            updated = "2026-09-29T16:00:03Z"
            incidents.append({
                "incidentId": "inc-runtime",
                "kind": phase,
                "reasonCode": "TEST_RUNTIME",
                "detectedAt": "2026-09-29T16:00:03Z",
                "detectedRevision": 3,
            })
        if phase == "FAILED":
            history.append({"revision": 1, "at": "2026-09-29T16:00:01Z", "phase": "FAILED"})
            revision = 1
            updated = "2026-09-29T16:00:01Z"
            incidents.append({
                "incidentId": "inc-failed",
                "kind": "FAILED",
                "reasonCode": "TEST_RUNTIME",
                "detectedAt": "2026-09-29T16:00:01Z",
                "detectedRevision": 1,
            })

        doc["phase"] = phase
        doc["journalRevision"] = revision
        doc["updatedAt"] = updated
        doc["phaseHistory"] = history
        doc["incidents"] = incidents
        return doc

    def current_target(self, journal):
        target = copy.deepcopy(journal["gameTarget"])
        target["fingerprints"]["installationExactFingerprint"]["sha256"] = "0" * 64
        for root in target["fingerprints"]["rootFingerprints"]:
            if root["path"] == "Cache":
                root["sha256"] = "1" * 64
        return target

    def build_root(self, td: str, state: str = "before") -> Path:
        root = Path(td) / "game"
        (root / "Data").mkdir(parents=True)
        if state == "before":
            (root / "Data" / "a.txt").write_bytes(BEFORE_A)
            (root / "Data" / "c.txt").write_bytes(BEFORE_C)
        elif state == "after-op0":
            (root / "Data" / "a.txt").write_bytes(AFTER_A)
            (root / "Data" / "c.txt").write_bytes(BEFORE_C)
        elif state == "all-after":
            (root / "Data" / "a.txt").write_bytes(AFTER_A)
            (root / "Data" / "b.txt").write_bytes(AFTER_B)
        elif state == "inverted":
            (root / "Data" / "a.txt").write_bytes(BEFORE_A)
            (root / "Data" / "b.txt").write_bytes(AFTER_B)
            (root / "Data" / "c.txt").write_bytes(BEFORE_C)
        elif state == "foreign":
            (root / "Data" / "a.txt").write_bytes(FOREIGN)
            (root / "Data" / "c.txt").write_bytes(BEFORE_C)
        else:
            raise AssertionError(state)
        return root

    def validate_report(self, report):
        self.report_validator.validate(report)
        validate_transaction_recovery_report_semantics(report)

    def test_target_binding_ignores_exact_and_cache_root_drift(self):
        journal = self.make_journal()
        current = self.current_target(journal)
        binding = compare_game_target_binding(journal["gameTarget"], current)
        self.assertEqual(binding, {"status": "MATCH", "mismatches": []})

    def test_target_binding_rejects_canonical_drift(self):
        journal = self.make_journal()
        current = self.current_target(journal)
        current["fingerprints"]["canonicalGameFingerprint"]["sha256"] = "2" * 64
        binding = compare_game_target_binding(journal["gameTarget"], current)
        self.assertEqual(binding["status"], "MISMATCH")
        self.assertTrue(any(x["field"] == "fingerprints.canonicalGameFingerprint" for x in binding["mismatches"]))

    def test_target_binding_rejects_strict_target_drift(self):
        journal = self.make_journal()
        current = self.current_target(journal)
        current["fingerprints"]["targetFingerprints"][0]["sha256"] = "3" * 64
        binding = compare_game_target_binding(journal["gameTarget"], current)
        self.assertEqual(binding["status"], "MISMATCH")
        self.assertTrue(any(x["field"].startswith("targetFingerprints[") for x in binding["mismatches"]))

    def test_planned_before_state_needs_no_recovery(self):
        journal = self.make_journal("PLANNED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "NO_RECOVERY_NEEDED")
        self.assertEqual(report["summary"], {"operationCount": 3, "beforeCount": 3, "afterCount": 0, "foreignCount": 0, "unsafePathCount": 0})

    def test_committing_after_prefix_resumes_at_first_before(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "after-op0")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"], {"decision": "RESUME_COMMIT", "nextSequence": 1})
        self.assertEqual(report["operations"][0]["journalStatusAssessment"], "STALE_STATUS")

    def test_committing_all_after_is_ready_to_verify(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "all-after")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "READY_TO_VERIFY")

    def test_impossible_before_after_frontier_requires_recovery(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "inverted")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "RECOVERY_REQUIRED")

    def test_foreign_content_is_fail_closed(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "foreign")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "FOREIGN_MODIFICATION")
        self.assertGreaterEqual(report["summary"]["foreignCount"], 1)

    def test_symlink_leaf_is_observed_without_following_and_blocks(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            target = root / "outside.txt"
            target.write_bytes(AFTER_A)
            (root / "Data" / "a.txt").unlink()
            os.symlink(target, root / "Data" / "a.txt")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        first = report["operations"][0]
        self.assertEqual(first["observation"]["kind"], "symlink")
        self.assertEqual(first["observation"]["pathSafety"]["status"], "BLOCKED")
        self.assertEqual(report["recovery"]["decision"], "PATH_POLICY_BLOCKED")

    def test_hardlinked_replace_is_observable_but_blocked(self):
        journal = self.make_journal("COMMITTING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            os.link(root / "Data" / "a.txt", root / "Data" / "a-hardlink.txt")
            observed = observe_operation_path(root, journal["operations"][0])
            self.assertEqual(observed["kind"], "file")
            self.assertEqual(observed["sha256"], sha256_bytes(BEFORE_A))
            self.assertEqual(observed["pathSafety"]["status"], "BLOCKED")
            self.assertEqual(observed["pathSafety"]["issues"][0]["code"], "HARDLINK_FORBIDDEN")

    def test_case_mismatch_is_blocked(self):
        journal = self.make_journal("COMMITTING")
        journal["operations"][0]["path"] = "Data/A.txt"
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["operations"][0]["observation"]["pathSafety"]["issues"][0]["code"], "CASE_MISMATCH")
        self.assertEqual(report["recovery"]["decision"], "PATH_POLICY_BLOCKED")

    def test_target_mismatch_has_precedence_over_recovery(self):
        journal = self.make_journal("COMMITTING")
        current = self.current_target(journal)
        current["steamBuildId"] = "99999999"
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "after-op0")
            report = inspect_transaction_recovery(journal, root, current, inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "TARGET_MISMATCH")

    def test_rollback_required_lists_after_states_in_reverse_order(self):
        journal = self.make_journal("ROLLBACK_REQUIRED")
        for op in journal["operations"]:
            op["status"] = "APPLIED"
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "all-after")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"], {"decision": "ROLLBACK_REQUIRED", "rollbackSequences": [2, 1, 0]})

    def test_committed_all_after_is_terminal_consistent(self):
        journal = self.make_journal("COMMITTED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "all-after")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "TERMINAL_COMMITTED")


    def test_prepared_after_state_requires_recovery(self):
        journal = self.make_journal("PREPARED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "after-op0")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "RECOVERY_REQUIRED")

    def test_verifying_all_after_is_ready_to_verify(self):
        journal = self.make_journal("VERIFYING")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "all-after")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "READY_TO_VERIFY")

    def test_rollback_complete_when_every_operation_is_before(self):
        journal = self.make_journal("ROLLBACK_REQUIRED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "ROLLBACK_COMPLETE")

    def test_foreign_incident_does_not_silently_resume_when_foreign_state_disappears(self):
        journal = self.make_journal("FOREIGN_MODIFICATION")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "RECOVERY_REQUIRED")

    def test_failed_phase_is_terminal(self):
        journal = self.make_journal("FAILED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "TERMINAL_FAILED")

    def test_committed_drift_is_foreign_modification(self):
        journal = self.make_journal("COMMITTED")
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["recovery"]["decision"], "FOREIGN_MODIFICATION")

    def test_missing_ancestor_is_path_policy_blocked(self):
        journal = self.make_journal("PLANNED")
        journal["operations"][1]["path"] = "MissingParent/b.txt"
        with tempfile.TemporaryDirectory() as td:
            root = self.build_root(td, "before")
            report = inspect_transaction_recovery(journal, root, self.current_target(journal), inspected_at="2026-09-30T07:30:00Z")
        self.validate_report(report)
        self.assertEqual(report["operations"][1]["observation"]["pathSafety"]["issues"][0]["code"], "ANCESTOR_MISSING")
        self.assertEqual(report["recovery"]["decision"], "PATH_POLICY_BLOCKED")

    def test_cli_writes_only_outside_game_root(self):
        journal = self.make_journal("PLANNED")
        current = self.current_target(journal)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            root = self.build_root(td, "before")
            journal_path = td_path / "journal.json"
            target_path = td_path / "game-target.json"
            output_path = td_path / "report.json"
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            target_path.write_text(json.dumps(current), encoding="utf-8")
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            cmd = [
                sys.executable,
                str(ROOT / "tools" / "gp1" / "transaction-recovery-inspector" / "smml_transaction_recovery_inspector.py"),
                "--journal", str(journal_path),
                "--game-root", str(root),
                "--game-target", str(target_path),
                "--output", str(output_path),
            ]
            run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stdout + run.stderr)
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.validate_report(report)

            forbidden = root / "recovery-report.json"
            cmd[-1] = str(forbidden)
            blocked = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1)
            self.assertFalse(forbidden.exists())

            if hasattr(os, "symlink"):
                link_output = td_path / "report-link.json"
                try:
                    os.symlink(root / "would-be-report.json", link_output)
                except OSError:
                    pass
                else:
                    cmd[-1] = str(link_output)
                    linked = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(linked.returncode, 1)
                    self.assertFalse((root / "would-be-report.json").exists())


if __name__ == "__main__":
    unittest.main()
