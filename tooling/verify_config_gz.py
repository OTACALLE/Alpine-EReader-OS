#!/usr/bin/env python3
"""Validate a /proc/config.gz capture and summarize what it means for the port."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path

#: option -> why the port cares
KEY_OPTIONS = {
    "ARM": "32-bit ARM kernel (matches the armv7 userspace decision, ADR 0002)",
    "ARM64": "64-bit kernel (would contradict ADR 0002)",
    "BLK_DEV_INITRD": "initramfs support (required by core/initramfs/init)",
    "DEVTMPFS": "devtmpfs for /dev",
    "DEVTMPFS_MOUNT": "automatic devtmpfs mount",
    "TMPFS": "tmpfs",
    "PROC_FS": "procfs",
    "SYSFS": "sysfs",
    "MODULES": "loadable modules",
    "VT": "virtual terminals",
    "VT_CONSOLE": "console on virtual terminals",
    "FB": "framebuffer driver layer",
    "FRAMEBUFFER_CONSOLE": "on-screen text console (fbcon)",
    "DRM": "DRM/KMS display",
    "SERIAL_SAMSUNG": "Samsung UART driver",
    "SERIAL_SAMSUNG_CONSOLE": "console over the Samsung UART",
    "USB_GADGET": "USB gadget (serial/ADB console over USB)",
    "USB_G_ANDROID": "Android composite gadget",
    "PSTORE": "pstore (logs that survive a crash/reboot)",
    "PSTORE_RAM": "ramoops pstore backend",
    "ANDROID_RAM_CONSOLE": "Samsung/Android RAM console (last_kmsg)",
    "EXT4_FS": "ext4 root/data",
    "F2FS_FS": "f2fs",
    "SQUASHFS": "squashfs read-only system image",
    "OVERLAY_FS": "overlayfs",
    "MMC_DW": "Synopsys DesignWare MMC (eMMC controller)",
    "DM_CRYPT": "dm-crypt (userdata encryption)",
    "RFKILL": "rfkill (radio kill switch used by powerd)",
    "SUSPEND": "suspend-to-RAM",
    "PM_SLEEP": "sleep states",
    "CGROUPS": "cgroups",
    "NAMESPACES": "namespaces",
}
#: not fatal, but the port is blocked/limited without them
WARN_IF_MISSING = {
    "BLK_DEV_INITRD": "initramfs boot will not work",
    "DEVTMPFS": "/dev will not be populated automatically",
    "PROC_FS": "no /proc",
    "SYSFS": "no /sys",
}


class ConfigGzError(Exception):
    pass


def read_config(path: Path) -> tuple[str, bytes]:
    raw = Path(path).read_bytes()
    if raw[:2] != b"\x1f\x8b":
        hint = " (looks like text: was it redirected as text?)" if raw[:1].isascii() and raw[:1] != b"" else ""
        raise ConfigGzError(f"not a gzip file: bad magic {raw[:2].hex()}{hint}")
    try:
        return gzip.decompress(raw).decode("utf-8", "replace"), raw
    except (OSError, EOFError, zlib.error) as error:
        mangled = b"\r\n" in raw
        hint = ("; the file contains CRLF bytes, which is what PowerShell/text-mode redirection does. "
                "Recollect with tooling/collect_device_evidence.py (binary-safe)") if mangled else ""
        raise ConfigGzError(f"corrupt gzip stream: {error}{hint}") from error


def parse_options(text: str) -> dict[str, str]:
    options: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r'CONFIG_(\w+)=(.*)$', line)
        if match:
            options[match.group(1)] = match.group(2).strip('"')
            continue
        match = re.match(r'# CONFIG_(\w+) is not set$', line)
        if match:
            options[match.group(1)] = "n"
    return options


def analyze(path: Path) -> dict:
    text, raw = read_config(path)
    options = parse_options(text)
    header = re.search(r"^# Linux/(\S+) (\S+) Kernel Configuration", text, re.M)
    state = lambda name: options.get(name, "absent")  # noqa: E731
    report = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "options_total": len(options),
              "header_architecture": header.group(1) if header else None,
              "header_kernel_version": header.group(2) if header else None,
              "key_options": {name: state(name) for name in KEY_OPTIONS}, "errors": [], "warnings": []}
    if options.get("ARM64") == "y":
        report["errors"].append("CONFIG_ARM64=y: the kernel is 64-bit, contradicting the armv7 userspace decision")
    if options.get("ARM") != "y" and options.get("ARM64") != "y":
        report["errors"].append("neither CONFIG_ARM nor CONFIG_ARM64 is set: this is not an ARM kernel config")
    for name, consequence in WARN_IF_MISSING.items():
        if options.get(name) != "y":
            report["warnings"].append(f"CONFIG_{name} is {state(name)}: {consequence}")
    console = [name for name in ("VT_CONSOLE", "FRAMEBUFFER_CONSOLE", "SERIAL_SAMSUNG_CONSOLE") if options.get(name) == "y"]
    report["console_options_enabled"] = console
    if not console:
        report["warnings"].append("no kernel console option is enabled: bring-up needs pstore/last_kmsg or a rebuilt kernel")
    return report


def check_against_profile(report: dict, profile: dict) -> list[str]:
    problems = []
    version = profile.get("kernel", {}).get("version", "")
    header_version = report.get("header_kernel_version")
    if header_version and version and not version.startswith(header_version):
        problems.append(f"config is for kernel {header_version}, profile says {version}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--profile", type=Path, default=Path("devices/samsung-j2core/device-profile.json"))
    args = parser.parse_args(argv)
    try:
        report = analyze(args.config)
    except ConfigGzError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.profile.exists():
        report["errors"].extend(check_against_profile(report, json.loads(args.profile.read_text(encoding="utf-8"))))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    for message in report["errors"]:
        print("ERROR:", message, file=sys.stderr)
    for message in report["warnings"]:
        print("warning:", message)
    print(f"{report['options_total']} options; console options enabled: {report['console_options_enabled'] or 'none'}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
