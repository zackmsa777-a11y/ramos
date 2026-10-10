"""Native 0.14 branching, range and compound-assignment contracts."""
import os
import random
import subprocess
import unittest
import test_ramos as support

BOOTSTRAP = False
if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
    BOOTSTRAP = b'native assembly bootstrap' in subprocess.check_output([str(support.COMPILER), '--version'])


@unittest.skipIf(BOOTSTRAP, 'the retained assembly seed implements the pre-0.14 grammar')
class SyntaxTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_native(self):
        return subprocess.run([str(self.output)], capture_output=True, timeout=10)

    def test_else_if_chains_returns_and_short_circuit(self):
        self.assert_runs('''fn mark(n: int64, value: bool) -> bool { print(n)
return value }
fn choose(n: int64) -> int64 {
if n == 0 { return 10 }
else if n == 1 { return 20 }
else if n == 2 { return 30 }
else { return 40 }
}
fn main() {
for i in 0..4 { print(choose(i)) }
if mark(1, false) { print(100) }
else if mark(2, true) { print(200) }
else if mark(3, true) { print(300) }
if false { print(9) } else if false { print(8) }
print(7)
}''', b'10\n20\n30\n40\n1\n2\n200\n7\n')

    def test_else_if_crlf_comments_and_branch_scopes(self):
        source='''fn main() {
let n = 8
if false { let n = 1
print(n) }
else /* separator */ if true { let n = 2
print(n) }
else
if true { print(3) }
else { print(4) }
print(n)
}'''
        self.assert_runs(source.replace('\n', '\r\n'), b'2\n8\n')

    def test_long_else_if_chain_uses_bounded_block_depth(self):
        chain='if false { print(0) }' + ''.join('\nelse if false { print(0) }' for _ in range(180))
        self.assert_runs('fn main() {\n'+chain+'\nelse { print(42) }\n}', b'42\n')

    def test_else_if_missing_return_is_rejected(self):
        for chain in [
            'if n == 0 { return 1 } else if n == 1 { return 2 }',
            'if n == 0 { print(1) } else if n == 1 { return 2 } else { return 3 }',
            'if n == 0 { return 1 } else if n == 1 { print(2) } else { return 3 }',
        ]:
            result=self.build('fn pick(n: int64) -> int64 { '+chain+'\n}\nfn main() {}')
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertIn(b'without returning',result.stderr)
            self.assertFalse(self.output.exists())

    def test_range_bounds_run_once_left_to_right_before_binding(self):
        self.assert_runs('''fn bound(log: [int64], value: int64) -> int64 {
log[0] += 1
print(value)
return value
}
fn main() {
let log = array(int64, 1, 0)
let i = 2
for i in bound(log, i)..bound(log, i + 3) { print(i) }
print(log[0])
print(i)
for j in bound(log, 9)..bound(log, 1) { print(99) }
print(log[0])
}''', b'2\n5\n2\n3\n4\n2\n2\n9\n1\n4\n')

    def test_range_empty_negative_and_int64_edges(self):
        self.assert_runs('''fn main() {
for i in 0..0 { print(9) }
for i in 5..2 { print(9) }
for i in -3..0 { print(i) }
for i in 9223372036854775806..9223372036854775807 { print(i) }
for i in -9223372036854775808..-9223372036854775807 { print(i) }
for i in 9223372036854775807..9223372036854775807 { print(9) }
}''', b'-3\n-2\n-1\n9223372036854775806\n-9223372036854775808\n')

    def test_range_nested_while_break_continue_and_scope(self):
        self.assert_runs('''fn main() {
var sum = 0
for i in 0..4 {
if i == 1 { continue }
for j in 0..4 {
if j == 2 { break }
var k = 0
while k < 3 { k += 1
if k == 1 { continue }
sum += 1
break }
sum += i + j
}
}
print(sum)
var k = 0
while k < 2 { k += 1
for i in 0..3 { if i == 1 { continue }
print(i) }
}
}''', b'19\n0\n2\n0\n2\n')

    def test_range_rejects_types_mutation_and_leaked_scope(self):
        for statement in [
            'for i in true..3 {}', 'for i in 0..false {}',
            'for i in s"a"..s"b" {}', 'for i in 0..3 { i = 2 }',
            'for i in 0..3 { i += 1 }', 'for i in 0..3 {}\nprint(i)',
            'for i in 0..3 { let i = 4 }', 'for i 0..3 {}',
            'for i in 0...3 {}', 'for i in 0.. {}', 'for in in 0..3 {}',
        ]:
            with self.subTest(statement=statement):
                result=self.build('fn main() { '+statement+'\n}')
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertFalse(self.output.exists())

    def test_range_seeded_results_match_python(self):
        rng=random.Random(14001)
        code=[];expected=[]
        for case in range(24):
            start,end=rng.randrange(-15,16),rng.randrange(-15,16)
            code += [f'var s{case} = 0',f'for i in {start}..{end} {{ if i % 3 == 0 {{ continue }}', f's{case} += i\n}}',f'print(s{case})']
            expected.append(sum(i for i in range(start,end) if i % 3 != 0))
        self.assert_runs('fn main() {\n'+'\n'.join(code)+'\n}', ''.join(f'{n}\n' for n in expected).encode())

    def test_compound_destinations_and_old_value_evaluate_once(self):
        self.assert_runs('''struct Box { value: int64, name: string, rows: [[int64]] }
fn index(log: [int64]) -> int64 { log[0] += 1
return 0 }
fn change(box: Box) -> int64 { box.value = 100
return 2 }
fn main() {
var n = 4
n += 3 * 2
n -= 1 + 2
print(n)
let log = array(int64, 1, 0)
let row = array(int64, 1, 5)
let box = Box(7, s"a", array([int64], 1, row))
box.rows[index(log)][index(log)] += 3
print(log[0])
print(row[0])
box.value += change(box)
print(box.value)
box.name += s"b"
print(box.name)
var text = s"x"
text += s"y" + s"z"
print(text)
}''', b'7\n2\n8\n9\nab\nxyz\n')

    def test_compound_alias_replacement_keeps_original_destination(self):
        self.assert_runs('''struct Box { values: [int64] }
fn replace(box: Box) -> int64 {
box.values = array(int64, 1, 90)
collect()
return 4
}
fn main() {
let original = array(int64, 1, 3)
let box = Box(original)
box.values[0] += replace(box)
print(original[0])
print(box.values[0])
}''', b'7\n90\n')

    def test_compound_string_keeps_roots_across_collection(self):
        self.assert_runs('''struct Box { name: string }
fn more(box: Box) -> string {
box.name = s"changed"
for i in 0..40 { buffer(1048576) }
collect()
return s"b"
}
fn main() {
let box = Box(s"a")
box.name += more(box)
print(box.name)
}''', b'ab\n')

    def test_compound_overflow_and_bounds_fail_before_rhs(self):
        for source,output,message in [
            ('var n = 9223372036854775807\nn += 1', b'', b'arithmetic'),
            ('var n = -9223372036854775808\nn -= 1', b'', b'arithmetic'),
            ('let a = array(int64, 1, 9223372036854775807)\na[0] += 1', b'', b'arithmetic'),
            ('let a = array(int64, 1, 1)\na[1] += rhs()', b'', b'Ramos runtime error'),
        ]:
            with self.subTest(source=source):
                result=self.build('fn rhs() -> int64 { print(99)\nreturn 1 }\nfn main() { '+source+'\n}', '--force')
                self.assertEqual(result.returncode,0,result.stderr)
                result=self.run_native()
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertEqual(result.stdout,output)
                self.assertIn(message,result.stderr)

    def test_compound_type_errors_preserve_existing_output(self):
        result=self.build('fn main() { print(42) }')
        self.assertEqual(result.returncode,0,result.stderr)
        original=self.output.read_bytes()
        for statement in [
            'let n = 1\nn += 2', 'var n = 1\nn += true',
            'var n = true\nn += false', 'var n = s"a"\nn -= s"b"',
            'var n = "a"\nn += "b"', 'var n = array(int64, 1, 1)\nn += n',
            'var n = 1\nn +=', 'var n = 1\nprint(n += 1)',
        ]:
            with self.subTest(statement=statement):
                result=self.build('fn main() { '+statement+'\n}', '--force')
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertEqual(self.output.read_bytes(),original)

    def test_range_hidden_slots_obey_declaration_budget(self):
        source = 'fn main() {\n' + 'for i in 0..0 {}\n' * 2048 + '}\n'
        self.assert_runs(source, b'')
        original = self.output.read_bytes()
        overflow = 'fn main() {\n' + 'for i in 0..0 {}\n' * 2049 + '}\n'
        result = self.build(overflow, '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'limit', result.stderr)
        self.assertEqual(self.output.read_bytes(), original)
