"""Native OS boundary: binary bytes, fallible I/O, and safe publication."""
import os
import subprocess
import unittest
import test_ramos as support


class IOTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def run_program(self, code, *args):
        result = self.build(code, '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        return subprocess.run([str(self.output), *args], capture_output=True, timeout=5)

    def test_arguments_and_exit(self):
        result = self.run_program('''fn main() {
print(arg_count())
print(arg(1))
print(arg(2))
stderr("diagnostic\\n")
exit(7)
}''', 'é', '')
        self.assertEqual(result.stdout, '3\né\n\n'.encode())
        self.assertEqual(result.stderr, b'diagnostic\n')
        self.assertEqual(result.returncode, 7)

    def test_binary_read_and_atomic_write(self):
        src = self.directory / 'input'
        dst = self.directory / 'copy'
        src.write_bytes(b'\0\xff\x80hello')
        result = self.run_program('''fn main() {
let b = read_file(arg(1))
print(io_error())
print(buffer_len(b))
print(write_file(arg(2), b, 0))
print(io_error())
}''', str(src), str(dst))
        self.assertEqual(result.stdout, b'0\n8\n0\n0\n')
        self.assertEqual(dst.read_bytes(), src.read_bytes())
        self.assertEqual(dst.stat().st_mode & 0o777, 0o644)
        result = subprocess.run([str(self.output), str(src), str(dst)], capture_output=True)
        self.assertEqual(result.stdout, b'0\n8\n-17\n-17\n')
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_aliases_and_failed_publication_preserve_files(self):
        src = self.directory / 'input'
        alias = self.directory / 'alias'
        src.write_bytes(b'original')
        os.link(src, alias)
        for dst in (src, alias):
            result = self.run_program('''fn main() {
read_file(arg(1))
print(write_file(arg(2), "replacement", 3))
}''', str(src), str(dst))
            self.assertEqual(result.stdout, b'-22\n')
            self.assertEqual(src.read_bytes(), b'original')
        alias.unlink()
        alias.symlink_to(src)
        result = subprocess.run([str(self.output), str(src), str(alias)], capture_output=True)
        self.assertEqual(result.stdout, b'-22\n')
        directory = self.directory / 'is-directory'
        directory.mkdir()
        result = subprocess.run([str(self.output), str(src), str(directory)], capture_output=True)
        self.assertNotEqual(result.stdout, b'0\n')
        self.assertTrue(directory.is_dir())
        self.assertEqual(list(self.directory.glob('.ramos-tmp-*')), [])

    def test_errors_are_fallible_and_paths_reject_nul(self):
        fifo = self.directory / 'fifo'
        os.mkfifo(fifo)
        result = self.run_program('''fn main() {
let b = read_file(arg(1))
print(buffer_len(b))
print(io_error())
print(write_file("bad\\0path", "x", 0))
}''', str(fifo))
        self.assertEqual(result.stdout, b'0\n-22\n-22\n')
        result = subprocess.run([str(self.output), str(self.directory / 'absent')], capture_output=True)
        self.assertEqual(result.stdout, b'0\n-2\n-22\n')

    def test_replacement_flags_and_executable_mode(self):
        dst = self.directory / 'target'
        dst.write_bytes(b'old')
        result = self.run_program('fn main() { print(write_file(arg(1), "new", 3)) }', str(dst))
        self.assertEqual(result.stdout, b'0\n')
        self.assertEqual(dst.read_bytes(), b'new')
        self.assertEqual(dst.stat().st_mode & 0o777, 0o755)
