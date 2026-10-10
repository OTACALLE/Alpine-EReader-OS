# ADR 0002 J2 Core first userspace armv7

Status: accepted for the first physical-device build.

Read-only ADB evidence from the physical SM-J260M reports Linux
`3.18.14-15008757-QB43519801` and machine `armv8l`. The initial Alpine
userspace must therefore be armv7, which matches the kernel's demonstrated
AArch32 execution mode. This does not prevent a future aarch64 port, but that
port requires a separately validated 64-bit kernel, DT, and boot path.

The decision does not assert `CONFIG_COMPAT`: the attempted config capture was
corrupted by Windows PowerShell text redirection and must be repeated using a
binary-safe transfer before relying on configuration details.
