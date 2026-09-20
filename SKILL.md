---
name: platformize-app-ios
description: Build and ship a native iOS app for jailbroken devices — a UIKit app plus its own root LaunchDaemon over XPC, packaged as roothide (iphoneos-arm64e) and rootless (iphoneos-arm64) debs and as a TrollStore .tipa / sideload .ipa, released from GitHub Actions and served by the owngoal-packages APT repo. Use when asked to "build a jailbreak app", "give my app a root daemon", "package an iOS app as a deb", "make it work on roothide and rootless", "ship it to TrollStore too", or to start a new OwnGoal app repo the way Fila, iGhostVT, CocoaInspector and Irisin are built.
---

# platformize-app-ios

Turn an iOS app into `wiki.qaq.<app>_<ver>_iphoneos-arm64{,e}.deb` plus
`<App>.tipa` / `<App>.ipa`, the way
`owngoal-dev/{Fila,iGhostVT,CocoaInspector}` and `Lakr233/Irisin` do it.
Reference implementations — pick by *daemon shape*, then copy that sibling's
`Scripts/` and `Makefile`:

- `../Fila` — file manager: app + `filad` + a spawn-only archive helper + a
  Save Action + a WebDAV server. The most complete *packaging* machinery. The
  default shape: the daemon `open(2)`s and forgets, bytes never enter it.
- `../iGhostVT` — terminal: app + `ighostvtd` proxy + `ighostvtd-io` + CLI +
  widgets, SwiftUI. Copy this only when something must stay open after the app
  dies and its buffers would jetsam a 6 MB launchd job.
- `../CocoaInspector` — process inspector: app + daemon + CLI. The smallest
  on-demand daemon, and the easiest to read end to end. Floor is iOS 13.
