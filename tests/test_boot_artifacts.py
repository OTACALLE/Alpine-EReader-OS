import gzip
import tempfile
import unittest
from pathlib import Path

from tooling.android_bootimg import inspect, pack
from tooling.build_initramfs import build


class BootArtifactTests(unittest.TestCase):
    def test_android_v0_image_has_expected_addresses_and_is_deterministic(self):
        arguments = dict(base=0x10000000, kernel_offset=0x8000, ramdisk_offset=0x1000000,
                         tags_offset=0x100, page_size=2048, board="SRPRF18A001RU")
        first = pack(b"kernel", b"ramdisk", b"dt", **arguments)
        self.assertEqual(first, pack(b"kernel", b"ramdisk", b"dt", **arguments))
        metadata = inspect(first)
        self.assertEqual(metadata["format"], "android-boot-v0")
        self.assertEqual(metadata["kernel_addr"], "0x10008000")
        self.assertEqual(metadata["ramdisk_addr"], "0x11000000")
        self.assertEqual(metadata["tags_addr"], "0x10000100")
        self.assertEqual(metadata["dt_size"], 2)

    def test_corrupt_or_truncated_boot_image_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect(b"ANDROID!")

    def test_newc_payload_is_stable_and_contains_trailer(self):
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary) / "root"
            (staging / "etc").mkdir(parents=True)
            (staging / "etc" / "issue").write_text("Alpine EReader OS\n")
            first = build(staging)
            self.assertEqual(first, build(staging))
            self.assertIn(b"TRAILER!!!", first)
