#!/usr/bin/env python3
"""Create a reproducible gzip-compressed newc initramfs from a staging tree."""
from __future__ import annotations

import argparse
import gzip
import os
from pathlib import Path


def entry(name: str, mode: int, data: bytes, ino: int) -> bytes:
    namesize = len(name.encode()) + 1
    header = "070701" + "".join(f"{value:08x}" for value in (ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, namesize, 0))
    blob = header.encode() + name.encode() + b"\0"
    blob += b"\0" * ((-len(blob)) % 4) + data
    return blob + b"\0" * ((-len(blob)) % 4)


def build(staging: Path) -> bytes:
    records: list[bytes] = []
    ino = 1
    for path in sorted(staging.rglob("*")):
        relative = path.relative_to(staging).as_posix()
        if path.is_symlink():
            raise ValueError(f"symlinks are not supported in this deterministic builder: {relative}")
        mode = 0o040755 if path.is_dir() else 0o100644
        data = b"" if path.is_dir() else path.read_bytes()
        records.append(entry(relative, mode, data, ino)); ino += 1
    records.append(entry("TRAILER!!!", 0, b"", ino))
    return b"".join(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = build(args.staging)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    print(f"created initramfs: {args.output} ({len(raw)} bytes uncompressed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
