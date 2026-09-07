#!/usr/bin/env python3
"""Fail when a source tree names an SF Symbol newer than the deployment target.

This one never crashes and never warns, which is why it ships: on an OS older
than the symbol, `UIImage(systemName:)` returns nil and the control draws with
no icon. Xcode's completion offers this year's symbols with no regard for the
deployment target.

The availability table ships on every Mac inside CoreGlyphs: `symbols` maps a
name to a release year, `year_to_release` maps that year to an iOS version.
Without it — a Linux CI runner — this exits 0 rather than pretending.

Usage: check-symbol-availability.py <floor> <source root> [<source root> …]
       check-symbol-availability.py 15.0 Fila Packages/FilaKit/Sources
"""

import plistlib
import re
import subprocess
import sys
from pathlib import Path

TABLE = Path(
    "/System/Library/CoreServices/CoreGlyphs.bundle/Contents/Resources/name_availability.plist"
)
USES = re.compile(r'system(?:Name|Image|ImageName|SymbolName)\s*:\s*"([^"]+)"')


def version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    floor = version_key(sys.argv[1])
    roots = sys.argv[2:]

    try:
        table = plistlib.loads(TABLE.read_bytes())
    except OSError:
        print(f"note: {TABLE.name} is not available here; skipping", file=sys.stderr)
        return 0

    symbols, releases = table["symbols"], table["year_to_release"]
    found = subprocess.run(
        ["grep", "-rn", "--include=*.swift", "-E",
         "system(Name|Image|ImageName|SymbolName)", *roots],
        capture_output=True, text=True,
    ).stdout

    failures = 0
    for line in found.splitlines():
        location = ":".join(line.split(":", 2)[:2])
        for name in USES.findall(line):
            release = releases.get(symbols.get(name, ""), {}).get("iOS")
            if release and version_key(release) > floor:
                print(f"error: {location}: {name} needs iOS {release}", file=sys.stderr)
                failures += 1

    if failures:
        print(f"error: {failures} SF Symbol(s) draw nothing on iOS {sys.argv[1]}", file=sys.stderr)
        return 65
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
