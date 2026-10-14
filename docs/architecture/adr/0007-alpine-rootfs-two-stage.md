# ADR 0007: Alpine rootfs is built in two stages from a pinned minirootfs

Status: accepted. KOReader packaging is explicitly **not** decided here.

**Stage 1** (`tooling/build_alpine_rootfs.py`, runs anywhere Python runs): the
official Alpine armv7 minirootfs is taken from a pinned `alpinelinux/docker-alpine`
commit, verified by SHA-256 (`images/alpine-rootfs.lock.json`), its `busybox` is
checked to be a 32-bit ARM EABI5 hard-float ELF (matching the armv7 userspace of
ADR 0002), and the EReader overlay is added with deterministic metadata.

**Stage 2** (`images/Dockerfile.provision`, CI only): `apk add` of
`images/alpine-rootfs.packages` under qemu-user. It needs the Alpine mirrors, so it
is unvalidated until a CI run succeeds.

Known limits: the pin proves integrity relative to the pinned GitHub commit, not
Alpine's PGP signature; the lock records the pending independent check against
`dl-cdn.alpinelinux.org`. Packages are not version-pinned, so stage 2 output is not
bit-reproducible; its package list is recorded in `/etc/ereader/apk-packages.txt`.
`koreader` has no verified Alpine package and lives in
`images/alpine-rootfs.unverified` until an ADR chooses how to obtain it.
