"""Arithmetic and evaluation contracts for both native emitters."""
import random
import subprocess
import unittest
import test_ramos as support


class OptimizationTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_output(self):
        return subprocess.run([str(self.output)], capture_output=True, timeout=10)

    def test_constant_and_dynamic_division_agree_at_signed_boundaries(self):
        rng = random.Random(70101)
        divisors = [1, 2, 3, 5, 7, 10, 31, 64, 255, 256, 257, 1000,
                    16777216, 1000000007, 1073741824, 2147483647,
                    2147483648, 4294967295, 9223372036854775807]
        statements, expected = [], []
        for i, divisor in enumerate(divisors):
            values = [-2**63, -2**63 + 1, -2**63 + divisor, 2**63 - 1,
                      2**63 - 1 - divisor, -divisor, -divisor + 1,
                      divisor - 1, divisor, 0, 1, -1]
            values += [rng.randrange(-2**63, 2**63) for _ in range(16)]
            statements.append(f'var divisor_{i} = {divisor}')
            for value in values:
                quotient = abs(value) // divisor * (-1 if value < 0 else 1)
                remainder = value - quotient * divisor
                statements += [f'print({value} / {divisor})', f'print({value} % {divisor})',
                               f'print({value} / divisor_{i})', f'print({value} % divisor_{i})']
                expected += [quotient, remainder, quotient, remainder]
        self.assert_runs('fn main() {\n' + '\n'.join(statements) + '\n}',
                         ''.join(f'{n}\n' for n in expected).encode())

    def test_constant_arithmetic_comparisons_and_parentheses(self):
        self.assert_runs('''fn id(n: int64) -> int64 { return n }
fn main() {
var n = -17
print((id(n) + (5)) * 3 - 1)
print(id(n) / (5))
print(id(n) % (5))
print((n < 0) == true)
print(n + 17 == 0)
print(3 + 5 * 7 / 2 % 11)
print(id(7) + id(11) * (id(13) - id(3)))
print((8 / 1) + (8 % 1))
print(9223372036854775807 * 1)
print(-9223372036854775808 + 0)
}''', b'-37\n-3\n-2\ntrue\ntrue\n9\n117\n8\n9223372036854775807\n-9223372036854775808\n')

    def test_checked_constant_arithmetic_keeps_prior_side_effects(self):
        for expression in ('9223372036854775807 + 1', '-9223372036854775808 - 1',
                           '9223372036854775807 * 2', '7 / 0', '7 % 0',
                           '-9223372036854775808 / -1', '-9223372036854775808 % -1'):
            with self.subTest(expression=expression):
                result = self.build('fn mark() -> int64 { print(17)\nreturn 0 }\n'
                                    'fn main() { print(mark() + (' + expression + ')) }', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.run_output()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b'17\n')
                self.assertIn(b'arithmetic', result.stderr)

    def test_buffer_failure_checks_index_before_byte_value(self):
        for index, value, message in [(-1, 256, b'buffer index'), (1, -1, b'buffer index'),
                                      (0, -1, b'byte value'), (0, 256, b'byte value')]:
            with self.subTest(index=index, value=value):
                result = self.build(f'fn main() {{ print(17)\nbuffer_set(buffer(1), {index}, {value}) }}', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.run_output()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b'17\n')
                self.assertIn(message, result.stderr)

    def test_nested_buffer_calls_preserve_evaluation_order(self):
        self.assert_runs('''fn mark(n: int64) -> int64 { print(n)
return n }
fn main() {
let b = buffer(3)
buffer_set(b, mark(1), mark(65))
print(10 + buffer_get(b, mark(1)) / 5)
print(buffer_len(buffer(mark(3))))
print(buffer_get(b, 1) * 2 + buffer_len(b))
}''', b'1\n65\n1\n23\n3\n3\n133\n')

    def test_loop_branch_targets_and_recursive_arguments(self):
        self.assert_runs('''fn sum(n: int64) -> int64 {
if n == 0 { return 0 }
return n + sum(n - 1)
}
fn main() {
var i = 0
var result = 0
while i < 1000 {
i = i + 1
if i % 3 == 0 { continue }
if i == 999 { break }
if i % 2 == 0 { result = result + sum(3) }
else { result = result + 5 }
}
print(result)
}''', b'3669\n')
