"""The stale gate refuses a key Xcode reaped, and the pruner keeps translations.

The second half is the one that matters. An app with an iOS target and a macOS
target has its macOS-only strings marked stale by an iOS build, and they are
not dead. Deleting them takes every translation with them, in a diff too large
to read.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts/check-stale-strings.py'
PRUNE = ROOT / 'scripts/prune-xcstrings.py'

TRANSLATION = {'stringUnit': {'state': 'translated', 'value': 'アプリケーションへ移動'}}


class StringCatalogGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def catalog(self, strings, name='Localizable.xcstrings'):
        path = self.root / name
        body = {'sourceLanguage': 'en', 'version': '1.0', 'strings': strings}
        path.write_text(json.dumps(body, indent=2, separators=(',', ' : '),
                                   ensure_ascii=False) + '\n')
        return path

    def source(self, where, name, text):
        directory = self.root / where
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text)
        return directory

    def run_tool(self, tool, *args):
        return subprocess.run([sys.executable, str(tool), *(str(a) for a in args)],
                              capture_output=True, text=True, timeout=30)

    def read(self, path):
        return json.loads(path.read_text())['strings']

    # ---- the gate -------------------------------------------------------

    def test_stale_key_fails_the_build(self):
        path = self.catalog({'Move to Applications': {'extractionState': 'stale'}})
        result = self.run_tool(GATE, path)
        self.assertEqual(result.returncode, 65)
        self.assertIn('Move to Applications', result.stderr)

    def test_manual_key_is_left_alone(self):
        # `manual` is a deliberate choice in the apps that keep unseen keys by
        # hand; only the state Xcode assigns by itself is refused.
        path = self.catalog({'Kept on purpose': {'extractionState': 'manual'}})
        self.assertEqual(self.run_tool(GATE, path).returncode, 0)

    def test_unmarked_catalog_passes(self):
        path = self.catalog({'Ordinary': {'localizations': {}}})
        self.assertEqual(self.run_tool(GATE, path).returncode, 0)

    def test_a_whole_tree_is_walked_and_build_output_skipped(self):
        self.catalog({'Ordinary': {}}, name='Localizable.xcstrings')
        buried = self.root / '.build' / 'index-build' / 'Stale.xcstrings'
        buried.parent.mkdir(parents=True)
        buried.write_text(json.dumps(
            {'strings': {'Copy': {'extractionState': 'stale'}}}))
        # The stale marker exists, but only in something a build wrote.
        self.assertEqual(self.run_tool(GATE, self.root).returncode, 0)

    def test_unparseable_catalog_is_its_own_exit_code(self):
        path = self.root / 'Broken.xcstrings'
        path.write_text('{ not json')
        self.assertEqual(self.run_tool(GATE, path).returncode, 66)

    def test_gate_is_executable(self):
        self.assertTrue(GATE.stat().st_mode & 0o111, f'{GATE.name} is not executable')

    # ---- the pruner -----------------------------------------------------

    def test_a_key_only_the_mac_target_uses_keeps_its_translations(self):
        path = self.catalog({
            'Move to Applications': {'extractionState': 'stale',
                                     'localizations': {'ja': TRANSLATION}},
        })
        ios = self.source('ios', 'A.swift', 'let a = "Something else"\n')
        self.source('mac', 'B.swift', 'let b = "Move to Applications"\n')

        # Only the iOS root is passed — exactly what an iOS build knows.
        result = self.run_tool(PRUNE, path, ios)
        self.assertEqual(result.returncode, 0)

        strings = self.read(path)
        self.assertIn('Move to Applications', strings)
        self.assertEqual(
            strings['Move to Applications']['localizations']['ja'], TRANSLATION)
        self.assertEqual(
            strings['Move to Applications']['extractionState'], 'manual')
        self.assertIn('orphan', result.stdout)

    def test_deleting_orphans_is_opt_in(self):
        path = self.catalog({'Dead': {'extractionState': 'stale'}})
        ios = self.source('ios', 'A.swift', 'let a = "Something else"\n')

        self.run_tool(PRUNE, path, ios)
        self.assertIn('Dead', self.read(path), 'kept without the flag')

        path = self.catalog({'Dead': {'extractionState': 'stale'}})
        self.run_tool(PRUNE, '--delete-orphans', path, ios)
        self.assertNotIn('Dead', self.read(path), 'removed with the flag')

    def test_a_referenced_stale_key_becomes_manual(self):
        path = self.catalog({'Please Wait': {'extractionState': 'stale'}})
        ios = self.source('ios', 'A.swift',
                          'Alert(title: "Please Wait")\n')
        self.run_tool(PRUNE, '--delete-orphans', path, ios)
        self.assertEqual(self.read(path)['Please Wait']['extractionState'], 'manual')

    def test_a_key_named_only_in_a_xib_is_not_an_orphan(self):
        path = self.catalog({'Done': {'extractionState': 'stale'}})
        ios = self.source('ios', 'Main.xib', '<string>Done</string>\n')
        # The xib writes the key bare, so quote it the way a source file would.
        (ios / 'Main.xib').write_text('<attributedString value="Done"/>\n')
        self.run_tool(PRUNE, '--delete-orphans', path, ios)
        self.assertIn('Done', self.read(path))

    def test_empty_source_root_refuses_rather_than_orphaning_everything(self):
        path = self.catalog({'Anything': {'extractionState': 'stale'}})
        empty = self.root / 'empty'
        empty.mkdir()
        result = self.run_tool(PRUNE, '--delete-orphans', path, empty)
        self.assertEqual(result.returncode, 66)
        self.assertIn('Anything', self.read(path), 'the catalog was not touched')

    def test_a_second_run_changes_nothing(self):
        path = self.catalog({
            'Please Wait': {'extractionState': 'stale'},
            'Move to Applications': {'extractionState': 'stale',
                                     'localizations': {'ja': TRANSLATION}},
        })
        ios = self.source('ios', 'A.swift', 'Alert(title: "Please Wait")\n')
        self.run_tool(PRUNE, path, ios)
        once = path.read_text()
        self.run_tool(PRUNE, path, ios)
        self.assertEqual(once, path.read_text())

    def test_the_pruned_catalog_passes_the_gate(self):
        path = self.catalog({
            'Please Wait': {'extractionState': 'stale'},
            'Move to Applications': {'extractionState': 'stale',
                                     'localizations': {'ja': TRANSLATION}},
        })
        ios = self.source('ios', 'A.swift', 'Alert(title: "Please Wait")\n')
        self.assertEqual(self.run_tool(GATE, path).returncode, 65)
        self.run_tool(PRUNE, path, ios)
        self.assertEqual(self.run_tool(GATE, path).returncode, 0)


if __name__ == '__main__':
    unittest.main()
