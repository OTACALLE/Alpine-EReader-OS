"""The J2 Core JSON records are verified against the raw ADB transcript, not constants."""
import copy
import json
import unittest
from pathlib import Path

from tooling import j2core_capture, render_partition_map, verify_config_gz
from tooling import validate_j2core_evidence as validator

DEVICE = Path("devices/samsung-j2core")


def _load(name):
    return json.loads((DEVICE / name).read_text(encoding="utf-8"))


class RawCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = j2core_capture.load()
        cls.profile = _load("device-profile.json")
        cls.mapping = _load("partition-map.json")
        cls.boot = _load("boot-parameters.json")
        cls.config = verify_config_gz.analyze(DEVICE / "evidence" / "j2core-config.gz")

    def test_capture_parses_the_expected_facts(self):
        self.assertEqual(self.capture["uname"]["machine"], "armv8l")
        self.assertEqual(self.capture["uname"]["release"], "3.18.14-15008757-QB43519801")
        self.assertEqual(len(self.capture["by_name"]), 26)
        self.assertEqual(self.capture["block_sizes"]["mmcblk0p10"], 32 * 1024 * 1024)
        self.assertEqual(self.capture["controller"], "13540000.dwmmc0")
        props = self.capture["properties"]
        self.assertEqual(props["sys.oem_unlock_allowed"], "0")
        self.assertEqual(props["ro.oem_unlock_supported"], "1")
        self.assertEqual(props["ro.boot.bootloader"], "J260MUBSDAUI4")

    def test_every_captured_partition_is_in_the_map_with_exact_device_and_size(self):
        self.assertEqual(set(self.mapping["partitions"]), set(self.capture["by_name"]))
        for name, entry in self.mapping["partitions"].items():
            device = self.capture["by_name"][name]
            self.assertEqual(entry["device"], device, name)
            self.assertEqual(entry["bytes"], self.capture["block_sizes"][device], name)
        for name, entry in self.mapping["emmc_special"].items():
            self.assertEqual(entry["bytes"], self.capture["block_sizes"][name], name)

    def test_committed_records_pass_the_validator(self):
        self.assertEqual(validator.check(self.capture, self.profile, self.mapping, self.boot, self.config), [])

    def test_profile_matches_the_capture_and_the_kernel_config(self):
        runtime = self.profile["runtime"]
        self.assertEqual(runtime["uname_machine_seen_by_32bit_adb_shell"], self.capture["uname"]["machine"])
        self.assertEqual(runtime["kernel_architecture"], self.config["kernel_architecture"])
        self.assertEqual(self.config["key_options"]["COMPAT"], "y")  # what makes the armv7 userspace possible
        self.assertEqual(self.config["header_kernel_version"], "3.18.14")

    def test_boot_capacity_matches_boot_partition(self):
        self.assertEqual(self.boot["boot_partition_max_bytes"], self.mapping["partitions"]["BOOT"]["bytes"])
        self.assertEqual(self.boot["cmdline"], "androidboot.selinux=permissive androidboot.selinux=permissive")  # extracted from stock boot.img

    def test_oem_unlock_availability_is_recorded_but_not_assumed_performed(self):
        status = self.profile["boot"]["unlock_status"]
        self.assertIn("availability verified", status)
        self.assertIn("not recorded", status)  # unlocked state itself is unknown
        self.assertEqual(self.capture["properties"]["sys.oem_unlock_allowed"], "0")  # capture predates the toggle

    def test_generated_markdown_is_current(self):
        text = (DEVICE / "partition-map.md").read_text(encoding="utf-8")
        self.assertEqual(text, render_partition_map.render(self.mapping))

    def test_validator_rejects_tampered_records(self):
        def mutated(change):
            mapping = copy.deepcopy(self.mapping)
            change(mapping)
            return validator.check(self.capture, self.profile, mapping, self.boot, self.config)

        self.assertTrue(mutated(lambda m: m["partitions"]["BOOT"].update(bytes=1)))
        self.assertTrue(mutated(lambda m: m["partitions"]["BOOT"].update(device="mmcblk0p11")))
        self.assertTrue(mutated(lambda m: m["partitions"].pop("MISC")))
        self.assertTrue(mutated(lambda m: m["partitions"]["EFS"].update(write_policy="explicit-authorization")))
        self.assertTrue(mutated(lambda m: m["partitions"]["BOOT"].update(write_policy="whatever")))
        self.assertTrue(mutated(lambda m: m.update(default_for_unlisted_targets="allow")))
        for key, value in (("kernel_architecture", "arm"), ("uname_machine_seen_by_32bit_adb_shell", "aarch64")):
            profile = copy.deepcopy(self.profile)
            profile["runtime"][key] = value
            self.assertTrue(validator.check(self.capture, profile, self.mapping, self.boot, self.config), key)
        self.assertTrue(validator.check(self.capture, self.profile, self.mapping, self.boot, None))  # no config = unproven
        no_compat = dict(self.config, key_options=dict(self.config["key_options"], COMPAT="n"))
        self.assertTrue(validator.check(self.capture, self.profile, self.mapping, self.boot, no_compat))

    def test_capture_parser_errors(self):
        with self.assertRaises(ValueError):
            j2core_capture.parse_uname("nothing here")
        with self.assertRaises(ValueError):
            j2core_capture.parse_controller("nothing here")

    def test_validator_main_reports_success(self):
        self.assertEqual(validator.main(), 0)


if __name__ == "__main__":
    unittest.main()
