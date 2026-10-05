"""Scaffold an app from fake sibling checkouts and read what it wrote."""
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/new-app.py'

MAKEFILE = '''# {name} build
DERIVED_DATA ?= /private/tmp/{slug}-deriveddata
.PHONY: all check harness
check:
\t@echo checked {name}
harness:
\t@echo harness
'''
PACKAGER = '''#!/bin/sh
# usage: package-deb.sh <{name}.app> <{slug}d>
sed -e "s|@PACKAGE_ID@|$1|" control
[ "$bundle_identifier" = wiki.qaq.{name} ] && echo wiki.qaq.{slug}d wiki.qaq.{slug}.service
tmp="$(mktemp -d /private/tmp/{slug}-deb.XXXXXX)"
'''
CI = '''name: CI
on:
  push:
    branches:
      - main-4.0
concurrency:
  group: irisin-${{ github.workflow }}-${{ github.sha }}
jobs:
  build:
    runs-on: macos-26
    steps:
      - run: echo "Irisin $GITHUB_SHA"
'''
RELEASE = '''name: Release
on:
  push:
    tags: ['v*']
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: test -f "Documentation/Releases/${GITHUB_REF_NAME#v}.md" && echo wiki.qaq.irisin
'''


def commit(repo, files):
    repo.mkdir(parents=True)
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    for args in (['init', '-q'], ['add', '-A'],
                 ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init']):
        subprocess.run(['git', '-C', str(repo), *args], check=True)


def sibling(name):
    slug = name.lower()
    return {
        'Makefile': MAKEFILE.format(name=name, slug=slug),
        'Scripts/package-deb.sh': PACKAGER.format(name=name, slug=slug),
        # The sibling's copy of a gate is replaced by this skill's, not renamed.
        'Scripts/check-gpu-entitlements.py': f'# {name} copy\n',
        '.gitignore': '.DS_Store\n',
    }


class NewAppTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.siblings = self.temp / 'owngoal-dev'
        commit(self.siblings / 'Inspector', sibling('Inspector'))
        commit(self.siblings / 'iGhostVT', sibling('iGhostVT'))
        irisin = sibling('Irisin')
        irisin['.github/workflows/ci.yml'] = CI
        irisin['.github/workflows/release.yml'] = RELEASE
        # Irisin lives under another owner; the script looks beside the org.
        commit(self.temp / 'Lakr233/Irisin', irisin)

    def scaffold(self, *args, dest='Foo'):
        return subprocess.run([str(SCRIPT), str(self.temp / dest), '--name', 'Foo',
                               '--siblings', str(self.siblings), *args],
                              capture_output=True, text=True)

    def test_on_demand_scaffold_is_renamed_and_gated(self):
        # Uncommitted work in the sibling stays there.
        (self.siblings / 'Inspector/Scripts/package-deb.sh').write_text('half-edited\n')
        result = self.scaffold('--from', 'Inspector', '--floor', '16.0',
                               '--description', 'Watch your things',
                               '--package-description', 'Watches things.',
                               '--banner-url', 'https://example.com/banner.png',
                               '--depiction-description', 'Say "hi".\n\nTwo paragraphs.')
        self.assertEqual(result.returncode, 0, result.stderr)
        repo = self.temp / 'Foo'
        self.assertEqual(sorted(p.name for p in (repo / 'Packaging').iterdir()),
                         ['DEBIAN', 'Foo.entitlements', 'Food.entitlements', 'wiki.qaq.food.plist'])
        self.assertTrue((repo / 'Foo/main.swift').is_file())
        for source in ('AppDelegate', 'SceneRestorationReset', 'ExecutableWatch', 'QuietExit'):
            self.assertTrue((repo / f'Foo/Application/{source}.swift').is_file())
        for path in ('Foo/RootViewController.swift', 'Foo/DaemonClient.swift',
                     'Foo/Resources/Assets.xcassets/AppIcon.appiconset/icon.png',
                     'Food/main.swift', 'Food/PeerAuthenticator.swift'):
            self.assertTrue((repo / path).is_file(), path)
        for gone in ('App', 'Daemon', 'APP.xcodeproj'):
            self.assertFalse((repo / gone).exists(), gone)
        project = (repo / 'Foo.xcodeproj/project.pbxproj').read_text()
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER = wiki.qaq.foo;', project)
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER = wiki.qaq.food;', project)
        self.assertIn('path = Food;', project)
        self.assertNotIn('IPHONEOS_DEPLOYMENT_TARGET', project)
        self.assertIn('"wiki.qaq.foo.service"', (repo / 'Shared/Protocol/AppProtocol.swift').read_text())
        self.assertIn('IPHONEOS_DEPLOYMENT_TARGET = 16.0\n', (repo / 'Configuration/Base.xcconfig').read_text())
        self.assertIn('firmware (>= 16.0)', (repo / 'Packaging/DEBIAN/control').read_text())

        packager = (repo / 'Scripts/package-deb.sh').read_text()
        self.assertIn('<Foo.app> <food>', packager)
        self.assertIn('/private/tmp/foo-deb.', packager)
        self.assertIn('@PACKAGE_ID@', packager)  # the packager's own token, untouched
        # The sibling's ids map to this app's, whatever case the sibling used.
        self.assertIn('= wiki.qaq.foo ]', packager)
        self.assertIn('wiki.qaq.food wiki.qaq.foo.service', packager)
        self.assertEqual((repo / 'Scripts/check-gpu-entitlements.py').read_text(),
                         (ROOT / 'scripts/check-gpu-entitlements.py').read_text())
        workflow = (repo / '.github/workflows/ci.yml').read_text()
        self.assertIn('- main\n', workflow)
        self.assertIn('group: foo-', workflow)
        self.assertIn('Documents/Releases/', (repo / '.github/workflows/release.yml').read_text())
        ignored = (repo / '.gitignore').read_text().splitlines()
        self.assertIn('.build/', ignored)
        self.assertIn('.swiftpm/', ignored)

        for path in repo.rglob('*'):
            if path.is_file() and 'Scripts' not in path.parts and path.suffix != '.png':
                left = set(re.findall(r'@([A-Z_]+)@', path.read_text()))
                self.assertLessEqual(left, {'PREFIX', 'VERSION', 'ARCHITECTURE', 'FLAVOR', 'INSTALLED_SIZE', 'ROOTFS'}, path)
        self.assertNotIn('sibling name', result.stdout)

        # The gate runs first, and only a fully ticked checklist gets past it.
        gated = subprocess.run(['make', '-C', str(repo), 'check'], capture_output=True, text=True)
        self.assertNotEqual(gated.returncode, 0)
        self.assertIn('unticked', gated.stderr)
        checklist = repo / 'CHECKLIST.md'
        checklist.write_text(checklist.read_text().replace('- [ ]', '- [x]'))
        passed = subprocess.run(['make', '-C', str(repo), 'check'], capture_output=True, text=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn('checked Foo', passed.stdout)

    def test_session_host_plist(self):
        result = self.scaffold('--from', 'iGhostVT', '--id-prefix', 'dev.example')
        self.assertEqual(result.returncode, 0, result.stderr)
        repo = self.temp / 'Foo'
        packager = (repo / 'Scripts/package-deb.sh').read_text()
        self.assertIn('= dev.example.foo ]', packager)
        self.assertNotIn('wiki.qaq', packager)
        text = (repo / 'Packaging/dev.example.food.plist').read_text()
        plist = plistlib.loads(text.encode())
        self.assertIs(plist['RunAtLoad'], True)
        self.assertIs(plist['KeepAlive'], True)
        self.assertEqual(plist['ProcessType'], 'Interactive')
        self.assertEqual(plist['SoftResourceLimits'], {'NumberOfFiles': 10240})
        self.assertNotIn('AbandonProcessGroup', plist)
        self.assertNotIn('<!-- <key>', text)
        self.assertFalse((repo / 'Packaging/HELPER.entitlements').exists())

    def test_helper_per_job_plist_and_helper(self):
        result = self.scaffold('--from', 'Irisin')
        self.assertEqual(result.returncode, 0, result.stderr)
        repo = self.temp / 'Foo'
        plist = plistlib.loads((repo / 'Packaging/wiki.qaq.food.plist').read_bytes())
        self.assertIs(plist['AbandonProcessGroup'], True)
        self.assertNotIn('KeepAlive', plist)
        self.assertNotIn('RunAtLoad', plist)
        self.assertTrue((repo / 'Packaging/foo-install.entitlements').is_file())

    def test_leftover_sibling_name_is_reported_not_guessed(self):
        (self.siblings / 'Inspector/Scripts/note.sh').write_text('# from InSpector\n')
        subprocess.run(['git', '-C', str(self.siblings / 'Inspector'), 'add', '-A'], check=True)
        subprocess.run(['git', '-C', str(self.siblings / 'Inspector'), '-c', 'user.name=t',
                        '-c', 'user.email=t@t', 'commit', '-qm', 'note'], check=True)
        result = self.scaffold('--from', 'Inspector')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('sibling name Scripts/note.sh:1: # from InSpector', result.stdout)

    def test_refuses_a_folder_with_files_and_leaves_nothing_on_failure(self):
        (self.temp / 'Taken').mkdir()
        (self.temp / 'Taken/README.md').write_text('mine\n')
        refused = self.scaffold('--from', 'Inspector', dest='Taken')
        self.assertEqual(refused.returncode, 73)
        self.assertEqual([p.name for p in (self.temp / 'Taken').iterdir()], ['README.md'])

        failed = subprocess.run([str(SCRIPT), str(self.temp / 'Foo'), '--name', 'Foo', '--from', 'Fila',
                                 '--siblings', str(self.siblings)], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn('Fila is not checked out', failed.stderr)
        self.assertFalse((self.temp / 'Foo').exists())
        self.assertEqual(list(self.temp.glob('.Foo.scaffold-*')), [])


if __name__ == '__main__':
    unittest.main()
