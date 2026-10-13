# Samsung Galaxy J2 Core (SM-J260M)

Status: **UNVALIDATED**. This is the pilot device under investigation, not
working support. Nothing has been boot-tested.

No kernel, device tree, firmware blob, boot image, or flashing command is
included because none has been verified against a physical device. Evidence is
in `evidence/` and `adb-evidence.md`; `partition-map.json` is checked against
the raw capture and enforced by `tooling/flash_guard.py`. Next steps: verify
the bootloader unlock and Download Mode on the unit; obtain lawful kernel-source
provenance and the stock `boot.img`; then reach a visible kernel-console boot
before any display work.
