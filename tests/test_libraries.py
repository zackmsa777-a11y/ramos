"""Native multi-source loading and the Ramos-written standard library."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ramos as support

BOOTSTRAP = False
if os.name != 'nt' and not os.environ.get('RAMOS_WINDOWS_COMPILER'):
    BOOTSTRAP = b'native assembly bootstrap' in subprocess.check_output([str(support.COMPILER), '--version'])


@unittest.skipIf(BOOTSTRAP, 'the retained assembly seed has no weave grammar')
class LibraryTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def library(self, name, source):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode() if isinstance(source, str) else source)
        return path

    def standard_library(self):
        shutil.copytree(support.ROOT / 'stdlib', self.directory / 'stdlib')

    native_path = staticmethod(str)

    def run_native(self, *args):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=10)

    def test_nested_relative_paths_forward_types_and_calls(self):
        self.library('lib/models.ramos', 'weave "helpers/math.ramos"\nstruct Point { x: int64 }\nfn total(p: Point) -> int64 { return double(p.x) }')
        self.library('lib/helpers/math.ramos', 'fn double(n: int64) -> int64 { return n * 2 }')
        self.assert_runs('weave "lib/models.ramos"\nfn main() { print(total(Point(21))) }', b'42\n')

    def test_shared_diamond_and_normalized_paths_load_once(self):
        self.library('a.ramos', 'weave "common.ramos"\nfn a() -> int64 { return shared() }')
        self.library('b.ramos', 'weave "sub/../common.ramos"\nfn b() -> int64 { return shared() }')
        self.library('common.ramos', 'fn shared() -> int64 { return 21 }')
        self.assert_runs('weave "a.ramos"\nweave "b.ramos"\nweave "./common.ramos"\nfn main() { print(a() + b()) }', b'42\n')

    def test_library_paths_with_spaces_unicode_and_crlf(self):
        self.library('لغات/my helper.ramos', 'fn answer() -> string {\r\nreturn s"مرحبا 🌍"\r\n}\r\n')
        self.assert_runs('weave "لغات/my helper.ramos"\r\nfn main() { print(answer()) }', 'مرحبا 🌍\n'.encode())

    def test_comment_and_literal_weave_are_not_directives(self):
        self.assert_runs('''// weave "missing.ramos"
/* weave "also-missing.ramos" */
fn main() {
print("weave \\\"literal.ramos\\\"")
print(s"weave")
}''', b'weave "literal.ramos"\nweave\n')

    def test_library_lexer_parser_and_type_errors_show_own_file(self):
        for code, location, message in [
            ('fn value() -> int64 {\n  return true\n}', b':2:14:', b'expected int64'),
            ('fn value() {\n  print(missing)\n}', b':2:9:', b'unknown variable'),
            (b'fn value() {}\n// \xff', b':2:4:', b'invalid UTF-8'),
            ('fn value() {\n/* unclosed', b':2:1:', b'unterminated block comment'),
        ]:
            with self.subTest(code=code):
                bad = self.library('bad.ramos', code)
                result = self.build('weave "bad.ramos"\nfn main() {}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(bad.name.encode() + location, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.output.exists())

    def test_first_token_error_uses_library_not_previous_file_eof(self):
        self.library('bad.ramos', 'oops\n')
        result = self.build('weave "bad.ramos"\nfn main() {}\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'bad.ramos:1:1:', result.stderr)

    def test_missing_library_reports_the_weave_site(self):
        self.library('lib/parent.ramos', '// line one\nweave "missing.ramos"\n')
        result = self.build('weave "lib/parent.ramos"\nfn main() {}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'parent.ramos:2:1:', result.stderr)
        self.assertIn(b'cannot read weave source:', result.stderr)
        self.assertIn(b'missing.ramos', result.stderr)

    def test_direct_indirect_and_shared_dependency_cycles_fail(self):
        for a, b in [('weave "a.ramos"', ''), ('weave "b.ramos"', 'weave "a.ramos"')]:
            with self.subTest(a=a, b=b):
                self.library('a.ramos', a)
                self.library('b.ramos', b)
                result = self.build('weave "a.ramos"\nweave "b.ramos"\nfn main() {}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'weave dependency cycle', result.stderr)
        result = self.build(f'weave "{self.source.name}"\nfn main() {{}}', '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'weave dependency cycle', result.stderr)

    def test_duplicate_names_main_and_local_directives_rejected(self):
        self.library('a.ramos', 'fn duplicate() {}')
        self.library('b.ramos', 'fn duplicate() {}')
        for source, message in [
            ('weave "a.ramos"\nweave "b.ramos"\nfn main() {}', b'duplicate function'),
            ('fn main() {\nweave "a.ramos"\n}', b'only allowed at top level'),
        ]:
            result = self.build(source, '--force')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(message, result.stderr)
        self.library('a.ramos', 'fn main() {}')
        result = self.build('weave "a.ramos"\nfn main() {}', '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'libraries cannot define main', result.stderr)

    def test_weave_path_and_statement_contracts(self):
        self.library('ok.ramos', 'fn helper() {}')
        for directive in ['weave', 'weave s"ok.ramos"', 'weave 1', 'weave ""',
                          'weave "/absolute.ramos"', 'weave "C:/absolute.ramos"',
                          'weave "bad\\0name"', 'weave "bad\\nname"',
                          'weave "dir\\\\file.ramos"', 'weave "ok.ramos" print(1)',
                          'weave "' + ('x' * 4096) + '"']:
            with self.subTest(directive=directive):
                result = self.build(directive + '\nfn main() {}', '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error:', result.stderr)
                self.assertNotIn(b'Ramos runtime error:', result.stderr)

    def test_source_count_and_deep_chain_are_bounded(self):
        for i in range(63):
            next_file = f'weave "m{i+1}.ramos"\n' if i < 62 else 'fn answer() -> int64 { return 42 }\n'
            self.library(f'm{i}.ramos', next_file)
        self.assert_runs('weave "m0.ramos"\nfn main() { print(answer()) }', b'42\n')
        self.library('m62.ramos', 'weave "m63.ramos"\n')
        self.library('m63.ramos', 'fn answer() -> int64 { return 42 }')
        result = self.build('weave "m0.ramos"\nfn main() {}', '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'at most 64 source files', result.stderr)

    def test_aggregate_source_and_token_budgets_are_checked(self):
        self.library('large.ramos', '// ' + ('x' * 600000))
        result = self.build('weave "large.ramos"\nfn main() {}\n// ' + ('y' * 500000))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'weave source total exceeds', result.stderr)
        self.library('tokens.ramos', 'fn a() {\n' + ('print(1)\n' * 5000) + '}')
        result = self.build('weave "tokens.ramos"\nfn main() {\n' + ('print(1)\n' * 5000) + '}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'token limit', result.stderr)
        long_parent = '/'.join(['a' * 242] * 16)
        directives = '\n'.join(f'weave "{long_parent}/file{i}.ramos"' for i in range(11))
        result = self.build(directives + '\nfn main() {}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'source paths exceed 41900 bytes', result.stderr)


    def test_every_source_and_hardlink_is_protected_with_force(self):
        a = self.library('a.ramos', 'fn a() -> int64 { return 1 }')
        b = self.library('b.ramos', 'fn b() -> int64 { return 2 }')
        original_output = self.output
        source = 'weave "a.ramos"\nweave "b.ramos"\nfn main() { print(a() + b()) }'
        for target in [self.source, a, b]:
            with self.subTest(target=target):
                self.output = target
                result = self.build(source, '--force')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'cannot publish output', result.stderr)
                self.assertEqual(a.read_text(), 'fn a() -> int64 { return 1 }')
                self.assertEqual(b.read_text(), 'fn b() -> int64 { return 2 }')
                self.assertEqual(self.source.read_text(), source)
        alias = self.directory / 'alias.ramos'
        os.link(a, alias)
        self.output = alias
        result = self.build(source, '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(alias.read_text(), a.read_text())
        self.output = original_output

    def test_registered_source_identities_survive_heap_collection(self):
        a = self.library('guard-a.txt', 'first')
        b = self.library('guard-b.txt', 'second')
        result = self.build('''fn main() {
read_file(arg(1))
print(_protect_input())
read_file(arg(2))
print(_protect_input())
var i = 0
while i < 100 { buffer(1048576)
i = i + 1 }
collect()
print(write_file(arg(3), "replacement", 3))
}''')
        self.assertEqual(result.returncode, 0, result.stderr)
        for destination in (a, b):
            result = self.run_native(self.native_path(a), self.native_path(b), self.native_path(destination))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b'0\n0\n-22\n')
        self.assertEqual(a.read_text(), 'first')
        self.assertEqual(b.read_text(), 'second')

    def test_failed_library_build_preserves_existing_output(self):
        self.assert_runs('fn main() { print(7) }', b'7\n')
        original = self.output.read_bytes()
        self.library('bad.ramos', 'fn broken() -> int64 { return false }')
        result = self.build('weave "bad.ramos"\nfn main() {}', '--force')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_number_text_and_binary_libraries(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/numbers.ramos"
weave "stdlib/text.ramos"
weave "stdlib/bytes.ramos"
fn main() {
print(num_min(-3, 8))
print(num_max(-3, 8))
print(num_abs(-9))
print(num_clamp(42, 0, 10))
print(num_text(-9223372036854775808))
print(num_parse(s"+42"))
print(parse_error())
print(num_parse(s"bad"))
print(parse_error())
print(text_starts(s"مرحبا 🌍", s"مر"))
print(text_ends(s"مرحبا 🌍", s"🌍"))
print(text_find(s"مرحبا 🌍", s"🌍"))
print(text_find(s"abc", s"x"))
print(text_find(s"abc", s""))
print(text_contains(s"abc", s"ab"))
print(text_repeat(s"é", 3))
let parts = array(string, 3, s"x")
parts[1] = s"é"
print(text_join(parts, s","))
let raw = "A\\0B"
let copy = bytes_copy(raw)
buffer_set(copy, 0, 90)
print(bytes_equal(raw, copy))
print(bytes_slice(raw, 1, 3))
}''', b'-3\n8\n9\n10\n-9223372036854775808\n42\n0\n0\n-22\ntrue\ntrue\n6\n-1\n0\ntrue\n' + 'ééé\nx,é,x\n'.encode() + b'false\n\0B\n')

    def test_growable_lists_maps_and_aliases(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/lists.ramos"
weave "stdlib/maps.ramos"
weave "stdlib/numbers.ramos"
fn main() {
let list = list_new()
let alias = list
var i = 0
while i < 1000 { list_push(list, i)
i = i + 1 }
print(list_len(alias))
print(list_get(alias, 999))
list_set(alias, 0, 42)
print(list_get(list, 0))
print(list_pop(list))
print(list_len(list))
list_clear(list)
print(list_len(list))
list_push(list, 7)
print(list_get(alias, 0))
let map = map_new()
i = 0
while i < 200 { map_set(map, num_text(i), s"value " + num_text(i))
i = i + 1 }
let other = map
map_set(other, s"42", s"updated")
print(map_len(map))
print(map_get(map, s"42", s"missing"))
print(map_remove(map, s"42"))
print(map_len(map))
print(map_has(other, s"42"))
print(map_get(map, s"42", s"fallback"))
print(map_get(map, s"199", s"missing"))
print(map_remove(map, s"absent"))
collect()
print(map_get(map, s"0", s"missing"))
}''', b'1000\n999\n42\n999\n999\n0\n7\n200\nupdated\ntrue\n199\nfalse\nfallback\nvalue 199\nfalse\nvalue 0\n')

    def test_text_builders_empty_unicode_and_payload_limits(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/text.ramos"
fn main() {
print(len(text_join(array_empty(string), s",")))
print(text_join(array(string, 1, s"é"), s","))
print(len(text_repeat(s"x", 0)))
print(len(text_repeat(s"", 9223372036854775807)))
print(len(text_repeat(s"é", 524288)))
print(len(text_join(array(string, 10000, s"é"), s",")))
}''', b'0\n' + 'é\n'.encode() + b'0\n0\n524288\n19999\n')
        for expression in ['text_repeat(s"x", 1048577)',
                           'text_join(array(string, 2, string(buffer(600000))), s"")']:
            result = self.build('weave "stdlib/text.ramos"\nfn main() { print(' + expression + ') }', '--force')
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_native()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'buffer size', result.stderr)

    def test_map_remove_releases_values_during_long_running_reuse(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/maps.ramos"
weave "stdlib/numbers.ramos"
fn main() {
let map = map_new()
var i = 0
while i < 10000 {
let key = num_text(i)
map_set(map, key, string(buffer(4096)))
if !map_remove(map, key) { exit(2) }
i = i + 1
}
collect()
print(map_len(map))
print(memory_used() < 65536)
}''', b'0\ntrue\n')

    def test_standard_library_failures_are_checked(self):
        self.standard_library()
        for expression, message in [
            ('list_get(list_new(), 0)', b'list index'),
            ('list_pop(list_new())', b'empty list'),
            ('num_clamp(1, 2, 0)', b'reversed clamp'),
            ('num_abs(-9223372036854775808)', b'arithmetic overflow'),
            ('text_repeat(s"x", -1)', b'negative repeat'),
            ('bytes_slice("x", 0, 2)', b'byte slice'),
        ]:
            with self.subTest(expression=expression):
                source = '\n'.join(f'weave "stdlib/{name}.ramos"' for name in ['lists', 'numbers', 'text', 'bytes'])
                result = self.build(source + '\nfn main() {\nprint(' + expression + ')\n}', '--force')
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.run_native()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
