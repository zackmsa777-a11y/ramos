"""Reproducible Ramos 0.2 / GCC C / Rust / CPython microbenchmark.

Uses unrolled arithmetic because Ramos 0.2 has no loops or functions. For the
math-only measurement, adapt the generated Ramos main's input and exit to the
same function ABI as C/Rust. Arithmetic instruction bytes remain unchanged.
The separately measured CLI executables are completely unmodified.
"""
import argparse
import ctypes
import json
import mmap
import os
from pathlib import Path
import platform
import random
import statistics
import struct
import subprocess
import sys
import time


def checked_run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(str(command) + '\n' + result.stderr.decode(errors='replace'))
    return result


def summary(samples):
    ordered = sorted(samples)
    return {'median_ns': statistics.median(samples),
            'min_ns': min(samples), 'max_ns': max(samples),
            'p10_ns': ordered[int((len(ordered) - 1) * 0.1)],
            'p90_ns': ordered[int((len(ordered) - 1) * 0.9)],
            'samples_ns': samples}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'ramos')
    parser.add_argument('--work-dir', type=Path, default=Path('work/ramos-benchmark'))
    parser.add_argument('--output-dir', type=Path, default=Path('work/results-0.2'))
    parser.add_argument('--steps', type=int, default=2048)
    args = parser.parse_args()
    compiler, work, output = args.compiler.resolve(), args.work_dir.resolve(), args.output_dir.resolve()
    version = checked_run([compiler, '--version']).stdout.decode().splitlines()[0]
    if not version.startswith('Ramos 0.2.'):
        parser.error('this legacy binary adapter requires Ramos 0.2; '
                     'newer native calling conventions need a new benchmark harness')
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    allowed = sorted(os.sched_getaffinity(0))
    cpu = allowed[min(2, len(allowed) - 1)]
    os.sched_setaffinity(0, {cpu})
    steps = args.steps
    assert 1 <= steps <= 16000
    multiply, increment, modulus = 1664525, 1013904223, 2147483647

    def reference(seed):
        x = seed
        for _ in range(steps):
            x = (x * multiply + increment) % modulus
        return x

    update = f'x = (x * {multiply} + {increment}) % {modulus}'
    ramos_source = 'fn main() {\nvar x = 1\n' + (update + '\n') * steps
    (work / 'kernel.ramos').write_text(ramos_source + '}\n')
    (work / 'cli.ramos').write_text(ramos_source + 'print(x)\n}\n')
    python_source = 'def kernel(x):\n' + ('    ' + update + '\n') * steps
    python_source += '    return x\n\nif __name__ == "__main__":\n    print(kernel(1))\n'
    (work / 'cli.py').write_text(python_source)
    c_source = '#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <inttypes.h>\n'
    c_source += '__attribute__((noinline)) int64_t kernel(int64_t x) {\n'
    c_step = (f'if (__builtin_mul_overflow(x, INT64_C({multiply}), &x)) abort();\n'
              f'if (__builtin_add_overflow(x, INT64_C({increment}), &x)) abort();\n'
              f'x %= INT64_C({modulus});\n')
    c_source += c_step * steps + 'return x;\n}\n'
    c_source += ('#ifndef BENCH_SHARED\nvolatile int64_t input_seed = 1;\n'
                 'int main(void) { printf("%" PRId64 "\\n", kernel(input_seed)); return 0; }\n#endif\n')
    (work / 'cli.c').write_text(c_source)
    rust_source = '#[no_mangle]\n#[inline(never)]\npub extern "C" fn kernel(mut x: i64) -> i64 {\n'
    rust_source += ('    ' + update + ';\n') * steps + '    x\n}\n'
    rust_source += 'fn main() { println!("{}", kernel(std::hint::black_box(1i64))); }\n'
    (work / 'cli.rs').write_text(rust_source)
    runner_source = ('#include <stdint.h>\n'
                     'typedef int64_t (*kernel_fn)(int64_t);\n'
                     'uint64_t run(kernel_fn f, int64_t seed, uint64_t n) {\n'
                     ' uint64_t checksum = 0;\n'
                     ' for (uint64_t i = 0; i < n; ++i) checksum += (uint64_t) f(seed);\n'
                     ' return checksum;\n}\n')
    (work / 'runner.c').write_text(runner_source)

    commands = {
        'C': ['gcc', '-O3', '-std=c11', '-o', work / 'c-cli', work / 'cli.c'],
        'Rust': ['rustc', '--edition=2021', '-C', 'opt-level=3', '-C', 'overflow-checks=yes',
                 '-C', 'panic=abort', '-o', work / 'rust-cli', work / 'cli.rs'],
        'Ramos': [compiler, 'build', work / 'cli.ramos', '-o', work / 'ramos-cli', '--force'],
    }
    build = {}
    for name in ('Ramos', 'C', 'Rust'):
        samples = []
        for iteration in range(3):
            print(f'Building {name}, sample {iteration + 1}/3', flush=True)
            started = time.perf_counter_ns()
            checked_run(commands[name])
            samples.append(time.perf_counter_ns() - started)
        build[name] = summary(samples)

    print('Building shared kernels and repetition harness', flush=True)
    checked_run(['gcc', '-O3', '-std=c11', '-fPIC', '-shared', '-DBENCH_SHARED',
                 '-o', work / 'c-kernel.so', work / 'cli.c'])
    checked_run(['rustc', '--edition=2021', '--crate-type=cdylib', '-A', 'dead_code',
                 '-C', 'opt-level=3', '-C', 'overflow-checks=yes', '-C', 'panic=abort',
                 '-o', work / 'rust-kernel.so', work / 'cli.rs'])
    checked_run(['gcc', '-O3', '-std=c11', '-fPIC', '-shared', '-o', work / 'runner.so', work / 'runner.c'])
    checked_run([compiler, 'build', work / 'kernel.ramos', '-o', work / 'ramos-kernel', '--force'])

    # Convert process entry/exit to function argument/return without changing
    # any arithmetic, local accesses, safety checks, or relative code positions.
    image_bytes = bytearray((work / 'ramos-kernel').read_bytes())
    entry = struct.unpack_from('<Q', image_bytes, 24)[0] - 0x400000
    rx_length = struct.unpack_from('<Q', image_bytes, 96)[0]
    assert image_bytes[entry:entry + 7] == bytes.fromhex('55 48 89 e5 48 81 ec')
    literal = entry + 11
    assert image_bytes[literal:literal + 10] == bytes.fromhex('48 b8 01 00 00 00 00 00 00 00')
    assert image_bytes[rx_length - 9:rx_length] == bytes.fromhex('b8 3c 00 00 00 31 ff 0f 05')
    image_bytes[literal:literal + 10] = bytes.fromhex('48 89 f8') + b'\x90' * 7
    image_bytes[rx_length - 9:rx_length] = bytes.fromhex('48 8b 45 f8 c9 c3') + b'\x90' * 3
    mapping_size = (rx_length + mmap.PAGESIZE - 1) & -mmap.PAGESIZE
    image = mmap.mmap(-1, mapping_size, prot=mmap.PROT_READ | mmap.PROT_WRITE)
    image.write(image_bytes[:rx_length])
    address = ctypes.addressof(ctypes.c_char.from_buffer(image))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    assert libc.mprotect(address, mapping_size, mmap.PROT_READ | mmap.PROT_EXEC) == 0
    function_type = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)
    ramos_function = function_type(address + entry)
    libraries = {name: ctypes.CDLL(str(work / filename))
                 for name, filename in [('C', 'c-kernel.so'), ('Rust', 'rust-kernel.so')]}
    functions = {'Ramos': ramos_function}
    for name, library in libraries.items():
        library.kernel.argtypes = [ctypes.c_int64]
        library.kernel.restype = ctypes.c_int64
        functions[name] = library.kernel
    namespace = {'__name__': 'benchmark_kernel'}
    exec(compile(python_source, str(work / 'cli.py'), 'exec'), namespace)
    python_function = namespace['kernel']
    for seed in (1, 2, 123, 2147483646):
        expected = reference(seed)
        assert python_function(seed) == expected
        for name, function in functions.items():
            assert function(seed) == expected, (name, seed)
    expected_output = (str(reference(1)) + '\n').encode()

    runner = ctypes.CDLL(str(work / 'runner.so'))
    runner.run.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint64]
    runner.run.restype = ctypes.c_uint64
    addresses = {name: ctypes.cast(function, ctypes.c_void_p).value
                 for name, function in functions.items()}
    mask = (1 << 64) - 1

    def run_batch(name, count):
        if name == 'Python':
            checksum = 0
            for _ in range(count):
                checksum = (checksum + python_function(1)) & mask
            return checksum
        return runner.run(addresses[name], 1, count)

    repeats = {}
    for name in ('Python', 'Ramos', 'C', 'Rust'):
        count = 1
        while True:
            started = time.perf_counter_ns()
            checksum = run_batch(name, count)
            elapsed = time.perf_counter_ns() - started
            assert checksum == (reference(1) * count) & mask
            if elapsed >= 80_000_000:
                break
            count *= 2
        repeats[name] = count
        print(f'Calibrated {name}: {count} calculations per sample', flush=True)

    samples = {name: [] for name in repeats}
    rng = random.Random(971034)
    for iteration in range(11):
        order = list(repeats)
        rng.shuffle(order)
        for name in order:
            count = repeats[name]
            started = time.perf_counter_ns()
            checksum = run_batch(name, count)
            elapsed = time.perf_counter_ns() - started
            assert checksum == (reference(1) * count) & mask
            samples[name].append(elapsed / count)
        print(f'Arithmetic sample {iteration + 1}/11 complete', flush=True)

    cli_commands = {'Python': [sys.executable, work / 'cli.py'],
                    'Ramos': [work / 'ramos-cli'], 'C': [work / 'c-cli'], 'Rust': [work / 'rust-cli']}
    for name, command in cli_commands.items():
        for _ in range(5):
            assert checked_run(command).stdout == expected_output, name
    cli_samples = {name: [] for name in cli_commands}
    for iteration in range(101):
        order = list(cli_commands)
        rng.shuffle(order)
        for name in order:
            started = time.perf_counter_ns()
            result = checked_run(cli_commands[name])
            elapsed = time.perf_counter_ns() - started
            assert result.stdout == expected_output, name
            cli_samples[name].append(elapsed)

    versions = {name: checked_run(command).stdout.decode().splitlines()[0]
                for name, command in [('C', ['gcc', '--version']), ('Rust', ['rustc', '--version']),
                                      ('Python', [sys.executable, '--version']), ('Ramos', [compiler, '--version'])]}
    cpu_model = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                     if line.startswith('model name'))
    results = {'steps': steps, 'operation': update, 'expected_result': reference(1),
               'metadata': {'cpu': cpu_model, 'pinned_logical_cpu': cpu, 'platform': platform.platform(),
                            'versions': versions, 'clock': 'time.perf_counter_ns',
                            'command_lines': {name: [str(x) for x in command] for name, command in commands.items()}},
               'build': build, 'kernel': {name: {**summary(values), 'repeats_per_sample': repeats[name]}
                                         for name, values in samples.items()},
               'cli': {name: summary(values) for name, values in cli_samples.items()},
               'cli_binary_bytes': {name: Path(command[0]).stat().st_size
                                    for name, command in cli_commands.items() if name != 'Python'},
               'source_bytes': {name: (work / filename).stat().st_size for name, filename in
                                [('Ramos', 'cli.ramos'), ('C', 'cli.c'), ('Rust', 'cli.rs'), ('Python', 'cli.py')]}}
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({name: {'kernel_us': results['kernel'][name]['median_ns'] / 1000,
                            'cli_ms': results['cli'][name]['median_ns'] / 1e6,
                            'build_ms': build[name]['median_ns'] / 1e6 if name in build else None}
                      for name in ('Python', 'C', 'Rust', 'Ramos')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
