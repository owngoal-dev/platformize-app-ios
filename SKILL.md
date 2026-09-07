---
name: platformize-app-ios
description: Build and ship a native iOS app for jailbroken devices — a UIKit app plus its own root LaunchDaemon over XPC, packaged as roothide (iphoneos-arm64e) and rootless (iphoneos-arm64) debs and as a TrollStore .tipa / sideload .ipa, released from GitHub Actions and served by the owngoal-packages APT repo. Use when asked to "build a jailbreak app", "give my app a root daemon", "package an iOS app as a deb", "make it work on roothide and rootless", "ship it to TrollStore too", or to start a new OwnGoal app repo the way Fila, iGhostVT and CocoaInspector are built.
---

# platformize-app-ios

Turn an iOS app into `wiki.qaq.<app>_<ver>_iphoneos-arm64{,e}.deb` plus
`<App>.tipa` / `<App>.ipa`, the way `owngoal-dev/{Fila,iGhostVT,CocoaInspector}`
do it. Reference implementations, in order of completeness:

- `../Fila` — file manager: app + `filad` + a spawn-only archive helper + a File
  Provider extension + a WebDAV server. The most complete build and packaging
  machinery; copy its `Scripts/` and `Makefile` first.
- `../iGhostVT` — terminal: app + daemon + CLI + widgets, SwiftUI.
- `../CocoaInspector` — process inspector: app + daemon + CLI, the smallest of
  the three and the easiest to read end to end.
- Chromatic (Saily, the package manager; joins this list when it is published)
  — app + daemon + a per-job install helper. The first of the four in Swift 6
  language mode with main-actor default isolation; the reference for the
  helper-per-job pattern and the string catalog pruning below.

Read one before starting. This skill is the part that is the same in all three;
everything else is the app.

The sibling skill `platformize-bin-ios` ports *command-line tools*. If what you
are shipping has no `.app`, use that one instead.

## The contract (do not bend these)

- **One app, several wrappers, and the backend is resolved at runtime, never at
  build time.** The same binary runs under roothide, under rootless, from
  TrollStore and from a sideload. Never add a build flag, a compilation
  condition or a per-packaging source variant to tell them apart. The link to
  the daemon answers "am I privileged" at its handshake, and that answer is an
  enum carrying the install root, not a boolean beside it.
- **The daemon is on-demand, and its absence is never an error.** launchd starts
  it when the app looks the Mach service up; a miss means it has not started
  yet, which is what a device that just resprang looks like. Keep retrying and
  keep saying *Connecting…*. The fallback to an unprivileged in-process backend
  is a **grace period** — a duration, measured from the first miss — never a
  timeout and never a count of attempts, because a count means whatever the
  caller's polling cadence makes it mean.
- **The daemon opens files; it does not read them.** launchd's jetsam budget for
  a daemon is 6 MB. The client asks for a path, the daemon `open(2)`s it as root
  and the descriptor travels over XPC (`xpc_dictionary_set_fd`); bytes flow
  between the app and the kernel with nothing in between. The wire protocol has
  no `readFile` and no `writeFile`, and it never will.
- **Peer authentication is the whole trust boundary.** A root daemon that hands
  out descriptors is a privilege-escalation service for every process on the
  device until it proves who is calling: audit token from the connection, then
  the peer's entitlement, then its code identity on disk (a regular executable
  file owned by root inside the install root). Do this before the first request
  is decoded, not per operation.
