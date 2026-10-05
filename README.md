# platformize-app-ios

A good starting point for packaging native iOS apps.

For command-line tools, see [platformize-bin-ios](https://github.com/owngoal-dev/platformize-bin-ios).

## Included

- `SKILL.md`: app and daemon setup, packaging, third-party license
  collection, and release guidance.
- `template/`: a one-time `CHECKLIST.md` to finish before writing code,
  configuration, packaging files, a native depiction, a Pages workflow that
  loads release notes from GitHub, an fd-based executable watcher for updates
  and removal, a quiet exit, the roothide root check, and a skeleton that
  builds as it is: a two-target Xcode project, an app, and an on-demand
  daemon that authenticates the app and answers its hello over XPC.
- `scripts/`: `new-app.py`, which scaffolds a new app repo, the checklist
  gate for `make check`, deployment compatibility
  and SF Symbol checks, an accessibility gate that refuses a label UIKit will
  never read, a gate that refuses a string key Xcode marked stale, a gate
  that refuses app entitlements missing the GPU list, plus
  localization cleanup that keeps a translation it cannot account for.

## Get Started

Read [SKILL.md](SKILL.md), pick the daemon shape, then scaffold the repo in
one run:

```sh
scripts/new-app.py ../MyApp --name MyApp --from Inspector --description "…"
```

It copies the template, fills the placeholders, takes `Scripts/`, `Makefile`
and the CI/Release pair from the sibling checkouts, renames them, wires the
checklist gate, and prints what is still open. Nothing of it is copied into
the new repo. Then work through `CHECKLIST.md`: `make check` refuses to run
until every box is ticked.

Use the largest banner from your README for the depiction and write its Details
copy for your app. Package installation and removal use uikittools triggers for
app registration. Follow the release-workflow setup in the skill.

Run `python3 -m unittest discover -s tests -v` to validate the rendered templates.

Run `scripts/audit-ios-floor.sh` to check deployment compatibility before release.

## License

MIT. See [LICENSE](LICENSE).
