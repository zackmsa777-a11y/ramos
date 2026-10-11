"""Reusable UTF-8 assembly, immutable snapshots and a streamed acceptance tool."""
import subprocess
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_libraries import BOOTSTRAP


@unittest.skipIf(BOOTSTRAP, 'retained seed has no weave or struct grammar')
class TextBuilderTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    example = streams.StreamTests.example
    native_path = staticmethod(str)

    def run_native(self, *args):
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=20)

    def test_utf8_empty_nul_aliases_and_immutable_snapshots(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/text.ramos"
fn main() {
let b = text_builder()
let alias = b
print(text_builder_finish(b))
print(text_builder_append(b, s""))
print(text_builder_append(b, s"é🚀"))
print(text_builder_bytes(alias))
let first = text_builder_finish(b)
print(text_builder_append(alias, s"\\0Z"))
print(first)
print(text_builder_finish(b))
text_builder_clear(b)
print(text_builder_bytes(alias))
print(text_builder_append(alias, s"again"))
text_builder_release(b)
print(buffer_len(b.data))
collect()
print(first)
print(text_builder_append(alias, s"reused"))
print(text_builder_finish(b))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, '\n0\n0\n6\n0\né🚀\né🚀\0Z\n0\n0\n0\né🚀\n0\nreused\n'.encode()), result.stderr)

    def test_doubling_growth_exact_limit_and_atomic_rejection(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/text.ramos"
fn main() {
let b = text_builder()
let chunk = text_repeat(s"é", 2048)
for i in 0..256 {
if text_builder_append(b, chunk) != 0 { exit(9) }
}
print(text_builder_bytes(b))
print(buffer_len(b.data))
print(len(text_builder_finish(b)))
print(text_builder_append(b, s"x"))
print(text_builder_bytes(b))
print(text_builder_append(b, s""))
text_builder_clear(b)
print(buffer_len(b.data))
print(text_builder_append(b, s"ok"))
print(text_builder_finish(b))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'1048576\n1048576\n524288\n-27\n1048576\n0\n1048576\n0\nok\n'), result.stderr)

    def test_many_reused_results_collect_without_heap_exhaustion(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/text.ramos"
fn main() {
let b = text_builder()
let part = text_repeat(s"ab", 2048)
for i in 0..6000 {
text_builder_clear(b)
if text_builder_append(b, part) != 0 { exit(8) }
let result = text_builder_finish(b)
if len(result) != 4096 || result != part { exit(9) }
}
text_builder_release(b)
collect()
print(text_builder_bytes(b))
print(buffer_len(b.data))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode, result.stdout), (0, b'0\n0\n'), result.stderr)

    def test_invalid_public_state_traps_before_access(self):
        self.standard_library()
        for statement in ['b.count = -1', 'b.count = 65']:
            with self.subTest(statement=statement):
                self.build_ok('weave "stdlib/text.ramos"\nfn main() { let b = text_builder()\n' + statement + '\ntext_builder_append(b, s"x") }')
                result = self.run_native()
                self.assertEqual(result.returncode, 1)
                self.assertIn(b'invalid text builder state', result.stderr)

    def test_numbered_stream_unicode_crlf_empty_final_and_large_file(self):
        self.example('rnumber')
        path = self.directory / 'input é.txt'
        lines = ['é🚀', '', 'last']
        path.write_bytes('\r\n'.join(lines).encode())
        result = self.run_native(self.native_path(path))
        self.assertEqual((result.returncode, result.stdout), (0, '1: é🚀\n2: \n3: last\n'.encode()), result.stderr)
        path.write_bytes(b'')
        self.assertEqual(self.run_native(self.native_path(path)).stdout, b'')
        line = b'x' * 4096
        path.write_bytes((line + b'\n') * 400)
        result = self.run_native(self.native_path(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b''.join(str(i).encode() + b': ' + line + b'\n' for i in range(1, 401)))

    def test_numbered_stream_missing_and_size_failures(self):
        self.example('rnumber')
        missing = self.directory / 'missing'
        result = self.run_native(self.native_path(missing))
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'input failed', result.stderr)
        path = self.directory / 'large.txt'
        path.write_bytes(b'x' * 1048576 + b'\n')
        result = self.run_native(self.native_path(path))
        self.assertEqual((result.returncode, result.stdout), (2, b''))
        self.assertIn(b'numbered line exceeds', result.stderr)
        path.write_bytes(b'x' * 1048577 + b'\n')
        result = self.run_native(self.native_path(path))
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'I/O status -27', result.stderr)
