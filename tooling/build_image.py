#!/usr/bin/env python3
"""Compose a deterministic development rootfs tarball without host Linux.

The archive has an installed layout (not a copy of the source tree):

    usr/lib/ereader/{core,shell,reader_integration}/...   Python packages
    usr/libexec/ereader/powerd                             service wrapper (0755)
    etc/init.d/{powerd,ereader-shell}                      OpenRC scripts (0755)
    etc/runlevels/default/powerd -> /etc/init.d/powerd     enabled service
    etc/ereader/{manifest.json,device-profile.json}

File order, modes, ownership and timestamps do not depend on the host, so the
same sources give the same SHA-256 on Windows and Linux (see CI job
``reproducible``).  This is still not an Alpine image: no apk, busybox, kernel
or KOReader is included.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

try:
    from tooling.fsmodes import file_mode
except ImportError:  # executed as a script
    from fsmodes import file_mode

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_TREES = (
    ("core/ereader_core", "usr/lib/ereader/core/ereader_core"),
    ("shell/ereader_shell", "usr/lib/ereader/shell/ereader_shell"),
    ("reader_integration", "usr/lib/ereader/reader_integration"),
)
SINGLE_FILES = (
    ("core/libexec/powerd", "usr/libexec/ereader/powerd"),
    ("core/openrc/powerd.initd", "etc/init.d/powerd"),
    ("core/openrc/ereader-shell.initd", "etc/init.d/ereader-shell"),
)
# The shell exits immediately until a display backend exists, so it is installed
# but not enabled.
ENABLED_SERVICES = ("powerd",)


def _add_file(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = file_mode(name, data)
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def _add_symlink(archive: tarfile.TarFile, name: str, target: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    info.mode = 0o777
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = 0
    archive.addfile(info)


def collect(root: Path, manifest: dict, profile: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for source, target in PACKAGE_TREES:
        for path in (root / source).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix == ".py":
                files[f"{target}/{path.relative_to(root / source).as_posix()}"] = path.read_bytes()
    for source, target in SINGLE_FILES:
        files[target] = (root / source).read_bytes()
    files["etc/ereader/device-profile.json"] = profile.read_bytes()
    files["etc/ereader/manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return files


def build_tarball(root: Path, device_manifest: Path) -> bytes:
    manifest = json.loads(device_manifest.read_text(encoding="utf-8"))
    profile = root / manifest["device_profile"]
    if not profile.exists():
        raise SystemExit(f"device profile missing: {profile}")
    files = collect(root, manifest, profile)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(files):
            _add_file(archive, name, files[name])
        for service in ENABLED_SERVICES:
            _add_symlink(archive, f"etc/runlevels/default/{service}", f"/etc/init.d/{service}")
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="path to an image manifest relative to repository root")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_tarball(ROOT, ROOT / args.device)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest + "  " + args.output.name + "\n", encoding="ascii", newline="\n")
    print(f"created development rootfs: {args.output}\nsha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
