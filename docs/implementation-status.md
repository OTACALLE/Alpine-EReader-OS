# Implementation status

## Implemented and host-tested

- Device-independent power-policy state machine with a development backend.
- Persistent `/var/lib/ereader` directory model and book discovery for EPUB,
  PDF, and TXT files.
- Strict, atomic user configuration store.
- Thin stack-based Shell navigation model with all MVP entry points represented:
  Library, Reader, Catalogs, Search, Settings, Network, Device Info, Update,
  and Recovery.
- KOReader process-launch integration boundary; it neither bundles nor fakes a
  reader engine.
- J2 Core structured Device Profile plus a dependency-free validator.
- Deterministic development-rootfs tar assembly and checksum output.
- OpenRC service-definition scaffolding.

## Not implemented or proven

- Bootloader unlock, kernel boot, DTB, display, input, storage, Wi-Fi,
  suspend/resume, recovery, and flashing on the SM-J260M.
- A bootable image, Alpine package repository, KOReader package build, real
  DRM/KMS or Weston backend, MTP, update signing/staging/rollback, and a
  hardware power measurement.

These omissions are intentional evidence boundaries. The current artifact must
not be flashed onto a device.
