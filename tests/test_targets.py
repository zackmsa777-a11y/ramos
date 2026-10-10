"""Target selection and PE emission from the self-hosted Linux compiler."""
import struct
import subprocess
import unittest
import test_ramos as support


@unittest.skipIf('stage0' in str(support.COMPILER), 'assembly bootstrap only emits Linux')
class TargetTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def test_cross_compile_windows_pe(self):
        result = self.build('fn main() { print("Windows") }', '--target', 'windows')
        self.assertEqual(result.returncode, 0, result.stderr)
        binary = self.output.read_bytes()
        self.assertEqual(binary[:2], b'MZ')
        nt = struct.unpack_from('<I', binary, 60)[0]
        self.assertEqual(binary[nt:nt + 4], b'PE\0\0')
        self.assertEqual(struct.unpack_from('<H', binary, nt + 4)[0], 0x8664)

    def test_target_and_force_in_either_order(self):
        for options in [('--target', 'windows', '--force'), ('--force', '--target', 'windows')]:
            self.output.write_bytes(b'old')
            result = self.build('fn main() {}', *options)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.output.read_bytes()[:2], b'MZ')

    def test_unknown_or_missing_target_never_publishes(self):
        for options in [('--target', 'other'), ('--target',), ('--target', 'windows', '--target', 'linux'),
                        ('--force', '--force')]:
            result = self.build('fn main() {}', *options)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.output.exists())

    def test_explicit_linux_preserves_default_output(self):
        source = 'fn main() { print(42) }'
        result = self.build(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        default = self.output.read_bytes()
        result = self.build(source, '--target', 'linux', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(default, self.output.read_bytes())


class PlatformTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    assert_runs = support.RamosTests.assert_runs

    def test_linux_platform_and_signature(self):
        self.assert_runs('fn main() { print(platform()) }', b'0\n')
        self.output.unlink()
        result = self.build('fn main() { print(platform(1)) }')
        self.assertNotEqual(result.returncode, 0)
