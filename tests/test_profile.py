import json
import unittest
from pathlib import Path

from tooling.validate_device_profile import validate


class DeviceProfileTests(unittest.TestCase):
    def test_j2core_profile_is_valid(self):
        profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        self.assertEqual(validate(profile), [])

    def test_missing_identity_is_rejected(self):
        self.assertTrue(validate({"schema_version": 1}))
