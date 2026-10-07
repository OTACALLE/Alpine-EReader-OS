#!/usr/bin/env python3
"""Dependency-free validation for the project Device Profile contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "": {"schema_version", "identity", "support", "kernel", "boot", "hardware", "firmware", "known_limitations"},
    "identity": {"manufacturer", "model", "codename", "variants", "soc"},
    "support": {"tier", "boot_status", "kernel_status", "display_status", "touchscreen_status", "storage_status", "wifi_status", "recovery_status"},
    "kernel": {"strategy", "version", "source", "status"},
    "boot": {"unlock_status", "flash_method", "recovery_entry"},
    "hardware": {"ram_mb", "display", "battery_mah"},
    "firmware": {"wifi", "gpu"},
}


def validate(profile: dict) -> list[str]:
    errors: list[str] = []
    for path, keys in REQUIRED.items():
        value = profile if not path else profile.get(path, {})
        if not isinstance(value, dict):
            errors.append(f"{path or 'root'} must be an object")
            continue
        missing = keys - value.keys()
        if missing:
            errors.append(f"{path or 'root'} missing: {', '.join(sorted(missing))}")
    if profile.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if profile.get("support", {}).get("tier") not in {"green", "yellow", "red"}:
        errors.append("support.tier must be green, yellow, or red")
    if not isinstance(profile.get("known_limitations"), list):
        errors.append("known_limitations must be an array")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} DEVICE_PROFILE.json", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        errors = validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 2
    if errors:
        print("invalid device profile:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"valid device profile: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
