"""Compile the template's roothide root check and run it against real names."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('swiftc'), 'requires the Swift compiler')
class RoothideRootTests(unittest.TestCase):
    def test_names(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'roothide-root'
            subprocess.run([
                'swiftc', str(ROOT / 'template/Shared/RoothideRoot.swift'),
                str(ROOT / 'tests/roothide-root/main.swift'), '-o', str(binary),
            ], check=True, timeout=60)
            subprocess.run([str(binary)], check=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
