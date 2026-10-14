# SM-J260M bring-up: what is done and what needs the device

Roadmap phase: **Phase 1**. Everything below the line "Needs the device or Samsung
servers" has **not** been done.

## Done (host-side, tested)

| Need | Tool |
|---|---|
| Collect read-only evidence, binary-safe `config.gz` | `tooling/collect_device_evidence.py` |
| Validate a `config.gz` and read what it implies (32-bit vs 64-bit, console options) | `tooling/verify_config_gz.py` |
| Extract and describe the stock `boot.img` (checks the `.tar.md5`), diff against our boot parameters | `tooling/extract_stock_boot.py` |
| Check a Samsung GPL kernel archive (version, defconfig, device tree) and record provenance; never auto-approves | `tooling/verify_kernel_source.py` |
| Verified Alpine armv7 userspace base, stage 1 | `tooling/build_alpine_rootfs.py` |
| Build/inspect/unpack Android boot images; mandatory write gate | `tooling/android_bootimg.py`, `tooling/flash_guard.py` |

## Needs the device or Samsung servers

1. **Back up, then unlock.** Unlocking erases user data and trips Knox. On most
   Samsung models: power off, hold Volume Up + Volume Down while connecting USB to
   reach Download mode, then long-press Volume Up at the warning screen (confirm the
   on-screen text). Afterwards record the state in `device-profile.json`.
2. **Stock firmware `J260MUBSDAUI4`** (the AP file, for your CSC): download it from a
   Samsung firmware source. Do not flash firmware older than the phone's bootloader
   (anti-rollback). Run `tooling/extract_stock_boot.py --ap <AP file>`; commit only the
   JSON report, never the firmware or the extracted images.
3. **GPL kernel source** from Samsung's Open Source Release Center (search SM-J260M and
   pick the package for Android 8.1 / this build). Run
   `tooling/verify_kernel_source.py <zip> --write-lock`; approving it as an input stays a
   manual, reviewed edit of `sources.lock.json`.
4. **Recollect `config.gz`** with the phone booted into Android and USB debugging on:
   `py -3 tooling/collect_device_evidence.py --adb <path to adb.exe>`.
5. **Kernel with a console.** Needs a Linux build host (CI or a VM; the Windows host
   stays untouched, see `building-on-windows.md`). The build recipe cannot be written
   before the source is in hand: a 3.18 kernel usually needs a period toolchain or
   patches. Console options, in order of effort: on-screen `console=tty0` (needs
   `CONFIG_VT_CONSOLE`/`FRAMEBUFFER_CONSOLE`), `last_kmsg`/pstore read after a reboot,
   USB-gadget serial, and finally a UART (opens the phone). `verify_config_gz.py` lists
   which of these the stock kernel already enables.
6. **Alpine stage 2** (`python3`, `openrc`, ...) runs in CI against the Alpine mirrors;
   KOReader packaging is an open decision (ADR 0007).

The first write to the device must be BOOT only, with the stock BOOT image saved first,
through `tooling/flash_guard.py` (see `docs/recovery/samsung-j2core-flash-gate.md`).
