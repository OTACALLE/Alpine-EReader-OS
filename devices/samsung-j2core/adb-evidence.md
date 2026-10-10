# Physical ADB evidence

Collected through authorized, read-only USB debugging on 2026-10-08. No device
state was changed.

- Kernel: `3.18.14-15008757-QB43519801`, built 2021-09-16 with GCC 4.9.x.
- Kernel machine: `armv8l`.
- Bootloader property: `J260MUBSDAUI4`.
- OEM unlocking capability property: supported; current allow property: false.
- Block controller: `/dev/block/platform/13540000.dwmmc0`.
- Full safety-relevant partition mapping: `partition-map.json`.

The raw `/proc/config.gz` capture is not evidence because PowerShell text
redirection inserted/translated bytes. Reacquire it only with a binary-safe
command such as `adb exec-out cat /proc/config.gz > config.gz` from `cmd.exe`,
then validate it with a gzip reader before using its contents.
