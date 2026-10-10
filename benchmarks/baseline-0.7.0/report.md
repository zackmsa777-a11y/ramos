# Ramos 0.7.0 performance: eight-task index

Measured 2026-10-10T06:24:57.693306+00:00 on x86-64 Linux. Higher scores are faster; optimized C = 100.

| Language | Overall execution index | Within-run bootstrap 95% interval |
|---|---:|---:|
| Rust | 119.04 | 117.54–120.57 |
| C | 100.00 | 100.00–100.00 |
| Ramos | 19.93 | 19.73–20.49 |
| Python | 2.53 | 2.49–2.56 |

Across these tasks, Ramos is **7.89× faster than Python**, and takes **5.02× the time of C** and **5.97× the time of Rust** (geometric means of per-task median ratios).

## Per-task execution time

Median wall time in milliseconds for the same work and seed. Includes process creation, loading, argument parsing, allocation, computation and one checked output line.

| Task | Work count | Ramos | C | Rust | Python | Ramos vs Python |
|---|---:|---:|---:|---:|---:|---:|
| Serial integer arithmetic / modulo | 6,640,450 | 82.997 | 30.884 | 33.085 | 1076.429 | 12.97× |
| Data-dependent branches | 2,766,668 | 101.765 | 30.296 | 30.783 | 728.550 | 7.16× |
| Euclidean GCD | 577,528 | 106.478 | 39.523 | 33.021 | 423.261 | 3.98× |
| Runtime-seeded recursive tree | 1,402 | 143.703 | 35.651 | 48.739 | 1397.788 | 9.73× |
| Rolling byte-buffer hash | 7,151,162 | 108.531 | 32.221 | 40.125 | 973.571 | 8.97× |
| Insertion sort of 128 bytes | 10,991 | 555.741 | 38.510 | 36.718 | 3642.678 | 6.55× |
| 16×16 byte matrix multiplication | 22,503 | 1188.317 | 171.012 | 31.840 | 10883.310 | 9.16× |
| Scan 16 KiB ASCII text | 2,242 | 463.551 | 38.264 | 34.536 | 3591.434 | 7.75× |

## Score definition

`Index(language) = 100 × geometric_mean(C_median(task) / language_median(task))`

All eight tasks have equal weight. The suite measures execution of ordinary programs, not patched code, an in-process kernel, compilation throughput or a universal language score. Startup is included in task timings but its separate probe is excluded from the index. The 95% intervals resample the collected timing samples; they do not capture uncertainty from different machines, task selection or operating systems.

## Tasks and correctness

- LCG: serial multiply/add/modulo recurrence with runtime seed.
- Branches: runtime-generated parity and divisibility branches with checksum.
- GCD: Euclidean remainder loops on varying positive inputs.
- Recursion: traverse a depth-12 binary tree with runtime-dependent child values and leaf checksum.
- Byte hash: visit a 4 KiB buffer and update a bounded polynomial hash.
- Insertion sort: refill and sort 128 bytes; checksum weights sorted positions.
- Matrix: multiply two 16×16 byte matrices, writing one input cell per pass, reduce output cells modulo 256, then checksum weighted positions.
- Text scan: classify digits, uppercase ASCII and spaces in 16 KiB; write one byte per pass.

Programs use the same algorithms, sizes, deterministic data and work count in all four languages. Work counts and seeds come from command-line arguments, so answers are not compile-time constants. All 32 task implementations pass independent reference checks at counts 0, 1 and 7 with seeds 1, 17 and 123. Full-size outputs are checked against references on every warmup and timed execution. Native compilers can optimize code normally; recursive calls may be transformed or inlined.

## Measurement method

