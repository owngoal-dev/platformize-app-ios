"""The template's one-time checklist ships unticked and its gate enforces it."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / 'template/CHECKLIST.md'
GATE = ROOT / 'scripts/check-checklist.sh'
ITEM = re.compile(r'^\s*- \[([ xX])\] (.+)$', re.M)


def gate(path):
    return subprocess.run(['sh', str(GATE), str(path)], capture_output=True, text=True, timeout=10)


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.copy = Path(self.temp.name) / 'CHECKLIST.md'

    def test_template_ships_every_box_unticked(self):
        items = ITEM.findall(CHECKLIST.read_text())
        self.assertGreater(len(items), 0)
        self.assertEqual([text for mark, text in items if mark != ' '], [])

    def test_gate_lists_open_items_then_passes_when_all_ticked(self):
        text = CHECKLIST.read_text()
        items = ITEM.findall(text)
        self.copy.write_text(text)
        result = gate(self.copy)
        self.assertEqual(result.returncode, 65)
        for _, item in items:
            self.assertIn(item, result.stderr)

        # One box left open still fails, and names only that one.
        ticked = text.replace('- [ ]', '- [x]')
        self.copy.write_text(ticked.replace('- [x]', '- [ ]', 1))
        result = gate(self.copy)
        self.assertEqual(result.returncode, 65)
        self.assertIn(items[0][1], result.stderr)
        self.assertNotIn(items[1][1], result.stderr)

        self.copy.write_text(ticked)
        result = gate(self.copy)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn(str(len(items)), result.stdout)

    def test_missing_and_empty_checklists_fail(self):
        self.assertEqual(gate(self.copy).returncode, 66)
        self.copy.write_text('# Checklist\n\nNothing to decide.\n')
        self.assertEqual(gate(self.copy).returncode, 65)

    def test_gate_is_executable_and_documented(self):
        self.assertTrue(GATE.stat().st_mode & 0o111)
        subprocess.run(['sh', '-n', str(GATE)], check=True)
        for path in ('SKILL.md', 'template/AGENTS.md'):
            text = (ROOT / path).read_text()
            self.assertIn('CHECKLIST.md', text, path)
            self.assertIn('check-checklist.sh', text, path)


if __name__ == '__main__':
    unittest.main()
