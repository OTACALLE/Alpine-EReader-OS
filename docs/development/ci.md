# Continuous integration

GitHub Actions runs on Linux and Windows: syntax compilation, the unit and
integration suite with a coverage floor, Device Profile, raw-evidence, package
and generated-map validation, and development-rootfs assembly. A `reproducible`
job compares the rootfs SHA-256 built on both hosts. CI validates only
device-independent work: no job asserts that an SM-J260M boots, renders,
connects to Wi-Fi, or can be flashed.