- [Irisin](https://github.com/Lakr233/Irisin) (formerly Chromatic / Saily) — package manager: app +
  `irisind` + one `irisin-install` per closed job. Swift 6 with main-actor
  default isolation. The helper-per-job reference. `chromatic` and `Saily` are
  dead names; Irisin's `make check` fails on either, and so should a new repo.

Read one before starting. This skill is the part that is the same in all four;
everything else is the app. Do not `cp ../Fila/Scripts` before the shape is
chosen — Fila's packager assumes an archive helper and no
`KeepAlive`.

The sibling skill `platformize-bin-ios` ports *command-line tools*. If what you
are shipping has no `.app`, use that one instead. App repos use `Makefile`,
`Scripts/`, `Packaging/`, `Configuration/` (Pascal). Packaging-only C/Rust
repos use lowercase `makefile` and directories; a SwiftPM CLI may match the
app casing (`kk` does — do not "fix" it).

## Pick the daemon shape

launchd caps a LaunchDaemon at 6 MB. That number decides the process model.
Absence of the daemon at lookup is still *Connecting…* in every shape; a miss
is a respring, not a failure screen.

**Fila / CocoaInspector — one process, on-demand (the template default).**
Privileged work is a syscall that returns immediately, or an fd the *client*
holds (`xpc_dictionary_set_fd`). Bytes never enter the daemon. Last client
gone → idle-exit (Fila: 3 s, and not while a child it spawned is unreaped).
No `KeepAlive`, no `RunAtLoad`. Copy Fila for a file/descriptor daemon,
CocoaInspector for a pull-sampler.

**iGhostVT — proxy + unsized child, `KeepAlive`.** Something must stay open
after the app dies (PTY master, replay, a long-lived child) *and* that
something's memory is unbounded. The launchd job is a thin authenticated
proxy; fat work is `posix_spawn` of a child launchd never sized (do not set
jetsam attrs on that spawn — children inherit 6 MB if you do). The io wire
*refuses* fds and mach ports (the opposite of Fila). Device plist is
`RunAtLoad` + `KeepAlive = true`. Demand-launch itself works; the race they
could not close is last session emptying the registry → daemon deciding to
exit → launchd already routing the next Mach connection. A crash while the
app sits idle is the other case demand-launch cannot cover.

**Irisin — one helper per closed job.** The work is a finite privileged
*transaction* (dpkg, icon-cache rebuild) that must survive the daemon
restarting, including when the job is this app itself. The wire is a closed
enum of jobs, never `exec(path, argv)`. The daemon `posix_spawn`s a named
helper (`POSIX_SPAWN_SETSID`, empty env, job on stdin) and hands back the
output pipe. Plist `AbandonProcessGroup` so `postinst` `bootout` does not
kill the in-flight helper. Helper ignores `SIGPIPE` and mirrors the
transcript to `<root>/var/log/<helper>.log`.

Anti-patterns: raising `JetsamMemoryLimit` instead of splitting; putting
Foundation/`DateFormatter` in a 6 MB proxy; idle-exit on a daemon that still
holds PTYs; forwarding XPC fds through a proxy codec; inlining a
self-updating installer into the daemon.

## The contract (do not bend these)

- **One app, several wrappers, and the backend is resolved at runtime, never at
  build time.** The same binary runs under roothide, under rootless, from
  TrollStore and from a sideload. Never add a build flag, a compilation
  condition or a per-packaging source variant to tell them apart. The link to
  the daemon answers "am I privileged" at its handshake, and that answer is an
  enum carrying the install root, not a boolean beside it.
- **The daemon's absence is never an error.** Keep retrying and keep saying
  *Connecting…*. Fallback to an unprivileged in-process backend is a **grace
  period** — a duration from the first miss, never a timeout and never a count
  of attempts. A build that ships a daemon beside its bundle never falls back.
  Ask `hello().isPrivileged`, never a construction-time "is the daemon
  installed" flag.
- **Peer authentication is the whole trust boundary.** Before the first
  request field is decoded: kernel audit token; pid > 1; euid root or mobile
  (501); `wiki.qaq.<app>.client` and `com.apple.private.security.no-sandbox`
  strictly true; `proc_pidpath` realpath-equal to the installed app (and CLI,
  if any) inside the install root; regular file, uid 0, owner-executable, not
  group- or world-writable. Fila, CocoaInspector and Irisin also require
  `platform-application` on the peer. iGhostVT dropped it on both sides: it
  attests "signed as platform", not "this client", and requiring it forced
  the app to carry an entitlement that tightens its sandbox and buys the
  daemon nothing. Match the authenticator to the app entitlement set — do not
  require a key the app does not have. Mach lookup is not auth. A CLI is a
  second peer; add one only if someone will use it. Bundle ids, the Mach
  service and the client entitlement are named after the app so two OwnGoal
  apps cannot admit each other's peers.
- **Nothing generic executes.** There is no `exec(path, argv)` on the wire. A
  root daemon that can be talked into running a command is a root shell.
  Spawn names exactly what, as whom, and what it refuses. Ordinary
  `posix_spawn` — not `fork`, `forkpty`, `execve`, `POSIX_SPAWN_SETEXEC`.
- **No install prefix is written in Swift.** Derive it from the daemon's own
  `proc_pidpath`; an unrecognized path refuses startup. `@PREFIX@` is packager
  only. Native app, daemon and helper keep **physical paths**: packaging
  `otool -L` fails on `libvroot`. Do not `symredirect` one side of a
  Foundation/XPC boundary. libroot's path spelling is not bootstrap identity
  (`/var/jb` may be what it returns on roothide).
- **An app replaced or removed while it runs says so** — unless this package *is* the
  installer of itself. dpkg renames each new file over the old one.
  `template/App/ExecutableWatch.swift` holds the launched executable with
  `O_EVTONLY` and fires once when the link count reaches zero, on update or
  uninstall. It checks after dispatch-source registration too, so an unlink
  between opening the fd and arming the watch is not lost. A `.dpkg-tmp`
  hard link delays notification until cleanup; rollback keeps the old inode
  linked and must not notify. The app asks *Later* or *Quit*, using wording
  that covers both update and removal (the watch does not distinguish them).
  Copy the file unchanged; start it once, early in `didFinishLaunching`.
  It watches the inode opened at startup: changes before that open, in-place
  writes, and moves that retain a hard link are outside this guard.
  `tests/test_executable_watch.py` compiles it into a real macOS process and
  exercises replacement, unlink, dpkg backup cleanup, rollback, and unlink
  before the registration callback. Device suspension still needs an iOS run.
  **Do not watch the daemon**: postinst restarts it once every file is in
  place, and a daemon that exited mid-unpack would kill its own helper. A
  self-updating installer has no watch: the helper finishes the job and the
  app `exit(0)`s after the transcript.
- **A cold launch starts with no saved scenes.** UIKit reads
  `Library/Saved Application State/<bundleID>.savedState` before any scene
  delegate runs. A leftover archive — previous UI framework, previous
  `Info.plist` scene configuration, previous `delegateClass` — restores that
  old delegate and never reaches the current one. `template/App/main.swift`
  deletes this bundle's `.savedState` *before* `UIApplicationMain`. The app
  delegate is not `@main`. Background resumes do not run `main`, so a live
  scene is left alone. Preferences and other bundles under the same folder
  stay. Do this on every app, not only after a UI-framework rewrite.
- **Every path is canonicalised before a decision is made about it.**
  `realpath(3)` first, then compare components; reject an embedded NUL first.
- **Versions and the deployment target live in `Configuration/*.xcconfig`
  only.** A target-level `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION` or
  `IPHONEOS_DEPLOYMENT_TARGET` in `project.pbxproj` silently shadows the
  xcconfig. `make check` must reject both. Two styles for the build number:
  Fila dirties `CURRENT_PROJECT_VERSION` from `make bump-build` on every
  xcodebuild; Irisin passes it on the xcodebuild line (`GITHUB_RUN_NUMBER` /
  git commit count) and never writes the file from a build. Pick one.
- **No project generators.** `project.pbxproj` is hand-written, `objectVersion`
  pinned (77). `make check` fails if Xcode rewrites it; revert that line.
- **Name no specific package manager.** README, `AGENTS.md`, the depiction
  and script messages say "your preferred package manager" — no named
  client, no client-specific "Add to …" link, no `brew install` hint. Field
  names such as `SileoDepiction` are identifiers and stay.
- **No `CLAUDE.md`.** It is deprecated; `AGENTS.md` is the only notes file.
- **Ad-hoc sign every embedded library, then read the entitlements back out.**
  The Swift compatibility dylibs the toolchain copies in keep Apple's own
  signature, which a jailbroken iOS 18 refuses outside the system: dyld halts
  the app with "code signature invalid", and a newer iOS never loads the
  library at all — so the crash appears only on the older device. Both
  packagers re-read entitlements from the *signed* binaries. The deb and the
  ordinary ipa fail in opposite directions. The app entitlement set always
  includes mach-lookup of `@SERVICE_NAME@`. An App Group is required on the
  app and every embedded extension *that shares a container* (Fila's Save
  Action); a Live Activity–only appex (iGhostVT) has none — do not invent
  one, and delete `$(APP_GROUP_IDENTIFIER)` from the entitlements if the
  packager you copied does not substitute it (Inspector does not).
  `platform-application` on the *app* is not automatic: iGhostVT measured
  it as unused there and dropped it from the authenticator too.
- **No third-party dependency links into the daemon.** The helper, if any,
  is a separate budget (Irisin: IcliKit only). Root and `no-sandbox` do not
  open a data vault: a process that writes under `/var/mobile/Library/Photos`
  (and friends) needs `com.apple.private.security.storage.<Class>` on *that*
  process. Fila's `Filad.entitlements` is the list; copy it onto a file-manager
  daemon or an install helper, not onto a sampler.
- **No absolute build path in a shipped binary.** `#file` is concise
  (`SWIFT_UPCOMING_FEATURE_CONCISE_MAGIC_FILE`); `-file-prefix-map` /
  `-ffile-prefix-map` are in `template/Configuration/Base.xcconfig`. A
  dependency that spells `#file` in a *default argument* in Swift 5 mode leaks
  the caller's path — SnapKit before 6.0 did. The packager greps every binary
  for the repository root, `GITHUB_WORKSPACE` and `RUNNER_TEMP`.
- **The deb Depends on `firmware (>= <floor>)`, `uikittools` and `launchctl`.**
  Keep `uikittools`: its triggers register and unregister the app. Do not call
  `uicache` in installation or removal hooks, including copied scripts.
  `@PREFIX@` in the launchd plist, `postinst` and `prerm` is substituted at
  package time.
  `postinst` boots out **system, user/501 and gui/501** before bootstrap:
  roothide's launchctl can land a system daemon in the per-user domain.
- **Every shipped app carries the notices of everything it links, generated
  by the build.** A **Collect Licenses** build phase writes `Licenses.json`
  into the bundle, Settings shows it, `make check` requires the phase and the
  packager refuses a bundle without the file. Never a hand-kept list, never a
  rewritten collector or screen — copy the sibling's. See *Licenses* below.
- **Review for sensitive information before every upload or publish, by
  reading.** Before a push, a tag or a release, have an agent read the diff,
  the staged payload tree and `strings` of the built binaries for credentials,
  private keys, home or scratch paths, device identifiers, hostnames and
  addresses. Never paste a device hostname, serial, UDID or LAN address into
  docs, commit messages or release bodies.

## The deployment floor is not what you set — it is what the linker believes

An app that says `IPHONEOS_DEPLOYMENT_TARGET = 15.0` and builds cleanly against
this year's SDK is **not** an app that runs on iOS 15. The live floors are not
one number (CocoaInspector 13, Fila and iGhostVT 15, Irisin 16). Four things
silently raise whatever floor you claim, and none of them is a warning. Audit
all four before any release; `scripts/audit-ios-floor.sh` does exactly that.

### 1. A library the SDK links non-weakly and the old OS does not have

The case that produced this section: the iOS 27 SDK added a Swift *overlay* for
XPC. Naming `XPC_TYPE_DICTIONARY`, `XPC_ARRAY_APPEND` or
`XPC_ERROR_CONNECTION_INVALID` in Swift — spellings that had been in the code
for a year — stopped resolving to the libSystem globals they are in C and
started resolving to accessors exported by `/usr/lib/swift/libswiftXPC.dylib`.
That dylib first shipped in iOS 16. `libswiftXPC.tbd` carries no
back-deployment metadata and the constants are annotated `@available(iOS 8.0)`,
so ld emitted a **required** load command. On iOS 15, dyld kills the process
before `main`:

```
"reasons" : ["Library not loaded: /usr/lib/swift/libswiftXPC.dylib", …]
```

Two users, two devices, one clean build. The rule:

```sh
otool -L <binary> | grep -v ', weak)'   # every entry must exist on the floor
```

Anything in that list that arrived after the floor is a launch failure, not a
runtime one. The fix is to stop referencing the new symbols, not to add a
linker flag: with no symbol from a dylib in use, ld weak-links it by itself and
dyld tolerates its absence. For SDK constants that exist in C, read them through
C — a header-only `[system]` module with `static inline` accessors, imported by
the one module every target links (see `../Fila`'s `Packages/FilaKit/Sources/CFilaXPC`
and `FilaXPC` in `FilaProtocol`, and the same shim in `../CocoaInspector`,
`../iGhostVT` and Irisin). `import XPC` itself is harmless; only the symbols
matter. Keep the shim even at a floor of 16: one path on every OS.

**Use one path on every OS.** Do not branch on availability to keep the "new"
spelling for new systems: then the code that runs on the old floor is the code
nobody ever runs. With a single C path, testing on iOS 26 tests exactly what
iOS 15 will execute.

### 2. Symbols newer than the floor, weak-linked and null

```sh
nm -m <binary> | grep 'weak external'
```

Every entry is NULL on an OS that predates it. A Swift or C call through one is
a crash at first use; each must be guarded in source. Objective-C *methods* have
no symbol at all — they are an unrecognized selector — so guard those with
`if #available(iOS N, *)` and never silence `-Wunguarded-availability-new`.

### 3. An embedded framework with a higher floor than the app

```sh
vtool -show-build <framework>/<name> | grep minos
```

An `.xcframework` built by someone else carries its own `minos`. Higher than
your floor means dyld refuses it on the old device, with the same launch
failure and a different library name.

### 4. Asset and resource identifiers with an OS version attached

The one that never crashes and is therefore the one that ships: **SF Symbols**.
`UIImage(systemName: "text.word.spacing")` returns nil on iOS 15 — the symbol is
from 2022 — and the button simply draws with no icon. Xcode's completion offers
this year's symbols with no regard for the deployment target. The availability
table ships on every Mac:

```
/System/Library/CoreServices/CoreGlyphs.bundle/Contents/Resources/name_availability.plist
```

`symbols` maps a name to a release year, `year_to_release` maps that year to an
iOS version. Check every `systemName:` / `systemImage:` literal against it in
`make check`.

## Layout

The four reference repos share this shape. Keep it; an agent that knows one
then knows all of them.

```
<App>/               the app: main.swift (manual UIApplicationMain), Application/,
                     Interface/<feature>/, Resources/
<app>d/              the daemon, product `<app>d`: main.swift, Server/, System/
<app>-install/       optional helper (Irisin shape), product `<app>-install`
Packages/<App>Kit/   a local Swift package: the wire protocol, the privileged
                     file/system layer, the client link, and everything else
                     that must be testable on a Mac with plain `swift test`
Configuration/       Version.xcconfig, Base.xcconfig, Development/Release
Packaging/           DEBIAN/{control,postinst,prerm} and optional postrm,
                     entitlements, launchd plist, Info.plist supplement
Shared/              XPC constant shim (template); Fila keeps it inside the package
Scripts/             copied from the sibling: package-deb.sh, verify-deb.sh,
                     sign-frameworks.sh, install-device.sh, vphone.sh,
                     run-xcodebuild.sh, collect-licenses.py. package-ipa.sh
                     is Fila only.
Licenses/            reviewed discipline only: one folder per binary component
                     (notice + notice.json), review.json, Compatibility.md
Documents/           Architecture.md, Roadmap.md, Site/ (Pages source)
manifest.json        the owngoal-packages entry
```

Fila and Irisin spell the prose folder `Documentation/`. iGhostVT and
CocoaInspector use `Documents/`. The template uses `Documents/Site/`. The
repo's Pages source is **GitHub Actions** deploying that folder, not the
legacy `main:/docs` setting.

The package is the reason the destructive code is testable: the jobs that copy
and delete, and the guard that refuses, live there and are exercised by
`swift test` on the Mac without a device, a simulator or the daemon. Anything
UIKit-only stays behind `canImport(UIKit)` so the package still builds on macOS.

There is deliberately **no CLI target** in Fila and a deliberate one in iGhostVT
and CocoaInspector: a CLI is a second client of the same daemon. A CLI that
must run below iOS 15 embeds `libswift_Concurrency.dylib` next to itself
(CocoaInspector: `usr/lib/cocoainspector/`); the daemon stays free of
`async`/`await`.

## Build & verify

The Makefile targets, in the order you will need them:

| target | what it does |
| --- | --- |
| `make harness` | `swift test --package-path Packages/<App>Kit`. No device. Run first: this is where a guard mistake or a copy that loses an xattr is caught. |
| `make check` | project and packaging validation: xcconfig ownership, `objectVersion`, plist lint, entitlement shape, the UI-library greps, the deployment-floor greps, the Collect Licenses phase. |
| `make build` | unsigned app + daemon for iPhoneOS (runs `check` and `harness` first). |
| `make sim` | Debug onto the booted simulator. There is **no LaunchDaemon** there and there cannot be — `launchd_sim` prefixes every job's program path with the sealed runtime root — so the simulator exercises the unprivileged backend and everything visual. Irisin is the exception: it runs the installer in-process against a directory of its own. Do not fake a daemon in the app to "fix" the simulator. |
| `make deb` / `make deb-all` | package for `FLAVOR` (roothide default, `iphoneos-arm64e`, rootful paths; `FLAVOR=rootless` packages the same binaries under `/var/jb` as `iphoneos-arm64`), ad-hoc sign with ldid, then verify the archive. |
| `make tipa` / `make ipa` | Fila only: the app alone, with and without jailbreak entitlements. iGhostVT, CocoaInspector and Irisin do not ship these targets — do not invent them after copying those Makefiles. |
| `make install` | build for `FLAVOR` and update an existing installation over `iproxy`. First installation still goes through the device's package installer. Confirm the payload *and* the launch: a locked iPad can accept an installation while refusing to open the app. |
| `make vphone` | incremental Debug build, then serve one `.deb` over HTTP to the VM. No SSH, no VM restart. |
| `make bump-build` | Fila-style: `CURRENT_PROJECT_VERSION += 1` in `Configuration/Version.xcconfig`. Not used by Irisin (see contract). |

Give every parallel worker its own `DERIVED_DATA=/private/tmp/<name>` (or
`~/Library/Caches/<name>`): the default path is shared, concurrent builds
cross-contaminate, and you get false greens and false reds. Spell it
`/private/tmp`, never `/tmp`: Xcode passes the path as written while
FileManager resolves it through the symlink, and a package manifest that strips
its own checkout path to compute header search paths (LNPopupController does)
then strips nothing and its private headers go unfound. The live Makefiles
already default to `/private/tmp/<app>-deriveddata`.

`run-xcodebuild.sh` must print the failed build commands and the raw tail of
the log when xcodebuild fails, not only the `error:` lines: a compiler killed
by the system, or a crashed `swift-frontend`, reports no `error:` line at all,
and the raw log is gone once the script exits.

## Where things get tested

1. **The Mac harness** for everything the package can reach. Always, first.
2. **The simulator** for the shell and the visuals, through the unprivileged
   backend (or Irisin's in-process installer).
3. **A vphone or a jailbroken device** for the privileged half: the XPC hop, the
   authenticator, entitlements, launchd, both bootstrap layouts, a descriptor
   opened as root. Nothing else proves those.
4. **The oldest OS you claim** — or, when you have no such device, the four
   static audits above. Say which one you did; "it builds" is not a claim about
   iOS 15.

Report what actually ran.

## Localization is verified against the compiler, never against a grep

A key missing from `Localizable.xcstrings` is not a build failure and never
warns — it renders the English key on a Chinese device. A release build emits
one `.stringsdata` per source file under `Build/Intermediates.noindex/…`; each
is a JSON whose `tables.Localizable` lists the exact keys the runtime will look
up. Diff that set against the catalogue and require `missing = 0` and
`orphaned = 0`.

Two ways the live apps keep the catalogue honest. Pick the one the sibling
you copied already uses; do not mix them.

- **Fila:** per-target catalogues, `bundle: .module`, no `extractionState` in
  any Localizable catalogue, `String.LocalizationValue("…")` at a package API
  (AlertController), compiler `.stringsdata` diff in `make check`. A prune
  script that writes `extractionState: manual` would fail Fila's checker.
- **Irisin / CocoaInspector:** keys Xcode cannot see (a `LocalizationValue`
  handed to another module; Inspector's iOS 13 `String(localized:)` shim) stay
  `"extractionState": "manual"`. `scripts/prune-xcstrings.py <catalog>
  <source roots…>` turns a stale key still quoted in a Swift file into
  `manual` and removes the rest. Run it by hand with Xcode closed, never from
  `make check`, because it writes.

Blind spots in both: a grep for `String(localized:)` cannot see SwiftUI's bare
`Text("Grid")`, and cannot see an interpolated key — `"\(count) selected"` is
looked up as `%lld selected`. Xcode's extractor only walks the **app target**
unless each package has its own catalogue. An open project rewrites and
reorders the file during every build — re-read the diff.

A translation keeps every format specifier with the same type and count, and
uses positional forms (`%1$@`, `%2$lld`) wherever the language reorders them.
Keep blunt warnings blunt in every language.

## Licenses are collected by the build, never written by hand

MIT, BSD and Apache all make the same demand of a binary distribution: the
notice travels with it. A deb is a binary distribution. An app with SwiftPM
dependencies and no Licenses screen is out of compliance the day it ships, and
a hand-kept list is out of date the day a pin moves. Three of the four
siblings ship this; CocoaInspector links nothing third-party and has none.
A new app gets it **in the scaffold, before the first dependency is added** —
not as a release chore.

The pieces, all copied, none rewritten:

- **`Scripts/collect-licenses.py`** (chmod +x) writes one `Licenses.json`: a
  JSON array of `{name, version?, license, url, text}`. It collects the
  repository's own `LICENSE` (versioned from `Version.xcconfig`, named from
  `manifest.json`), every pin in `Package.resolved` — the checkout under
  DerivedData's `SourcePackages/checkouts` *and* its binary artifacts under
  `SourcePackages/artifacts`, walked for LICENSE / COPYING / NOTICE files and
  `Licenses/` folders, nested ones included (that is how TreeSitter's notice
  inside `Runestone.xcframework` gets in) — and whatever the repo vendors.
  It **fails the build** on a pin with no checkout, a checkout with neither a
  license file nor a copyright header, and GPL-family text anywhere in the
  set. iGhostVT once shipped Ghostty's GPLv3 shell integration in a deb by
  accident; this is the check that keeps it out.
- **The "Collect Licenses" build phase** on the app target, last, hand-written
  into `project.pbxproj`: `alwaysOutOfDate = 1`, `outputPaths` =
  `$(TARGET_BUILD_DIR)/$(UNLOCALIZED_RESOURCES_FOLDER_PATH)/Licenses.json`,
  and `exec "$SRCROOT/Scripts/collect-licenses.py" --project "$SRCROOT"
  --build-dir "$BUILD_DIR" --output <that path>`. The script finds
  `SourcePackages` by walking up from `BUILD_DIR`, so it works for a build and
  an archive alike. It reads outside `SRCROOT`: either set
  `ENABLE_USER_SCRIPT_SANDBOXING = NO` on the app target (Fila, Irisin) or
  declare every file it reads as `inputPaths` (iGhostVT — and then a new
  vendored folder that is not declared never re-runs the phase). The file
  goes into the **app bundle only**, never the daemon.
- **The screen.** Settings ▸ About ▸ Licenses: a row per notice (name,
  `license · version`), the whole text selectable a push away, read from
  `Bundle.main`'s `Licenses.json`. UIKit: Fila's
  `Interface/Settings/LicensesViewController.swift` or Irisin's
  `LicenseController.swift` (the same screen). SwiftUI: iGhostVT's
  `LicensesView.swift`. Copy, rename, localize the title; about 140 lines.
- **The gates.** `make check`: the collector is executable and
  `project.pbxproj` names `collect-licenses.py` (otherwise the screen is
  silently empty). `verify-deb.sh` / the packagers: the payload contains
  `<App>.app/Licenses.json`. Both are a few lines in the sibling's Makefile
  and scripts; keep them when trimming.

Two disciplines, as with the string catalogue. Pick by what the app links:

- **Scanned (Irisin).** Everything comes from the checkouts; the license label
  is a keyword heuristic with `Other` as the fallback and the text shipped
  whole. Right when every dependency is a SwiftPM pin that carries its own
  notice. Two constants to edit after copying: `APP_SOURCES` (the app's own
  targets, scanned for a Swift file whose header comment names a license —
  code copied in from elsewhere ships that header) and `NOT_SHIPPED` (pins no
  shipped target links, e.g. an argument parser that serves only a CLI).
- **Reviewed (Fila, iGhostVT).** A `Licenses/` folder at the repo root, one
  directory per component that ships as a *binary with no license file*
  (Ghostty inside libghostty-spm, the tree-sitter grammars inside Runestone,
  BoringSSL, smbclient): the full notice plus `notice.json` (source URL,
  content hash, version). `review.json` records the reviewed hash and display
  label of every notice and the reviewed XCFramework revisions; a changed
  text, a new component or a binary upgrade fails collection until a person
  re-reads it, and `Compatibility.md` says why each licence is compatible.
  Right as soon as one prebuilt binary hides its components.

**Vendored source keeps its notice beside it.** Code copied into a local
package lives under `Sources/<Target>/Vendor/<Name>/` with the upstream
`LICENSE` in that folder and the upstream header left on each file; the
collector walks `Packages/` for nested license files and names the entry after
the folder (Xrash's `local_entries`). Vendoring is a licence decision before it
is a code decision: MIT / BSD / Apache-2.0 / ISC / zlib are fine, LGPL and GPL
are not — LGPL's relinking condition cannot be met by a statically linked,
ad-hoc signed iOS binary. Check the licence *before* evaluating the library,
and record the refusal where the dependency decision is written down.

Verify it rather than trust it: after a build, `python3 -m json.tool
<App>.app/Licenses.json | grep '"name"'` and compare against
`Package.resolved` plus the vendored folders. A missing transitive pin
(swift-crypto behind a wrapper, swift-asn1 behind that) is the usual surprise
— the collector reads `Package.resolved`, so they are all there; a reader
expecting only the direct dependencies should not "fix" the longer list.

## Publishing

1. `make check`, `make harness`, `make deb-all`, and (Fila only) `make tipa`
   / `make ipa`.
2. A read-through for sensitive information (above). Nothing goes out until it
   comes back clean.
3. Commit, push, tag `vX.Y.Z`. **Every published package comes out of the
   sibling's Release workflow** (copy `.github/workflows/release.yml` from
   the same repo you copied `Scripts/` from, then delete product-only jobs).
   CocoaInspector names that file `ci.yml`; normalize the copied workflow name
   to `Release` so the template Pages workflow observes its completion.
   The app template ships Pages only. Local `make deb` exists to prove the
   build and to `make install` on a device.

   **The workflow publishes the dSYMs too**, in the run's artifact and on the
   GitHub release, listed in `SHA256SUMS`. A crash report from a shipped
   build is addresses without them, and the runner's DerivedData is gone
   when the job ends. Release is already `dwarf-with-dsym`, so they sit
   beside the products; after packaging:

   ```sh
   cd "$DERIVED_DATA/Build/Products/Release-iphoneos"
   zip -qry "$GITHUB_WORKSPACE/build/Packages/<App>_${version}_dSYMs.zip" *.dSYM
   ```

   One zip **per build**, not per package: both flavours wrap one build, and
   neither `strip -xS` nor ldid touches `LC_UUID` (check with
   `dwarfdump --uuid` on the dSYM and on the binary inside the `.deb`). A
   second build is a second zip — Fila's sandboxed composition
   (`$DERIVED_DATA-sandboxed`), each of iGhostVT's platform jobs (`-xros`
   products; the Mac zip takes `Release-maccatalyst` and `Release`). Name
   it so no existing glob catches it: a merge job that counts `*.zip` or
   a checksum step over `*.deb` needs the dSYM zip added by name. The APT
   fetcher picks `.deb` assets by architecture and ignores the rest.
4. Enable Pages as **GitHub Actions** (not the legacy `/docs` folder). The
   workflow deploys `Documents/Site/` (`index.html`, `icon.png`, and
   `depiction.json` at Site root). Prepare the native depiction as described
   below. Before the first stable release, the updater leaves the Details-only
   page intact. Point `manifest.json`'s icon at
   `https://owngoal-dev.github.io/<repo>/icon.png`. The APT verify is
   CDN-delayed (`max-age` 600 s).
5. Add the repo to `owngoal-packages`' `manifest.json` (`repository` +
   `architectures`) *after* the release exists — the APT build fails on a
   manifest entry with no release — and watch its run go green.

