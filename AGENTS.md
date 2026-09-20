# platformize-app-ios — Agent Notes

This repository is a Claude Code skill (`SKILL.md`), the release-gate scripts,
and the repo skeleton they instantiate (`template/`). It is documentation and
scaffolding; there is no build here.

## Hard rules

- **`SKILL.md` is the source of truth.** `README.md` summarises it for humans;
  when they disagree, fix `README.md`.
- **`template/` mirrors the live app repos.** It is the generic part of
  [Fila](https://github.com/owngoal-dev/Fila), with the shared pieces of
  iGhostVT, CocoaInspector and
  [Irisin](https://github.com/Lakr233/Irisin). When one of those changes a
  packaging input, port the change here; when this changes, port it there. Do
  not let them drift.
- **The build scripts stay out of `template/`.** `package-deb.sh`,
  `verify-deb.sh`, the ipa pair, `install-device.sh`, `vphone.sh` and the
  `Makefile` belong to the live repos and change with them. The skill says to
  copy them from the sibling whose daemon shape you picked, which is honest;
  a fork here would be stale and would be copied anyway.
- **Name no specific package manager**, here and in `template/`: say "your
  preferred package manager". Field names such as `SileoDepiction` stay.
- **No `CLAUDE.md`**, here or in `template/`. It is deprecated.
- **Facts come from a device, an SDK or a build, not from memory.** Add a fact
  together with how it was observed (`otool -L`, `nm -m`, a `.tbd` grep, a
  crash report, a device run). Remove it when it stops being true.
- **The scripts must run.** All three were written against a real product
  tree and must keep passing on one before a commit: `scripts/audit-ios-floor.sh
  15.0 <built .app> <daemon>`, `scripts/check-symbol-availability.py 15.0
  <source roots>`, and `scripts/prune-xcstrings.py` on a copy of a live
  catalogue that uses `extractionState: manual` (a second run on its own
  output changes nothing). Do not run the prune script on Fila's catalogues.
- **Review for sensitive information before anything is uploaded or
  published.** A reading job, not a regex. Device facts recorded here are
  generic; never a serial, UDID, hostname or address.

## Why this exists separately from platformize-bin-ios

A CLI is one Mach-O and a package. An app is a bundle, an extension or two, a
daemon that runs as root, a Mach service, two entitlement sets that fail in
opposite directions, an App Group that has to match across wrappers that share
a container, and a UI whose failures are silent. The porting playbook in
`platformize-bin-ios` — SDK header shims, fork/exec, IOKit facts — still
applies to anything native this repo builds; read both when the app links C.

## Where the content came from

`SKILL.md` is the intersection of four shipped repos. Fila is the packaging
reference and the default (fd-over-XPC) daemon. iGhostVT is the session-host
exception (`KeepAlive`, proxy + io). CocoaInspector is the smallest on-demand
daemon. Irisin (published as Lakr233/Irisin; Chromatic/Saily are dead names)
contributed helper-per-job, Swift 6, catalogue pruning and the build-path
rule. In the deployment floor section it is the record of one bug: Fila 0.1.6
terminated at launch on iOS 15 because the iOS 27 SDK's new Swift XPC overlay
was linked non-weakly. Two users, two devices, a clean build and no warning
anywhere. That is the reason the four audits are written down rather than
remembered.
