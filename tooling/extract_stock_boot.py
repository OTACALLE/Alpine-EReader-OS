#!/usr/bin/env python3
"""Extract and describe the stock boot.img from a Samsung AP firmware archive.

Read-only analysis: nothing is flashed.  The extracted image is copyrighted
firmware and must not be committed (``devices/*/stock/`` and ``dist/`` are
ignored).  The JSON report (no firmware bytes) is what gets committed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import zlib
from pathlib import Path

try:
    from tooling import android_bootimg, j2core_capture
except ImportError:  # executed as a script
    import android_bootimg
    import j2core_capture

CHUNK = 1 << 20
MD5_LINE = re.compile(rb"([0-9a-fA-F]{32})[ \t]+\*?(\S+)[ \t]*\r?\n?$")
BOOT_MEMBERS = ("boot.img", "boot.img.lz4")


class StockBootError(Exception):
    pass


def hash_and_check_md5(path: Path) -> dict:
    """SHA-256 of the whole file plus Samsung ``.tar.md5`` verification (an MD5 line is appended to the tar)."""
    size = path.stat().st_size
    with path.open("rb") as stream:
        stream.seek(max(0, size - 512))
        tail = stream.read()
    match = MD5_LINE.search(tail)
    body_end = size - len(tail) + match.start() if match else size
    sha, md5, position = hashlib.sha256(), hashlib.md5(), 0  # noqa: S324 - integrity check of the Samsung .tar.md5 format, not security
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            sha.update(chunk)
            take = max(0, min(len(chunk), body_end - position))
            md5.update(chunk[:take])
            position += len(chunk)
    result = {"sha256": sha.hexdigest(), "bytes": size, "md5_line_present": bool(match)}
    if match:
        result["md5_expected"] = match.group(1).decode().lower()
        result["md5_actual"] = md5.hexdigest()
        result["md5_verified"] = result["md5_expected"] == result["md5_actual"]
    return result


def read_boot_image(path: Path) -> tuple[str, bytes]:
    try:
        archive = tarfile.open(path, mode="r:")
    except tarfile.TarError as error:
        raise StockBootError(f"not a readable tar archive: {error}") from error
    with archive:
        for member in archive:
            if member.name.split("/")[-1] in BOOT_MEMBERS and member.isfile():
                data = archive.extractfile(member).read()
                if member.name.endswith(".lz4"):
                    try:
                        import lz4.frame  # type: ignore
                    except ImportError as error:
                        raise StockBootError("boot.img.lz4 needs the 'lz4' package: pip install lz4") from error
                    data = lz4.frame.decompress(data)
                return member.name, data
    raise StockBootError("no boot.img or boot.img.lz4 in the archive (is this the AP file?)")


BANNER = re.compile(rb"Linux version \d[^\n\x00]{20,300}")


def find_linux_banner(kernel: bytes) -> str | None:
    """The kernel's embedded `Linux version ...` banner (gunzips a compressed kernel first)."""
    if kernel[:2] == b"\x1f\x8b":
        try:
            kernel = zlib.decompressobj(31).decompress(kernel)
        except zlib.error:
            return None
    match = BANNER.search(kernel)
    return match.group(0).decode("ascii", "replace").strip() if match else None


def describe(path: Path, out_dir: Path | None = None, device_banner: str | None = None) -> dict:
    integrity = hash_and_check_md5(path)
    if integrity.get("md5_line_present") and not integrity["md5_verified"]:
        raise StockBootError("MD5 trailer does not match: the download is corrupt, do not use it")
    member, image = read_boot_image(path)
    parts = android_bootimg.unpack(image)
    report = {"source_file": path.name, "source": integrity, "boot_member": member,
              "boot_img": {"bytes": len(image), "sha256": hashlib.sha256(image).hexdigest()},
              "header": {key: value for key, value in parts["meta"].items() if key != "sha256"}}
    banner = find_linux_banner(parts["kernel"])
    report["kernel_banner"] = banner
    report["device_banner"] = device_banner
    report["matches_device"] = None if banner is None or device_banner is None else banner == device_banner
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "boot.img").write_bytes(image)
        for name in ("kernel", "ramdisk", "dt"):
            if parts[name]:
                (out_dir / name).write_bytes(parts[name])
    return report


