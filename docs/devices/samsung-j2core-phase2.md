# SM-J260M / j2corelte: Phase 2 evidence and build boundary

## Kernel and device tree provenance

The physical SM-J260M has now confirmed `J260MUBSDAUI4` / Linux
`3.18.14-15008757-QB43519801` through read-only ADB `uname -a` and
`/proc/version` captures. No matching Samsung GPL source is present in this
repository. Consequently, no kernel, DTB, firmware, or flashable `boot.img` is
produced. The only pinned external configuration evidence is the
community `android_device_samsung_j2corelte` Android 8.1 tree at commit
`6d1d755ab5fcef815a3b7cd0a86e0201131ad2c6`. It identifies `universal7570_go`,
uses an ARM64 `Image` and a separately supplied DT image, and supplies the
candidate Android boot-v0 offsets captured in `boot-parameters.json`.

The prior public-kernel mismatch is resolved: the physical ADB capture is the
authoritative record for this device. The evidence still does not supply an
approved source tree, kernel binary, DTB, DTBO, or stock boot-image hash.

The physical kernel reports `armv8l`, which is an AArch32 execution mode. The
initial Alpine userspace architecture is therefore **armv7**. This is a narrow
compatibility decision based on the running kernel, not a claim that the SoC
lacks 64-bit hardware. A future aarch64 userspace requires a separately
validated 64-bit kernel and device port. The `/proc/config.gz` attempt was
corrupted by PowerShell text redirection, so no `CONFIG_COMPAT` claim is made.

## Verified live storage evidence

The device controller path is `/dev/block/platform/13540000.dwmmc0`; the exact
mapping is in `devices/samsung-j2core/partition-map.json`. In particular, BOOT
is `mmcblk0p10` (32 MiB), RECOVERY is `mmcblk0p11` (38 MiB), DTBO is
`mmcblk0p16` (2 MiB), SYSTEM is `mmcblk0p18`, VENDOR is `mmcblk0p19`, and
USERDATA is `mmcblk0p26`. This corrects community-map size mismatches.

`ro.oem_unlock_supported=1` but `sys.oem_unlock_allowed=0` was captured from
the running system. No unlock attempt has been made, and the image pipeline
must not treat an available menu capability as authorization or permission.

## What is implemented

`tooling/build_initramfs.py` produces deterministic gzip/newc initramfs
artifacts from a supplied Alpine rootfs staging tree. `tooling/android_bootimg.py`
implements and validates the Android legacy boot-v0 binary layout, including
the candidate offsets. It has no kernel compiler and deliberately has no
default kernel/DT input.

When approved, hash-locked kernel, DT, and rootfs inputs exist, build with:

```powershell
py -3 tooling/build_initramfs.py --staging <alpine-staging-root> --output dist/initramfs.cpio.gz
py -3 tooling/android_bootimg.py create --kernel <Image> --ramdisk dist/initramfs.cpio.gz --dt <dt.img> --output dist/boot.img --base 0x10000000 --kernel-offset 0x8000 --ramdisk-offset 0x1000000 --tags-offset 0x100 --page-size 2048 --board SRPRF18A001RU
py -3 tooling/android_bootimg.py inspect dist/boot.img
```

This is a structural build only until its input provenance and a physical boot
test are recorded. The script does not flash or interact with a device.
