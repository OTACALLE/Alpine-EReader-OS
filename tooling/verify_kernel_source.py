#!/usr/bin/env python3
"""Check a Samsung GPL kernel-source archive against the device facts.

Accepts a .tar/.tar.gz/.tar.xz or a Samsung .zip (which usually nests
``Kernel.tar.gz``).  It records provenance (SHA-256, version, defconfigs, device
trees) and NEVER marks the source as an approved input: that stays a manual,
reviewed decision (sources.lock.json ``approved_input``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

DEVICE_PATTERN = re.compile(r"j2core|7570", re.I)
LOCK = Path("devices/samsung-j2core/sources.lock.json")


class SourceError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_tar(tar: tarfile.TarFile) -> dict:
    found = {"makefiles": {}, "defconfigs": [], "dts": [], "arch_dirs": set()}
    for member in tar:
        name = member.name.lstrip("./")
        parts = name.split("/")
        if member.isfile() and parts[-1] == "Makefile" and len(parts) <= 2 and not found["makefiles"].get(name):
            text = tar.extractfile(member).read(4096).decode("utf-8", "replace")
            found["makefiles"][name] = {key: (re.search(rf"^{key}\s*=\s*(\S*)", text, re.M) or [None, ""])[1]
                                        for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL", "EXTRAVERSION")}
        match = re.search(r"(?:^|/)arch/(arm|arm64)/", name)
        if match:
            found["arch_dirs"].add(match.group(1))
        if re.search(r"arch/(arm|arm64)/configs/[^/]+$", name) and DEVICE_PATTERN.search(parts[-1]):
            found["defconfigs"].append(name)
        if re.search(r"arch/(arm|arm64)/boot/dts/.*\.dts[i]?$", name) and DEVICE_PATTERN.search(parts[-1]):
            found["dts"].append(name)
    return found


def scan_archive(path: Path) -> dict:
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                nested = [n for n in archive.namelist() if re.search(r"kernel.*\.tar(\.gz|\.xz|\.bz2)?$", n, re.I)]
                if not nested:
                    raise SourceError("zip has no nested Kernel tarball")
                with archive.open(nested[0]) as stream, tarfile.open(fileobj=stream, mode="r|*") as tar:
                    found = _scan_tar(tar)
                found["nested_archive"] = nested[0]
        else:
            with tarfile.open(path, mode="r|*") as tar:
                found = _scan_tar(tar)
    except (tarfile.TarError, zipfile.BadZipFile, EOFError, OSError) as error:
        raise SourceError(f"unreadable archive: {error}") from error
    return found


def analyze(path: Path, expected_version: str) -> dict:
    found = scan_archive(path)
    versions = {name: info for name, info in found["makefiles"].items() if info.get("VERSION") and info.get("PATCHLEVEL")}
    if not versions:
        raise SourceError("no kernel top-level Makefile with VERSION/PATCHLEVEL found")
    root, info = sorted(versions.items(), key=lambda item: item[0].count("/"))[0]
    version = f"{info['VERSION']}.{info['PATCHLEVEL']}.{info['SUBLEVEL']}"
    return {"archive": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
            "nested_archive": found.get("nested_archive"), "kernel_makefile": root, "version": version,
            "extraversion": info["EXTRAVERSION"], "expected_version": expected_version,
            "version_matches": version == expected_version, "arch_dirs": sorted(found["arch_dirs"]),
            "defconfigs": sorted(found["defconfigs"]), "device_trees": sorted(found["dts"]),
            "approved_input": False,
            "note": "Local version suffix (e.g. -15008757-QB43519801) cannot be proven from source; "
                    "approval stays a manual decision."}


def update_lock(lock_path: Path, report: dict) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    kernel = lock["kernel"]
    kernel["source_archive"] = {key: report[key] for key in ("archive", "sha256", "bytes", "version", "defconfigs", "device_trees")}
    kernel["status"] = ("source archive acquired and version-checked; not built, not booted, not approved"
                        if report["version_matches"] else "source archive acquired but version DOES NOT match; do not use")
    kernel["approved_input"] = False
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expect-version", default="3.18.14")
    parser.add_argument("--write-lock", action="store_true", help=f"record provenance in {LOCK}")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.archive, args.expect_version)
    except SourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    if args.write_lock:
        update_lock(LOCK, report)
    return 0 if report["version_matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