- **Nothing generic executes.** The daemon may spawn exactly the helpers it
  names, with an argv of exactly itself and an empty environment. There is no
  `exec(path, argv)` case in the wire protocol, because a root daemon that can
  be talked into running a command is a root shell for whoever can talk to it.
  When the privileged work is a *job* rather than a descriptor — dpkg over a
  set of packages, an icon-cache rebuild — the wire carries a closed enum of
  jobs and the daemon starts **one helper for one job**, then hands the app
  the helper's output pipe. The helper composes every argv itself from the
  job's fields. It is spawned with `POSIX_SPAWN_SETSID` and the daemon plist
  sets `AbandonProcessGroup`, so the postinst of the app's own package
  restarting the daemon does not kill the transaction; the helper ignores
  `SIGPIPE` and mirrors its transcript to `<root>/var/log/<helper>.log`, so a
  reader that went away (the app being replaced) loses nothing. The daemon
  keeps no state across jobs.
- **No install prefix is written in Swift.** roothide relocates rootful paths
  into a randomized bootstrap; rootless installs under `/var/jb`; a rootful
  layout has no prefix. Derive all three from the daemon's own `proc_pidpath`,
  and let everything that needs the prefix ask the daemon. An unrecognized
  daemon path refuses startup.
- **Every path is canonicalised before a decision is made about it.** `/var` and
  `/etc` are symlinks into `/private`; a guard that compares an unresolved
  string is a guard with a bypass. `realpath(3)` first, then compare
  components, and reject an embedded NUL before the C conversion.
- **Versions and the deployment target live in `Configuration/*.xcconfig`
  only.** A target-level `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION` or
  `IPHONEOS_DEPLOYMENT_TARGET` in `project.pbxproj` silently shadows the
  xcconfig and ships the wrong number. `make check` must reject both.
- **No project generators.** `project.pbxproj` is hand-written and checked in,
  with `objectVersion` pinned and file-system-synchronized groups so a new file
  joins its target by existing. Never introduce XcodeGen or Tuist. `make check`
  fails if Xcode rewrites `objectVersion` on a GUI save; revert that line.
- **Ad-hoc sign every embedded library, then read the entitlements back out.**
  The Swift compatibility dylibs the toolchain copies in keep Apple's own
  signature, which a jailbroken iOS 18 refuses outside the system: dyld halts
  the app with "code signature invalid", and a newer iOS never loads the library
  at all — so the crash appears only on the older device. Both packagers must
  re-read entitlements from the *signed* binaries and fail on them; the deb and
  the ordinary ipa fail in opposite directions (jailbreak entitlements required
  in one, forbidden in the other), and both wrappers require a matching App
  Group on the app and every embedded extension.
- **No third-party dependency links into the daemon.** Whatever the app links,
  the daemon's list is a budget, not a habit: the wire vocabulary, the file
  layer, the log. Everything else is app-side because of the 6 MB cap.
- **No absolute build path in a shipped binary.** `#file` in Swift 5 mode is
  the absolute source path, so every `fatalError` and `precondition` ships the
  build machine's home directory. `SWIFT_UPCOMING_FEATURE_CONCISE_MAGIC_FILE`
  makes it `Module/File.swift`; `-file-prefix-map` / `-ffile-prefix-map` cover
  debug info and C's `__FILE__` (both are in `template/Configuration/Base.xcconfig`).
  A dependency that still spells `#file` in a *default argument* in Swift 5
  mode leaks the caller's path regardless — SnapKit before 6.0 did. So the
  packager greps every binary for the repository root, `GITHUB_WORKSPACE` and
  `RUNNER_TEMP` and fails the build on a hit; that is the check that finds the
  dependency.
- **The deb depends on `firmware (>= <floor>)`, `uikittools` and `launchctl`,
  and nothing else.** `postinst` boots the daemon and runs `uicache`; `prerm`
  boots it out and uncaches. `@PREFIX@` in the launchd plist, `postinst` and
  `prerm` is substituted at package time.
- **Review for sensitive information before every upload or publish, by
  reading.** Before a push, a tag or a release, have an agent read the diff, the
  staged payload tree and `strings` of the built binaries for credentials,
  private keys, home or scratch paths, device identifiers, hostnames and
  addresses. Never paste a device hostname, serial, UDID or LAN address into
  docs, commit messages or release bodies.

