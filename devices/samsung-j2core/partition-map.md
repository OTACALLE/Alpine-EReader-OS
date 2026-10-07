# Partition-map evidence

This is an evidence record from community TWRP configuration at commit
`6d1d755ab5fcef815a3b7cd0a86e0201131ad2c6`, not a read from the physical
SM-J260M. Never use it as an authorization to erase or flash.

| Logical role | Community by-name target | Status |
|---|---|---|
| Boot | `BOOT` | Unverified on SM-J260M |
| Recovery | `RECOVERY` | Unverified on SM-J260M |
| System | `SYSTEM` | Unverified on SM-J260M |
| User data | `USERDATA` | Unverified on SM-J260M |
| Vendor | `VENDOR` | Unverified on SM-J260M |
| EFS / radio identity | `EFS`, `CPEFS`, `RADIO`, `CP_DEBUG` | **Never touch** |

Reported candidate sizes are 32 MiB boot, 38 MiB recovery, 1216 MiB system,
and 176 MiB vendor. Confirm all names and sizes from the device in a
non-destructive recovery/ADB session before using them.
