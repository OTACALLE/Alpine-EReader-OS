# Continuous integration

GitHub Actions runs syntax compilation, the dependency-free unit/integration
suite, Device Profile and package-metadata validation, and development-rootfs
assembly. It validates only device-independent work. No CI job asserts that an
SM-J260M boots, renders, connects to Wi-Fi, or can be flashed.
