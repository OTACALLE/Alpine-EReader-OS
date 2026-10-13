# SM-J260M / j2corelte: boot evidence and build boundary

This is part of roadmap **Phase 1** preparation. It does not describe a working
port.

## Evidence

- Read-only ADB capture, 2026-10-08: `devices/samsung-j2core/evidence/PS_C.docx`
  (parsed by `tooling/j2core_capture.py`).
- Kernel `3.18.14-15008757-QB43519801`, machine `armv8l`: a 64-bit-capable
  SoC running in AArch32 mode, hence the armv7 first userspace (ADR 0002).
- Bootloader `J260MUBSDAUI4`; `ro.oem_unlock_supported=1`. The capture shows
  `sys.oem_unlock_allowed=0`; the maintainer later reported the OEM-unlock
  toggle is visible in Developer options. Unlock is unperformed and unverified.
- Storage controller `13540000.dwmmc0`; BOOT is `mmcblk0p10`, 32 MiB.

## Community boot-header candidate (not tested)

Base `0x10000000`, page size 2048, kernel offset `0x8000`, ramdisk offset
`0x1000000`, tags offset `0x100`, separate DT image, from the cited community
recovery tree (`sources.lock.json`). The tree also lists an ARM64 `Image`; that
**conflicts** with the AArch32 kernel the device reports and is not adopted. The
kernel image format is unknown until the stock `boot.img` and kernel config are
inspected. The stock command line is unknown (`/proc/cmdline` was denied).

## Building a structural test image

```
python tooling/build_initramfs.py --staging STAGING --output dist/initramfs.cpio.gz
python tooling/android_bootimg.py create --kernel K --ramdisk R --dt D \
  --output dist/boot.img --base 0x10000000 --kernel-offset 0x8000 \
  --ramdisk-offset 0x1000000 --tags-offset 0x100 --page-size 2048 \
  --cmdline "<from stock boot.img>" --max-bytes 33554432
```

`--samsung-trailer` appends `SEANDROIDENFORCE`; whether this device requires it
is unverified. The project-defined `ereader.root=<device>` parameter makes the
bring-up `/init` mount and switch into a root filesystem.

## Blockers

No exact, provenance-verified Samsung GPL kernel source, matching DTB, stock
boot image, or firmware archive has been acquired. Without them no flashable
image can be produced.