## Swift 6 and the main actor

Irisin is the first of the apps on `SWIFT_VERSION = 6.0` for every target
with `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` on the app; Fila, iGhostVT
and CocoaInspector are still Swift 5 mode. What held up under it, and what
did not:

- **State lives on the main actor; work that takes time runs on a copy.** The
  engines hold their state on the main actor, so a read or a commit is a
  dictionary operation and nothing is locked. Parsing, resolving, hashing and
  writing take a value snapshot into a `nonisolated static` or `@concurrent`
  function and commit the result back. Every engine notification is posted on
  the main actor, so a UI observer is a plain `@objc func`. The migration
  removed every `NSLock` and serial queue; none of them was replaced by an
  actor. Do not add one; add a snapshot.
- A singleton is `nonisolated static let shared` with a `private nonisolated
  init()`; a property wrapper cannot be applied to a stored property of a
  nonisolated type, so it becomes `let store = Wrapper(...)` plus a computed
  property. A nested `Hashable` type used from the background is a
  `nonisolated struct`.
- **Xcode 26.6's `swift-frontend` crashes** (EarlyPerfInliner, in the
  optimizer of a Release build) on the *implicit* deinit of a generic subclass
  of an Objective-C generic class — `final class X<S, I>:
  UITableViewDiffableDataSource<S, I>` — under main-actor default isolation.
  Debug builds and the simulator are fine, so it shows up on CI. Spell the
  deinit out as `nonisolated deinit {}` and it compiles. Observed on the
  macos-26 runner with Xcode 26.6.
