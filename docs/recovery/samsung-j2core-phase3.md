# SM-J260M Phase 3 readiness and recovery gate

No physical action is authorized by this document. It is a checklist for the
maintainer to review before issuing a separate, explicit authorization.

## Required evidence before any flash

1. Photograph and record the exact model label, serial/IMEI **privately**,
   bootloader/OEM-unlock state, Android build, and region/CSC.
2. Obtain a stock firmware package matching that exact model/region/build (or a
   newer Samsung-approved package) from a reputable archive; record every
   archive hash before proceeding.
3. Confirm the package includes the partitions needed to return to stock and
   that a Windows-compatible restore tool recognizes it *without writing*.
4. Use only read-only Android/Download-Mode queries to confirm the partition
   names and boot/recovery sizes; compare them with `partition-map.md`.
5. Obtain the exact Samsung GPL source archive, its checksum/source URL, and
   derive the exact kernel config and DTB from that source.
6. Create the signed/reviewed boot artifact and a `release_manifest.py` hash
   manifest. Inspect the Android header and enforce the 32 MiB candidate limit.

## Smallest reversible physical test

After explicit authorization only, use the device’s recovery-boot path to test
an image that does not overwrite `SYSTEM`, `USERDATA`, `EFS`, modem/radio, or
bootloader partitions. Stop immediately if Download Mode does not recognize the
expected recovery state. Never alter `EFS`, `CPEFS`, `RADIO`, `CP_DEBUG`, or
`MISC`.

## Expected evidence and diagnosis

Capture a timestamped serial/UART or on-screen kernel log, image SHA-256,
boot-mode screen, and recovery result. A black screen alone is inconclusive:
distinguish boot-loader rejection, kernel panic, display initialization failure,
and userspace failure from logs before changing inputs. Restore stock only from
the verified matching firmware archive and retain the failing image/logs.

There is intentionally no Odin command here: a command with model/partition
assumptions would be a destructive operation without the required confirmation.
