#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import stat
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

CHUNK_SIZE = 1024 * 1024
SAMPLE_SIZE = 64 * 1024
DEFAULT_DEEP_TEXT_LIMIT = 16 * 1024 * 1024
DEFAULT_SAMPLE_COPY_LIMIT = 512 * 1024

UUID_RE = re.compile(rb"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
DATA_REF_RE = re.compile(
    rb"\$(?:GAME_DATA|SURVIVAL_DATA|CONTENT_DATA|MOD_DATA|CHALLENGE_DATA|CACHE_DATA|CUSTOMIZATION_DATA|PARTICLE_EDITOR_DATA)"
    rb"/[A-Za-z0-9_./() \-\[\]@+]+"
)

CACHE_EXTENSIONS = {".cbo", ".dco", ".mco", ".tco"}
NATIVE_EXTENSIONS = {".exe", ".dll", ".pdb", ".so", ".dylib"}
LOG_EXTENSIONS = {".log"}
TEXT_DECLARATIVE_EXTENSIONS = {
    ".lua", ".json", ".xml", ".txt", ".md", ".csv", ".tsv", ".ini", ".cfg",
    ".shapeset", ".rend", ".effectset", ".harvestableset", ".world",
    ".tileson", ".prefabson", ".kinematicset", ".tracknodes", ".blueprint",
    ".projectileset", ".scriptableobjectset", ".characterset", ".toolset",
}
ASSET_EXTENSIONS = {
    ".obj", ".mtl", ".dae", ".fbx", ".glb", ".gltf",
    ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".dds",
    ".wav", ".ogg", ".bank",
}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".gz", ".bz2", ".xz"}

