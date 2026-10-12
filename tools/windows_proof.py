#!/usr/bin/env python3
"""Run native PE programs and prove Windows self-hosting, on Windows or Wine."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
COMPILER = Path(os.environ.get('RAMOS_WINDOWS_COMPILER', BUILD / 'ramos.exe')).resolve()
RUNNER = [] if os.name == 'nt' else [os.environ.get('RAMOS_WINE', shutil.which('wine') or 'wine')]
ENV = dict(os.environ, WINEDEBUG='-all')


def winpath(path):
    path = Path(path).resolve()
    return str(path) if os.name == 'nt' else 'Z:' + str(path).replace('/', '\\')


def execute(binary, *args, timeout=45, input=None, stdin=None, env=None):
    return subprocess.run([*RUNNER, str(binary), *args], cwd=ROOT, env=ENV if env is None else dict(env, WINEDEBUG="-all"),
                          capture_output=True, timeout=timeout, input=input, stdin=stdin)


def compile_source(source, output, *options, compiler=None):
    return execute(compiler or COMPILER, 'build', winpath(source), '-o', winpath(output), *options)


def checked(result):
    if result.returncode:
        raise RuntimeError(f'Native Windows command failed ({result.returncode}): {result.stderr!r}')
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / 'source.ramos'
        self.output = self.directory / 'program.exe'

    def build(self, source, *extra):
        self.source.write_bytes(source.encode() if isinstance(source, str) else source)
        return compile_source(self.source, self.output, *extra)

    def assert_runs(self, source, expected):
        result = self.build(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = execute(self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)

    def test_pe_layout_and_permissions(self):
        self.assert_runs('fn main() { print("hello") }', b'hello\n')
        binary = self.output.read_bytes()
        self.assertEqual(binary[:2], b'MZ')
        nt = struct.unpack_from('<I', binary, 60)[0]
        self.assertEqual(binary[nt:nt + 4], b'PE\0\0')
        machine, count, timestamp = struct.unpack_from('<HHI', binary, nt + 4)
        self.assertEqual((machine, count, timestamp), (0x8664, 4, 0))
        optional = nt + 24
        self.assertEqual(struct.unpack_from('<H', binary, optional)[0], 0x20b)
        self.assertEqual(struct.unpack_from('<H', binary, optional + 68)[0], 3)
        self.assertEqual(struct.unpack_from('<Q', binary, optional + 72)[0], 8 * 1024 * 1024)
        protections = struct.unpack_from('<H', binary, optional + 70)[0]
        self.assertEqual(protections & 0x160, 0x160)  # NX, ASLR, high entropy
        start = optional + 240
        names = []
        next_rva = 4096
        for i in range(count):
            at = start + i * 40
            names.append(binary[at:at + 8].rstrip(b'\0'))
            virtual_size, rva, raw_size, raw = struct.unpack_from('<IIII', binary, at + 8)
            flags = struct.unpack_from('<I', binary, at + 36)[0]
            self.assertFalse(flags & 0x80000000 and flags & 0x20000000)
            self.assertLessEqual(raw + raw_size, len(binary))
            self.assertEqual(raw % 4096, 0)
            self.assertEqual(rva % 4096, 0)
            self.assertEqual(rva, next_rva)
            next_rva = rva + ((max(virtual_size, raw_size) + 4095) // 4096) * 4096
        self.assertEqual(names, [b'.text', b'.rdata', b'.idata', b'.reloc'])
        self.assertIn(b'KERNEL32.dll\0', binary)
        self.assertIn(b'SHELL32.dll\0', binary)
        self.assertNotIn(b'msvcrt.dll\0', binary.lower())

    def test_checked_runtime_failures(self):
        for expression, message in [('9223372036854775807 + 1', b'arithmetic'),
                                    ('-9223372036854775808 / -1', b'arithmetic'),
                                    ('1 / 0', b'arithmetic'),
                                    ('buffer_get(buffer(1), 1)', b'buffer index'),
                                    ('buffer_get(buffer(-1), 0)', b'buffer size')]:
            with self.subTest(expression=expression):
                checked(self.build('fn main() { print(' + expression + ') }', '--force'))
                result = execute(self.output)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)

    def test_arguments_unicode_quotes_and_exit(self):
        checked(self.build('''fn main() {
print(platform())
print(arg_count())
print(arg(1))
print(arg(2))
print(arg(3))
print(arg(4))
stderr("diagnostic\\n")
exit(7)
}'''))
        result = execute(self.output, 'مرحبا 🌍', '', 'a"b', 'trailing\\')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, '1\n5\nمرحبا 🌍\n\na"b\ntrailing\\\n'.encode())
        self.assertEqual(result.stderr, b'diagnostic\n')

    def test_binary_io_unicode_paths_and_preservation(self):
        source = self.directory / 'مرحبا source.bin'
        output = self.directory / 'é copy.bin'
        source.write_bytes(b'\0\xff\x80binary\n')
        checked(self.build('''fn main() {
let content = read_file(arg(1))
print(io_error())
print(buffer_len(content))
print(write_file(arg(2), content, 0))
print(io_error())
}'''))
        result = execute(self.output, winpath(source), winpath(output))
        self.assertEqual(result.stdout, b'0\n10\n0\n0\n')
        self.assertEqual(output.read_bytes(), source.read_bytes())
        result = execute(self.output, winpath(source), winpath(output))
        self.assertEqual(result.stdout, b'0\n10\n-17\n-17\n')
        self.assertEqual(output.read_bytes(), source.read_bytes())
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_source_alias_and_invalid_build_preserve_output(self):
        text = 'fn main() { print("original") }'
        self.source.write_text(text)
        alias = self.directory / 'alias.exe'
        os.link(self.source, alias)
        for output in (self.source, alias):
            result = compile_source(self.source, output, '--force')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.source.read_text(), text)
        self.output.write_bytes(b'preserve this')
        result = self.build('fn main() { print( }', '--force')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'preserve this')
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_force_replace_and_failed_directory_publication(self):
        self.output.write_bytes(b'old')
        result = self.build('fn main() { print("new") }')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'old')
        checked(self.build('fn main() { print("new") }', '--force'))
        self.assertEqual(execute(self.output).stdout, b'new\n')
        self.output.unlink()
        self.output.mkdir()
        result = self.build('fn main() {}', '--force')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_large_windows_stack_frame(self):
        declarations = ''.join(f'let value_{i} = {i}\n' for i in range(4096))
        self.assert_runs('fn main() {\n' + declarations + 'print(value_4095)\n}', b'4095\n')

    def test_native_windows_cross_compiles_linux(self):
        result = self.build('fn main() { print(42) }', '--target', 'linux')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes()[:4], b'\x7fELF')
        if os.name != 'nt':
            self.output.chmod(0o755)
            result = subprocess.run([str(self.output)], capture_output=True, timeout=10)
            self.assertEqual(result.stdout, b'42\n')

    def test_invalid_target_is_rejected_without_output(self):
        for options in [('--target', 'other'), ('--target',), ('--target', 'windows', '--target', 'linux')]:
            result = self.build('fn main() {}', *options)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.output.exists())

    def test_examples(self):
        for name in ('hello', 'calculator', 'control_flow', 'functions', 'buffers', 'usability'):
            with self.subTest(example=name):
                checked(compile_source(ROOT / f'examples/{name}.ramos', self.output, '--force'))
                checked(execute(self.output))

    def test_version_and_help(self):
        self.assertIn(b'Ramos 0.22.0', checked(execute(COMPILER, '--version')).stdout)
        self.assertIn(b'--target linux|windows', checked(execute(COMPILER, '--help')).stdout)


# Reuse shared language contracts instead of defining a second Windows dialect.
sys.path.insert(0, str(ROOT / 'tests'))
import test_ramos
for name in (
    'test_empty_body', 'test_multiple_prints_unicode_and_escapes', 'test_crlf_and_whitespace',
    'test_reject_invalid_source_without_output', 'test_integer_literals_and_signed_limits',
    'test_arithmetic_precedence_associativity_and_unary', 'test_signed_division_and_remainder',
    'test_integer_bindings_mutation_and_mixed_printing', 'test_reject_invalid_integers_expressions_and_bindings',
    'test_many_distinct_bindings_resolve_correctly', 'test_arithmetic_at_valid_boundaries',
    'test_boolean_literals_bindings_and_not', 'test_typed_comparisons_and_precedence',
    'test_if_else_and_skipped_runtime_failure', 'test_while_break_continue_and_stack_balance',
    'test_nested_loops_target_innermost_loop', 'test_block_scope_shadowing_and_reinitialization',
    'test_control_flow_and_type_errors', 'test_shadow_initializer_and_type_restore',
    'test_control_flow_crlf_and_newline_lookahead', 'test_functions_forward_calls_and_typed_returns',
    'test_function_call_limit_and_counter_restoration',
    'test_function_recursion_and_mutual_recursion', 'test_void_functions_early_return_and_discarded_value',
    'test_argument_evaluation_and_expression_stack_survive_calls',
    'test_functions_have_independent_frames_and_lexical_scope',
    'test_function_signatures_crlf_and_multiline_arguments', 'test_function_type_scope_and_return_errors',
    'test_nested_calls_in_assignment_rhs', 'test_native_arithmetic_matches_seeded_integer_cases',
):
    setattr(WindowsTests, name, getattr(test_ramos.RamosTests, name))


import test_stack
for name in dir(test_stack.StackTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_stack.StackTests, name))
WindowsTests.stack_run = lambda self: execute(self.output)
WindowsTests.wide_source = staticmethod(test_stack.StackTests.wide_source)


import test_optimization
WindowsTests.run_output = lambda self: execute(self.output)
for name in dir(test_optimization.OptimizationTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_optimization.OptimizationTests, name))


import test_usability
for name in dir(test_usability.UsabilityTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_usability.UsabilityTests, name))


import test_syntax
for name in dir(test_syntax.SyntaxTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_syntax.SyntaxTests, name))


import test_input_text
WindowsTests.run_native = lambda self, *args, **kwargs: execute(self.output, *args, **kwargs)
WindowsTests.native_path = staticmethod(winpath)
WindowsTests.start_native = lambda self: subprocess.Popen(
    [*RUNNER, str(self.output)], cwd=ROOT, env=ENV,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
WindowsTests.build_ok = test_input_text.InputTextTests.build_ok
for name in dir(test_input_text.InputTextTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_input_text.InputTextTests, name))


import test_values
WindowsTests.assert_traps = test_values.ValueTests.assert_traps
for name in dir(test_values.ValueTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_values.ValueTests, name))


import test_libraries
WindowsTests.library = test_libraries.LibraryTests.library
WindowsTests.standard_library = test_libraries.LibraryTests.standard_library
for name in dir(test_libraries.LibraryTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_libraries.LibraryTests, name))


import test_cli_streams
WindowsTests.example = test_cli_streams.StreamTests.example
for name in dir(test_cli_streams.StreamTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_cli_streams.StreamTests, name))

import test_devtools
WindowsTests.compiler_executable = COMPILER
WindowsTests.compiler_prefix = RUNNER
WindowsTests.compiler_command = lambda self, *args, **kwargs: execute(COMPILER, *args, **kwargs)
WindowsTests.write_source = test_devtools.DevToolsTests.write_source
WindowsTests.format_file = test_devtools.DevToolsTests.format_file
for name in dir(test_devtools.DevToolsTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_devtools.DevToolsTests, name))
if RUNNER:
    # Wine replaces invalid TMP/TEMP values with its own Windows temp path.
    WindowsTests.test_run_unusable_temp_directory_fails_fallibly = unittest.skip(
        'requires native Windows temp-directory environment handling')(
            WindowsTests.test_run_unusable_temp_directory_fails_fallibly)

import test_system
WindowsTests.child = test_system.SystemTests.child
for name in dir(test_system.SystemTests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_system.SystemTests, name))

import test_text_builder
for name in dir(test_text_builder.TextBuilderTests):
    if name.startswith('test_'):
        setattr(WindowsTests, name, getattr(test_text_builder.TextBuilderTests, name))

import test_float
for name in dir(test_float.FloatTests):
    if name.startswith('test_'):
        setattr(WindowsTests, name, getattr(test_float.FloatTests, name))

import test_math_input
for name in dir(test_math_input.MathInputTests):
    if name.startswith('test_'):
        setattr(WindowsTests, name, getattr(test_math_input.MathInputTests, name))

import test_tui
for name in dir(test_tui.TUITests):
    if name.startswith("test_"):
        setattr(WindowsTests, name, getattr(test_tui.TUITests, name))

import test_console_native
WindowsTests.console_probe = test_console_native.WindowsConsoleTests.console_probe
if os.name == 'nt':
    for name in dir(test_console_native.WindowsConsoleTests):
        if name.startswith("test_"):
            setattr(WindowsTests, name, getattr(test_console_native.WindowsConsoleTests, name))


import test_gui
for name in dir(test_gui.GUITests):
    if name.startswith('test_'):
        setattr(WindowsTests, name, getattr(test_gui.GUITests, name))
WindowsTests.gui_probe = test_gui.WindowsGUITests.gui_probe
if os.name == 'nt' or os.environ.get('RAMOS_GUI_WINE_PYTHON'):
    for name in dir(test_gui.WindowsGUITests):
        if name.startswith('test_'):
            setattr(WindowsTests, name, getattr(test_gui.WindowsGUITests, name))


def main():
    if not COMPILER.is_file():
        raise SystemExit('Build the native Windows compiler first: make windows')
    BUILD.mkdir(exist_ok=True)
    source = ROOT / 'compiler/ramos.ramos'
    stage2 = BUILD / 'windows-stage2.exe'
    stage3 = BUILD / 'windows-stage3.exe'
    checked(compile_source(source, stage2, '--force'))
    checked(compile_source(source, stage3, '--force', compiler=stage2))
    hashes = {'seed': sha(COMPILER), 'stage2': sha(stage2), 'stage3': sha(stage3)}
    if len(set(hashes.values())) != 1:
        raise SystemExit('Windows self-hosting did not reach the deterministic fixed point')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WindowsTests)
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    report = {
        'version': checked(execute(COMPILER, '--version')).stdout.decode().split()[1], 'target': 'x86_64-windows',
        'execution_host': 'windows' if os.name == 'nt' else 'wine',
        'source_sha256': sha(source), 'executables': hashes,
        'stage2_equals_stage3': True, 'seed_equals_stage2': True,
        'tests_discovered': count, 'tests_skipped': len(result.skipped),
        'tests_passed': count - len(result.skipped),
    }
    (BUILD / 'windows-bootstrap-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
