"""Render the scaffold and exercise its package/page integration."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VALUES = {
    'APP_NAME': 'Example', 'REPO': 'Example', 'BUNDLE_ID': 'wiki.qaq.example',
    'DAEMON': 'exampled', 'DAEMON_ID': 'wiki.qaq.exampled',
    'SERVICE_NAME': 'wiki.qaq.example.service',
    'APP_CLIENT_ENTITLEMENT': 'wiki.qaq.example.client',
    'PACKAGE_ID': 'wiki.qaq.example', 'MINIMUM_IOS_VERSION': '15.0',
    'ONE_LINE_DESCRIPTION': 'View your documents',
    'PACKAGE_DESCRIPTION': 'Browse and preview your documents.',
    'BANNER_URL': 'https://raw.githubusercontent.com/owngoal-dev/Example/main/Documents/banner.png',
    'DEPICTION_DESCRIPTION': 'View your "Documents".\n\nRequires iOS 15 or later and a jailbreak.',
}
PACKAGE_KEYS = {'PREFIX', 'VERSION', 'ARCHITECTURE', 'FLAVOR', 'INSTALLED_SIZE'}


def replace_text(text, values):
    for key, value in values.items():
        text = text.replace(f'@{key}@', value)
    return text


def replace_json(value):
    if isinstance(value, str):
        return replace_text(value, VALUES)
    if isinstance(value, list):
        return [replace_json(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_json(item) for key, item in value.items()}
    return value


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'Example'
        shutil.copytree(ROOT / 'template', self.repo, symlinks=True)
        for path in self.repo.rglob('*'):
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix == '.json':
                path.write_text(json.dumps(replace_json(json.loads(path.read_text())), indent=2) + '\n')
            else:
                path.write_text(replace_text(path.read_text(), VALUES))

    def test_rendered_native_page_and_control_urls(self):
        depiction = json.loads((self.repo / 'Documents/Site/depiction.json').read_text())
        self.assertEqual(depiction['headerImage'], VALUES['BANNER_URL'])
        self.assertEqual([tab['tabname'] for tab in depiction['tabs']], ['Details'])
        markdown = depiction['tabs'][0]['views'][1]['markdown']
        self.assertEqual(markdown, VALUES['DEPICTION_DESCRIPTION'])
        control = (self.repo / 'Packaging/DEBIAN/control').read_text()
        self.assertIn('Depiction: https://owngoal-dev.github.io/Example/\n', control)
        self.assertIn('SileoDepiction: https://owngoal-dev.github.io/Example/depiction.json\n', control)
        self.assertIn('uikittools', control)
        self.assertTrue((self.repo / 'CLAUDE.md').is_symlink())
        for path in self.repo.rglob('*'):
            if path.is_file() and not path.is_symlink():
                remaining = set(re.findall(r'@([A-Z_]+)@', path.read_text()))
                self.assertLessEqual(remaining, PACKAGE_KEYS, str(path))

    def test_hooks_manage_daemon_without_registering_apps(self):
        prefix = Path(self.temp.name) / 'bootstrap'
        tools = prefix / 'usr/bin'
        tools.mkdir(parents=True)
        log = Path(self.temp.name) / 'launchctl.log'
        launchctl = tools / 'launchctl'
        launchctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_LAUNCH_LOG"\n')
        launchctl.chmod(0o755)
        env = dict(os.environ, TEST_LAUNCH_LOG=str(log))
        for hook, argument, expected_count in [('postinst', 'configure', 5), ('prerm', 'remove', 3), ('postrm', 'purge', 3)]:
            path = self.repo / 'Packaging/DEBIAN' / hook
            path.write_text(path.read_text().replace('@PREFIX@', str(prefix)))
            self.assertNotIn('uicache', path.read_text())
            subprocess.run(['sh', '-n', str(path)], check=True)
            log.write_text('')
            subprocess.run(['sh', str(path), argument], env=env, check=True)
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), expected_count)
            for domain in ('system', 'user/501', 'gui/501'):
                self.assertIn(f'bootout {domain}/wiki.qaq.exampled', calls)
            if hook == 'postinst':
                self.assertIn(f'bootstrap system {prefix}/Library/LaunchDaemons/wiki.qaq.exampled.plist', calls)

    def test_pages_workflow_uses_generic_pinned_updater(self):
        workflow = self.repo / '.github/workflows/pages.yml'
        text = workflow.read_text()
        self.assertRegex(text, r'ref: [0-9a-f]{40}')
        self.assertIn('ref: main', text)
        self.assertIn('gh workflow run pages.yml --ref main', text)
        self.assertIn("github.event_name != 'release' &&", text)
        self.assertIn('workflows: [Release]', text)
        self.assertIn('--repository "$RELEASE_REPOSITORY" --depiction Documents/Site/depiction.json', text)
        self.assertIn('RELEASE_REPOSITORY: ${{ github.repository }}', text)
        self.assertIn('path: Documents/Site', text)
        if shutil.which('actionlint'):
            subprocess.run(['actionlint', str(workflow)], check=True)
        else:
            self.skipTest('actionlint is not installed')


if __name__ == '__main__':
    unittest.main()
