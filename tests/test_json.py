"""Strict JSON and serialization, checked against Python's independent parser."""
import json
import random
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_libraries import BOOTSTRAP

RUNNER = '''weave "stdlib/json.ramos"
fn main() {
let raw = read_file(arg(1))
let doc = json_parse(raw)
print(doc.status)
print(doc.error_at)
if doc.status == 0 { let out = json_encode(doc)
print(out.status)
stdout(to_bytes(out.text)) }
}'''

@unittest.skipIf(BOOTSTRAP, 'retained seed has no typed JSON library')
class JsonTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native
    native_path = staticmethod(str)

    def json_build(self, source=RUNNER):
        self.standard_library()
        r = self.build(source, '--force')
        self.assertEqual(r.returncode, 0, r.stderr)

    def json_run(self, data):
        path = self.directory / 'input.json'
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        r = self.run_native(self.native_path(path))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, b'')
        status, offset, rest = r.stdout.split(b'\n', 2)
        return int(status), int(offset), rest

    def test_json_nested_scalars_unicode_and_exact_numbers(self):
        self.json_build()
        cases = ['null', 'false', 'true', '0', '-0', '1e400', '-123456789012345678901234567890',
                 ' [ 1.25e-3, true, null, {"text":"مرحبا 🌍","empty":[]} ] ',
                 r'{"\u0061":"\u0000\b\f\n\r\t\"\\\/","emoji":"\ud83c\udf0d"}',
                 '{"a":1,"a":2}', '"\U0010ffff"']
        for source in cases:
            with self.subTest(source=source):
                status, offset, rest = self.json_run(source)
                self.assertEqual((status, offset), (0, -1))
                encode_status, encoded = rest.split(b'\n', 1)
                self.assertEqual(encode_status, b'0')
                # Decimal spelling, including values outside binary64, is exact.
                self.assertEqual(json.loads(encoded, parse_int=str, parse_float=str),
                                 json.loads(source, parse_int=str, parse_float=str))

    def test_json_rejects_malformed_and_invalid_utf8_without_trapping(self):
        self.json_build()
        cases = [b'', b' ', b'01', b'+1', b'.5', b'1.', b'1e+', b'NaN', b'Infinity',
                 b'true false', b'[1,]', b'{"a":1,}', b'{a:1}', b'{"a" 1}',
                 b'[}', b'[1 2]', b'"\n"', b'"\\x"', b'"unterminated',
                 b'"\\uD800"', b'"\\uDC00"', b'"\\uD800\\u0041"', b'"\\u00q0"',
                 b'\xef\xbb\xbfnull', b'"\xff"', b'"\xc0\x80"', b'"\xed\xa0\x80"',
                 b'"\xf4\x90\x80\x80"', b'"\xe2\x82', b'null\0']
        for source in cases:
            with self.subTest(source=source):
                status, offset, rest = self.json_run(source)
                self.assertEqual(status, -22)
                self.assertGreaterEqual(offset, 0)
                self.assertLessEqual(offset, len(source))
                self.assertEqual(rest, b'')

    def test_json_lookup_snapshot_missing_duplicate_and_quote(self):
        self.json_build(r'''weave "stdlib/json.ramos"
fn main() {
let raw = "{\"a\":1,\"a\":2,\"items\":[\"مرحبا 🌍\",null]}"
let doc = json_parse(raw)
buffer_set(raw, 0, 32)
print(json_raw(doc, json_get(doc, doc.root, s"a")))
let items = json_get(doc, doc.root, s"items")
print(json_size(doc, items))
print(json_text(doc, json_at(doc, items, 0)))
print(json_kind(doc, json_at(doc, items, 1)))
print(json_at(doc, items, -1))
print(json_at(doc, items, 2))
print(json_get(doc, doc.root, s"missing"))
print(json_kind(doc, -1))
print(json_quote(s"\0\n\t\"\\ مرحبا").text)
}''')
        r = self.run_native()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '2\n2\nمرحبا 🌍\n1\n-1\n-1\n-1\n0\n"\\u0000\\u000a\\u0009\\\"\\\\ مرحبا"\n'.encode())

    def test_json_limits_depth_nodes_and_string_capacity(self):
        self.json_build()
        for source in ['[' * 64 + '0' + ']' * 64, '[' + ','.join(['0'] * 4095) + ']',
                       '"' + 'x' * 1048574 + '"']:
            status, offset, rest = self.json_run(source)
            self.assertEqual((status, offset), (0, -1))
            self.assertEqual(rest[:2], b'0\n')
        for source in ['[' * 65 + '0' + ']' * 65, '[' + ','.join(['0'] * 4096) + ']']:
            self.assertEqual(self.json_run(source)[0], -27)
        # JSON escape expansion is bounded before allocation.
        r = self.build('weave "stdlib/json.ramos"\nfn main() { print(json_quote(text_repeat(s"\\0", 174763)).status) }', '--force')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_native()
        self.assertEqual((r.returncode, r.stdout), (0, b'-27\n'), r.stderr)

    def test_json_random_reference_round_trips_and_repeated_collection(self):
        self.json_build()
        rng = random.Random(26)
        def value(depth=0):
            leaves = [None, True, False, rng.randrange(-10**30, 10**30),
                      rng.choice(['', 'a\0b', '\"\\\n', 'مرحبا 🌍', '\u007f'])]
            if depth > 3 or rng.randrange(3) == 0:
                return rng.choice(leaves)
            if rng.randrange(2):
                return [value(depth + 1) for _ in range(rng.randrange(5))]
            return {str(i): value(depth + 1) for i in range(rng.randrange(5))}
        for _ in range(70):
            expected = value()
            status, offset, rest = self.json_run(json.dumps(expected, ensure_ascii=rng.choice([True, False])))
            self.assertEqual((status, offset), (0, -1))
            self.assertEqual(json.loads(rest.split(b'\n', 1)[1]), expected)
        r = self.build('''weave "stdlib/json.ramos"
fn main() {
for i in 0..300 {
let doc = json_parse("{\\\"text\\\":\\\"مرحبا 🌍\\\",\\\"list\\\":[1,2,3]}")
if doc.status != 0 || json_encode(doc).status != 0 { exit(1) }
}
collect()
print(memory_used())
}''', '--force')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_native()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(int(r.stdout), 1048576)
