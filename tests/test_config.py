import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.ereader_core.config import DEFAULT_CONFIG, ConfigStore, validate_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "Config" / "settings.json"
        self.store = ConfigStore(self.path)

    def test_defaults_and_atomic_roundtrip(self):
        self.assertEqual(self.store.load()["theme"], "light")
        self.store.save({"theme": "dark", "font_size": 24, "wifi_pinned": True})
        self.assertEqual(self.store.load()["font_size"], 24)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["settings.json"])

    def test_rejects_invalid_values(self):
        for bad in ({"font_size": 2}, {"font_size": True}, {"font_size": 20.0}, {"theme": "x"},
                    {"wifi_pinned": 1}, {"nope": 1}):
            with self.assertRaises(ValueError, msg=bad):
                validate_config(bad)
        with self.assertRaises(ValueError):
            validate_config([1, 2])

    def test_corrupt_json_returns_defaults_and_preserves_file(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"theme": "lig', encoding="utf-8")
        self.assertEqual(self.store.load(), DEFAULT_CONFIG)
        self.assertIn("JSONDecodeError", self.store.last_error)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.store.preserved_path.read_text(encoding="utf-8"), '{"theme": "lig')

    def test_invalid_content_and_binary_garbage_are_preserved_too(self):
        self.path.parent.mkdir(parents=True)
        for index, content in enumerate((b'{"font_size": 1}', b"[1]", b"\xff\xfe\x00bad")):
            self.path.write_bytes(content)
            self.assertEqual(self.store.load(), DEFAULT_CONFIG)
            self.assertEqual(self.store.preserved_path.read_bytes(), content)
            expected = "settings.json.corrupt" + (f".{index}" if index else "")
            self.assertEqual(self.store.preserved_path.name, expected)

    def test_good_load_clears_previous_error(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("garbage")
        self.store.load()
        self.store.save({"theme": "dark"})
        self.store.load()
        self.assertIsNone(self.store.last_error)
        self.assertIsNone(self.store.preserved_path)

    def test_save_fsyncs_file_and_replaces_atomically(self):
        with mock.patch("core.ereader_core.config.os.fsync") as fsync:
            self.store.save({"theme": "dark"})
        self.assertGreaterEqual(fsync.call_count, 1)
        self.assertEqual(json.loads(self.path.read_text())["theme"], "dark")

    def test_failed_save_keeps_old_file_and_leaves_no_temp_files(self):
        self.store.save({"theme": "light", "font_size": 30})
        with mock.patch("core.ereader_core.config.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save({"theme": "dark"})
        self.assertEqual(self.store.load()["font_size"], 30)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["settings.json"])

    def test_invalid_save_never_touches_disk(self):
        with self.assertRaises(ValueError):
            self.store.save({"font_size": 1})
        self.assertFalse(self.path.parent.exists())


if __name__ == "__main__":
    unittest.main()
