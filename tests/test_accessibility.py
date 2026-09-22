"""The accessibility gate finds an unreachable label and nothing else."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts/check-accessibility.py'


class AccessibilityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)

    def write(self, name, text):
        path = self.source / name
        path.write_text(text)
        return path

    def gate(self, *roots):
        return subprocess.run(
            [sys.executable, str(GATE), *(str(r) for r in (roots or (self.source,)))],
            capture_output=True, text=True, timeout=30,
        )

    def test_container_labelled_without_becoming_an_element_fails(self):
        # Fila's BrowserGridCell, reduced: the sentence is assembled and never read.
        self.write('BrowserGridCell.swift', '''
        import UIKit

        final class BrowserGridCell: UICollectionViewCell {
            func configure(_ item: Item) {
                nameLabel.text = item.name
                accessibilityLabel = "\\(item.name), \\(item.detail)"
            }
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 65, result.stdout)
        self.assertIn('BrowserGridCell', result.stderr)
        self.assertIn('UICollectionViewCell', result.stderr)
        self.assertIn('BrowserGridCell.swift:7', result.stderr)

    def test_the_same_cell_passes_once_it_is_an_element(self):
        self.write('BrowserGridCell.swift', '''
        import UIKit

        final class BrowserGridCell: UICollectionViewCell {
            override init(frame: CGRect) {
                super.init(frame: frame)
                isAccessibilityElement = true
            }

            func configure(_ item: Item) {
                accessibilityLabel = "\\(item.name), \\(item.detail)"
            }
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_element_inherited_from_a_base_class_counts(self):
        self.write('BaseCell.swift', '''
        import UIKit

        class BaseCell: UITableViewCell {
            override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
                super.init(style: style, reuseIdentifier: reuseIdentifier)
                isAccessibilityElement = true
            }
        }
        ''')
        self.write('DetailCell.swift', '''
        import UIKit

        final class DetailCell: BaseCell {
            func configure(_ row: Row) {
                accessibilityLabel = row.title
            }
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_extension_of_the_cell_is_the_same_type(self):
        self.write('Cell.swift', '''
        import UIKit

        final class Cell: UITableViewCell {}

        extension Cell {
            func configure(_ row: Row) {
                accessibilityLabel = row.title
            }
        }
        ''')
        self.assertEqual(self.gate().returncode, 65)

    def test_labels_written_on_something_else_are_that_type_s_business(self):
        self.write('Controller.swift', '''
        import UIKit

        final class Controller: UIViewController {
            func build() {
                let item = UIBarButtonItem(image: icon, primaryAction: action)
                item.accessibilityLabel = String(localized: "Add Repository")
                cell.accessibilityLabel = row.title
                button.then { $0.accessibilityLabel = String(localized: "More") }
            }
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_types_that_are_already_elements_are_left_alone(self):
        self.write('Badge.swift', '''
        import UIKit

        final class Badge: UILabel {
            func configure(_ count: Int) {
                accessibilityLabel = String(localized: "\\(count) unread")
            }
        }

        final class Icon: UIButton {
            func configure() {
                accessibilityLabel = String(localized: "More")
            }
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_comments_and_strings_are_not_code(self):
        self.write('Quiet.swift', '''
        import UIKit

        final class Quiet: UIView {
            // accessibilityLabel = "not code"
            /* accessibilityLabel = "also not code" */
            let sample = "accessibilityLabel = still not code"
            let doc = """
            accessibilityLabel = not code either
            """
        }
        ''')
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bad_usage_is_its_own_exit_code(self):
        self.assertEqual(self.gate(self.source / 'nope').returncode, 66)
        result = subprocess.run(
            [sys.executable, str(GATE)], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 66)

    def test_the_scaffold_s_own_sources_pass(self):
        result = self.gate(ROOT / 'template')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gate_is_executable_and_documented(self):
        self.assertTrue(GATE.stat().st_mode & 0o111)
        for path in ('SKILL.md', 'template/AGENTS.md', 'template/CHECKLIST.md'):
            self.assertIn('check-accessibility.py', (ROOT / path).read_text(), path)


if __name__ == '__main__':
    unittest.main()