- A package at iOS 15 stays Swift 5 mode (tools 5.9) and is annotated
  `@MainActor` where the app needs it; IrisinKit follows the app at iOS 16 /
  Swift 6.

## Gotchas observed across the apps

- **A Swift wrapper module and a C framework that differ only by case.** The
  libarchive xcframework's module is `libarchive`; the upstream Swift package
  wraps it in a module named `LibArchive`. Xcode's module cache on a
  case-insensitive volume cannot tell them apart and the build fails with
  `cannot load module 'LibArchive' as 'libarchive'` — on CI, after a clean
  local build, because the local cache happened to be warm. Two fixes, both
  shipping: Fila aliases the wrapper (`moduleAliases: ["LibArchive":
  "FilaLibArchive"]`); Irisin drops the wrapper and links the artifact as
  its own `.binaryTarget(name: "libarchive", url:, checksum:)`, adding `z`,
  `bz2`, `iconv` and `xml2` to `linkerSettings` itself. The alias renames the
  *built* module only: source keeps `import LibArchive`, and
  `import <App>LibArchive` is a compile error.
- **A package's floor is in its source, not only in its manifest.** A
  library that uses `Int128` / `UInt128` needs iOS 18 whatever `platforms:`
  says, and lowering the manifest in a fork does not compile. Build a
  candidate for `generic/platform=iOS` at your floor before designing around
  it — next to reading its licence, and before reading its API.
