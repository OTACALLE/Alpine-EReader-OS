import json
import unittest
from pathlib import Path


class PackageMetadataTests(unittest.TestCase):
    def test_core_metadata_declares_alpine_runtime(self):
        data = json.loads(Path("packages/ereader-core/package.json").read_text())
        self.assertEqual(data["target"], "alpine")
        self.assertIn("openrc", data["runtime_dependencies"])
        self.assertTrue(data["files"])
