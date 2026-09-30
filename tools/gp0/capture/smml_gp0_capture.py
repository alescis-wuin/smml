#!/usr/bin/env python3
"""Build a compact SMML GP0 analysis corpus from a Scrap Mechanic installation.

The tool consumes a scan ZIP produced by smml_gp0_scan.py plus a versioned capture
policy. It copies only FULL files and deterministic SAMPLE files. All other files
remain represented by their scan metadata/hashes inside the resulting archive.

Standard library only. Read-only with respect to the game tree.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

CHUNK = 1024 * 1024


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return str(n)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                return h.hexdigest()
            h.update(chunk)


def read_scan(scan_zip: Path) -> Tuple[List[dict], dict, Dict[str, bytes]]:
    with zipfile.ZipFile(scan_zip, "r") as zf:
        names = set(zf.namelist())
        if "manifest.jsonl" not in names or "summary.json" not in names:
            raise ValueError("scan ZIP must contain manifest.jsonl and summary.json")
        records = [
            json.loads(line)
            for line in zf.read("manifest.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        summary = json.loads(zf.read("summary.json").decode("utf-8"))
        reports = {name: zf.read(name) for name in sorted(names) if not name.endswith("/")}
    return records, summary, reports


def load_policy(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        p = json.load(f)
    if not str(p.get("schema", "")).startswith("smml-gp0-capture-policy/"):
        raise ValueError("unsupported capture policy schema")
    return p


def path_rule_action(path: str, rules: List[dict]) -> Optional[Tuple[str, str]]:
    for rule in rules:
        if fnmatch.fnmatchcase(path, rule["pattern"]):
            return rule["action"], rule.get("reason", "path rule")
    return None


def extension_maps(policy: dict) -> Tuple[Dict[str, str], Dict[str, str]]:
    actions: Dict[str, str] = {}
    reasons: Dict[str, str] = {}
    for action, spec in policy.get("extension_rules", {}).items():
        for ext in spec.get("extensions", []):
            key = ext.lower()
            actions[key] = action
            reasons[key] = spec.get("reason", "extension rule")
    return actions, reasons


def classify(record: dict, policy: dict, ext_actions: Dict[str, str], ext_reasons: Dict[str, str]) -> Tuple[str, str]:
    path = str(record["path"])
    matched = path_rule_action(path, policy.get("path_rules", []))
    if matched:
        return matched
    ext = str(record.get("extension") or "").lower()
    if ext in ext_actions:
        return ext_actions[ext], ext_reasons[ext]
    return policy.get("default_action", "REFERENCE"), "default policy"


def deterministic_sample(records: List[dict], count: int, max_bytes: int) -> List[dict]:
    if count <= 0:
        return []
    candidates = [r for r in records if 0 < int(r["size_bytes"]) <= max_bytes]
    if not candidates:
        return []

    chosen: Dict[str, dict] = {}

    def add(r: dict) -> None:
        if len(chosen) < count:
            chosen[str(r["path"])] = r

    # 1. Top-level diversity.
    by_root: Dict[str, List[dict]] = defaultdict(list)
    for r in candidates:
        parts = PurePosixPath(str(r["path"])).parts
        root = parts[0] if parts else "."
        by_root[root].append(r)
    for root in sorted(by_root, key=str.casefold):
        pool = sorted(by_root[root], key=lambda r: (int(r["size_bytes"]), str(r["path"]).casefold()))
        add(pool[0])
        if len(chosen) >= count:
            return list(chosen.values())

    # 2. Include text/binary variants when both exist.
    for kind in ("likely_text", "likely_binary"):
        pool = [r for r in candidates if r.get("text_kind") == kind]
        if pool:
            add(min(pool, key=lambda r: (int(r["size_bytes"]), str(r["path"]).casefold())))
        if len(chosen) >= count:
            return list(chosen.values())

    # 3. Size-distributed deterministic representatives.
    ordered = sorted(candidates, key=lambda r: (int(r["size_bytes"]), str(r["path"]).casefold()))
    anchors = [0, len(ordered)//4, len(ordered)//2, (3*len(ordered))//4, len(ordered)-1]
    for idx in anchors:
        add(ordered[idx])
        if len(chosen) >= count:
            return list(chosen.values())

    # 4. Fill deterministically.
    for r in ordered:
        add(r)
        if len(chosen) >= count:
            break
    return list(chosen.values())


def choose_records(files: List[dict], policy: dict) -> Tuple[List[dict], List[dict], Dict[str, dict]]:
    ext_actions, ext_reasons = extension_maps(policy)
    full: List[dict] = []
    reference: List[dict] = []
    sample_groups: Dict[str, List[dict]] = defaultdict(list)
    decisions: Dict[str, dict] = {}

    for r in files:
        action, reason = classify(r, policy, ext_actions, ext_reasons)
        p = str(r["path"])
        decisions[p] = {"action": action, "reason": reason, "selected": False}
        if action == "FULL":
            full.append(r)
            decisions[p]["selected"] = True
        elif action == "SAMPLE":
            sample_groups[str(r.get("extension") or "")].append(r)
        else:
            reference.append(r)

    sp = policy.get("sample_policy", {})
    default_count = int(sp.get("default_per_extension", 5))
    overrides = sp.get("per_extension", {})
    max_bytes = int(sp.get("max_single_sample_bytes", 8 * 1024 * 1024))
    sampled: List[dict] = []
    sampled_paths = set()
    for ext in sorted(sample_groups):
        count = int(overrides.get(ext, default_count))
        selected = deterministic_sample(sample_groups[ext], count, max_bytes)
        for r in selected:
            p = str(r["path"])
            sampled.append(r)
            sampled_paths.add(p)
            decisions[p]["selected"] = True
            decisions[p]["reason"] += "; deterministic representative sample"
        for r in sample_groups[ext]:
            if str(r["path"]) not in sampled_paths:
                reference.append(r)

    included = sorted(full + sampled, key=lambda r: str(r["path"]).casefold())
    reference = sorted(reference, key=lambda r: str(r["path"]).casefold())
    return included, reference, decisions


def verify_and_copy(root: Path, record: dict, dest: Path) -> None:
    src = root / str(record["path"])
    if not src.is_file():
        raise FileNotFoundError(f"missing selected file: {record['path']}")
    actual_size = src.stat().st_size
    expected_size = int(record["size_bytes"])
    if actual_size != expected_size:
        raise ValueError(f"size drift: {record['path']} expected={expected_size} actual={actual_size}")
    expected_hash = record.get("sha256")
    actual_hash = sha256_file(src)
    if expected_hash and actual_hash.lower() != str(expected_hash).lower():
        raise ValueError(f"SHA-256 drift: {record['path']}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            json.dump(r, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")


def zip_tree(staging: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as zf:
        for p in sorted(staging.rglob("*"), key=lambda p: p.as_posix().casefold()):
            if p.is_file():
                zf.write(p, p.relative_to(staging).as_posix())
    os.replace(tmp, output)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a selective SMML GP0 analysis corpus from a scan ZIP.")
    ap.add_argument("root", type=Path, help="Scrap Mechanic installation root")
    ap.add_argument("--scan", required=True, type=Path, help="smml_gp0_scan ZIP used as authoritative metadata")
    ap.add_argument("--policy", required=True, type=Path, help="capture policy JSON")
    ap.add_argument("--output", "-o", required=True, type=Path, help="output analysis corpus ZIP")
    ap.add_argument("--plan-only", action="store_true", help="print selection summary without copying files")
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    scan = args.scan.expanduser().resolve()
    policy_path = args.policy.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: game root not found: {root}", file=sys.stderr)
        return 2

    records, scan_summary, reports = read_scan(scan)
    policy = load_policy(policy_path)
    files = [r for r in records if r.get("kind") == "file"]
    included, reference, decisions = choose_records(files, policy)

    full_count = sum(1 for r in included if decisions[str(r['path'])]['action'] == 'FULL')
    sample_count = len(included) - full_count
    selected_bytes = sum(int(r["size_bytes"]) for r in included)
    reference_bytes = sum(int(r["size_bytes"]) for r in reference)

    by_action = Counter()
    by_action_bytes = Counter()
    for r in files:
        a = decisions[str(r["path"])]["action"]
        by_action[a] += 1
        by_action_bytes[a] += int(r["size_bytes"])

    print("[SMML GP0 CAPTURE] Selection plan")
    print(f"  scan schema:         {scan_summary.get('schema')}")
    print(f"  scan fingerprint:    {scan_summary.get('fingerprints', {}).get('installation_content_sha256')}")
    print(f"  source files:        {len(files)}")
    print(f"  FULL candidates:     {by_action['FULL']} ({human_size(by_action_bytes['FULL'])})")
    print(f"  SAMPLE candidates:   {by_action['SAMPLE']} ({human_size(by_action_bytes['SAMPLE'])})")
    print(f"  REFERENCE candidates:{by_action['REFERENCE']} ({human_size(by_action_bytes['REFERENCE'])})")
    print(f"  actually included:   {len(included)} = {full_count} full + {sample_count} samples")
    print(f"  included raw bytes:  {human_size(selected_bytes)}")
    print(f"  referenced raw bytes:{human_size(reference_bytes)}")

    if args.plan_only:
        return 0

    with tempfile.TemporaryDirectory(prefix="smml-gp0-capture-") as td:
        staging = Path(td)
        content_root = staging / policy.get("archive_layout", {}).get("content_root", "game")
        analysis_root = staging / policy.get("archive_layout", {}).get("analysis_root", "_analysis")
        source_scan_root = analysis_root / "source-scan"
        content_root.mkdir(parents=True, exist_ok=True)
        source_scan_root.mkdir(parents=True, exist_ok=True)

        print("[SMML GP0 CAPTURE] Verifying and copying selected files...")
        for i, r in enumerate(included, 1):
            verify_and_copy(root, r, content_root / str(r["path"]))
            if i % 1000 == 0:
                print(f"  {i}/{len(included)} selected files copied")

        for name, data in reports.items():
            dest = source_scan_root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        shutil.copyfile(policy_path, analysis_root / "capture-policy.json")
        write_jsonl(analysis_root / "included-manifest.jsonl", included)
        write_jsonl(analysis_root / "reference-manifest.jsonl", reference)

        decision_rows = []
        for r in sorted(files, key=lambda r: str(r["path"]).casefold()):
            d = decisions[str(r["path"])]
            decision_rows.append({
                "path": r["path"],
                "extension": r.get("extension"),
                "size_bytes": r["size_bytes"],
                "sha256": r.get("sha256"),
                "action": d["action"],
                "selected": d["selected"],
                "reason": d["reason"],
            })
        write_jsonl(analysis_root / "capture-decisions.jsonl", decision_rows)

        ext_summary: Dict[str, dict] = {}
        for r in files:
            ext = str(r.get("extension") or "")
            d = decisions[str(r["path"])]
            row = ext_summary.setdefault(ext, {"extension": ext, "files": 0, "bytes": 0, "included_files": 0, "included_bytes": 0, "actions": Counter()})
            row["files"] += 1
            row["bytes"] += int(r["size_bytes"])
            row["actions"][d["action"]] += 1
            if d["selected"]:
                row["included_files"] += 1
                row["included_bytes"] += int(r["size_bytes"])
        serializable_ext = []
        for ext in sorted(ext_summary):
            row = ext_summary[ext]
            row["actions"] = dict(row["actions"])
            serializable_ext.append(row)
        with (analysis_root / "capture-extension-summary.json").open("w", encoding="utf-8") as f:
            json.dump(serializable_ext, f, ensure_ascii=False, indent=2, sort_keys=True)

        summary = {
            "schema": "smml-gp0-analysis-corpus/1",
            "source_scan_schema": scan_summary.get("schema"),
            "source_installation_content_sha256": scan_summary.get("fingerprints", {}).get("installation_content_sha256"),
            "policy_schema": policy.get("schema"),
            "counts": {
                "source_files": len(files),
                "full_files": full_count,
                "sample_files": sample_count,
                "included_files": len(included),
                "reference_only_files": len(reference),
            },
            "bytes": {
                "included_raw": selected_bytes,
                "reference_only_raw": reference_bytes,
                "source_total": selected_bytes + reference_bytes,
            },
            "notes": [
                "Files under game/ are copied from the local installation only after size and SHA-256 verification against the source scan.",
                "Files omitted from game/ remain represented in _analysis/reference-manifest.jsonl and the embedded source scan.",
                "This corpus is for private GP0 analysis and is not a redistribution package.",
            ],
        }
        with (analysis_root / "capture-summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)

        readme = f"""SMML GP0 analysis corpus\n========================\n\nSource scan fingerprint: {summary['source_installation_content_sha256']}\nPolicy: {policy.get('schema')}\n\nLayout:\n  game/                         selected full files and representative samples\n  _analysis/source-scan/        complete source scan reports\n  _analysis/capture-policy.json policy used for this capture\n  _analysis/included-manifest.jsonl\n  _analysis/reference-manifest.jsonl\n  _analysis/capture-decisions.jsonl\n  _analysis/capture-extension-summary.json\n  _analysis/capture-summary.json\n\nFULL files are copied completely. SAMPLE families contribute deterministic representatives.\nREFERENCE files are not copied but remain fully described by metadata and SHA-256.\n"""
        (analysis_root / "README.txt").write_text(readme, encoding="utf-8")

        print(f"[SMML GP0 CAPTURE] Building ZIP: {output}")
        zip_tree(staging, output)

    print("[SMML GP0 CAPTURE] Done")
    print(f"  output: {output}")
    print(f"  ZIP size: {human_size(output.stat().st_size)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
