#!/usr/bin/env python3
"""Deterministic Android boot-image v0 creator and structural inspector.

This implements the legacy Android boot header used by the cited community
j2corelte recovery tree.  It cannot prove a produced image boots on hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

MAGIC = b"ANDROID!"
HEADER = struct.Struct("<8s10I16s512s32s1024s")


def align(value: int, page_size: int) -> int:
    return (value + page_size - 1) // page_size * page_size


def padded(data: bytes, page_size: int) -> bytes:
    return data + b"\0" * (align(len(data), page_size) - len(data))


def pack(kernel: bytes, ramdisk: bytes, dt: bytes, *, base: int, kernel_offset: int,
         ramdisk_offset: int, tags_offset: int, page_size: int, board: str = "") -> bytes:
    if page_size not in {2048, 4096, 8192, 16384}:
        raise ValueError("unsupported Android boot page size")
    if len(board.encode()) > 16:
        raise ValueError("board name exceeds Android boot header limit")
    image_id = hashlib.sha1(kernel + ramdisk + dt).digest().ljust(32, b"\0")
    header = HEADER.pack(
        MAGIC, len(kernel), base + kernel_offset, len(ramdisk), base + ramdisk_offset,
        0, 0, base + tags_offset, page_size, len(dt), 0,
        board.encode().ljust(16, b"\0"), b"\0" * 512, image_id, b"\0" * 1024,
    )
    return padded(header, page_size) + padded(kernel, page_size) + padded(ramdisk, page_size) + padded(dt, page_size)


def inspect(blob: bytes) -> dict:
    if len(blob) < HEADER.size:
        raise ValueError("file is shorter than an Android boot header")
    fields = HEADER.unpack(blob[:HEADER.size])
    if fields[0] != MAGIC:
        raise ValueError("Android boot magic is missing")
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr = fields[1:5]
    tags_addr, page_size, dt_size = fields[7:10]
    if page_size not in {2048, 4096, 8192, 16384}:
        raise ValueError("invalid boot header page size")
    required = page_size + align(kernel_size, page_size) + align(ramdisk_size, page_size) + align(dt_size, page_size)
    if len(blob) != required:
        raise ValueError(f"unexpected image length: expected {required}, got {len(blob)}")
    return {"format": "android-boot-v0", "kernel_size": kernel_size, "kernel_addr": hex(kernel_addr),
            "ramdisk_size": ramdisk_size, "ramdisk_addr": hex(ramdisk_addr), "dt_size": dt_size,
            "tags_addr": hex(tags_addr), "page_size": page_size,
            "board": fields[11].rstrip(b"\0").decode("ascii", "replace"),
            "sha256": hashlib.sha256(blob).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--kernel", type=Path, required=True)
    create.add_argument("--ramdisk", type=Path, required=True)
    create.add_argument("--dt", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--base", type=lambda x: int(x, 0), required=True)
    create.add_argument("--kernel-offset", type=lambda x: int(x, 0), required=True)
    create.add_argument("--ramdisk-offset", type=lambda x: int(x, 0), required=True)
    create.add_argument("--tags-offset", type=lambda x: int(x, 0), required=True)
    create.add_argument("--page-size", type=int, required=True)
    create.add_argument("--board", default="")
    show = sub.add_parser("inspect")
    show.add_argument("image", type=Path)
    args = parser.parse_args()
    if args.action == "create":
        image = pack(args.kernel.read_bytes(), args.ramdisk.read_bytes(), args.dt.read_bytes(), base=args.base,
                     kernel_offset=args.kernel_offset, ramdisk_offset=args.ramdisk_offset,
                     tags_offset=args.tags_offset, page_size=args.page_size, board=args.board)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
        print(inspect(image))
    else:
        print(inspect(args.image.read_bytes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
