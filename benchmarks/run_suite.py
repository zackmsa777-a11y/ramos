#!/usr/bin/env python3
"""Eight ordinary CLI workloads; unmodified Ramos 0.7 binaries, checked peers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'benchmarks/fixtures'
LANGUAGES = ('Ramos', 'C', 'Rust', 'Python')
TASKS = {
    'lcg': ('Serial integer arithmetic / modulo', 100000),
    'branches': ('Data-dependent branches', 50000),
    'gcd': ('Euclidean GCD', 20000),
    'recursive_tree': ('Runtime-seeded recursive tree', 10),
    'byte_hash': ('Rolling byte-buffer hash', 100000),
    'insertion_sort': ('Insertion sort of 128 bytes', 50),
    'matrix': ('16×16 byte matrix multiplication', 25),
    'text_scan': ('Scan 16 KiB ASCII text', 25),
}
MOD = 1000000007


def reference(task, n, seed):
    """Independent or differently structured references; outside timed regions."""
    if task == 'startup':
        return seed
    if task == 'lcg':
        x = seed
        for _ in range(n):
            x = (1664525 * x + 1013904223) % 2147483647
        return x
    if task == 'branches':
        x, total = seed, 0
        for _ in range(n):
            x = 48271 * x % 2147483647
            total += x % (97 if x % 2 == 0 else 31) + (11 if x % 7 == 0 else 0)
        return total % MOD
    if task == 'gcd':
        x, total = seed, 0
        for i in range(n):
            x = 48271 * x % 2147483647
            total += math.gcd(x + 1, (i + seed) % 100000 + 1)
        return total % MOD
    if task == 'recursive_tree':
        x, total = seed, 0
        for _ in range(n):
            x = x * 48271 % 2147483647
            stack = [(12, x)]
            while stack:
                depth, value = stack.pop()
                if depth == 0:
                    total += value % 97
                else:
                    stack.append((depth - 1, (value * 17 + 3) % 1000003))
                    stack.append((depth - 1, (value * 29 + 5) % 1000003))
        return total % MOD
    if task == 'byte_hash':
        data = bytes((i * 17 + seed) % 256 for i in range(4096))
        h = seed
        for i in range(n):
            h = (33 * h + data[i % 4096]) % MOD
        return h
    if task == 'insertion_sort':
        cycle = []
        for r in range(min(n, 256)):
            data = sorted((i * 73 + seed + r) % 256 for i in range(128))
            cycle.append(sum(v * (i + 1) for i, v in enumerate(data)))
        return (sum(cycle) * (n // 256) + sum(cycle[:n % 256])) % MOD if n >= 256 else sum(cycle) % MOD
    if task == 'matrix':
        a = [(i * 17 + seed) % 256 for i in range(256)]
        b = [(i * 29 + seed) % 256 for i in range(256)]
        total = 0
        for r in range(n):
            a[r % 256] = (r + seed) % 256
            out = [sum(a[row * 16 + k] * b[k * 16 + col] for k in range(16)) % 256
                   for row in range(16) for col in range(16)]
            total += sum(v * (i + 1) for i, v in enumerate(out))
        return total % MOD
    if task == 'text_scan':
        data = [(i * 37 + seed) % 95 + 32 for i in range(16384)]
        def weight(c):
            return int(48 <= c <= 57) + 2 * int(65 <= c <= 90) + 3 * int(c == 32)
        count = sum(map(weight, data))
        total = 0
        for r in range(n):
            i, value = r % 16384, (r + seed) % 95 + 32
            count += weight(value) - weight(data[i])
            data[i] = value
            total += count
        return total % MOD
    raise ValueError(task)


def run(command, expected=None, timeout=180):
    started = time.perf_counter_ns()
    result = subprocess.run(list(map(str, command)), capture_output=True, timeout=timeout)
    elapsed = time.perf_counter_ns() - started
    if result.returncode:
        raise RuntimeError(f'{command}: exit {result.returncode}, {result.stderr!r}')
    if expected is not None and result.stdout != f'{expected}\n'.encode():
        raise RuntimeError(f'{command}: expected {expected}, got {result.stdout!r}')
    return elapsed, result


def quantile(samples, p):
    ordered = sorted(samples)
    index = (len(ordered) - 1) * p
    a, b = math.floor(index), math.ceil(index)
    return ordered[a] + (ordered[b] - ordered[a]) * (index - a)


def summarize(samples):
    return {'median_ns': statistics.median(samples), 'p10_ns': quantile(samples, .1),
            'p90_ns': quantile(samples, .9), 'min_ns': min(samples),
            'max_ns': max(samples), 'samples_ns': samples}


def geomean(values):
    return math.exp(statistics.mean(math.log(v) for v in values))


def scores(tasks):
    result = {}
    rng = random.Random(71821)
    for lang in LANGUAGES:
        ratios = [t['timings']['C']['median_ns'] / t['timings'][lang]['median_ns']
                  for t in tasks.values()]
        trials = []
        if lang != 'C':
            for _ in range(2000):
                trial = []
                for t in tasks.values():
                    a = t['timings']['C']['samples_ns']
                    b = t['timings'][lang]['samples_ns']
                    trial.append(statistics.median(rng.choices(a, k=len(a))) /
                                 statistics.median(rng.choices(b, k=len(b))))
                trials.append(100 * geomean(trial))
        else:
            trials = [100]
        result[lang] = {'score': 100 * geomean(ratios),
                        'bootstrap_95pct': [quantile(trials, .025), quantile(trials, .975)]}
    return result


def report_markdown(data):
    score = data['index']
    lines = [f"# Ramos {data['ramos_version'].split()[1]} performance: eight-task index", '',
             f"Measured {data['measured_at_utc']} on x86-64 Linux. Higher scores are faster; optimized C = 100.", '',
             '| Language | Overall execution index | Within-run bootstrap 95% interval |',
             '|---|---:|---:|']
    for lang in sorted(LANGUAGES, key=lambda x: score[x]['score'], reverse=True):
        s = score[lang]
        low, high = s['bootstrap_95pct']
        lines.append(f"| {lang} | {s['score']:.2f} | {low:.2f}–{high:.2f} |")
    python_speed = score['Ramos']['score'] / score['Python']['score']
    c_slow = 100 / score['Ramos']['score']
    rust_slow = score['Rust']['score'] / score['Ramos']['score']
    lines += ['', f'Across these tasks, Ramos is **{python_speed:.2f}× faster than Python**, '
              f'and takes **{c_slow:.2f}× the time of C** and **{rust_slow:.2f}× the time of Rust** '
              '(geometric means of per-task median ratios).', '',
              '## Per-task execution time', '',
              'Median wall time in milliseconds for the same work and seed. Includes process creation, '
              'loading, argument parsing, allocation, computation and one checked output line.', '',
              '| Task | Work count | Ramos | C | Rust | Python | Ramos vs Python |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for t in data['tasks'].values():
        med = {l: t['timings'][l]['median_ns'] for l in LANGUAGES}
        times = ' | '.join(f'{med[l] / 1e6:.3f}' for l in LANGUAGES)
        lines.append(f"| {t['description']} | {t['work_count']:,} | {times} | {med['Python'] / med['Ramos']:.2f}× |")
    lines += ['', '## Score definition', '',
              '`Index(language) = 100 × geometric_mean(C_median(task) / language_median(task))`', '',
              'All eight tasks have equal weight. The suite measures execution of ordinary programs, '
              'not patched code, an in-process kernel, compilation throughput or a universal language score. '
              'Startup is included in task timings but its separate probe is excluded from the index. '
              'The 95% intervals resample the collected timing samples; they do not capture uncertainty '
              'from different machines, task selection or operating systems.', '',
              '## Tasks and correctness', '',
              '- LCG: serial multiply/add/modulo recurrence with runtime seed.',
              '- Branches: runtime-generated parity and divisibility branches with checksum.',
              '- GCD: Euclidean remainder loops on varying positive inputs.',
              '- Recursion: traverse a depth-12 binary tree with runtime-dependent child values and leaf checksum.',
              '- Byte hash: visit a 4 KiB buffer and update a bounded polynomial hash.',
              '- Insertion sort: refill and sort 128 bytes; checksum weights sorted positions.',
              '- Matrix: multiply two 16×16 byte matrices, writing one input cell per pass, '
              'reduce output cells modulo 256, then checksum weighted positions.',
              '- Text scan: classify digits, uppercase ASCII and spaces in 16 KiB; write one byte per pass.', '',
              'Programs use the same algorithms, sizes, deterministic data and work count in all four '
              'languages. Work counts and seeds come from command-line arguments, so answers are not '
              'compile-time constants. All 32 task implementations pass independent reference checks '
              'at counts 0, 1 and 7 with seeds 1, 17 and 123. Full-size outputs are checked against '
              'references on every warmup and timed execution. Native compilers can optimize code '
              'normally; recursive calls may be transformed or inlined.', '',
              '## Measurement method', '',
              f"- {data['settings']['samples']} timed samples per task/language; randomized language order "
              'within each round, sequential execution, two verified warmups.',
              f"- Work counts calibrated until both C and Rust took at least about "
              f"{data['settings']['target_native_ms']:g} ms in the calibration probes. "
              'The same count is then held fixed for all languages.',
              '- This 0.7.1 run reuses the recorded 0.7.0 work counts; it does not recalibrate for the optimizer.',
              f"- Pinned to logical CPU {data['environment']['pinned_cpu']}; Python `perf_counter_ns` wall clock.",
              '- Shared virtual machine; CPU frequency, other tenants and background activity are '
              'not controlled. Warm filesystem caches; no Windows performance claim.',
              '- CPython executes source scripts normally, including parsing on every launch. '
              'C/Rust/Ramos binaries are built before execution timing.',
              '- GCC: `-O3 -std=c11`, with checked add/subtract/multiply builtins and explicit byte bounds.',
              '- Rust: `-C opt-level=3 -C overflow-checks=yes -C panic=abort`; safe byte indexing/conversion.',
              '- Ramos: default 0.7.1 native backend with local instruction selection optimizations; arithmetic, buffer and call-depth checks '
              'retained. Python integers stay within signed 64-bit range for these inputs. '
              'C/Rust can eliminate provably redundant checks; Python has no Ramos-style call-depth '
              'or byte arena limit. Limits are not reached by the suite.', '',
              'Raw nanosecond samples, p10/p90, calibration probes, build commands, source hashes and '
              'compiler/environment versions are retained in [results.json](results.json).', '',
              '## Startup probe (excluded from index)', '',
              'Argument parsing and printing a supplied integer; median over 51 randomized launches.', '',
              '| Ramos | C | Rust | Python |', '|---:|---:|---:|---:|',
              '| ' + ' | '.join(f"{data['startup'][l]['median_ns'] / 1e6:.3f} ms" for l in LANGUAGES) + ' |', '',
              '## Builds and output size (excluded from index)', '',
              'Median of three builds per task, including compiler startup and linking/publication. '
              'The table shows geometric means across tasks. It is not a general compiler throughput '
              'ranking: source sizes differ, and C/Rust use broader optimizers than the local Ramos emitter. '
              'Python is run as source and has no native binary in this experiment. Sizes are '
              'unstripped compiler outputs with different standard-library/linkage choices.', '',
              '| Language | Build time | Native binary size | Source size |', '|---|---:|---:|---:|']
    for lang in LANGUAGES:
        source_sizes = [t['sources'][lang]['bytes'] for t in data['tasks'].values()]
        if lang == 'Python':
            lines.append(f'| Python | — | — | {geomean(source_sizes):.0f} B |')
        else:
            builds = [t['builds'][lang]['median_ns'] / 1e6 for t in data['tasks'].values()]
            sizes = [t['binary_bytes'][lang] for t in data['tasks'].values()]
            lines.append(f'| {lang} | {geomean(builds):.3f} ms | {geomean(sizes):.0f} B | {geomean(source_sizes):.0f} B |')
    slowest = sorted(data['tasks'].values(),
                     key=lambda t: t['timings']['Ramos']['median_ns'] / t['timings']['C']['median_ns'],
                     reverse=True)[:3]
    lines += ['', '## Next work for Ramos', '',
              '1. Profile the largest native gaps before adding an optimization pass: ' +
              ', '.join(f"{t['description']} ({t['timings']['Ramos']['median_ns'] / t['timings']['C']['median_ns']:.1f}× C time)"
                        for t in slowest) + '. Version 0.7.1 already reduces buffer-call and stack traffic '
              'and specializes constant arithmetic. Further changes need their own measurements.',
              '2. Compare each optimizer change against these exact work counts and compiler hashes, '
              'with fresh samples, language correctness tests and both self-hosting proofs. '
              'See [the paired 0.7.0/0.7.1 comparison](optimization.md).',
              '3. Measure native Windows separately, then extend the suite with real file-processing '
              'programs. Keep syntax small while improving generated code.', '',
              '![Overall index and task ratios](score.png)', '',
              '## Environment', '', f"- CPU: {data['environment']['cpu_model']}",
              f"- Platform: {data['environment']['platform']}",
              *[f'- {value}' for value in data['environment']['versions'].values()],
              f"- Ramos executable SHA-256: `{data['compiler_sha256']}`", '',
              '## Reproduce', '', 'From the repository root on x86-64 Linux with GCC, Rust and Python:', '',
              '```sh', 'make', 'python3 benchmarks/run_suite.py', '```', '',
              'Use `--validate-only` for output verification without timings. `--work-counts '
              'benchmarks/results.json` reuses the published work counts; `--output-dir` keeps '
              'results from another machine separate. Workload sources are in [fixtures/](fixtures/). '
              'This is a custom Ramos suite, not a SPEC benchmark. The geometric mean follows '
              '[the established ratio aggregation method](https://open.spec.org/cpu2026/docs/runrules.html). '
              'See [GCC checked arithmetic](https://gcc.gnu.org/onlinedocs/gcc/Integer-Overflow-Builtins.html) '
              'and [Rust code generation settings](https://doc.rust-lang.org/rustc/codegen-options/index.html).', '',
              'Historical results from a different machine and Ramos 0.2 are preserved in '
              '[report-0.2.md](report-0.2.md) and [results-0.2.json](results-0.2.json); '
              'they are not directly comparable to this suite.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'ramos')
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'work/benchmark-0.7')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'benchmarks')
    parser.add_argument('--samples', type=int, default=9)
    parser.add_argument('--target-native-ms', type=float, default=30)
    parser.add_argument('--work-counts', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        parser.error('this suite currently measures x86-64 Linux')
    if args.samples < 5 or args.target_native_ms <= 0:
        parser.error('use at least five samples and a positive calibration target')
    compiler, work, output = args.compiler.resolve(), args.work_dir.resolve(), args.output_dir.resolve()
    version = run([compiler, '--version'])[1].stdout.decode().strip()
    if not version.startswith('Ramos 0.7.'):
        parser.error('these sources and bounds target Ramos 0.7')
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    versions = {'ramos': version}
    for name, cmd in [('gcc', ['gcc', '--version']), ('rustc', ['rustc', '--version']),
                      ('python', [sys.executable, '--version'])]:
        versions[name] = run(cmd)[1].stdout.decode().splitlines()[0]
    cpu_model = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                     if line.startswith('model name'))
    environment = {'cpu_model': cpu_model, 'platform': platform.platform(), 'pinned_cpu': cpu,
                   'logical_cpus': os.cpu_count(), 'versions': versions}
    fixed = json.loads(args.work_counts.read_text())['tasks'] if args.work_counts else {}
    rng = random.Random(7012026)
    task_results = {}
    startup = {}
    for task in [*TASKS, 'startup']:
        description, initial = TASKS.get(task, ('Startup probe', 0))
        print(f'Building and validating {task}', flush=True)
        sources = {l: FIXTURES / f"{task}.{ext}" for l, ext in
                   [('Ramos', 'ramos'), ('C', 'c'), ('Rust', 'rs'), ('Python', 'py')]}
        binaries = {l: work / f'{task}-{l.lower()}' for l in LANGUAGES if l != 'Python'}
        commands = {
            'Ramos': [compiler, 'build', sources['Ramos'], '-o', binaries['Ramos'], '--force'],
            'C': ['gcc', '-O3', '-std=c11', '-o', binaries['C'], sources['C']],
            'Rust': ['rustc', '--edition=2021', '-C', 'opt-level=3', '-C', 'overflow-checks=yes',
                     '-C', 'panic=abort', '-o', binaries['Rust'], sources['Rust']],
        }
        builds = {l: [] for l in commands}
        for _ in range(1 if args.validate_only else 3):
            order = list(commands)
            rng.shuffle(order)
            for lang in order:
                builds[lang].append(run(commands[lang])[0])
        runtime = {l: [binaries[l]] for l in binaries}
        runtime['Python'] = [sys.executable, sources['Python']]
        for n in (0, 1, 7):
            for seed in (1, 17, 123):
                expected = reference(task, n, seed)
                for lang in LANGUAGES:
                    run([*runtime[lang], n, seed], expected)
        if args.validate_only:
            continue
        calibration = []
        n = int(fixed[task]['work_count']) if task in fixed else initial
        if task != 'startup' and task not in fixed:
            for _ in range(12):
                probes = {l: [run([*runtime[l], n, 17])[0] for _ in range(2)] for l in ('C', 'Rust')}
                fastest = min(statistics.median(v) for v in probes.values())
                calibration.append({'work_count': n, 'probes_ns': probes})
                if fastest >= args.target_native_ms * 1e6:
                    break
                factor = min(16, max(1.3, args.target_native_ms * 1e6 / fastest * 1.15))
                n = math.ceil(n * factor)
            else:
                raise RuntimeError(f'Calibration did not settle for {task}')
        print(f'{task}: work count {n:,}; calculating independent reference', flush=True)
        expected = reference(task, n, 17)
        for _ in range(2):
            for lang in LANGUAGES:
                run([*runtime[lang], n, 17], expected)
        count = 51 if task == 'startup' else args.samples
        samples = {l: [] for l in LANGUAGES}
        orders = []
        for sample in range(count):
            order = list(LANGUAGES)
            rng.shuffle(order)
            orders.append(order)
            for lang in order:
                samples[lang].append(run([*runtime[lang], n, 17], expected)[0])
            if task != 'startup':
                print(f'{task}: sample {sample + 1}/{count} verified', flush=True)
        if task == 'startup':
            startup = {l: summarize(v) for l, v in samples.items()}
            continue
        task_results[task] = {
            'description': description, 'work_count': n, 'seed': 17, 'expected_stdout': f'{expected}\n',
            'timings': {l: summarize(v) for l, v in samples.items()}, 'calibration': calibration,
            'measurement_orders': orders, 'builds': {l: summarize(v) for l, v in builds.items()},
            'build_commands': {l: list(map(str, c)) for l, c in commands.items()},
            'runtime_commands': {l: list(map(str, [*c, n, 17])) for l, c in runtime.items()},
            'binary_bytes': {l: p.stat().st_size for l, p in binaries.items()},
            'sources': {l: {'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for l, p in sources.items()},
        }
        (output / 'partial-results.json').write_text(json.dumps(task_results, indent=2) + '\n')
    if args.validate_only:
        print('All 36 programs verified: nine (including startup) × four languages × nine input cases.', flush=True)
        return
    data = {'schema_version': 1, 'suite': 'ramos-eight-task-cli-v1',
            'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'ramos_version': version,
            'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(), 'environment': environment,
            'settings': {'samples': args.samples, 'target_native_ms': args.target_native_ms,
                         'warmups': 2, 'random_seed': 7012026, 'index_reference': 'C=100',
                         'equal_task_weights': True, 'startup_in_index': False,
                         'fixed_baseline_work_counts': bool(args.work_counts)},
            'tasks': task_results, 'startup': startup, 'index': scores(task_results)}
    (output / 'results.json').write_text(json.dumps(data, indent=2) + '\n')
    (output / 'report.md').write_text(report_markdown(data))
    (output / 'partial-results.json').unlink(missing_ok=True)
    print(json.dumps(data['index'], indent=2), flush=True)


if __name__ == '__main__':
    main()
