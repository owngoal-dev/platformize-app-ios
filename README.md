# platformize-app-ios

A good starting point for packaging native iOS apps.

For command-line tools, see [platformize-bin-ios](https://github.com/owngoal-dev/platformize-bin-ios).

## Included

- `SKILL.md`: app and daemon setup, packaging, and release guidance.
- `template/`: configuration, packaging files, a native Sileo depiction,
  a Pages workflow that loads release notes from GitHub, and an fd-based
  executable watcher for updates and removal.
- `scripts/`: deployment compatibility and SF Symbol checks, plus localization cleanup.

## Get Started

Read [SKILL.md](SKILL.md), then adapt the templates to your app.

Use the largest banner from your README for the depiction and write its Details
copy for your app. Package installation and removal use uikittools triggers for
app registration. Follow the release-workflow setup in the skill.

Run `python3 -m unittest discover -s tests -v` to validate the rendered templates.

Run `scripts/audit-ios-floor.sh` to check deployment compatibility before release.

## License

MIT. See [LICENSE](LICENSE).
