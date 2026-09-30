from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .hashing import CONTENT_TREE_ALGORITHM, content_tree_summary
from .path_policy import portable_collision_key, validate_logical_path, validate_logical_prefix

FILE_INVENTORY_SCHEMA = "smml.file-inventory/1"
FILE_INVENTORY_DIFF_SCHEMA = "smml.file-inventory-diff/1"


class InventoryError(ValueError):
    pass


def _canonical_sort(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [
        {"path": str(item["path"]), "size": int(item["size"]), "sha256": str(item["sha256"])}
        for item in records
    ]
    result.sort(key=lambda item: (portable_collision_key(item["path"]), item["path"].encode("utf-8")))
    return result


def _scope_records(records: Iterable[dict[str, Any]], scope: dict[str, Any]) -> list[dict[str, Any]]:
    kind = scope.get("kind")
    if kind == "game-root":
        return list(records)
    if kind == "prefix":
        prefix = scope.get("path")
        validate_logical_prefix(prefix)
        return [item for item in records if item["path"].startswith(prefix)]
    raise InventoryError(f"unsupported inventory scope: {kind!r}")


def build_file_inventory(
    records: Iterable[dict[str, Any]],
    *,
    target: dict[str, Any],
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope = dict(scope or {"kind": "game-root"})
    selected = _canonical_sort(_scope_records(records, scope))
    summary = content_tree_summary(selected)
    return {
        "schema": FILE_INVENTORY_SCHEMA,
        "target": {
            "steamAppId": int(target["steamAppId"]),
            "steamBuildId": str(target["steamBuildId"]),
            "steamBranch": str(target["steamBranch"]),
        },
        "scope": scope,
        "contentTreeAlgorithm": CONTENT_TREE_ALGORITHM,
        "summary": summary,
        "files": selected,
    }


def slice_inventory(document: dict[str, Any], prefix: str) -> dict[str, Any]:
    validate_file_inventory(document)
    validate_logical_prefix(prefix)
    return build_file_inventory(
        document["files"],
        target=document["target"],
        scope={"kind": "prefix", "path": prefix},
    )


def validate_file_inventory(document: dict[str, Any]) -> None:
    if document.get("schema") != FILE_INVENTORY_SCHEMA:
        raise InventoryError(f"unexpected schema: {document.get('schema')!r}")
    if document.get("contentTreeAlgorithm") != CONTENT_TREE_ALGORITHM:
        raise InventoryError("unexpected contentTreeAlgorithm")
    target = document.get("target")
    if not isinstance(target, dict):
        raise InventoryError("target must be an object")
    app_id = target.get("steamAppId")
    if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
        raise InventoryError("target.steamAppId must be a positive integer")
    for key in ("steamBuildId", "steamBranch"):
        if not isinstance(target.get(key), str) or not target[key]:
            raise InventoryError(f"target.{key} must be a non-empty string")

    scope = document.get("scope")
    if not isinstance(scope, dict):
        raise InventoryError("scope must be an object")
    kind = scope.get("kind")
    if kind == "game-root":
        if set(scope) != {"kind"}:
            raise InventoryError("game-root scope must contain only 'kind'")
    elif kind == "prefix":
        if set(scope) != {"kind", "path"}:
            raise InventoryError("prefix scope must contain kind/path")
        validate_logical_prefix(scope.get("path"))
    else:
        raise InventoryError(f"unsupported inventory scope: {kind!r}")

    files = document.get("files")
    if not isinstance(files, list):
        raise InventoryError("files must be an array")
    expected = _canonical_sort(files)
    if expected != files:
        raise InventoryError("files must be sorted canonically")
    scoped = _scope_records(files, scope)
    if len(scoped) != len(files):
        raise InventoryError("inventory contains a path outside its scope")
    expected_summary = content_tree_summary(files)
    if document.get("summary") != expected_summary:
        raise InventoryError("summary does not match files")


def compare_file_inventories(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    classification: str | None = None,
    strict_target_paths: Iterable[str] = (),
) -> dict[str, Any]:
    validate_file_inventory(baseline)
    validate_file_inventory(current)
    if baseline["target"] != current["target"]:
        raise InventoryError("baseline/current target metadata differ")
    if baseline["scope"] != current["scope"]:
        raise InventoryError("baseline/current scopes differ")

    strict = set(strict_target_paths)
    base = {item["path"]: item for item in baseline["files"]}
    now = {item["path"]: item for item in current["files"]}
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []

    def decorate(record: dict[str, Any]) -> dict[str, Any]:
        result = dict(record)
        if classification is not None:
            result["classification"] = classification
        if record["path"] in strict:
            result["strictTargetFingerprint"] = True
        return result

    for path in sorted(set(now) - set(base), key=lambda p: (portable_collision_key(p), p.encode("utf-8"))):
        added.append(decorate(now[path]))
    for path in sorted(set(base) - set(now), key=lambda p: (portable_collision_key(p), p.encode("utf-8"))):
        removed.append(decorate(base[path]))
    for path in sorted(set(base) & set(now), key=lambda p: (portable_collision_key(p), p.encode("utf-8"))):
        if base[path]["size"] != now[path]["size"] or base[path]["sha256"] != now[path]["sha256"]:
            item: dict[str, Any] = {
                "path": path,
                "baseline": {"size": base[path]["size"], "sha256": base[path]["sha256"]},
                "current": {"size": now[path]["size"], "sha256": now[path]["sha256"]},
            }
            if classification is not None:
                item["classification"] = classification
            if path in strict:
                item["strictTargetFingerprint"] = True
            modified.append(item)

    added_bytes = sum(item["size"] for item in added)
    removed_bytes = sum(item["size"] for item in removed)
    modified_delta = sum(item["current"]["size"] - item["baseline"]["size"] for item in modified)
    return {
        "schema": FILE_INVENTORY_DIFF_SCHEMA,
        "target": baseline["target"],
        "scope": baseline["scope"],
        "baselineSummary": baseline["summary"],
        "currentSummary": current["summary"],
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": len(set(base) & set(now)) - len(modified),
            "addedBytes": added_bytes,
            "removedBytes": removed_bytes,
            "modifiedSizeDelta": modified_delta,
            "netSizeDelta": added_bytes - removed_bytes + modified_delta,
        },
        "changes": {"added": added, "removed": removed, "modified": modified},
    }


def load_json_document(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    try:
        if source.suffix == ".gz":
            with gzip.open(source, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot load {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise InventoryError(f"{source}: top-level JSON value must be an object")
    return data


def write_json_document(path: Path | str, document: dict[str, Any], *, pretty: bool = False) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".tmp")
    if pretty:
        encoded = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    else:
        encoded = (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        if destination.suffix == ".gz":
            with tmp.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                    gz.write(encoded)
        else:
            tmp.write_bytes(encoded)
        os.replace(tmp, destination)
    finally:
        if tmp.exists():
            tmp.unlink()