- **iPadOS 18 reserves the top of the screen for a hidden tab bar.** A
  `UITabBarController` whose tab bar is hidden — because the app draws its own
  — still lays out for the iPad top tab bar and leaves a blank band under the
  status bar. A root that does not want a tab bar is a plain
  `UIViewController` with child containment, not a `UITabBarController` with
  the bar hidden. Seen on an iPad on iPadOS 18, absent on iOS 15 and 16.
  Whether the root wants one is the owner's rule, not taste: **more than
  three top-level pages get a real tab bar**, one navigation controller per
  tab; three or fewer get a single stack with a bar button that pushes
  Settings.
- **Nothing the developer needed to see stays on screen.** A backend state
  dumped into a navigation prompt is the first thing the owner sees. Status
  is a localized word in Settings (*Connecting…*, *Connected*, *Limited*);
  raw enum descriptions, install roots and file names with their extensions
  belong in the log. A list row is a picture (the app's icon, or a `terminal`
  glyph for a bare executable), a name a person would say, and a subtitle
  that carries information.
- **A blank Metal surface is an entitlement miss.** The bootstrap withholds
  the GPU from an ad-hoc binary until
  `com.apple.security.iokit-user-client-class` names the classes
  (`AGXDeviceUserClient`, `AppleParavirtDeviceUserClient` on vphone, IOAccel,
  IOSurface, framebuffer, HID). The kernel logs
  `deny iokit-open-user-client`; the view is a rectangle that never reports a
  viewport, while the daemon and everything behind it work. Copy iGhostVT's
  list. Core Image / Vision may need the `exception.iokit-user-client-class`
  spelling as well (Irisin, after a Bold Text crash).
