import json
import unittest
from pathlib import Path


class J2CoreEvidenceTests(unittest.TestCase):
    def test_boot_parameters_remain_marked_unverified(self):
        values = json.loads(Path("devices/samsung-j2core/boot-parameters.json").read_text())
        self.assertIn("not verified", values["confidence"])
        self.assertEqual(values["page_size"], 2048)

    def test_kernel_is_not_an_approved_input_without_exact_provenance(self):
        lock = json.loads(Path("devices/samsung-j2core/sources.lock.json").read_text())
        self.assertFalse(lock["kernel"]["approved_input"])
        self.assertEqual(lock["kernel"]["reported_version_by_maintainer"], "3.18.14-15008757-QB43519801")
        self.assertIn("conflict", lock["kernel"]["version_disposition"])
