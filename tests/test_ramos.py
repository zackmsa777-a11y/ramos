"""End-to-end tests: build Ramos source and execute the resulting ELF file.

Changing generated output, accepting malformed input, or breaking output-file
protection must fail these tests. Python is a test harness, not compiler code.
"""
import os
import random
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / 'ramos'


class RamosTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(COMPILER.is_file(), 'The assembly compiler must exist')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / 'example.ramos'
        self.output = self.directory / 'example'

    def build(self, source, *extra):
        self.source.write_bytes(source.encode() if isinstance(source, str) else source)
        return subprocess.run(
            [str(COMPILER), 'build', str(self.source), '-o', str(self.output), *extra],
            capture_output=True, timeout=5)

    def assert_runs(self, source, expected):
        result = self.build(source)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)

    def test_compile_and_execute_hello(self):
        self.assert_runs('fn main() {\n    print("Hello, Ramos!")\n}\n', b'Hello, Ramos!\n')

    def test_generated_elf_is_static_with_memory_protections(self):
        self.assert_runs('fn main() { print("hello") }', b'hello\n')
        binary = self.output.read_bytes()
        self.assertEqual(binary[:7], b'\x7fELF\x02\x01\x01')
        header = struct.unpack_from('<16sHHIQQQIHHHHHH', binary)
        self.assertEqual(header[1:4], (2, 62, 1))  # EXEC, x86-64, current
        segments = [struct.unpack_from('<IIQQQQQQ', binary, header[5] + i * header[9])
                    for i in range(header[10])]
        self.assertFalse(any(segment[0] in (2, 3) for segment in segments))
        self.assertFalse(any(segment[0] == 1 and segment[1] & 3 == 3 for segment in segments))
        self.assertTrue(any(segment[0] == 0x6474e551 and segment[1] == 6 for segment in segments))
        for segment in segments:
            if segment[0] == 1:
                self.assertLessEqual(segment[5], segment[6])
                self.assertLessEqual(segment[2] + segment[5], len(binary))
                self.assertEqual(segment[2] % segment[7], segment[3] % segment[7])

    def test_empty_body(self):
        self.assert_runs('fn main() {}', b'')

    def test_multiple_prints_unicode_and_escapes(self):
        self.assert_runs('fn main() {\nprint("مرحبا 🌍")\nprint("a\\nb\\tc\\r\\\"\\\\")\nprint("")\n}',
                         'مرحبا 🌍\na\nb\tc\r"\\\n\n'.encode())

    def test_crlf_and_whitespace(self):
        self.assert_runs('fn\r\nmain\t( )\r\n{\r\nprint ( "ok" )\r\n}\r\n', b'ok\n')

    def test_reject_invalid_source_without_output(self):
        invalid = [
            '', 'fn main() {', 'fn other() {}', 'fn main(x) {}',
            'fn main() { print("x")', 'fn main() { print("x) }',
            'fn main() { print("\\q") }', 'fn main() { print("x\ny") }',
            'fn main() { print(true) }', 'fn main() { let x = "string" }',
            'fn main() {} fn main() {}', 'fn main() {} garbage',
            'fn main() { print("a") print("b") }',
            b'fn main() { print("\xc0\x80") }',
            b'fn main() { print("\xed\xa0\x80") }',
            b'fn main() { print("\xf4\x90\x80\x80") }',
            b'fn main() { print("\xe2\x82") }',
            b'fn main() {}\x00',
        ]
        for source in invalid:
            with self.subTest(source=source):
                result = self.build(source)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'error:', result.stderr)
                self.assertFalse(self.output.exists())
                self.assertEqual(list(self.directory.glob('*.ramos-tmp-*')), [])

    def test_error_reports_source_line_and_column(self):
        result = self.build('fn main() {\n  nonsense\n}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn((str(self.source) + ':2:3: error:').encode(), result.stderr)

    def test_existing_output_requires_force(self):
        self.output.write_bytes(b'preserve this')
        result = self.build('fn main() { print("new") }')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'preserve this')
        result = self.build('fn main() { print("new") }', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(result.stdout, b'new\n')

    def test_invalid_source_preserves_existing_output_even_with_force(self):
        self.output.write_bytes(b'preserve this')
        result = self.build('fn main() { print( }', '--force')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'preserve this')

    def test_never_overwrites_source_or_its_hardlink(self):
        source = 'fn main() { print("original") }'
        self.source.write_text(source)
        for destination in (self.source, self.output):
            if destination != self.source:
                os.link(self.source, destination)
            result = subprocess.run([str(COMPILER), 'build', str(self.source), '-o',
                                     str(destination), '--force'], capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.source.read_text(), source)

    def test_source_size_limit(self):
        result = self.build(b' ' * (1024 * 1024 + 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'error:', result.stderr)
        self.assertFalse(self.output.exists())

    def test_fifo_input_is_rejected_without_blocking(self):
        fifo = self.directory / 'input.ramos'
        os.mkfifo(fifo)
        try:
            result = subprocess.run([str(COMPILER), 'build', str(fifo), '-o',
                                     str(self.output)], capture_output=True, timeout=1)
        except subprocess.TimeoutExpired:
            self.fail('Opening a non-regular input must not block before validation')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'error:', result.stderr)
        self.assertFalse(self.output.exists())

    def test_maximum_length_output_filename(self):
        self.output = self.directory / ('x' * os.pathconf(self.directory, 'PC_NAME_MAX'))
        self.assert_runs('fn main() { print("long filename") }', b'long filename\n')

    def test_failed_publish_cleans_temporary_output(self):
        self.output.mkdir()
        result = self.build('fn main() { print("hello") }', '--force')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_large_strings_and_many_statements(self):
        self.assert_runs('fn main() { print("' + 'x' * 100000 + '") }', b'x' * 100000 + b'\n')
        self.output.unlink()
        self.assert_runs('fn main() {\n' + 'print("hello")\n' * 5000 + '}', b'hello\n' * 5000)

    def test_invalid_cli_missing_input_and_output_directory(self):
        for arguments in ([], ['build'], ['--unknown'], ['build', 'missing.ramos', '-o', str(self.output)]):
            result = subprocess.run([str(COMPILER), *arguments], capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
        self.source.write_text('fn main() {}')
        result = subprocess.run([str(COMPILER), 'build', str(self.source), '-o',
                                 str(self.directory / 'missing' / 'file')], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_output_failure_is_nonzero(self):
        result = self.build('fn main() { print("hello") }')
        self.assertEqual(result.returncode, 0, result.stderr)
        with open('/dev/full', 'wb') as destination:
            result = subprocess.run([str(self.output)], stdout=destination, stderr=subprocess.PIPE, timeout=5)
        self.assertNotEqual(result.returncode, 0)

    def test_help_and_version(self):
        for argument, expected in (('--help', b'ramos build'), ('--version', b'Ramos 0.2')):
            result = subprocess.run([str(COMPILER), argument], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout)

    def test_integer_literals_and_signed_limits(self):
        self.assert_runs('fn main() {\nprint(0)\nprint(42)\nprint(-42)\n'
                         'print(9223372036854775807)\nprint(-9223372036854775808)\n}',
                         b'0\n42\n-42\n9223372036854775807\n-9223372036854775808\n')

    def test_arithmetic_precedence_associativity_and_unary(self):
        self.assert_runs('fn main() {\nprint(2 + 3 * 4)\nprint((2 + 3) * 4)\n'
                         'print(20 - 3 - 2)\nprint(20 / 2 / 2)\n'
                         'print(-(-5) + +3)\nprint(17 % 5)\n}',
                         b'14\n20\n15\n5\n8\n2\n')

    def test_signed_division_and_remainder(self):
        self.assert_runs('fn main() {\nprint(-7 / 3)\nprint(-7 % 3)\n'
                         'print(7 / -3)\nprint(7 % -3)\n}', b'-2\n-1\n-2\n1\n')

    def test_integer_bindings_mutation_and_mixed_printing(self):
        self.assert_runs('fn main() {\nlet price = 20\nvar count = 3\n'
                         'print("total")\nprint(price * count)\ncount = count + 2\n'
                         'let total = price * count\nprint(total)\nprint(price)\n}',
                         b'total\n60\n100\n20\n')

    def test_arithmetic_failures_report_runtime_error(self):
        for expression in ('9223372036854775807 + 1', '-9223372036854775808 - 1',
                           '9223372036854775807 * 2', '-(-9223372036854775808)',
                           '1 / 0', '1 % 0', '-9223372036854775808 / -1',
                           '-9223372036854775808 % -1'):
            with self.subTest(expression=expression):
                result = self.build('fn main() { print(' + expression + ') }', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'arithmetic', result.stderr)
                self.assertEqual(result.stdout, b'')

    def test_reject_invalid_integers_expressions_and_bindings(self):
        invalid = [
            'print(9223372036854775808)', 'print(18446744073709551616)',
            'print(-9223372036854775809)', 'print(1 +)', 'print(* 2)',
            'print((1 + 2)', 'print(1 2)', 'print(1 + "x")', 'print(missing)',
            'let x = x', 'let x = 1\nlet x = 2', 'let x = 1\nx = 2',
            'x = 2', 'var x = 1\nvar x = 2', 'let main = 1',
        ]
        for statement in invalid:
            with self.subTest(statement=statement):
                result = self.build('fn main() {\n' + statement + '\n}')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)
                self.assertFalse(self.output.exists())

    def test_deep_expression_is_rejected_without_crash(self):
        result = self.build('fn main() { print(' + '(' * 512 + '1' + ')' * 512 + ') }')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'error:', result.stderr)
        self.assertFalse(self.output.exists())

    def test_many_distinct_bindings_resolve_correctly(self):
        declarations = ''.join('let value_' + str(i) + ' = ' + str(i) + '\n' for i in range(1000))
        self.assert_runs('fn main() {\n' + declarations + 'print(value_0 + value_999)\n}', b'999\n')

    def test_compiler_complexity_limits_fail_cleanly(self):
        cases = [
            'fn main() {\n' + ''.join('let n' + str(i) + ' = 1\n' for i in range(4097)) + '}',
            'fn main() { print(' + '-' * 512 + '1) }',
            'fn main() { print(' + '1+' * 131073 + '1) }',
            'fn main() { print(' + '1/' * 80000 + '1) }',
        ]
        for index, source in enumerate(cases):
            with self.subTest(case=index):
                result = self.build(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'limit', result.stderr)
                self.assertFalse(self.output.exists())

    def test_arithmetic_at_valid_boundaries(self):
        self.assert_runs('fn main() {\nvar smallest = -9223372036854775808\n'
                         'let largest = 9223372036854775807\nprint(smallest / 1)\n'
                         'print(largest + 0)\nprint(largest * 0)\nprint(smallest % 1)\n'
                         'print(smallest + largest)\n}',
                         b'-9223372036854775808\n9223372036854775807\n0\n0\n-1\n')

    def test_native_arithmetic_matches_seeded_integer_cases(self):
        rng = random.Random(971032)

        def expression(depth):
            if depth == 0 or rng.randrange(4) == 0:
                value = rng.randrange(-100, 101)
                return str(value), value
            left, a = expression(depth - 1)
            right, b = expression(depth - 1)
            operator = rng.choice(['+', '-', '*', '/', '%'])
            if operator in ('/', '%') and b == 0:
                right, b = '1', 1
            if operator == '+':
                value = a + b
            elif operator == '-':
                value = a - b
            elif operator == '*':
                value = a * b
            else:
                quotient = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    quotient = -quotient
                value = quotient if operator == '/' else a - quotient * b
            if not -(1 << 63) <= value < (1 << 63):
                return '0', 0
            return '(' + left + ' ' + operator + ' ' + right + ')', value

        cases = [expression(4) for _ in range(250)]
        source = 'fn main() {\n' + ''.join('print(' + code + ')\n' for code, _ in cases) + '}'
        expected = ''.join(str(value) + '\n' for _, value in cases).encode()
        self.assert_runs(source, expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
