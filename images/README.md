# Image assembly

`tooling/build_image.py` produces a deterministic **development rootfs tarball**
from the Core/Shell/service files and a device manifest. It is not a bootable
J2 Core image: a verified kernel, DTB, boot format, firmware, partition map,
and signing path are still absent. The artifact is useful for reviewing the
Core/Device-Port composition and for later incorporation into an Alpine build
environment without pretending to flash hardware.
