"""Native CLI OS boundary: resource ownership, argv fidelity and fallible errors."""
import os
from pathlib import Path
import subprocess
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams


@unittest.skipIf(BOOTSTRAP, 'retained seed predates system intrinsics and libraries')
class SystemTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs
    native_path = staticmethod(str)
    run_native = streams.StreamTests.run_native
    standard_library = streams.StreamTests.standard_library
    build_ok = streams.StreamTests.build_ok
    example = streams.StreamTests.example

    def child(self, code):
        self.build_ok(code)
        child = self.directory / 'child é space.exe'
        self.output.replace(child)
        return self.native_path(child)

    def test_cwd_and_environment_empty_missing_invalid_unicode(self):
        self.build_ok('''fn main() {
print(buffer_len(cwd()) > 0)
print(io_error())
print(env_get("RAMOS_SYSTEM_TEST"))
print(io_error())
print(buffer_len(env_get("RAMOS_SYSTEM_EMPTY")))
print(io_error())
print(buffer_len(env_get("RAMOS_SYSTEM_ABSENT_71293")))
print(io_error())
print(buffer_len(env_get("")))
print(io_error())
print(buffer_len(env_get("A=B")))
print(io_error())
print(buffer_len(env_get("A\\0B")))
print(io_error())
}''')
        env = dict(os.environ, RAMOS_SYSTEM_TEST='héllo 🚀', RAMOS_SYSTEM_EMPTY='')
        env.pop('RAMOS_SYSTEM_ABSENT_71293', None)
        result = self.run_native(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'true\n0\nhéllo 🚀\n0\n0\n0\n0\n-2\n0\n-22\n0\n-22\n0\n-22\n'.encode())

    def test_directory_entries_multiple_chunks_and_gc(self):
        root = self.directory / 'd é'
        root.mkdir()
        (root / 'sub').mkdir()
        names = [f'file{i:04}' for i in range(900)] + ['héllo 🚀']
        for name in names:
            (root / name).touch()
        self.build_ok('''fn main() {
let h = dir_open(arg(1))
print(io_error())
var count = 0
var directories = 0
while true {
    collect()
    let name = dir_next(h)
    if io_error() != 0 { print(io_error())\nexit(1) }
    if buffer_len(name) == 0 { break }
    let kind = dir_kind(h)
    if kind == 1 { count += 1 }
    if kind == 2 { directories += 1 }
    print(name)
}
print(count)
print(directories)
print(buffer_len(dir_next(h)))
print(dir_kind(h))
print(dir_close(h))
}''')
        result = self.run_native(self.native_path(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], b'0')
        self.assertEqual(set(lines[1:-5]), {x.encode() for x in names + ['sub']})
        self.assertEqual(lines[-5:], [b'901', b'1', b'0', b'0', b'0'])

    def test_directory_invalid_paths_stale_and_wrong_handle(self):
        self.build_ok('''fn main() {
print(dir_open(""))
print(dir_open("a\\0b"))
print(dir_open(arg(1)))
let h = dir_open(arg(2))
print(io_error())
let f = file_open(arg(1), 0)
print(buffer_len(dir_next(f)))
print(io_error())
print(file_close(h))
print(dir_close(h))
let next = dir_open(arg(2))
print(next != h)
print(buffer_len(dir_next(h)))
print(io_error())
print(dir_close(h))
print(dir_close(next))
print(file_close(f))
}''')
        file = self.directory / 'regular'; file.touch()
        result = self.run_native(self.native_path(file), self.native_path(self.directory))
        self.assertEqual(result.stdout, b'-22\n-22\n-20\n0\n0\n-9\n-9\n0\ntrue\n0\n-9\n-9\n0\n0\n')

    def test_directory_capacity_close_releases_slots(self):
        self.build_ok('''fn main() {
let handles = array(int64, 64, 0)
for i in 0..64 { handles[i] = dir_open(arg(1)) }
print(dir_open(arg(1)))
for i in 0..64 { if dir_close(handles[i]) != 0 { exit(1) } }
let h = dir_open(arg(1))
print(h > 0)
print(dir_close(h))
}''')
        self.assertEqual(self.run_native(self.native_path(self.directory)).stdout, b'-24\ntrue\n0\n')

    def test_directory_library_empty_and_close_lifecycle(self):
        empty = self.directory / 'empty'; empty.mkdir()
        self.standard_library()
        self.build_ok('''weave "stdlib/system.ramos"
fn main() {
let d = directory_open(arg(1))
let e = directory_next(d)
print(e.end)
print(e.status)
print(d.status)
print(directory_close(d))
print(directory_close(d))
print(directory_next(d).end)
}''')
        self.assertEqual(self.run_native(self.native_path(empty)).stdout, b'true\n0\n0\n0\n-9\ntrue\n')

    def test_path_lexical_helpers_and_native_separators(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/path.ramos"
fn main() {
print(path_join(s"root", s"é file"))
print(path_join(s"root/", s"x"))
print(path_join(s"", s"x"))
print(path_join(s"root", s"/abs"))
print(path_name(s"root/file///"))
print(path_name(s"/"))
print(path_absolute(s"../x"))
print(path_absolute(s"/x"))
print(path_absolute(s"C:\\\\x") == (platform() == 1))
print(path_join(s"C:", s"file"))
}''', b'root/\xc3\xa9 file\nroot/x\nx\n/abs\nfile\n\nfalse\ntrue\ntrue\n' + (b'C:file\n' if self.native_path(Path('x')).startswith(('Z:', 'C:')) or os.name == 'nt' else b'C:/file\n'))

    def test_process_argument_fidelity_inherited_streams_and_status(self):
        child = self.child('''fn main() {
for i in 1..arg_count() { print(buffer_len(arg(i)))\nstdout(arg(i))\nstdout("\\n") }
print(read_line())
print(env_get("RAMOS_CHILD_ENV"))
stderr("child stderr\\n")
exit(7)
}''')
        self.example('rrun')
        args = ['', 'space tab\t', 'quote"', 'backslash\\', '\\"\\', 'héllo 🚀', '; & $HOME > injected']
        result = self.run_native(child, *args, input=b'from stdin\n', env=dict(os.environ, RAMOS_CHILD_ENV='inherited'))
        expected = b''.join(str(len(x.encode())).encode() + b'\n' + x.encode() + b'\n' for x in args) + b'from stdin\ninherited\n'
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, expected, b'child stderr\n'))
        self.assertFalse((support.ROOT / 'injected').exists())

    def test_process_spawn_failure_distinct_from_exit_127(self):
        child = self.child('fn main() { exit(127) }')
        self.example('rrun')
        self.assertEqual(self.run_native(child).returncode, 127)
        result = self.run_native(child + '-missing')
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'process failed', result.stderr)

    def test_process_limits_and_nul_arguments_fail_without_trap(self):
        self.standard_library()
        self.assert_runs('''weave "stdlib/process.ramos"
fn main() {
let a = array(string, 1, s"bad\\0arg")
print(process_run(s"missing", a).status)
let many = array(string, 257, s"")
print(process_run(s"missing", many).status)
let long = array(string, 1, s"")
let data = buffer(32768)
for i in 0..32768 { buffer_set(data, i, 65) }
long[0] = string(data)
print(process_run(s"missing", long).status)
}''', b'-22\n-7\n-7\n')

    def test_process_repeated_children_and_gc(self):
        child = self.child('fn main() { exit(0) }')
        self.standard_library()
        self.build_ok('''weave "stdlib/process.ramos"
fn main() {
for i in 0..40 {
let result = process_run(string(arg(1)), array_empty(string))
if result.code != 0 || result.status != 0 { print(result.status)\nexit(1) }
collect()
}
print("ok")
}''')
        result = self.run_native(child)
        self.assertEqual((result.returncode, result.stdout), (0, b'ok\n'))

    def test_recursive_find_real_tree_filtered_and_missing(self):
        root = self.directory / 'tree'; root.mkdir()
        (root / 'é sub').mkdir()
        (root / 'empty').mkdir()
        (root / 'one.txt').touch()
        (root / 'é sub' / 'two.txt').touch()
        (root / 'é sub' / 'three.bin').touch()
        self.example('rfind')
        result = self.run_native(self.native_path(root), '.txt')
        self.assertEqual(result.returncode, 0, result.stderr)
        got = {x.decode().replace('\\', '/') for x in result.stdout.splitlines()}
        expected = {self.native_path(root / x).replace('\\', '/') for x in ['one.txt', 'é sub/two.txt']}
        self.assertEqual(got, expected)
        self.assertEqual(self.run_native(self.native_path(root / 'missing')).returncode, 2)
        self.assertEqual(self.run_native('--help').returncode, 0)

    @unittest.skipUnless(os.name != 'nt', 'Linux symlink fixture; Windows reparse fixture is separate')
    def test_recursive_find_skips_symlink_cycles(self):
        # When attached to the PE corpus under Wine, symlinks are not a Windows fixture.
        if self.native_path(self.directory).startswith('Z:'):
            self.skipTest('Linux symlink fixture')
        root = self.directory / 'tree'; root.mkdir()
        (root / 'file').touch()
        (root / 'loop').symlink_to(root, target_is_directory=True)
        self.example('rfind')
        result = self.run_native(str(root))
        self.assertEqual((result.returncode, result.stdout), (0, (str(root / 'file') + '\n').encode()))

    def test_process_exact_argument_limit_and_inherited_cwd(self):
        child = self.child('fn main() { print(arg_count())\nprint(cwd()) }')
        self.example('rrun')
        result = self.run_native(child, *([''] * 256))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], b'257')
        self.assertTrue(lines[1])
        self.assertEqual(self.run_native(child, *([''] * 257)).returncode, 2)

    def test_system_intrinsic_argument_types_checked(self):
        for expression in ['cwd(1)', 'env_get(1)', 'dir_open(1)', 'dir_next("x")', 'dir_kind("x")', 'dir_close("x")', '_process_run("x", 1)']:
            result = self.build('fn main() { ' + expression + ' }', '--force')
            self.assertNotEqual(result.returncode, 0, expression)

    def test_directory_trailing_separator_and_missing_path(self):
        root = self.directory / 'trailing'; root.mkdir()
        (root / 'file').touch()
        self.build_ok('''fn main() {
let d = dir_open(arg(1))
print(d > 0)
print(dir_next(d))
print(io_error())
print(dir_close(d))
print(dir_open(arg(2)))
}''')
        result = self.run_native(self.native_path(root) + '/', self.native_path(root / 'missing'))
        self.assertEqual(result.stdout, b'true\nfile\n0\n0\n-2\n')

    def test_python_child_uses_crt_argv_without_shell_interpretation(self):
        import json
        import sys
        if self.native_path(self.directory).startswith('Z:'):
            self.skipTest('Wine cannot run the host Python executable as a PE child')
        self.example('rrun')
        args = ['', 'a b', 'a\t b', 'a"b', '\\', '\\\\', '\\"', '\\\\"', 'trail \\', 'é🚀', 'line\nnext', '; & $HOME']
        code = 'import json,sys; print(json.dumps(sys.argv[1:], ensure_ascii=True))'
        result = self.run_native(sys.executable, '-c', code, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), args)

    @unittest.skipUnless(os.name == 'nt', 'requires a native Windows NTFS junction')
    def test_recursive_find_skips_windows_junction_cycle(self):
        root = self.directory / 'tree'; root.mkdir()
        (root / 'file').touch()
        junction = root / 'loop'
        result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(junction), str(root)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(lambda: os.rmdir(junction) if junction.exists() else None)
        self.example('rfind')
        result = self.run_native(str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        got = {x.decode().replace('\\', '/') for x in result.stdout.splitlines()}
        self.assertEqual(got, {str(root / 'file').replace('\\', '/')})

    def test_directory_create_exclusive_unicode_and_parent_errors(self):
        directory = self.directory / 'new é 🚀'
        self.build_ok('''fn main() {
print(dir_create(arg(1)))
print(io_error())
print(dir_create(arg(1)))
print(dir_create(arg(2)))
print(dir_create("bad\\0path"))
let h = dir_open(arg(1))
print(h > 0)
print(dir_close(h))
}''')
        result = self.run_native(self.native_path(directory), self.native_path(self.directory / 'missing' / 'child'))
        self.assertEqual(result.stdout, b'0\n0\n-17\n-2\n-22\ntrue\n0\n')
        self.assertTrue(directory.is_dir())
