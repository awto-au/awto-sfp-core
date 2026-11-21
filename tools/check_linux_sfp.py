#!/usr/bin/env python3
"""check_linux_sfp — drift check of the core's quirk/fixup tables against a pinned Linux drivers/net/phy/sfp.c.

- Parses Linux `sfp_quirks[]` (SFP_QUIRK, _S, _F, _F_PREFIX) and the core's `quirks[]` / `fixups[]` in src/sfp_core.c.
- Linux entry with a `.support` hook (2500BASE-X / UBNT) must be in core `quirks[]`; one with fs_10gt / rollball_cc must be
  in core `fixups[]`; the Cisco space-padded fixup is covered by `sfp_unpad` (content-based).
- Every other Linux entry must be listed in tools/linux_quirks_ignored.txt (`vendor|part|reason`): it does not change the
  decode this core feeds, or it needs hardware the core does not model. A core entry missing from Linux fails too.
- Exit 0 = in sync, 1 = drift. Usage: tools/check_linux_sfp.py PATH/TO/sfp.c [--kernel-label 7.4-rc3]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORT_HOOKS = {"sfp_quirk_2500basex": "2500", "sfp_quirk_oem_2_5g": "2500", "sfp_quirk_ubnt_uf_instant": "ubnt"}
FIXUP_HOOKS = {"sfp_fixup_fs_10gt": "FS_10GT", "sfp_fixup_rollball_cc": "ROLLBALL_CC"}
COVERED_BY_CODE = {"sfp_fixup_space_padded": "sfp_unpad"}


def linux_entries(text: str) -> list[tuple[str, str, str, str]]:
    body = text[text.index("sfp_quirks[] = {"):]
    body = body[:body.index("\n};")]
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    out = []
    for m in re.finditer(r"SFP_QUIRK(_S|_F_PREFIX|_F)?\(", body):
        i, depth, args, cur, q = m.end(), 1, [], "", False
        while depth:
            c = body[i]
            if c == '"':
                q = not q
            if not q and c == "(":
                depth += 1
            elif not q and c == ")":
                depth -= 1
                if not depth:
                    break
            if not q and c == "," and depth == 1:
                args.append(cur.strip())
                cur = ""
            else:
                cur += c
            i += 1
        args.append(cur.strip())
        args = [a.strip('"') if a.startswith('"') else " ".join(a.split()) for a in args]
        kind = m.group(1) or ""
        v, p = args[0], args[1]
        if kind == "":
            sup, fix = args[2], args[3]
        elif kind == "_S":
            sup, fix = args[2], "NULL"
        else:
            sup, fix = "NULL", args[2]
        out.append((v, p, sup, fix))
    return out


def core_tables(text: str) -> tuple[set[tuple[str, str]], dict[tuple[str, str], str]]:
    q = text[text.index("quirks[] = {"):]
    q = q[:q.index("};")]
    quirks = {(m.group(1), m.group(2)) for m in re.finditer(r'\{ "([^"]+)", "([^"]+)",', q)}
    f = text[text.index("fixups[] = {"):]
    f = f[:f.index("};")]
    fixups = {(m.group(1), m.group(2)): m.group(3) for m in re.finditer(r'\{ "([^"]+)", "([^"]+)", (\w+) \}', f)}
    return quirks, fixups


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sfp_c = Path(sys.argv[1])
    ignored = {}
    ign = ROOT / "tools/linux_quirks_ignored.txt"
    if ign.exists():
        for ln in ign.read_text().splitlines():
            if ln.strip() and not ln.startswith("#"):
                v, p, why = ln.split("|", 2)
                ignored[(v, p)] = why
    lin = linux_entries(sfp_c.read_text())
    quirks, fixups = core_tables((ROOT / "src/sfp_core.c").read_text())
    bad, seen = [], set()
    for v, p, sup, fix in lin:
        key = (v, p)
        seen.add(key)
        if sup in SUPPORT_HOOKS:
            if key not in quirks:
                bad.append(f"MISSING in core quirks[]: {v} {p} ({sup})")
        elif fix in FIXUP_HOOKS:
            if fixups.get(key) != FIXUP_HOOKS[fix]:
                bad.append(f"MISSING/WRONG in core fixups[]: {v} {p} ({fix}, core has {fixups.get(key)})")
        elif fix in COVERED_BY_CODE:
            pass
        elif key not in ignored:
            bad.append(f"UNLISTED Linux quirk (add to the core or to tools/linux_quirks_ignored.txt): {v} {p} ({sup}/{fix})")
    for key in sorted(quirks | set(fixups)):
        if key not in seen:
            bad.append(f"IN CORE, NOT IN LINUX: {key[0]} {key[1]}")
    for key in sorted(set(ignored) - seen):
        bad.append(f"STALE ignore entry (not in Linux any more): {key[0]} {key[1]}")
    print(f"Linux {sfp_c}: {len(lin)} quirks; core: {len(quirks)} support quirks, {len(fixups)} fixups, {len(ignored)} ignored")
    for b in bad:
        print("DRIFT:", b)
    print("OK: in sync" if not bad else f"{len(bad)} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
