import json
import unittest
from pathlib import Path


class J2CoreEvidenceTests(unittest.TestCase):
    def test_boot_parameters_remain_marked_unverified(self):
        values = json.loads(
            Path("devices/samsung-j2core/boot-parameters.json").read_text()
        )
        self.assertIn("no custom boot image has been tested", values["confidence"])
        self.assertEqual(values["page_size"], 2048)

    def test_approved_source_is_not_a_built_kernel_binary(self):
        lock = json.loads(
            Path("devices/samsung-j2core/sources.lock.json").read_text()
        )
        self.assertTrue(lock["kernel"]["approved_input"])
        self.assertEqual(
            lock["kernel"]["source_archive"]["sha256"],
            "0059b115fc49d93c83319f8c3c11b21242e08475147ce96598d463fab53f7b36",
        )
        self.assertEqual(lock["binary_inputs"]["kernel_image"], "absent")
        self.assertEqual(
            lock["kernel"]["reported_version_by_maintainer"],
            "3.18.14-15008757-QB43519801",
        )
        self.assertIn(
            "resolved by read-only ADB",
            lock["kernel"]["version_disposition"],
        )