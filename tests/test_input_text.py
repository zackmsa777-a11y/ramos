"""Real native stdin and decimal conversions; no mocked runtime."""
import json
import random
import queue
import threading
import subprocess
import unittest
import test_ramos as support


class InputTextTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_native(self, *args, input=None, stdin=None):
        return subprocess.run([str(self.output), *args], input=input, stdin=stdin,
                              capture_output=True, timeout=10)

    def build_ok(self, source):
        result = self.build(source, '--force')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_decimal_signed_boundaries_and_seeded_roundtrips(self):
        rng = random.Random(901)
        values = [-2**63, -2**63 + 1, -100, -1, 0, 1, 10, 2**63 - 2, 2**63 - 1]
        values += [rng.randrange(-2**63, 2**63) for _ in range(180)]
        statements, expected = ['print(parse_error())'], ['0']
        for n in values:
            statements += [f'print(int_to_text({n}))', f'print(text_to_int(int_to_text({n})))',
                           'print(parse_error())']
            expected += [str(n), str(n), '0']
        self.assert_runs('fn main() {\n' + '\n'.join(statements) + '\n}',
                         ('\n'.join(expected) + '\n').encode())

    def test_whole_buffer_decimal_syntax_and_range_errors(self):
        valid = [('0', 0), ('-0', 0), ('+0', 0), ('+000123', 123), ('-000123', -123),
                 ('-9223372036854775808', -2**63), ('+9223372036854775807', 2**63-1)]
        invalid = ['', '+', '-', '--1', '+-1', ' 1', '1 ', '1\n', '1\r', '1.0', '0x10', '١', '1a']
        overflow = ['9223372036854775808', '-9223372036854775809',
                    '+9999999999999999999999999999999']
        statements, expected = [], []
        for text, value, status in [(s, n, 0) for s, n in valid] + [(s, 0, -22) for s in invalid] + [(s, 0, -34) for s in overflow] + [('999999999999999999999x', 0, -22)]:
            statements += ['print(text_to_int(' + json.dumps(text, ensure_ascii=False) + '))', 'print(parse_error())']
            expected += [str(value), str(status)]
        statements += ['print(text_to_int("1\\0"))', 'print(parse_error())',
                       'let raw = buffer(1)', 'buffer_set(raw, 0, 255)',
                       'print(text_to_int(raw))', 'print(parse_error())']
        expected += ['0', '-22', '0', '-22']
        self.assert_runs('fn main() {\n' + '\n'.join(statements) + '\n}',
                         ('\n'.join(expected) + '\n').encode())

    def test_text_is_fresh_mutable_and_has_no_terminator(self):
        self.assert_runs('''fn main() {
let a = int_to_text(-123)
let b = int_to_text(-123)
buffer_set(a, 1, 57)
print(a)
print(b)
print(buffer_len(b))
print(buffer_get(b, 3))
}''', b'-923\n-123\n4\n51\n')

    def test_parse_and_io_status_are_independent(self):
        self.build_ok('''fn main() {
read_file("does-not-exist/ramos-test-input")
print(io_error())
print(text_to_int("bad"))
print(parse_error())
print(io_error())
print(int_to_text(21))
print(parse_error())
print(read_line())
print(io_error())
print(parse_error())
print(text_to_int("0"))
print(parse_error())
}''')
        result = self.run_native(input=b'ok\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'-2\n0\n-22\n-2\n21\n-22\nok\n0\n-22\n0\n0\n')

    def test_long_decimal_validation_has_no_hidden_digit_cap(self):
        self.assert_runs('''fn main() {
let text = buffer(100000)
var i = 0
while i < buffer_len(text) {
buffer_set(text, i, 48)
i = i + 1
}
buffer_set(text, 99999, 55)
print(text_to_int(text))
print(parse_error())
buffer_set(text, 0, 57)
print(text_to_int(text))
print(parse_error())
buffer_set(text, 99999, 120)
print(text_to_int(text))
print(parse_error())
}''', b'7\n0\n0\n-34\n0\n-22\n')

    def test_blank_lines_final_line_binary_bytes_and_sticky_eof(self):
        self.build_ok('''fn main() {
print(stdin_eof())
var i = 0
while i < 5 {
let line = read_line()
print(buffer_len(line))
print(line)
print(io_error())
print(stdin_eof())
i = i + 1
}
}''')
        result = self.run_native(input=b'\nA\x00\xff\r\nlast\r')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'false\n0\n\n0\nfalse\n3\nA\x00\xff\n0\nfalse\n5\nlast\r\n0\ntrue\n0\n\n0\ntrue\n0\n\n0\ntrue\n')

    def test_crlf_and_lines_crossing_refill_boundaries(self):
        lines = [b'a' * 4095, b'b' * 4096, b'c' * 4097, b'd' * 8191, b'tail']
        self.build_ok('''fn main() {
var i = 0
while i < 5 {
let line = read_line()
print(buffer_len(line))
print(buffer_get(line, 0))
print(buffer_get(line, buffer_len(line) - 1))
print(io_error())
print(stdin_eof())
i = i + 1
}
}''')
        data = b'\r\n'.join(lines)
        expected = []
        for i, line in enumerate(lines):
            expected += [str(len(line)), str(line[0]), str(line[-1]), '0', 'true' if i == 4 else 'false']
        result = self.run_native(input=data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, ('\n'.join(expected) + '\n').encode())

    def test_exact_line_limit_and_oversized_line_drain(self):
        self.build_ok('''fn main() {
var i = 0
while i < 4 {
let line = read_line()
print(buffer_len(line))
print(io_error())
print(stdin_eof())
if buffer_len(line) == 2 { print(line) }
i = i + 1
}
}''')
        data = b'a' * 1048576 + b'\r\n' + b'b' * 1048577 + b'\r\nOK\n'
        result = self.run_native(input=data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'1048576\n0\nfalse\n0\n-27\nfalse\n2\n0\nfalse\nOK\n0\n0\ntrue\n')

    def test_oversized_final_line_and_status_reset_after_eof(self):
        self.build_ok('''fn main() {
print(buffer_len(read_line()))
print(io_error())
print(stdin_eof())
print(buffer_len(read_line()))
print(io_error())
print(stdin_eof())
}''')
        result = self.run_native(input=b'x' * 1048576 + b'\r')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'0\n-27\ntrue\n0\n0\ntrue\n')

    def test_many_short_lines_use_actual_payload_allocations(self):
        self.build_ok('''fn main() {
var i = 0
var sum = 0
while i < 20000 {
let line = read_line()
if io_error() != 0 { exit(2) }
sum = sum + text_to_int(line)
if parse_error() != 0 { exit(3) }
i = i + 1
}
print(sum)
}''')
        result = self.run_native(input=b'7\n' * 20000)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'140000\n')

    def test_stdin_os_failure_is_fallible_and_does_not_mark_eof(self):
        self.build_ok('''fn main() {
print(buffer_len(read_line()))
print(io_error())
print(stdin_eof())
}''')
        with self.source.open('wb') as write_only:
            result = self.run_native(stdin=write_only)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], b'0')
        self.assertLess(int(lines[1]), 0)
        self.assertEqual(lines[2], b'false')

    def test_intrinsic_types_arity_and_reserved_function_names(self):
        for body in ('print(read_line(1))', 'print(stdin_eof(0))', 'print(int_to_text(true))',
                     'print(text_to_int(1))', 'print(parse_error(0))', 'print(1 + stdin_eof())'):
            result = self.build('fn main() { ' + body + ' }')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(self.output.exists())
        result = self.build('fn int_to_text() {}\nfn main() {}')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())

    def start_native(self):
        return subprocess.Popen([str(self.output)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_interactive_line_returns_before_input_is_closed(self):
        self.build_ok('fn main() {\nprint(read_line())\nprint(read_line())\n}')
        process = self.start_native()
        lines = queue.Queue()
        reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            process.stdin.write(b'first\n')
            process.stdin.flush()
            self.assertEqual(lines.get(timeout=5), b'first\n')
            reader.join(timeout=1)
            process.stdin.write(b'second\r\n')
            process.stdin.close()
            process.stdin = None
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(stdout, b'second\n')
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            process.stdout.close()
            process.stderr.close()

    def test_stdin_preserves_source_identity_and_writes_preserve_parse_status(self):
        self.build_ok('''fn main() {
read_file(arg(1))
print(io_error())
text_to_int("bad")
read_line()
print(parse_error())
print(write_file(arg(1), "replacement", 2))
print(parse_error())
print(write_file(arg(2), "fresh", 0))
print(parse_error())
}''')
        original = self.source.read_bytes()
        destination = self.directory / 'fresh.bin'
        result = self.run_native(self.native_path(self.source), self.native_path(destination), input=b'ok\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'0\n-22\n-22\n-22\n0\n-22\n')
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(destination.read_bytes(), b'fresh')

    native_path = staticmethod(str)

    def test_interactive_example(self):
        self.build_ok((support.ROOT / 'examples/input.ramos').read_text())
        result = self.run_native(input=b'21\r\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'Enter a signed integer:\nDouble:\n42\n')
