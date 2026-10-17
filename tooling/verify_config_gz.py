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
    "ARM": "32-bit ARM kernel",
    "ARM64": "64-bit kernel (a 32-bit userspace then needs COMPAT)",
    "COMPAT": "32-bit (AArch32) userspace on an arm64 kernel",
    "ARM64_4K_PAGES": "4 KiB pages",
    "CMDLINE": "built-in kernel command line (empty = bootloader/boot.img supplies it)",
    "RD_GZIP": "gzip initramfs (the only compression such a kernel may support)",
    "RD_XZ": "xz initramfs", "RD_LZ4": "lz4 initramfs",
    "PSTORE_CONSOLE": "kernel log saved to pstore across a crash",
    "SEC_DEBUG_LAST_KMSG": "Samsung last_kmsg (previous boot's kernel log)",
    "EXYNOS_DECON_FB": "Exynos DECON framebuffer display driver (fbdev)",
    "FB_SIMPLE": "simple framebuffer",
    "USB_F_ACM": "USB serial (ACM) gadget function",
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
    "ZRAM": "compressed RAM swap",
    "OVERLAY_FS": "overlayfs",
    "MMC_DW": "Synopsys DesignWare MMC (eMMC controller)",
    "DM_CRYPT": "dm-crypt (userdata encryption)",
    "RFKILL": "rfkill (radio kill switch used by powerd, ARCHITECTURE.md section 17)",
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
    "COMPAT": None,  # only a problem for an arm64 kernel with 32-bit userspace; handled in check_against_profile
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
    if options.get("ARM") != "y" and options.get("ARM64") != "y":
        report["errors"].append("neither CONFIG_ARM nor CONFIG_ARM64 is set: this is not an ARM kernel config")
    architecture = "arm64" if options.get("ARM64") == "y" else "arm" if options.get("ARM") == "y" else None
    report["kernel_architecture"] = architecture
    report["default_cmdline"] = options.get("CMDLINE", "") or None
    report["initramfs_compression"] = [name.removeprefix("RD_").lower() for name in ("RD_GZIP", "RD_BZIP2", "RD_LZMA", "RD_XZ", "RD_LZO", "RD_LZ4")
                                       if options.get(name) == "y"]
    report["display_backends"] = {"drm_kms": options.get("DRM") == "y",
                                  "fbdev_exynos_decon": options.get("EXYNOS_DECON_FB") == "y"}
    for name, consequence in WARN_IF_MISSING.items():
        if consequence and options.get(name) != "y":
            report["warnings"].append(f"CONFIG_{name} is {state(name)}: {consequence}")
    if options.get("BLK_DEV_INITRD") == "y" and not report["initramfs_compression"]:
        report["warnings"].append("no initramfs decompressor is enabled")
    if options.get("RFKILL") != "y":
        report["warnings"].append("CONFIG_RFKILL is not enabled: the power policy cannot block radios on this kernel as built")
    if options.get("DRM") != "y":
        report["warnings"].append("CONFIG_DRM is not enabled: the display is not DRM/KMS on this kernel as built")
    if options.get("SQUASHFS") != "y" and options.get("OVERLAY_FS") != "y":
        report["warnings"].append("neither SQUASHFS nor OVERLAY_FS is enabled: a read-only /usr needs ext4 mounted read-only or a rebuild")
    console = [name for name in ("VT_CONSOLE", "FRAMEBUFFER_CONSOLE", "SERIAL_SAMSUNG_CONSOLE") if options.get(name) == "y"]
    report["console_options_enabled"] = console
    if not console:
        report["warnings"].append("no kernel console option is enabled: bring-up needs pstore/last_kmsg or a rebuilt kernel")
    if not {"VT_CONSOLE", "FRAMEBUFFER_CONSOLE"} & set(console):
        report["warnings"].append("no on-screen kernel console (VT/fbcon): early output needs a UART, the USB ACM gadget or pstore")
    return report


def check_against_profile(report: dict, profile: dict) -> list[str]:
    problems = []
    runtime = profile.get("runtime", {})
    kernel_arch, userspace = report.get("kernel_architecture"), runtime.get("initial_userspace_architecture")
    if runtime.get("kernel_architecture") and kernel_arch and runtime["kernel_architecture"] != kernel_arch:
        problems.append(f"profile says kernel architecture {runtime['kernel_architecture']}, config says {kernel_arch}")
    if userspace == "armv7" and kernel_arch == "arm64" and report["key_options"].get("COMPAT") != "y":
        problems.append("armv7 userspace on an arm64 kernel needs CONFIG_COMPAT=y")
    if userspace == "aarch64" and kernel_arch != "arm64":
        problems.append("aarch64 userspace needs an arm64 kernel")
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
    print(f"{report['options_total']} options; {report['kernel_architecture']} kernel; "
          f"console options enabled: {report['console_options_enabled'] or 'none'}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
