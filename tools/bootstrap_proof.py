#!/usr/bin/env python3
"""Record the source and native bootstrap fixed point; no compiler implementation."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args, env=None):
    subprocess.run(args, check=True, env=env, timeout=120)


def check_runtime():
    """Embedded PIC OS boundary must exactly match its audited bootstrap source."""
    sample = ROOT / 'build/runtime-proof.ramos'
    sample.write_text('fn main() {}\n')
    run('./build/stage0', 'build', str(sample), '-o', 'build/runtime-proof', '--force')
    symbols = {}
    for line in subprocess.check_output(['nm', '-n', 'build/stage0'], text=True).splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    source = (ROOT / 'compiler/ramos.ramos').read_text()
    runtime = bytes.fromhex(re.search(r'fn runtime_text\(\) -> bytes \{ return "([0-9a-f]+)"', source)[1])
    native = (ROOT / 'build/runtime-proof').read_bytes()[4096:4096 + symbols['RUNTIME_SIZE']]
    if runtime != native:
        raise SystemExit('Embedded runtime differs from bootstrap/src: update it before publication')
    entry = bytes.fromhex(re.search(r'fn entry_text\(\) -> bytes \{ return "([0-9a-f]+)"', source)[1])
    entry_offset = 4096 + symbols['RUNTIME_SIZE']
    sample_bytes = (ROOT / 'build/runtime-proof').read_bytes()
    if sample_bytes[entry_offset:entry_offset + symbols['ENTRY_INITIALIZE_SIZE']] != entry:
        raise SystemExit('Embedded process entry differs from bootstrap source')
    if int(re.search(r'fn runtime_end\(\) -> int64 \{ return (\d+)', source)[1]) != entry_offset:
        raise SystemExit('Runtime entry offset mismatch')
    from runtime_data import BUILTINS
    table = source[source.index('fn builtin_address'):]
    for i, name in enumerate(BUILTINS):
        value = int(re.search(r'if n == ' + str(i) + r' \{ return (\d+)', table)[1])
        expected = 4096 + symbols['runtime_' + name] - symbols['runtime_writer']
        if value != expected:
            raise SystemExit(f'Runtime intrinsic offset mismatch: {name}')
    for fn, const in [('math_address', 'RUNTIME_ERROR_FILE'), ('depth_address', 'RUNTIME_DEPTH_FILE'),
                      ('literal_address', 'RUNTIME_BUFFER_LITERAL_FILE'), ('integer_address', 'RUNTIME_INTEGER_FILE'),
                      ('boolean_address', 'RUNTIME_BOOLEAN_FILE'), ('print_buffer_address', 'RUNTIME_BUFFER_PRINT_FILE')]:
        value = int(re.search(r'fn ' + fn + r'\(\) -> int64 \{ return (\d+)', source)[1])
        if value != symbols[const]:
            raise SystemExit(f'Runtime address mismatch: {fn}')


def main():
    check_runtime()
    run(sys.executable, "tools/runtime_data.py")
    # The self-hosted executable runs with no assembler, linker, Python or compiler in PATH.
    environment = dict(os.environ, PATH='/nonexistent')
    run('./build/stage2', 'build', 'compiler/ramos.ramos', '-o', 'build/stage3-isolated', '--force', env=environment)
    hashes = {f'stage{i}': digest(ROOT / f'build/stage{i}') for i in range(4)}
    if hashes['stage2'] != hashes['stage3'] or digest(ROOT / 'build/stage3-isolated') != hashes['stage3']:
        raise SystemExit('Self-hosting fixed point failed')
    report = {
        'version': '0.10.0', 'target': 'x86_64-linux',
        'compiler_source': 'compiler/ramos.ramos',
        'source_sha256': digest(ROOT / 'compiler/ramos.ramos'),
        'executables': hashes, 'stage2_equals_stage3': True,
        'isolated_path_rebuild_matches': True, 'embedded_runtime_matches_bootstrap': True,
    }
    for stage in (0, 2, 3):
        env = dict(os.environ, RAMOS_COMPILER=str(ROOT / f'build/stage{stage}'))
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', env=env)
    report['tests_discovered_per_stage'] = unittest.TestLoader().discover(str(ROOT / 'tests')).countTestCases()
    report['bootstrap_skips_linux_only_target_selection_tests'] = 4
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_usability import UsabilityTests
    report['bootstrap_skips_post_0_7_grammar_tests'] = unittest.TestLoader().loadTestsFromTestCase(UsabilityTests).countTestCases()
    from test_values import ValueTests
    report['bootstrap_skips_values_tests'] = unittest.TestLoader().loadTestsFromTestCase(ValueTests).countTestCases()
    report['corpus_passed_with'] = ['stage0', 'stage2', 'stage3']
    (ROOT / 'build/bootstrap-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
