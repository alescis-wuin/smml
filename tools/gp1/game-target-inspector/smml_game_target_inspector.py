#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError as exc:
    if exc.name == "jsonschema":
        raise SystemExit(
            "Missing runtime dependency 'jsonschema'. "
            "Run 'python3 -m pip install -r requirements.txt' or 'make setup'."
        ) from None
    raise

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "reference" / "python"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

from smml_reference.game_target_inspector import (  # noqa: E402
    InspectorError,
    inspect_game_target,
    known_canonical_fingerprints,
    load_json,
    validate_inspection_plan,
)
from smml_reference.inventory import (  # noqa: E402
    InventoryError,
    build_file_inventory,
    compare_file_inventories,
    load_json_document,
    slice_inventory,
    validate_file_inventory,
    write_json_document,
)


def _output_inside_game_root(output: Path, game_root: Path) -> bool:
    try:
        output.resolve().relative_to(game_root.resolve())
        return True
    except ValueError:
        return False


def _canonical_policy_path(policy_id: str) -> Path:
    mapping = {
        "smml.canonical-game-policy/1": ROOT / "policies" / "smml.canonical-game-policy-1.json",
        "smml.canonical-game-policy/2": ROOT / "policies" / "smml.canonical-game-policy-2.json",
    }
    try:
        return mapping[policy_id]
    except KeyError:
        raise InspectorError("GTI_PLAN_INVALID", f"unsupported canonical policy {policy_id!r}") from None


def _canonical_policy_schema_path(policy_id: str) -> Path:
    mapping = {
        "smml.canonical-game-policy/1": ROOT / "schemas" / "smml.canonical-game-policy-1.schema.json",
        "smml.canonical-game-policy/2": ROOT / "schemas" / "smml.canonical-game-policy-2.schema.json",
    }
    try:
        return mapping[policy_id]
    except KeyError:
        raise InspectorError("GTI_PLAN_INVALID", f"unsupported canonical policy {policy_id!r}") from None


def _matching_build(plan: dict, identity: dict) -> dict:
    matches = [
        build
        for build in plan["builds"]
        if build["steamBuildId"] == identity["steamBuildId"]
        and build["steamBranch"] == identity["steamBranch"]
    ]
    if len(matches) != 1:
        raise InspectorError("GTI_PLAN_INVALID", "cannot resolve unique build record after inspection")
    return matches[0]


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
        help="canonical policy override; default is selected by the inspection plan",
    )
    parser.add_argument("--appmanifest", type=Path, help="Steam appmanifest override")
    parser.add_argument(
        "--compatibility-layer",
        choices=["none", "proton", "wine", "other"],
        help="required when host OS differs from game OS",
    )
    parser.add_argument("--compatibility-version")
    parser.add_argument("--output", "-o", type=Path, help="write GameTargetIdentity JSON outside the game root; default stdout")
    parser.add_argument(
        "--inventory-output",
        type=Path,
        help="optional complete file inventory (.json or deterministic .json.gz), outside the game root",
    )
    parser.add_argument(
        "--cache-diff-output",
        type=Path,
        help="optional Cache/ diff against the GP0 B0 baseline inventory",
    )
    parser.add_argument(
        "--baseline-inventory",
        type=Path,
        default=ROOT / "evidence" / "gp0" / "baselines" / "b0-file-inventory.json.gz",
        help="baseline inventory used by --cache-diff-output",
    )
    parser.add_argument(
        "--require-known-canonical",
        action="store_true",
        help="fail if the computed canonical fingerprint is not a known fingerprint for the build",
    )
    args = parser.parse_args()

    try:
        plan = load_json(args.plan)
        validate_inspection_plan(plan)
        policy_path = args.canonical_policy or _canonical_policy_path(plan["canonicalPolicy"])
        canonical_policy = load_json(policy_path)

        plan_schema = load_json(ROOT / "schemas" / "smml.game-target-inspection-plan-1.schema.json")
        canonical_schema = load_json(_canonical_policy_schema_path(canonical_policy.get("schema", "")))
        game_target_schema = load_json(ROOT / "schemas" / "smml.game-target-1.schema.json")
        inventory_schema = load_json(ROOT / "schemas" / "smml.file-inventory-1.schema.json")
        diff_schema = load_json(ROOT / "schemas" / "smml.file-inventory-diff-1.schema.json")
        Draft202012Validator.check_schema(plan_schema)
        Draft202012Validator.check_schema(canonical_schema)
        Draft202012Validator.check_schema(inventory_schema)
        Draft202012Validator.check_schema(diff_schema)
        Draft202012Validator(plan_schema).validate(plan)
        Draft202012Validator(canonical_schema).validate(canonical_policy)

        for output in (args.output, args.inventory_output, args.cache_diff_output):
            if output and _output_inside_game_root(output, args.game_root):
                raise InspectorError("GTI_OUTPUT_INSIDE_GAME_ROOT", str(output))

        inventory_records: list[dict] = []
        identity = inspect_game_target(
            args.game_root,
            plan=plan,
            canonical_policy=canonical_policy,
            appmanifest_path=args.appmanifest,
            compatibility_layer=args.compatibility_layer,
            compatibility_version=args.compatibility_version,
            inventory_records=inventory_records,
        )
        Draft202012Validator(game_target_schema).validate(identity)

        target = {
            "steamAppId": identity["steamAppId"],
            "steamBuildId": identity["steamBuildId"],
            "steamBranch": identity["steamBranch"],
        }
        inventory = build_file_inventory(inventory_records, target=target)
        Draft202012Validator(inventory_schema).validate(inventory)
        validate_file_inventory(inventory)

        if args.inventory_output:
            write_json_document(args.inventory_output, inventory)
            print(f"[OK] File inventory written to {args.inventory_output}", file=sys.stderr)

        known = known_canonical_fingerprints(plan, identity)
        observed = identity["fingerprints"]["canonicalGameFingerprint"]["sha256"]
        if known:
            if observed in known:
                print(f"[OK] canonical fingerprint matches known baseline: {observed}", file=sys.stderr)
            else:
                print(
                    f"[WARN] canonical fingerprint is not a known baseline: {observed}; expected one of {list(known)!r}",
                    file=sys.stderr,
                )
                if args.require_known_canonical:
                    raise InspectorError("GTI_CANONICAL_MISMATCH", observed)

        if args.cache_diff_output:
            baseline = load_json_document(args.baseline_inventory)
            Draft202012Validator(inventory_schema).validate(baseline)
            validate_file_inventory(baseline)
            baseline_cache = slice_inventory(baseline, "Cache/")
            current_cache = slice_inventory(inventory, "Cache/")
            build = _matching_build(plan, identity)
            diff = compare_file_inventories(
                baseline_cache,
                current_cache,
                classification="rebuildable-cache",
                strict_target_paths=build["targetFingerprints"],
            )
            Draft202012Validator(diff_schema).validate(diff)
            write_json_document(args.cache_diff_output, diff, pretty=True)
            summary = diff["summary"]
            print(
                "[OK] Cache diff written to "
                f"{args.cache_diff_output}: +{summary['added']} -{summary['removed']} ~{summary['modified']}",
                file=sys.stderr,
            )

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
    except (InspectorError, InventoryError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
