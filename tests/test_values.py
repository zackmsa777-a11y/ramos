"""Strings, typed aggregates and heap lifetime contracts on both native targets."""
import os
import random
import subprocess
import unittest
import test_ramos as support

BOOTSTRAP = False
if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
    BOOTSTRAP = b'native assembly bootstrap' in subprocess.check_output([str(support.COMPILER), '--version'])


@unittest.skipIf(BOOTSTRAP, 'the retained seed implements the pre-0.8 grammar')
class ValueTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_native(self, **kwargs):
        return subprocess.run([str(self.output)], capture_output=True, timeout=15, **kwargs)

    def assert_traps(self, source, message):
        result = self.build(source, '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_native()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)

    def test_unicode_strings_scalars_slicing_and_nul(self):
        self.assert_runs('''fn main() {
let text = s"Aéمرحبا🌍\\0é"
print(len(text))
print(slice(text, 1, 2))
print(slice(text, 2, 7))
print(slice(text, 7, 9))
print(slice(text, 9, 11))
print(slice(text, 11, 11))
print(len(s""))
print(buffer_len(to_bytes(text)))
}''', '11\né\nمرحبا\n🌍\0\né\n\n0\n21\n'.encode())

    def test_strings_immutable_copies_and_bytes_compatibility(self):
        self.assert_runs('''fn main() {
let binary = "abc\\0"
let text = string(binary)
buffer_set(binary, 0, 90)
let copy = to_bytes(text)
buffer_set(copy, 1, 88)
print(text)
print(binary)
print(copy)
print(s"abc\\0" == text)
}''', b'abc\0\nZbc\0\naXc\0\ntrue\n')

    def test_string_operators_calls_returns_and_precedence(self):
        self.assert_runs('''fn join(a: string, b: string) -> string { return a + b }
fn main() {
var text = s"a"
text = join(text, s"b") + s"c"
print(text)
print(text == s"abc")
print(text != s"ABC")
print(s"" + s"" == s"")
print(s"a" == s"aa")
print(s"aa" != s"a")
print(s"aa" == s"ab")
print(false || text == s"abc" && !(text != s"abc"))
}''', b'abc\ntrue\ntrue\ntrue\nfalse\ntrue\nfalse\ntrue\n')

    def test_unicode_slices_match_independent_reference(self):
        randomizer = random.Random(1010)
        alphabet = ['a', 'é', 'م', '🌍', '́', '\x00', '\n', '"', '\\']
        def literal(value):
            return 's"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\x00', '\\0').replace('\n', '\\n') + '"'
        lines, output = [], bytearray()
        for _ in range(50):
            text = ''.join(randomizer.choice(alphabet) for _ in range(randomizer.randrange(20)))
            begin = randomizer.randrange(len(text) + 1)
            end = randomizer.randrange(begin, len(text) + 1)
            lines += [f'print(len({literal(text)}))', f'print(slice({literal(text)}, {begin}, {end}))']
            output += str(len(text)).encode() + b'\n' + text[begin:end].encode() + b'\n'
        self.assert_runs('fn main() {\n' + '\n'.join(lines) + '\n}', bytes(output))

    def test_string_encoding_rejects_invalid_utf8(self):
        malformed = [b'\x80', b'\xc0\x80', b'\xc1\xbf', b'\xc2', b'\xc2A',
                     b'\xe0\x9f\xbf', b'\xed\xa0\x80', b'\xef\xbf',
                     b'\xf0\x8f\xbf\xbf', b'\xf4\x90\x80\x80',
                     b'\xf5\x80\x80\x80', b'\xff']
        for data in malformed:
            with self.subTest(data=data):
                writes = '\n'.join(f'buffer_set(b, {i}, {v})' for i, v in enumerate(data))
                self.assert_traps(f'fn main() {{\nlet b = buffer({len(data)})\n{writes}\nprint(string(b))\n}}', b'invalid UTF-8 string')

    def test_string_encoding_valid_boundaries(self):
        data = '\x00\x7f\x80\u07ff\u0800\ud7ff\ue000\uffff\U00010000\U0010ffff'
        # Source allows escaped NUL; all other scalars can be literal UTF-8.
        self.assert_runs('fn main() {\nlet text = s"\\0' + data[1:] + '"\nprint(len(text))\nprint(string(to_bytes(text)) == text)\n}', b'10\ntrue\n')

    def test_string_slice_bounds_checked(self):
        for begin, end in [(-1, 0), (0, -1), (2, 1), (0, 4), (4, 4), (9223372036854775807, 9223372036854775807)]:
            with self.subTest(begin=begin, end=end):
                self.assert_traps(f'fn main() {{ print(slice(s"aé🌍", {begin}, {end})) }}', b'string slice out of bounds')

    def test_string_size_limit_checked(self):
        self.assert_runs('''fn main() {
let text = string(buffer(1048576))
print(len(text))
print(len(slice(text, 1048575, 1048576)))
print(len(text + s""))
}''', b'1048576\n1\n1048576\n')
        self.assert_traps('fn main() { print(string(buffer(1048576)) + s"x") }', b'buffer size')

    def test_struct_forward_types_and_constructor_arguments(self):
        self.assert_runs('''fn total(p: Point) -> int64 { return p.x + p.y }
struct Player { name: string, position: Point }
struct Point { x: int64, y: int64 }
fn mark(n: int64) -> int64 { print(n)
return n }
fn main() {
let player = Player(s"Ramos", Point(mark(3), mark(4)))
print(player.name)
print(total(player.position))
print(-Point(1, 2).x)
}''', b'3\n4\nRamos\n7\n-1\n')

    def test_struct_alias_field_assignment_and_returns(self):
        self.assert_runs('''struct Point { x: int64, y: int64 }
struct Player { name: string, position: Point }
fn make() -> Player { return Player(s"old", Point(1, 2)) }
fn main() {
let p = make()
let alias = p
alias.position.x = 42
p.name = p.name + s" name"
print(p.position.x)
print(alias.name)
print(make().position.x)
}''', b'42\nold name\n1\n')

    def test_struct_empty_multiline_and_maximum_fields(self):
        fields = ', '.join(f'x{i}: int64' for i in range(16))
        values = ', '.join(str(i) for i in range(16))
        self.assert_runs('struct\nEmpty\n{ }\nstruct Big {' + fields + '}\nfn main() {\nlet e = Empty()\nlet b = Big(' + values + ')\nprint(b.x0 + b.x15)\ncollect()\nprint(memory_used() > 0)\n}', b'15\ntrue\n')

    def test_typed_arrays_get_set_index_and_resize(self):
        self.assert_runs('''fn make() -> [int64] { return array(int64, 3, 7) }
fn main() {
let a = make()
let alias = a
alias[
1
] = 42
array_set(a, 2, 5)
print(array_get(alias, 1))
print(a[0] + a[2])
let grown = array_resize(a, 5, 9)
grown[1] = 88
print(a[1])
print(grown[1] + grown[4])
print(array_len(array_resize(a, 1, 0)))
print(array_len(array_empty(string)))
print(array_len(array(int64, 0, 42)))
}''', b'42\n12\n42\n97\n1\n0\n0\n')

    def test_arrays_of_references_nested_indices_and_alias_fill(self):
        self.assert_runs('''struct Point { x: int64 }
struct Group { members: [Point], grid: [[int64]] }
fn main() {
let p = Point(3)
let members = array(Point, 2, p)
let row = array(int64, 4, 9)
let g = Group(members, array([int64], 2, row))
g.members[1].x = 42
g.grid[0][1 + 1] = 99
print(members[0].x)
print(row[2])
members[1] = Point(7)
print(members[0].x + members[1].x)
print(array_get(array(string, 1, s"yes"), 0))
print(array_get(array(bool, 1, true), 0))
print(buffer_get(array_get(array(bytes, 1, "A"), 0), 0))
}''', b'42\n99\n49\nyes\ntrue\n65\n')

    def test_array_size_and_bounds_checked(self):
        for expression in ['array(int64, -1, 0)', 'array(int64, 131073, 0)',
                           'array_resize(array_empty(int64), -1, 0)']:
            with self.subTest(expression=expression):
                self.assert_traps(f'fn main() {{ let a = {expression} }}', b'array size')
        for body in ['print(a[-1])', 'print(array_get(a, 1))', 'a[1] = 3',
                     'array_set(a, -1, 7)', 'print(array_empty(int64)[0])']:
            with self.subTest(body=body):
                self.assert_traps(f'fn main() {{\nlet a = array(int64, 1, 0)\n{body}\n}}', b'array index')
        self.output.unlink()
        self.assert_runs('''fn main() {
let a = array(int64, 131072, 9223372036854775807)
print(array_len(a))
print(a[131071])
}''', b'131072\n9223372036854775807\n')

    def test_value_static_type_errors(self):
        cases = ['string(1)', 'to_bytes("x")', 'len("x")', 'slice(s"x", true, 1)',
                 'print(s"a" + "b")', 'print(s"a" - s"b")', 'print(s"a" < s"b")',
                 'buffer_set(s"x", 0, 65)', 'var s = s"x"\ns = "y"',
                 'array(int64, 2, true)', 'array(void, 0, 0)', 'array_get(buffer(8), 0)',
                 'array_set(array(int64, 1, 0), 0, s"x")',
                 'array_resize(array(int64, 1, 0), 2, false)', 'array_empty(void)',
                 'print(array(int64, 1, 0)[false])', 'print(s"x"[0])',
                 'let p = Point(1)\np.x = false', 'let p = Point(1)\np = Point(2)',
                 'print(Point(1).missing)', 'Point()', 'Point(true)',
                 'let a = array(Point, 1, Point(0))\na[0] = 1',
                 'let n = 1\nn.x = 2', 'let a = array(int64, 1, 0)\na[0] = false']
        for body in cases:
            with self.subTest(body=body):
                result = self.build('struct Point { x: int64 }\nfn main() {\n' + body + '\n}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)

    def test_aggregate_delimiters_are_checked(self):
        for expression in ['a[]', 'a[1', 'a[(1]', 'a[1, 2]', 'a[1))', 'Point(1).',
                           'a[true]', 'array(int64)', 'array_empty()', 'array([void], 0, 0)']:
            with self.subTest(expression=expression):
                result = self.build('struct Point { x: int64 }\nfn main() {\nlet a = array(int64, 3, 0)\nprint(' + expression + ')\n}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)

    def test_struct_definition_and_type_limits(self):
        cases = ['struct P { x: void }', 'struct P { x: int64, x: bool }',
                 'struct P {}\nstruct P {}', 'struct buffer {}',
                 'struct P { x: Missing }', 'struct P {}\nfn P() {}',
                 'struct P {' + ', '.join(f'x{i}: int64' for i in range(17)) + '}',
                 '\n'.join(f'struct P{i} {{}}' for i in range(65)),
                 'fn f(a: ' + '[' * 17 + 'int64' + ']' * 17 + ') {}']
        for prefix in cases:
            with self.subTest(prefix=prefix):
                result = self.build(prefix + '\nfn main() {}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_unreachable_buffers_reused_automatically_and_zeroed(self):
        self.assert_runs('''fn main() {
let keep = buffer(65536)
buffer_set(keep, 0, 123)
var i = 0
while i < 256 {
let b = buffer(1048576)
if buffer_get(b, 0) != 0 { exit(2) }
if buffer_get(b, 1048575) != 0 { exit(3) }
buffer_set(b, 0, 255)
buffer_set(b, 1048575, 255)
i = i + 1
}
collect()
print(buffer_get(keep, 0))
print(memory_used() < 2200000)
}''', b'123\ntrue\n')

    def test_live_heap_limit_traps_instead_of_freeing_reachable_values(self):
        source = '''fn main() {
let live = array(bytes, 15, buffer(0))
var i = 0
while i < 15 {
live[i] = buffer(1048576)
i = i + 1
}
collect()
print(array_len(live))
buffer(1048576)
}'''
        self.assert_traps(source, b'buffer allocation')
        self.assertEqual(self.run_native().stdout, b'15\n')

    def test_live_aggregate_graph_and_cycles_survive_then_are_reclaimed(self):
        self.assert_runs('''struct Node { value: int64, links: [Node], text: string }
fn cycle() {
let a = Node(42, array_empty(Node), s"alive")
let b = Node(7, array(Node, 1, a), s"other")
a.links = array(Node, 1, b)
var i = 0
while i < 64 { buffer(1048576)
i = i + 1 }
collect()
print(a.links[0].links[0].value)
print(a.links[0].links[0].text)
}
fn main() {
var i = 0
while i < 100 { cycle()
i = i + 1 }
collect()
print(memory_used() < 1048576)
}''', (b'42\nalive\n' * 100) + b'true\n')

    def test_active_expression_and_argument_roots_across_collection(self):
        self.assert_runs('''struct Item { text: string }
fn churn() -> string {
var i = 0
while i < 32 { buffer(1048576)
i = i + 1 }
collect()
return s"right"
}
fn join(a: string, b: string) -> string { collect()
return a + b }
fn main() {
print(s"left " + churn())
print(join(s"left ", churn()))
let item = Item(s"old")
item.text = s"new " + churn()
print(item.text)
let a = array(string, 1, s"old")
a[0] = churn()
print(a[0])
}''', b'left right\nleft right\nnew right\nright\n')

    def test_scope_break_continue_and_return_release_roots(self):
        self.assert_runs('''fn temporary() -> int64 { let b = buffer(1048576)
return buffer_len(b) }
fn main() {
var i = 0
while i < 50 {
let b = buffer(1048576)
i = i + 1
if i < 49 { continue }
break
}
if true { let b = buffer(1048576) }
print(temporary())
collect()
print(memory_used() < 1048576)
}''', b'1048576\ntrue\n')

    def test_growable_string_and_array_loop_reuses_memory(self):
        self.assert_runs('''fn main() {
var text = s""
var values = array_empty(int64)
var i = 0
while i < 20000 {
text = text + s"x"
values = array_resize(values, array_len(values) + 1, i)
if len(text) == 1000 {
if values[999] != i { exit(3) }
text = s""
values = array_empty(int64)
}
i = i + 1
}
collect()
print(len(text))
print(array_len(values))
print(memory_used() < 1048576)
}''', b'0\n0\ntrue\n')
