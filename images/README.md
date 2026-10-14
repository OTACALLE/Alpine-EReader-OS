# Image assembly

- `tooling/build_image.py`: deterministic development rootfs tarball of the EReader
  installed layout (not an Alpine image).
- `tooling/build_alpine_rootfs.py`: stage 1, the pinned official Alpine armv7
  minirootfs plus that layout (`alpine-rootfs.lock.json`, ADR 0007).
- `Dockerfile.provision` + `alpine-rootfs.packages`: stage 2 (`apk add`), CI only,
  unvalidated. `alpine-rootfs.unverified` lists intended packages with no verified source
  (KOReader).
- `tooling/build_test_artifacts.py`: regenerates `dist/` (rootfs plus clearly
  synthetic, NOT-FLASHABLE boot artifacts).

None of these is a bootable J2 Core image: a verified kernel, DTB and the stock boot
parameters are still missing.
