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
        for argument, expected in (('--help', b'ramos build'), ('--version', b'Ramos 0.5')):
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

    def test_boolean_literals_bindings_and_not(self):
        self.assert_runs('fn main() {\nvar ready = true\nlet off = false\n'
                         'print(ready)\nprint(off)\nready = !ready\n'
                         'print(ready)\nprint(!!true)\nprint(!false)\n}',
                         b'true\nfalse\nfalse\ntrue\ntrue\n')

    def test_typed_comparisons_and_precedence(self):
        expressions = [('1 < 2', True), ('2 <= 2', True), ('3 > 2', True),
                       ('2 >= 3', False), ('2 == 2', True), ('2 != 2', False),
                       ('true == !false', True), ('false != true', True),
                       ('1 + 2 * 3 == 7', True), ('(2 < 3) == true', True),
                       ('-9223372036854775808 < 9223372036854775807', True),
                       ('9223372036854775807 > -9223372036854775808', True)]
        self.assert_runs('fn main() {\n' + ''.join('print(' + e + ')\n' for e, _ in expressions) + '}',
                         ''.join(str(v).lower() + '\n' for _, v in expressions).encode())

    def test_if_else_and_skipped_runtime_failure(self):
        self.assert_runs('fn main() {\nif false { print(1 / 0) } else { print("yes") }\n'
                         'if true { print(1) }\nprint(2)\n'
                         'if false {}\nelse { if true { print(3) } }\n}', b'yes\n1\n2\n3\n')

    def test_while_break_continue_and_stack_balance(self):
        self.assert_runs('fn main() {\nvar i = 0\nvar sum = 0\n'
                         'while i < 100000 {\ni = i + 1\n'
                         'if i % 2 == 0 { continue }\nsum = sum + 1\n}\n'
                         'print(sum)\nwhile true { break }\n'
                         'while false { print(1 / 0) }\nprint(i)\n}', b'50000\n100000\n')

    def test_nested_loops_target_innermost_loop(self):
        self.assert_runs('fn main() {\nvar outer = 0\nvar total = 0\n'
                         'while outer < 3 {\nouter = outer + 1\nvar inner = 0\n'
                         'while true {\ninner = inner + 1\nif inner == 2 { continue }\n'
                         'if inner == 4 { break }\ntotal = total + inner\n}\n}\nprint(total)\n}', b'12\n')

    def test_block_scope_shadowing_and_reinitialization(self):
        self.assert_runs('fn main() {\nlet x = 10\nvar i = 0\n'
                         'while i < 2 {\nlet x = i\nprint(x)\ni = i + 1\n}\n'
                         'if false { let hidden = 1 } else { let hidden = 2\nprint(hidden) }\n'
                         'print(x)\n}', b'0\n1\n2\n10\n')

    def test_control_flow_and_type_errors(self):
        statements = ['print(true + 1)', 'print(-false)', 'print(+true)',
                      'print(!1)', 'print(true < false)', 'print(true == 1)',
                      'var x = true\nx = 1', 'var x = 1\nx = false',
                      'if 1 {}', 'while 0 {}', 'break', 'continue', 'else {}',
                      'if true { let x = 1 }\nprint(x)',
                      'while false { let x = 1 }\nprint(x)',
                      'if true { let x = 1\nlet x = 2 }',
                      'if true { print(1) } print(2)', 'while true { break } print(2)',
                      'if true {', 'while true {', 'print(1 === 1)', 'print(1 < < 2)',
                      'let true = 1', 'let while = 1']
        for statement in statements:
            with self.subTest(statement=statement):
                result = self.build('fn main() {\n' + statement + '\n}')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)
                self.assertFalse(self.output.exists())

    def test_nested_blocks_limit_fails_cleanly(self):
        result = self.build('fn main() {' + 'while false {' * 512 + '}' * 513)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)
        self.assertFalse(self.output.exists())

    def test_many_branch_fixups_and_boolean_names(self):
        source = 'fn main() {\nlet true_value = true\nlet false_value = false\n' + \
                 'if true_value { print(false_value) }\n' * 2000 + '}'
        self.assert_runs(source, b'false\n' * 2000)

    def test_all_comparisons_at_signed_boundaries(self):
        values = [-(1 << 63), -1, 0, 1, (1 << 63) - 1]
        operations = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
                      '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
                      '==': lambda a, b: a == b, '!=': lambda a, b: a != b}
        cases = [(str(a) + ' ' + op + ' ' + str(b), fn(a, b))
                 for a in values for b in values for op, fn in operations.items()]
        self.assert_runs('fn main() {\n' + ''.join('print(' + e + ')\n' for e, _ in cases) + '}',
                         ''.join(str(v).lower() + '\n' for _, v in cases).encode())

    def test_shadow_initializer_and_type_restore(self):
        self.assert_runs('fn main() {\nvar x = 5\n'
                         'if true {\nlet x = x + 1\nprint(x)\n'
                         'if true { var x = false\nx = !x\nprint(x) }\nprint(x)\n}\n'
                         'x = x + 2\nprint(x)\n}', b'6\ntrue\n6\n7\n')

    def test_exact_block_nesting_boundary(self):
        self.assert_runs('fn main() {' + 'if true {' * 127 + 'print(1)' + '}' * 128, b'1\n')
        self.output.unlink()
        result = self.build('fn main() {' + 'if true {' * 128 + '}' * 129)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)
        self.assertFalse(self.output.exists())

    def test_while_runtime_failure_retains_prior_output(self):
        result = self.build('fn main() {\nvar x = 1\nwhile true {\n'
                            'print(x)\nx = x / 0\n}\n}')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'1\n')
        self.assertIn(b'arithmetic', result.stderr)

    def test_control_flow_crlf_and_newline_lookahead(self):
        source = 'fn main() {\nif true { print(1) }\n\nprint(2)\n'
        source += 'if false {}\n\nelse { print(3) }\nwhile false {}\nprint(4)\n}'
        self.assert_runs(source.replace('\n', '\r\n'), b'1\n2\n3\n4\n')

    def test_hash_collision_scope_restoration(self):
        names = ['v684', 'v4930', 'v5418', 'v5577', 'v6226', 'v8585', 'v8699', 'v12720']
        source = 'fn main() {\n'
        source += ''.join('let ' + name + ' = ' + str(i) + '\n' for i, name in enumerate(names))
        source += 'if true {\n'
        source += ''.join('let ' + name + ' = ' + str(i + 10) + '\n' for i, name in enumerate(names))
        source += 'if true { let v684 = false\nprint(v684) }\n'
        source += 'print(' + ' + '.join(names) + ')\n}\n'
        source += 'if true { let v684 = 100\nprint(v684) }\n'
        source += 'print(' + ' + '.join(names) + ')\n}'
        self.assert_runs(source, b'false\n108\n100\n28\n')

    def test_exact_boolean_expression_depth_boundary(self):
        for left, right in [('!' * 127, ''), ('(' * 127, ')' * 127)]:
            with self.subTest(kind=left[0]):
                self.assert_runs('fn main() { print(' + left + 'true' + right + ') }',
                                 b'false\n' if left[0] == '!' else b'true\n')
                self.output.unlink()
        for left, right in [('!' * 128, ''), ('(' * 128, ')' * 128)]:
            result = self.build('fn main() { print(' + left + 'true' + right + ') }')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'limit', result.stderr)
            self.assertFalse(self.output.exists())

    def test_functions_forward_calls_and_typed_returns(self):
        self.assert_runs('fn main() {\nprint(add(20, 22))\nprint(positive(-1))\n}\n'
                         'fn add(a: int64, b: int64) -> int64 { return a + b }\n'
                         'fn positive(n: int64) -> bool { return n > 0 }', b'42\nfalse\n')

    def test_function_recursion_and_mutual_recursion(self):
        self.assert_runs('fn factorial(n: int64) -> int64 {\n'
                         'if n == 0 { return 1 } else { return n * factorial(n - 1) }\n}\n'
                         'fn odd(n: int64) -> bool {\n'
                         'if n == 0 { return false } else { return even(n - 1) }\n}\n'
                         'fn main() {\nprint(factorial(10))\nprint(odd(7))\nprint(even(8))\n}\n'
                         'fn even(n: int64) -> bool {\n'
                         'if n == 0 { return true } else { return odd(n - 1) }\n}',
                         b'3628800\ntrue\ntrue\n')

    def test_void_functions_early_return_and_discarded_value(self):
        self.assert_runs('fn greet(active: bool) {\nif !active { return }\nprint("hi")\n}\n'
                         'fn result() -> int64 { print(99)\nreturn 7 }\n'
                         'fn main() {\ngreet(false)\ngreet(true)\nresult()\nreturn\nprint("after")\n}',
                         b'hi\n99\n')

    def test_argument_evaluation_and_expression_stack_survive_calls(self):
        self.assert_runs('fn mark(n: int64) -> int64 { print(n)\nreturn n }\n'
                         'fn difference(a: int64, b: int64) -> int64 { return a - b }\n'
                         'fn main() {\nprint(100 + difference(mark(8), mark(3)) * mark(2))\n}',
                         b'8\n3\n2\n110\n')

    def test_functions_have_independent_frames_and_lexical_scope(self):
        self.assert_runs('fn sum(n: int64) -> int64 {\nvar x = n\n'
                         'if n > 0 {\nlet next = sum(n - 1)\nx = x + next\n}\nreturn x\n}\n'
                         'fn flag(x: bool) -> bool { if true { let x = 1\nprint(x) }\nreturn x }\n'
                         'fn main() {\nvar x = 100\nprint(sum(8))\nprint(x)\nprint(flag(true))\n}',
                         b'36\n100\n1\ntrue\n')

    def test_function_signatures_crlf_and_multiline_arguments(self):
        self.assert_runs(('fn pick(\nvalue: int64,\nactive: bool\n) -> int64 {\n'
                          'if active { return value } else { return -value }\n}\n'
                          'fn main() { print(pick(\n7,\nfalse\n)) }').replace('\n', '\r\n'), b'-7\n')

    def test_function_call_limit_and_counter_restoration(self):
        prefix = 'fn recurse(n: int64) -> int64 {\n'
        prefix += 'if n == 0 { return 0 } else { return recurse(n - 1) }\n}\n'
        self.assert_runs(prefix + 'fn main() {\nvar i = 0\nwhile i < 10000 {\n'
                         'recurse(62)\ni = i + 1\n}\nprint(i)\n}', b'10000\n')
        self.output.unlink()
        result = self.build(prefix + 'fn main() { print(recurse(63)) }')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(self.output)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'call depth', result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_function_type_scope_and_return_errors(self):
        invalid = [
            'fn f(n: int64) -> int64 { return n }\nfn main() { print(f(true)) }',
            'fn f(n: int64) -> int64 { return n }\nfn main() { print(f()) }',
            'fn f(n: int64) -> int64 { return n }\nfn main() { print(f(1, 2)) }',
            'fn main() { print(missing()) }', 'fn main() { print(main()) }',
            'fn f() {}\nfn main() { print(f()) }',
            'fn f() -> bool { return 1 }\nfn main() {}',
            'fn f() -> int64 { return }\nfn main() {}',
            'fn f() -> int64 {}\nfn main() {}',
            'fn f(n: bool) -> int64 { if n { return 1 } }\nfn main() {}',
            'fn f() -> int64 { while true { return 1 } }\nfn main() {}',
            'fn main() { return 1 }', 'fn main(n: int64) {}',
            'fn f() {}\nfn f() {}\nfn main() {}',
            'fn f(n: int64, n: int64) {}\nfn main() {}',
            'fn f(n: int64) { n = 1 }\nfn main() {}',
            'fn f(n: int64) { let n = 1 }\nfn main() {}',
            'fn f() { let hidden = 1 }\nfn main() { print(hidden) }',
            'fn f() { break }\nfn main() {}',
            'fn f() -> int64 { return 1 }\nfn main() { let f = 1\nprint(f()) }',
            'fn main() { fn f() {} }', 'fn f(n) {}\nfn main() {}',
            'fn f(n: void) {}\nfn main() {}', 'fn f() -> string {}\nfn main() {}',
        ]
        for source in invalid:
            with self.subTest(source=source):
                result = self.build(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)
                self.assertFalse(self.output.exists())

    def test_function_and_parameter_limits(self):
        names = ['a' + str(i) for i in range(16)]
        source = 'fn sum(' + ', '.join(n + ': int64' for n in names) + ') -> int64 { return '
        source += ' + '.join(names) + ' }\nfn main() { print(sum('
        source += ', '.join(str(i) for i in range(16)) + ')) }'
        self.assert_runs(source, b'120\n')
        self.output.unlink()
        source = 'fn too_many(' + ', '.join('a' + str(i) + ': int64' for i in range(17)) + ') {}\nfn main() {}'
        result = self.build(source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)
        source = ''.join('fn f' + str(i) + '() {}\n' for i in range(256)) + 'fn main() {}'
        result = self.build(source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)

    def test_function_name_errors_point_to_the_name(self):
        for source, location in [
            ('fn main() {\n  missing()\n}', ':2:3: error:'),
            ('fn helper() -> int64 {\n return missing + 1\n}\nfn main() {}', ':2:9: error:'),
        ]:
            with self.subTest(source=source):
                result = self.build(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn((str(self.source) + location).encode(), result.stderr)

    def test_signature_scan_does_not_duplicate_string_arena(self):
        payload = 'x' * 800000
        self.assert_runs('fn unused() { print("' + payload + '") }\n'
                         'fn main() { print("ok") }', b'ok\n')

    def test_all_function_slots_and_symbol_limits(self):
        source = ''.join('fn f' + str(i) + '() {}\n' for i in range(255))
        self.assert_runs(source + 'fn main() { f254()\nprint(1) }', b'1\n')
        self.output.unlink()
        params = ', '.join('p' + str(i) + ': int64' for i in range(16))
        source = ''.join('fn f' + str(i) + '(' + params + ') {}\n' for i in range(255))
        locals_ = ''.join('let x' + str(i) + ' = 1\n' for i in range(16))
        self.assert_runs(source + 'fn main() {\n' + locals_ + 'print(x15)\n}', b'1\n')
        self.output.unlink()
        result = self.build(source + 'fn main() {\n' + locals_ + 'let extra = 1\n}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)

    def test_legacy_benchmark_rejects_incompatible_calling_convention(self):
        result = subprocess.run(['python3', str(ROOT / 'benchmarks/run_benchmark.py'),
                                 '--compiler', str(COMPILER), '--work-dir',
                                 str(self.directory / 'work'), '--output-dir',
                                 str(self.directory / 'results'), '--steps', '1'],
                                capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'requires Ramos 0.2', result.stderr)
        self.assertFalse((self.directory / 'work').exists())
        self.assertFalse((self.directory / 'results').exists())

    def test_nested_calls_in_assignment_rhs(self):
        self.assert_runs('fn add(a: int64, b: int64) -> int64 { return a + b }\n'
                         'fn main() {\nvar value = 1\n'
                         'value = 100 + add(add(value, 2), add(3, 4))\nprint(value)\n}', b'110\n')

    def test_nested_if_return_paths(self):
        source = 'fn choose(a: bool, b: bool) -> int64 {\n'
        source += 'if a { if b { return 10 } else { return 20 } }\n'
        source += 'else { if b { return 30 } else { return 40 } }\n}\n'
        self.assert_runs(source + 'fn main() {\nprint(choose(true, true))\n'
                         'print(choose(true, false))\nprint(choose(false, true))\n'
                         'print(choose(false, false))\n}', b'10\n20\n30\n40\n')
        self.output.unlink()
        result = self.build(source.replace('else { return 40 }', '') + 'fn main() {}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'without returning', result.stderr)
        self.assertFalse(self.output.exists())

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
