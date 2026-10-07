import tempfile
import unittest
from pathlib import Path

from core.ereader_core.config import ConfigStore, validate_config


class ConfigTests(unittest.TestCase):
    def test_defaults_and_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ConfigStore(Path(temporary) / "Config" / "settings.json")
            self.assertEqual(store.load()["theme"], "light")
            store.save({"theme": "dark", "font_size": 24, "wifi_pinned": True})
            self.assertEqual(store.load()["font_size"], 24)

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            validate_config({"font_size": 2})