- **Connected is not the first byte.** After `launchctl reboot userspace` the
  first zsh can take ~30 s to print (cold caches, AMFI/trustcache, load
  300–500). A UI that hides *Connecting…* at `openSession` looks identical to
  a broken surface. Show a "Starting…" state until the first byte (a replay
  counts).
- **`await dismiss` does not wait** on the iOS 27 SDK
  (`NS_SWIFT_DISABLE_ASYNC` on `dismissViewControllerAnimated:completion:`).
  Presenting the next sheet hits the one still leaving. Wrap dismiss in a
  continuation (Irisin `dismissFinishing(animated:)`).
- **`#available` does not hide a reference.** A symbol that exists only in a
  newer SDK still has to typecheck on CI's Xcode. Talk to it through KVC
  under the runtime check, or it will not compile on last year's Xcode.
- **Saved scene state outlives the code that wrote it.** After a SwiftUI app
  becomes a UIKit app (or the scene `delegateClass` changes), a cold launch
  still restores the old session and never calls the new delegate. Clearing
  the archive in `main` — not in `didFinishLaunching` — is the fix; UIKit has
  already read the archive by then.

## When a merge goes wrong

Splitting work across agents is fine; the risk is at the merge, not in the
branch. In one night of ten merged branches, every bug that reached `main` came
from the resolution:

