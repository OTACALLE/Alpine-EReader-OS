# Windows development workflow

No Linux distribution, WSL, virtual machine, partition, or host-OS change is
required for the current repository checks.

From PowerShell, use the Python launcher already available on Windows:

```powershell
py -3 -m unittest discover -s tests -t . -v
py -3 tooling/validate_device_profile.py devices/samsung-j2core/device-profile.json
py -3 tooling/build_image.py --device images/samsung-j2core.json --output dist/samsung-j2core-development-rootfs.tar
```

The last command builds a deterministic development rootfs tarball and SHA-256
sidecar, not a device image. Producing a real Alpine ARM image will need a
separate Linux-capable build executor (for example a CI runner) after the J2
Core boot-chain evidence exists. Do not install or enable a Linux environment
on the Windows host for this project.

Image hashes are host-independent: modes, ordering and line endings come from
the sources (`.gitattributes` forces LF), and CI proves that Windows and Linux
produce the same SHA-256 (`reproducible` job).
