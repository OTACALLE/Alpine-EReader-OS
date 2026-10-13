import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tooling import build_image

ROOT = Path(build_image.ROOT)
MANIFEST = ROOT / "images" / "samsung-j2core.json"


def members(blob: bytes) -> dict[str, tarfile.TarInfo]:
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        return {m.name: m for m in archive.getmembers()}


class BuildImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = build_image.build_tarball(ROOT, MANIFEST)
        cls.members = members(cls.blob)

    def test_two_builds_are_identical(self):
        self.assertEqual(self.blob, build_image.build_tarball(ROOT, MANIFEST))

    def test_names_are_sorted_and_metadata_is_normalized(self):
        names = [n for n, m in self.members.items() if not m.issym()]
        self.assertEqual(names, sorted(names))
        for member in self.members.values():
            self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 0))
            self.assertEqual((member.uname, member.gname), ("root", "root"))

    def test_scripts_are_executable_and_data_is_not_world_writable(self):
        for name in ("etc/init.d/powerd", "etc/init.d/ereader-shell", "usr/libexec/ereader/powerd"):
            self.assertEqual(self.members[name].mode, 0o755, name)
        for name, member in self.members.items():
            if name.endswith(".py") or name.endswith(".json"):
                self.assertEqual(member.mode, 0o644, name)

    def test_output_does_not_depend_on_host_modes_mtimes_or_listing_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for sub in ("core", "shell", "reader_integration", "images", "devices/samsung-j2core"):
                shutil.copytree(ROOT / sub, copy / sub, ignore=shutil.ignore_patterns("__pycache__", "evidence"))
            for path in copy.rglob("*"):
                os.utime(path, (1_234_567_890, 1_234_567_890))
                os.chmod(path, 0o777 if path.is_dir() else 0o666)  # what Windows reports
            self.assertEqual(self.blob, build_image.build_tarball(copy, copy / "images" / "samsung-j2core.json"))

    def test_powerd_is_enabled_and_shell_is_installed_but_not_enabled(self):
        link = self.members["etc/runlevels/default/powerd"]
        self.assertTrue(link.issym())
        self.assertEqual(link.linkname, "/etc/init.d/powerd")
        self.assertNotIn("etc/runlevels/default/ereader-shell", self.members)

    def test_every_service_command_exists_in_the_image(self):
        with tarfile.open(fileobj=io.BytesIO(self.blob)) as archive:
            for script in ("etc/init.d/powerd", "etc/init.d/ereader-shell"):
                text = archive.extractfile(script).read().decode()
                self.assertTrue(text.startswith("#!/sbin/openrc-run\n"))
                command = re.search(r'^command="([^"]+)"', text, re.M).group(1)
                if command.startswith("/usr/libexec/"):
                    self.assertIn(command.lstrip("/"), self.members)
            wrapper = archive.extractfile("usr/libexec/ereader/powerd").read().decode()
            self.assertIn("PYTHONPATH=/usr/lib/ereader", wrapper)
            self.assertIn("core.ereader_core.powerd", wrapper)

    def test_installed_tree_runs_without_the_repository_on_the_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "rootfs"
            with tarfile.open(fileobj=io.BytesIO(self.blob)) as archive:
                regular = [m for m in archive.getmembers() if m.isfile()]
                archive.extractall(target, members=regular)
            env = {**os.environ, "PYTHONPATH": str(target / "usr/lib/ereader")}
            code = ("import core.ereader_core.power, core.ereader_core.powerd, shell.ereader_shell.state, "
                    "reader_integration.launcher; print('imports-ok')")
            result = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), "imports-ok", result.stderr)
            data = Path(tmp) / "data"
            (data / "Books").mkdir(parents=True)
            (data / "Books" / "a.epub").write_text("x")
            shell = subprocess.run([sys.executable, "-m", "shell.ereader_shell.app", "--data-root", str(data)],
                                   cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(shell.returncode, 0, shell.stderr)
            self.assertIn("a.epub", shell.stdout)
            self.assertIn("screen=library", shell.stdout)
            powerd = subprocess.run([sys.executable, "-m", "core.ereader_core.powerd", "--run-for", "0.05",
                                     "--interval", "0.01"], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(powerd.returncode, 0, powerd.stderr)

    def test_cli_writes_archive_and_matching_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist" / "image.tar"
            argv = ["build_image.py", "--device", "images/samsung-j2core.json", "--output", str(out)]
            with mock.patch("sys.argv", argv):
                self.assertEqual(build_image.main(), 0)
            digest = hashlib.sha256(out.read_bytes()).hexdigest()
            sidecar = out.with_suffix(".tar.sha256").read_bytes()
            self.assertEqual(sidecar, f"{digest}  image.tar\n".encode())  # LF even on Windows
            self.assertEqual(out.read_bytes(), self.blob)

    def test_missing_device_profile_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "m.json"
            manifest.write_text('{"device_profile": "nope.json"}')
            with self.assertRaises(SystemExit):
                build_image.build_tarball(Path(tmp), manifest)


if __name__ == "__main__":
    unittest.main()
