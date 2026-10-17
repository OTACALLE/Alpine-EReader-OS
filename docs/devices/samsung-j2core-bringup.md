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
2. **Stock firmware `J260MUBSDAUI4`** (the AP file). Samsung publishes no download portal: use a
   tool that reads Samsung's update servers (Frija, samloader) or a firmware-archive site. Only the
   **AP file** matters, and it depends on the PDA build (`J260MUBSDAUI4`), not on the CSC, so the same
   AP appears in packages for different regions (this device is CSC `ZTO`). The servers only offer the
   latest build; archive sites keep older ones. Never flash firmware with an older bootloader than the
   phone's (anti-rollback). Run `tooling/extract_stock_boot.py --ap <AP file>`: it checks the file's
   MD5 trailer and compares the kernel's embedded `Linux version` banner with the phone's
   `/proc/version`. If they differ it reports `matches_device: false`, exits with code 3 and refuses
   `--apply`: the file is not the build on the phone, wherever it came from. Commit only the JSON
   report, never the firmware or the extracted images. Do not run executables bundled in a download.
3. **GPL kernel source** from Samsung's Open Source Release Center (search SM-J260M and
   pick the package for Android 8.1 / this build). Run
   `tooling/verify_kernel_source.py <zip> --write-lock`; approving it as an input stays a
   manual, reviewed edit of `sources.lock.json`.
4. **`config.gz`: done** (2026-10-17, arm64). Still worth running
   `py -3 tooling/collect_device_evidence.py --adb <path to adb.exe>` once: it now also reads the
   framebuffer geometry, the `android_usb` interface, `last_kmsg` and the vendor firmware list.
5. **Kernel with a console.** Needs a Linux build host (CI or a VM; the Windows host
   stays untouched, see `building-on-windows.md`). The build recipe cannot be written
   before the source is in hand: a 3.18 kernel usually needs a period toolchain or
   patches. The stock config has **no on-screen console** (`VT=n`). Options, least effort
   first: `last_kmsg` (enabled) read after a reboot; a USB ACM serial port started from
   `/init` (the ACM function is enabled; the `android_usb` interface is unverified);
   rebuild with `VT`/`FRAMEBUFFER_CONSOLE`; a UART (opens the phone, `SERIAL_SAMSUNG_CONSOLE`
   is enabled). See ADR 0008 for the display, rfkill and squashfs consequences.
6. **Alpine stage 2** (`python3`, `openrc`, ...) runs in CI against the Alpine mirrors;
   KOReader packaging is an open decision (ADR 0007).

The first write to the device must be BOOT only, with the stock BOOT image saved first,
through `tooling/flash_guard.py` (see `docs/recovery/samsung-j2core-flash-gate.md`).
