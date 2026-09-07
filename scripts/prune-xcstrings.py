#!/usr/bin/env python3
"""Tidy a string catalog after Xcode has marked entries stale.

Xcode's extractor only sees `String.LocalizationValue` literals handed to
functions of the same module. A literal handed straight to a package's API
(`AlertProgressIndicatorViewController(title: "Please Wait")`) still resolves
against the catalog at run time, but Xcode marks it stale and, while the
project sits open, deletes it together with its translations. This script
keeps those: a stale key whose quoted text still appears in a Swift file
becomes `manual`, which Xcode never touches; a stale key that appears nowhere
is removed.

Usage: prune-xcstrings.py <catalog> <source root> [<source root> ...]
       prune-xcstrings.py Fila/Resources/Localizable.xcstrings Fila Packages/FilaKit/Sources

The catalog is written back in Xcode's own layout (two-space indent, a space
before each colon), so the diff is only the entries that changed.
"""

import json
import os
import sys


def swift_sources(roots):
    for root in roots:
        for directory, _, files in os.walk(root):
            for name in files:
                if name.endswith(".swift"):
                    with open(os.path.join(directory, name), encoding="utf-8") as handle:
                        yield handle.read()


def main(argv):
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 64
    catalog_path, source_roots = argv[1], argv[2:]

    with open(catalog_path, encoding="utf-8") as handle:
        raw = handle.read()
    catalog = json.loads(raw)
    strings = catalog["strings"]

    sources = list(swift_sources(source_roots))

    def referenced(key):
        literal = '"' + key + '"'
        return any(literal in text for text in sources)

    kept, removed = [], []
    for key in list(strings):
        if strings[key].get("extractionState") != "stale":
            continue
        if referenced(key):
            strings[key]["extractionState"] = "manual"
            kept.append(key)
        else:
            del strings[key]
            removed.append(key)

    out = json.dumps(catalog, indent=2, separators=(",", " : "), ensure_ascii=False)
    if raw.endswith("\n"):
        out += "\n"
    with open(catalog_path, "w", encoding="utf-8") as handle:
        handle.write(out)

    for key in kept:
        print(f"manual  {key}")
    for key in removed:
        print(f"removed {key}")
    print(f"{len(kept)} kept as manual, {len(removed)} removed, {len(strings)} entries left")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
