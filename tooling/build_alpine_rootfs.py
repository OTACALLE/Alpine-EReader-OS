#!/usr/bin/env python3
"""Stage 1 of the real Alpine rootfs: verified Alpine minirootfs + EReader overlay.

The pinned Alpine armv7 minirootfs (images/alpine-rootfs.lock.json) is verified by
SHA-256 and by inspecting its ELF userspace, then the installed layout produced
by tooling/build_image.py is added.  Output is deterministic (sorted names, zero
mtimes).  Stage 2 (apk add python3 openrc ...) needs the Alpine mirrors and runs
in CI (images/Dockerfile.provision); it is not performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import sys
import tarfile
import urllib.request
from pathlib import Path

try:
    from tooling import build_image
    from tooling.fsmodes import file_mode
except ImportError:  # executed as a script
    import build_image
    from fsmodes import file_mode

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "images" / "alpine-rootfs.lock.json"
EM_ARM, EF_ARM_EABI_VER5, EF_ARM_ABI_FLOAT_HARD = 40, 0x05000000, 0x400
EXPECTED_ELF = {"armv7": {"class": 1, "machine": EM_ARM, "abi": "eabi5-hard-float"}}


class AlpineRootfsError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def verify_tarball(path: Path, lock: dict) -> None:
    actual = sha256_file(path)
    if actual != lock["sha256"]:
        raise AlpineRootfsError(f"sha256 mismatch for {Path(path).name}: expected {lock['sha256']}, got {actual}")


def fetch(lock: dict, destination: Path) -> Path:
    source = lock["source"]
    url = f"https://raw.githubusercontent.com/alpinelinux/docker-alpine/{source['commit']}/{source['path']}"
    target = Path(destination) / Path(source["path"]).name
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - fixed https URL pinned by commit
        target.write_bytes(response.read())
    verify_tarball(target, lock)
    return target


def elf_report(header: bytes) -> dict:
    if header[:4] != b"\x7fELF":
        raise AlpineRootfsError("bin/busybox is not an ELF file")
    machine = struct.unpack("<H", header[18:20])[0]
    flags = struct.unpack("<I", header[36:40])[0]
    abi = "eabi%d-%s" % (flags >> 24, "hard-float" if flags & EF_ARM_ABI_FLOAT_HARD else "soft-float") if machine == EM_ARM else "n/a"
    return {"class": header[4], "little_endian": header[5] == 1, "machine": machine, "abi": abi}


def check_userspace(archive: tarfile.TarFile, architecture: str) -> dict:
    expected = EXPECTED_ELF.get(architecture)
    if expected is None:
        raise AlpineRootfsError(f"unsupported architecture {architecture!r}")
    try:
        header = archive.extractfile(_member(archive, "bin/busybox")).read(64)
    except KeyError as error:
        raise AlpineRootfsError("bin/busybox missing from the minirootfs") from error
    report = elf_report(header)
    if (report["class"], report["machine"], report["abi"]) != (expected["class"], expected["machine"], expected["abi"]):
        raise AlpineRootfsError(f"busybox is {report}, expected {expected}")
    return report


def _member(archive: tarfile.TarFile, name: str) -> tarfile.TarInfo:
    for candidate in (name, "./" + name):
        try:
            member = archive.getmember(candidate)
        except KeyError:
            continue
        while member.issym() and not member.linkname.startswith("/"):
            member = archive.getmember(str(Path(member.name).parent / member.linkname).replace("\\", "/"))
        return member
    raise KeyError(name)


def _clean(name: str) -> str:
    name = name.strip()
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def build_rootfs(minirootfs: Path, lock: dict, root: Path, device_manifest: Path) -> bytes:
    verify_tarball(minirootfs, lock)
    manifest = json.loads(Path(device_manifest).read_text(encoding="utf-8"))
    profile_path = Path(root) / manifest["device_profile"]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    wanted = profile["runtime"]["initial_userspace_architecture"]
    if lock["architecture"] != wanted:
        raise AlpineRootfsError(f"lock is {lock['architecture']} but the device profile requires {wanted}")
    entries: dict[str, tuple[tarfile.TarInfo, bytes]] = {}
    with tarfile.open(minirootfs, mode="r:gz") as archive:
        elf = check_userspace(archive, lock["architecture"])
        release = archive.extractfile(_member(archive, "etc/alpine-release")).read().decode().strip()
        if release != lock["alpine_version"]:
            raise AlpineRootfsError(f"minirootfs is Alpine {release}, lock pins {lock['alpine_version']}")
        for member in archive:
            name = _clean(member.name)
            if not name:
                continue
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.uid, info.gid = member.type, member.mode, member.uid, member.gid
            info.uname, info.gname, info.linkname, info.mtime = member.uname, member.gname, member.linkname, 0
            if member.islnk():
                info.linkname = _clean(member.linkname)
            data = archive.extractfile(member).read() if member.isreg() else b""
            info.size = len(data)
            entries[name] = (info, data)
    provenance = {"stage": 1, "alpine_version": lock["alpine_version"], "architecture": lock["architecture"],
                  "minirootfs_sha256": lock["sha256"], "source_commit": lock["source"]["commit"],
                  "userspace_elf": elf, "packages_installed": "none (stage 2 pending)"}
    overlay = build_image.collect(Path(root), manifest, profile_path)
    overlay["etc/ereader/rootfs-provenance.json"] = json.dumps(provenance, sort_keys=True, indent=2).encode() + b"\n"
    for name, data in overlay.items():
        if name in entries:
            raise AlpineRootfsError(f"overlay path collides with the Alpine rootfs: {name}")
        info = tarfile.TarInfo(name)
        info.mode, info.uid, info.gid, info.uname, info.gname, info.mtime = file_mode(name, data), 0, 0, "root", "root", 0
        info.size = len(data)
        entries[name] = (info, data)
    for service in build_image.ENABLED_SERVICES:
        link = tarfile.TarInfo(f"etc/runlevels/default/{service}")
        link.type, link.linkname, link.mode, link.uid, link.gid = tarfile.SYMTYPE, f"/etc/init.d/{service}", 0o777, 0, 0
        link.uname = link.gname = "root"
        link.mtime = 0
        entries[link.name] = (link, b"")
    for name in list(entries):
        parts = name.split("/")
        for depth in range(1, len(parts)):
            parent = "/".join(parts[:depth])
            if parent not in entries:
                directory = tarfile.TarInfo(parent)
                directory.type, directory.mode, directory.uid, directory.gid = tarfile.DIRTYPE, 0o755, 0, 0
                directory.uname = directory.gname = "root"
                directory.mtime = 0
                entries[parent] = (directory, b"")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as out:
        for name in sorted(entries):
            info, data = entries[name]
            out.addfile(info, io.BytesIO(data) if info.isreg() else None)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--minirootfs", type=Path, help="local alpine-minirootfs tarball")
    source.add_argument("--fetch", action="store_true", help="download the pinned tarball from GitHub")
    parser.add_argument("--cache", type=Path, default=Path("dist/cache"))
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--device", type=Path, default=ROOT / "images" / "samsung-j2core.json")
    parser.add_argument("--output", type=Path, default=Path("dist/alpine-ereader-rootfs-armv7-stage1.tar"))
    args = parser.parse_args(argv)
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    try:
        tarball = fetch(lock, args.cache) if args.fetch else args.minirootfs
        payload = build_rootfs(tarball, lock, ROOT, args.device)
    except (AlpineRootfsError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        f"{digest}  {args.output.name}\n", encoding="ascii", newline="\n")
    print(f"created stage-1 rootfs: {args.output}\nsha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
