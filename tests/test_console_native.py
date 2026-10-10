"""Real Windows console painting, key events and cleanup on termination."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import test_ramos as support


@unittest.skipUnless(os.name == 'nt', 'requires a native Windows console')
class WindowsConsoleTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build

    def console_probe(self, mode, ending):
        shutil.copytree(support.ROOT / 'stdlib', self.directory / 'stdlib', dirs_exist_ok=True)
        marker, report = self.directory / 'key.txt', self.directory / 'console.json'
        result = self.build('''weave "stdlib/tui.ramos"
fn main() {
if terminal_start() != 0 { exit(2) }
tui_color(6, 0)
tui_at(2, 3, s"Ramos TUI")
let key = terminal_key(-1)
write_file(arg(1), int_to_text(key), 2)
''' + ending + '\n}', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        worker = subprocess.run([sys.executable, str(support.ROOT / 'tools/console_probe.py'), str(self.output), mode, str(marker), str(report)], creationflags=subprocess.CREATE_NEW_CONSOLE, timeout=20)
        self.assertEqual(worker.returncode, 0)
        evidence = json.loads(report.read_text())
        self.assertTrue(evidence['changed'], evidence)
        self.assertTrue(evidence['painted'], evidence)
        self.assertTrue(evidence['restored'], evidence)
        return evidence

    def test_native_windows_console_draw_input_and_exit_cleanup(self):
        for ending, status in [('', 0), ('exit(7)', 7), ('print(9223372036854775807 + 1)', 1)]:
            with self.subTest(ending=ending):
                evidence = self.console_probe('key', ending)
                self.assertEqual(evidence['key'], '256')
                self.assertEqual(evidence['status'], status)

    def test_native_windows_console_control_handler_cleanup(self):
        evidence = self.console_probe('control', '')
        self.assertNotEqual(evidence['status'], 0)
