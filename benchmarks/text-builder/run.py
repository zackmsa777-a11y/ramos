#!/usr/bin/env python3
"""Measure one text-assembly workload; this is not the C/Rust/Python suite."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'ramos')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    builds = ROOT / 'build/text-builder-benchmark'
    builds.mkdir(parents=True, exist_ok=True)
    binaries = {}
    for name in ['concat', 'builder']:
        binary = builds / name
        subprocess.run([str(compiler), 'build', str(Path(__file__).parent / (name + '.ramos')),
                        '-o', str(binary), '--force'], check=True)
        binaries[name] = binary
    results = []
    for count in [1024, 2048, 4096, 8192]:
        timings = {name: [] for name in binaries}
        # One warmup per variant; alternate measurement order to limit ordering bias.
        for sample in range(6):
            order = list(binaries) if sample % 2 == 0 else list(reversed(binaries))
            for name in order:
                start = time.perf_counter()
                result = subprocess.run([str(binaries[name]), str(count)], capture_output=True,
                                        timeout=60, check=True)
                elapsed = time.perf_counter() - start
                assert result.stdout == f'true\n{count * 64}\n'.encode(), result.stdout
                assert result.stderr == b'', result.stderr
                if sample:
                    timings[name].append(elapsed)
        row = {'appends': count, 'result_bytes': count * 64, 'timings_seconds': timings}
        row['medians_seconds'] = {name: statistics.median(values) for name, values in timings.items()}
        row['concat_over_builder'] = row['medians_seconds']['concat'] / row['medians_seconds']['builder']
        results.append(row)
    report = {'measured_at': datetime.now(timezone.utc).isoformat(), 'version': subprocess.check_output([str(compiler), '--version'], text=True).strip(),
              'machine': platform.platform(), 'cpu': next((line.split(':', 1)[1].strip() for line in
                  Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown'),
              'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
              'text_library_sha256': hashlib.sha256((ROOT / 'stdlib/text.ramos').read_bytes()).hexdigest(),
              'method': 'Linux native processes; one warmup and five measured runs; alternate order; elapsed includes startup and full content verification against text_repeat; 64-byte ASCII appends; same compiler and OS checks in both variants.',
              'scope': 'Single application workload comparing two Ramos APIs, not a language score or a comparison with C, Rust or Python.',
              'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
