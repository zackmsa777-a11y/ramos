"""Native end-to-end buffer contracts; no mocked runtime."""
from pathlib import Path
import os
import resource
import select
import subprocess
import unittest
import test_ramos as support


class BufferTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def test_zero_fill_and_binary_output(self):
        self.assert_runs('''fn main() {
let b = buffer(3)
print(buffer_len(b))
print(buffer_get(b, 0))
buffer_set(b, 1, 255)
print(buffer_get(b, 1))
print(b)
print(buffer(0))
}''', b'3\n0\n255\n\x00\xff\x00\n\n')

    def test_literals_utf8_and_zero(self):
        self.assert_runs('''fn main() {
let b = "é\\0A"
print(buffer_len(b))
print(buffer_get(b, 0))
print(buffer_get(b, 1))
print(buffer_get(b, 2))
print(b)
print(("x\\0y"))
print("x\\0y")
}''', b'4\n195\n169\n0\n\xc3\xa9\x00A\nx\x00y\nx\x00y\n')

    def test_aliases_and_independent_allocations(self):
        self.assert_runs('''fn main() {
let a = "abc"
let alias = a
let other = "abc"
buffer_set(alias, 0, 90)
print(a)
print(other)
var changing = a
changing = buffer(1)
buffer_set(changing, 0, 88)
print(changing)
print(a)
}''', b'Zbc\nabc\nX\nZbc\n')

    def test_functions_and_escaping_frames(self):
        self.assert_runs('''fn make() -> bytes { return "code" }
fn change(b: bytes) -> bytes {
buffer_set(b, 0, 67)
return b
}
fn length(b: bytes, n: int64) -> int64 {
if n == 0 { return buffer_len(b) }
return length(b, n - 1)
}
fn main() {
let b = make()
print(change(b))
print(length(b, 20))
print(make())
print(b)
}''', b'Code\n4\ncode\nCode\n')

    def test_nested_arguments_evaluate_left_to_right(self):
        self.assert_runs('''fn mark(b: bytes, value: int64) -> int64 {
buffer_set(b, 0, value)
return 0
}
fn main() {
let b = "A"
buffer_set(b, mark(b, 66), buffer_get(b, mark(b, 67)))
print(b)
print(10 + buffer_get(b, 0) * 2)
print(buffer_len(buffer(buffer_get(b, 0) - 66)))
}''', b'C\n144\n1\n')

    def test_literal_evaluations_are_independent(self):
        self.assert_runs('''fn fresh() -> bytes { return "abc" }
fn main() {
let a = fresh()
buffer_set(a, 1, 88)
print(fresh())
print(a)
var i = 0
while i < 3 {
let b = "hello"
print(buffer_get(b, 0))
buffer_set(b, 0, 0)
i = i + 1
}
}''', b'abc\naXc\n104\n104\n104\n')

    def test_maximum_payload_and_boundary_bytes(self):
        self.assert_runs('''fn main() {
let b = buffer(1048576)
buffer_set(b, 0, 0)
buffer_set(b, 1048575, 255)
print(buffer_get(b, 0))
print(buffer_get(b, 1048575))
print(buffer_len(b))
}''', b'0\n255\n1048576\n')

    def test_invalid_sizes_fail_at_runtime(self):
        for size in (-1, -9223372036854775808, 1048577, 9223372036854775807):
            with self.subTest(size=size):
                result = self.build(f'fn main() {{ let b = buffer({size}) }}', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b'')
                self.assertIn(b'buffer size', result.stderr)

    def test_out_of_bounds_fail_at_runtime(self):
        for operation in ('buffer_get', 'buffer_set'):
            for size, index in ((0, 0), (1, -1), (1, 1), (3, 3),
                                (1, -9223372036854775808), (1, 9223372036854775807)):
                with self.subTest(operation=operation, size=size, index=index):
                    args = f'b, {index}' + (', 42' if operation == 'buffer_set' else '')
                    result = self.build(f'fn main() {{\nlet b = buffer({size})\n'
                                        f'{operation}({args})\n}}', '--force')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b'buffer index', result.stderr)

    def test_invalid_byte_values_fail_before_truncation(self):
        for value in (-1, 256, -9223372036854775808, 9223372036854775807):
            with self.subTest(value=value):
                result = self.build(f'fn main() {{\nlet b = buffer(1)\n'
                                    f'buffer_set(b, 0, {value})\n}}', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn(b'byte value', result.stderr)

    def test_arena_limit_includes_metadata_and_padding(self):
        body = '''var i = 0
while i < 15 {
buffer(1048576)
i = i + 1
}
buffer(1048441)
print(42)
'''
        self.assert_runs('fn main() {\n' + body + '}', b'42\n')
        result = self.build('fn main() {\n' + body + 'buffer(0)\n}', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'42\n')
        self.assertIn(b'buffer allocation', result.stderr)

    def test_static_type_and_arity_errors(self):
        cases = ['buffer(true)', 'buffer()', 'buffer(1, 2)',
                 'buffer_len(1)', 'buffer_get(buffer(1), false)',
                 'buffer_set(buffer(1), 0, true)', 'buffer_set(buffer(1), 0)',
                 'let x = buffer_set(buffer(1), 0, 0)',
                 'print(buffer(1) + 1)', 'print(buffer(1) == buffer(1))',
                 'print(buffer(1) < buffer(1))', 'if buffer(1) {}',
                 'var b = buffer(1)\nb = 1',
                 'let buffer_get = 1\nbuffer_get(buffer(1), 0)']
        for body in cases:
            with self.subTest(body=body):
                result = self.build('fn main() {\n' + body + '\n}')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'error:', result.stderr)
                self.assertFalse(self.output.exists())
        for source in ['fn buffer(x: int64) -> int64 { return x }\nfn main() {}',
                       'fn f(b: bytes) {}\nfn main() { f(1) }',
                       'fn f() -> bytes { return 1 }\nfn main() {}']:
            with self.subTest(source=source):
                self.assertNotEqual(self.build(source).returncode, 0)

    def test_source_scanning_example(self):
        self.assert_runs('''fn digits(source: bytes) -> int64 {
var i = 0
var count = 0
while i < buffer_len(source) {
let c = buffer_get(source, i)
if c >= 48 {
if c <= 57 { count = count + 1 }
}
i = i + 1
}
return count
}
fn main() { print(digits("let answer = 42 + 100")) }''', b'5\n')

    def test_print_reports_failed_output(self):
        result = self.build('fn main() {\nlet b = "hello"\nprint(b)\n}')
        self.assertEqual(result.returncode, 0, result.stderr)
        with open('/dev/full', 'wb') as sink:
            result = subprocess.run([str(self.output)], stdout=sink,
                                    stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 1)

    def test_mapping_failure_reports_allocation_error(self):
        result = self.build('fn main() { buffer(1) }')
        self.assertEqual(result.returncode, 0, result.stderr)

        def limit_address_space():
            resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 * 1024,) * 2)

        result = subprocess.run([str(self.output)], capture_output=True, timeout=5,
                                preexec_fn=limit_address_space)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'buffer allocation', result.stderr)

    def test_arena_mapping_is_rw_and_never_executable(self):
        status = dict(line.split(':', 1) for line in
                      Path('/proc/self/status').read_text().splitlines())
        if int(status['Pid']) != os.getpid():
            self.skipTest('host /proc PIDs differ from sandbox process PIDs')
        result = self.build('''fn main() {
let b = buffer(1)
buffer_set(b, 0, 65)
print(b)
while true {}
}''')
        self.assertEqual(result.returncode, 0, result.stderr)
        child = subprocess.Popen([str(self.output)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        try:
            # Reading the line synchronizes with allocation before inspecting maps.
            self.assertTrue(select.select([child.stdout], [], [], 5)[0],
                            'generated program did not produce output in time')
            self.assertEqual(child.stdout.readline(), b'A\n')
            maps = Path(f'/proc/{child.pid}/maps').read_text().splitlines()
            arena = []
            for line in maps:
                fields = line.split()
                begin, end = (int(part, 16) for part in fields[0].split('-'))
                if end - begin == 16 * 1024 * 1024:
                    arena.append(fields[1])
                self.assertFalse('w' in fields[1] and 'x' in fields[1])
            self.assertEqual(arena, ['rw-p'])
        finally:
            child.terminate()
            child.communicate(timeout=5)
