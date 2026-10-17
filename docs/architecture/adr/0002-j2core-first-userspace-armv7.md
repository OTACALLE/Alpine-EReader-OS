# ADR 0002: J2 Core first userspace is armv7 on an arm64 kernel

Status: accepted for the first physical-device build. **Revised 2026-10-17**: the
first version of this ADR wrongly inferred an AArch32 kernel from `uname -m`.

`uname` reported `armv8l`, but that is what a **32-bit process** sees on an arm64
kernel. The binary-safe `config.gz` (`evidence/j2core-config.gz`) shows header
`Linux/arm64 3.18.14`, `CONFIG_ARM64=y` and `CONFIG_COMPAT=y`: the kernel is 64-bit
and runs the stock 32-bit Android userspace through the compat layer.

Decision: the initial Alpine userspace stays **armv7 (32-bit, EABI5 hard-float)**.
It runs on this kernel because `CONFIG_COMPAT=y`; it halves pointer size, which
matters with about 1 GB of RAM; and it matches the stock userspace the device ships
with. The kernel image is expected to be an arm64 `Image`. An aarch64 userspace is
possible on the same kernel and may be revisited with measured RAM numbers; it is
not selected now. `tooling/verify_config_gz.py` fails if the profile's userspace
needs `COMPAT` and the kernel config lacks it.
