"""Binary64 values, independent decimal rounding and finite arithmetic safety."""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import math
import random
import struct
import subprocess
import unittest
import test_ramos as support
import test_cli_streams as streams
import test_devtools as devtools
from test_libraries import BOOTSTRAP


def fixed(value, places):
    with localcontext() as context:
        context.prec = 400
        rounded = Decimal.from_float(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
        return format(rounded, f'.{places}f')


@unittest.skipIf(BOOTSTRAP, 'retained assembly seed does not parse float64 syntax')
class FloatTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    example = streams.StreamTests.example
    compiler_command = devtools.DevToolsTests.compiler_command
    write_source = devtools.DevToolsTests.write_source
    native_path = staticmethod(str)
    compiler_executable = support.COMPILER
    compiler_prefix = []

    def run_native(self, *args):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=30)

    def test_arithmetic_comparisons_calls_and_default_print(self):
        self.build_ok('''fn twice(x: float64) -> float64 { return x * 2.0 }
fn main() {
print(0.1 + 0.2)
print(4.5 - 1.25)
print(1.25 * 2.0)
print(7.5 / 2.0)
print(twice(-1.25))
print(+1.5)
print(1.5 == 1.5)
print(1.5 != 1.25)
print(-1.5 < 1.25)
print(1.25 <= 1.25)
print(1.5 > 1.25)
print(1.25 >= 1.25)
print(1.5 < 1.25)
print(-0.0 == 0.0)
print(-0.0)
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'0.300000\n3.250000\n2.500000\n3.750000\n-2.500000\n1.500000\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\nfalse\ntrue\n-0.000000\n'), result.stderr)

    def test_arrays_structs_compound_assignment_and_gc(self):
        self.build_ok('''struct Point { x: float64, y: float64 }
fn main() {
let p = Point(1.25, 2.5)
let a = array(float64, 3, 0.0)
a[1] = p.x
p.x += a[1]
a[1] -= 0.25
var value = 0.25
value += 0.5
value -= 0.125
let b = array_resize(a, 5, 1.5)
let empty = array_empty(float64)
collect()
print(p.x)
print(a[1])
print(value)
print(b[4])
print(array_len(empty))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'2.500000\n1.000000\n0.625000\n1.500000\n0\n'), result.stderr)

    def test_explicit_conversions_and_integer_boundaries(self):
        self.build_ok('''fn main() {
print(float64(-9223372036854775808))
print(float_to_int(-9223372036854775808.0))
print(float_to_int(9223372036854774784.0))
print(float_to_int(-2.9))
print(float_to_int(2.9))
print(float64(9007199254740993) == 9007199254740992.0)
print(float_to_int(-0.0))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'-9223372036854775808.000000\n-9223372036854775808\n9223372036854774784\n-2\n2\ntrue\n0\n'), result.stderr)

    def test_literals_encode_independent_binary64_reference(self):
        rng = random.Random(1800)
        literals = ['0.1', '0.3', '1.7976931348623157e308', '2.2250738585072014e-308',
                    '2.225073858507201e-308', '5e-324', '2e-324', '2.4703282292062327e-324',
                    '2.4703282292062328e-324', '1e-400', '9007199254740993.0',
                    '1.00000000000000011102230246251565404236316680908203125',
                    '1.00000000000000011102230246251565404236316680908203126']
        with localcontext() as context:
            context.prec = 2000
            literals += [format(Decimal(2) ** -1075, 'e'), format(Decimal(2) ** -1074, 'e')]
        literals += [f'{rng.randrange(1, 10**17)}e{rng.randrange(-340, 290)}' for _ in range(80)]
        for literal in literals:
            with self.subTest(literal=literal):
                self.build_ok('fn main() { print(' + literal + ') }')
                # Last MOV RAX,imm64 belongs to the sole literal in main. Compare
                # its bytes with Python's independent correctly-rounded converter.
                code = self.output.read_bytes()
                at = code.rfind(b'\x48\xb8')
                self.assertGreater(at, 4096)
                self.assertEqual(code[at + 2:at + 10], struct.pack('<d', float(literal)))

    def test_fixed_decimal_rounding_independent_reference(self):
        rng = random.Random(1818)
        values = [0.0, -0.0, 0.1, 0.3, 2.5, 3.5, -2.5, -3.5, 1.25, 1.75,
                  5e-324, -5e-324, 1.7976931348623157e308, -1.7976931348623157e308]
        values += [struct.unpack('<d', struct.pack('<Q', rng.randrange(0, 0x7ff0000000000000)))[0] for _ in range(50)]
        cases = [(value, places) for value in values for places in [0, 1, 6, 18]]
        source = 'fn main() {\n' + '\n'.join(f'print(float_to_text({repr(value)}, {places}))' for value, places in cases) + '\n}'
        self.build_ok(source)
        result = self.run_native()
        expected = ''.join(fixed(value, places) + '\n' for value, places in cases).encode()
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)

    def test_sqrt_normal_subnormal_and_signed_zero(self):
        self.build_ok('''fn main() {
print(float_to_text(float_sqrt(2.0), 18))
print(float_sqrt(4.0))
print(float_sqrt(-0.0))
print(float_sqrt(5e-324) > 0.0)
print(5e-324 / 2.0 == 0.0)
print(1e-300 * 1e-30 > 0.0)
}''')
        result = self.run_native()
        expected = (fixed(math.sqrt(2.0), 18) + '\n2.000000\n-0.000000\ntrue\ntrue\nfalse\n').encode()
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)

    def test_invalid_operations_trap_cleanly(self):
        for expression in ['1.0 / 0.0', '1.0 / -0.0', '0.0 / 0.0', '1e308 * 2.0',
                           'float_sqrt(-1.0)', 'float_to_int(9223372036854775808.0)',
                           'float_to_int(-9223372036854777856.0)',
                           'float_to_int(float64(9223372036854775807))',
                           'float_to_text(1.0, -1)', 'float_to_text(1.0, 19)']:
            with self.subTest(expression=expression):
                self.build_ok('fn main() { print(' + expression + ') }')
                result = self.run_native()
                self.assertEqual(result.returncode, 1)
                self.assertIn(b'invalid float operation', result.stderr)

    def test_types_unsupported_syntax_and_literal_limits_preserve_output(self):
        self.output.write_bytes(b'keep')
        for expression in ['1.0 + 1', '1 == 1.0', '1.0 % 0.5', 'float64(1.0)',
                           'float_to_int(1)', 'float_sqrt(4)', 'float_to_text(1.0, 1.0)',
                           '.5', '1.0e', '1.0e+', '1e401', '1e-401', '1e309',
                           '1.7976931348623159e308', '1.' + '1' * 768]:
            with self.subTest(expression=expression):
                result = self.build('fn main() { print(' + expression + ') }', '--force')
                self.assertEqual(result.returncode, 1)
                self.assertIn(b'error:', result.stderr)
                self.assertEqual(self.output.read_bytes(), b'keep')

    def test_range_syntax_and_formatter_float_tokens(self):
        source = 'fn main( ) {\nvar n=1.25e+2\nn+=0.5\nfor i in 0..2 {print(n)}\n}'
        self.build_ok(source)
        before = self.output.read_bytes()
        result = self.compiler_command('fmt', self.native_path(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'1.25e+2', result.stdout)
        self.assertIn(b'0..2', result.stdout)
        self.build_ok(result.stdout)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.compiler_command('fmt', self.native_path(self.source)).stdout, result.stdout)

    def test_math_library_helpers_and_checked_clamp(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
fn main() {
print(math_abs(-0.0))
print(math_abs(-1.25))
print(math_min(3.5, 1.25))
print(math_max(3.5, 1.25))
print(math_clamp(9.0, 0.0, 2.5))
print(math_text(math_sqrt(2.0), 3))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'0.000000\n1.250000\n1.250000\n3.500000\n2.500000\n1.414\n'), result.stderr)
        self.build_ok('weave "stdlib/math.ramos"\nfn main() { print(math_clamp(0.0, 2.0, 1.0)) }')
        result = self.run_native()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'reversed float clamp', result.stderr)

    def test_arithmetic_independent_reference_and_recursive_calls(self):
        rng = random.Random(1853)
        cases = []
        for i in range(50):
            a = rng.uniform(-10000.0, 10000.0)
            b = rng.uniform(0.01, 10000.0)
            for op in ['+', '-', '*', '/']:
                cases.append((a, op, b, eval(f'a {op} b')))
        source = 'fn main() {\n' + '\n'.join(
            f'print(float_to_text({repr(a)} {op} {repr(b)}, 18))' for a, op, b, value in cases) + '\n}'
        self.build_ok(source)
        result = self.run_native()
        self.assertEqual(result.stdout, ''.join(fixed(value, 18) + '\n' for a, op, b, value in cases).encode())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.build_ok('''fn factorial(n: int64) -> float64 {
if n == 0 { return 1.0 }
return float64(n) * factorial(n - 1)
}
fn main() { print(factorial(8)) }
''')
        self.assertEqual(self.run_native().stdout, b'40320.000000\n')

    def test_renderer_matches_independent_pixel_reference_and_preserves_files(self):
        self.example('mandelbrot')
        path = self.directory / 'image.pgm'
        width, height, iterations = 32, 24, 40
        result = self.run_native(self.native_path(path), str(width), str(height), str(iterations))
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = bytearray(f'P5\n{width} {height}\n255\n'.encode())
        for y in range(height):
            ci = float(y) * 2.0 / float(height) - 1.0
            for x in range(width):
                cr = float(x) * 3.5 / float(width) - 2.5
                zr = zi = 0.0
                count = 0
                while count < iterations and zr * zr + zi * zi <= 4.0:
                    real = zr * zr - zi * zi + cr
                    zi = 2.0 * zr * zi + ci
                    zr = real
                    count += 1
                expected.append(0 if count == iterations else 255 - count * 255 // iterations)
        self.assertEqual(path.read_bytes(), expected)
        result = self.run_native(self.native_path(path), '32', '24', '40')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), expected)
        for args in [('0', '24', '40'), ('bad', '24', '40'), ('1024', '1024', '40')]:
            result = self.run_native(self.native_path(path), *args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), expected)
