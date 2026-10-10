"""Cross-platform file tools: streams, library state, statuses and exact bytes."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP


@unittest.skipIf(BOOTSTRAP, 'the retained seed has no stream intrinsics or library grammar')
class StreamTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs
    native_path = staticmethod(str)

    def run_native(self, *args, **kwargs):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=20, **kwargs)

    def standard_library(self):
        shutil.copytree(support.ROOT / 'stdlib', self.directory / 'stdlib')

    def build_ok(self, code):
        result = self.build(code, '--force')
        self.assertEqual(result.returncode, 0, result.stderr)

    def example(self, name):
        self.standard_library()
        code = (support.ROOT / 'examples' / (name + '.ramos')).read_text()
        self.build_ok(code.replace('../stdlib/', 'stdlib/'))

    def test_exact_stdout_binary_and_empty(self):
        self.build_ok('fn main() { stdout("\\0\\n\\r\\t")\nstdout("")\nprint(io_error()) }')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'\0\n\r\t0\n'))

    def test_large_copy_with_bounded_memory_and_no_replace(self):
        self.example('rcopy')
        source = self.directory / 'é large input.bin'
        destination = self.directory / 'copy.bin'
        source.write_bytes(bytes(range(256)) * 100000)
        result = self.run_native(self.native_path(source), self.native_path(destination))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        source.write_bytes(b'new')
        result = self.run_native(self.native_path(source), self.native_path(destination))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(destination.stat().st_size, 25600000)

    def test_empty_copy_missing_file_and_help(self):
        self.example('rcopy')
        source = self.directory / 'empty'
        destination = self.directory / 'copy'
        source.touch()
        self.assertEqual(self.run_native(self.native_path(source), self.native_path(destination)).returncode, 0)
        self.assertEqual(destination.read_bytes(), b'')
        result = self.run_native(self.native_path(source) + 'missing', self.native_path(destination))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.run_native().returncode, 2)
        self.assertEqual(self.run_native('--help').returncode, 0)

    def test_stream_eof_seek_and_zero_read(self):
        source = self.directory / 'source.bin'
        source.write_bytes(b'abc')
        self.build_ok('''fn main() {
let handle = file_open(arg(1), 0)
print(file_eof(handle))
print(buffer_len(file_read(handle, 0)))
print(file_eof(handle))
print(file_read(handle, 2))
print(file_read(handle, 2))
print(file_eof(handle))
print(buffer_len(file_read(handle, 2)))
print(file_eof(handle))
print(file_seek(handle, 1))
print(file_eof(handle))
print(file_read(handle, 2))
print(file_close(handle))
}''')
        result = self.run_native(self.native_path(source))
        self.assertEqual(result.stdout, b'false\n0\nfalse\nab\nc\nfalse\n0\ntrue\n1\nfalse\nbc\n0\n')

    def test_invalid_handles_modes_counts_and_path_fail_fallibly(self):
        self.build_ok('''fn main() {
print(file_open("missing", -1))
print(file_open("bad\\0path", 0))
print(buffer_len(file_read(-1, 4)))
print(io_error())
print(file_write(1234567, "x"))
print(file_close(0))
print(file_eof(0))
print(io_error())
print(file_seek(0, 0))
}''')
        self.assertEqual(self.run_native().stdout, b'-22\n-22\n0\n-9\n-9\n-9\nfalse\n-9\n-9\n')
        source = self.directory / 'valid'
        source.write_bytes(b'abc')
        self.build_ok('''fn main() {
let h = file_open(arg(1), 0)
print(buffer_len(file_read(h, -1)))
print(io_error())
print(buffer_len(file_read(h, 1048577)))
print(io_error())
print(file_seek(h, -1))
print(file_write(h, "x"))
print(file_read(h, 3))
file_close(h)
}''')
        self.assertEqual(self.run_native(self.native_path(source)).stdout, b'0\n-22\n0\n-22\n-22\n-9\nabc\n')

    def test_generation_ids_and_stream_capacity(self):
        source = self.directory / 'source'
        source.write_bytes(b'x')
        self.build_ok('''fn main() {
let old = file_open(arg(1), 0)
file_close(old)
let new = file_open(arg(1), 0)
print(old != new)
print(buffer_len(file_read(old, 1)))
print(io_error())
file_close(new)
let handles = array(int64, 64, 0)
var i = 0
while i < 64 { handles[i] = file_open(arg(1), 0)
if handles[i] < 0 { exit(2) }
i = i + 1 }
print(file_open(arg(1), 0))
file_close(handles[0])
print(file_open(arg(1), 0) > 0)
}''')
        self.assertEqual(self.run_native(self.native_path(source)).stdout, b'true\n0\n-9\n-24\ntrue\n')

    def test_closed_slots_reused_across_gc_and_many_opens(self):
        source = self.directory / 'source'
        source.write_bytes(b'rooted')
        self.build_ok('''fn main() {
let kept = file_open(arg(1), 0)
var i = 0
while i < 2000 {
let temporary = file_open(arg(1), 0)
if file_close(temporary) != 0 { exit(2) }
if true { let garbage = buffer(1048576)
buffer_set(garbage, 0, i % 256) }
i = i + 1
}
collect()
print(file_read(kept, 6))
print(file_close(kept))
}''')
        self.assertEqual(self.run_native(self.native_path(source)).stdout, b'rooted\n0\n')

    def test_exclusive_creation_append_and_read_only_enforcement(self):
        destination = self.directory / 'output'
        self.build_ok('''fn main() {
let h = file_open(arg(1), 1)
print(file_write(h, "first"))
file_read(h, 1)
print(io_error())
print(file_seek(h, 0))
file_eof(h)
print(io_error())
print(file_close(h))
print(file_open(arg(1), 1))
let a = file_open(arg(1), 2)
print(file_write(a, "second"))
print(file_close(a))
}''')
        result = self.run_native(self.native_path(destination))
        self.assertEqual(result.stdout, b'0\n-9\n-9\n-9\n0\n-17\n0\n0\n')
        self.assertEqual(destination.read_bytes(), b'firstsecond')

    def test_all_active_inputs_protected_from_append_and_atomic_replace(self):
        a, b, alias = [self.directory / name for name in ('a', 'b', 'alias')]
        a.write_bytes(b'first'); b.write_bytes(b'second'); os.link(a, alias)
        self.build_ok('''fn main() {
let a = file_open(arg(1), 0)
let b = file_open(arg(2), 0)
print(file_open(arg(3), 2))
print(write_file(arg(3), "replaced", 2))
print(file_read(a, 8))
print(file_read(b, 8))
file_close(a)
file_close(b)
}''')
        result = self.run_native(*map(self.native_path, (a, b, alias)))
        self.assertEqual(result.stdout, b'-22\n-22\nfirst\nsecond\n')
        self.assertEqual(a.read_bytes(), b'first')

    def test_regular_files_only_and_directories_rejected(self):
        self.build_ok('fn main() { print(file_open(arg(1), 0)) }')
        self.assertLess(int(self.run_native(self.native_path(self.directory)).stdout), 0)
        if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
            fifo = self.directory / 'fifo'; os.mkfifo(fifo)
            self.assertEqual(self.run_native(str(fifo)).stdout, b'-22\n')

    def test_line_reader_binary_crlf_offsets_and_seek(self):
        self.standard_library()
        source = self.directory / 'lines'
        source.write_bytes(b'\nfirst\r\n\0\xff\rlast\r')
        self.build_ok('''weave "stdlib/io.ramos"
fn main() {
let r = io_reader(arg(1))
print(io_line(r))
print(r.offset)
print(io_line(r))
print(r.offset)
stdout(io_line(r))
print(r.eof)
print(r.status)
print(io_seek(r, 1))
print(io_line(r))
print(io_close(r))
}''')
        result = self.run_native(self.native_path(source))
        self.assertEqual(result.stdout, b'\n1\nfirst\n8\n\0\xff\rlast\rtrue\n0\n0\nfirst\n0\n')

    def test_line_limit_crlf_and_oversize_recovery(self):
        self.standard_library()
        source = self.directory / 'lines'
        source.write_bytes(b'x' * 1048576 + b'\r\n' + b'y' * 1048577 + b'\nnext\n')
        self.build_ok('''weave "stdlib/io.ramos"
fn main() {
let r = io_reader(arg(1))
print(buffer_len(io_line(r)))
print(r.status)
print(buffer_len(io_line(r)))
print(r.status)
print(io_line(r))
print(r.status)
io_close(r)
}''')
        self.assertEqual(self.run_native(self.native_path(source)).stdout, b'1048576\n0\n0\n-27\nnext\n0\n')

    def test_search_tool_large_binary_multiple_files_and_exit_statuses(self):
        self.example('rgrep')
        a, b = self.directory / 'a', self.directory / 'b'
        a.write_bytes(b'no match\n' * 200000 + b'hit\0\xff\r\nlast hit')
        b.write_bytes(b'hit\n')
        result = self.run_native('hit', self.native_path(a), self.native_path(b))
        expected = (self.native_path(a).encode()+b':200001:hit\0\xff\n'+self.native_path(a).encode()+b':200002:last hit\n'+self.native_path(b).encode()+b':1:hit\n')
        self.assertEqual((result.returncode, result.stdout), (0, expected))
        self.assertEqual(self.run_native('missing', self.native_path(a)).returncode, 1)
        self.assertEqual(self.run_native('hit', self.native_path(a)+'missing').returncode, 2)
        self.assertEqual(self.run_native('--', '--help', self.native_path(a)).returncode, 1)
        self.assertEqual(self.run_native('--help').returncode, 0)

    def test_cli_helpers_options_and_terminator(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/cli.ramos"
fn main() {
print(cli_has(s"--verbose"))
print(cli_value(s"--name", s"default"))
}''')
        self.assertEqual(self.run_native('--verbose', '--name=🌍').stdout, 'true\n🌍\n'.encode())
        self.assertEqual(self.run_native('--name', 'Ramos').stdout, b'false\nRamos\n')
        self.assertEqual(self.run_native('--', '--verbose', '--name=x').stdout, b'false\ndefault\n')
        self.assertEqual(self.run_native('--name').returncode, 2)

    def test_stream_intrinsic_types_checked(self):
        for expression in ['file_open(s"x", 0)', 'file_read("x", 1)', 'file_write(1, s"x")', 'file_eof(true)', 'file_close("x")', 'file_seek(1, true)', 'stdout(s"x")']:
            result = self.build('fn main() { '+expression+' }', '--force')
            self.assertEqual(result.returncode, 1, (expression, result.stderr))
            self.assertIn(b'error:', result.stderr)
