import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shell.ereader_shell.state import Screen, ShellState
from tooling import release_manifest, render_partition_map, validate_device_profile, validate_package_metadata


def run(main, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class PackageMetadataTests(unittest.TestCase):
    def good(self):
        return json.loads(Path("packages/ereader-core/package.json").read_text())

    def test_repository_package_is_valid_and_all_files_exist(self):
        self.assertEqual(validate_package_metadata.validate(self.good()), [])
        self.assertEqual(run(validate_package_metadata.main, "packages/ereader-core/package.json")[0], 0)

    def test_problems_are_reported(self):
        data = self.good()
        data["files"].append("core/does_not_exist.py")
        data["target"] = "debian"
        del data["version"]
        errors = validate_package_metadata.validate(data)
        self.assertEqual(len(errors), 3, errors)
        self.assertTrue(validate_package_metadata.validate({**self.good(), "files": []}))

    def test_cli_exit_codes(self):
        self.assertEqual(run(validate_package_metadata.main)[0], 2)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "p.json"
            bad.write_text(json.dumps({"target": "alpine"}))
            self.assertEqual(run(validate_package_metadata.main, str(bad))[0], 1)


class DeviceProfileCliTests(unittest.TestCase):
    def test_exit_codes(self):
        path = "devices/samsung-j2core/device-profile.json"
        self.assertEqual(validate_device_profile.main(["v"]), 2)
        self.assertEqual(validate_device_profile.main(["v", path]), 0)
        self.assertEqual(validate_device_profile.main(["v", "no-such-file.json"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "p.json"
            broken.write_text(json.dumps({"schema_version": 1}))
            self.assertEqual(validate_device_profile.main(["v", str(broken)]), 1)
            broken.write_text("{not json")
            self.assertEqual(validate_device_profile.main(["v", str(broken)]), 2)


class ReleaseManifestTests(unittest.TestCase):
    def test_manifest_hashes_artifacts_and_never_claims_flashable(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "a.bin"
            artifact.write_bytes(b"abc")
            out = Path(tmp) / "m" / "manifest.json"
            with mock.patch("sys.argv", ["r", "--output", str(out), str(artifact)]):
                self.assertEqual(release_manifest.main(), 0)
            data = json.loads(out.read_text())
            self.assertFalse(data["flashable_claim"])
            self.assertEqual(data["artifacts"][0]["bytes"], 3)
            self.assertEqual(data["artifacts"][0]["sha256"],
                             "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_missing_artifact_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.argv", ["r", "--output", str(Path(tmp) / "m.json"), str(Path(tmp) / "nope")]):
                with self.assertRaises(SystemExit):
                    release_manifest.main()


class RenderPartitionMapTests(unittest.TestCase):
    def test_generate_then_check_and_detect_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "dev"
            device.mkdir()
            shutil.copy("devices/samsung-j2core/partition-map.json", device)
            self.assertEqual(render_partition_map.main(["--device", str(device), "--check"]), 1)
            self.assertEqual(render_partition_map.main(["--device", str(device)]), 0)
            self.assertEqual(render_partition_map.main(["--device", str(device), "--check"]), 0)
            (device / "partition-map.md").write_text("stale\n")
            self.assertEqual(render_partition_map.main(["--device", str(device), "--check"]), 1)


class ShellStateTests(unittest.TestCase):
    def test_navigation_rules(self):
        state = ShellState()
        self.assertEqual(state.back(), Screen.LIBRARY)  # cannot pop the last screen
        state.open(Screen.SETTINGS)
        state.open(Screen.SETTINGS)  # no duplicate
        self.assertEqual(len(state.stack), 2)
        state.open_book("/Books/a.epub")
        self.assertEqual(state.screen, Screen.READER)
        self.assertEqual(state.back(), Screen.SETTINGS)
        state.open(Screen.LIBRARY)
        self.assertEqual(state.stack, [Screen.LIBRARY])
        with self.assertRaises(ValueError):
            state.open_book("")


if __name__ == "__main__":
    unittest.main()
