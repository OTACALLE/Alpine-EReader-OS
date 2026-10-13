# SM-J260M flash gate and recovery checklist

Nothing here authorizes flashing. It lists what must be true first.

## Gate

1. The OEM-unlock toggle is enabled and the bootloader unlock is **verified on
   the unit** (it erases user data and trips Knox). Back up everything first.
2. The exact stock firmware (`J260MUBSDAUI4`) is downloaded and its checksum
   recorded, so the device can be returned to stock.
3. Download mode entry and the flashing method are demonstrated on the unit.
4. The stock `boot.img` is extracted: kernel command line and format known.
5. Every write goes through `tooling/flash_guard.py`
   (`devices/samsung-j2core/partition-map.json`):
   - `never-modify`: BOTA0/1, EFS, CPEFS, m9kefs1-3, RADIO, NAD_*, CP_DEBUG,
     PARAM, PERSISTENT, STEADY, MISC, OMR, RESERVED2, the whole disk and the
     eMMC boot/RPMB areas. No override exists.
   - `blocked-until-verified`: DTBO, VENDOR, ODM, HIDDEN.
   - `explicit-authorization`: BOOT, RECOVERY. `explicit-destructive-authorization`:
     SYSTEM, USERDATA, CACHE.
6. Candidate first writes target BOOT only, with the stock BOOT image saved
   first and an image no larger than 32 MiB.

## Recovery

Re-flash the stock firmware with the recorded method. No on-device recovery
exists; the architecture accepts manual re-flash for the MVP.
