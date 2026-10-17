# Raw evidence

`PS_C.docx` is the unedited PowerShell transcript of the read-only ADB session
on the physical SM-J260M (2026-10-08). It is the ground truth that
`partition-map.json` and `device-profile.json` are verified against
(`tooling/j2core_capture.py`, `tests/test_j2core_raw_capture.py`).

`j2core-config.gz` is the stock kernel configuration, collected binary-safe on 2026-10-17
and validated by `tooling/verify_config_gz.py` (summary: `../kernel-config-report.json`).
It shows an arm64 kernel with `CONFIG_COMPAT=y`; ADR 0002 and ADR 0008 build on it.

Known gaps:

- `PS_C.docx` predates the valid `config.gz`; its own `config.gz` attempt was corrupt
  (PowerShell text redirection) and was never stored.
- `/proc/cmdline` returned "Permission denied": the stock kernel command line is unknown
  until a stock `boot.img` is read.
- Use `tooling/collect_device_evidence.py` for any further capture (binary-safe, read-only).
