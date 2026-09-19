# @APP_NAME@ — Agent Notes

<!--
    The skeleton of an app repo's agent notes. Replace every placeholder, delete
    every section that is not true here, and add the ones this app needs. The
    value of this file is the sentences that could only have been written after
    the bug: keep the reason next to the rule.
-->

@ONE_LINE_DESCRIPTION@ for jailbroken iOS @MINIMUM_IOS_VERSION@+ — roothide and
rootless bootstraps both. **iOS only**: there is no Mac Catalyst build and no
macOS product. The app runs as `mobile`; with the privileged backend, the
bundled `@DAEMON@` LaunchDaemon does the privileged half as root. Without that
backend, the app still works under its own OS permissions.

The single idea the design hangs off: <one sentence — the trade this app makes
that everything else follows from. fd daemon: opens files, does not read them.
session host: the launchd job is a proxy; buffers live in an unsized child.
helper-per-job: the daemon starts one helper for one closed job.>

## Hard rules

- **One app, several wrappers, and the backend is resolved at runtime.** Never a
  build flag, never a compilation condition, never a per-packaging source
  variant. The handshake with the daemon is the only honest answer to "am I
  privileged", and it carries the install root rather than a boolean beside it.
- **The daemon's absence is never surfaced as an error.** A miss means launchd
  has not started it yet. Keep retrying, keep saying *Connecting…*, and fall
  back only after a grace period measured as a duration from the first miss —
  not a timeout, not a count of attempts. On-demand is the default. A session
  host that owns live PTYs is `KeepAlive` + `RunAtLoad` instead; a miss is
  still *Connecting…*, the daemon just refuses to *create* one by exiting.
- **Peer authentication happens before the first request is decoded.** Audit
  token, euid 0 or 501, the client entitlement and `no-sandbox`, then the
  executable on disk (root-owned, not group/world writable). Require
  `platform-application` only if the app actually carries it — match both
  sides.
- **No install prefix is written in Swift.** Derive it from the daemon's own
  `proc_pidpath`; anything that needs it asks the daemon. Packaging fails on
  `libvroot` in the app, daemon or helper.
- **Every path is canonicalised before a decision is made about it.**
  `realpath(3)` first, then compare components; reject an embedded NUL first.
- **A cold launch starts with no saved scenes.** `main.swift` deletes this
  bundle's `Library/Saved Application State/<id>.savedState` before
  `UIApplicationMain`. UIKit reads that archive before any scene delegate
  runs; leftover sessions from a previous UI framework or Info.plist restore
  the old delegate. Background resumes do not run `main`. Preferences stay.
  The app delegate is not `@main`.
- **Versions and the deployment target live in `Configuration/*.xcconfig`
  only.** `make check` rejects either in `project.pbxproj`.
- **No project generators.** `project.pbxproj` is hand-written; `objectVersion`
  is pinned and `make check` fails when Xcode rewrites it.
- **`CLAUDE.md` is a symlink to `AGENTS.md`.** `make check` enforces it.
- **No Swift file names the SDK's XPC constant macros.** They come from
  `Shared/XPCShim` through `AppXPC`; naming them in Swift links a dylib that
  iOS 15 does not have. `make check` greps for them.
- **No SF Symbol newer than `IPHONEOS_DEPLOYMENT_TARGET`.** It draws nothing on
  the floor and warns nowhere. `make check` checks it against CoreGlyphs.
- **No new dependency without a reason that survives the ladder**: what it
  replaces, and why the hand-written version would be worse rather than merely
  longer. Nothing third-party links into the daemon.
- **No absolute build path in a shipped binary.** `#file` is concise
  (`SWIFT_UPCOMING_FEATURE_CONCISE_MAGIC_FILE`, prefix maps in `Base.xcconfig`);
  the packager greps every binary for the repository root and fails on a hit.
- **User-facing text is a `String.LocalizationValue` spelled out in English**,
  resolved against `Localizable.xcstrings`. No `NSLocalizedString`, no
  `SHOUTING_KEY` identifiers; `make check` greps for both. Pick one catalogue
  discipline and keep it: compiler `.stringsdata` with no `extractionState`,
  or unseen keys kept as `manual` and pruned by hand.

## Layout

<the tree, one line per directory, saying what owns what>

## Build & verify

- `make harness` — the package tests on the Mac. Run this first.
- `make check` — project and packaging validation, including the floor greps.
- `make build` — unsigned app + daemon for iPhoneOS.
- `make sim` — Debug onto the simulator; no LaunchDaemon there and there cannot be.
- `make deb` / `make deb-all` — roothide and rootless packages, verified.
- `make tipa` / `make ipa` — only if the copied Makefile actually has them.
- `make install` — build and update an installation on an authorized device.
- `make vphone` — serve one `.deb` to the VM over HTTP.

Give every parallel worker its own `DERIVED_DATA=/private/tmp/<name>` — spelled
`/private/tmp`, never `/tmp`, or a package manifest that strips its own
checkout path finds no headers.

## Where things get tested

The Mac harness first, the simulator for the visuals, a vphone or a jailbroken
device for anything privileged, and the four floor audits (or an actual device)
for the oldest OS this app claims. Report which of those actually ran.

## Gotchas that bit us

<one entry per bug that cost more than an hour, with the symptom first and the
cause second — this section is why the file exists>