## The deployment floor is not what you set — it is what the linker believes

An app that says `IPHONEOS_DEPLOYMENT_TARGET = 15.0` and builds cleanly against
this year's SDK is **not** an app that runs on iOS 15. Four things silently
raise the floor, and none of them is a warning. Audit all four before any
release; `scripts/audit-ios-floor.sh` does exactly that.

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
and `FilaXPC` in `FilaProtocol`, and the same shim in `../CocoaInspector` and
`../iGhostVT`). `import XPC` itself is harmless; only the symbols matter.

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

The three reference repos share this shape. Keep it; an agent that knows one
then knows all of them.

```
<App>/               the app: main.swift (manual UIApplicationMain), Application/,
                     Interface/<feature>/, Resources/
<app>d/              the daemon, product `<app>d`: main.swift, Server/, System/
Packages/<App>Kit/   a local Swift package: the wire protocol, the privileged
                     file/system layer, the client link, and everything else
                     that must be testable on a Mac with plain `swift test`
Configuration/       Version.xcconfig, Base.xcconfig, Development/Release
Packaging/           DEBIAN/{control,postinst,prerm}, entitlements, launchd
                     plist, Info.plist supplement
Scripts/             package-deb.sh, verify-deb.sh, package-ipa.sh,
                     verify-ipa.sh, sign-frameworks.sh, install-device.sh,
                     vphone.sh, run-xcodebuild.sh, build-package-inputs.py
Documents/           Architecture.md, Roadmap.md
docs/                the GitHub Pages redirect and the package icon
manifest.json        the owngoal-packages entry
```

The package is the reason the destructive code is testable: the jobs that copy
and delete, and the guard that refuses, live there and are exercised by
`swift test` on the Mac without a device, a simulator or the daemon. Anything
UIKit-only stays behind `canImport(UIKit)` so the package still builds on macOS.

There is deliberately **no CLI target** in Fila and a deliberate one in iGhostVT
and CocoaInspector: a CLI is a second client of the same daemon, and every
client is another peer the authenticator has to be right about. Add one only if
someone will use it.

## Build & verify

The Makefile targets, in the order you will need them:

| target | what it does |
| --- | --- |
| `make harness` | `swift test --package-path Packages/<App>Kit`. No device. Run first: this is where a guard mistake or a copy that loses an xattr is caught. |
| `make check` | project and packaging validation: xcconfig ownership, `objectVersion`, plist lint, entitlement shape, the UI-library greps, the deployment-floor greps. |
| `make build` | unsigned app + daemon for iPhoneOS (runs `check` and `harness` first). |
| `make sim` | Debug onto the booted simulator. There is **no daemon** there and there cannot be — `launchd_sim` prefixes every job's program path with the sealed runtime root — so the simulator exercises the unprivileged backend and everything visual, and nothing privileged. |
| `make deb` / `make deb-all` | package for `FLAVOR` (roothide default, `iphoneos-arm64e`, rootful paths; `FLAVOR=rootless` packages the same binaries under `/var/jb` as `iphoneos-arm64`), ad-hoc sign with ldid, then verify the archive. |
| `make tipa` / `make ipa` | the app alone: the `.tipa` keeps the jailbreak entitlements, the `.ipa` carries only the App Group. |
| `make install` | build for `FLAVOR` and update an existing installation over `iproxy`. First installation still goes through the device's package installer. |
| `make vphone` | incremental Debug build, then serve one `.deb` over HTTP to the VM. No SSH, no VM restart. |

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
   backend.
3. **A vphone or a jailbroken device** for the privileged half: the XPC hop, the
   authenticator, entitlements, launchd, both bootstrap layouts, a descriptor
   opened as root. Nothing else proves those.
4. **The oldest OS you claim** — or, when you have no such device, the four
   static audits above. Say which one you did; "it builds" is not a claim about
   iOS 15.

