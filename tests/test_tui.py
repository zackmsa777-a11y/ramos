"""VT drawing, native console contracts, and real Linux pseudo-terminal input."""
import os
from pathlib import Path
import shutil
import subprocess
import time
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams


@unittest.skipIf(BOOTSTRAP, 'the retained seed has no terminal intrinsics or library grammar')
class TUITests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native
    example = streams.StreamTests.example

    def test_redirected_streams_reject_interactive_mode(self):
        self.build_ok('''fn main() {
print(terminal_start())
print(terminal_width())
print(io_error() != 0)
print(terminal_height())
print(terminal_key(0))
print(io_error())
print(terminal_key(-2))
print(io_error())
print(terminal_stop())
print(terminal_stop())
}''')
        self.assertEqual(self.run_native().stdout, b'-25\n0\ntrue\n0\n-1\n-25\n-1\n-22\n0\n0\n')

    def test_draw_controls_colors_box_and_sanitized_preview(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/tui.ramos"
fn main() {
tui_move(2, 3)
tui_color(6, 0)
tui_write(s"Ramos")
tui_reset()
tui_box(4, 1, 4, 3)
print(tui_safe("a\\0\\t🌍", 6))
}''')
        expected = b'\x1b[2;3H\x1b[36;40mRamos\x1b[0m\x1b[4;1H+--+\x1b[5;1H|\x1b[5;4H|\x1b[6;1H+--+a?????\n'
        self.assertEqual(self.run_native().stdout, expected)
        for call in ['tui_color(8, 0)', 'tui_move(0, 1)', 'tui_box(1,1,1,2)', 'tui_safe("x", -1)']:
            self.build_ok('weave "stdlib/tui.ramos"\nfn main() { '+call+' }')
            self.assertEqual(self.run_native().returncode, 1)

    def test_viewer_help_missing_file_and_nonterminal(self):
        self.example('rview')
        source = self.directory / 'file'; source.write_bytes(b'hello\n')
        self.assertEqual(self.run_native('--help').returncode, 0)
        self.assertEqual(self.run_native().returncode, 2)
        self.assertEqual(self.run_native(self.native_path(source)+'missing').returncode, 1)
        result = self.run_native(self.native_path(source))
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'interactive terminal', result.stderr)

    native_path = staticmethod(str)


@unittest.skipIf(BOOTSTRAP or os.name == 'nt' or bool(os.environ.get('RAMOS_WINDOWS_COMPILER')), 'Linux pseudo-terminal integration')
class LinuxTerminalTests(TUITests):
    # Base contract tests run once, on TUITests.
    test_redirected_streams_reject_interactive_mode = None
    test_draw_controls_colors_box_and_sanitized_preview = None
    test_viewer_help_missing_file_and_nonterminal = None

    def start_terminal(self, source, *args):
        import fcntl, pty, struct, termios
        self.build_ok(source)
        master, slave = pty.openpty()
        self.addCleanup(os.close, master); self.addCleanup(os.close, slave)
        before = termios.tcgetattr(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
        process = subprocess.Popen([str(self.output), *args], stdin=slave, stdout=slave, stderr=slave)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        return process, master, slave, before

    def read_until(self, master, marker):
        import select
        data = b''; deadline = time.monotonic() + 6
        while marker not in data and time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]: data += os.read(master, 65536)
        self.assertIn(marker, data)
        return data

    def assert_restored(self, process, slave, before, status=0):
        import termios
        self.assertEqual(process.wait(timeout=5), status)
        self.assertEqual(termios.tcgetattr(slave), before)

    def test_real_key_input_dimensions_and_normal_return_restore(self):
        process, master, slave, before = self.start_terminal('''fn main() {
print(terminal_start())
print(terminal_width())
print(terminal_height())
stdout("READY")
print(terminal_key(3000))
}''')
        self.read_until(master, b'READY')
        os.write(master, b'q')
        data = self.read_until(master, b'113')
        self.assertIn(b'113', data)
        self.assert_restored(process, slave, before)

    def test_arrow_escape_timeout_and_idempotent_stop(self):
        self.standard_library()
        process, master, slave, before = self.start_terminal('''weave "stdlib/tui.ramos"
fn main() {
print(tui_begin())
print(terminal_start())
print(tui_key(0))
print(io_error())
stdout("READY")
print(tui_key(3000))
stdout("ESCAPE")
print(tui_key(3000))
print(tui_end())
print(tui_end())
}''')
        self.read_until(master, b'READY')
        os.write(master, b'\x1b[A')
        self.assertIn(b'256', self.read_until(master, b'ESCAPE'))
        os.write(master, b'\x1b')
        self.read_until(master, b'27')
        self.assert_restored(process, slave, before)

    def test_explicit_exit_and_native_overflow_restore(self):
        for ending, status in [('exit(7)', 7), ('print(9223372036854775807 + 1)', 1), ('buffer_get("x", 2)', 1)]:
            process, master, slave, before = self.start_terminal('fn main() { terminal_start()\nstdout("READY")\nterminal_key(3000)\n'+ending+' }')
            self.read_until(master, b'READY'); os.write(master, b'q')
            self.assert_restored(process, slave, before, status)

    def test_external_sigterm_restores_terminal(self):
        import signal
        process, master, slave, before = self.start_terminal('fn main() { terminal_start()\nstdout("READY")\nterminal_key(-1) }')
        self.read_until(master, b'READY')
        os.kill(process.pid, signal.SIGTERM)
        self.assert_restored(process, slave, before, 143)

    def test_terminal_state_remains_rooted_across_gc(self):
        process, master, slave, before = self.start_terminal('''fn main() {
terminal_start()
var i = 0
while i < 40 { let garbage = buffer(1048576)
buffer_set(garbage, 0, i)
i = i + 1 }
collect()
stdout("READY")
print(terminal_key(3000))
}''')
        self.read_until(master, b'READY'); os.write(master, b'x')
        self.read_until(master, b'120')
        self.assert_restored(process, slave, before)

    def test_viewer_navigation_pages_redraw_and_quit(self):
        self.standard_library()
        source = self.directory / 'file'
        source.write_bytes(b'first\x1b[2J\n'+b''.join(f'line {i}\n'.encode() for i in range(2, 66)))
        code = (support.ROOT / 'examples/rview.ramos').read_text().replace('../stdlib/', 'stdlib/')
        process, master, slave, before = self.start_terminal(code, str(source))
        first = self.read_until(master, b'Page 1 | line 1')
        self.assertIn(b'first?[2J', first)
        os.write(master, b'\x1b[B'); self.read_until(master, b'Page 1 | line 2')
        os.write(master, b'n'); self.read_until(master, b'Page 2 | line 21')
        os.write(master, b'p'); self.read_until(master, b'Page 1 | line 1')
        import fcntl, termios, struct
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 40, 0, 0))
        self.read_until(master, b'\x1b[11;1H')
        os.write(master, b'q')
        self.assert_restored(process, slave, before)

    def test_viewer_ctrl_c_and_empty_file(self):
        self.standard_library()
        source = self.directory / 'empty'; source.touch()
        code = (support.ROOT / 'examples/rview.ramos').read_text().replace('../stdlib/', 'stdlib/')
        process, master, slave, before = self.start_terminal(code, str(source))
        self.read_until(master, b'Page 1')
        os.write(master, b'\x03')
        self.assert_restored(process, slave, before, 130)

    def test_stdout_broken_pipe_is_fallible(self):
        self.build_ok('fn main() { read_line()\nlet status = stdout(buffer(1048576))\nstderr(int_to_text(status))\nstderr("\\n") }')
        process = subprocess.Popen([str(self.output)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.stdout.close(); process.stdout = None
        process.stdin.write(b'\n'); process.stdin.close(); process.stdin = None
        _, error = process.communicate(timeout=5)
        self.assertEqual((process.returncode, error), (0, b'-32\n'))
