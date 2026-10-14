#!/usr/bin/env python3
"""Deterministic Android boot-image v0 creator and structural inspector.

This implements the legacy Android boot header used by the cited community
j2corelte recovery tree.  It cannot prove a produced image boots on hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

MAGIC = b"ANDROID!"
HEADER = struct.Struct("<8s10I16s512s32s1024s")
PAGE_SIZES = {2048, 4096, 8192, 16384}
SAMSUNG_TRAILER = b"SEANDROIDENFORCE"
DEFAULT_SECOND_OFFSET = 0x00F00000
CMDLINE_MAX = 511        # always NUL-terminated
EXTRA_CMDLINE_MAX = 1023


def align(value: int, page_size: int) -> int:
    return (value + page_size - 1) // page_size * page_size


def padded(data: bytes, page_size: int) -> bytes:
    return data + b"\0" * (align(len(data), page_size) - len(data))


def image_id(kernel: bytes, ramdisk: bytes, second: bytes, dt: bytes) -> bytes:
    """The SHA-1 AOSP mkbootimg stores in the header (sizes included)."""
    digest = hashlib.sha1()
    for blob in (kernel, ramdisk, second):
        digest.update(blob)
        digest.update(struct.pack("<I", len(blob)))
    if dt:
        digest.update(dt)
        digest.update(struct.pack("<I", len(dt)))
    return digest.digest()


def _command_line(value: str, limit: int, name: str) -> bytes:
    encoded = value.encode("ascii")  # raises UnicodeEncodeError (a ValueError) for non-ASCII
    if b"\0" in encoded:
        raise ValueError(f"{name} must not contain NUL")
    if len(encoded) > limit:
        raise ValueError(f"{name} exceeds {limit} bytes")
    return encoded.ljust(limit + 1, b"\0")


def pack(kernel: bytes, ramdisk: bytes, dt: bytes, *, base: int, kernel_offset: int,
         ramdisk_offset: int, tags_offset: int, page_size: int, board: str = "",
         cmdline: str = "", extra_cmdline: str = "", second_offset: int = DEFAULT_SECOND_OFFSET,
         samsung_trailer: bool = False, max_bytes: int | None = None) -> bytes:
    if page_size not in PAGE_SIZES:
        raise ValueError("unsupported Android boot page size")
    if len(board.encode()) > 15:
        raise ValueError("board name exceeds Android boot header limit")
    if not kernel:
        raise ValueError("kernel image is empty")
    command = _command_line(cmdline, CMDLINE_MAX, "cmdline")
    extra = _command_line(extra_cmdline, EXTRA_CMDLINE_MAX, "extra cmdline")
    ident = image_id(kernel, ramdisk, b"", dt).ljust(32, b"\0")
    header = HEADER.pack(
        MAGIC, len(kernel), base + kernel_offset, len(ramdisk), base + ramdisk_offset,
        0, base + second_offset, base + tags_offset, page_size, len(dt), 0,
        board.encode().ljust(16, b"\0"), command[:512].ljust(512, b"\0"), ident,
        extra[:1024].ljust(1024, b"\0"),
    )
    image = padded(header, page_size) + padded(kernel, page_size) + padded(ramdisk, page_size) + padded(dt, page_size)
    if samsung_trailer:
        image += SAMSUNG_TRAILER
    if max_bytes is not None and len(image) > max_bytes:
        raise ValueError(f"image is {len(image)} bytes, over the {max_bytes}-byte partition limit")
    return image


def _text(field: bytes) -> str:
    return field.split(b"\0", 1)[0].decode("ascii", "replace")


def _split(blob: bytes, max_bytes: int | None = None) -> tuple[dict, bytes, bytes, bytes, bytes]:
    if len(blob) < HEADER.size:
        raise ValueError("file is shorter than an Android boot header")
    fields = HEADER.unpack(blob[:HEADER.size])
    if fields[0] != MAGIC:
        raise ValueError("Android boot magic is missing")
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr = fields[1:7]
    tags_addr, page_size, dt_size = fields[7:10]
    if page_size not in PAGE_SIZES:
        raise ValueError("invalid boot header page size")
    if kernel_size == 0:
        raise ValueError("boot image declares an empty kernel")
    required = (page_size + align(kernel_size, page_size) + align(ramdisk_size, page_size)
                + align(second_size, page_size) + align(dt_size, page_size))
    if len(blob) < required:
        raise ValueError(f"truncated image: expected at least {required}, got {len(blob)}")
    trailing = blob[required:]
    samsung = trailing.startswith(SAMSUNG_TRAILER)
    remainder = trailing[len(SAMSUNG_TRAILER):] if samsung else trailing
    if remainder.strip(b"\0"):
        raise ValueError("unrecognized trailing data after the boot image")
    if max_bytes is not None and len(blob) > max_bytes:
        raise ValueError(f"image is {len(blob)} bytes, over the {max_bytes}-byte partition limit")
    offset = page_size
    kernel = blob[offset:offset + kernel_size]
    offset += align(kernel_size, page_size)
    ramdisk = blob[offset:offset + ramdisk_size]
    offset += align(ramdisk_size, page_size)
    second = blob[offset:offset + second_size]
    offset += align(second_size, page_size)
    dt = blob[offset:offset + dt_size]
    base = kernel_addr - 0x8000  # AOSP default kernel offset; an assumption, not a header field
    meta = {"format": "android-boot-v0", "kernel_size": kernel_size, "kernel_addr": hex(kernel_addr),
            "ramdisk_size": ramdisk_size, "ramdisk_addr": hex(ramdisk_addr),
            "second_size": second_size, "second_addr": hex(second_addr),
            "dt_size": dt_size, "tags_addr": hex(tags_addr), "page_size": page_size,
            "board": _text(fields[11]), "cmdline": _text(fields[12]), "extra_cmdline": _text(fields[14]),
            "samsung_trailer": samsung, "zero_padding": len(remainder),
            "id_matches_content": fields[13][:20] == image_id(kernel, ramdisk, second, dt),
            "derived_offsets": {"assumption": "base = kernel_addr - 0x8000", "base": hex(base),
                                "kernel_offset": "0x8000", "ramdisk_offset": hex(ramdisk_addr - base),
                                "second_offset": hex(second_addr - base), "tags_offset": hex(tags_addr - base)},
            "sha256": hashlib.sha256(blob).hexdigest()}
    return meta, kernel, ramdisk, second, dt


def inspect(blob: bytes, *, max_bytes: int | None = None) -> dict:
    return _split(blob, max_bytes)[0]


def unpack(blob: bytes, *, max_bytes: int | None = None) -> dict:
    """Return the header metadata plus the kernel/ramdisk/second/dt payloads."""
    meta, kernel, ramdisk, second, dt = _split(blob, max_bytes)
    return {"meta": meta, "kernel": kernel, "ramdisk": ramdisk, "second": second, "dt": dt}


def _int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--kernel", type=Path, required=True)
    create.add_argument("--ramdisk", type=Path, required=True)
    create.add_argument("--dt", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--base", type=_int, required=True)
    create.add_argument("--kernel-offset", type=_int, required=True)
    create.add_argument("--ramdisk-offset", type=_int, required=True)
    create.add_argument("--tags-offset", type=_int, required=True)
    create.add_argument("--second-offset", type=_int, default=DEFAULT_SECOND_OFFSET)
    create.add_argument("--page-size", type=int, required=True)
    create.add_argument("--board", default="")
    create.add_argument("--cmdline", default="", help="kernel command line (<= 511 ASCII bytes)")
    create.add_argument("--extra-cmdline", default="", help="continuation (<= 1023 ASCII bytes)")
    create.add_argument("--samsung-trailer", action="store_true",
                        help="append SEANDROIDENFORCE (unverified requirement on this device)")
    create.add_argument("--max-bytes", type=_int, default=None, help="partition size limit")
    unpack_cmd = sub.add_parser("unpack")
    unpack_cmd.add_argument("image", type=Path)
    unpack_cmd.add_argument("--out", type=Path, required=True)
    show = sub.add_parser("inspect")
    show.add_argument("image", type=Path)
    show.add_argument("--max-bytes", type=_int, default=None)
    args = parser.parse_args()
    if args.action == "create":
        image = pack(args.kernel.read_bytes(), args.ramdisk.read_bytes(), args.dt.read_bytes(), base=args.base,
                     kernel_offset=args.kernel_offset, ramdisk_offset=args.ramdisk_offset,
                     tags_offset=args.tags_offset, page_size=args.page_size, board=args.board,
                     cmdline=args.cmdline, extra_cmdline=args.extra_cmdline,
                     second_offset=args.second_offset, samsung_trailer=args.samsung_trailer,
                     max_bytes=args.max_bytes)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
        print(inspect(image, max_bytes=args.max_bytes))
    elif args.action == "unpack":
        parts = unpack(args.image.read_bytes())
        args.out.mkdir(parents=True, exist_ok=True)
        for name in ("kernel", "ramdisk", "second", "dt"):
            if parts[name]:
                (args.out / name).write_bytes(parts[name])
        (args.out / "header.json").write_text(json.dumps(parts["meta"], indent=2) + "\n", encoding="utf-8", newline="\n")
        print(parts["meta"])
    else:
        print(inspect(args.image.read_bytes(), max_bytes=args.max_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