- **Two correct fixes for the same bug make one crash.** Two patches for "a job
  whose link dropped hangs forever" merged into a `CheckedContinuation` resumed
  twice. Any callback that resumes a continuation must be taken off its row
  before anything else runs.
- **Identifiers collide silently.** Two agents took the same wire operation
  number; three took the same pbxproj object IDs. Git merges that without
  complaint. After any multi-branch merge, verify raw values are unique and
  every `productRef` points at the product its comment names.
- **A file nobody owns gets edited by nobody.** Excluding the string catalogue
  from every worker to avoid conflicts left a hundred keys missing. Whatever is
  excluded from everyone needs an owner at the end.

## Template

`template/` holds only the parts that are the same in every app repo and that
you cannot get by reading a sibling: the packaging inputs, the xcconfigs, the
XPC constant shim, the app's update watch, the scene-restoration reset
(`App/main.swift`, `App/SceneRestorationReset.swift`), the Pages workflow and
Site stub, and an `AGENTS.md` skeleton. **The build scripts are not here on
purpose** — `package-deb.sh`, `verify-deb.sh`, the ipa pair,
`sign-frameworks.sh`, `install-device.sh`, `vphone.sh`, `collect-licenses.py`
(and the Licenses screen) and the `Makefile` move with the live repos, and a fork of them here would be stale within a month.
Copy those from the sibling whose daemon shape you picked, then rename.

```sh
cp -R <this skill>/template/ <repo>/ && cd <repo>
# Pick one. Irisin lives at github.com/Lakr233/Irisin, not owngoal-dev/Irisin.
# fd / on-demand:     cp -R ../Fila/Scripts ../Fila/Makefile .
# smallest on-demand: cp -R ../CocoaInspector/Scripts ../CocoaInspector/Makefile .
# session host:       cp -R ../iGhostVT/Scripts ../iGhostVT/Makefile .
# helper-per-job:     cp -R <path-to-Lakr233/Irisin>/Scripts <path-to-Lakr233/Irisin>/Makefile .
# Copy the release workflow that matches the chosen build scripts:
# Fila / iGhostVT / Irisin: .github/workflows/release.yml
# CocoaInspector:         .github/workflows/ci.yml
cp <sibling>/.github/workflows/<release.yml-or-ci.yml> .github/workflows/release.yml
# Licenses: CocoaInspector has no collector, so its Scripts/ brings none. Take
# Irisin's (scanned) or Fila's (reviewed) collector, the matching screen, the
# build phase, and the make check / verify-deb gates — see "Licenses".
# cp <Irisin>/Scripts/collect-licenses.py Scripts/ && chmod +x Scripts/collect-licenses.py
# UI and string gates: CocoaInspector's Scripts/ brings neither. An app on
# SnapKit / AlertController takes Fila's check-ui-libraries.sh and
# check-localization.sh, cut down to its own roots, and wires both into
# `make check` on day one — run them once straight away: copied code that
# still presents a UIAlertController fails the first of them.
# The two release gates travel with the repo; they name no sibling.
cp <this skill>/scripts/audit-ios-floor.sh <this skill>/scripts/check-symbol-availability.py Scripts/
# Set its workflow name to Release, then remove only product-only jobs.
# Keep macos-26, Xcode selection, signing, verification, and all required assets.
mv Packaging/APP.entitlements    "Packaging/<App>.entitlements"
mv Packaging/DAEMON.entitlements "Packaging/<App>d.entitlements"
mv Packaging/DAEMON.plist        "Packaging/<daemon bundle id>.plist"
# helper-per-job: mv Packaging/HELPER.entitlements "Packaging/<app>-install.entitlements"
# otherwise:      rm Packaging/HELPER.entitlements
mkdir -p "<App>/Application"
mv App/main.swift "<App>/"
mv App/SceneRestorationReset.swift "<App>/Application/"
# skip ExecutableWatch only for a self-updating installer (the helper owns the replace):
mv App/ExecutableWatch.swift "<App>/Application/"
rmdir App
grep -rn '@[A-Z_]*@' --exclude-dir=.git .         # every hit is a decision
# The sibling's name, swept over the whole repo — not just Makefile/Scripts.
# Must print nothing before the first build (AGENTS.md may credit the sibling).
grep -rniE 'fila|ighostvt|inspector|irisin|chromatic|saily' \
    --exclude-dir=.git --exclude=AGENTS.md .
```

**The rename is finished when that sweep is empty, not when the build is
green.** A leftover sibling name builds and packages without complaint. Where
they were found while scaffolding Xrash from CocoaInspector, all outside
anything a compiler reads: `DERIVED_DATA ?= /private/tmp/inspector-deriveddata`
(two apps then share one derived-data folder and cross-contaminate — the
false-green case from *Build & verify*), `mktemp` prefixes in every script,
the `<sibling>-harness` temp names, the workflow `concurrency.group`,
`$RUNNER_TEMP/<sibling>-…`, the artifact name, the release-notes title, the
package id handed to `verify-deb.sh` in the workflow, and the `usage:` /
header comments of copied scripts. Rewrite the Makefile and the packager in one
pass rather than patching lines as they fail: a copied packager also carries
the sibling's *shape* (CocoaInspector's takes a CLI binary, its entitlements
and a back-deployed `libswift_Concurrency.dylib` for an iOS 13 floor), and
argument counts, payload lists and entitlement loops all have to change
together.

Copy the sibling's `.gitignore` too, then make sure it ignores `.build/` and
`.swiftpm/`: CocoaInspector has no local package, so its file does not, and the
first `git add -A` after `make harness` stages the whole SwiftPM build folder.
Read `git status --short` before the first commit; the scaffold is about fifty
files, not hundreds.

