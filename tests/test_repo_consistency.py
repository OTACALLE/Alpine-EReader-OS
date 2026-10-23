"""Guards against the documentation/metadata drift found in the first audit."""
import json
import re
import unittest
from pathlib import Path
import subprocess

SKIP_DIRS = {".git", "dist", "__pycache__"}
BINARY_SUFFIXES = {".docx", ".gz", ".img", ".tar", ".cpio", ".pyc"}


def text_files():
    tracked = subprocess.run(["git", "ls-files", "-z"], check=True, stdout=subprocess.PIPE).stdout.split(b"\\0")
    for raw in tracked:
        if raw:
            path = Path(raw.decode("utf-8"))
            if path.is_file() and not (set(path.parts) & SKIP_DIRS) and path.suffix not in BINARY_SUFFIXES:
                yield path


class RepositoryConsistencyTests(unittest.TestCase):
    def test_license_file_and_metadata_agree_on_apache_2(self):
        self.assertIn("Apache License", Path("LICENSE").read_text(encoding="utf-8")[:200])
        self.assertIn('"Apache-2.0"', Path("pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(Path("packages/ereader-core/package.json").read_text(encoding="utf-8"))["license"], "Apache-2.0")
        self.assertTrue(Path("docs/architecture/adr/0003-project-license-apache-2.md").exists())
        self.assertRegex(Path("ARCHITECTURE.md").read_text(encoding="utf-8"), r"Apache-2\.0")

    def test_no_text_file_uses_crlf(self):
        offenders = [str(p) for p in text_files() if b"\r\n" in p.read_bytes()]
        self.assertEqual(offenders, [])
        self.assertRegex(Path(".gitattributes").read_text(encoding="utf-8"), r"\*\s+text=auto eol=lf")

    def test_phase_naming_is_single_and_honest(self):
        readme, agents = Path("README.md").read_text(encoding="utf-8"), Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Current phase: Phase 1", readme)
        self.assertNotIn("intentionally contains no implementation code", readme)
        self.assertIn("None is met", Path("docs/implementation-status.md").read_text(encoding="utf-8"))
        self.assertIn("flash_guard", agents)
        for path in Path("docs").rglob("*.md"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"samsung-j2core-phase[23]", str(path))
        self.assertFalse(list(Path("docs").rglob("*phase2*")) + list(Path("docs").rglob("*phase3*")))

    def test_architecture_statements_say_arm64_kernel_with_32bit_userspace(self):
        evidence = Path("docs/devices/samsung-j2core-boot-evidence.md").read_text(encoding="utf-8")
        adr = Path("docs/architecture/adr/0002-j2core-first-userspace-armv7.md").read_text(encoding="utf-8")
        for text in (evidence, adr):
            self.assertIn("arm64", text)
            self.assertIn("CONFIG_COMPAT", text)
        self.assertNotRegex(evidence, r"(?i)AArch32 (kernel|execution mode)")  # the ADR may quote the retracted claim
        self.assertIn("wrongly inferred", adr)
        for path in Path(".").rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json"} and not (set(path.parts) & SKIP_DIRS) and path.name != "ARCHITECTURE.md":
                self.assertNotIn('"kernel_machine"', path.read_text(encoding="utf-8"), str(path))

    def test_unvalidated_tier_is_reflected_everywhere(self):
        self.assertIn("UNVALIDATED", Path("devices/samsung-j2core/README.md").read_text(encoding="utf-8"))
        for path in Path("devices").rglob("*.md"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\byellow\b", str(path))

    def test_raw_evidence_lives_in_the_device_folder_not_the_root(self):
        self.assertFalse(Path("PS C.docx").exists())
        self.assertTrue(Path("devices/samsung-j2core/evidence/PS_C.docx").exists())

    def test_every_documented_file_reference_exists(self):
        missing = []
        for path in Path("docs").rglob("*.md"):
            for ref in re.findall(r"`((?:tooling|core|shell|reader_integration|devices|images|packages)/[\w./-]+)`", path.read_text(encoding="utf-8")):
                if not Path(ref).exists() and "<" not in ref:
                    missing.append(f"{path}: {ref}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
