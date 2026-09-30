#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORED_DIRS = {".git", ".venv", "venv", "artifacts", "dist", "build", "out", "tmp"}
ACTIVE_DIRS = {"specs", "schemas", "policies", "examples", "tests", "tools"}
VERSIONED_PATH_RE = re.compile(r"(?:^|[-_])v\d+(?:[._-]\d+)+", re.IGNORECASE)


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        yield path, rel


def main() -> int:
    errors: list[str] = []
    hashes: dict[str, list[str]] = defaultdict(list)

    for path, rel in iter_files():
        rel_s = rel.as_posix()
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            errors.append(f"temporary Python artifact: {rel_s}")
        if rel.parts and rel.parts[0] in ACTIVE_DIRS and VERSIONED_PATH_RE.search(rel_s):
            # Public schema filenames intentionally carry their format version.
            if not (rel.parts[0] == "schemas" and rel_s.endswith(".schema.json")):
                errors.append(f"manual version in active path: {rel_s}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[digest].append(rel_s)

    for digest, paths in sorted(hashes.items()):
        if len(paths) > 1:
            errors.append(f"exact duplicate {digest}: {', '.join(paths)}")

    if errors:
        print("Repository hygiene: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"Repository hygiene: PASS ({sum(len(v) for v in hashes.values())} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
