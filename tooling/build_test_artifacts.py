#!/usr/bin/env python3
"""Regenerate the reproducible artifacts in dist/ from the current sources.

Everything produced here is for review and tests.  The boot image uses
SYNTHETIC kernel/DT payloads and carries "NOT-FLASHABLE" in its name; a manifest
with ``flashable_claim: false`` accompanies it.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

try:
    from tooling import android_bootimg, build_image, build_initramfs, release_manifest
except ImportError:  # executed as a script
    import android_bootimg
    import build_image
    import build_initramfs
    import release_manifest

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_KERNEL = b"SYNTHETIC-KERNEL-NOT-BOOTABLE\n"
SYNTHETIC_DT = b"SYNTHETIC-DT-NOT-VALID\n"


def build(output: Path, root: Path = ROOT) -> list[Path]:
    output = Path(output)
    synthetic = output / "synthetic"
    synthetic.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []
    manifest_path = root / "images" / "samsung-j2core.json"
    rootfs = output / "samsung-j2core-development-rootfs.tar"
    rootfs.write_bytes(build_image.build_tarball(root, manifest_path))
    produced.append(rootfs)
    with tempfile.TemporaryDirectory() as staging:
        (Path(staging) / "etc").mkdir()
        (Path(staging) / "etc" / "issue").write_text("synthetic test initramfs\n", encoding="utf-8", newline="\n")
        raw = build_initramfs.build(Path(staging), init=(root / "core" / "initramfs" / "init").read_bytes())
    initramfs = synthetic / "initramfs-synthetic.cpio.gz"
    with initramfs.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    produced.append(initramfs)
    params = json.loads((root / "devices" / "samsung-j2core" / "boot-parameters.json").read_text(encoding="utf-8"))
    image = android_bootimg.pack(
        SYNTHETIC_KERNEL, initramfs.read_bytes(), SYNTHETIC_DT, base=int(params["base"], 0),
        kernel_offset=int(params["kernel_offset"], 0), ramdisk_offset=int(params["ramdisk_offset"], 0),
        tags_offset=int(params["tags_offset"], 0), page_size=params["page_size"], board=params["board"],
        cmdline="SYNTHETIC-TEST-IMAGE", max_bytes=params["boot_partition_max_bytes"])
    boot = synthetic / "boot-synthetic-NOT-FLASHABLE.img"
    boot.write_bytes(image)
    produced.append(boot)
    manifest = synthetic / "manifest.json"
    payload = {"format": 1, "purpose": "pre-flash review only", "flashable_claim": False,
               "artifacts": [release_manifest.digest(path) for path in produced]}
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    produced.append(manifest)
    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)
    for path in build(args.output):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
