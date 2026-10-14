#!/usr/bin/env python3
"""Collect device evidence over ADB with a fixed allowlist of READ-ONLY commands.

Binary-safe (no shell redirection), so ``/proc/config.gz`` arrives intact.  The
tool accepts no user-supplied device commands, flashes nothing and changes no
device state.  The phone must be booted into Android with USB debugging enabled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    from tooling import verify_config_gz
except ImportError:  # executed as a script
    import verify_config_gz

#: name -> (adb arguments, output suffix).  Every entry only reads.
COMMANDS: dict[str, tuple[list[str], str]] = {
    "uname": (["shell", "uname", "-a"], ".txt"),
    "proc_version": (["shell", "cat", "/proc/version"], ".txt"),
    "cmdline": (["shell", "cat", "/proc/cmdline"], ".txt"),
    "cpuinfo": (["shell", "cat", "/proc/cpuinfo"], ".txt"),
    "meminfo": (["shell", "cat", "/proc/meminfo"], ".txt"),
    "partitions": (["shell", "cat", "/proc/partitions"], ".txt"),
    "mounts": (["shell", "cat", "/proc/mounts"], ".txt"),
    "devices": (["shell", "cat", "/proc/devices"], ".txt"),
    "modules": (["shell", "cat", "/proc/modules"], ".txt"),
    "input_devices": (["shell", "cat", "/proc/bus/input/devices"], ".txt"),
    "getprop": (["shell", "getprop"], ".txt"),
    "by_name": (["shell", "ls", "-l", "/dev/block/platform/13540000.dwmmc0/by-name/"], ".txt"),
    "dev_listing": (["shell", "ls", "-l", "/dev/"], ".txt"),
    "pstore": (["shell", "ls", "-l", "/sys/fs/pstore/"], ".txt"),
    "rfkill": (["shell", "ls", "/sys/class/rfkill/"], ".txt"),
    "backlight": (["shell", "ls", "/sys/class/backlight/"], ".txt"),
    "framebuffer_modes": (["shell", "cat", "/sys/class/graphics/fb0/modes"], ".txt"),
    "display_size": (["shell", "wm", "size"], ".txt"),
    "battery": (["shell", "dumpsys", "battery"], ".txt"),
    "selinux": (["shell", "getenforce"], ".txt"),
    "whoami": (["shell", "id"], ".txt"),
    "dmesg": (["shell", "dmesg"], ".txt"),
    "config_gz": (["exec-out", "cat", "/proc/config.gz"], ".gz"),
}
READ_ONLY_PROGRAMS = {"cat", "ls", "getprop", "uname", "dumpsys", "wm", "getenforce", "id", "dmesg"}
FORBIDDEN_CHARACTERS = set(";&|<>`$()\\'\"")


class CollectionError(Exception):
    pass


def assert_read_only() -> None:
    """Self-check run before every collection (and by the tests)."""
    for name, (arguments, _suffix) in COMMANDS.items():
        if arguments[0] not in {"shell", "exec-out"} or arguments[1] not in READ_ONLY_PROGRAMS:
            raise CollectionError(f"{name}: not an allowlisted read-only command")
        if arguments[1] == "dumpsys" and arguments[2:] != ["battery"]:
            raise CollectionError(f"{name}: dumpsys is only allowed for the battery service")
        if any(FORBIDDEN_CHARACTERS & set(argument) for argument in arguments):
            raise CollectionError(f"{name}: shell metacharacters are not allowed")


def _run(adb: str, serial: str | None, arguments: list[str], runner, timeout: int = 60):
    command = [adb] + (["-s", serial] if serial else []) + arguments
    return runner(command, capture_output=True, timeout=timeout)


def connected_devices(adb: str, runner=None) -> list[str]:
    runner = runner or subprocess.run
    result = runner([adb, "devices"], capture_output=True, timeout=30)
    states = [line.split() for line in result.stdout.decode("utf-8", "replace").splitlines()[1:] if line.strip()]
    return [fields[0] for fields in states if len(fields) >= 2 and fields[1] == "device"]


def collect(out_dir: Path, *, adb: str = "adb", serial: str | None = None, runner=None,
            timestamp: str = "") -> dict:
    runner = runner or subprocess.run
    assert_read_only()
    devices = connected_devices(adb, runner)
    if serial is None:
        if len(devices) != 1:
            raise CollectionError(f"expected exactly one authorized device, found {len(devices)}: {devices}")
        serial = devices[0]
    elif serial not in devices:
        raise CollectionError(f"device {serial} is not connected and authorized")
    out_dir.mkdir(parents=True, exist_ok=True)
    version = _run(adb, None, ["version"], runner).stdout.decode("utf-8", "replace").strip()
    manifest = {"collected_utc": timestamp, "adb_version": version, "device_serial_recorded": False, "commands": {}}
    for name, (arguments, suffix) in COMMANDS.items():
        result = _run(adb, serial, arguments, runner)
        data = result.stdout
        (out_dir / f"{name}{suffix}").write_bytes(data)
        manifest["commands"][name] = {
            "adb_arguments": arguments, "returncode": result.returncode, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "permission_denied": b"Permission denied" in data or b"Permission denied" in result.stderr}
    config = out_dir / "config_gz.gz"
    try:
        manifest["config_gz_verification"] = {"ok": True, **{k: v for k, v in verify_config_gz.analyze(config).items()
                                                              if k in ("sha256", "options_total", "console_options_enabled", "errors", "warnings")}}
    except verify_config_gz.ConfigGzError as error:
        manifest["config_gz_verification"] = {"ok": False, "error": str(error)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb", help="path to adb(.exe)")
    parser.add_argument("--serial", help="device serial when several are attached")
    parser.add_argument("--out", type=Path, help="default: devices/samsung-j2core/evidence/capture-<UTC date>")
    args = parser.parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)
    out = args.out or Path("devices/samsung-j2core/evidence") / f"capture-{now:%Y%m%d}"
    try:
        manifest = collect(out, adb=args.adb, serial=args.serial, timestamp=now.isoformat(timespec="seconds"))
    except (CollectionError, FileNotFoundError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    denied = [name for name, info in manifest["commands"].items() if info["permission_denied"]]
    print(f"saved {len(manifest['commands'])} captures to {out}")
    print("permission denied for:", ", ".join(denied) or "nothing")
    verification = manifest["config_gz_verification"]
    print("config.gz:", "OK" if verification["ok"] else "FAILED - " + verification["error"])
    return 0 if verification["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
