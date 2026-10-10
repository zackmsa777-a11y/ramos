"""Native comments, diagnostics and short-circuit boolean contracts."""
import random
import os
import subprocess
import unittest
import test_ramos as support

BOOTSTRAP = False
if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
    BOOTSTRAP = b'native assembly bootstrap' in subprocess.check_output([str(support.COMPILER), '--version'])


@unittest.skipIf(BOOTSTRAP, 'the retained assembly seed implements the pre-0.8 grammar')
class UsabilityTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_output(self):
        return subprocess.run([str(self.output)], capture_output=True, timeout=10)

    def test_line_block_comments_strings_and_division(self):
        self.assert_runs('''// Fake fn main() { invalid }
fn /* comment */ main() {
print("// /* */") // quotes " and braces } are ignored
print(8 / 2)
print(9/* inline separator */ / 3)
print((
7 /* multiline
not code + } */ + 5
))
/* empty-looking */
} // EOF comment''', b'// /* */\n4\n3\n12\n')
        self.output.unlink()
        self.assert_runs('fn main() {}//no final newline', b'')

    def test_comment_newlines_and_crlf_are_statement_separators(self):
        self.assert_runs('fn main() {\r\nprint(1) /*\r\n*/ print(2)//tail\r\n}', b'1\n2\n')
        self.output.unlink()
        self.assert_runs('fn main() { print(3) /*\n*/ print(4) }', b'3\n4\n')

    def test_comment_failures_and_source_encoding(self):
        for source, message, location in [
            ('fn main() {\n  /* never closed', b'unterminated block comment', b':2:3:'),
            ('fn main() { /*\r*/ }', b'bare carriage return', b':1:15:'),
            (b'fn main() {} //\x00', b'NUL byte', b':1:16:'),
            (b'fn main() {} //\xff', b'invalid UTF-8', b':1:16:'),
        ]:
            with self.subTest(source=source):
                result = self.build(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertIn(location, result.stderr)
                self.assertFalse(self.output.exists())

    def test_boolean_truth_tables_and_precedence(self):
        statements, results = [], []
        for a in (False, True):
            for b in (False, True):
                left, right = str(a).lower(), str(b).lower()
                statements += [f'print({left} && {right})', f'print({left} || {right})']
                results += [a and b, a or b]
        statements += ['print(true || false && false)', 'print((true || false) && false)',
                       'print(true == false || 1 < 2 && false)', 'print(!(false || true))',
                       'print(!false && 2 + 3 * 4 == 14)', 'print(false || false || true && true)']
        results += [True, False, False, False, True, True]
        self.assert_runs('fn main() {\n' + '\n'.join(statements) + '\n}',
                         ''.join(str(v).lower() + '\n' for v in results).encode())

    def test_short_circuit_skips_runtime_failures(self):
        self.assert_runs('''fn main() {
print(false && (1 / 0 == 0))
print(true || (buffer_get(buffer(0), 0) == 0))
print(false && (9223372036854775807 + 1 == 0))
print(true || (false && (1 / 0 == 0)))
}''', b'false\ntrue\nfalse\ntrue\n')
        for expression in ('true && (1 / 0 == 0)', 'false || (1 / 0 == 0)'):
            result = self.build(f'fn main() {{ print({expression}) }}', '--force')
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_output()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'arithmetic', result.stderr)

    def test_boolean_calls_evaluate_left_to_right_and_keep_arguments(self):
        self.assert_runs('''fn mark(n: int64, value: bool) -> bool {
print(n)
return value
}
fn pick(a: bool, b: bool) -> bool { return a || b }
fn number(b: bool) -> int64 {
if b { return 1 }
return 0
}
fn main() {
print(mark(1, false) && mark(2, true))
print(mark(3, true) || mark(4, false))
print(mark(5, true) && (mark(6, false) || mark(7, true)))
print(pick(mark(8, false) && mark(9, true), mark(10, true) || mark(11, false)))
print(100 + number(false || (true && true)))
}''', b'1\nfalse\n3\ntrue\n5\n6\n7\ntrue\n8\n10\ntrue\n101\n')

    def test_seeded_boolean_trees_match_independent_evaluation_and_trace(self):
        rng = random.Random(8010)
        def tree(depth):
            if depth == 0:
                return ('leaf', rng.randrange(10000), bool(rng.randrange(2)))
            return (rng.choice(('&&', '||')), tree(depth - 1), tree(depth - 1))
        def source(node):
            if node[0] == 'leaf':
                return f'mark({node[1]}, {str(node[2]).lower()})'
            return f'({source(node[1])} {node[0]} {source(node[2])})'
        def evaluate(node, trace):
            if node[0] == 'leaf':
                trace.append(str(node[1]))
                return node[2]
            left = evaluate(node[1], trace)
            if node[0] == '&&':
                return left and evaluate(node[2], trace)
            return left or evaluate(node[2], trace)
        statements, expected = [], []
        for _ in range(80):
            node = tree(4)
            statements.append('print(' + source(node) + ')')
            value = evaluate(node, expected)
            expected.append(str(value).lower())
        self.assert_runs('fn mark(n: int64, b: bool) -> bool {\nprint(n)\nreturn b\n}\n'
                         'fn main() {\n' + '\n'.join(statements) + '\n}',
                         ('\n'.join(expected) + '\n').encode())

    def test_loop_guards_and_long_chains_keep_stack_balanced(self):
        chain = ' && '.join(['true'] * 1000)
        self.assert_runs('''fn main() {
let b = "abc"
var i = 0
while i < buffer_len(b) && buffer_get(b, i) > 0 { i = i + 1 }
print(i)
var rounds = 0
while rounds < 1000 {
if ''' + chain + ''' { rounds = rounds + 1 }
}
print(rounds)
}''', b'3\n1000\n')

    def test_invalid_boolean_operands_are_checked_even_when_skipped(self):
        for expression in ('1 && true', 'false && 1', 'true || 1', 'false || "x"',
                           'true || missing', 'false && f()'):
            self.output.write_bytes(b'preserve output')
            result = self.build('fn f() {}\nfn main() { print(' + expression + ') }', '--force')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(self.output.read_bytes(), b'preserve output')
            self.assertIn(b'error:', result.stderr)
        for expression in ('true & false', 'true | false'):
            result = self.build('fn main() { print(' + expression + ') }', '--force')
            self.assertEqual(result.returncode, 1)
            self.assertIn(b'use', result.stderr)

    def test_diagnostics_explain_tokens_types_names_and_arity(self):
        cases = [
            ('fn main() {\n  print(missing)\n}', b'unknown variable', b':2:9:'),
            ('fn main() { print(missing()) }', b'unknown function', None),
            ('fn main() { if 1 {} }', b'expected bool, found int64', None),
            ('fn main() { print(true + false) }', b'require int64', None),
            ('fn main() { print(true && 1) }', b'require bool', b':1:24:'),
            ('fn main() { print("\\q") }', b'unsupported string escape', None),
            ('fn main() { print("abc) }', b'unterminated string literal', None),
            ('fn main() { let a 1 }', b"expected '='", None),
            ('fn main() { let a = 1\na = 2 }', b'immutable let binding', None),
            ('fn f(n: int64) {}\nfn main() { f() }', b'too few function arguments', None),
            ('fn f(n: int64) {}\nfn main() { f(1, 2) }', b'too many function arguments', None),
            ('fn f(n: int64) {}\nfn main() { f(false) }', b'expected int64, found bool', None),
            ('fn f() -> int64 { return false }\nfn main() {}', b'expected int64, found bool', None),
            ('fn main() { var n = 0\nn = true }', b'expected int64, found bool', None),
            ('fn f(n: unknown) {}\nfn main() {}', b'expected type:', None),
            ('fn main() { break }', b'enclosing loop', None),
            ('fn main() { print(@) }', b'unexpected character', None),
            ('fn other() {}', b'missing main function', None),
        ]
        for source, message, location in cases:
            with self.subTest(source=source):
                result = self.build(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
                if location:
                    self.assertIn(location, result.stderr)
                self.assertFalse(self.output.exists())
