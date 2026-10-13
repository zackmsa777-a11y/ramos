"""Exact scientific/compact decimal output against independent binary64 references."""
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import math
import random
import struct
import subprocess
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_libraries import BOOTSTRAP


def reference(value, precision, compact=False):
    """Round Decimal.from_float once, then apply the documented notation rules."""
    negative = math.copysign(1.0, value) < 0
    prefix = '-' if negative else ''
    if value == 0:
        return prefix + ('0' if compact else '0' + ('.' + '0' * precision if precision else '') + 'e+0')
    retained = precision if compact else precision + 1
    with localcontext() as context:
        context.prec = 2000
        exact = abs(Decimal.from_float(value))
        rounded = exact.quantize(Decimal(1).scaleb(exact.adjusted() - retained + 1), rounding=ROUND_HALF_EVEN)
        exponent = rounded.adjusted()
        # A carry can increase the exponent and leave a redundant coefficient digit.
        mantissa = rounded.scaleb(-exponent)
        text = format(mantissa, f'.{retained - 1}f')
        if compact:
            text = text.rstrip('0').rstrip('.') if '.' in text else text
            if -4 <= exponent < precision:
                plain = format(rounded, 'f')
                if '.' in plain:
                    plain = plain.rstrip('0').rstrip('.')
                return prefix + plain
        return prefix + text + f'e{exponent:+d}'


def values():
    selected = [0.0, -0.0, 0.1, -0.3, 0.1 + 0.2, 2.5, 3.5, 1.25, 1.75,
                9.5, 99.5, 9999.5, 0.000099995, 0.0001, 0.00001, 1e-100, -1e-100,
                1e100, -1e100, 5e-324, -5e-324, 2.2250738585072014e-308,
                1.7976931348623157e308, -1.7976931348623157e308]
    for value in [1e-4, 1e-5, 1.0, 10.0, 1e17, 1e-100, 1e100, 2.2250738585072014e-308]:
        selected += [math.nextafter(value, 0), math.nextafter(value, math.inf)]
    rng = random.Random(24101)
    while len(selected) < 256:
        value = struct.unpack('>d', rng.getrandbits(64).to_bytes(8, 'big'))[0]
        if math.isfinite(value):
            selected.append(value)
    return selected


@unittest.skipIf(BOOTSTRAP, 'retained seed does not parse weave/struct/float syntax')
class MathOutputTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library

    def run_native(self, *args, **kwargs):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=60, **kwargs)

    def test_exact_output_against_independent_decimal(self):
        self.standard_library()
        source = 'weave "stdlib/math.ramos"\nfn show(v: float64) {\n'
        source += '\n'.join(f'print(math_scientific(v, {p}))' for p in [0, 1, 6, 16, 18])
        source += '\n' + '\n'.join(f'print(math_format(v, {p}))' for p in [1, 2, 6, 17])
        source += '\n}\nfn main() {\n' + '\n'.join(f'show({repr(v)})' for v in values()) + '\n}'
        self.build_ok(source)
        result = self.run_native()
        expected = []
        for value in values():
            expected += [reference(value, p) for p in [0, 1, 6, 16, 18]]
            expected += [reference(value, p, True) for p in [1, 2, 6, 17]]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode().splitlines(), expected)
        self.assertEqual(len(expected), 2304)

    def test_seventeen_digits_round_trip_including_signed_zero(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
fn check(v: float64) {
let text = math_format(v, 17)
let r = math_parse(text)
if r.status != 0 || r.value != v { stderr(to_bytes(text))
exit(9) }
if v == 0.0 && math_text(v, 0) != math_text(r.value, 0) { exit(8) }
}
fn main() {
''' + '\n'.join(f'check({repr(v)})' for v in values()) + '\nprint("round trip passed")\n}')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'round trip passed\n'), result.stderr)

    def test_output_gc_roots_aliases_and_independent_status(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/math.ramos"
fn main() {
text_to_int("bad")
read_file("does-not-exist")
let old_io = io_error()
let kept = math_format(5e-324, 17)
let alias = kept
for i in 0..6000 {
let a = math_format(1e-100, 17)
let b = math_scientific(3.5, 0)
if a != s"1e-100" || b != s"4e+0" { exit(9) }
}
collect()
print(kept)
print(alias == kept)
print(parse_error())
print(io_error() == old_io)
print(memory_used() < 1048576)
print(math_text(3.5, 3))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'4.9406564584124654e-324\ntrue\n-22\ntrue\ntrue\n3.500\n'), result.stderr)

    def test_invalid_precision_checked_before_arithmetic(self):
        self.standard_library()
        for name, bad, message in [('math_scientific', [-9223372036854775808, -1, 19, 9223372036854775807], b'places must be 0..18'),
                                   ('math_format', [-9223372036854775808, 0, 18, 9223372036854775807], b'digits must be 1..17')]:
            for precision in bad:
                with self.subTest(name=name, precision=precision):
                    self.build_ok(f'weave "stdlib/math.ramos"\nfn main() {{ print({name}(0.0, {precision})) }}')
                    result = self.run_native()
                    self.assertEqual((result.returncode, result.stdout), (1, b''), result.stderr)
                    self.assertIn(b'Ramos library error:', result.stderr)
                    self.assertIn(message, result.stderr)
