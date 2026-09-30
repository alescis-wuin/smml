#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

from smml_reference.game_target_inspector import (  # noqa: E402
    InspectorError,
    inspect_game_target,
    load_json,
    validate_inspection_plan,
)


def _output_inside_game_root(output: Path, game_root: Path) -> bool:
    try:
        output.resolve().relative_to(game_root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only SMML GameTargetInspector reference implementation."
    )
    parser.add_argument("game_root", type=Path, help="Scrap Mechanic installation root")
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "policies" / "smml.game-target-inspection-plan-1.json",
        help="versioned inspection plan",
    )
    parser.add_argument(
        "--canonical-policy",
        type=Path,
        default=ROOT / "policies" / "smml.canonical-game-policy-1.json",
    )
    parser.add_argument("--appmanifest", type=Path, help="Steam appmanifest override")
    parser.add_argument(
        "--compatibility-layer",
        choices=["none", "proton", "wine", "other"],
        help="required when host OS differs from game OS",
    )
    parser.add_argument("--compatibility-version")
    parser.add_argument("--output", "-o", type=Path, help="write JSON outside the game root; default stdout")
    args = parser.parse_args()

    try:
        plan = load_json(args.plan)
        canonical_policy = load_json(args.canonical_policy)
        validate_inspection_plan(plan)

        plan_schema = load_json(ROOT / "schemas" / "smml.game-target-inspection-plan-1.schema.json")
        canonical_schema = load_json(ROOT / "schemas" / "smml.canonical-game-policy-1.schema.json")
        game_target_schema = load_json(ROOT / "schemas" / "smml.game-target-1.schema.json")
        Draft202012Validator.check_schema(plan_schema)
        Draft202012Validator(plan_schema).validate(plan)
        Draft202012Validator(canonical_schema).validate(canonical_policy)

        if args.output and _output_inside_game_root(args.output, args.game_root):
            raise InspectorError("GTI_OUTPUT_INSIDE_GAME_ROOT", str(args.output))

        identity = inspect_game_target(
            args.game_root,
            plan=plan,
            canonical_policy=canonical_policy,
            appmanifest_path=args.appmanifest,
            compatibility_layer=args.compatibility_layer,
            compatibility_version=args.compatibility_version,
        )
        Draft202012Validator(game_target_schema).validate(identity)

        encoded = json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            tmp = args.output.with_name(args.output.name + ".tmp")
            tmp.write_text(encoded, encoding="utf-8", newline="\n")
            os.replace(tmp, args.output)
            print(f"[OK] GameTargetIdentity written to {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(encoded)
        return 0
    except (InspectorError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
