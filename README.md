# platformize-app-ios

A [Claude Code](https://claude.com/claude-code) skill for shipping a native iOS
**app** — with its own root LaunchDaemon — to **jailbroken devices**: one Xcode
project, packaged for both **roothide** and **rootless** bootstraps, plus a
TrollStore `.tipa` and a sideload `.ipa`, released from GitHub Actions and
served by the
[OwnGoal Studio APT repository](https://github.com/owngoal-dev/owngoal-packages).

It is the distilled procedure behind
[Fila](https://github.com/owngoal-dev/Fila) (file manager),
[iGhostVT](https://github.com/owngoal-dev/iGhostVT) (terminal) and
CocoaInspector (process inspector): how an unprivileged app and a root daemon
divide the work, what the packaging contract is, and what silently raises the
deployment floor out from under a build that looks clean.

Its sibling [platformize-bin-ios](https://github.com/owngoal-dev/platformize-bin-ios)
does the same for command-line tools. If what you are shipping has no `.app`,
use that one.

## What you get

| path | what it is |
| --- | --- |
| `SKILL.md` | the skill: the app/daemon contract, the deployment-floor audit, layout, build and test surfaces, localization verification, publishing |
| `scripts/audit-ios-floor.sh` | proves a built product can actually launch on the OS it claims: required libraries, build versions, embedded frameworks, weak symbols |
| `scripts/check-symbol-availability.py` | fails when a source tree names an SF Symbol newer than the deployment target — the failure that never crashes and never warns |
| `template/` | the packaging inputs, the two xcconfigs, the XPC constant shim, and an `AGENTS.md` skeleton |
| `AGENTS.md` (`CLAUDE.md` links to it) | notes for agents working on this repository |

The build scripts are deliberately **not** in `template/`: they move with the
live repos, so the skill tells you to copy them from the closest sibling rather
than keeping a fork that goes stale.

## Install

```sh
git clone https://github.com/owngoal-dev/platformize-app-ios ~/.claude/skills/platformize-app-ios
```

Then ask for it by name, or just describe the job: "package this app as a deb
for roothide and rootless", "give it a root daemon over XPC", "why does it not
launch on iOS 15".

## The one thing to take away

A clean build against this year's SDK is not evidence that the app runs on the
OS its deployment target claims. The linker believes the SDK's availability
metadata, and where that metadata is wrong the app dies in dyld before `main` on
the old device — with no warning anywhere in the build, and no way to find out
except from a user. `scripts/audit-ios-floor.sh` is that missing warning.

## License

MIT. See [LICENSE](LICENSE).
