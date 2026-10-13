#!/usr/bin/env python3
"""Create a reproducible gzip-compressed newc initramfs from a staging tree.

Modes come from ``fsmodes`` (not the host), symlinks are preserved, /dev/console
and /dev/null are created, and a real /init is installed.
"""
from __future__ import annotations

import argparse
import gzip
import os
from pathlib import Path

try:
    from tooling.fsmodes import file_mode
except ImportError:  # executed as a script: python tooling/build_initramfs.py
    from fsmodes import file_mode

DEFAULT_INIT = Path(__file__).resolve().parents[1] / "core" / "initramfs" / "init"
S_DIR, S_REG, S_LNK, S_CHR = 0o040000, 0o100000, 0o120000, 0o020000


def entry(name: str, mode: int, data: bytes = b"", ino: int = 0, *, nlink: int = 1,
          rdev: tuple[int, int] = (0, 0)) -> bytes:
    encoded = name.encode("utf-8")
    namesize = len(encoded) + 1
    fields = (ino, mode, 0, 0, nlink, 0, len(data), 0, 0, rdev[0], rdev[1], namesize, 0)
    blob = b"070701" + "".join(f"{value:08x}" for value in fields).encode("ascii") + encoded + b"\0"
    blob += b"\0" * ((-len(blob)) % 4) + data
    return blob + b"\0" * ((-len(blob)) % 4)


def _scan(staging: Path) -> dict[str, tuple[int, bytes, tuple[int, int]]]:
    nodes: dict[str, tuple[int, bytes, tuple[int, int]]] = {}
    for current, directories, files in os.walk(staging, followlinks=False):
        base = Path(current)
        for name in list(directories) + files:
            path = base / name
            relative = path.relative_to(staging).as_posix()
            if path.is_symlink():
                nodes[relative] = (S_LNK | 0o777, os.readlink(path).replace("\\", "/").encode(), (0, 0))
            elif path.is_dir():
                nodes[relative] = (S_DIR | 0o755, b"", (0, 0))
            else:
                data = path.read_bytes()
                nodes[relative] = (S_REG | file_mode(relative, data), data, (0, 0))
    return nodes


def build(staging: Path, *, init: bytes | None = None, extra_symlinks: dict[str, str] | None = None,
          device_nodes: bool = True) -> bytes:
    nodes = _scan(Path(staging))
    for link, target in (extra_symlinks or {}).items():
        link = link.strip("/")
        if link in nodes:
            raise ValueError(f"symlink collides with an existing path: {link}")
        nodes[link] = (S_LNK | 0o777, target.encode(), (0, 0))
    if "init" not in nodes:
        if init is None:
            raise ValueError("staging tree has no /init and none was supplied")
        nodes["init"] = (S_REG | 0o755, init, (0, 0))
    if device_nodes:
        nodes.setdefault("dev", (S_DIR | 0o755, b"", (0, 0)))
        for name, mode, rdev in (("dev/console", 0o600, (5, 1)), ("dev/null", 0o666, (1, 3))):
            if name in nodes:
                raise ValueError(f"staging tree must not contain {name}")
            nodes[name] = (S_CHR | mode, b"", rdev)
    # Parents always sort before their children, so this order is valid cpio order.
    records = []
    for ino, relative in enumerate(sorted(nodes), start=1):
        mode, data, rdev = nodes[relative]
        nlink = 2 if (mode & 0o170000) == S_DIR else 1
        records.append(entry(relative, mode, data, ino, nlink=nlink, rdev=rdev))
    records.append(entry("TRAILER!!!", 0, b"", len(nodes) + 1))
    return b"".join(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--init", type=Path, default=DEFAULT_INIT,
                        help="used only when the staging tree has no /init")
    parser.add_argument("--symlink", action="append", default=[], metavar="LINK=TARGET",
                        help="add a symlink (needed on hosts that cannot hold symlinks)")
    parser.add_argument("--no-device-nodes", action="store_true")
    args = parser.parse_args()
    links = dict(item.split("=", 1) for item in args.symlink)
    raw = build(args.staging, init=args.init.read_bytes() if args.init.is_file() else None,
                extra_symlinks=links, device_nodes=not args.no_device_nodes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    print(f"created initramfs: {args.output} ({len(raw)} bytes uncompressed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
