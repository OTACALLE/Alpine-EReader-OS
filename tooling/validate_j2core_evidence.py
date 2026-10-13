#!/usr/bin/env python3
"""Verify the J2 Core JSON records against the raw ADB capture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from tooling import j2core_capture
except ImportError:  # executed as a script
    import j2core_capture

ROOT = Path(__file__).resolve().parents[1]
DEVICE = ROOT / "devices" / "samsung-j2core"
POLICIES = {"never-modify", "blocked-until-verified", "explicit-authorization",
            "explicit-destructive-authorization"}
MUST_NEVER = {"EFS", "CPEFS", "RADIO", "CP_DEBUG", "MISC", "PARAM", "PERSISTENT", "STEADY",
              "BOTA0", "BOTA1", "m9kefs1", "m9kefs2", "m9kefs3", "NAD_REFER", "NAD_FW", "OMR", "RESERVED2"}


def check(capture: dict, profile: dict, mapping: dict, boot: dict) -> list[str]:
    failures: list[str] = []
    runtime = profile.get("runtime", {})
    if runtime.get("kernel_machine") != capture["uname"]["machine"]:
        failures.append("profile kernel_machine differs from the captured uname")
    if capture["uname"]["machine"] == "armv8l" and runtime.get("initial_userspace_architecture") != "armv7":
        failures.append("armv8l capture requires an armv7 initial userspace")
    if profile.get("kernel", {}).get("version") != capture["uname"]["release"]:
        failures.append("profile kernel version differs from the captured kernel release")
    parts, special = mapping.get("partitions", {}), mapping.get("emmc_special", {})
    if set(parts) != set(capture["by_name"]):
        failures.append(f"partition names differ from capture: {sorted(set(parts) ^ set(capture['by_name']))}")
    for name, entry in parts.items():
        device = capture["by_name"].get(name)
        if entry.get("device") != device:
            failures.append(f"{name}: device {entry.get('device')} != captured {device}")
        if entry.get("bytes") != capture["block_sizes"].get(device):
            failures.append(f"{name}: size differs from captured /proc/partitions")
    for name, entry in special.items():
        if entry.get("bytes") != capture["block_sizes"].get(name):
            failures.append(f"{name}: size differs from captured /proc/partitions")
    for name, entry in {**parts, **special}.items():
        if entry.get("write_policy") not in POLICIES:
            failures.append(f"{name}: unknown write_policy {entry.get('write_policy')!r}")
    for name in MUST_NEVER:
        if parts.get(name, {}).get("write_policy") != "never-modify":
            failures.append(f"{name} must stay never-modify")
    if mapping.get("default_for_unlisted_targets") != "deny":
        failures.append("unlisted targets must default to deny")
    if boot.get("boot_partition_max_bytes") != parts.get("BOOT", {}).get("bytes"):
        failures.append("boot_partition_max_bytes must equal the captured BOOT partition size")
    if capture["controller"] not in mapping.get("evidence", {}).get("controller", ""):
        failures.append("controller path differs from capture")
    return failures


def main() -> int:
    failures = check(j2core_capture.load(),
                     json.loads((DEVICE / "device-profile.json").read_text(encoding="utf-8")),
                     json.loads((DEVICE / "partition-map.json").read_text(encoding="utf-8")),
                     json.loads((DEVICE / "boot-parameters.json").read_text(encoding="utf-8")))
    if failures:
        print("invalid J2 Core evidence:\n- " + "\n- ".join(failures), file=sys.stderr)
        return 1
    print("J2 Core records match the raw capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