MAGIC_SIGNATURES = [
    (b"MZ", "PE/COFF"),
    (b"\x7fELF", "ELF"),
    (b"SQLite format 3\x00", "SQLite3"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"DDS ", "DDS"),
    (b"GIF87a", "GIF87a"),
    (b"GIF89a", "GIF89a"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"PK\x03\x04", "ZIP"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip"),
    (b"Rar!\x1a\x07", "RAR"),
    (b"OggS", "Ogg"),
    (b"RIFF", "RIFF"),
    (b"glTF", "GLB"),
    (b"Kaydara FBX Binary", "FBX binary"),
]


def utc_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def human_size(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(n)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{n} B"


def safe_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def extension_info(path: Path) -> Tuple[str, str]:
    suffixes = path.suffixes
    ext = suffixes[-1].lower() if suffixes else "[no extension]"
    chain = "".join(suffixes).lower() if suffixes else "[no extension]"
    return ext, chain


def shannon_entropy(data: bytes) -> Optional[float]:
    if not data:
        return None
    counts = Counter(data)
    total = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def detect_magic(sample: bytes) -> str:
    for sig, name in MAGIC_SIGNATURES:
        if sample.startswith(sig):
            return name
    return "unknown"


def detect_text(sample: bytes) -> Tuple[str, str]:
    if not sample:
        return "empty", "n/a"
    if sample.startswith(b"\xef\xbb\xbf"):
        try:
            sample.decode("utf-8-sig")
            return "likely_text", "utf-8-sig"
        except UnicodeDecodeError:
            pass
    if sample.startswith(b"\xff\xfe"):
        try:
            sample.decode("utf-16-le")
            return "likely_text", "utf-16-le"
        except UnicodeDecodeError:
            pass
    if sample.startswith(b"\xfe\xff"):
        try:
            sample.decode("utf-16-be")
            return "likely_text", "utf-16-be"
        except UnicodeDecodeError:
            pass
    if b"\x00" in sample:
        return "likely_binary", "binary/unknown"
    try:
        sample.decode("utf-8")
        return "likely_text", "utf-8"
    except UnicodeDecodeError:
        pass
    printable = sum(1 for b in sample if b in b"\t\n\r" or 32 <= b <= 126)
    return ("likely_text", "single-byte/unknown") if printable / len(sample) >= 0.90 else ("likely_binary", "binary/unknown")


def package_hint(rel_path: str, ext: str, text_kind: str) -> str:
    lower_parts = {p.lower() for p in Path(rel_path).parts}
    if "cache" in lower_parts or ext in CACHE_EXTENSIONS:
        return "reference_only:generated_cache"
    if ext in NATIVE_EXTENSIONS:
        return "reference_only:native_binary"
    if ext in LOG_EXTENSIONS:
        return "reference_only:runtime_log"
    if ext in TEXT_DECLARATIVE_EXTENSIONS or text_kind == "likely_text":
        return "inspect:script_or_declarative"
    if ext in ASSET_EXTENSIONS:
        return "inspect:asset_dependency"
    if ext in ARCHIVE_EXTENSIONS:
        return "inspect:archive"
    return "inspect:unknown"


def hash_and_inspect(path: Path) -> Dict[str, object]:
    sha = hashlib.sha256()
    sample = bytearray()
    newline_count = 0
    total = 0
    last_byte: Optional[int] = None
    with path.open("rb", buffering=0) as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
            total += len(chunk)
            newline_count += chunk.count(b"\n")
            last_byte = chunk[-1]
            if len(sample) < SAMPLE_SIZE:
                sample.extend(chunk[: SAMPLE_SIZE - len(sample)])
    sample_bytes = bytes(sample)
    text_kind, encoding_hint = detect_text(sample_bytes)
    line_count = None
    if text_kind == "likely_text":
        line_count = newline_count + (1 if total > 0 and last_byte not in (10, 13) else 0)
    return {
        "sha256": sha.hexdigest(),
        "sample_size": len(sample_bytes),
        "sample_entropy": round(shannon_entropy(sample_bytes), 5) if sample_bytes else None,
        "magic": detect_magic(sample_bytes),
        "text_kind": text_kind,
        "encoding_hint": encoding_hint,
        "contains_nul_in_sample": b"\x00" in sample_bytes,
        "line_count": line_count,
    }


def get_xattr_names(path: Path) -> List[str]:
    if not hasattr(os, "listxattr"):
        return []
    try:
        return sorted(os.listxattr(path, follow_symlinks=False))
    except Exception:
        return []


def metadata_record(path: Path, root: Path) -> Dict[str, object]:
    st = path.lstat()
    rel = safe_rel(path, root)
    ext, ext_chain = extension_info(path)
    if stat.S_ISREG(st.st_mode):
        kind = "file"
    elif stat.S_ISDIR(st.st_mode):
        kind = "directory"
    elif stat.S_ISLNK(st.st_mode):
        kind = "symlink"
    else:
        kind = "other"
    record: Dict[str, object] = {
        "path": rel,
        "name": path.name,
        "kind": kind,
        "extension": ext if kind == "file" else "",
        "extension_chain": ext_chain if kind == "file" else "",
        "size_bytes": st.st_size if kind == "file" else 0,
        "content_state": "empty" if kind == "file" and st.st_size == 0 else "nonempty" if kind == "file" else "n/a",
        "depth": len(Path(rel).parts),
        "hidden_path": any(part.startswith(".") for part in Path(rel).parts),
        "mode": stat.filemode(st.st_mode),
        "mode_octal": oct(stat.S_IMODE(st.st_mode)),
        "uid": getattr(st, "st_uid", None),
        "gid": getattr(st, "st_gid", None),
        "inode": getattr(st, "st_ino", None),
        "device": getattr(st, "st_dev", None),
        "hardlink_count": getattr(st, "st_nlink", None),
        "modified_utc": utc_iso(getattr(st, "st_mtime", None)),
        "ctime_utc_platform_dependent": utc_iso(getattr(st, "st_ctime", None)),
        "birth_utc_if_available": utc_iso(getattr(st, "st_birthtime", None)),
        "windows_file_attributes": getattr(st, "st_file_attributes", None),
        "xattr_names": get_xattr_names(path),
        "symlink_target": None,
        "sha256": None,
        "sample_size": None,
        "sample_entropy": None,
        "magic": None,
        "text_kind": None,
        "encoding_hint": None,
        "contains_nul_in_sample": None,
        "line_count": None,
        "mime_guess": None,
        "package_hint": None,
        "error": None,
    }
    if kind == "symlink":
        try:
            record["symlink_target"] = os.readlink(path)
        except OSError as e:
            record["error"] = f"readlink: {e}"
    return record


def walk_paths(root: Path, output_dir: Path) -> Iterable[Path]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept = []
        for name in sorted(dirs, key=str.casefold):
            p = current_path / name
            try:
                resolved = p.resolve(strict=False)
            except OSError:
                resolved = p.absolute()
            if resolved == output_dir or is_within(resolved, output_dir):
                continue
            kept.append(name)
        dirs[:] = kept
        for name in dirs:
            yield current_path / name
        for name in sorted(files, key=str.casefold):
            p = current_path / name
            try:
                resolved = p.resolve(strict=False)
            except OSError:
                resolved = p.absolute()
            if resolved == output_dir or is_within(resolved, output_dir):
                continue
            yield p


def write_manifest_jsonl(records: List[Dict[str, object]], out: Path) -> None:
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            json.dump(r, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")


def write_manifest_csv(records: List[Dict[str, object]], out: Path) -> None:
    fields = [
        "path", "name", "kind", "extension", "extension_chain", "size_bytes",
        "content_state", "depth", "hidden_path", "mode", "mode_octal",
        "uid", "gid", "inode", "device", "hardlink_count", "modified_utc",
        "ctime_utc_platform_dependent", "birth_utc_if_available",
        "windows_file_attributes", "symlink_target", "sha256", "sample_size",
        "sample_entropy", "magic", "text_kind", "encoding_hint",
        "contains_nul_in_sample", "line_count", "mime_guess",
        "package_hint", "error",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def write_tree(records: List[Dict[str, object]], root: Path, out: Path) -> None:
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"{root.name}/\n")
        for r in sorted(records, key=lambda x: str(x["path"]).casefold()):
            rel = Path(str(r["path"]))
            indent = "    " * len(rel.parts)
            marker = {"directory": "[D]", "file": "[F]", "symlink": "[L]"}.get(str(r["kind"]), "[?]")
            extra = f" ({r['size_bytes']} B)" if r["kind"] == "file" else f" -> {r.get('symlink_target')}" if r["kind"] == "symlink" else ""
            f.write(f"{indent}{marker} {rel.name}{extra}\n")


def extension_statistics(files: List[Dict[str, object]]) -> List[Dict[str, object]]:
    groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for r in files:
        groups[str(r["extension"])].append(r)
    rows = []
    for ext, items in groups.items():
        ordered = sorted(items, key=lambda x: str(x["path"]).casefold())
        nonempty = [x for x in ordered if int(x["size_bytes"]) > 0]
        representative_pool = [x for x in nonempty if x.get("text_kind") == "likely_text"] or nonempty or ordered
        example = min(representative_pool, key=lambda x: (int(x["size_bytes"]), str(x["path"]).casefold()))
        rows.append({
            "extension": ext,
            "count": len(items),
            "total_bytes": sum(int(x["size_bytes"]) for x in items),
            "empty_count": sum(1 for x in items if int(x["size_bytes"]) == 0),
            "likely_text_count": sum(1 for x in items if x.get("text_kind") == "likely_text"),
            "likely_binary_count": sum(1 for x in items if x.get("text_kind") == "likely_binary"),
            "min_bytes": min(int(x["size_bytes"]) for x in items),
            "max_bytes": max(int(x["size_bytes"]) for x in items),
            "example": example["path"],
        })
    return sorted(rows, key=lambda x: (-int(x["count"]), str(x["extension"])))


def write_extensions(rows: List[Dict[str, object]], out_txt: Path, out_csv: Path) -> None:
    with out_txt.open("w", encoding="utf-8", newline="\n") as f:
        f.write("Extension\tCount\tTotal\tEmpty\tText\tBinary\tMin\tMax\tExample\n")
        for r in rows:
            f.write(f"{r['extension']}\t{r['count']}\t{human_size(int(r['total_bytes']))}\t{r['empty_count']}\t{r['likely_text_count']}\t{r['likely_binary_count']}\t{r['min_bytes']}\t{r['max_bytes']}\t{r['example']}\n")
    fields = ["extension", "count", "total_bytes", "empty_count", "likely_text_count", "likely_binary_count", "min_bytes", "max_bytes", "example"]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_duplicates(files: List[Dict[str, object]], out: Path) -> int:
    groups: Dict[Tuple[int, str], List[str]] = defaultdict(list)
    for r in files:
        if r.get("sha256"):
            groups[(int(r["size_bytes"]), str(r["sha256"]))].append(str(r["path"]))
    duplicate_groups = [(size, sha, paths) for (size, sha), paths in groups.items() if len(paths) > 1]
    duplicate_groups.sort(key=lambda x: (-x[0] * len(x[2]), x[1]))
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for i, (size, sha, paths) in enumerate(duplicate_groups, 1):
            f.write(f"[group {i}] size={size} sha256={sha} copies={len(paths)}\n")
            for p in sorted(paths, key=str.casefold):
                f.write(f"  {p}\n")
            f.write("\n")
    return len(duplicate_groups)


def write_largest(files: List[Dict[str, object]], out: Path, limit: int = 250) -> None:
    ordered = sorted(files, key=lambda x: (-int(x["size_bytes"]), str(x["path"]).casefold()))
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for r in ordered[:limit]:
            f.write(f"{int(r['size_bytes']):>14}\t{human_size(int(r['size_bytes'])):>12}\t{r['path']}\n")


def write_directory_summary(files: List[Dict[str, object]], out: Path) -> None:
    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "bytes": 0})
    for r in files:
        p = Path(str(r["path"]))
        top = p.parts[0] if p.parts else "."
        stats[top]["files"] += 1
        stats[top]["bytes"] += int(r["size_bytes"])
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("TopLevel\tFiles\tBytes\tHuman\n")
        for name, s in sorted(stats.items(), key=lambda kv: (-kv[1]["bytes"], kv[0].casefold())):
            f.write(f"{name}\t{s['files']}\t{s['bytes']}\t{human_size(s['bytes'])}\n")


def write_package_hints(files: List[Dict[str, object]], out: Path) -> None:
    groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for r in files:
        groups[str(r.get("package_hint"))].append(r)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("Advisory pre-analysis only. Do not redistribute vanilla files merely because they appear here.\n\n")
        for hint in sorted(groups):
            items = groups[hint]
            total = sum(int(x["size_bytes"]) for x in items)
            f.write(f"[{hint}] files={len(items)} total={human_size(total)}\n")
            for r in sorted(items, key=lambda x: str(x["path"]).casefold())[:25]:
                f.write(f"  {r['path']}\n")
            if len(items) > 25:
                f.write(f"  ... {len(items) - 25} more\n")
            f.write("\n")


def scan_deep_references(root: Path, files: List[Dict[str, object]], out_refs: Path, out_uuids: Path, max_size: int) -> Tuple[int, int]:
    ref_count = uuid_count = 0
    with out_refs.open("w", encoding="utf-8", newline="\n") as rf, out_uuids.open("w", encoding="utf-8", newline="\n") as uf:
        rf.write("source\treference\n")
        uf.write("source\tuuid\n")
        for r in files:
            if r.get("text_kind") != "likely_text" or int(r["size_bytes"]) > max_size:
                continue
            path = root / str(r["path"])
            try:
                data = path.read_bytes()
            except OSError:
                continue
            refs = sorted({m.group(0).decode("utf-8", errors="replace").rstrip(".,;:)]}") for m in DATA_REF_RE.finditer(data)})
            uuids = sorted({m.group(0).decode("ascii", errors="ignore").lower() for m in UUID_RE.finditer(data)})
            for ref in refs:
                rf.write(f"{r['path']}\t{ref}\n")
                ref_count += 1
            for uuid in uuids:
                uf.write(f"{r['path']}\t{uuid}\n")
                uuid_count += 1
    return ref_count, uuid_count


def copy_extension_samples(root: Path, ext_rows: List[Dict[str, object]], files_by_path: Dict[str, Dict[str, object]], out_dir: Path, max_size: int) -> int:
    samples_dir = out_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    index = []
    copied = 0
    for row in ext_rows:
        rel = str(row["example"])
        record = files_by_path.get(rel)
        if not record or record.get("text_kind") != "likely_text" or int(record["size_bytes"]) > max_size:
            continue
        src = root / rel
        ext_name = str(row["extension"]).replace("/", "_").replace("\\", "_").replace(" ", "_")
        if ext_name == "[no_extension]":
            ext_name = "no_extension"
        safe_name = f"{ext_name.lstrip('.') or 'no_extension'}__{src.name}"
        dst = samples_dir / safe_name
        try:
            shutil.copyfile(src, dst)
        except OSError:
            continue
        copied += 1
        index.append({"extension": row["extension"], "source": rel, "copied_as": f"samples/{safe_name}", "sha256": record.get("sha256"), "size_bytes": record.get("size_bytes")})
    with (samples_dir / "index.json").open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
    return copied


def zip_reports(out_dir: Path) -> Path:
    zip_path = out_dir.parent / f"{out_dir.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(out_dir.rglob("*"), key=lambda p: p.as_posix().casefold()):
            if path.is_file():
                zf.write(path, path.relative_to(out_dir).as_posix())
    return zip_path



def canonical_file_fingerprint(files, prefix=None):
    """Hash canonical path/size/SHA tuples; timestamps are intentionally excluded."""
    h = hashlib.sha256()
    selected = []
    for r in files:
        path = str(r["path"])
        if prefix is not None and not (path == prefix or path.startswith(prefix + "/")):
            continue
        selected.append(r)
    for r in sorted(selected, key=lambda x: str(x["path"]).casefold()):
        payload = f"{r['path']}\0{r['size_bytes']}\0{r.get('sha256') or ''}\n".encode("utf-8")
        h.update(payload)
    return h.hexdigest()


def split_runtime_report(source, static_out, runtime_out):
    """Split deep-scan rows into static sources versus Cache/Logs runtime sources."""
    with source.open("r", encoding="utf-8") as srcf:
        header = srcf.readline()
        with static_out.open("w", encoding="utf-8", newline="\n") as sf, runtime_out.open("w", encoding="utf-8", newline="\n") as rf:
            sf.write(header)
            rf.write(header)
            for line in srcf:
                if not line.strip():
                    continue
                source_path = line.split("\t", 1)[0]
                if source_path.startswith("Logs/") or source_path.startswith("Cache/"):
                    rf.write(line)
                else:
                    sf.write(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Scrap Mechanic installation inventory for SMML GP0.")
    parser.add_argument("root", type=Path, help="Scrap Mechanic installation root")
    parser.add_argument("--output", "-o", type=Path, default=Path("./smml-gp0-scan"), help="Report directory")
    parser.add_argument("--deep", action="store_true", help="Extract $*_DATA references and UUID occurrences from likely-text files")
    parser.add_argument("--deep-text-limit", type=int, default=DEFAULT_DEEP_TEXT_LIMIT)
    parser.add_argument("--copy-text-samples", action="store_true", help="Copy one small likely-text example per extension into the report only")
    parser.add_argument("--sample-copy-limit", type=int, default=DEFAULT_SAMPLE_COPY_LIMIT)
    parser.add_argument("--no-zip", action="store_true", help="Do not create a ZIP containing the reports")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    out_dir = args.output.expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: root is not a directory: {root}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, object]] = []
    errors: List[str] = []

    print(f"[SMML GP0] Root:   {root}")
    print(f"[SMML GP0] Output: {out_dir}")
    print("[SMML GP0] Scanning metadata and computing SHA-256...")

    for idx, path in enumerate(walk_paths(root, out_dir), 1):
        try:
            rec = metadata_record(path, root)
            if rec["kind"] == "file":
                try:
                    rec.update(hash_and_inspect(path))
                    rec["mime_guess"] = mimetypes.guess_type(path.name)[0]
                    rec["package_hint"] = package_hint(str(rec["path"]), str(rec["extension"]), str(rec["text_kind"]))
                except (OSError, PermissionError) as e:
                    rec["content_state"] = "unreadable"
                    rec["error"] = f"read/hash: {e}"
                    errors.append(f"{rec['path']}\tread/hash\t{e}")
            records.append(rec)
        except (OSError, PermissionError) as e:
            rel = safe_rel(path, root)
            errors.append(f"{rel}\tmetadata\t{e}")
        if idx % 1000 == 0:
            print(f"[SMML GP0] {idx} paths processed")

    records.sort(key=lambda x: str(x["path"]).casefold())
    files = [r for r in records if r["kind"] == "file"]
    dirs = [r for r in records if r["kind"] == "directory"]
    symlinks = [r for r in records if r["kind"] == "symlink"]

    write_manifest_jsonl(records, out_dir / "manifest.jsonl")
    write_manifest_csv(records, out_dir / "manifest.csv")
    write_tree(records, root, out_dir / "tree.txt")

    ext_rows = extension_statistics(files)
    write_extensions(ext_rows, out_dir / "extensions.txt", out_dir / "extensions.csv")
    duplicate_groups = write_duplicates(files, out_dir / "duplicates.txt")
    write_largest(files, out_dir / "largest-files.txt")
    write_directory_summary(files, out_dir / "top-level-summary.txt")
    write_package_hints(files, out_dir / "packaging-hints.txt")

    with (out_dir / "empty-files.txt").open("w", encoding="utf-8") as f:
        for r in files:
            if int(r["size_bytes"]) == 0:
                f.write(str(r["path"]) + "\n")

    with (out_dir / "symlinks.txt").open("w", encoding="utf-8") as f:
        for r in symlinks:
            f.write(f"{r['path']} -> {r.get('symlink_target')}\n")

    long_paths = [str(r["path"]) for r in records if len(str(root / str(r["path"]))) >= 240]
    with (out_dir / "long-paths.txt").open("w", encoding="utf-8") as f:
        f.write("\n".join(long_paths) + ("\n" if long_paths else ""))

    case_map: Dict[str, List[str]] = defaultdict(list)
    for r in records:
        case_map[str(r["path"]).casefold()].append(str(r["path"]))
    case_collisions = [v for v in case_map.values() if len(v) > 1]
    with (out_dir / "case-collisions.txt").open("w", encoding="utf-8") as f:
        for i, paths in enumerate(case_collisions, 1):
            f.write(f"[group {i}]\n")
            for p in sorted(paths):
                f.write(f"  {p}\n")
            f.write("\n")

    magic_counts = Counter(str(r.get("magic")) for r in files)
    with (out_dir / "magic-types.txt").open("w", encoding="utf-8") as f:
        for magic, count in magic_counts.most_common():
            f.write(f"{count}\t{magic}\n")

    with (out_dir / "errors.txt").open("w", encoding="utf-8") as f:
        for line in errors:
            f.write(line + "\n")

    ref_count = uuid_count = 0
    if args.deep:
        print("[SMML GP0] Deep scan: extracting references and UUIDs...")
        ref_count, uuid_count = scan_deep_references(root, files, out_dir / "references.tsv", out_dir / "uuids.tsv", args.deep_text_limit)
        split_runtime_report(out_dir / "references.tsv", out_dir / "references-static.tsv", out_dir / "references-runtime.tsv")
        split_runtime_report(out_dir / "uuids.tsv", out_dir / "uuids-static.tsv", out_dir / "uuids-runtime.tsv")

    copied_samples = 0
    if args.copy_text_samples:
        print("[SMML GP0] Copying representative small text samples...")
        files_by_path = {str(r["path"]): r for r in files}
        copied_samples = copy_extension_samples(root, ext_rows, files_by_path, out_dir, args.sample_copy_limit)

    total_bytes = sum(int(r["size_bytes"]) for r in files)
    top_level_names = sorted({Path(str(r["path"])).parts[0] for r in files if Path(str(r["path"])).parts}, key=str.casefold)
    fingerprints = {
        "installation_content_sha256": canonical_file_fingerprint(files),
        "top_level_content_sha256": {name: canonical_file_fingerprint(files, name) for name in top_level_names},
    }

    summary = {
        "schema": "smml-gp0-scan/1.2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root_name": root.name,
        "root_path_local_only": str(root),
        "platform": sys.platform,
        "python": sys.version,
        "counts": {
            "records": len(records),
            "files": len(files),
            "directories": len(dirs),
            "symlinks": len(symlinks),
            "extensions": len(ext_rows),
            "empty_files": sum(1 for r in files if int(r["size_bytes"]) == 0),
            "likely_text_files": sum(1 for r in files if r.get("text_kind") == "likely_text"),
            "likely_binary_files": sum(1 for r in files if r.get("text_kind") == "likely_binary"),
            "unreadable_files": sum(1 for r in files if r.get("content_state") == "unreadable"),
            "duplicate_groups": duplicate_groups,
            "case_collision_groups": len(case_collisions),
            "long_paths": len(long_paths),
            "errors": len(errors),
            "deep_references": ref_count,
            "uuid_occurrences": uuid_count,
            "copied_text_samples": copied_samples,
        },
        "fingerprints": fingerprints,
        "total_file_bytes": total_bytes,
        "total_file_bytes_human": human_size(total_bytes),
        "notes": [
            "ctime semantics are platform-dependent.",
            "birth time is recorded only when exposed by the OS.",
            "atime is intentionally not recorded because reading files can update access time.",
            "package_hint is advisory only.",
            "directory symlinks are never followed.",
        ],
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)

    with (out_dir / "README.txt").open("w", encoding="utf-8") as f:
        f.write(
            "SMML GP0 installation scan\n"
            "===========================\n\n"
            "Core reports:\n"
            "- summary.json\n"
            "- manifest.jsonl / manifest.csv\n"
            "- tree.txt\n"
            "- extensions.txt / extensions.csv\n"
            "- duplicates.txt\n"
            "- largest-files.txt\n"
            "- top-level-summary.txt\n"
            "- empty-files.txt\n"
            "- magic-types.txt\n"
            "- case-collisions.txt\n"
            "- long-paths.txt\n"
            "- symlinks.txt\n"
            "- packaging-hints.txt\n"
            "- errors.txt\n\n"
            "With --deep:\n"
            "- references.tsv\n"
            "- references-static.tsv / references-runtime.tsv\n"
            "- uuids.tsv\n"
            "- uuids-static.tsv / uuids-runtime.tsv\n\n"
            "With --copy-text-samples:\n"
            "- samples/\n"
        )

    zip_path = None
    if not args.no_zip:
        print("[SMML GP0] Creating report ZIP...")
        zip_path = zip_reports(out_dir)

    print("[SMML GP0] Done")
    print(f"  files:       {len(files)}")
    print(f"  directories: {len(dirs)}")
    print(f"  size:        {human_size(total_bytes)}")
    print(f"  extensions:  {len(ext_rows)}")
    print(f"  duplicates:  {duplicate_groups} groups")
    print(f"  errors:      {len(errors)}")
    if args.deep:
        print(f"  references:  {ref_count}")
        print(f"  UUIDs:       {uuid_count}")
    print(f"  report dir:  {out_dir}")
    if zip_path:
        print(f"  report ZIP:  {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
