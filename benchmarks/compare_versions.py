#!/usr/bin/env python3
"""Interleave old/new Ramos programs with identical sources, inputs and checksums."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import run_suite as suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-compiler', required=True, type=Path)
    parser.add_argument('--compiler', type=Path, default=suite.ROOT / 'ramos')
    parser.add_argument('--baseline-results', type=Path,
                        default=suite.ROOT / 'benchmarks/baseline-0.7.0/results.json')
    parser.add_argument('--output-dir', type=Path, default=suite.ROOT / 'benchmarks')
    parser.add_argument('--samples', type=int, default=9)
    args = parser.parse_args()
    if args.samples < 5:
        parser.error('at least five samples required')
    old, new = args.baseline_compiler.resolve(), args.compiler.resolve()
    baseline = json.loads(args.baseline_results.read_text())
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(old) != baseline['compiler_sha256']:
        parser.error('baseline compiler hash must match the baseline results')
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    work = suite.ROOT / 'work/paired-optimization'
    work.mkdir(parents=True, exist_ok=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rng, tasks = random.Random(70101), {}
    for task, t in baseline['tasks'].items():
        source = suite.FIXTURES / f'{task}.ramos'
        if digest(source) != t['sources']['Ramos']['sha256']:
            raise RuntimeError(f'{task}: changed source invalidates the comparison')
        programs = {name: work / f'{task}-{name}' for name in ('old', 'new')}
        for name, compiler in [('old', old), ('new', new)]:
            suite.run([compiler, 'build', source, '-o', programs[name], '--force'])
        n, seed = t['work_count'], t['seed']
        expected = suite.reference(task, n, seed)
        if f'{expected}\n' != t['expected_stdout']:
            raise RuntimeError(f'{task}: baseline reference mismatch')
        for _ in range(2):
            for program in programs.values():
                suite.run([program, n, seed], expected)
        samples, orders = {'old': [], 'new': []}, []
        for _ in range(args.samples):
            order = list(programs)
            rng.shuffle(order)
            orders.append(order)
            for name in order:
                samples[name].append(suite.run([programs[name], n, seed], expected)[0])
        timings = {name: suite.summarize(values) for name, values in samples.items()}
        ratio = timings['old']['median_ns'] / timings['new']['median_ns']
        tasks[task] = {'description': t['description'], 'work_count': n, 'seed': seed,
                       'source_sha256': digest(source), 'expected_stdout': f'{expected}\n',
                       'timings': timings, 'orders': orders, 'speedup': ratio,
                       'binary_sha256': {name: digest(p) for name, p in programs.items()}}
        print(f'{task}: {ratio:.3f}x; every output verified', flush=True)
    speed = suite.geomean(t['speedup'] for t in tasks.values())
    trials = []
    for _ in range(2000):
        trials.append(suite.geomean(
            statistics.median(rng.choices(t['timings']['old']['samples_ns'], k=args.samples)) /
            statistics.median(rng.choices(t['timings']['new']['samples_ns'], k=args.samples))
            for t in tasks.values()))
    report = {'measured_at_utc': datetime.now(timezone.utc).isoformat(),
              'compilers': {name: {'version': suite.run([p, '--version'])[1].stdout.decode().strip(),
                                    'sha256': digest(p)} for name, p in [('old', old), ('new', new)]},
              'settings': {'samples': args.samples, 'warmups': 2, 'pinned_cpu': cpu,
                           'random_seed': 70101, 'equal_task_weights': True},
              'tasks': tasks, 'geomean_speedup': speed,
              'bootstrap_95pct': [suite.quantile(trials, .025), suite.quantile(trials, .975)]}
    (output / 'optimization.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Ramos 0.7.1 optimization measurements', '',
             f'Ramos 0.7.1 executes these eight tasks **{speed:.2f}× faster** than the saved 0.7.0 compiler '
             '(equal-weight geometric mean of median time ratios).', '',
             '| Task | 0.7.0 ms | 0.7.1 ms | Speedup |', '|---|---:|---:|---:|']
    for t in tasks.values():
        lines.append(f"| {t['description']} | {t['timings']['old']['median_ns']/1e6:.3f} | "
                     f"{t['timings']['new']['median_ns']/1e6:.3f} | {t['speedup']:.2f}× |")
    low, high = report['bootstrap_95pct']
    lines += ['', f'Within-run bootstrap 95% interval: {low:.2f}–{high:.2f}×. It excludes machine/task-selection uncertainty.', '',
              'Both compilers build the same source hashes and use the same work counts, seeds and independent '
              f'reference outputs as the published baseline. Each pair has two verified warmups and {args.samples} '
              f'timed rounds with randomized old/new order on one pinned logical CPU. Every timed output '
              'is verified. The compiler hashes, binary hashes, ordering and raw samples are in '
              '[optimization.json](optimization.json). The host is the same shared Xeon Linux VM '
              'as the [four-language report](report.md). No Windows performance claim.', '',
              'The old compiler is preserved by SHA-256 from the [0.7.0 baseline](baseline-0.7.0/results.json). '
              'This interleaved comparison gives stronger evidence for the change than comparing timings '
              'recorded in separate runs. The [current C/Rust/Python comparison](report.md) uses those '
              'same workloads, with fresh samples. This is an execution index, not a language-quality grade.', '',
              '## Reproduce', '', '```sh',
              'git worktree add work/baseline-source v0.7.0', 'make -C work/baseline-source',
              'make', 'python3 benchmarks/compare_versions.py --baseline-compiler work/baseline-source/ramos', '```', '',
              'See [instruction selection and correctness](../docs/optimization.md).', '']
    (output / 'optimization.md').write_text('\n'.join(lines))
    print(f'Overall speedup: {speed:.3f}x', flush=True)


if __name__ == '__main__':
    main()
