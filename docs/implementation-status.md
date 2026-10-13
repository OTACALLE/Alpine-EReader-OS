# Implementation status

Roadmap phase: **Phase 1 — Proof of Concept, not yet complete.** Success
criteria (ARCHITECTURE.md §44): kernel boots to a shell, KOReader runs, RAM
measured, a book renders on real hardware. None is met.

## Implemented and host-tested

- Power-policy state machine (ACTIVE/READING/IDLE/SUSPEND/RESUME/SHUTDOWN,
  forbidden transitions, LOW/CRITICAL battery modifiers, Wi-Fi request policy)
  with a development backend only. `powerd` runs that backend; no rfkill,
  sysfs, or suspend write exists.
- Durable configuration store (fsync, atomic replace, corrupt files preserved).
- Recursive, symlink-safe book discovery under `Books/` (ADR 0005). No covers,
  metadata, or inotify rescans.
- Thin Shell navigation model and a CLI that lists books. There is no display
  backend or UI; the shell service is installed but not enabled.
- KOReader process-launch boundary (never exercised against a real KOReader).
- Reproducible installed-layout development rootfs tarball (not an Alpine
  image: no apk, busybox, kernel, or KOReader).
- Executable-preserving initramfs builder (symlinks, `/dev/console`,
  `/dev/null`, a bring-up `/init`) and an Android boot-v0 creator/inspector with
  `--cmdline`. Neither has booted anything.
- `tooling/flash_guard.py`: default-deny partition write policy.
- J2 Core records verified against the raw ADB transcript (26 partitions plus
  eMMC boot/RPMB areas, kernel release, execution mode).

## Not implemented or proven

- Bootloader unlock (the OEM-unlock toggle is reported visible; unlock is
  unverified), kernel source/DTB/stock boot image, kernel command line,
  display, input, storage, Wi-Fi, suspend/resume, recovery, and flashing.
- A flashing tool, a bootable image, an Alpine package repository, a KOReader
  package, a DRM/KMS or Weston backend, MTP, update signing/staging/rollback,
  and a hardware power measurement.

The current artifacts must not be flashed onto a device. `dist/` test images use
synthetic kernel and DT inputs.
