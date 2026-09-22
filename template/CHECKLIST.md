# @APP_NAME@ — Checklist

One time, before any code is written. `make check` runs
`Scripts/check-checklist.sh` first, and every build target depends on it, so
nothing builds until every box below is ticked.

Tick a box only after doing or deciding the thing, never to get past the gate.
An item that does not apply here is ticked with the reason written after it.
A decision is recorded where the item says (usually `AGENTS.md`), so the next
reader finds the answer and not only the tick. "SKILL.md" is
platformize-app-ios's; the quoted name is its section.

## Identity and rename

- [ ] The daemon shape is chosen (on-demand, session host or helper-per-job) and is the one-sentence idea at the top of `AGENTS.md`.
      SKILL.md "Pick the daemon shape".
- [ ] `Scripts/`, `Makefile`, `.gitignore` and the release workflow are copied from the sibling of that shape, and `.gitignore` ignores `.build/` and `.swiftpm/`.
      SKILL.md "Template".
- [ ] `grep -rn '@[A-Z_]*@' --exclude-dir=.git .` shows only the packager's tokens (`@PREFIX@`, `@VERSION@`, `@ARCHITECTURE@`, `@FLAVOR@`, `@INSTALLED_SIZE@`).
      SKILL.md "Template", Placeholders.
- [ ] The sibling-name sweep prints nothing, `DERIVED_DATA`, `mktemp` prefixes and the workflow's `concurrency.group` included.
      SKILL.md "Template": the rename is finished when the sweep is empty.
- [ ] The bundle id, daemon id, Mach service and client entitlement are all named after this app and shared with no other.
      SKILL.md "The contract", peer authentication.
- [ ] The hooks survived the rename: `grep -nE '[A-Za-z0-9_@]2>' Packaging/DEBIAN/*` prints nothing and the daemon id appears once in each hook.
      SKILL.md "Template": replace the token and nothing around it.
- [ ] `AGENTS.md` has no placeholder left and no section that is untrue here; there is no `CLAUDE.md`, and no file names a package manager.
      `AGENTS.md`; SKILL.md "The contract".

## Daemon and trust boundary

- [ ] The wire is a closed list of operations written down in `AGENTS.md`; none of them is `exec(path, argv)`.
      SKILL.md "The contract": nothing generic executes.
- [ ] The authenticator's checks and their order are written down, and `platform-application` is required of the peer only if `Packaging/<App>.entitlements` carries it.
      SKILL.md "The contract": peer authentication.
- [ ] The backend is resolved at runtime: `hello` answers an enum carrying the install root, and no build flag or compilation condition tells the wrappers apart.
      SKILL.md "The contract", first bullet.
- [ ] A missing daemon is *Connecting…*; the fallback grace period is a duration, and the hello timeout is a chosen number of seconds guarded by connection generation.
      SKILL.md "The contract": a hello has a bound.
- [ ] Every optional key in the launchd plist (`KeepAlive`, `RunAtLoad`, `AbandonProcessGroup`, `ProcessType`) is enabled or deleted to match the shape.
      `Packaging/<daemon id>.plist`; SKILL.md "Template".
- [ ] Nothing third-party links into the daemon, and whether a CLI (a second peer) exists is decided and written down.
      SKILL.md "The contract"; "Layout".

## Bootstrap detection

- [ ] No install prefix is written in Swift: the daemon derives it from its own `proc_pidpath` and refuses to start from an unrecognised path.
      SKILL.md "The contract".
- [ ] `Shared/RoothideRoot.swift` is in the project unchanged and is the only bootstrap check made before `hello`: no `dlopen` of libroothide through `.jbroot`, no "`/var/jb`, so rootless" fallback.
      `Shared/RoothideRoot.swift`; SKILL.md "The contract": roothide is recognised by the process's own path.
- [ ] Every path is canonicalised (`realpath(3)`, NUL rejected) before a decision is made about it.
      SKILL.md "The contract".

## Packaging and entitlements

- [ ] The entitlement files and the launchd plist carry this app's names; `HELPER.entitlements` is renamed for a helper-per-job daemon and deleted otherwise.
      SKILL.md "Template".
- [ ] The App Group key is kept only if an extension shares a container and the packager substitutes `$(APP_GROUP_IDENTIFIER)`.
      `Packaging/<App>.entitlements`.
- [ ] `storage.AppBundles` and `storage.AppDataContainers` are on the app and on the daemon if either reads another app's bundle or container, and on neither if not; every data-vault class is on the process that writes there.
      `Packaging/*.entitlements`; SKILL.md "The contract": `no-sandbox` does not open another app's bundle.
- [ ] `com.apple.security.iokit-user-client-class` is present if the app draws with Metal itself, absent if not.
      `Packaging/<App>.entitlements`.
- [ ] `control` depends on `firmware (>= <floor>)`, `uikittools` and `launchctl`; no hook calls `uicache`; `postinst` boots out system, user/501 and gui/501.
      `Packaging/DEBIAN/`; SKILL.md "The contract".
- [ ] Versions and the deployment target live in `Configuration/*.xcconfig` only, `objectVersion` is pinned, `make check` rejects both, and one build-number style is chosen.
      SKILL.md "The contract".
