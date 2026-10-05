"""The launchd path gate refuses a path roothide would move into the bootstrap."""
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts/check-launchd-paths.py'

PROGRAM = {'Label': 'wiki.qaq.exampled', 'ProgramArguments': ['@PREFIX@/usr/libexec/exampled']}


class LaunchdPathGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def plist(self, job):
        path = self.directory / 'job.plist'
        path.write_bytes(plistlib.dumps(job))
        return path

    def gate(self, *arguments):
        return subprocess.run(
            [sys.executable, str(GATE), *(str(a) for a in arguments)],
            capture_output=True, text=True, timeout=30,
        )

    def test_template_daemon_passes(self):
        self.assertEqual(self.gate(ROOT / 'template/Packaging/DAEMON.plist').returncode, 0)

    def test_program_alone_passes_without_a_packaging_script(self):
        job = dict(PROGRAM, EnvironmentVariables={'DISABLE_TWEAKS': '1'})
        self.assertEqual(self.gate(self.plist(job)).returncode, 0)

    def test_bare_watch_path_fails(self):
        # Xrash 0.4.15, reduced: roothide watched <jbroot>/private/var/mobile/…
        job = dict(PROGRAM, WatchPaths=['/private/var/mobile/Library/Logs/CrashReporter'])
        result = self.gate(self.plist(job))
        self.assertEqual(result.returncode, 1)
        self.assertIn('WatchPaths[0]', result.stderr)

    def test_literal_rootfs_fails(self):
        # rootless launchctl passes it through untouched
        job = dict(PROGRAM, StandardErrorPath='/rootfs/private/var/log/exampled.log')
        self.assertEqual(self.gate(self.plist(job)).returncode, 1)

    def test_rootfs_needs_a_substituting_script(self):
        job = dict(PROGRAM, WatchPaths=['@ROOTFS@/private/var/mobile/Library/Logs/CrashReporter'])
        plist = self.plist(job)
        self.assertEqual(self.gate(plist).returncode, 1)
        silent = self.directory / 'silent.sh'
        silent.write_text('sed -e "s|@PREFIX@|$prefix|g"\n')
        self.assertEqual(self.gate(plist, '--substituted-by', silent).returncode, 1)
        script = self.directory / 'package-deb.sh'
        script.write_text('sed -e "s|@PREFIX@|$prefix|g" -e "s|@ROOTFS@|$rootfs|g"\n')
        self.assertEqual(self.gate(plist, '--substituted-by', script).returncode, 0)

    def test_bootstrap_paths_use_the_prefix(self):
        job = dict(
            PROGRAM,
            StandardOutPath='@PREFIX@/var/log/exampled.log',
            KeepAlive={'PathState': {'@PREFIX@/var/run/exampled.flag': True}},
            Sockets={'Listener': [{'SockPathName': '@PREFIX@/var/run/exampled.sock'}]},
        )
        self.assertEqual(self.gate(self.plist(job)).returncode, 0)
        job['Sockets'] = {'Listener': {'SockPathName': '/var/run/exampled.sock'}}
        self.assertEqual(self.gate(self.plist(job)).returncode, 1)

    def test_program_under_rootfs_fails(self):
        job = dict(PROGRAM, ProgramArguments=['@ROOTFS@/usr/libexec/exampled'])
        self.assertEqual(self.gate(self.plist(job)).returncode, 1)

    def test_arguments_after_the_program_are_not_checked(self):
        job = dict(PROGRAM, ProgramArguments=['@PREFIX@/usr/libexec/exampled', '/private/var/mobile'])
        self.assertEqual(self.gate(self.plist(job)).returncode, 0)


if __name__ == '__main__':
    unittest.main()
