#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXAMPLES = ROOT / "examples"
CASES_PATH = HERE / "cases.json"

sys.path.insert(0, str(HERE))
from transaction_journal_validation import (  # noqa: E402
    TransactionJournalSemanticError,
    validate_transaction_journal_semantics,
)
from package_manifest_validation import (  # noqa: E402
    PackageManifestSemanticError,
    validate_package_manifest_semantics,
)
from contract_descriptor_validation import (  # noqa: E402
    ContractDescriptorSemanticError,
    validate_contract_descriptor_semantics,
)
from hook_pack_manifest_validation import (  # noqa: E402
    HookPackManifestSemanticError,
    validate_hook_pack_manifest_semantics,
)
from validation import SemanticValidationError, validate_policy_semantics, validate_semantics  # noqa: E402
from profile_validation import ProfileSemanticError, validate_profile_semantics  # noqa: E402
from lockfile_validation import LockfileSemanticError, validate_lockfile_semantics  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    game_schema = load_json(ROOT / "schemas" / "smml.game-target-1.schema.json")
    game_validator = Draft202012Validator(game_schema)

    tx_schema = load_json(ROOT / "schemas" / "smml.transaction-journal-1.schema.json")
    registry = Registry().with_resource(game_schema["$id"], Resource.from_contents(game_schema))
    tx_validator = Draft202012Validator(tx_schema, registry=registry)

    package_schema = load_json(ROOT / "schemas" / "smml.package-manifest-1.schema.json")
    package_validator = Draft202012Validator(package_schema)

    contract_schema = load_json(ROOT / "schemas" / "smml.contract-descriptor-1.schema.json")
    contract_validator = Draft202012Validator(contract_schema)

    hook_pack_schema = load_json(ROOT / "schemas" / "smml.hook-pack-manifest-1.schema.json")
    hook_pack_validator = Draft202012Validator(hook_pack_schema)

    profile_schema = load_json(ROOT / "schemas" / "smml.profile-1.schema.json")
    profile_validator = Draft202012Validator(profile_schema)

    lockfile_schema = load_json(ROOT / "schemas" / "smml.lockfile-1.schema.json")
    lockfile_validator = Draft202012Validator(lockfile_schema)

    for version in (1, 2):
        policy_schema = load_json(ROOT / "schemas" / f"smml.canonical-game-policy-{version}.schema.json")
        policy = load_json(ROOT / "policies" / f"smml.canonical-game-policy-{version}.json")
        Draft202012Validator.check_schema(policy_schema)
        Draft202012Validator(policy_schema).validate(policy)
        validate_policy_semantics(policy)
        print(f"PASS smml.canonical-game-policy/{version}")

    inspection_plan_schema = load_json(ROOT / "schemas" / "smml.game-target-inspection-plan-1.schema.json")
    inspection_plan = load_json(ROOT / "policies" / "smml.game-target-inspection-plan-1.json")
    Draft202012Validator.check_schema(inspection_plan_schema)
    Draft202012Validator(inspection_plan_schema).validate(inspection_plan)
    print("PASS smml.game-target-inspection-plan/1")

    path_policy_schema = load_json(ROOT / "schemas" / "smml.path-policy-1.schema.json")
    path_policy = load_json(ROOT / "policies" / "smml.path-policy-1.json")
    Draft202012Validator.check_schema(path_policy_schema)
    Draft202012Validator(path_policy_schema).validate(path_policy)
    print("PASS smml.path-policy/1")

    cases = load_json(CASES_PATH)
    failures = 0

    for case in cases:
        path = EXAMPLES / case["file"]
        document = load_json(path)
        schema_kind = case["schema"]

        if schema_kind == "game-target":
            validator = game_validator
            semantic_fn = validate_semantics
            semantic_error_type = SemanticValidationError
        elif schema_kind == "transaction-journal":
            validator = tx_validator
            semantic_fn = validate_transaction_journal_semantics
            semantic_error_type = TransactionJournalSemanticError
        elif schema_kind == "package-manifest":
            validator = package_validator
            semantic_fn = validate_package_manifest_semantics
            semantic_error_type = PackageManifestSemanticError
        elif schema_kind == "contract-descriptor":
            validator = contract_validator
            semantic_fn = validate_contract_descriptor_semantics
            semantic_error_type = ContractDescriptorSemanticError
        elif schema_kind == "hook-pack-manifest":
            validator = hook_pack_validator
            semantic_fn = validate_hook_pack_manifest_semantics
            semantic_error_type = HookPackManifestSemanticError
        elif schema_kind == "profile":
            validator = profile_validator
            semantic_fn = validate_profile_semantics
            semantic_error_type = ProfileSemanticError
        elif schema_kind == "lockfile":
            validator = lockfile_validator
            semantic_fn = validate_lockfile_semantics
            semantic_error_type = LockfileSemanticError
        else:
            print(f"FAIL {case['file']}: unknown schema kind {schema_kind!r}")
            failures += 1
            continue

        schema_errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
        semantic_error = None

        if not schema_errors:
            try:
                semantic_fn(document)
            except semantic_error_type as exc:
                semantic_error = exc

        actual_valid = not schema_errors and semantic_error is None
        expected_valid = bool(case["valid"])

        if actual_valid != expected_valid:
            failures += 1
            print(f"FAIL {case['file']}: expected valid={expected_valid}, got {actual_valid}")
            if schema_errors:
                print(f"  schema: {schema_errors[0].message}")
            if semantic_error:
                print(f"  semantic: {semantic_error}")
            continue

        if not expected_valid:
            expected_layer = case.get("failureLayer")
            actual_layer = "schema" if schema_errors else "semantic"
            if actual_layer != expected_layer:
                failures += 1
                print(f"FAIL {case['file']}: expected failure layer {expected_layer}, got {actual_layer}")
                continue

        print(f"PASS {case['file']}")

    if failures:
        print(f"\n{failures} failure(s)")
        return 1

    print(f"\nAll {len(cases)} example cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
