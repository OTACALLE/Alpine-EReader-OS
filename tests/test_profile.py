import json
import unittest
from pathlib import Path

from tooling.validate_device_profile import validate


class DeviceProfileTests(unittest.TestCase):
    def test_j2core_profile_is_valid(self):
        profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        self.assertEqual(validate(profile), [])

    def test_j2core_makes_no_unproven_support_claim(self):
        profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        self.assertEqual(profile["support"]["tier"], "unvalidated")

    def test_yellow_and_green_require_verified_hardware_results(self):
        profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        for tier in ("yellow", "green"):
            profile["support"]["tier"] = tier
            errors = validate(profile)
            self.assertEqual(len(errors), 5, errors)
        for field in ("boot_status", "kernel_status", "display_status", "touchscreen_status", "storage_status"):
            profile["support"][field] = "verified"
        profile["support"]["tier"] = "yellow"
        self.assertEqual(validate(profile), [])

    def test_unknown_tier_is_rejected(self):
        profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        profile["support"]["tier"] = "shiny"
        self.assertTrue(validate(profile))

    def test_missing_identity_is_rejected(self):
        self.assertTrue(validate({"schema_version": 1}))