Report what actually ran. A locked iPad can accept an installation while
refusing to launch the app, so confirm the payload *and* the launch.

## Localization is verified against the compiler, never against a grep

A key missing from `Localizable.xcstrings` is not a build failure and never
warns — it renders the English key on a Chinese device. A release build emits
one `.stringsdata` per source file under `Build/Intermediates.noindex/…`; each
is a JSON whose `tables.Localizable` lists the exact keys the runtime will look
up. Diff that set against the catalogue and require `missing = 0` and
`orphaned = 0`.

Two blind spots to plan around:

- A grep for `String(localized:)` cannot see SwiftUI's bare `Text("Grid")`, and
  cannot see an interpolated key — `"\(count) selected"` is looked up as
  `%lld selected`.
- Xcode's extractor only walks the **app target**. Strings inside
  `Packages/…/Sources` never reach a `.stringsdata`, so a diff against that set
  alone reports a clean catalogue while a whole module ships English. Scrape
  package targets separately, and keep their strings plain — no interpolated
  keys — so a scrape can see them all.
- The extractor also only sees a `String.LocalizationValue` literal handed to
  a function of the **same module**. One handed straight to a package's API
  (`AlertViewController(title: "No Repositories to Share")`) resolves against
  the catalogue at run time and is marked *stale* at build time — and Xcode,
  while the project sits open, deletes stale entries together with their
  translations on its own schedule. `extractionState: manual` is the state
  Xcode never touches. `scripts/prune-xcstrings.py <catalog> <source roots…>`
  makes that decision from the sources: a stale key still quoted in a Swift
  file becomes `manual`, the rest are removed. Run it instead of hand-editing,
  and commit catalogue changes with Xcode closed, or re-read the diff: an open
  project rewrites and reorders the file during every build.

A translation keeps every format specifier with the same type and count, and
uses positional forms (`%1$@`, `%2$lld`) wherever the language reorders them:
getting that wrong is a crash at format time. Keep blunt warnings blunt in every
language — softening a destructive-action warning in translation means only that
language's users lose a file.

## Publishing

1. `make check`, `make harness`, `make deb-all`, `make tipa`, `make ipa`.
2. A read-through for sensitive information (above). Nothing goes out until it
   comes back clean.
3. Commit, push, tag `vX.Y.Z`. **Every published package comes out of the
   Release workflow**; local `make deb` exists to prove the build and to
   `make install` on a device.
4. Enable Pages from `main:/docs` and point `manifest.json`'s icon at it.
5. Add the repo to `owngoal-packages`' `manifest.json` (`repository` +
   `architectures`) *after* the release exists — the APT build fails on a
   manifest entry with no release — and watch its run go green.

## Swift 6 and the main actor

Chromatic is the first of the apps on `SWIFT_VERSION = 6.0` for every target
with `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` on the app; the others are
still Swift 5 mode. What held up under it, and what did not:

- **State lives on the main actor; work that takes time runs on a copy.** The
  engines (repositories, packages, tasks, downloads) hold their state on the
  main actor, so a read or a commit is a dictionary operation and nothing is
  locked. Parsing dpkg's status, compiling repository indexes, resolving
  dependencies, hashing downloads and writing to disk take a value snapshot
  into a `nonisolated static` or `@concurrent` function and commit the result
  back. Every engine notification is posted on the main actor, so a UI
  observer is a plain `@objc func`. The migration removed every `NSLock` and
  serial queue; none of them was replaced by an actor. Do not add one; add a
  snapshot.
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
- The package targets stay Swift 5 mode (tools 5.9, iOS 15) and are annotated
  `@MainActor` where the app needs them to be; a package in Swift 6 mode would
  turn every UIKit-adjacent call in it into a diagnostic at once.

## Gotchas observed across the apps

