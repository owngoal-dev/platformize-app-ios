#!/usr/bin/env python3
"""Scaffold a new app repo: the mechanical half of SKILL.md "Template".

Copies `template/`, fills the placeholders it was given, renames and moves the
packaging and app files, takes `Scripts/`, `Makefile` and `.gitignore` from
the committed HEAD of the sibling whose daemon shape was picked and the
CI/Release pair from Irisin's, renames that sibling's name through what it
copied, wires the checklist gate into the Makefile, copies this skill's gate
scripts, and sets the launchd plist's optional keys for the shape. Then it
runs the scaffold checks and prints what is still open.

The template's skeleton becomes `<App>/`, `<App>d/` and `<App>.xcodeproj`: an
app and an on-demand daemon that say hello over XPC and build as they are.

It decides nothing a person has to: it ticks no box in `CHECKLIST.md`, and it
does not reshape the copied packager, Makefile or workflows to this app's
products. A sibling name it could not rename is
printed, not guessed at. The script stays here; nothing of it is copied into
the new repo, so there is nothing to delete after it runs.

The destination must not exist or must be empty. The repo is assembled in a
temporary folder beside it and moved into place only when every step passed.

usage: new-app.py <dest> --name <App> --from <Fila|Inspector|iGhostVT|Irisin>
                  [--floor 15.0] [--id-prefix wiki.qaq] [--repo <Repo>]
                  [--description <one line>] [--package-description <text>]
                  [--banner-url <https url>] [--depiction-description <md>]
                  [--siblings <dir>]
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

# The org is the GitHub owner; a checkout is found at <siblings>/<name> or
# <siblings>/../<org>/<name>, the way the repos are laid out on GitHub.
SIBLINGS = {
    'Fila': ('owngoal-dev', 'on-demand'),
    'Inspector': ('owngoal-dev', 'on-demand'),
    'iGhostVT': ('owngoal-dev', 'session host'),
    'Irisin': ('Lakr233', 'helper-per-job'),
}
SIBLING_FILES = ['Scripts', 'Makefile', '.gitignore']
WORKFLOW_FILES = ['.github/workflows/ci.yml', '.github/workflows/release.yml']
# Irisin's own spellings that a new repo does not share (SKILL.md "Template").
WORKFLOW_SPELLINGS = [('main-4.0', 'main'), ('Documentation/Releases', 'Documents/Releases')]
GATE_SCRIPTS = [
    'audit-ios-floor.sh', 'check-symbol-availability.py', 'check-checklist.sh',
    'check-gpu-entitlements.py', 'check-launchd-paths.py',
    'check-accessibility.py', 'check-stale-strings.py',
]
# Every sibling's ids start with this; the app bundle id is not always the
# lowercase name (Inspector's is wiki.qaq.Inspector), so ids are mapped as ids.
SIBLING_ID_PREFIX = 'wiki.qaq'
PACKAGER_KEYS = {'PREFIX', 'VERSION', 'ARCHITECTURE', 'FLAVOR', 'INSTALLED_SIZE', 'ROOTFS'}
SWEEP = re.compile(r'fila|ighostvt|inspector|irisin|chromatic|saily', re.IGNORECASE)
OPTIONAL_KEY = '\t<!-- <key>{0}</key><true/> -->\n'
SESSION_LIMITS = (
    '\t<key>SoftResourceLimits</key>\n'
    '\t<dict>\n'
    '\t\t<key>NumberOfFiles</key>\n'
    '\t\t<integer>10240</integer>\n'
    '\t</dict>\n'
)


class ScaffoldError(Exception):
    pass


def replace_once(text, old, new, where):
    if text.count(old) != 1:
        raise ScaffoldError(f'{where}: expected exactly one {old!r}; the template changed, update new-app.py')
    return text.replace(old, new)


def find_sibling(name, siblings):
    org = SIBLINGS[name][0]
    for candidate in (siblings / name, siblings.parent / org / name):
        if (candidate / '.git').exists():
            return candidate
    raise ScaffoldError(f'{name} is not checked out at {siblings / name} or {siblings.parent / org / name}; pass --siblings')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout


def copy_committed(repo, paths, dest):
    """Copy paths from HEAD, so an uncommitted edit in the sibling stays there."""
    present = [path for path in paths if git(repo, 'ls-tree', '--name-only', 'HEAD', '--', path).strip()]
    missing = sorted(set(paths) - set(present))
    if present:
        archive = subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', 'HEAD', '--', *present],
                                 check=True, capture_output=True).stdout
        subprocess.run(['tar', '-x', '-C', str(dest)], input=archive, check=True)
    return present, missing


def files_under(dest, paths):
    for path in paths:
        target = dest / path
        if target.is_dir():
            yield from sorted(p for p in target.rglob('*') if p.is_file() and not p.is_symlink())
        elif target.is_file():
            yield target


def rename_through(dest, files, pairs):
    """Replace each (old, new) in every text file; return {file: count}."""
    changed = {}
    for path in files:
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        count = 0
        for old, new in pairs:
            count += text.count(old)
            text = text.replace(old, new)
        if count:
            path.write_text(text)
            changed[str(path.relative_to(dest))] = count
    return changed


def rename_ids(dest, files, sibling, prefix, slug):
    """Map `wiki.qaq.<sibling>` in any case to `<prefix>.<slug>`; return {file: count}.

    Runs before the plain rename, so the app's bundle id, the daemon's and the
    service's all come out as the template spells them, whatever case the
    sibling used.
    """
    pattern = re.compile(re.escape(f'{SIBLING_ID_PREFIX}.') + f'(?i:{re.escape(sibling)})')
    changed = {}
    for path in files:
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        text, count = pattern.subn(f'{prefix}.{slug}', text)
        if count:
            path.write_text(text)
            changed[str(path.relative_to(dest))] = count
    return changed


def merge_counts(*counts):
    merged = {}
    for count in counts:
        for path, number in count.items():
            merged[path] = merged.get(path, 0) + number
    return merged


def name_pairs(old, new):
    pairs = [(old, new), (old.lower(), new.lower()), (old.upper(), new.upper())]
    return [pair for i, pair in enumerate(pairs) if pair[0] not in [p[0] for p in pairs[:i]]]


def rename_paths(dest, files, pairs):
    moved = []
    for path in files:
        name = path.name
        for old, new in pairs:
            name = name.replace(old, new)
        if name != path.name:
            path.rename(path.with_name(name))
            moved.append(f'{path.relative_to(dest)} -> {name}')
    return moved


def fill_placeholders(dest, values):
    for path in sorted(dest.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix == '.json':
            # Through the encoder, so quotes and multi-line Markdown stay valid.
            def fill(value):
                if isinstance(value, str):
                    for key, item in values.items():
                        value = value.replace(f'@{key}@', item)
                    return value
                if isinstance(value, list):
                    return [fill(item) for item in value]
                if isinstance(value, dict):
                    return {key: fill(item) for key, item in value.items()}
                return value
            path.write_text(json.dumps(fill(json.loads(path.read_text())), indent=2, ensure_ascii=False) + '\n')
        else:
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue  # the icon
            for key, value in values.items():
                # The token and nothing around it: see "Replace the token and
                # nothing around it" in SKILL.md.
                text = text.replace(f'@{key}@', value)
            path.write_text(text)


def shape_daemon_plist(path, shape):
    text = path.read_text()
    enabled = {
        'on-demand': [],
        'session host': ['RunAtLoad', 'KeepAlive'],
        'helper-per-job': ['AbandonProcessGroup'],
    }[shape]
    for key in ('AbandonProcessGroup', 'RunAtLoad', 'KeepAlive'):
        marker = OPTIONAL_KEY.format(key)
        line = f'\t<key>{key}</key>\n\t<true/>\n' if key in enabled else ''
        if key == 'KeepAlive' and shape == 'session host':
            line += SESSION_LIMITS
        text = replace_once(text, marker, line, path.name)
    if shape == 'session host':
        text = replace_once(text, '\t<!-- Background is conservative. On-demand daemons often use Adaptive. -->\n', '', path.name)
        text = replace_once(text, '<key>ProcessType</key>\n\t<string>Background</string>',
                            '<key>ProcessType</key>\n\t<string>Interactive</string>', path.name)
    path.write_text(text)
    plistlib.loads(path.read_bytes())


def wire_checklist(makefile):
    text = makefile.read_text()
    if re.search(r'^checklist\s*:', text, re.MULTILINE):
        return 'already has a checklist rule; left alone'
    rules = re.findall(r'^check\s*:(?!=)', text, re.MULTILINE)
    if len(rules) != 1:
        raise ScaffoldError(f'Makefile: expected one `check:` rule, found {len(rules)}; wire the checklist gate by hand')
    targets = ['check'] + [t for t in ('harness', 'sim', 'vphone')
                           if re.search(rf'^{t}\s*:(?!=)', text, re.MULTILINE)]
    gate = ('checklist:\n\t@Scripts/check-checklist.sh CHECKLIST.md\n\n'
            f'{" ".join(targets)}: checklist\n\n')
    match = re.search(r'^check\s*:(?!=)', text, re.MULTILINE)
    text = text[:match.start()] + gate + text[match.start():]
    if re.search(r'^\.PHONY\s*:', text, re.MULTILINE):
        text = re.sub(r'^\.PHONY\s*:', '.PHONY: checklist', text, count=1, flags=re.MULTILINE)
    else:
        text = '.PHONY: checklist\n' + text
    makefile.write_text(text)
    return f'gate added before `check:`; `{" ".join(targets)}` depend on it'


def ensure_ignored(gitignore, entries):
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    stripped = {line.strip().strip('/') for line in lines}
    added = [entry for entry in entries if entry.strip('/') not in stripped]
    if added:
        text = gitignore.read_text() if gitignore.exists() else ''
        if text and not text.endswith('\n'):
            text += '\n'
        gitignore.write_text(text + ''.join(f'{entry}\n' for entry in added))
    return added


def check_scaffold(repo, daemon_id, copied):
    """Findings, not failures: every one is a decision left for the agent.

    `copied` is what came from a sibling. Its `@TOKEN@`s are the packager's own
    substitutions, not placeholders.
    """
    findings = []
    for path in sorted(repo.rglob('*')):
        if '.git' in path.parts or path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(repo)
        if str(rel) not in copied:
            left = sorted(set(re.findall(r'@([A-Z_]+)@', text)) - PACKAGER_KEYS)
            if left:
                findings.append(f'placeholder  {rel}: ' + ', '.join(f'@{k}@' for k in left))
        if rel.name == 'AGENTS.md':
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if SWEEP.search(line):
                findings.append(f'sibling name {rel}:{number}: {line.strip()[:100]}')
    for hook in ('postinst', 'prerm', 'postrm'):
        path = repo / 'Packaging/DEBIAN' / hook
        text = path.read_text()
        if re.search(r'[A-Za-z0-9_@]2>', text):
            findings.append(f'hook         {hook}: a redirect lost its space')
        if text.count(daemon_id) != 1:
            findings.append(f'hook         {hook}: names {daemon_id} {text.count(daemon_id)} times, not once')
        result = subprocess.run(['sh', '-n', str(path)], capture_output=True, text=True)
        if result.returncode:
            findings.append(f'hook         {hook}: sh -n: {result.stderr.strip()}')
    for path in sorted((repo / 'Packaging').glob('*.plist')) + sorted((repo / 'Packaging').glob('*.entitlements')):
        try:
            plistlib.loads(path.read_bytes())
        except Exception as error:  # noqa: BLE001 — any parse failure is the finding
            findings.append(f'plist        {path.relative_to(repo)}: {error}')
    json.loads((repo / 'Documents/Site/depiction.json').read_text())
    if shutil.which('actionlint'):
        workflows = sorted(str(p) for p in (repo / '.github/workflows').glob('*.yml'))
        result = subprocess.run(['actionlint', *workflows], capture_output=True, text=True, cwd=repo)
        for line in result.stdout.splitlines():
            if re.match(r'\S+:\d+:\d+: ', line):
                findings.append(f'actionlint   {line.strip()}')
    else:
        findings.append('actionlint   not installed; the workflows were not linted')
    return findings


def scaffold(args, work):
    name = args.name
    slug = name.lower()
    sibling_name = args.sibling
    shape = SIBLINGS[sibling_name][1]
    sibling = find_sibling(sibling_name, args.siblings)
    irisin = sibling if sibling_name == 'Irisin' else find_sibling('Irisin', args.siblings)
    prefix = args.id_prefix
    values = {
        'APP_NAME': name,
        'REPO': args.repo or name,
        'BUNDLE_ID': f'{prefix}.{slug}',
        'DAEMON': f'{slug}d',
        'DAEMON_ID': f'{prefix}.{slug}d',
        'SERVICE_NAME': f'{prefix}.{slug}.service',
        'APP_CLIENT_ENTITLEMENT': f'{prefix}.{slug}.client',
        'PACKAGE_ID': f'{prefix}.{slug}',
        'MINIMUM_IOS_VERSION': args.floor,
    }
    for key, value in (('ONE_LINE_DESCRIPTION', args.description),
                       ('PACKAGE_DESCRIPTION', args.package_description),
                       ('BANNER_URL', args.banner_url),
                       ('DEPICTION_DESCRIPTION', args.depiction_description)):
        if value is not None:
            values[key] = value
    report = {'values': values, 'shape': shape}

    shutil.copytree(ROOT / 'template', work, symlinks=True, dirs_exist_ok=True)
    fill_placeholders(work, values)
    base = work / 'Configuration/Base.xcconfig'
    base.write_text(re.sub(r'^IPHONEOS_DEPLOYMENT_TARGET = .*$', f'IPHONEOS_DEPLOYMENT_TARGET = {args.floor}',
                           base.read_text(), count=1, flags=re.MULTILINE))

    packaging = work / 'Packaging'
    (packaging / 'APP.entitlements').rename(packaging / f'{name}.entitlements')
    (packaging / 'DAEMON.entitlements').rename(packaging / f'{name}d.entitlements')
    daemon_plist = packaging / f'{values["DAEMON_ID"]}.plist'
    (packaging / 'DAEMON.plist').rename(daemon_plist)
    if shape == 'helper-per-job':
        (packaging / 'HELPER.entitlements').rename(packaging / f'{slug}-install.entitlements')
    else:
        (packaging / 'HELPER.entitlements').unlink()
    shape_daemon_plist(daemon_plist, shape)

    # The skeleton: an app and an on-demand daemon that say hello over XPC, in
    # a two-target project. It builds as it is, so the first build tests the
    # packaging rather than the boilerplate.
    application = work / 'App/Application'
    application.mkdir()
    for source in ('AppDelegate.swift', 'SceneRestorationReset.swift', 'ExecutableWatch.swift', 'QuietExit.swift'):
        (work / 'App' / source).rename(application / source)
    (work / 'App').rename(work / name)
    (work / 'Daemon').rename(work / f'{name}d')
    (work / 'APP.xcodeproj').rename(work / f'{name}.xcodeproj')

    copied, missing = copy_committed(sibling, SIBLING_FILES, work)
    if 'Scripts' not in copied or 'Makefile' not in copied:
        raise ScaffoldError(f'{sibling} has no committed Scripts/ or Makefile')
    report['sibling'] = (sibling_name, git(sibling, 'rev-parse', '--short', 'HEAD').strip(),
                         len(git(sibling, 'status', '--porcelain').splitlines()))
    report['sibling_missing'] = missing
    workflows, missing = copy_committed(irisin, WORKFLOW_FILES, work)
    if missing:
        raise ScaffoldError(f'{irisin} has no committed ' + ', '.join(missing))
    report['irisin'] = git(irisin, 'rev-parse', '--short', 'HEAD').strip()

    # The gates replace the sibling's copies verbatim, before the rename: they
    # travel unchanged and name no sibling.
    scripts = work / 'Scripts'
    for script in GATE_SCRIPTS:
        shutil.copy2(ROOT / 'scripts' / script, scripts / script)
    gates = {scripts / script for script in GATE_SCRIPTS}
    sibling_files = [path for path in files_under(work, copied) if path not in gates]
    workflow_files = list(files_under(work, workflows))
    report['renamed'] = merge_counts(
        rename_ids(work, sibling_files, sibling_name, prefix, slug),
        rename_through(work, sibling_files, name_pairs(sibling_name, name)),
        rename_ids(work, workflow_files, 'Irisin', prefix, slug),
        rename_through(work, workflow_files, name_pairs('Irisin', name) + WORKFLOW_SPELLINGS),
    )
    report['moved'] = rename_paths(work, sibling_files, name_pairs(sibling_name, name))
    from_sibling = {str(path.relative_to(work))
                    for path in files_under(work, copied + workflows) if path not in gates}
    makefile_text = (work / 'Makefile').read_text()
    report['unwired'] = [s for s in GATE_SCRIPTS if s != 'check-checklist.sh' and s not in makefile_text]
    report['gate'] = wire_checklist(work / 'Makefile')
    report['ignored'] = ensure_ignored(work / '.gitignore', ['.build/', '.swiftpm/'])
    report['findings'] = check_scaffold(work, values['DAEMON_ID'], from_sibling)
    return report


def print_report(dest, report):
    values = report['values']
    sibling, commit, dirty = report['sibling']
    print(f'Scaffolded {values["APP_NAME"]} at {dest}')
    print(f'  shape       {report["shape"]}; Scripts/, Makefile, .gitignore from {sibling} {commit}'
          + (f' ({dirty} uncommitted changes there were not copied)' if dirty else ''))
    print(f'  workflows   ci.yml and release.yml from Irisin {report["irisin"]}')
    print(f'  ids         {values["BUNDLE_ID"]}, daemon {values["DAEMON_ID"]}, '
          f'service {values["SERVICE_NAME"]}, client {values["APP_CLIENT_ENTITLEMENT"]}')
    print(f'  floor       iOS {values["MINIMUM_IOS_VERSION"]} (Base.xcconfig and the placeholders)')
    print(f'  Makefile    {report["gate"]}')
    if report['sibling_missing']:
        print(f'  not in {sibling}: ' + ', '.join(report['sibling_missing']))
    if report['ignored']:
        print('  .gitignore  added ' + ', '.join(report['ignored']))
    print(f'  renamed     {sum(report["renamed"].values())} occurrences in {len(report["renamed"])} files:')
    for path, count in sorted(report['renamed'].items()):
        print(f'      {count:4}  {path}')
    for move in report['moved']:
        print(f'      moved {move}')
    print('\nLeft open — review each; none of these is a bug in the scaffold:')
    for script in report['unwired']:
        print(f'  unwired      Scripts/{script} is copied but the Makefile never names it')
    for finding in report['findings']:
        print(f'  {finding}')
    print(f'''
Still yours, in this order:
  1. git diff the renamed files against {sibling}: a rename is not a rewrite.
     The Makefile, packager and workflows still carry {sibling}'s products,
     binaries, entitlement loops and extra jobs (SKILL.md "Template").
  2. The Xcode project is a two-target skeleton ({values["APP_NAME"]}, {values["APP_NAME"]}d) that
     builds as it is; add targets by hand, objectVersion pinned, no generator.
  3. AGENTS.md's <...> prose, the daemon plist's header comment,
     Documents/Site/icon.png, LICENSE's holder and year.
  4. CHECKLIST.md, top to bottom. `make check` refuses to run until it is done.''')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('dest', type=Path)
    parser.add_argument('--name', required=True, help='the app name, e.g. Xrash')
    parser.add_argument('--from', dest='sibling', required=True, choices=sorted(SIBLINGS),
                        help='the sibling whose daemon shape this app takes')
    parser.add_argument('--floor', default='15.0', help='IPHONEOS_DEPLOYMENT_TARGET (default 15.0)')
    parser.add_argument('--id-prefix', default='wiki.qaq', help='bundle id prefix (default wiki.qaq)')
    parser.add_argument('--repo', help='GitHub repository name under owngoal-dev (default: --name)')
    parser.add_argument('--description', help='@ONE_LINE_DESCRIPTION@')
    parser.add_argument('--package-description', help='@PACKAGE_DESCRIPTION@, one paragraph')
    parser.add_argument('--banner-url', help='@BANNER_URL@, the largest banner the README shows')
    parser.add_argument('--depiction-description', help='@DEPICTION_DESCRIPTION@, Markdown')
    parser.add_argument('--siblings', type=Path, default=ROOT.parent,
                        help='folder holding the sibling checkouts (default: beside this skill)')
    args = parser.parse_args()

    if not re.fullmatch(r'[A-Z][A-Za-z0-9]*', args.name):
        parser.error('--name is letters and digits starting with a capital, e.g. Xrash')
    if not re.fullmatch(r'\d+\.\d+', args.floor):
        parser.error('--floor is major.minor, e.g. 15.0')
    if not re.fullmatch(r'[a-z0-9]+(\.[a-z0-9]+)+', args.id_prefix):
        parser.error('--id-prefix is a reverse-DNS prefix, e.g. wiki.qaq')
    for flag in ('description', 'package_description'):
        if '\n' in (getattr(args, flag) or ''):
            parser.error(f'--{flag.replace("_", "-")} is one line: it lands in a Debian control field')
    if args.banner_url and not args.banner_url.startswith('https://'):
        parser.error('--banner-url is an https URL')

    dest = args.dest.resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        print(f'error: {dest} exists and is not an empty folder; nothing was written', file=sys.stderr)
        return 73
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f'.{dest.name}.scaffold-', dir=dest.parent))
    try:
        report = scaffold(args, work)
        if dest.exists():
            dest.rmdir()
        os.rename(work, dest)
    except (ScaffoldError, subprocess.CalledProcessError, OSError) as error:
        shutil.rmtree(work, ignore_errors=True)
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) and error.stderr else error
        print(f'error: {detail}; nothing was written', file=sys.stderr)
        return 1
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    print_report(dest, report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
