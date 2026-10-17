# ADR 0008: What the stock kernel configuration means for the architecture

Status: findings accepted; **the decisions marked OPEN are not made**.
Source: `devices/samsung-j2core/evidence/j2core-config.gz` (kernel 3.18.14);
machine-readable summary in `devices/samsung-j2core/kernel-config-report.json`.

| Finding | Consequence |
|---|---|
| arm64, 4 KiB pages, `COMPAT=y`, `CMDLINE=""` | armv7 userspace works (ADR 0002); the command line must come from the stock `boot.img` |
| `BLK_DEV_INITRD=y`, only `RD_GZIP=y` | the initramfs must be gzip-compressed (ours is) |
| `DEVTMPFS=y`, `DEVTMPFS_MOUNT=n` | `/init` must mount devtmpfs (ours does) |
| `DRM=n`; display is the Exynos DECON **framebuffer** (`EXYNOS_DECON_FB=y`, `FB=y`) | ARCHITECTURE.md assumes DRM/KMS (section 14). **OPEN:** either rebuild with a DRM driver (none is evident for DECON 7570) or take the framebuffer path the spec holds in reserve |
| `RFKILL=n` | the power policy's radio blocking (section 17) needs a rebuild with `CONFIG_RFKILL`, or another mechanism. **OPEN** |
| `SQUASHFS=n`, `OVERLAY_FS=n` | a read-only `/usr` needs ext4 mounted read-only or a rebuild. **OPEN** |
| Wi-Fi/BT are the vendor `SCSC` driver | Wi-Fi under Alpine needs the stock firmware and the vendor driver from the GPL source; high risk |
| `VT=n`, no fbcon; `SERIAL_SAMSUNG_CONSOLE=y`; `PSTORE`/`PSTORE_RAM` on, `PSTORE_CONSOLE=n`; `SEC_DEBUG_LAST_KMSG=y`; `USB_G_ANDROID=y` with `USB_F_ACM=y` | no on-screen kernel console. Bring-up options without opening the phone: USB ACM serial from `/init`, Samsung `last_kmsg`, pstore. A UART needs the phone opened. Whether the `android_usb` sysfs interface exists on this kernel is unverified (the collector now reads it) |
| Touch driver `TOUCHSCREEN_SYNAPTICS_I2C_TD4X00_J2CORELTE=y`, `ZRAM=y`, `CGROUPS=y` | the touch driver for this exact model is in the source tree; zram and cgroups are available |
