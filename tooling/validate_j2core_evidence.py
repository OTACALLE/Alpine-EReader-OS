#!/usr/bin/env python3
"""Validate safety-critical facts captured from the physical J2 Core."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "devices/samsung-j2core/device-profile.json").read_text())
    mapping = json.loads((root / "devices/samsung-j2core/partition-map.json").read_text())
    failures: list[str] = []
    if profile.get("runtime", {}).get("initial_userspace_architecture") != "armv7":
        failures.append("initial userspace must match captured armv8l AArch32 execution mode")
    boot = mapping.get("partitions", {}).get("BOOT", {})
    if boot.get("device") != "mmcblk0p10" or boot.get("bytes") != 33554432:
        failures.append("BOOT mapping must match physical capture")
    for sensitive in ("EFS", "CPEFS", "RADIO", "CP_DEBUG"):
        if mapping.get("partitions", {}).get(sensitive, {}).get("write_policy") != "never modify":
            failures.append(f"{sensitive} must retain never-modify policy")
    if failures:
        print("invalid J2 Core evidence:\n- " + "\n- ".join(failures), file=sys.stderr)
        return 1
    print("valid physical J2 Core evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
