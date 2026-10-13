"""Parse the raw read-only ADB transcript of the physical SM-J260M.

The transcript (a Word document produced from a PowerShell session) is the
ground truth; every derived JSON file is verified against it.  Standard
library only.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CAPTURE = Path(__file__).resolve().parents[1] / "devices" / "samsung-j2core" / "evidence" / "PS_C.docx"


def read_docx_text(path: Path = CAPTURE) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return "\n".join("".join(node.text or "" for node in paragraph.iter(_W + "t"))
                     for paragraph in root.iter(_W + "p"))


def parse_block_sizes(text: str) -> dict[str, int]:
    """/proc/partitions rows -> {device name: size in bytes}."""
    sizes: dict[str, int] = {}
    for match in re.finditer(r"^\s*\d+\s+\d+\s+(\d+)\s+(mmcblk0\w*|dm-\d+)\s*$", text, re.M):
        sizes[match.group(2)] = int(match.group(1)) * 1024
    return sizes


def parse_by_name(text: str) -> dict[str, str]:
    """`NAME -> /dev/block/mmcblk0pN` symlink rows -> {NAME: 'mmcblk0pN'}."""
    return {m.group(1): m.group(2)
            for m in re.finditer(r"\s(\S+) -> /dev/block/(mmcblk0p\d+)\s*$", text, re.M)}


def parse_properties(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"^\[([^\]]+)\]: \[([^\]]*)\]\s*$", text, re.M)}


def parse_uname(text: str) -> dict[str, str]:
    match = re.search(r"^Linux (\S+) (\S+) #.* (\S+)\s*$", text, re.M)
    if not match:
        raise ValueError("uname line not found in capture")
    return {"nodename": match.group(1), "release": match.group(2), "machine": match.group(3)}


def parse_controller(text: str) -> str:
    match = re.search(r"/dev/block/platform/([\w.]+)/by-name/", text)
    if not match:
        raise ValueError("storage controller path not found in capture")
    return match.group(1)


def load(path: Path = CAPTURE) -> dict:
    text = read_docx_text(path)
    return {"block_sizes": parse_block_sizes(text), "by_name": parse_by_name(text),
            "properties": parse_properties(text), "uname": parse_uname(text),
            "controller": parse_controller(text)}
