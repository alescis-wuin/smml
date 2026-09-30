from __future__ import annotations

import copy
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

from smml_reference.hashing import sha256_bytes  # noqa: E402
from smml_reference.transaction_store import (  # noqa: E402
    InjectedTransactionFault,
    JournalStore,
    StagingStore,
    TransactionStoreError,
    validate_staging_manifest_semantics,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fault_at(wanted: str):
    def inject(point: str):
        if point == wanted:
            raise InjectedTransactionFault(point)
    return inject


class TransactionStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_json(ROOT / "examples" / "transaction-journal.valid.planned.json")
        cls.staging_schema = load_json(ROOT / "schemas" / "smml.transaction-staging-manifest-1.schema.json")
        Draft202012Validator.check_schema(cls.staging_schema)
        cls.staging_validator = Draft202012Validator(cls.staging_schema)

    def make_plan(self):
        plan = copy.deepcopy(self.base)
        plan["transactionId"] = "tx-store-test"
        plan["operations"] = [
            {
                "operationId": "op-create",
                "sequence": 0,
                "path": "Data/new.txt",
                "kind": "create",
                "owner": "test",
                "before": {"exists": False},
                "after": {"exists": True, "sha256": sha256_bytes(b"new\n")},
                "status": "PENDING",
            }
        ]
        return plan

    def make_prepared(self, plan):
        prepared = copy.deepcopy(plan)
        prepared["journalRevision"] = 1
        prepared["phase"] = "PREPARED"
        prepared["updatedAt"] = "2026-09-29T16:00:01Z"
        prepared["phaseHistory"].append({
            "revision": 1,
            "at": "2026-09-29T16:00:01Z",
            "phase": "PREPARED",
        })
        return prepared

    def make_manifest(self, prepared):
        digest = prepared["operations"][0]["after"]["sha256"]
        return {
            "schema": "smml.transaction-staging-manifest/1",
            "transactionId": prepared["transactionId"],
            "journalRevision": prepared["journalRevision"],
            "contentAlgorithm": "sha256",
            "layout": "sha256-prefix-v1",
            "operations": [{
                "operationId": "op-create",
                "sequence": 0,
                "path": "Data/new.txt",
                "before": {"exists": False},
                "after": {"exists": True, "sha256": digest, "size": 4},
            }],
            "blobs": [{"sha256": digest, "size": 4}],
        }

    def test_staging_manifest_schema_and_semantics(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        manifest = self.make_manifest(prepared)
        self.staging_validator.validate(manifest)
        validate_staging_manifest_semantics(manifest, prepared)

    def test_staging_manifest_rejects_unreferenced_blob(self):
        prepared = self.make_prepared(self.make_plan())
        manifest = self.make_manifest(prepared)
        manifest["blobs"].append({"sha256": "f" * 64, "size": 1})
        with self.assertRaises(ValueError):
            validate_staging_manifest_semantics(manifest, prepared)

    def test_staging_blob_is_content_addressed_and_idempotent(self):
        payload = b"new\n"
        digest = sha256_bytes(payload)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = StagingStore(state, "tx-store-test")
            first = store.put_bytes(payload, digest)
            second = store.put_bytes(payload, digest)
            self.assertEqual(first, second)
            path = store.blob_path(digest)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(path.relative_to(state).as_posix(), f"transactions/tx-store-test/staging/blobs/sha256/{digest[:2]}/{digest}")

    def test_staging_rejects_wrong_expected_digest(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = StagingStore(state, "tx-store-test")
            with self.assertRaises(TransactionStoreError) as ctx:
                store.put_bytes(b"new\n", "0" * 64)
            self.assertEqual(ctx.exception.code, "TXS_STAGED_DIGEST_MISMATCH")

    def test_staging_detects_corrupt_existing_blob(self):
        payload = b"new\n"
        digest = sha256_bytes(payload)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = StagingStore(state, "tx-store-test")
            path = store.blob_path(digest)
            path.write_bytes(b"corrupt")
            with self.assertRaises(TransactionStoreError) as ctx:
                store.put_bytes(payload, digest)
            self.assertEqual(ctx.exception.code, "TXS_STAGED_BLOB_CORRUPT")

    def test_journal_initialize_and_rewrite(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            self.assertEqual(store.initialize(plan), plan)
            self.assertEqual(store.rewrite(prepared), prepared)
            self.assertEqual(store.load()["phase"], "PREPARED")

    def test_journal_rewrite_requires_exact_revision_increment(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        prepared["journalRevision"] = 2
        prepared["phaseHistory"][-1]["revision"] = 2
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            store.initialize(plan)
            with self.assertRaises(TransactionStoreError) as ctx:
                store.rewrite(prepared)
            self.assertEqual(ctx.exception.code, "TXS_JOURNAL_REVISION")

    def test_journal_rewrite_rejects_operation_change(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        prepared["operations"][0]["owner"] = "other"
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            store.initialize(plan)
            with self.assertRaises(TransactionStoreError) as ctx:
                store.rewrite(prepared)
            self.assertEqual(ctx.exception.code, "TXS_JOURNAL_IMMUTABLE")

    def test_fault_after_temp_fsync_keeps_previous_complete_journal(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            store.initialize(plan)
            with self.assertRaises(InjectedTransactionFault):
                store.rewrite(prepared, fault_injector=fault_at("journal.rewrite.after_temp_fsync"))
            self.assertEqual(store.load(), plan)

    def test_fault_after_replace_exposes_complete_new_journal(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            store.initialize(plan)
            with self.assertRaises(InjectedTransactionFault):
                store.rewrite(prepared, fault_injector=fault_at("journal.rewrite.after_replace"))
            self.assertEqual(store.load(), prepared)

    def test_journal_reader_rejects_symlink(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = JournalStore(state, plan["transactionId"])
            outside = Path(td) / "outside.json"
            outside.write_text(json.dumps(plan), encoding="utf-8")
            os.symlink(outside, store.path)
            with self.assertRaises(TransactionStoreError) as ctx:
                store.load()
            self.assertEqual(ctx.exception.code, "TXS_FILE_UNSAFE")

    def test_staging_manifest_fault_never_publishes_partial_json(self):
        plan = self.make_plan()
        prepared = self.make_prepared(plan)
        manifest = self.make_manifest(prepared)
        payload = b"new\n"
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            store = StagingStore(state, plan["transactionId"])
            store.put_bytes(payload, sha256_bytes(payload))
            with self.assertRaises(InjectedTransactionFault):
                store.write_manifest(
                    manifest,
                    journal=prepared,
                    fault_injector=fault_at("staging.manifest.after_temp_fsync"),
                )
            self.assertFalse(store.manifest_path.exists())
            store.write_manifest(manifest, journal=prepared)
            self.assertEqual(store.load_manifest(journal=prepared), manifest)

    def test_blob_fault_after_temp_fsync_is_retryable(self):
        payload = b"streamed\n"
        digest = sha256_bytes(payload)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state = base / "state"
            state.mkdir()
            source = base / "source.bin"
            source.write_bytes(payload)
            store = StagingStore(state, "tx-store-test")
            with source.open("rb") as handle:
                with self.assertRaises(InjectedTransactionFault):
                    store.put_fd(handle.fileno(), digest, fault_injector=fault_at("staging.blob.after_temp_fsync"))
            self.assertFalse(store.blob_path(digest).exists())
            with source.open("rb") as handle:
                record = store.put_fd(handle.fileno(), digest)
            self.assertEqual(record, {"sha256": digest, "size": len(payload)})

    def test_blob_fault_after_replace_leaves_complete_blob(self):
        payload = b"streamed\n"
        digest = sha256_bytes(payload)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state = base / "state"
            state.mkdir()
            source = base / "source.bin"
            source.write_bytes(payload)
            store = StagingStore(state, "tx-store-test")
            with source.open("rb") as handle:
                with self.assertRaises(InjectedTransactionFault):
                    store.put_fd(handle.fileno(), digest, fault_injector=fault_at("staging.blob.after_replace"))
            self.assertEqual(store.blob_path(digest).read_bytes(), payload)

    def test_state_root_symlink_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            real = base / "real"
            real.mkdir()
            link = base / "state"
            os.symlink(real, link)
            with self.assertRaises(TransactionStoreError) as ctx:
                JournalStore(link, "tx-store-test")
            self.assertEqual(ctx.exception.code, "TXS_DIRECTORY_UNSAFE")



if __name__ == "__main__":
    unittest.main()
