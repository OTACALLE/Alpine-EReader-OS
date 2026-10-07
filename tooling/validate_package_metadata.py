#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    if path is None:
        print("usage: validate_package_metadata.py PACKAGE.json", file=sys.stderr)
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "version", "license", "target", "architecture", "runtime_dependencies", "files", "build_status"}
    missing = required - data.keys()
    if missing or data["target"] != "alpine" or not data["files"]:
        print("invalid package metadata", file=sys.stderr)
        return 1
    print(f"valid package metadata: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
