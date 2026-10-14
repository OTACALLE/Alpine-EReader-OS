import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tooling import (android_bootimg, build_alpine_rootfs, build_image, build_test_artifacts,
                     collect_device_evidence, extract_stock_boot, verify_config_gz, verify_kernel_source)

BOOT_ARGS = dict(base=0x10000000, kernel_offset=0x8000, ramdisk_offset=0x1000000,
                 tags_offset=0x100, page_size=2048, board="SRPRF18A001RU")
CONFIG_TEXT = """# Linux/arm 3.18.14 Kernel Configuration
CONFIG_ARM=y
CONFIG_BLK_DEV_INITRD=y
CONFIG_DEVTMPFS=y
CONFIG_PROC_FS=y
CONFIG_SYSFS=y
CONFIG_VT_CONSOLE=y
CONFIG_FRAMEBUFFER_CONSOLE=y
# CONFIG_ARM64 is not set
CONFIG_LOCALVERSION="-15008757"
"""


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_ap(path: Path, image: bytes, *, member="boot.img", md5=True, corrupt=False) -> Path:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in (("recovery.img", b"R" * 100), (member, image)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    data = buffer.getvalue()
    trailer = f"{hashlib.md5(data).hexdigest()}  {path.name}\n".encode() if md5 else b""
    if corrupt:
        data = data[:700] + bytes([data[700] ^ 0xFF]) + data[701:]
    return write(path, data + trailer)


class BootUnpackTests(unittest.TestCase):
    def test_unpack_roundtrip_and_derived_offsets(self):
        image = android_bootimg.pack(b"kernel", b"ramdisk", b"dt", cmdline="a=b", **BOOT_ARGS)
        parts = android_bootimg.unpack(image)
        self.assertEqual((parts["kernel"], parts["ramdisk"], parts["dt"], parts["second"]), (b"kernel", b"ramdisk", b"dt", b""))
        derived = parts["meta"]["derived_offsets"]
        self.assertEqual((derived["base"], derived["ramdisk_offset"], derived["tags_offset"]), ("0x10000000", "0x1000000", "0x100"))

    def test_cli_unpack_writes_parts_and_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = write(Path(tmp) / "boot.img", android_bootimg.pack(b"k", b"r", b"d", **BOOT_ARGS))
            with mock.patch("sys.argv", ["x", "unpack", str(image), "--out", str(Path(tmp) / "out")]):
                self.assertEqual(android_bootimg.main(), 0)
            self.assertEqual((Path(tmp) / "out" / "kernel").read_bytes(), b"k")
            self.assertEqual(json.loads((Path(tmp) / "out" / "header.json").read_text())["page_size"], 2048)


class StockBootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.image = android_bootimg.pack(b"stock-kernel", b"stock-ramdisk", b"stock-dt",
                                          cmdline="console=ttySAC2,115200 androidboot.hardware=samsungexynos7570",
                                          samsung_trailer=True, **BOOT_ARGS)

    def test_extracts_and_describes_boot_img_with_verified_md5(self):
        ap = make_ap(self.tmp / "AP_TEST.tar.md5", self.image)
        report = extract_stock_boot.describe(ap, self.tmp / "stock")
        self.assertTrue(report["source"]["md5_verified"])
        self.assertEqual(report["boot_img"]["sha256"], hashlib.sha256(self.image).hexdigest())
        self.assertIn("androidboot.hardware", report["header"]["cmdline"])
        self.assertTrue(report["header"]["samsung_trailer"])
        self.assertEqual((self.tmp / "stock" / "kernel").read_bytes(), b"stock-kernel")

    def test_corrupt_download_is_refused(self):
        ap = make_ap(self.tmp / "AP_BAD.tar.md5", self.image, corrupt=True)
        with self.assertRaisesRegex(extract_stock_boot.StockBootError, "MD5"):
            extract_stock_boot.describe(ap)

    def test_plain_tar_without_md5_is_reported_as_unverified(self):
        ap = make_ap(self.tmp / "AP.tar", self.image, md5=False)
        report = extract_stock_boot.describe(ap)
        self.assertFalse(report["source"]["md5_line_present"])

    def test_archive_without_boot_and_non_tar_are_errors(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            info = tarfile.TarInfo("system.img")
            archive.addfile(info, io.BytesIO(b""))
        with self.assertRaises(extract_stock_boot.StockBootError):
            extract_stock_boot.describe(write(self.tmp / "x.tar", buffer.getvalue()))
        with self.assertRaises(extract_stock_boot.StockBootError):
            extract_stock_boot.describe(write(self.tmp / "y.tar", b"not a tar" * 100))

    def test_lz4_member_needs_the_lz4_package(self):
        ap = make_ap(self.tmp / "AP_LZ4.tar", self.image, member="boot.img.lz4", md5=False)
        with mock.patch.dict(sys.modules, {"lz4": None, "lz4.frame": None}):
            with self.assertRaisesRegex(extract_stock_boot.StockBootError, "lz4"):
                extract_stock_boot.describe(ap)

    @unittest.skipUnless(__import__("importlib").util.find_spec("lz4"), "lz4 not installed")
    def test_lz4_member_roundtrip(self):
        import lz4.frame
        ap = make_ap(self.tmp / "AP_LZ4.tar", lz4.frame.compress(self.image), member="boot.img.lz4", md5=False)
        self.assertEqual(extract_stock_boot.describe(ap)["boot_img"]["bytes"], len(self.image))

    def test_parameter_diff_and_apply(self):
        report = extract_stock_boot.describe(make_ap(self.tmp / "AP.tar.md5", self.image))
        candidate = json.loads(Path("devices/samsung-j2core/boot-parameters.json").read_text())
        diff = extract_stock_boot.boot_parameters_diff(candidate, report)
        self.assertEqual(set(diff), {"cmdline"})  # offsets agree; cmdline was unknown
        updated = extract_stock_boot.apply_boot_parameters(candidate, report)
        self.assertIn("androidboot.hardware", updated["cmdline"])
        self.assertIn(report["boot_img"]["sha256"], updated["cmdline_status"])
        self.assertNotIn("kernel_image_format", updated)
        self.assertEqual(extract_stock_boot.boot_parameters_diff(updated, report), {})

    def test_cli_writes_report_and_updates_parameters_only_with_apply(self):
        ap = make_ap(self.tmp / "AP.tar.md5", self.image)
        params = write(self.tmp / "bp.json", Path("devices/samsung-j2core/boot-parameters.json").read_bytes())
        argv = ["--ap", str(ap), "--out", str(self.tmp / "s"), "--report", str(self.tmp / "r.json"),
                "--boot-parameters", str(params)]
        self.assertEqual(extract_stock_boot.main(argv), 0)
        self.assertIsNone(json.loads(params.read_text())["cmdline"])
        self.assertIn("cmdline", json.loads((self.tmp / "r.json").read_text())["differs_from_candidate_parameters"])
        self.assertEqual(extract_stock_boot.main(argv + ["--apply"]), 0)
        self.assertIn("androidboot", json.loads(params.read_text())["cmdline"])
        self.assertEqual(extract_stock_boot.main(["--ap", str(self.tmp / "missing.tar"), "--out", str(self.tmp)]), 1)


class ConfigGzTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def config(self, text=CONFIG_TEXT):
        return write(self.tmp / "config.gz", gzip.compress(text.encode(), mtime=0))

    def test_valid_config_is_summarized(self):
        report = verify_config_gz.analyze(self.config())
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["header_kernel_version"], "3.18.14")
        self.assertEqual(report["key_options"]["ARM"], "y")
        self.assertEqual(report["key_options"]["ARM64"], "n")
        self.assertEqual(report["key_options"]["FB"], "absent")
        self.assertEqual(report["console_options_enabled"], ["VT_CONSOLE", "FRAMEBUFFER_CONSOLE"])

    def test_arm64_kernel_contradicts_the_armv7_decision(self):
        report = verify_config_gz.analyze(self.config(CONFIG_TEXT.replace("CONFIG_ARM=y", "# CONFIG_ARM is not set")
                                                      .replace("# CONFIG_ARM64 is not set", "CONFIG_ARM64=y")))
        self.assertTrue(any("ARM64" in e for e in report["errors"]))

    def test_non_arm_config_and_missing_essentials_are_flagged(self):
        report = verify_config_gz.analyze(self.config("# Linux/x86 6.1 Kernel Configuration\nCONFIG_X86=y\n"))
        self.assertTrue(report["errors"])
        self.assertTrue(any("INITRD" in w for w in report["warnings"]))
        self.assertTrue(any("no kernel console" in w for w in report["warnings"]))

    def test_crlf_mangled_capture_is_detected(self):
        noisy = "\n".join(f"CONFIG_X{i}={hashlib.md5(str(i).encode()).hexdigest()}" for i in range(600))
        good = gzip.compress((noisy + "\n" + CONFIG_TEXT).encode(), mtime=0)
        self.assertIn(b"\n", good)  # real config.gz files always contain 0x0a bytes
        mangled = good.replace(b"\n", b"\r\n")
        self.assertNotEqual(good, mangled)
        path = write(self.tmp / "bad.gz", mangled)
        with self.assertRaisesRegex(verify_config_gz.ConfigGzError, "CRLF|corrupt"):
            verify_config_gz.read_config(path)

    def test_truncated_text_and_empty_inputs(self):
        good = gzip.compress(CONFIG_TEXT.encode() * 50, mtime=0)
        for name, data in (("trunc.gz", good[:-8]), ("text.gz", b"CONFIG_ARM=y\n"), ("empty.gz", b"")):
            with self.assertRaises(verify_config_gz.ConfigGzError, msg=name):
                verify_config_gz.read_config(write(self.tmp / name, data))

    def test_profile_mismatch_and_cli(self):
        report = verify_config_gz.analyze(self.config())
        self.assertEqual(verify_config_gz.check_against_profile(report, {"kernel": {"version": "3.18.14-15008757"}}), [])
        self.assertTrue(verify_config_gz.check_against_profile(report, {"kernel": {"version": "4.4.1"}}))
        out = self.tmp / "report.json"
        self.assertEqual(verify_config_gz.main([str(self.config()), "--report", str(out)]), 0)
        self.assertEqual(json.loads(out.read_text())["header_kernel_version"], "3.18.14")
        self.assertEqual(verify_config_gz.main([str(write(self.tmp / "z.gz", b"junk"))]), 1)
        wrong = write(self.tmp / "p.json", json.dumps({"kernel": {"version": "9.9.9"}}).encode())
        self.assertEqual(verify_config_gz.main([str(self.config()), "--profile", str(wrong)]), 1)

    def test_committed_config_if_present_is_valid(self):
        path = Path("devices/samsung-j2core/evidence/j2core-config.gz")
        if not path.exists():
            self.skipTest("config.gz not collected yet")
        self.assertEqual(verify_config_gz.analyze(path)["errors"], [])


class CollectorTests(unittest.TestCase):
    def fake(self, devices="List of devices attached\nABC123\tdevice\n", denied=("cmdline",)):
        calls = []

        def runner(command, capture_output=True, timeout=None):
            calls.append(command)
            tail = command[1:]
            if tail == ["devices"]:
                out = devices.encode()
            elif tail[-1:] == ["version"] and "shell" not in tail:
                out = b"Android Debug Bridge version 1.0.41"
            elif tail[-3:] == ["exec-out", "cat", "/proc/config.gz"]:
                out = gzip.compress(CONFIG_TEXT.encode(), mtime=0)
            elif tail[-2:] == ["cat", "/proc/cmdline"] and "cmdline" in denied:
                return SimpleNamespace(stdout=b"", stderr=b"cat: /proc/cmdline: Permission denied", returncode=1)
            else:
                out = b"ok\n"
            return SimpleNamespace(stdout=out, stderr=b"", returncode=0)
        return runner, calls

    def test_allowlist_is_read_only(self):
        collect_device_evidence.assert_read_only()
        for name, (arguments, _suffix) in collect_device_evidence.COMMANDS.items():
            self.assertIn(arguments[0], {"shell", "exec-out"}, name)
            self.assertIn(arguments[1], collect_device_evidence.READ_ONLY_PROGRAMS, name)

    def test_tampered_allowlist_is_rejected(self):
        for bad in (["shell", "rm", "-rf", "/data"], ["shell", "cat", "/proc/x;reboot"], ["shell", "dumpsys", "package"],
                    ["push", "a", "b"], ["shell", "dd", "if=/dev/zero"]):
            with mock.patch.dict(collect_device_evidence.COMMANDS, {"evil": (bad, ".txt")}):
                with self.assertRaises(collect_device_evidence.CollectionError, msg=bad):
                    collect_device_evidence.assert_read_only()

    def test_collector_source_contains_no_write_verbs(self):
        source = Path("tooling/collect_device_evidence.py").read_text()
        commands = "\n".join(str(arguments) for arguments, _ in collect_device_evidence.COMMANDS.values())
        for verb in ("push", "pull", "install", "reboot", "flash", "setprop", "remount", "sideload", "'rm'", "'dd'", "'su'"):
            self.assertNotIn(verb, commands, verb)
        self.assertNotIn("subprocess.run(command, shell=True", source)

    def test_collects_everything_and_verifies_config(self):
        runner, calls = self.fake()
        with tempfile.TemporaryDirectory() as tmp:
            manifest = collect_device_evidence.collect(Path(tmp) / "cap", runner=runner, timestamp="2026-10-13T00:00:00+00:00")
            self.assertEqual(len(manifest["commands"]), len(collect_device_evidence.COMMANDS))
            self.assertTrue(manifest["config_gz_verification"]["ok"])
            self.assertTrue(manifest["commands"]["cmdline"]["permission_denied"])
            self.assertFalse(manifest["commands"]["uname"]["permission_denied"])
            self.assertEqual(gzip.decompress((Path(tmp) / "cap" / "config_gz.gz").read_bytes()).decode(), CONFIG_TEXT)
            self.assertTrue((Path(tmp) / "cap" / "manifest.json").exists())
        issued = [" ".join(call[1:]) for call in calls]
        self.assertTrue(any("-s ABC123 exec-out cat /proc/config.gz" in c for c in issued))
        self.assertFalse(any(re.search(r"\b(push|pull|install|reboot|flash)\b", c) for c in issued))

    def test_device_selection_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c"
            for devices in ("List of devices attached\n", "List of devices attached\nA\tdevice\nB\tdevice\n",
                            "List of devices attached\nA\tunauthorized\n"):
                runner, _ = self.fake(devices)
                with self.assertRaises(collect_device_evidence.CollectionError, msg=devices):
                    collect_device_evidence.collect(out, runner=runner)
            runner, _ = self.fake("List of devices attached\nA\tdevice\nB\tdevice\n")
            self.assertTrue(collect_device_evidence.collect(out, runner=runner, serial="B")["commands"])
            with self.assertRaises(collect_device_evidence.CollectionError):
                collect_device_evidence.collect(out, runner=runner, serial="Z")

    def test_corrupt_config_is_reported_not_hidden(self):
        runner, _ = self.fake()

        def mangling(command, capture_output=True, timeout=None):
            result = runner(command, capture_output, timeout)
            if command[-3:] == ["exec-out", "cat", "/proc/config.gz"]:
                result.stdout = result.stdout.replace(b"\n", b"\r\n") + b"\r\n"
            return result
        with tempfile.TemporaryDirectory() as tmp:
            manifest = collect_device_evidence.collect(Path(tmp) / "c", runner=mangling)
        self.assertFalse(manifest["config_gz_verification"]["ok"])

    def test_cli_reports_missing_adb(self):
        self.assertEqual(collect_device_evidence.main(["--adb", "/definitely/not/adb", "--out", tempfile.gettempdir() + "/x"]), 1)

    def test_cli_success_path_with_injected_runner(self):
        runner, _ = self.fake(denied=())
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(collect_device_evidence.subprocess, "run", runner):
            self.assertEqual(collect_device_evidence.main(["--out", str(Path(tmp) / "c")]), 0)


def kernel_tar(version=("3", "18", "14")) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in (("linux/Makefile", f"VERSION = {version[0]}\nPATCHLEVEL = {version[1]}\nSUBLEVEL = {version[2]}\nEXTRAVERSION =\n"),
                           ("linux/arch/arm/configs/exynos7570-j2corelte_defconfig", "CONFIG_ARM=y\n"),
                           ("linux/arch/arm/configs/other_defconfig", "x\n"),
                           ("linux/arch/arm/boot/dts/exynos7570-j2corelte.dts", "/dts-v1/;\n"),
                           ("linux/drivers/Makefile", "obj-y += x.o\n")):
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class KernelSourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def zip_with(self, version=("3", "18", "14")) -> Path:
        path = self.tmp / "SM-J260M_SWA_Opensource.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Kernel.tar.gz", kernel_tar(version))
            archive.writestr("Platform.tar.gz", b"ignored")
        return path

    def test_samsung_zip_with_nested_kernel_is_analyzed(self):
        report = verify_kernel_source.analyze(self.zip_with(), "3.18.14")
        self.assertTrue(report["version_matches"])
        self.assertEqual(report["nested_archive"], "Kernel.tar.gz")
        self.assertEqual(report["defconfigs"], ["linux/arch/arm/configs/exynos7570-j2corelte_defconfig"])
        self.assertEqual(report["device_trees"], ["linux/arch/arm/boot/dts/exynos7570-j2corelte.dts"])
        self.assertEqual(report["arch_dirs"], ["arm"])
        self.assertFalse(report["approved_input"])
        self.assertEqual(report["kernel_makefile"], "linux/Makefile")

    def test_plain_tarball_and_version_mismatch(self):
        path = write(self.tmp / "kernel.tar.gz", kernel_tar(("4", "4", "1")))
        report = verify_kernel_source.analyze(path, "3.18.14")
        self.assertFalse(report["version_matches"])
        self.assertEqual(verify_kernel_source.main([str(path)]), 1)

    def test_bad_archives_are_errors(self):
        for data in (b"junk", b""):
            with self.assertRaises(verify_kernel_source.SourceError):
                verify_kernel_source.analyze(write(self.tmp / "bad.tar.gz", data), "3.18.14")
        empty_zip = self.tmp / "e.zip"
        with zipfile.ZipFile(empty_zip, "w") as archive:
            archive.writestr("readme.txt", "x")
        with self.assertRaises(verify_kernel_source.SourceError):
            verify_kernel_source.analyze(empty_zip, "3.18.14")
        no_makefile = io.BytesIO()
        with tarfile.open(fileobj=no_makefile, mode="w:gz") as archive:
            info = tarfile.TarInfo("a.txt")
            archive.addfile(info, io.BytesIO(b""))
        with self.assertRaises(verify_kernel_source.SourceError):
            verify_kernel_source.analyze(write(self.tmp / "n.tar.gz", no_makefile.getvalue()), "3.18.14")

    def test_lock_update_never_approves_the_source(self):
        lock = write(self.tmp / "lock.json", json.dumps({"kernel": {"approved_input": True, "status": "x"}}).encode())
        report = verify_kernel_source.analyze(self.zip_with(), "3.18.14")
        data = verify_kernel_source.update_lock(lock, report)
        self.assertFalse(data["kernel"]["approved_input"])
        self.assertIn("not approved", data["kernel"]["status"])
        self.assertEqual(data["kernel"]["source_archive"]["version"], "3.18.14")
        bad = verify_kernel_source.analyze(write(self.tmp / "o.tar.gz", kernel_tar(("4", "9", "9"))), "3.18.14")
        self.assertIn("DOES NOT match", verify_kernel_source.update_lock(lock, bad)["kernel"]["status"])

    def test_cli_success(self):
        self.assertEqual(verify_kernel_source.main([str(self.zip_with())]), 0)
        self.assertEqual(verify_kernel_source.main([str(self.tmp / "missing.zip")]), 1)


