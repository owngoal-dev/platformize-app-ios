"""Exercise the template watcher on a running executable using Darwin kqueue."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swiftc'),
                     'requires Darwin and the Swift compiler')
class ExecutableWatchTests(unittest.TestCase):
    def test_executable_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'watch'
            subprocess.run([
                'swiftc', str(ROOT / 'template/App/ExecutableWatch.swift'),
                str(ROOT / 'tests/executable-watch/main.swift'), '-o', str(binary),
            ], check=True, timeout=60)
            for mode in ('unchanged', 'remove', 'immediate-remove', 'replace',
                         'dpkg', 'rollback'):
                with self.subTest(mode=mode):
                    executable = Path(directory) / mode
                    shutil.copy2(binary, executable)
                    subprocess.run([str(executable), mode], check=True, timeout=5)
