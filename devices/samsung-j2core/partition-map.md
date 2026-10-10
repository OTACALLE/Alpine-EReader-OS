# Partition-map evidence

The JSON map beside this file is derived from a read-only ADB capture of the
physical SM-J260M on 2026-10-08. It supersedes the conflicting sizes in the
community TWRP configuration. Never use it as an authorization to erase or
flash.

| Logical role | Community by-name target | Status |
|---|---|---|
| Boot | `mmcblk0p10` / `BOOT`, 32 MiB | Requires explicit authorization |
| Recovery | `mmcblk0p11` / `RECOVERY`, 38 MiB | Requires explicit authorization |
| System | `mmcblk0p18` / `SYSTEM`, 1200 MiB | Requires explicit destructive authorization |
| User data | `mmcblk0p26` / `USERDATA`, 13204 MiB | Requires explicit destructive provisioning |
| Vendor | `mmcblk0p19` / `VENDOR`, 200 MiB | Do not modify until verified |
| EFS / radio identity | `EFS`, `CPEFS`, `RADIO`, `CP_DEBUG` | **Never touch** |

The exact DTBO partition is `mmcblk0p16` and is 2 MiB. It must not be assumed
safe to replace merely because it is visible from Android.
