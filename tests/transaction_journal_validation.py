from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from path_policy_validation import PathPolicyError, portable_collision_key, validate_logical_path

from validation import SemanticValidationError, validate_semantics as validate_game_target_semantics


class TransactionJournalSemanticError(ValueError):
    pass


NORMAL_PHASES = {"PLANNED", "PREPARED", "COMMITTING", "VERIFYING", "COMMITTED"}
INCIDENT_PHASES = {"RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED", "FAILED"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PLANNED": {"PREPARED", "FAILED"},
    "PREPARED": {"COMMITTING", "RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "FAILED"},
    "COMMITTING": {"VERIFYING", "RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED", "FAILED"},
    "VERIFYING": {"COMMITTED", "RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED", "FAILED"},
    "RECOVERY_REQUIRED": {"COMMITTING", "VERIFYING", "FOREIGN_MODIFICATION", "ROLLBACK_REQUIRED", "FAILED"},
    "FOREIGN_MODIFICATION": {"RECOVERY_REQUIRED", "ROLLBACK_REQUIRED", "FAILED"},
    "ROLLBACK_REQUIRED": {"RECOVERY_REQUIRED", "FOREIGN_MODIFICATION", "FAILED"},
    "COMMITTED": set(),
    "FAILED": set(),
}


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TransactionJournalSemanticError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise TransactionJournalSemanticError(f"timestamp must be UTC: {value!r}")
    return parsed


def _validate_relative_path(value: str) -> None:
    try:
        validate_logical_path(value)
    except PathPolicyError as exc:
        raise TransactionJournalSemanticError(str(exc)) from exc


def _validate_operation_shape(op: dict[str, Any]) -> None:
    before = op["before"]
    after = op["after"]
    kind = op["kind"]

    be = bool(before["exists"])
    ae = bool(after["exists"])

    expected = {
        (False, True): "create",
        (True, True): "replace",
        (True, False): "delete",
    }.get((be, ae))

    if expected is None:
        raise TransactionJournalSemanticError(
            f"operation {op['operationId']!r} has no mutation: before.exists={be}, after.exists={ae}"
        )
    if kind != expected:
        raise TransactionJournalSemanticError(
            f"operation {op['operationId']!r} kind={kind!r} does not match before/after; expected {expected!r}"
        )
    if kind == "replace" and before["sha256"] == after["sha256"]:
        raise TransactionJournalSemanticError(
            f"replace operation {op['operationId']!r} must change SHA-256"
        )


def _is_prefix(statuses: list[str], leading: str, trailing: str) -> bool:
    seen_trailing = False
    for status in statuses:
        if status == trailing:
            seen_trailing = True
        elif status == leading:
            if seen_trailing:
                return False
        else:
            return False
    return True


def validate_transaction_journal_semantics(document: dict[str, Any]) -> None:
    try:
        validate_game_target_semantics(document["gameTarget"])
    except SemanticValidationError as exc:
        raise TransactionJournalSemanticError(f"embedded gameTarget semantic error: {exc}") from exc

    revision = int(document["journalRevision"])
    phase = document["phase"]
    operations = document["operations"]

    created = _parse_utc(document["createdAt"])
    updated = _parse_utc(document["updatedAt"])
    if updated < created:
        raise TransactionJournalSemanticError("updatedAt must not be before createdAt")

    operation_ids: set[str] = set()
    path_keys: dict[str, str] = {}
    for index, op in enumerate(operations):
        operation_id = op["operationId"]
        if operation_id in operation_ids:
            raise TransactionJournalSemanticError(f"duplicate operationId: {operation_id!r}")
        operation_ids.add(operation_id)

        if op["sequence"] != index:
            raise TransactionJournalSemanticError(
                f"operation sequence must equal array index: expected {index}, got {op['sequence']}"
            )

        path = op["path"]
        _validate_relative_path(path)
        key = portable_collision_key(path)
        previous = path_keys.get(key)
        if previous is not None:
            raise TransactionJournalSemanticError(
                f"case-insensitive path collision: {previous!r} vs {path!r}"
            )
        path_keys[key] = path
        _validate_operation_shape(op)

    statuses = [op["status"] for op in operations]
    if phase in {"PLANNED", "PREPARED"} and any(s != "PENDING" for s in statuses):
        raise TransactionJournalSemanticError(f"all operations must be PENDING in {phase}")
    if phase == "COMMITTING" and not _is_prefix(statuses, "APPLIED", "PENDING"):
        raise TransactionJournalSemanticError(
            "COMMITTING requires an APPLIED prefix followed by PENDING operations"
        )
    if phase == "VERIFYING" and not _is_prefix(statuses, "VERIFIED", "APPLIED"):
        raise TransactionJournalSemanticError(
            "VERIFYING requires a VERIFIED prefix followed by APPLIED operations"
        )
    if phase == "COMMITTED" and any(s != "VERIFIED" for s in statuses):
        raise TransactionJournalSemanticError("all operations must be VERIFIED in COMMITTED")

    history = document["phaseHistory"]
    if history[0]["revision"] != 0 or history[0]["phase"] != "PLANNED":
        raise TransactionJournalSemanticError("phaseHistory must start at revision 0 with PLANNED")
    if _parse_utc(history[0]["at"]) != created:
        raise TransactionJournalSemanticError("first phaseHistory timestamp must equal createdAt")
    if history[-1]["phase"] != phase:
        raise TransactionJournalSemanticError("phaseHistory tail phase must equal top-level phase")

    last_revision = -1
    last_time = created
    previous_phase = None
    for item in history:
        item_revision = int(item["revision"])
        if item_revision <= last_revision:
            raise TransactionJournalSemanticError("phaseHistory revisions must be strictly increasing")
        if item_revision > revision:
            raise TransactionJournalSemanticError("phaseHistory revision must not exceed journalRevision")
        item_time = _parse_utc(item["at"])
        if item_time < last_time:
            raise TransactionJournalSemanticError("phaseHistory timestamps must be nondecreasing")
        if previous_phase is not None and item["phase"] not in ALLOWED_TRANSITIONS[previous_phase]:
            raise TransactionJournalSemanticError(
                f"invalid phase transition: {previous_phase} -> {item['phase']}"
            )
        previous_phase = item["phase"]
        last_revision = item_revision
        last_time = item_time

    if last_time > updated:
        raise TransactionJournalSemanticError("updatedAt must not precede the final phase history timestamp")

    incident_ids: set[str] = set()
    last_incident_kind = None
    last_incident_time = created
    for incident in document["incidents"]:
        incident_id = incident["incidentId"]
        if incident_id in incident_ids:
            raise TransactionJournalSemanticError(f"duplicate incidentId: {incident_id!r}")
        incident_ids.add(incident_id)
        if int(incident["detectedRevision"]) > revision:
            raise TransactionJournalSemanticError("incident detectedRevision must not exceed journalRevision")
        incident_time = _parse_utc(incident["detectedAt"])
        if incident_time < created:
            raise TransactionJournalSemanticError("incident cannot predate journal creation")
        if incident_time < last_incident_time:
            raise TransactionJournalSemanticError("incident timestamps must be nondecreasing")
        if incident_time > updated:
            raise TransactionJournalSemanticError("incident cannot postdate updatedAt")
        if "operationId" in incident and incident["operationId"] not in operation_ids:
            raise TransactionJournalSemanticError(
                f"incident references unknown operationId: {incident['operationId']!r}"
            )
        matching_phase_entries = [
            item for item in history
            if item["phase"] == incident["kind"] and int(item["revision"]) >= int(incident["detectedRevision"])
        ]
        if not matching_phase_entries:
            raise TransactionJournalSemanticError(
                f"incident {incident_id!r} has no corresponding phaseHistory entry"
            )
        last_incident_kind = incident["kind"]
        last_incident_time = incident_time

    if phase in INCIDENT_PHASES:
        if not document["incidents"]:
            raise TransactionJournalSemanticError(f"incident phase {phase} requires an incident record")
        if last_incident_kind != phase:
            raise TransactionJournalSemanticError(
                f"latest incident kind {last_incident_kind!r} must match current phase {phase!r}"
            )


def classify_current_state(operation: dict[str, Any], observed: dict[str, Any]) -> str:
    """Return BEFORE, AFTER or FOREIGN for a regular-file transaction operation."""
    kind = observed["kind"]
    if kind == "missing":
        current = {"exists": False}
    elif kind == "file":
        current = {"exists": True, "sha256": observed["sha256"]}
    else:
        return "FOREIGN"

    if current == operation["before"]:
        return "BEFORE"
    if current == operation["after"]:
        return "AFTER"
    return "FOREIGN"


def classify_commit_recovery(operations: list[dict[str, Any]], observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Classify a sequential COMMITTING recovery frontier without trusting journal statuses."""
    classifications = [classify_current_state(op, observations[op["operationId"]]) for op in operations]
    if "FOREIGN" in classifications:
        return {"classifications": classifications, "decision": "FOREIGN_MODIFICATION"}

    seen_before = False
    first_before = None
    for index, state in enumerate(classifications):
        if state == "BEFORE":
            if first_before is None:
                first_before = index
            seen_before = True
        elif state == "AFTER" and seen_before:
            return {"classifications": classifications, "decision": "RECOVERY_REQUIRED"}

    if first_before is None:
        return {"classifications": classifications, "decision": "READY_TO_VERIFY"}
    return {"classifications": classifications, "decision": "RESUME_COMMIT", "nextSequence": first_before}


def classify_rollback_safety(operation: dict[str, Any], observed: dict[str, Any]) -> str:
    """Return CAN_ROLLBACK, ALREADY_ROLLED_BACK or FOREIGN."""
    state = classify_current_state(operation, observed)
    if state == "AFTER":
        return "CAN_ROLLBACK"
    if state == "BEFORE":
        return "ALREADY_ROLLED_BACK"
    return "FOREIGN"
