#!/usr/bin/env python3
"""Compose a deterministic development rootfs tarball without host Linux."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ("core", "shell", "reader_integration", "reader-integration", "recovery")


def add_tree(archive: tarfile.TarFile, source: Path) -> None:
    for path in sorted(source.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        info = archive.gettarinfo(str(path), arcname=str(path.relative_to(ROOT)).replace("\\", "/"))
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = 0
        with path.open("rb") as stream:
            archive.addfile(info, stream)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="path to an image manifest relative to repository root")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = ROOT / args.device
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = ROOT / manifest["device_profile"]
    if not profile.exists():
        raise SystemExit(f"device profile missing: {profile}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, "w") as archive:
        for name in INCLUDE:
            source = ROOT / name
            if source.exists():
                add_tree(archive, source)
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size, info.uid, info.gid, info.mtime = len(payload), 0, 0, 0
        info.uname = info.gname = "root"
        archive.addfile(info, __import__("io").BytesIO(payload))
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(digest + "  " + args.output.name + "\n", encoding="ascii")
    print(f"created development rootfs: {args.output}\nsha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