- **A Swift wrapper module and a C framework that differ only by case.** The
  libarchive xcframework's module is `libarchive`; the upstream Swift package
  wraps it in a module named `LibArchive`. Xcode's module cache on a
  case-insensitive volume cannot tell them apart and the build fails with
  `cannot load module 'LibArchive' as 'libarchive'` — on CI, after a clean
  local build, because the local cache happened to be warm. Two fixes, both
  shipping: Fila aliases the wrapper (`moduleAliases: ["LibArchive":
  "FilaLibArchive"]`); Chromatic drops the wrapper and links the artifact as
  its own `.binaryTarget(name: "libarchive", url:, checksum:)`, adding `z`,
  `bz2`, `iconv` and `xml2` to `linkerSettings` itself.
- **iPadOS 18 reserves the top of the screen for a hidden tab bar.** A
  `UITabBarController` whose tab bar is hidden — because the app draws its own
  — still lays out for the iPad top tab bar and leaves a blank band under the
  status bar. A root that does not want a tab bar is a plain
  `UIViewController` with child containment, not a `UITabBarController` with
  the bar hidden. Seen on an iPad on iPadOS 18, absent on iOS 15 and 16.

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
you cannot get by reading a sibling: the packaging inputs, the two xcconfigs,
the XPC constant shim and an `AGENTS.md` skeleton. **The build scripts are not
here on purpose** — `package-deb.sh`, `verify-deb.sh`, `package-ipa.sh`,
`verify-ipa.sh`, `sign-frameworks.sh`, `install-device.sh`, `vphone.sh` and the
`Makefile` move with the live repos, and a fork of them here would be stale
within a month. Copy those from the closest sibling and rename.

```sh
cp -R <this skill>/template/ <repo>/ && cd <repo>
cp -R ../Fila/Scripts ../Fila/Makefile .          # or ../iGhostVT, ../CocoaInspector
mv Packaging/APP.entitlements    "Packaging/<App>.entitlements"
mv Packaging/DAEMON.entitlements "Packaging/<App>d.entitlements"
mv Packaging/DAEMON.plist        "Packaging/<daemon bundle id>.plist"
ln -s AGENTS.md CLAUDE.md
grep -rn '@[A-Z_]*@' .                            # every hit is a decision
grep -rni 'fila\|ighostvt\|inspector' Makefile Scripts Packaging   # every hit is a rename
```

Placeholders: `@APP_NAME@`, `@REPO@`, `@BUNDLE_ID@` (`wiki.qaq.<app>`),
`@DAEMON@` (`<app>d`), `@DAEMON_ID@` (`wiki.qaq.<app>d`), `@SERVICE_NAME@`
(`wiki.qaq.<app>.service`), `@APP_CLIENT_ENTITLEMENT@`
(`wiki.qaq.<app>.client`), `@PACKAGE_ID@`, `@MINIMUM_IOS_VERSION@`,
`@ONE_LINE_DESCRIPTION@`. `@PREFIX@`, `@VERSION@`, `@ARCHITECTURE@`, `@FLAVOR@`
and `@INSTALLED_SIZE@` are substituted by the packager at package time — leave
those alone.

Bundle identifiers are lowercase throughout, and the daemon, its Mach service
and the client entitlement are all named after the app so that two OwnGoal apps
on one device can never authenticate each other's peers.

`scripts/audit-ios-floor.sh <floor> <paths…>` and
`scripts/check-symbol-availability.py <floor> <source roots…>` are the two
release gates from the section above; wire both into `make check` (the symbol
one) and the release path (the floor one, over the built `.app`, the daemon and
every helper). `scripts/prune-xcstrings.py <catalog> <source roots…>` is the
catalogue tidy from the localization section; run it by hand after Xcode has
marked entries stale, never from `make check`, because it writes.

## Output

A report that says: what was built, which of the four floor audits ran and what
they said, which surfaces were actually tested (harness / simulator / vphone /
device / oldest OS), the deb names and digests for both flavours, the tipa and
ipa, the release URL and the owngoal-packages commit.
