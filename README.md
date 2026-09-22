# platformize-app-ios

A good starting point for packaging native iOS apps.

For command-line tools, see [platformize-bin-ios](https://github.com/owngoal-dev/platformize-bin-ios).

## Included

- `SKILL.md`: app and daemon setup, packaging, third-party license
  collection, and release guidance.
- `template/`: a one-time `CHECKLIST.md` to finish before writing code,
  configuration, packaging files, a native depiction, a Pages workflow that
  loads release notes from GitHub, an fd-based executable watcher for updates
  and removal, a quiet exit, and the roothide root check.
- `scripts/`: the checklist gate for `make check`, deployment compatibility
  and SF Symbol checks, an accessibility gate that refuses a label UIKit will
  never read, a gate that refuses a string key Xcode marked stale, plus
  localization cleanup that keeps a translation it cannot account for.

## Get Started

Read [SKILL.md](SKILL.md), then adapt the templates to your app. Work through
`CHECKLIST.md` first: `make check` refuses to run until every box is ticked.

Use the largest banner from your README for the depiction and write its Details
copy for your app. Package installation and removal use uikittools triggers for
app registration. Follow the release-workflow setup in the skill.

Run `python3 -m unittest discover -s tests -v` to validate the rendered templates.

Run `scripts/audit-ios-floor.sh` to check deployment compatibility before release.

## License

MIT. See [LICENSE](LICENSE).