Placeholders: `@APP_NAME@`, `@REPO@`, `@BUNDLE_ID@` (`wiki.qaq.<app>`),
`@DAEMON@` (`<app>d`), `@DAEMON_ID@` (`wiki.qaq.<app>d`), `@SERVICE_NAME@`
(`wiki.qaq.<app>.service`), `@APP_CLIENT_ENTITLEMENT@`
(`wiki.qaq.<app>.client`), `@PACKAGE_ID@`, `@MINIMUM_IOS_VERSION@`,
`@ONE_LINE_DESCRIPTION@`, `@PACKAGE_DESCRIPTION@`, `@BANNER_URL@`, and
`@DEPICTION_DESCRIPTION@`. `@PREFIX@`, `@VERSION@`, `@ARCHITECTURE@`, `@FLAVOR@`
and `@INSTALLED_SIZE@` are substituted by the packager at package time — leave
those alone.

**Replace the token and nothing around it.** Match `@DAEMON_ID@`, never
`/@DAEMON_ID@ ` with its neighbours: a replacement that drops the trailing
space turns `bootout system/<id> 2>/dev/null` into
`bootout system/<id>2>/dev/null`. That is still valid sh — `sh -n` passes, the
hook exits 0 — but launchctl is handed the label `<id>2`, the old daemon keeps
the Mach service across an upgrade, and stderr is no longer silenced. Observed
while scaffolding Xrash with a replace-all whose pattern ended in a space. The
hooks now assign `label=@DAEMON_ID@` once, alone on its line, and quote
`"system/$label"` everywhere else; keep that shape in copied hooks. After any
rename, prove it rather than read it:

```sh
grep -nE '[A-Za-z0-9_@]2>' Packaging/DEBIAN/*     # must print nothing
grep -c '<daemon id>' Packaging/DEBIAN/{postinst,prerm,postrm}   # 1 each
```

`template/Packaging/DAEMON.plist` is on-demand. Each optional key is a
one-line XML comment of the form `<!-- <key>…</key><true/> -->` — delete only
those markers, not the prose at the top of the file. Enable
`AbandonProcessGroup` for a helper-per-job daemon; enable `KeepAlive` /
`RunAtLoad` for a session host (and set `ProcessType` to Interactive).
`postinst` already boots out three launchd domains. Fila and Inspector
packagers copy only `postinst` and `prerm`: add `postrm` to that loop, or
delete `Packaging/DEBIAN/postrm`. Keep `uikittools` in `Depends` for automatic
app registration and removal through its triggers. The lifecycle hooks manage
the daemon only; remove any explicit `uicache` calls from copied scripts too.
Default `APP.entitlements` has an App Group; delete it unless an extension
shares a container, and only if the packager substitutes `$(APP_GROUP_IDENTIFIER)`.

`scripts/audit-ios-floor.sh <floor> <paths…>` and
`scripts/check-symbol-availability.py <floor> <source roots…>` are the two
release gates from the floor section; wire both into `make check` (the symbol
one) and the release path (the floor one, over the built `.app`, the daemon and
every helper). `scripts/prune-xcstrings.py` is the Irisin/Inspector catalogue
tidy; Fila's checker is in Fila's `Scripts/` — copy the one that matches.

### Native Depiction

Drop `icon.png` into `Documents/Site/` before the first Pages deploy. Keep the
control file's `Depiction` and `SileoDepiction` URLs pointing at the site root
and `/depiction.json`, respectively.

Set `@BANNER_URL@` to the full HTTPS URL of the largest banner image referenced
by the app's README. Compare the actual image dimensions; do not choose the
app icon or a thumbnail. A tracked image can use its GitHub raw URL on `main`.
Write `@PACKAGE_DESCRIPTION@` as one short paragraph and
`@DEPICTION_DESCRIPTION@` as Markdown describing supported features and
compatibility. Retain installation and device caveats from the README; never
invent generic features. Replace JSON string values through a JSON encoder so
quotes and multiline Markdown remain valid. Do not substitute packager-only
`@VERSION@` into the static depiction.

The template has only a Details tab. Pages runs the shared
`owngoal-packages/scripts/update-depiction-changelogs.py` at a pinned commit with
`--repository OWNER/REPO --depiction Documents/Site/depiction.json`. It adds the
Changelog tab from published GitHub release titles, dates, and Markdown notes.
Do not copy that implementation into the new app. Pages fetches releases on
site changes, manual runs, release publication or edits, and successful
`Release` workflow completion. Release events dispatch a Pages run on `main`
so tag-triggered runs do not conflict with Pages environment branch restrictions.
The completion trigger also handles releases created with `GITHUB_TOKEN`,
whose release events do not start another workflow.

The copied release workflow must publish the release only after its build and
package checks pass, and it must not serialize work that shares nothing. Shape
it as **test ‖ compile → release**: `test` runs `make harness`; `compile`
builds, verifies and uploads the packages with the harness skipped
(`SKIP_HARNESS=1`; the Makefile's `build` target drops that prerequisite only
when it is set, so a local build is still gated); `release` has
`needs: [test, compile]`, runs on tags only, downloads the artifact, checks
`SHA256SUMS` and publishes — no checkout, no Xcode, an Ubuntu runner. A
failure in either parallel job skips `release` and fails the run. Fila and
Xrash are the references. Retain its macOS runner, signing steps, and product-specific
verification. If its name differs, change it to `Release` or update the Pages
`workflow_run.workflows` entry to the same name. Enable Pages with GitHub Actions,
publish the first stable release, and verify the deployed JSON and banner URLs.

Validate a scaffold with `python3 -m unittest discover -s tests -v` in this
skill repository. In the generated app, run `actionlint` on both workflows,
parse `Documents/Site/depiction.json`, run `sh -n` on every maintainer hook,
and check that no unresolved scaffold placeholders remain. Packager placeholders
in packaging inputs are intentional until the packages are built.

## Output

A report that says: what was built, which daemon shape and which sibling the
scripts came from, which of the four floor audits ran and what they said, which
surfaces were actually tested (harness / simulator / vphone / device / oldest
OS), how many notices `Licenses.json` carries and which discipline collects
them, the deb names and digests for both flavours, the tipa and ipa, the release
URL and the owngoal-packages commit.
