#!/bin/sh
# Refuse to build until the repo's one-time checklist is fully ticked.
#
# A new app repo starts from template/CHECKLIST.md. Every box is a decision
# that is cheap before the first line of code and expensive after the first
# release, so `make check` runs this first and nothing builds until it passes.
#
# Usage: check-checklist.sh [<checklist>]      default: CHECKLIST.md
#
# Exit 0 when every item is `- [x]`; 65 when any `- [ ]` remains or the file
# has no items at all; 66 when the file is missing. An item is a line that
# starts (after indentation) with `- [ ]`, `- [x]` or `- [X]`.

set -eu

file="${1:-CHECKLIST.md}"

if [ ! -f "$file" ]; then
    echo "error: $file is missing; copy it from the platformize-app-ios template and work through it" >&2
    exit 66
fi

total="$(grep -cE '^[[:space:]]*- \[[ xX]\]' "$file" || true)"
if [ "$total" -eq 0 ]; then
    echo "error: $file has no checklist items; an emptied checklist is not a finished one" >&2
    exit 65
fi

open="$(grep -nE '^[[:space:]]*- \[ \]' "$file" || true)"
if [ -n "$open" ]; then
    count="$(printf '%s\n' "$open" | wc -l | tr -d ' ')"
    echo "error: $file has $count of $total items unticked; no code is written until all are:" >&2
    printf '%s\n' "$open" | sed "s|^|    $file:|" >&2
    exit 65
fi

echo "ok: all $total items in $file are ticked"
