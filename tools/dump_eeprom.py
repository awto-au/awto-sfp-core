#!/usr/bin/env python3
"""dump_eeprom — save the SFP EEPROMs of every fitted cage of a Linux switch into eeprom/ (test corpus).

- Read-only: `ethtool -m <port> hex on raw off` over ssh (A0h 0-255, A2h 256-511 when the module has DDM).
- One file per module: eeprom/<VENDOR>_<PN>_<SN>.hex = the ethtool hex dump, plus a header comment line
  (`# host port vendor pn sn date`). Same module dumped twice overwrites the file.
- Modules and serials are published as read (device identifiers are not secrets).

Usage: python3 tools/dump_eeprom.py ROOT@HOST [PORT ...]   (default ports lan1..lan8)
Example: python3 tools/dump_eeprom.py root@192.168.25.48
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "eeprom"
SSH = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
       "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]


def ssh(host: str, cmd: str) -> str:
    r = subprocess.run([*SSH, host, cmd], capture_output=True, text=True, timeout=40)
    return r.stdout


def field(raw: bytes, a: int, b: int) -> str:
    return re.sub(r"[^A-Za-z0-9._+ -]", "?", raw[a:b].decode("latin-1")).strip()


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    host = sys.argv[1]
    ports = sys.argv[2:] or [f"lan{i}" for i in range(1, 9)]
    OUT.mkdir(exist_ok=True)
    for port in ports:
        txt = ssh(host, f"ethtool -m {port} hex on raw off 2>/dev/null")
        rows = re.findall(r"^0x([0-9a-f]{4}):\s+((?:[0-9a-f]{2} ?)+)", txt, re.M)
        if not rows:
            print(f"{port}: no module / unreadable")
            continue
        data = bytearray()
        for off, hexes in rows:
            off = int(off, 16)
            if len(data) < off:
                data.extend(b"\x00" * (off - len(data)))
            data[off:off + 16] = bytes.fromhex(hexes.replace(" ", ""))
        vendor, pn, sn, date = field(data, 20, 36), field(data, 40, 56), field(data, 68, 84), field(data, 84, 92)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{vendor}_{pn}_{sn}").strip("_")
        lines = [f"# {host} {port} vendor={vendor!r} pn={pn!r} sn={sn!r} date={date!r} bytes={len(data)}"]
        for i in range(0, len(data), 16):
            lines.append(f"0x{i:04x}: " + " ".join(f"{b:02x}" for b in data[i:i + 16]))
        (OUT / f"{name}.hex").write_text("\n".join(lines) + "\n")
        print(f"{port}: {name}.hex ({len(data)} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
