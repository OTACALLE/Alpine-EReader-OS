#!/usr/bin/env python3
"""Mandatory write gate for any tool that flashes or dd's a device.

Every flashing tool in this repository MUST call ``require_allowed`` before it
touches a block device (``tests/test_flash_guard.py`` fails the build if a
tool that invokes a flasher does not reference this module).  Policy comes from
``devices/<device>/partition-map.json``; unknown targets are denied.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

NEVER = "never-modify"
VERIFIED = "blocked-until-verified"
EXPLICIT = "explicit-authorization"
DESTRUCTIVE = "explicit-destructive-authorization"


class FlashBlocked(Exception):
    """Raised when at least one requested write is refused."""


@dataclass(frozen=True)
class Decision:
    target: str
    name: str | None
    allowed: bool
    reason: str


def load_map(device_dir: Path) -> dict:
    return json.loads((Path(device_dir) / "partition-map.json").read_text(encoding="utf-8"))


def load_verified(device_dir: Path) -> set[str]:
    path = Path(device_dir) / "verified-partitions.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("verified", []))


def _entries(mapping: dict) -> dict[str, dict]:
    entries = {name: dict(entry, name=name) for name, entry in mapping.get("partitions", {}).items()}
    for name, entry in mapping.get("emmc_special", {}).items():
        entries[name] = dict(entry, name=name)
    return entries


def resolve(target: str, mapping: dict) -> dict | None:
    """Find a partition by name or device node (case-insensitive, any path form)."""
    leaf = re.split(r"[\\/]", target.strip())[-1]
    if not leaf:
        return None
    for name, entry in _entries(mapping).items():
        if leaf.lower() in (name.lower(), entry.get("device", "").lower()):
            return entry
    return None


def evaluate(device_dir: Path, targets: list[str], *, authorized: set[str] = frozenset(),
             destructive_authorized: set[str] = frozenset(), sizes: dict[str, int] | None = None,
             verified: set[str] | None = None) -> list[Decision]:
    mapping = load_map(device_dir)
    verified = load_verified(device_dir) if verified is None else verified
    authorized_l = {n.lower() for n in authorized}
    destructive_l = {n.lower() for n in destructive_authorized}
    decisions = []
    for target in targets:
        entry = resolve(target, mapping)
        if entry is None:
            decisions.append(Decision(target, None, False, "unknown target (default deny)"))
            continue
        name, policy = entry["name"], entry["write_policy"]
        key = name.lower()
        size = (sizes or {}).get(target, (sizes or {}).get(name))
        if policy == NEVER:
            decision = Decision(target, name, False, "never-modify partition")
        elif size is not None and size > entry["bytes"]:
            decision = Decision(target, name, False, f"image of {size} bytes exceeds the {entry['bytes']}-byte partition")
        elif policy == VERIFIED and name not in verified:
            decision = Decision(target, name, False, "not verified yet (verified-partitions.json)")
        elif policy == DESTRUCTIVE and key not in destructive_l:
            decision = Decision(target, name, False, "needs explicit destructive authorization")
        elif policy in (EXPLICIT, VERIFIED) and key not in authorized_l and key not in destructive_l:
            decision = Decision(target, name, False, "needs explicit authorization")
        else:
            decision = Decision(target, name, True, "authorized")
        decisions.append(decision)
    return decisions


def require_allowed(device_dir: Path, targets: list[str], **kwargs) -> list[Decision]:
    decisions = evaluate(device_dir, targets, **kwargs)
    refused = [d for d in decisions if not d.allowed]
    if refused:
        raise FlashBlocked("; ".join(f"{d.target}: {d.reason}" for d in refused))
    return decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether writes to partitions are permitted")
    parser.add_argument("--device", type=Path, required=True, help="e.g. devices/samsung-j2core")
    parser.add_argument("--authorize", action="append", default=[], metavar="NAME")
    parser.add_argument("--authorize-destructive", action="append", default=[], metavar="NAME")
    parser.add_argument("targets", nargs="+")
    args = parser.parse_intermixed_args(argv)
    decisions = evaluate(args.device, args.targets, authorized=set(args.authorize),
                         destructive_authorized=set(args.authorize_destructive))
    for decision in decisions:
        print(f"{'ALLOW' if decision.allowed else 'DENY '} {decision.target}: {decision.reason}")
    return 0 if all(d.allowed for d in decisions) else 1


if __name__ == "__main__":
    sys.exit(main())