def elf(machine=40, flags=0x05000400, klass=1) -> bytes:
    header = bytearray(64)
    header[:4], header[4], header[5] = b"\x7fELF", klass, 1
    header[18:20] = machine.to_bytes(2, "little")
    header[36:40] = flags.to_bytes(4, "little")
    return bytes(header)


def mini_rootfs(path: Path, *, busybox=None, release="3.24.2\n", extra=()) -> Path:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        def add(name, data=b"", type=tarfile.REGTYPE, mode=0o644, linkname=""):
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.linkname, info.size = type, mode, linkname, len(data)
            info.mtime, info.uid, info.gid = 1_700_000_000 + len(name), 0, 42
            archive.addfile(info, io.BytesIO(data) if type == tarfile.REGTYPE else None)
        add(".", type=tarfile.DIRTYPE, mode=0o755)
        add("./bin", type=tarfile.DIRTYPE, mode=0o755)
        add("./bin/busybox", busybox if busybox is not None else elf(), mode=0o755)
        add("./etc", type=tarfile.DIRTYPE, mode=0o755)
        add("./etc/alpine-release", release.encode())
        add("./sbin", type=tarfile.DIRTYPE, mode=0o755)
        add("./sbin/init", type=tarfile.SYMTYPE, mode=0o777, linkname="/bin/busybox")
        add("./tmp", type=tarfile.DIRTYPE, mode=0o1777)
        for name, data in extra:
            add(name, data)
    return write(path, buffer.getvalue())


class AlpineRootfsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = Path(build_alpine_rootfs.ROOT)
        self.manifest = self.root / "images" / "samsung-j2core.json"

    def lock_for(self, tarball: Path, **changes):
        lock = json.loads(build_alpine_rootfs.LOCK.read_text())
        lock["sha256"] = hashlib.sha256(tarball.read_bytes()).hexdigest()
        lock.update(changes)
        return lock

    def build(self, tarball, **changes):
        return build_alpine_rootfs.build_rootfs(tarball, self.lock_for(tarball, **changes), self.root, self.manifest)

    def test_committed_lock_pins_the_verified_minirootfs(self):
        lock = json.loads(build_alpine_rootfs.LOCK.read_text())
        self.assertEqual((lock["alpine_version"], lock["architecture"]), ("3.24.2", "armv7"))
        self.assertRegex(lock["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(lock["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertIn("PENDING", lock["independent_verification"])

    def test_overlay_is_added_on_top_of_alpine_with_exact_metadata(self):
        blob = self.build(mini_rootfs(self.tmp / "mini.tar.gz"))
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            members = {m.name: m for m in archive.getmembers()}
            names = [m.name for m in archive.getmembers()]
            self.assertEqual(names, sorted(names))
            self.assertEqual(members["bin/busybox"].mode, 0o755)
            self.assertEqual(members["tmp"].mode, 0o1777)
            self.assertTrue(members["sbin/init"].issym())
            self.assertEqual(members["etc/alpine-release"].gid, 42)  # Alpine ownership preserved
            for name in ("etc/init.d/powerd", "usr/libexec/ereader/powerd"):
                self.assertEqual(members[name].mode, 0o755)
            self.assertTrue(members["etc/runlevels/default/powerd"].issym())
            for directory in ("usr", "usr/lib", "usr/lib/ereader", "etc/runlevels", "etc/ereader"):
                self.assertTrue(members[directory].isdir(), directory)
            self.assertEqual({m.mtime for m in members.values()}, {0})
            provenance = json.loads(archive.extractfile("etc/ereader/rootfs-provenance.json").read())
            self.assertEqual(provenance["userspace_elf"]["abi"], "eabi5-hard-float")
            self.assertIn("stage 2 pending", provenance["packages_installed"])

    def test_output_is_deterministic_regardless_of_input_mtimes(self):
        first = self.build(mini_rootfs(self.tmp / "a.tar.gz"))
        second = self.build(mini_rootfs(self.tmp / "b.tar.gz", extra=()))
        self.assertEqual(first, second)

    def test_checksum_mismatch_is_refused(self):
        tarball = mini_rootfs(self.tmp / "m.tar.gz")
        with self.assertRaisesRegex(build_alpine_rootfs.AlpineRootfsError, "sha256 mismatch"):
            self.build(tarball, sha256="0" * 64)

    def test_wrong_userspace_architecture_is_refused(self):
        for label, busybox in (("x86-64", elf(machine=62)), ("soft-float", elf(flags=0x05000200)),
                               ("64-bit", elf(klass=2)), ("not elf", b"#!/bin/sh" + bytes(60))):
            with self.assertRaises(build_alpine_rootfs.AlpineRootfsError, msg=label):
                self.build(mini_rootfs(self.tmp / f"{label}.tar.gz", busybox=busybox))

    def test_version_and_profile_mismatches_are_refused(self):
        tarball = mini_rootfs(self.tmp / "m.tar.gz", release="3.99.0\n")
        with self.assertRaisesRegex(build_alpine_rootfs.AlpineRootfsError, "lock pins"):
            self.build(tarball)
        with self.assertRaisesRegex(build_alpine_rootfs.AlpineRootfsError, "requires armv7"):
            self.build(mini_rootfs(self.tmp / "ok.tar.gz"), architecture="aarch64")

    def test_overlay_collisions_are_refused(self):
        tarball = mini_rootfs(self.tmp / "m.tar.gz", extra=(("./etc/init.d/powerd", b"theirs"),))
        with self.assertRaisesRegex(build_alpine_rootfs.AlpineRootfsError, "collides"):
            self.build(tarball)

    def test_missing_busybox_is_refused(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            info = tarfile.TarInfo("./etc/alpine-release")
            info.size = 7
            archive.addfile(info, io.BytesIO(b"3.24.2\n"))
        with self.assertRaises(build_alpine_rootfs.AlpineRootfsError):
            self.build(write(self.tmp / "nb.tar.gz", buffer.getvalue()))

    def test_fetch_downloads_the_pinned_url_and_verifies(self):
        tarball = mini_rootfs(self.tmp / "m.tar.gz")
        lock = self.lock_for(tarball)
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = tarball.read_bytes()
        with mock.patch.object(build_alpine_rootfs.urllib.request, "urlopen", return_value=response) as opener:
            path = build_alpine_rootfs.fetch(lock, self.tmp / "cache")
        self.assertIn(lock["source"]["commit"], opener.call_args[0][0])
        self.assertEqual(path.read_bytes(), tarball.read_bytes())
        response.__enter__.return_value.read.return_value = b"tampered"
        with mock.patch.object(build_alpine_rootfs.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(build_alpine_rootfs.AlpineRootfsError):
                build_alpine_rootfs.fetch(lock, self.tmp / "cache2")

    def test_cli(self):
        tarball = mini_rootfs(self.tmp / "m.tar.gz")
        lock = write(self.tmp / "lock.json", json.dumps(self.lock_for(tarball)).encode())
        out = self.tmp / "out" / "rootfs.tar"
        argv = ["--minirootfs", str(tarball), "--lock", str(lock), "--output", str(out)]
        self.assertEqual(build_alpine_rootfs.main(argv), 0)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        self.assertEqual(out.with_suffix(".tar.sha256").read_bytes(), f"{digest}  rootfs.tar\n".encode())
        self.assertEqual(build_alpine_rootfs.main(["--minirootfs", str(self.tmp / "none.tar.gz"), "--lock", str(lock),
                                                   "--output", str(out)]), 1)

    def test_package_lists_keep_unverified_items_out_of_the_install_list(self):
        installed = Path("images/alpine-rootfs.packages").read_text()
        self.assertNotIn("koreader", installed)
        self.assertIn("koreader", Path("images/alpine-rootfs.unverified").read_text())
        self.assertIn("python3", installed)
        self.assertIn("openrc", installed)


class TestArtifactTests(unittest.TestCase):
    def test_artifacts_are_synthetic_reproducible_and_never_claim_flashable(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = build_test_artifacts.build(Path(one))
            second = build_test_artifacts.build(Path(two))
            for a, b in zip(first, second):
                self.assertEqual(a.read_bytes(), b.read_bytes(), a.name)
            names = {p.name for p in first}
            self.assertIn("boot-synthetic-NOT-FLASHABLE.img", names)
            manifest = json.loads((Path(one) / "synthetic" / "manifest.json").read_text())
            self.assertFalse(manifest["flashable_claim"])
            image = (Path(one) / "synthetic" / "boot-synthetic-NOT-FLASHABLE.img").read_bytes()
            parts = android_bootimg.unpack(image, max_bytes=33554432)
            self.assertIn(b"SYNTHETIC", parts["kernel"])
            self.assertEqual(parts["meta"]["cmdline"], "SYNTHETIC-TEST-IMAGE")
            self.assertEqual((Path(one) / "samsung-j2core-development-rootfs.tar").read_bytes(),
                             build_image.build_tarball(build_image.ROOT, build_image.ROOT / "images" / "samsung-j2core.json"))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_test_artifacts.main(["--output", tmp]), 0)
            self.assertTrue((Path(tmp) / "synthetic" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
