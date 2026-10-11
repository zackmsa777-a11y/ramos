"""Ramos-written authoring tools: diagnostics, token-preserving format and native run."""
import os
from pathlib import Path
import subprocess
import unittest
import test_ramos as support
import test_cli_streams as streams
from test_libraries import BOOTSTRAP


@unittest.skipIf(BOOTSTRAP, 'retained seed has no development-tool CLI')
class DevToolsTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    native_path = staticmethod(str)
    compiler_executable = support.COMPILER
    compiler_prefix = []

    def compiler_command(self, *args, **kwargs):
        return subprocess.run([*self.compiler_prefix, str(self.compiler_executable), *args],
                              cwd=support.ROOT, capture_output=True, timeout=30, **kwargs)

    def write_source(self, source):
        self.source.write_bytes(source.encode() if isinstance(source, str) else source)
        return self.native_path(self.source)

    def format_file(self, source, *args):
        return self.compiler_command('fmt', self.write_source(source), *args)

    def test_diagnostic_source_line_caret_and_expected_type(self):
        result = self.build('fn main() {\n\tif 123 { print(1) }\n}\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'expected bool, found int64', result.stderr)
        self.assertIn(b'  |     if 123 { print(1) }\n', result.stderr)
        preview, caret = result.stderr.splitlines()[-2:]
        self.assertEqual(preview.index(b'{'), caret.index(b'^'))

    def test_diagnostic_library_location_eof_unicode_and_control_escape(self):
        library = self.directory / 'lib.ramos'
        library.write_text('fn broken() -> int64 {\n    return s"\u00e9"\n}\n', encoding='utf-8')
        result = self.build('weave "lib.ramos"\nfn main() {}\n')
        self.assertIn(b'lib.ramos:2:', result.stderr)
        self.assertIn(b'expected int64, found string', result.stderr)
        self.assertIn(b's"\\xc3\\xa9"', result.stderr)
        result = self.build(b'fn main() {\nprint(1)\n')
        self.assertIn(b':3:1:', result.stderr)
        self.assertTrue(result.stderr.endswith(b'  | \n  | ^\n'))
        result = self.build(b'fn main() {\n\x1b\n}')
        self.assertNotIn(b'\x1b', result.stderr)
        self.assertIn(b'\\x1b', result.stderr)

    def test_diagnostic_long_line_clipping_and_array_type_names(self):
        result = self.build('fn main() { ' + ' ' * 500 + 'if 1 {} }')
        self.assertIn(b'... ', result.stderr)
        self.assertLess(len(result.stderr.splitlines()[-2]), 400)
        result = self.build('fn use(a: [int64]) {}\nfn main() { use(array_empty(string)) }')
        self.assertIn(b'expected [int64], found [string]', result.stderr)
        result = self.build('struct A { x: int64 }\nstruct B { x: int64 }\nfn use(a: A) {}\nfn main() { use(B(1)) }')
        self.assertIn(b'expected A, found B', result.stderr)

    def test_format_canonical_output_idempotence_and_check(self):
        source = 'fn main( ) {\nvar x=1+2\nif x>0 {\n print(x) // retained  \n}\n}\n'
        expected = b'fn main() {\n    var x = 1 + 2\n    if x > 0 {\n        print(x) // retained  \n    }\n}\n'
        result = self.format_file(source)
        self.assertEqual((result.returncode, result.stdout), (0, expected), result.stderr)
        self.assertEqual(self.source.read_text(), source)
        self.assertEqual(self.compiler_command('fmt', self.native_path(self.source), '--check').returncode, 1)
        result = self.format_file(expected)
        self.assertEqual(result.stdout, expected)
        result = self.compiler_command('fmt', self.native_path(self.source), '--check')
        self.assertEqual((result.returncode, result.stdout), (0, b''))
        # Formatting unfinished code must not combine separate operator tokens.
        result = self.format_file('! =\n- >\n. ..\n. .\n')
        self.assertEqual(result.stdout, b'! =\n- >\n. ..\n. .\n')

    def test_format_comments_literals_and_semantic_binary_equivalence(self):
        source = '''// literal /* comment */ text
struct Point {x:int64}
fn main() {
let text=s"é\\n\\\" // /* still text"
var p=Point(1)
/* preserve these bytes
   including braces } and spaces  */
p.x += -2
let values=array(int64,2,-1)
values[0]=p.x
if !false && values[0]<0 {print(text)}
for i in 0..2 {print(values[i])}
}
'''
        self.build_ok(source)
        before = self.output.read_bytes()
        formatted = self.compiler_command('fmt', self.native_path(self.source))
        self.assertEqual(formatted.returncode, 0, formatted.stderr)
        self.assertIn(b'/* preserve these bytes\n   including braces } and spaces  */', formatted.stdout)
        self.assertIn(b's"\xc3\xa9\\n\\\" // /* still text"', formatted.stdout)
        self.build_ok(formatted.stdout)
        self.assertEqual(self.output.read_bytes(), before)
        repeated = self.compiler_command('fmt', self.native_path(self.source))
        self.assertEqual(repeated.stdout, formatted.stdout)

    def test_format_multiline_crlf_weave_and_library_without_main(self):
        self.standard_library()
        source = b'weave "stdlib/numbers.ramos"\r\nfn main() {\r\nprint(num_max(\r\n1,\r\n2\r\n))\r\n}\r\n'
        self.build_ok(source)
        before = self.output.read_bytes()
        result = self.compiler_command('fmt', self.native_path(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'\n', result.stdout.replace(b'\r\n', b''))
        self.build_ok(result.stdout)
        self.assertEqual(self.output.read_bytes(), before)
        result2 = self.compiler_command('fmt', self.native_path(self.source))
        self.assertEqual(result2.stdout, result.stdout)
        result = self.format_file('fn value( )->int64 {return 1}')
        self.assertEqual(result.stdout, b'fn value() -> int64 { return 1 }\n')
        result = self.format_file(b'/* first\r\nsecond */')
        self.assertEqual(result.stdout, b'/* first\r\nsecond */\r\n')

    def test_format_output_creation_existing_output_and_source_protection(self):
        original = b'fn main( ){}\n'
        destination = self.directory / 'formatted.ramos'
        self.write_source(original)
        result = self.compiler_command('fmt', self.native_path(self.source), '-o', self.native_path(destination))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_bytes(), b'fn main() {}\n')
        destination.write_bytes(b'keep')
        result = self.compiler_command('fmt', self.native_path(self.source), '-o', self.native_path(destination))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(destination.read_bytes(), b'keep')
        result = self.compiler_command('fmt', self.native_path(self.source), '-o', self.native_path(destination), '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.compiler_command('fmt', self.native_path(self.source), '-o', self.native_path(self.source), '--force')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.source.read_bytes(), original)
        alias = self.directory / 'alias.ramos'; os.link(self.source, alias)
        result = self.compiler_command('fmt', self.native_path(self.source), '-o', self.native_path(alias), '--force')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.source.read_bytes(), original)

    def test_format_invalid_source_and_oversized_output_preserve_destination(self):
        destination = self.directory / 'output.ramos'; destination.write_bytes(b'keep')
        result = self.format_file('fn main() { /* missing', '-o', self.native_path(destination), '--force')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(destination.read_bytes(), b'keep')
        source = 'fn main() {\n' + 'let a=1\n' * 4200 + '// ' + 'x' * 1000000 + '\n}\n'
        # Below the input cap, but indentation/spacing expansion exceeds output cap.
        self.assertLess(len(source), 1048576)
        result = self.format_file(source, '-o', self.native_path(destination), '--force')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'formatted source exceeds', result.stderr)
        self.assertEqual(destination.read_bytes(), b'keep')

    def test_run_arguments_io_exit_status_and_temporary_cleanup(self):
        temp = self.directory / 'temp é'; temp.mkdir()
        code = 'fn main() {\nfor i in 1..arg_count() { stdout(arg(i))\nstdout("\\n") }\nprint(read_line())\nstderr("err\\n")\nexit(7)\n}'
        source = self.write_source(code)
        env = dict(os.environ, TMPDIR=self.native_path(temp), TMP=self.native_path(temp), TEMP=self.native_path(temp))
        args = ['', 'a b', 'tab\t', 'quote"', '\\"\\', 'é🚀', '; & $HOME']
        result = self.compiler_command('run', source, '--', *args, input=b'input\n', env=env)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, ('\n'.join(args) + '\ninput\n').encode(), b'err\n'))
        self.assertEqual(list(temp.iterdir()), [])
        self.assertFalse(self.output.exists())

    def test_run_compile_error_and_runtime_trap_cleanup(self):
        temp = self.directory / 'temp'; temp.mkdir()
        env = dict(os.environ, TMPDIR=self.native_path(temp), TMP=self.native_path(temp), TEMP=self.native_path(temp))
        for code, expected in [('fn main() { if 1 {} }', b'expected bool'), ('fn main() { print(1 / 0) }', b'arithmetic')]:
            result = self.compiler_command('run', self.write_source(code), env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn(expected, result.stderr)
            self.assertEqual(list(temp.iterdir()), [])

    def test_run_libraries_and_error_arguments_do_not_touch_existing_output(self):
        self.standard_library()
        source = self.write_source('weave "stdlib/numbers.ramos"\nfn main() { print(num_max(1, 2)) }')
        self.output.write_bytes(b'keep')
        result = self.compiler_command('run', source)
        self.assertEqual((result.returncode, result.stdout), (0, b'2\n'), result.stderr)
        self.assertEqual(self.output.read_bytes(), b'keep')
        self.assertEqual(self.compiler_command('run', source, '--target', 'windows').returncode, 1)
        self.assertEqual(self.compiler_command('run', source, '--', *([''] * 257)).returncode, 1)

    def test_run_unusable_temp_directory_fails_fallibly(self):
        source = self.write_source('fn main() { print("must not run") }')
        missing = self.directory / 'does not exist'
        env = dict(os.environ, TMPDIR=self.native_path(missing), TMP=self.native_path(missing), TEMP=self.native_path(missing))
        result = self.compiler_command('run', source, env=env)
        self.assertEqual((result.returncode, result.stdout), (1, b''))
        self.assertIn(b'I/O status', result.stderr)
        self.assertFalse(missing.exists())

    def test_run_with_no_build_tools_in_path(self):
        source = self.write_source('fn main() { print("native") }')
        env = dict(os.environ, PATH='/nonexistent')
        result = self.compiler_command('run', source, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, b'native\n'), result.stderr)

    def test_run_repeated_commands_cleanup(self):
        temp = self.directory / 'temp'; temp.mkdir()
        source = self.write_source('fn main() {}')
        env = dict(os.environ, TMPDIR=self.native_path(temp), TMP=self.native_path(temp), TEMP=self.native_path(temp))
        for _ in range(12):
            result = self.compiler_command('run', source, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(temp.iterdir()), [])
