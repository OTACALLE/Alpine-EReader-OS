#!/usr/bin/env python3
"""Produce a hash manifest for pre-flash review; it performs no device I/O."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> dict:
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("artifacts", type=Path, nargs="+")
    args = parser.parse_args()
    missing = [str(path) for path in args.artifacts if not path.is_file()]
    if missing:
        raise SystemExit("missing artifact(s): " + ", ".join(missing))
    payload = {"format": 1, "purpose": "pre-flash review only", "flashable_claim": False,
               "artifacts": [digest(path) for path in args.artifacts]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote review manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
