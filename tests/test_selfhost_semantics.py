"""Grammar and type boundaries used by the Ramos implementation itself."""
import unittest
import test_ramos as support


class CompilerBoundaryTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs
    def test_void_values_cannot_be_compared(self):
        for operator in ('==', '!='):
            result = self.build('fn f() {}\nfn main() { print(f() ' + operator + ' f()) }')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(self.output.exists())

    def test_call_statements_do_not_accept_trailing_arithmetic(self):
        result = self.build('fn f() -> int64 { return 1 }\nfn main() { f() + 1 }')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.output.exists())

    def test_bare_carriage_return_is_rejected(self):
        result = self.build('fn main() {\rprint(1) }')
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_unary_newline_and_multiline_call_arguments(self):
        self.assert_runs('fn f(n: bool) -> bool { return !n }\nfn main() {\n'
                         'print(!true)\nprint(f(\n!true\n))\nprint(!!false)\n}',
                         b'false\ntrue\nfalse\n')
