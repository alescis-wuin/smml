from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

from smml_reference.hashing import sha256_bytes  # noqa: E402
from smml_reference.transaction_engine import TransactionEngineError, prepare_transaction  # noqa: E402
from smml_reference.transaction_store import InjectedTransactionFault, JournalStore, StagingStore  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fault_at(wanted: str):
    def inject(point: str):
        if point == wanted:
            raise InjectedTransactionFault(point)
    return inject


BEFORE_A = b"alpha-before\n"
AFTER_A = b"alpha-after\n"
AFTER_B = b"bravo-created\n"
BEFORE_C = b"charlie-before\n"


class TransactionEnginePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_json(ROOT / "examples" / "transaction-journal.valid.planned.json")

    def make_plan(self):
        doc = copy.deepcopy(self.base)
        doc["transactionId"] = "tx-engine-test"
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
        return doc

    def build_roots(self, td: str):
        base = Path(td)
        game = base / "game"
        desired = base / "desired"
        state = base / "state"
        (game / "Data").mkdir(parents=True)
        (desired / "Data").mkdir(parents=True)
        state.mkdir()
        (game / "Data" / "a.txt").write_bytes(BEFORE_A)
        (game / "Data" / "c.txt").write_bytes(BEFORE_C)
        (desired / "Data" / "a.txt").write_bytes(AFTER_A)
        (desired / "Data" / "b.txt").write_bytes(AFTER_B)
        return game, desired, state

    def snapshot(self, root: Path):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def current_target(self, plan):
        current = copy.deepcopy(plan["gameTarget"])
        current["fingerprints"]["installationExactFingerprint"]["sha256"] = "0" * 64
        for root in current["fingerprints"]["rootFingerprints"]:
            if root["path"] == "Cache":
                root["sha256"] = "1" * 64
        return current

    def prepare(self, plan, game, desired, state, **kwargs):
        return prepare_transaction(
            plan,
            game_root=game,
            current_game_target=self.current_target(plan),
            state_root=state,
            after_root=desired,
            prepared_at="2026-09-30T08:00:00Z",
            **kwargs,
        )

    def test_prepare_stages_before_and_after_without_mutating_game(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            before = self.snapshot(game)
            result = self.prepare(plan, game, desired, state)
            after = self.snapshot(game)
            self.assertEqual(before, after)
            self.assertEqual(result["phase"], "PREPARED")
            self.assertEqual(result["journalRevision"], 1)
            self.assertFalse(result["idempotent"])
            self.assertEqual(result["blobCount"], 4)

            journal = JournalStore(state, plan["transactionId"]).load()
            self.assertEqual(journal["phase"], "PREPARED")
            self.assertTrue(all(op["status"] == "PENDING" for op in journal["operations"]))
            manifest = StagingStore(state, plan["transactionId"]).load_manifest(journal=journal)
            self.assertEqual(len(manifest["blobs"]), 4)

    def test_prepare_is_idempotent_after_prepared(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            first = self.prepare(plan, game, desired, state)
            second = self.prepare(plan, game, desired, state)
            self.assertFalse(first["idempotent"])
            self.assertTrue(second["idempotent"])
            self.assertEqual(second["journalRevision"], 1)

    def test_delete_only_plan_does_not_require_after_root(self):
        plan = self.make_plan()
        plan["operations"] = [copy.deepcopy(plan["operations"][2])]
        plan["operations"][0]["sequence"] = 0
        with tempfile.TemporaryDirectory() as td:
            game, _, state = self.build_roots(td)
            result = prepare_transaction(
                plan,
                game_root=game,
                current_game_target=self.current_target(plan),
                state_root=state,
                after_root=None,
                prepared_at="2026-09-30T08:00:00Z",
            )
            self.assertEqual(result["phase"], "PREPARED")
            self.assertEqual(result["blobCount"], 1)


    def test_target_mismatch_writes_no_transaction_state(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            current = self.current_target(plan)
            current["steamBuildId"] = "999999"
            with self.assertRaises(TransactionEngineError) as ctx:
                prepare_transaction(
                    plan,
                    game_root=game,
                    current_game_target=current,
                    state_root=state,
                    after_root=desired,
                )
            self.assertEqual(ctx.exception.code, "TXE_TARGET_MISMATCH")
            self.assertFalse((state / "transactions").exists())

    def test_before_precondition_must_match_live_game(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            (game / "Data" / "a.txt").write_bytes(b"foreign\n")
            with self.assertRaises(TransactionEngineError) as ctx:
                self.prepare(plan, game, desired, state)
            self.assertEqual(ctx.exception.code, "TXE_PRECONDITION_FAILED")
            journal = JournalStore(state, plan["transactionId"]).load()
            self.assertEqual(journal["phase"], "PLANNED")

    def test_after_source_digest_must_match_plan(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            (desired / "Data" / "a.txt").write_bytes(b"wrong\n")
            with self.assertRaises(Exception) as ctx:
                self.prepare(plan, game, desired, state)
            self.assertIn("DIGEST_MISMATCH", str(ctx.exception))
            self.assertEqual(JournalStore(state, plan["transactionId"]).load()["phase"], "PLANNED")

    def test_state_root_inside_game_is_rejected_before_writes(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, _ = self.build_roots(td)
            state = game / "SMML-state"
            state.mkdir()
            with self.assertRaises(TransactionEngineError) as ctx:
                self.prepare(plan, game, desired, state)
            self.assertEqual(ctx.exception.code, "TXE_STATE_ROOT_IN_GAME")

    def test_after_root_inside_game_is_rejected(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, _, state = self.build_roots(td)
            desired = game / "desired"
            (desired / "Data").mkdir(parents=True)
            with self.assertRaises(TransactionEngineError) as ctx:
                self.prepare(plan, game, desired, state)
            self.assertEqual(ctx.exception.code, "TXE_AFTER_ROOT_IN_GAME")

    def test_symlink_after_source_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            target = Path(td) / "outside.txt"
            target.write_bytes(AFTER_A)
            (desired / "Data" / "a.txt").unlink()
            os.symlink(target, desired / "Data" / "a.txt")
            with self.assertRaises(TransactionEngineError) as ctx:
                self.prepare(plan, game, desired, state)
            self.assertEqual(ctx.exception.code, "TXE_SOURCE_UNSAFE")

    def test_fault_after_staging_manifest_resumes_from_planned(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            before = self.snapshot(game)
            with self.assertRaises(InjectedTransactionFault):
                self.prepare(
                    plan,
                    game,
                    desired,
                    state,
                    fault_injector=fault_at("engine.after_staging_manifest"),
                )
            self.assertEqual(JournalStore(state, plan["transactionId"]).load()["phase"], "PLANNED")
            result = self.prepare(plan, game, desired, state)
            self.assertEqual(result["phase"], "PREPARED")
            self.assertEqual(before, self.snapshot(game))

    def test_fault_after_prepared_replace_is_recoverable_as_prepared(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            with self.assertRaises(InjectedTransactionFault):
                self.prepare(
                    plan,
                    game,
                    desired,
                    state,
                    fault_injector=fault_at("journal.rewrite.after_replace"),
                )
            self.assertEqual(JournalStore(state, plan["transactionId"]).load()["phase"], "PREPARED")
            result = self.prepare(plan, game, desired, state)
            self.assertTrue(result["idempotent"])

    def test_fault_before_initial_journal_publication_can_retry(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            with self.assertRaises(InjectedTransactionFault):
                self.prepare(
                    plan,
                    game,
                    desired,
                    state,
                    fault_injector=fault_at("journal.initialize.after_temp_fsync"),
                )
            store = JournalStore(state, plan["transactionId"])
            self.assertFalse(store.path.exists())
            result = self.prepare(plan, game, desired, state)
            self.assertEqual(result["phase"], "PREPARED")

    def test_persisted_plan_mismatch_is_rejected(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            self.prepare(plan, game, desired, state)
            changed = copy.deepcopy(plan)
            changed["operations"][0]["owner"] = "different"
            with self.assertRaises(TransactionEngineError) as ctx:
                self.prepare(changed, game, desired, state)
            self.assertEqual(ctx.exception.code, "TXE_PERSISTED_PLAN_MISMATCH")

    def test_cli_prepares_without_mutating_game_root(self):
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            game, desired, state = self.build_roots(td)
            base = Path(td)
            plan_path = base / "plan.json"
            target_path = base / "game-target.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            target_path.write_text(json.dumps(self.current_target(plan)), encoding="utf-8")
            before = self.snapshot(game)
            cmd = [
                sys.executable,
                str(ROOT / "tools" / "gp1" / "transaction-preparer" / "smml_transaction_prepare.py"),
                "--journal-plan", str(plan_path),
                "--game-root", str(game),
                "--game-target", str(target_path),
                "--after-root", str(desired),
                "--state-root", str(state),
            ]
            run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stdout + run.stderr)
            self.assertIn("phase=PREPARED", run.stdout)
            self.assertIn("game root was read-only", run.stdout)
            self.assertEqual(before, self.snapshot(game))
            stored = JournalStore(state, plan["transactionId"]).load()
            self.assertEqual(stored["phase"], "PREPARED")



if __name__ == "__main__":
    unittest.main()