- 9 timed samples per task/language; randomized language order within each round, sequential execution, two verified warmups.
- Work counts calibrated until both C and Rust took at least about 30 ms in the calibration probes. The same count is then held fixed for all languages.
- Pinned to logical CPU 0; Python `perf_counter_ns` wall clock.
- Shared virtual machine; CPU frequency, other tenants and background activity are not controlled. Warm filesystem caches; no Windows performance claim.
- CPython executes source scripts normally, including parsing on every launch. C/Rust/Ramos binaries are built before execution timing.
- GCC: `-O3 -std=c11`, with checked add/subtract/multiply builtins and explicit byte bounds.
- Rust: `-C opt-level=3 -C overflow-checks=yes -C panic=abort`; safe byte indexing/conversion.
- Ramos: default unoptimized 0.7 native backend; arithmetic, buffer and call-depth checks retained. Python integers stay within signed 64-bit range for these inputs. C/Rust can eliminate provably redundant checks; Python has no Ramos-style call-depth or byte arena limit. Limits are not reached by the suite.

Raw nanosecond samples, p10/p90, calibration probes, build commands, source hashes and compiler/environment versions are retained in [results.json](results.json).

## Startup probe (excluded from index)

Argument parsing and printing a supplied integer; median over 51 randomized launches.

| Ramos | C | Rust | Python |
|---:|---:|---:|---:|
| 0.309 ms | 0.667 ms | 0.843 ms | 17.585 ms |

## Builds and output size (excluded from index)

Median of three builds per task, including compiler startup and linking/publication. The table shows geometric means across tasks. It is not a general compiler throughput ranking: source sizes differ and C/Rust enable optimization while Ramos does not. Python is run as source and has no native binary in this experiment. Sizes are unstripped compiler outputs with different standard-library/linkage choices.

| Language | Build time | Native binary size | Source size |
|---|---:|---:|---:|
| Ramos | 2.142 ms | 8618 B | 750 B |
| C | 63.331 ms | 16616 B | 1547 B |
| Rust | 167.960 ms | 4506097 B | 925 B |
| Python | — | — | 475 B |

## Next work for Ramos

1. Profile the largest native gaps before adding an optimization pass: Insertion sort of 128 bytes (14.4× C time), Scan 16 KiB ASCII text (12.1× C time), 16×16 byte matrix multiplication (6.9× C time). Investigate buffer-access calls, stack temporaries and constant arithmetic. Preserve overflow/bounds diagnostics; remove checks only when proven redundant.
2. Compare each optimizer change against these exact work counts and compiler hashes, with fresh samples, language correctness tests and both self-hosting proofs.
3. Measure native Windows separately, then extend the suite with real file-processing programs. Keep syntax small while improving generated code.

![Overall index and task ratios](score.png)

## Environment

- CPU: Intel(R) Xeon(R) Platinum 8358 CPU @ 2.60GHz
- Platform: Linux-6.17.0-1020-oracle-x86_64-with-glibc2.39
- Ramos 0.7.0 — compiler written in Ramos; Linux and Windows x64
- gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- rustc 1.98.1 (48a229cea 2026-09-01)
- Python 3.12.3
- Ramos executable SHA-256: `ce7d20bda76c4f006f5ec57924169c8941de33a13ca598560d7624933d075a12`

## Reproduce

From the repository root on x86-64 Linux with GCC, Rust and Python:

```sh
make
python3 benchmarks/run_suite.py
```

Use `--validate-only` for output verification without timings. `--work-counts benchmarks/results.json` reuses the published work counts; `--output-dir` keeps results from another machine separate. Workload sources are in [fixtures/](../fixtures/). This is a custom Ramos suite, not a SPEC benchmark. The geometric mean follows [the established ratio aggregation method](https://open.spec.org/cpu2026/docs/runrules.html). See [GCC checked arithmetic](https://gcc.gnu.org/onlinedocs/gcc/Integer-Overflow-Builtins.html) and [Rust code generation settings](https://doc.rust-lang.org/rustc/codegen-options/index.html).

Historical results from a different machine and Ramos 0.2 are preserved in [report-0.2.md](../report-0.2.md) and [results-0.2.json](../results-0.2.json); they are not directly comparable to this suite.