def boot_parameters_diff(parameters: dict, report: dict) -> dict[str, tuple]:
    """Differences between the committed candidate parameters and the stock header."""
    header, derived = report["header"], report["header"]["derived_offsets"]
    observed = {"page_size": header["page_size"], "board": header["board"], "base": derived["base"],
                "kernel_offset": derived["kernel_offset"], "ramdisk_offset": derived["ramdisk_offset"],
                "tags_offset": derived["tags_offset"], "cmdline": header["cmdline"] or None}

    def norm(key, value):
        if key.endswith("offset") or key == "base":
            return int(value, 0) if isinstance(value, str) else value
        return value
    return {key: (parameters.get(key), observed[key]) for key in observed
            if norm(key, parameters.get(key)) != norm(key, observed[key])}


def apply_boot_parameters(parameters: dict, report: dict) -> dict:
    header, derived = report["header"], report["header"]["derived_offsets"]
    updated = dict(parameters)
    updated.update({"base": derived["base"], "page_size": header["page_size"], "board": header["board"],
                    "kernel_offset": derived["kernel_offset"], "ramdisk_offset": derived["ramdisk_offset"],
                    "tags_offset": derived["tags_offset"], "cmdline": header["cmdline"] or None,
                    "cmdline_status": f"read from stock boot.img sha256:{report['boot_img']['sha256']}",
                    "confidence": "offsets and cmdline come from the stock boot.img header; "
                                  "boot partition capacity is verified; no custom boot image has been tested"})
    updated["kernel_image_format"] = f"{header['kernel_format']} (from stock boot.img sha256:{report['boot_img']['sha256']})"
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ap", type=Path, required=True, help="AP_*.tar.md5 from the stock firmware")
    parser.add_argument("--out", type=Path, default=Path("devices/samsung-j2core/stock"),
                        help="where to extract boot.img, kernel, ramdisk, dt (git-ignored)")
    parser.add_argument("--report", type=Path, default=Path("devices/samsung-j2core/stock-boot-report.json"))
    parser.add_argument("--boot-parameters", type=Path, default=Path("devices/samsung-j2core/boot-parameters.json"))
    parser.add_argument("--apply", action="store_true", help="write the stock values into boot-parameters.json")
    args = parser.parse_args(argv)
    try:
        device_banner = j2core_capture.parse_linux_banner(j2core_capture.read_docx_text())
    except (OSError, KeyError, ValueError):
        device_banner = None
    try:
        report = describe(args.ap, args.out, device_banner)
    except (StockBootError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    parameters = json.loads(args.boot_parameters.read_text(encoding="utf-8"))
    report["differs_from_candidate_parameters"] = {k: list(v) for k, v in boot_parameters_diff(parameters, report).items()}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["header"], indent=2))
    print("differences vs candidate boot-parameters.json:", report["differs_from_candidate_parameters"] or "none")
    if report["matches_device"] is False:
        print("WARNING: this boot.img is NOT the kernel build running on the phone (banner differs).", file=sys.stderr)
        print(f"  firmware: {report['kernel_banner']}\n  device:   {report['device_banner']}", file=sys.stderr)
        if args.apply:
            print("refusing --apply: parameters must come from the build installed on the device", file=sys.stderr)
        return 3
    print("kernel banner:", {True: "MATCHES the phone's /proc/version", None: "not checked (no banner or no device capture)"}[report["matches_device"]])
    if args.apply:
        args.boot_parameters.write_text(json.dumps(apply_boot_parameters(parameters, report), indent=2) + "\n",
                                        encoding="utf-8", newline="\n")
        print(f"updated {args.boot_parameters}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
