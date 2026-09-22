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

- **The checklist comes before the code.** `CHECKLIST.md` is every one-time
  decision this repo has to make. No code is written until every box is
  ticked and `make check` passes `Scripts/check-checklist.sh`, which runs
  first and lists what is still open. An agent starting here works through
  it top to bottom and ticks a box only after doing or deciding the thing;
  one that does not apply is ticked with the reason beside it. The file
  stays, ticked: it is the record of what was decided.
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
- **roothide is recognised by the process's own path** (`RoothideRoot`,
  libroothide's own name rule), never by loading libroothide through the
  `.jbroot` link, which is not promised, and never by falling back to
  "`/var/jb`, so rootless". The daemon's `hello` stays the authority on the
  install root.
- **Every path is canonicalised before a decision is made about it.**
  `realpath(3)` first, then compare components; reject an embedded NUL first.
- **Start `ExecutableWatch` once, early in `didFinishLaunching`.** When the
  opened executable loses its last hard link, offer Later or Quit with wording
  covering both update and removal. Keep the registration-time check and the
  cancellation guard; the callback runs once on the main queue. Do not watch
  daemons: postinst restarts them after unpacking finishes. Omit this watch
  for a self-updating installer whose helper owns completion and exit.
- **The app never calls `exit` from the foreground.** A screen that vanishes
  reads as a crash. Quit, and any other exit the app chooses, is
  `QuietExit.run`: leave for the home screen, wait for the animation, run the
  cleanup `exit` would skip, then exit.
- **A cold launch starts with no saved scenes.** `main.swift` deletes this
  bundle's `Library/Saved Application State/<id>.savedState` before
  `UIApplicationMain`. UIKit reads that archive before any scene delegate
  runs; leftover sessions from a previous UI framework or Info.plist restore
  the old delegate. Background resumes do not run `main`. Preferences stay.
  The app delegate is not `@main`.
- **The app icon is never looked up by name.** An Icon Composer icon leaves
  `AppIcon` in the catalogue as an image stack with no bitmap, and on iOS 26
  `UIImage(named: "AppIcon")` aborts inside UIKit rather than returning nil.
  In-app uses draw the `AppIconMark` image set. Another app's icon comes
  from IconServices, then from its `CFBundleIconFiles` names read as files
  with `UIImage(contentsOfFile:)`, never `UIImage(named:in:)`.
- **A control with no text has no name.** Every icon-only button, bar button
  item and invisible button over a row gets an `accessibilityLabel` when it
  is written, not in a pass afterwards. The trait already says "button".
  Set the label beside the state it describes, or it goes stale: a
  pause/resume button labelled once at construction lies for half its life.
- **A label on a container UIKit does not treat as an element is never
  read.** A `UIView`, `UITableViewCell` or `UICollectionViewCell` with
  subviews is not an accessibility element, so the sentence `configure`
  assembles is walked past and the subviews are read instead, one stop each,
  with the drawn separators spoken. Set `isAccessibilityElement = true` on
  any cell or view that labels itself; `make check` runs
  `Scripts/check-accessibility.py`, which fails on a label that nothing can
  reach. A row that joins several labels puts the figure that changes in
  `accessibilityValue`, so a live sample re-announces the number without
  repeating the name. Setting the flag hides the subviews, so a row that
  owns a button — menu accessory, disclosure, checkbox — gives each one an
  `accessibilityCustomAction` or keeps the flag off and labels the subviews
  instead. Decide which before setting it; do not copy the neighbouring
  cell, which may be unreachable itself.
- **State that is only drawn is not spoken.** A checkmark, a tick, a
  selected card, a progress fill: `accessibilityValue` or a trait
  (`.selected`, `.isHeader`), never prose bolted onto the label. And a label
  that repeats what VoiceOver already reads is a regression — a
  `UIListContentConfiguration` row reads "title, value" already, a `UISwitch`
  supplies its own on/off, and a titled `UIAction` is already named.
- **Accessibility is semantics, never behaviour.** No
  `UIAccessibility.post(.layoutChanged)` on a routine view swap: it steals
  focus, and on a live-sampling screen it does so on every sample. No custom
  action that duplicates one the rotor already offers. Announce an event the
  user cannot see; nothing else.
- **Reading another app's bundle or container takes
  `com.apple.private.security.storage.AppBundles` and `.AppDataContainers`
  beside `no-sandbox`**, on the app and on the daemon; `no-sandbox` alone
  does not open them on every platform.
- **A crash is read before anything is changed.** Keep the dSYM of every
  build installed on a device, match it to the report's image UUID
  (`dwarfdump --uuid`), and symbolicate with `atos -o <dSYM DWARF> -l
  0x100000000 <0x100000000 + imageOffset>` before guessing at a cause.
- **Versions and the deployment target live in `Configuration/*.xcconfig`
  only.** `make check` rejects either in `project.pbxproj`.
- **No project generators.** `project.pbxproj` is hand-written; `objectVersion`
  is pinned and `make check` fails when Xcode rewrites it.
- **Name no specific package manager.** README, these notes and script
  messages say "your preferred package manager".
- **No Swift file names the SDK's XPC constant macros.** They come from
  `Shared/XPCShim` through `AppXPC`; naming them in Swift links a dylib that
  iOS 15 does not have. `make check` greps for them.
- **No SF Symbol newer than `IPHONEOS_DEPLOYMENT_TARGET`.** It draws nothing on
  the floor and warns nowhere. `make check` checks it against CoreGlyphs.
- **No new dependency without a reason that survives the ladder**: what it
  replaces, and why the hand-written version would be worse rather than merely
  longer. Nothing third-party links into the daemon.
- **The Licenses screen is generated, not written.** The app target's
  **Collect Licenses** build phase runs `Scripts/collect-licenses.py`, which
  writes `Licenses.json` into the app bundle from the repository `LICENSE`,
  every pin in `Package.resolved` (checkouts and binary artifacts, nested
  notices included) and any vendored source. A pin with no notice or
  GPL-family text fails the build. Vendored code keeps its upstream `LICENSE`
  beside it and its header on each file; MIT / BSD / Apache only. `make check`
  requires the phase, the packager requires the file. Read the generated list
  after adding a dependency.
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

## Package Pages

`Documents/Site/depiction.json` is the native depiction page. Keep its Details
copy accurate and use the largest banner referenced by the README as
`headerImage`. The Pages workflow refreshes its Changelog from published GitHub
releases using the shared updater pinned in that workflow; never maintain a
second changelog implementation or edit generated release notes by hand.
The copied publishing workflow must be named `Release` so Pages refreshes after
it succeeds. Deploy from `main`, including when an older release is edited.

Keep the `uikittools` dependency: its triggers register and unregister the app.
Maintainer hooks manage the daemon only; never add explicit `uicache` calls.

That trigger is `uicache -a`, which registers only what is not registered yet.
A package manager re-registers an upgrade itself; a bare `dpkg -i` over an
installed copy does not, and LaunchServices keeps the previous build's
Info.plist — version, document types, URL schemes, every key SpringBoard reads
from the record rather than from disk. After installing by hand, run
`uicache -p <prefix>/Applications/<App>.app` in the terminal, and respring if
SpringBoard has to read it again. When a plist or entitlement change "does not
take", check the record's `CFBundleVersion` against the bundle's before
anything else.

## Where things get tested

The Mac harness first, the simulator for the visuals, a vphone or a jailbroken
device for anything privileged, and the four floor audits (or an actual device)
for the oldest OS this app claims. Report which of those actually ran.

## Gotchas that bit us

<one entry per bug that cost more than an hour, with the symptom first and the
cause second — this section is why the file exists>
