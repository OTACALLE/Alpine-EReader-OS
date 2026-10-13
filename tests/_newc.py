"""Tiny newc cpio reader used to verify what build_initramfs wrote."""


def parse_newc(blob: bytes) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    position = 0
    while True:
        if blob[position:position + 6] != b"070701":
            raise AssertionError(f"bad newc magic at {position}")
        values = [int(blob[position + 6 + 8 * i:position + 14 + 8 * i], 16) for i in range(13)]
        ino, mode, uid, gid, nlink, mtime, size, _dmaj, _dmin, rmaj, rmin, namesize, _check = values
        position += 110
        name = blob[position:position + namesize - 1].decode()
        position += namesize
        position += (-position) % 4
        data = blob[position:position + size]
        position += size
        position += (-position) % 4
        if name == "TRAILER!!!":
            return entries
        entries[name] = {"ino": ino, "mode": mode, "uid": uid, "gid": gid, "nlink": nlink,
                         "mtime": mtime, "data": data, "rdev": (rmaj, rmin)}
