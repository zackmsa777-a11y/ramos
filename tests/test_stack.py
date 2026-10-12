"""Execute recursion and stack failures; shared with native Windows proof."""
import os
import subprocess
import unittest
import test_ramos as support

BOOTSTRAP = False
if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
    BOOTSTRAP = b'native assembly bootstrap' in subprocess.check_output([str(support.COMPILER), '--version'])

@unittest.skipIf(BOOTSTRAP, 'the retained seed has the original 64-call ABI')
class StackTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def stack_run(self):
        return subprocess.run([str(self.output)], capture_output=True, timeout=10)

    @staticmethod
    def wide_source(depth):
        locals = ''.join(f'let value_{i} = {i}\n' for i in range(2047))
        return ('fn wide(n: int64) -> int64 {\n' + locals +
                'if n == 0 { return value_2046 }\nreturn wide(n - 1)\n}\n' +
                f'fn main() {{ print(wide({depth})) }}')

    def test_deep_mutual_calls_and_pending_expression_values(self):
        self.assert_runs('''fn left(n: int64) -> int64 {
if n == 0 { return 7 }
return n + right(n - 1)
}
fn right(n: int64) -> int64 {
if n == 0 { return 7 }
return n + left(n - 1)
}
fn main() {
var i = 0
while i < 50 { print(left(800))
i = i + 1 }
}''', b'320407\n' * 50)

    def test_large_recursive_frames_fit_within_budget(self):
        self.assert_runs(self.wide_source(220), b'2046\n')

    def test_large_recursive_frames_fail_with_ramos_error(self):
        result = self.build(self.wide_source(300))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.stack_run()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'Ramos runtime error: stack budget exceeded\n')

    def test_managed_roots_survive_deep_calls_and_collection(self):
        self.assert_runs('''fn keep(n: int64) -> int64 {
let text = string(int_to_text(n))
if n == 0 { collect()
return len(text) }
let result = keep(n - 1)
return result + len(text)
}
fn main() { print(keep(500)) }''', b'1393\n')
