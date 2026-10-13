#!/usr/bin/env python3
"""Validate package metadata, including that every listed file exists."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {"name", "version", "license", "target", "architecture", "runtime_dependencies", "files", "build_status"}
ROOT = Path(__file__).resolve().parents[1]


def validate(data: dict, root: Path = ROOT) -> list[str]:
    errors = []
    missing = REQUIRED - data.keys()
    if missing:
        errors.append("missing keys: " + ", ".join(sorted(missing)))
    if data.get("target") != "alpine":
        errors.append("target must be alpine")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
    else:
        errors.extend(f"listed file does not exist: {name}" for name in files if not (root / name).exists())
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: validate_package_metadata.py PACKAGE.json", file=sys.stderr)
        return 2
    path = Path(argv[0])
    errors = validate(json.loads(path.read_text(encoding="utf-8")))
    if errors:
        print("invalid package metadata:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"valid package metadata: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
