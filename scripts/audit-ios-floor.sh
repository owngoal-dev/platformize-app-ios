#!/usr/bin/env bash
# Prove that a built product can actually launch on the OS version it claims.
#
# A clean build against this year's SDK says nothing about an old deployment
# target: the linker believes the SDK's availability metadata, and where that
# metadata is wrong or absent the app dies in dyld before `main` on the old
# device, with no warning anywhere in the build.
#
# Usage: audit-ios-floor.sh <floor> <path> [<path> …]
#   <floor>  the oldest iOS you claim, e.g. 15.0
#   <path>   an .app bundle, a framework, or a Mach-O; bundles are walked
#
# Exit 0 when everything checks out, 65 when something cannot run on the floor.
# Findings are printed as `error:` (cannot launch) or `note:` (must be guarded
# in source; this script cannot see whether it is).

set -Eeuo pipefail

[[ $# -ge 2 ]] || { echo "usage: $0 <floor> <path> [<path> …]" >&2; exit 64; }

floor="$1"
shift
fail=0

# 15.0 -> 150000, for string-free comparison of two dotted versions.
version_key() {
    local IFS=.
    # shellcheck disable=SC2206
    local parts=($1 0 0)
    printf '%d' $(( ${parts[0]} * 10000 + ${parts[1]} * 100 + ${parts[2]} ))
}
floor_key="$(version_key "$floor")"

# Every Mach-O under a path: the payload and every embedded library of an
# .app / .appex / .framework, because each one is loaded by the same dyld.
# `file` is asked one path at a time on purpose — its aligned, multi-line
# output for a universal binary cannot be split back into paths.
binaries() {
    local path="$1" candidate
    while IFS= read -r -d '' candidate; do
        [[ "$(file -b "$candidate" 2>/dev/null)" == Mach-O* ]] && printf '%s\n' "$candidate"
    done < <(find "$path" -type f -print0 2>/dev/null)
}

# 1. Required libraries. Anything here that arrived after the floor is a launch
#    failure on the floor: dyld refuses to build the process.
#
#    The list is deliberately explicit rather than clever. Add a line when the
#    SDK adds an overlay; the point is that these have bitten a shipped build.
declare -a late_libraries=(
    "libswiftXPC.dylib:16.0"          # iOS 27 SDK overlay; killed Fila 0.1.6 on 15
    "libswiftObservation.dylib:17.0"
    "libswiftSpatial.dylib:17.0"
    "libswiftSynchronization.dylib:18.0"
    "libswiftRealityKit.dylib:18.0"
)

check_libraries() {
    local binary="$1" line library minimum
    while IFS= read -r line; do
        [[ "$line" == *", weak)"* ]] && continue
        for entry in "${late_libraries[@]}"; do
            library="${entry%%:*}"
            minimum="${entry##*:}"
            if [[ "$line" == *"/$library"* ]] \
                && (( $(version_key "$minimum") > floor_key )); then
                echo "error: $binary requires $library (iOS $minimum) but claims iOS $floor" >&2
                fail=1
            fi
        done
    done < <(otool -L "$binary" | tail -n +2)
}

# 2. The binary's own build version. An embedded framework with a higher minos
#    than the app is refused by dyld on the old device.
check_minos() {
    local binary="$1" minos
    minos="$(vtool -show-build "$binary" 2>/dev/null | awk '/minos/ { print $2; exit }')" || return 0
    [[ -n "$minos" ]] || return 0
    (( $(version_key "$minos") > floor_key )) || return 0
    # An app extension is allowed a higher floor of its own: an OS that predates
    # it simply never loads it, and the app still launches. Anything the app
    # itself loads is not allowed one.
    if [[ "$binary" == *.appex/* ]]; then
        echo "note: $binary is an extension built for iOS $minos; it will not load below that" >&2
        return 0
    fi
    echo "error: $binary is built for iOS $minos, above the claimed floor $floor" >&2
    fail=1
}

# 3. Weak symbols are null on an OS older than the one that introduced them.
#    Each has to be null-checked in source; this only says which they are.
check_weak_symbols() {
    local binary="$1" symbols
    symbols="$(nm -m "$binary" 2>/dev/null | grep 'weak external' | grep -v 'FORCE_LOAD' || true)"
    if [[ -n "$symbols" ]]; then
        echo "note: $binary weak-imports symbols that are NULL below their own floor:" >&2
        echo "$symbols" | sed 's/^/    /' >&2
    fi
}

for path in "$@"; do
    [[ -e "$path" ]] || { echo "error: no such path: $path" >&2; exit 66; }
    while IFS= read -r binary; do
        [[ -n "$binary" ]] || continue
        check_libraries "$binary"
        check_minos "$binary"
        check_weak_symbols "$binary"
    done < <(binaries "$path")
done

# 4. SF Symbols. Not a link error and not a crash: `UIImage(systemName:)`
#    returns nil and the control draws nothing. Source-level, so it runs only
#    when a source root is given as the last argument's sibling — call
#    check-symbol-availability from `make check` instead; see SKILL.md.

if (( fail )); then
    echo "error: this product cannot launch on iOS $floor" >&2
    exit 65
fi

echo "ok: every required library, build version and framework fits iOS $floor"
