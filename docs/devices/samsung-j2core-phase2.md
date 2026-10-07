# SM-J260M / j2corelte: Phase 2 evidence and build boundary

## Kernel and device tree provenance

No exact Samsung source for `J260MUBSDAUI4` / `3.18.14-15008757-QB43519801`
is present in this repository. Consequently, no kernel, DTB, firmware, or
flashable `boot.img` is produced. The only pinned external evidence is the
community `android_device_samsung_j2corelte` Android 8.1 tree at commit
`6d1d755ab5fcef815a3b7cd0a86e0201131ad2c6`. It identifies `universal7570_go`,
uses an ARM64 `Image` and a separately supplied DT image, and supplies the
candidate Android boot-v0 offsets captured in `boot-parameters.json`.

There is a provenance conflict to resolve before source selection: a public
report for the same Android build identifies kernel `3.18.14-15009140-QB24355959`,
not the maintainer-reported `3.18.14-15008757-QB43519801`. Capture
`/proc/version`, `uname -a`, and the boot image hash from the actual SM-J260M
using a read-only shell before accepting either value.

Its recovery userspace declares 32-bit ARM while its kernel is ARM64. That does
not establish `CONFIG_COMPAT` in the exact SM-J260M kernel. Alpine userspace
architecture is therefore **unresolved**: inspect the exact kernel `.config`
for `CONFIG_COMPAT`, then select `armv7` only if it is enabled and the relevant
drivers work; otherwise build `aarch64`. Do not choose based on CPU marketing.

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
