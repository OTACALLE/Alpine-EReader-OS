# Raw evidence

`PS_C.docx` is the unedited PowerShell transcript of the read-only ADB session
on the physical SM-J260M (2026-10-08). It is the ground truth that
`partition-map.json` and `device-profile.json` are verified against
(`tooling/j2core_capture.py`, `tests/test_j2core_raw_capture.py`).

Known gaps in this capture:

- `/proc/config.gz` was captured through PowerShell text redirection and is
  corrupt, so **no `.gz` capture is stored here**. Recollect it with
  `cmd /c "adb exec-out cat /proc/config.gz > j2core-config.gz"`, verify it with
  a gzip reader, then add it to this folder (`*.gz` is marked binary in
  `.gitattributes`).
- `/proc/cmdline` returned "Permission denied": the stock kernel command line
  is unknown until a stock `boot.img` is obtained.
