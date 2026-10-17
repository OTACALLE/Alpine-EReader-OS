# Physical ADB evidence

Collected through authorized, read-only USB debugging on 2026-10-08. No device
state was changed.

- Kernel: `3.18.14-15008757-QB43519801`, built 2021-09-16 with GCC 4.9.x.
- `uname -m` as seen by the 32-bit ADB shell: `armv8l` (the kernel is arm64, see `evidence/j2core-config.gz`).
- Bootloader property: `J260MUBSDAUI4`.
- OEM unlocking capability property: supported; current allow property: false.
- Block controller: `/dev/block/platform/13540000.dwmmc0`.
- Raw transcript: `evidence/PS_C.docx`. Full partition mapping: `partition-map.json`.

The first `/proc/config.gz` capture was corrupted by PowerShell text redirection and was
replaced on 2026-10-17 by a binary-safe copy (`evidence/j2core-config.gz`, validated by
`tooling/verify_config_gz.py`).

Observation (inference, not proven): the capture lists `dm-0` with 13520880
blocks, exactly 16 KiB smaller than `USERDATA` (`mmcblk0p26`, 13520896 blocks),
which is consistent with a device-mapper crypto layer over USERDATA. Treat
USERDATA as potentially encrypted until `/proc/mounts` or `vdc` output proves
otherwise.
