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
from smml_reference.transaction_journal import validate_transaction_journal_semantics  # noqa: E402
from smml_reference.transaction_runtime import (  # noqa: E402
    TransactionRuntimeError,
    dump_report_bytes,
    inspect_transaction_recovery,
    path_is_within,
    validate_transaction_recovery_report_semantics,
)


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


def validate_report(report: dict) -> None:
    schema = load_json(ROOT / "schemas" / "smml.transaction-recovery-report-1.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    validate_transaction_recovery_report_semantics(report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect TransactionJournal recovery state without mutating the game root."
    )
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--game-root", required=True, type=Path)
    parser.add_argument("--game-target", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optional report path outside the game root; defaults to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        journal_path = Path(args.journal)
        game_target_path = Path(args.game_target)
        journal = load_json(journal_path)
        game_target = load_json(game_target_path)
        validate_inputs(journal, game_target)

        if args.output is not None:
            output = Path(args.output)
            if path_is_within(args.game_root, output):
                raise ValueError("--output must be outside --game-root in read-only mode")
            if output.is_symlink():
                raise ValueError("--output must not be a symlink")
            output_resolved = output.resolve(strict=False)
            if output_resolved in {journal_path.resolve(strict=False), game_target_path.resolve(strict=False)}:
                raise ValueError("--output must not overwrite --journal or --game-target")

        report = inspect_transaction_recovery(journal, args.game_root, game_target)
        validate_report(report)
        payload = dump_report_bytes(report)

        if args.output is None:
            sys.stdout.buffer.write(payload)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
            print(f"[OK] Transaction recovery report written to {output}")

        decision = report["recovery"]["decision"]
        print(
            f"[INFO] read-only decision={decision} "
            f"before={report['summary']['beforeCount']} "
            f"after={report['summary']['afterCount']} "
            f"foreign={report['summary']['foreignCount']} "
            f"unsafe={report['summary']['unsafePathCount']}",
            file=sys.stderr if args.output is None else sys.stdout,
        )
        if decision in {"TARGET_MISMATCH", "PATH_POLICY_BLOCKED", "FOREIGN_MODIFICATION", "RECOVERY_REQUIRED"}:
            return 2
        return 0
    except (ValueError, TransactionRuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # jsonschema ValidationError intentionally lands here with a clear type/message.
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
