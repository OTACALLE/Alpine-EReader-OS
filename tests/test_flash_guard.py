import json
import re
import tempfile
import unittest
from pathlib import Path

from tooling import flash_guard as guard

DEVICE = Path("devices/samsung-j2core")
FLASHERS = re.compile(r"\b(fastboot\s+flash|heimdall\s+flash|odin4?\b|dd\s+[^\n]*of=/dev/|adb\s+(?:\S+\s+)*(?:sideload|reboot\s+download))", re.I)


def decide(*targets, **kwargs):
    return {d.target: d for d in guard.evaluate(DEVICE, list(targets), **kwargs)}


class FlashGuardTests(unittest.TestCase):
    def test_never_modify_partitions_are_denied_even_if_authorized(self):
        for name in ("EFS", "CPEFS", "RADIO", "MISC", "PARAM", "BOTA0", "m9kefs1", "mmcblk0",
                     "mmcblk0boot0", "mmcblk0rpmb"):
            result = decide(name, authorized={name}, destructive_authorized={name})[name]
            self.assertFalse(result.allowed, name)

    def test_targets_resolve_by_name_device_and_path_case_insensitively(self):
        for form in ("EFS", "efs", "mmcblk0p3", "/dev/block/mmcblk0p3", "/dev/block/by-name/EFS",
                     "/dev/block/platform/13540000.dwmmc0/by-name/efs"):
            result = decide(form)[form]
            self.assertEqual(result.name, "EFS", form)
            self.assertFalse(result.allowed)

    def test_unknown_and_empty_targets_are_denied(self):
        for target in ("NOPE", "mmcblk0p99", "/dev/block/", ""):
            self.assertFalse(decide(target)[target].allowed, target)

    def test_boot_needs_explicit_authorization(self):
        self.assertFalse(decide("BOOT")["BOOT"].allowed)
        self.assertTrue(decide("BOOT", authorized={"boot"})["BOOT"].allowed)
        self.assertTrue(decide("mmcblk0p10", authorized={"BOOT"})["mmcblk0p10"].allowed)

    def test_destructive_partitions_need_destructive_authorization(self):
        self.assertFalse(decide("SYSTEM", authorized={"SYSTEM"})["SYSTEM"].allowed)
        self.assertTrue(decide("SYSTEM", destructive_authorized={"SYSTEM"})["SYSTEM"].allowed)
        self.assertFalse(decide("USERDATA")["USERDATA"].allowed)

    def test_unverified_partitions_stay_blocked_until_verified(self):
        self.assertFalse(decide("VENDOR", authorized={"VENDOR"})["VENDOR"].allowed)
        self.assertTrue(decide("VENDOR", authorized={"VENDOR"}, verified={"VENDOR"})["VENDOR"].allowed)
        self.assertFalse(decide("VENDOR", verified={"VENDOR"})["VENDOR"].allowed)

    def test_no_partition_is_verified_in_the_repository(self):
        self.assertEqual(guard.load_verified(DEVICE), set())

    def test_oversized_image_is_denied(self):
        size = 32 * 1024 * 1024 + 1
        self.assertFalse(decide("BOOT", authorized={"BOOT"}, sizes={"BOOT": size})["BOOT"].allowed)
        self.assertTrue(decide("BOOT", authorized={"BOOT"}, sizes={"BOOT": size - 1})["BOOT"].allowed)

    def test_require_allowed_raises_with_every_refusal(self):
        with self.assertRaises(guard.FlashBlocked) as caught:
            guard.require_allowed(DEVICE, ["BOOT", "EFS", "NOPE"], authorized={"BOOT"})
        self.assertIn("EFS", str(caught.exception))
        self.assertIn("NOPE", str(caught.exception))
        self.assertEqual(len(guard.require_allowed(DEVICE, ["BOOT"], authorized={"BOOT"})), 1)

    def test_verified_file_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp)
            (device / "partition-map.json").write_text((DEVICE / "partition-map.json").read_text())
            (device / "verified-partitions.json").write_text(json.dumps({"verified": ["VENDOR"]}))
            result = guard.evaluate(device, ["VENDOR"], authorized={"VENDOR"})[0]
            self.assertTrue(result.allowed)

    def test_cli_exit_codes(self):
        self.assertEqual(guard.main(["--device", str(DEVICE), "BOOT", "--authorize", "BOOT"]), 0)
        self.assertEqual(guard.main(["--device", str(DEVICE), "BOOT", "EFS", "--authorize", "BOOT"]), 1)

    def test_every_tool_that_invokes_a_flasher_consults_the_guard(self):
        offenders = []
        for path in list(Path("tooling").rglob("*.py")) + list(Path("tooling").rglob("*.sh")) + list(Path("devices").rglob("*.sh")):
            if path.name == "flash_guard.py":
                continue
            text = path.read_text(encoding="utf-8")
            if FLASHERS.search(text) and "flash_guard" not in text:
                offenders.append(str(path))
        self.assertEqual(offenders, [], "flashing tools must call tooling.flash_guard.require_allowed")

    def test_the_flasher_pattern_would_catch_a_violation(self):
        for sample in ("fastboot flash boot x.img", "heimdall flash --BOOT x", "dd if=x of=/dev/block/mmcblk0p10",
                       "adb reboot download"):
            self.assertTrue(FLASHERS.search(sample), sample)


if __name__ == "__main__":
    unittest.main()
