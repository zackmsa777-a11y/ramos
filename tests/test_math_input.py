"""Fallible Ramos-written decimal parsing and real streamed numerical input."""
from decimal import Decimal, localcontext
import math
import random
import subprocess
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_float import fixed
from test_libraries import BOOTSTRAP


@unittest.skipIf(BOOTSTRAP, 'retained seed does not parse weave/struct/float syntax')
class MathInputTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    example = streams.StreamTests.example
    native_path = staticmethod(str)

    def run_native(self, *args, **kwargs):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=60, **kwargs)

    def test_public_results_string_bytes_signs_and_independent_status(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
fn main() {
text_to_int("bad")
read_file("does-not-exist")
let old_io = io_error()
let a = math_parse(s"-2.5e+2")
let b = math_parse_bytes("+001.25E-1")
print(a.status)
print(a.value)
print(b.status)
print(b.value)
print(math_parse(s"-0").value)
print(math_parse(s"-1e-400").value)
print(math_parse(s"5e-324").value > 0.0)
print(math_parse(s"invalid").value)
print(math_parse(s"invalid").status)
print(parse_error())
print(io_error() == old_io)
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'0\n-250.000000\n0\n0.125000\n-0.000000\n-0.000000\ntrue\n0.000000\n-22\n-22\ntrue\n'), result.stderr)

    def test_independent_correct_rounding_for_normal_subnormal_and_ties(self):
        rng = random.Random(18101)
        inputs = ['0', '-0.0', '+0', '0.1', '-0.3', '1.7976931348623157e308',
                  '-1.7976931348623157e308', '1.7976931348623158e308',
                  '2.2250738585072014e-308', '2.225073858507201e-308',
                  '5e-324', '-5e-324', '2e-324', '-1e-400', '1e-400',
                  '2.4703282292062327e-324', '2.4703282292062328e-324',
                  '9007199254740993', '9223372036854775807', '-9223372036854775808',
                  '1.00000000000000011102230246251565404236316680908203125',
                  '1.00000000000000011102230246251565404236316680908203126']
        with localcontext() as context:
            context.prec = 2000
            inputs += [format(Decimal(2) ** -1075, 'e'), format(Decimal(2) ** -1074, 'e')]
        inputs += [f'{rng.choice(["", "-", "+"])}{rng.randrange(1, 10**18)}e{rng.randrange(-400, 290)}' for _ in range(200)]
        inputs += ['0.' + '0' * rng.randrange(1, 250) + str(rng.randrange(1, 10**16)) for _ in range(30)]
        inputs += ['0.' + ''.join(str(rng.randrange(10)) for _ in range(767)) for _ in range(10)]
        values = [float(text) for text in inputs]
        self.assertTrue(all(math.isfinite(v) for v in values))
        self.standard_library()
        # Normalize with exact powers of two so 18 fixed digits distinguish every
        # binary64 significand, even the smallest subnormal. Python frexp and
        # Decimal supply the independent significand/exponent reference.
        source = '''weave "stdlib/math.ramos"
fn show(text: bytes) {
let parsed = math_parse_bytes(text)
print(parsed.status)
var significand = parsed.value
var exponent = 0
if significand != 0.0 {
if significand < 0.0 { significand = -significand }
while significand < 1.0 { significand = significand * 2.0
exponent -= 1 }
while significand >= 2.0 { significand = significand / 2.0
exponent += 1 }
if parsed.value < 0.0 { significand = -significand }
}
print(float_to_text(significand, 18))
print(exponent)
}
fn main() {
''' + '\n'.join('show("' + text + '")' for text in inputs) + '\n}'
        self.build_ok(source)
        result = self.run_native()
        expected = []
        for value in values:
            fraction, exponent = math.frexp(value)
            significand = fraction * 2.0 if value != 0 else value
            expected.extend(['0', fixed(significand, 18), str(exponent - 1 if value != 0 else 0)])
        self.assertEqual((result.returncode, result.stdout), (0, ('\n'.join(expected) + '\n').encode()), result.stderr)
        self.assertEqual(len(inputs), 264)

    def test_syntax_caps_and_range_failure_are_fallible(self):
        self.standard_library()
        cases = [(s, -22) for s in ['', '+', '-', '.5', '1.', '1.e2', 'e1', '1e', '1e+',
                                   '1e-', '1e2.0', '1e2e3', '--1', '++1', '+-1', '1..2',
                                   ' 1', '1 ', '1\t', '0x1', 'inf', 'NaN', '١', '1_000', '1\0x']]
        cases += [(s, -34) for s in ['1e309', '-1e309', '1.7976931348623159e308', '9' * 768]]
        cases += [(s, -27) for s in ['1e401', '1e-401', '0e401', '0' * 769, '1.' + '1' * 768]]
        cases += [('1e' + '9' * 500 + 'x', -22), ('9' * 769 + 'x', -22), ('1e309x', -22)]
        source = 'weave "stdlib/math.ramos"\nfn main() {\n'
        for index, (text, status) in enumerate(cases):
            literal = text.replace('\\', '\\\\').replace('\t', '\\t').replace('\0', '\\0')
            source += f'let r{index} = math_parse_bytes("{literal}")\nprint(r{index}.status)\nprint(r{index}.value == 0.0)\n'
        source += 'let raw = buffer(1)\nbuffer_set(raw, 0, 255)\nprint(math_parse_bytes(raw).status)\n}'
        self.build_ok(source)
        result = self.run_native()
        expected = ''.join(f'{status}\ntrue\n' for text, status in cases).encode() + b'-22\n'
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)

    def test_exact_caps_whole_buffer_precedence_and_input_unchanged(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
weave "stdlib/text.ramos"
fn main() {
let a = to_bytes(text_repeat(s"0", 767) + s"1")
print(math_parse_bytes(a).value)
print(buffer_len(a))
print(buffer_get(a, 767))
print(math_parse(s"1e+000000400").status)
print(math_parse(s"1e-400").status)
let long = to_bytes(text_repeat(s"9", 1048576))
print(math_parse_bytes(long).status)
buffer_set(long, 1048575, 120)
print(math_parse_bytes(long).status)
let zeros = to_bytes(s"1e" + text_repeat(s"0", 1048574))
print(math_parse_bytes(zeros).value)
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'1.000000\n768\n49\n-34\n0\n-27\n-22\n1.000000\n'), result.stderr)

    def test_repeated_parse_reclaims_work_and_retains_live_results(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
fn main() {
let kept = math_parse(s"0.1")
for i in 0..6000 {
let parsed = math_parse_bytes("1.25e2")
if parsed.status != 0 || parsed.value != 125.0 { exit(9) }
}
collect()
print(kept.status)
print(float_to_text(kept.value, 18))
print(memory_used() < 1048576)
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'0\n0.100000000000000006\ntrue\n'), result.stderr)

    def test_rstats_stdin_and_files_crlf_final_line_and_large_stream(self):
        self.example('rstats')
        payload = b'1.25\r\n-2.5\n3e1'
        expected = b'count=3\nmin=-2.500000\nmax=30.000000\nsum=28.750000\nmean=9.583333\n'
        result = self.run_native(input=payload)
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)
        path = self.directory / 'numbers é.txt'
        path.write_bytes(payload)
        result = self.run_native(self.native_path(path))
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)
        self.assertEqual(path.read_bytes(), payload)
        payload = (b'0' * 700 + b'1\n') * 1536
        self.assertGreater(len(payload), 1048576)
        path.write_bytes(payload)
        result = self.run_native(self.native_path(path))
        expected = b'count=1536\nmin=1.000000\nmax=1.000000\nsum=1536.000000\nmean=1.000000\n'
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)
        self.assertEqual(path.read_bytes(), payload)

    def test_rstats_errors_no_partial_report_and_input_preserved(self):
        self.example('rstats')
        for payload, message in [(b'', b'no numbers'), (b'\n', b'line 1 (status -22)'),
                                 (b'1\nno\n', b'line 2 (status -22)'),
                                 (b'1e309\n', b'status -34'), (b'1e401\n', b'status -27'),
                                 (b'\xff\n', b'status -22')]:
            result = self.run_native(input=payload)
            self.assertEqual((result.returncode, result.stdout), (2, b''), result.stderr)
            self.assertIn(message, result.stderr)
            path = self.directory / 'bad.txt'
            path.write_bytes(payload)
            result = self.run_native(self.native_path(path))
            self.assertEqual((result.returncode, result.stdout), (2, b''), result.stderr)
            self.assertIn(message, result.stderr)
            self.assertEqual(path.read_bytes(), payload)
        path.write_bytes(b'1' * 1048577 + b'\n')
        result = self.run_native(self.native_path(path))
        self.assertEqual((result.returncode, result.stdout), (2, b''))
        self.assertIn(b'input failed', result.stderr)
        result = self.run_native(self.native_path(self.directory / 'missing'))
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'cannot open input', result.stderr)
        result = self.run_native('one', 'two')
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'usage:', result.stderr)
        result = self.run_native(input=b'1e308\n1e308\n')
        self.assertEqual((result.returncode, result.stdout), (1, b''))
        self.assertIn(b'non-finite float result', result.stderr)
