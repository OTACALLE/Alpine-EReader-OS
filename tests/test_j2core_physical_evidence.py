import json
import unittest
from pathlib import Path


class J2CorePhysicalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(Path("devices/samsung-j2core/device-profile.json").read_text())
        self.mapping = json.loads(Path("devices/samsung-j2core/partition-map.json").read_text())

    def test_kernel_is_arm64_with_a_32bit_userspace(self):
        runtime = self.profile["runtime"]
        self.assertEqual(runtime["uname_machine_seen_by_32bit_adb_shell"], "armv8l")
        self.assertEqual(runtime["kernel_architecture"], "arm64")
        self.assertEqual(runtime["initial_userspace_architecture"], "armv7")
        self.assertNotIn("kernel_machine", runtime)  # the old, wrong reading of uname

    def test_live_boot_recovery_and_data_mapping(self):
        partitions = self.mapping["partitions"]
        self.assertEqual(partitions["BOOT"]["device"], "mmcblk0p10")
        self.assertEqual(partitions["BOOT"]["bytes"], 32 * 1024 * 1024)
        self.assertEqual(partitions["RECOVERY"]["device"], "mmcblk0p11")
        self.assertEqual(partitions["USERDATA"]["device"], "mmcblk0p26")

    def test_radio_identity_partitions_cannot_be_targets(self):
        for name in ("EFS", "CPEFS", "RADIO", "CP_DEBUG"):
            self.assertEqual(self.mapping["partitions"][name]["write_policy"], "never-modify")
