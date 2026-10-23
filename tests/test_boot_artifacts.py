import gzip
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._newc import parse_newc
from tooling import android_bootimg as boot
from tooling import build_initramfs as initramfs

ARGS = dict(base=0x10000000, kernel_offset=0x8000, ramdisk_offset=0x1000000,
            tags_offset=0x100, page_size=2048, board="SRPRF18A001RU")


class AndroidBootImageTests(unittest.TestCase):
    def test_android_v0_image_has_expected_addresses_and_is_deterministic(self):
        first = boot.pack(b"kernel", b"ramdisk", b"dt", **ARGS)
        self.assertEqual(first, boot.pack(b"kernel", b"ramdisk", b"dt", **ARGS))
        metadata = boot.inspect(first)
        self.assertEqual(metadata["format"], "android-boot-v0")
        self.assertEqual(metadata["kernel_addr"], "0x10008000")
        self.assertEqual(metadata["ramdisk_addr"], "0x11000000")
        self.assertEqual(metadata["second_addr"], "0x10f00000")
        self.assertEqual(metadata["tags_addr"], "0x10000100")
        self.assertEqual(metadata["dt_size"], 2)
        self.assertTrue(metadata["id_matches_content"])

    def test_cmdline_roundtrip_and_header_fields(self):
        image = boot.pack(b"k", b"r", b"d", cmdline="console=ttyS0 ereader.root=/dev/x",
                          extra_cmdline="quiet", **ARGS)
        fields = boot.HEADER.unpack(image[:boot.HEADER.size])
        self.assertTrue(fields[12].startswith(b"console=ttyS0 ereader.root=/dev/x\0"))
        self.assertTrue(fields[14].startswith(b"quiet\0"))
        meta = boot.inspect(image)
        self.assertEqual(meta["cmdline"], "console=ttyS0 ereader.root=/dev/x")
        self.assertEqual(meta["extra_cmdline"], "quiet")

    def test_cmdline_limits_and_charset(self):
        boot.pack(b"k", b"r", b"d", cmdline="a" * 511, extra_cmdline="b" * 1023, **ARGS)
        for bad in ({"cmdline": "a" * 512}, {"extra_cmdline": "b" * 1024},
                    {"cmdline": "caf\u00e9"}, {"cmdline": "a\0b"}):
            with self.assertRaises(ValueError, msg=bad):
                boot.pack(b"k", b"r", b"d", **bad, **ARGS)

    def test_samsung_trailer_and_zero_padding_are_tolerated(self):
        base = boot.pack(b"kernel", b"ramdisk", b"dt", **ARGS)
        stock_like = boot.pack(b"kernel", b"ramdisk", b"dt", samsung_trailer=True, **ARGS)
        self.assertEqual(stock_like, base + boot.SAMSUNG_TRAILER)
        self.assertTrue(boot.inspect(stock_like)["samsung_trailer"])
        padded = stock_like + b"\0" * 100
        self.assertTrue(boot.inspect(padded)["samsung_trailer"])
        self.assertEqual(boot.inspect(base + b"\0" * 64)["zero_padding"], 64)

    def test_foreign_trailing_data_and_truncation_are_rejected(self):
        base = boot.pack(b"kernel", b"ramdisk", b"dt", **ARGS)
        for bad in (base + b"junk", base + boot.SAMSUNG_TRAILER + b"x", base[:-1]):
            with self.assertRaises(ValueError):
                boot.inspect(bad)
        with self.assertRaises(ValueError):
            boot.inspect(b"ANDROID!")
        with self.assertRaises(ValueError):
            boot.inspect(b"X" * 2048)

    def test_partition_limit_is_enforced(self):
        image = boot.pack(b"kernel", b"ramdisk", b"dt", **ARGS)
        boot.pack(b"kernel", b"ramdisk", b"dt", max_bytes=len(image), **ARGS)
        with self.assertRaises(ValueError):
            boot.pack(b"kernel", b"ramdisk", b"dt", max_bytes=len(image) - 1, **ARGS)
        with self.assertRaises(ValueError):
            boot.inspect(image, max_bytes=len(image) - 1)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            boot.pack(b"k", b"r", b"d", **{**ARGS, "page_size": 1000})
        with self.assertRaises(ValueError):
            boot.pack(b"k", b"r", b"d", **{**ARGS, "board": "x" * 16})
        with self.assertRaises(ValueError):
            boot.pack(b"", b"r", b"d", **ARGS)
        blob = bytearray(boot.pack(b"k", b"r", b"d", **ARGS))
        blob[36:40] = (1000).to_bytes(4, "little")  # page_size field
        with self.assertRaises(ValueError):
            boot.inspect(bytes(blob))

    def test_cli_create_and_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name, data in (("k", b"kernel"), ("r", b"ramdisk"), ("d", b"dt")):
                (tmp / name).write_bytes(data)
            out = tmp / "boot.img"
            create = ["create", "--kernel", str(tmp / "k"), "--ramdisk", str(tmp / "r"), "--dt", str(tmp / "d"),
                      "--output", str(out), "--base", "0x10000000", "--kernel-offset", "0x8000",
                      "--ramdisk-offset", "0x1000000", "--tags-offset", "0x100", "--page-size", "2048",
                      "--cmdline", "console=tty0", "--samsung-trailer", "--max-bytes", "33554432"]
            with mock.patch("sys.argv", ["android_bootimg.py", *create]):
                self.assertEqual(boot.main(), 0)
            self.assertTrue(boot.inspect(out.read_bytes())["samsung_trailer"])
            with mock.patch("sys.argv", ["android_bootimg.py", "inspect", str(out)]):
                self.assertEqual(boot.main(), 0)


class InitramfsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.staging = Path(self._tmp.name) / "root"
        (self.staging / "etc").mkdir(parents=True)
        (self.staging / "sbin").mkdir()
        (self.staging / "etc" / "issue").write_text("Alpine EReader OS\n")
        (self.staging / "sbin" / "tool").write_bytes(b"\x7fELF....")
        (self.staging / "bin").mkdir()
        (self.staging / "bin" / "script").write_text("#!/bin/sh\n")

    def build(self, **kwargs):
        kwargs.setdefault("init", b"#!/bin/sh\nexec sh\n")
        return parse_newc(initramfs.build(self.staging, **kwargs))

    def test_newc_payload_is_stable_and_contains_trailer(self):
        first = initramfs.build(self.staging, init=b"#!/bin/sh\n")
        self.assertEqual(first, initramfs.build(self.staging, init=b"#!/bin/sh\n"))
        self.assertIn(b"TRAILER!!!", first)

    def test_executable_bits_are_preserved_by_content_and_location(self):
        entries = self.build()
        self.assertEqual(entries["init"]["mode"], 0o100755)
        self.assertEqual(entries["sbin/tool"]["mode"], 0o100755)
        self.assertEqual(entries["bin/script"]["mode"], 0o100755)
        self.assertEqual(entries["etc/issue"]["mode"], 0o100644)
        self.assertEqual(entries["etc"]["mode"], 0o040755)

    def test_device_nodes_exist(self):
        entries = self.build()
        self.assertEqual(entries["dev/console"]["mode"], 0o020600)
        self.assertEqual(entries["dev/console"]["rdev"], (5, 1))
        self.assertEqual(entries["dev/null"]["mode"], 0o020666)
        self.assertEqual(entries["dev/null"]["rdev"], (1, 3))
        self.assertEqual(entries["dev"]["mode"], 0o040755)
        self.assertNotIn("dev/console", self.build(device_nodes=False))

    def test_symlinks_are_kept_and_extra_symlinks_work(self):
        try:
            os.symlink("busybox", self.staging / "bin" / "sh")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this host")
        entries = self.build(extra_symlinks={"sbin/init": "/init"})
        self.assertEqual(entries["bin/sh"]["mode"], 0o120777)
        self.assertEqual(entries["bin/sh"]["data"], b"busybox")
        self.assertEqual(entries["sbin/init"]["data"], b"/init")

    def test_extra_symlink_without_host_support(self):
        entries = self.build(extra_symlinks={"bin/sh": "busybox"})
        self.assertEqual(entries["bin/sh"]["mode"], 0o120777)
        with self.assertRaises(ValueError):
            self.build(extra_symlinks={"etc/issue": "x"})

    def test_init_rules(self):
        with self.assertRaises(ValueError):
            initramfs.build(self.staging)
        (self.staging / "init").write_bytes(b"#!/bin/sh\necho mine\n")
        self.assertEqual(self.build()["init"]["data"], b"#!/bin/sh\necho mine\n")

    def test_staging_must_not_ship_device_nodes(self):
        (self.staging / "dev").mkdir()
        (self.staging / "dev" / "null").write_text("")
        with self.assertRaises(ValueError):
            initramfs.build(self.staging, init=b"#!/bin/sh\n")

    def test_output_does_not_depend_on_host_modes_or_mtimes(self):
        reference = initramfs.build(self.staging, init=b"#!/bin/sh\n")
        for path in self.staging.rglob("*"):
            os.utime(path, (1_000_000_000, 1_000_000_000))
            if path.is_file():
                os.chmod(path, 0o666)
        self.assertEqual(reference, initramfs.build(self.staging, init=b"#!/bin/sh\n"))

    def test_entries_are_sorted_with_parents_first_and_inodes_unique(self):
        entries = self.build()
        names = list(entries)
        self.assertEqual(names, sorted(names))
        self.assertEqual(len({e["ino"] for e in entries.values()}), len(entries))
        for name in names:
            parent = Path(name).parent.as_posix()
            if parent != ".":
                self.assertLess(names.index(parent), names.index(name))

    def test_cli_writes_reproducible_gzip(self):
        out = Path(self._tmp.name) / "out" / "initramfs.cpio.gz"
        argv = ["build_initramfs.py", "--staging", str(self.staging), "--output", str(out),
                "--symlink", "bin/sh=busybox"]
        with mock.patch("sys.argv", argv):
            self.assertEqual(initramfs.main(), 0)
        first = out.read_bytes()
        with mock.patch("sys.argv", argv):
            initramfs.main()
        self.assertEqual(first, out.read_bytes())
        entries = parse_newc(gzip.decompress(first))
        self.assertEqual(entries["init"]["mode"], 0o100755)  # default core/initramfs/init
        self.assertIn(b"ereader.root", entries["init"]["data"])
        self.assertEqual(entries["bin/sh"]["mode"], 0o120777)

    @unittest.skipUnless(shutil.which("cpio"), "cpio not installed")
    def test_system_cpio_accepts_the_archive(self):
        blob = initramfs.build(self.staging, init=b"#!/bin/sh\n")
        listing = subprocess.run(["cpio", "-it", "--quiet"], input=blob, capture_output=True, check=True).stdout.decode()
        self.assertIn("init", listing.split())
        self.assertIn("dev/console", listing.split())

    @unittest.skipUnless(shutil.which("sh"), "sh not installed")
    def test_default_init_script_has_valid_shell_syntax(self):
        script = Path(initramfs.DEFAULT_INIT)
        subprocess.run(["sh", "-n", str(script)], check=True)
        text = script.read_text()
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        self.assertIn("switch_root", text)


if __name__ == "__main__":
    unittest.main()