- [ ] The floor is chosen; `audit-ios-floor.sh` and `check-symbol-availability.py` are in `Scripts/` and wired in; XPC constants are read through `Shared/XPCShim` only.
      SKILL.md "The deployment floor is not what you set".
- [ ] The packager ad-hoc signs every embedded library, re-reads entitlements from the signed binaries, and greps every binary for the build path.
      SKILL.md "The contract".

## App lifecycle

- [ ] `main.swift` calls `UIApplicationMain` by hand after the saved-state reset and the app delegate is not `@main`, or the exception is written in `AGENTS.md`.
      `App/main.swift`, `App/SceneRestorationReset.swift`; SKILL.md "The contract".
- [ ] `ExecutableWatch.swift` is in the project unchanged, started once early in `didFinishLaunching`; omitted only for a self-updating installer.
      `App/ExecutableWatch.swift`.
- [ ] `QuietExit.swift` is in the project unchanged and is the only caller of `exit` in the app.
      `App/QuietExit.swift`; SKILL.md "The contract": Quit never calls `exit` from the foreground.
- [ ] The root is a real tab bar for more than three top-level pages and a single navigation stack for three or fewer, never a `UITabBarController` with its bar hidden.
      SKILL.md "Gotchas observed across the apps".

## Accessibility

- [ ] `Scripts/check-accessibility.py` is copied in and wired into `make check`, so a label on a cell or view that UIKit will never read fails the build.
      SKILL.md "The contract": a label on a container that is not an accessibility element is never read.
- [ ] Every icon-only button and bar button item is labelled as it is written, the label is set beside the state it describes rather than once at construction, and no label repeats what VoiceOver already reads.
      SKILL.md "The contract": a control with no text has no name.
- [ ] State that is only drawn — a checkmark, a selection, a progress fill — is an `accessibilityValue` or a trait, and nothing posts `.layoutChanged` on a routine view swap.
      SKILL.md "The contract": state that is only drawn is not spoken; accessibility is semantics, never behaviour.

## Assets and icons

- [ ] The app icon is never looked up by name: every in-app use draws an ordinary image set, `AppIconMark`, and no source says `UIImage(named: "AppIcon")`.
      SKILL.md "The contract": the app icon is never looked up by name.
- [ ] Another app's icon is asked of IconServices first; the fallback reads `CFBundleIconFiles` names as files with `UIImage(contentsOfFile:)`, never `UIImage(named:in:)`. Ticked as not applicable if the app shows none.
      SKILL.md "The contract", same bullet.
- [ ] `Documents/Site/icon.png` exists and the depiction's banner is the largest image the README references.
      SKILL.md "Native Depiction".

## Strings and licences

- [ ] One catalogue discipline is chosen (compiler `.stringsdata` with no `extractionState`, or `manual` keys pruned by hand) and its gate is in `make check`.
      SKILL.md "Localization is verified against the compiler".
- [ ] `Scripts/check-stale-strings.py` is copied in and wired into `make check`, so a key Xcode reaped during a build cannot ride into a commit unseen.
      SKILL.md "Localization is verified against the compiler": nothing else catches the marker.
- [ ] Every target's source root is written down for `prune-xcstrings.py` — app, extensions, macOS, visionOS, packages — and `--delete-orphans` is used only if this app has one target.
      SKILL.md: stale does not mean dead; a missing root deletes live strings and their translations.
- [ ] One licence discipline is chosen (scanned or reviewed), and the collector, the Collect Licenses build phase, the screen and both gates are in before the first dependency.
      SKILL.md "Licenses are collected by the build".
- [ ] `LICENSE` names the right holder and year, and every dependency's licence is read before its API: no GPL, no LGPL.
      `LICENSE`; SKILL.md "Licenses", vendored source.

## Release and debugging

- [ ] `ci.yml` and `release.yml` are both in, copied as a pair: CI builds and keeps `<app>-<sha>` for thirty days, Release waits for that run, compiles nothing, and publishes the artifact CI verified.
      SKILL.md "Publishing": CI builds, Release publishes what CI built.
- [ ] The release workflow is named `Release`, shaped test ‖ compile → release, and publishes one dSYM zip per build listed in `SHA256SUMS`.
      SKILL.md "Publishing"; "Native Depiction".
- [ ] CI's concurrency keys a push on `github.sha` and a pull request on `github.ref`, so a push's run survives to be published by a tag on that commit.
      SKILL.md "Publishing": the concurrency keys are not decoration.
- [ ] `<docs>/Releases/` exists and the first release's note is written before its tag: a headline sentence, a bullet per user-visible change, a closing line naming the package and `SHA256SUMS`.
      SKILL.md "Publishing": the release notes are a file in the repo.
- [ ] Pages is set to GitHub Actions and `manifest.json` points its icon at the Pages URL.
      SKILL.md "Publishing".
- [ ] Release builds are `dwarf-with-dsym`, and the dSYM of every build installed on a device is kept until that build is gone from the device.
      SKILL.md "A crash is read before anything is changed".
- [ ] The sensitive-information read-through is a step of every push, tag and release, and `AGENTS.md` says so.
      SKILL.md "The contract".
