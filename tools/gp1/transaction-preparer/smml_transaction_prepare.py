#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ModuleNotFoundError as exc:
    print(
        "[ERROR] Missing runtime dependency. Run `python -m pip install -r requirements.txt` "
        "or `make setup` from the repository root.",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from smml_reference.game_target_identity import validate_semantics as validate_game_target_semantics  # noqa: E402
from smml_reference.transaction_engine import TransactionEngineError, prepare_transaction  # noqa: E402
from smml_reference.transaction_journal import validate_transaction_journal_semantics  # noqa: E402
from smml_reference.transaction_store import TransactionStoreError  # noqa: E402


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def validate_inputs(journal: dict, game_target: dict) -> None:
    game_schema = load_json(ROOT / "schemas" / "smml.game-target-1.schema.json")
    tx_schema = load_json(ROOT / "schemas" / "smml.transaction-journal-1.schema.json")
    registry = Registry().with_resource(game_schema["$id"], Resource.from_contents(game_schema))
    Draft202012Validator(game_schema).validate(game_target)
    Draft202012Validator(tx_schema, registry=registry).validate(journal)
    validate_game_target_semantics(game_target)
    validate_transaction_journal_semantics(journal)
    if journal["phase"] != "PLANNED":
        raise ValueError("--journal-plan must be a PLANNED TransactionJournal")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a transaction durably outside the game root without mutating the game installation."
    )
    parser.add_argument("--journal-plan", required=True, type=Path, help="PLANNED TransactionJournal v1")
    parser.add_argument("--game-root", required=True, type=Path)
    parser.add_argument("--game-target", required=True, type=Path, help="Fresh GameTargetIdentity for --game-root")
    parser.add_argument(
        "--after-root",
        type=Path,
        help="Read-only desired output tree. Required when any operation has after.exists=true.",
    )
    parser.add_argument(
        "--state-root",
        required=True,
        type=Path,
        help="Existing trusted SMML state directory outside --game-root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.journal_plan)
        target = load_json(args.game_target)
        validate_inputs(plan, target)
        result = prepare_transaction(
            plan,
            game_root=args.game_root,
            current_game_target=target,
            state_root=args.state_root,
            after_root=args.after_root,
        )
        tx_root = args.state_root / "transactions" / result["transactionId"]
        print(
            f"[OK] transaction {result['transactionId']} phase={result['phase']} "
            f"revision={result['journalRevision']} idempotent={str(result['idempotent']).lower()}"
        )
        print(
            f"[OK] staged blobs={result['blobCount']} totalBytes={result['totalStagedBytes']}"
        )
        print(f"[OK] durable journal: {tx_root / 'journal.json'}")
        print(f"[OK] staging manifest: {tx_root / 'staging' / 'manifest.json'}")
        print("[INFO] game root was read-only; no commit or rollback was executed")
        return 0
    except (ValueError, TransactionEngineError, TransactionStoreError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
