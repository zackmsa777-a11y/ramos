# Historical Ramos 0.2 speed comparison

Measured locally on 2026-10-09 using the current Ramos 0.2 compiler. This is a specific microbenchmark, not a general ranking of language performance.

## Result

| Language | In-process calculation, median | CLI invocation, median |
|---|---:|---:|
| C | 7.28 µs | 2.98 ms |
| Rust | 8.45 µs | 3.21 ms |
| Ramos | 13.50 µs | 1.58 ms |
| Python | 316.25 µs | 36.98 ms |

On this workload Ramos is **23.4× faster than Python**. Ramos takes **1.85× the time of C** and **1.60× the time of Rust**.

The CLI result measures a different outcome: subprocess creation, loading, calculation, formatting, printing, and output capture. Python runs its approximately 98 KiB source script directly, so this timing also includes parsing and bytecode compilation on every launch. The native CLI binaries were built ahead of time. These numbers are not generic language startup times.

## Workload

Each calculation starts with seed 1 and performs 2,048 serial rounds of:

```text
x = (x * 1664525 + 1013904223) % 2147483647
```

Every CLI program prints the same checked result: `129317434`. The in-process kernels were also validated with seeds 2, 123, and 2,147,483,646 against an independently calculated reference.

The rounds are unrolled in all four languages because Ramos currently lacks loops and callable functions. This increases code size and is not a substitute for benchmarking ordinary loops, real CLI tools, games, or web applications.

## Measurement method

- Process pinned to logical CPU 2. CPU frequency scaling and unrelated system activity were not disabled.
- Clock: Python `time.perf_counter_ns`, reporting wall time.
- In-process measurements use 11 samples per language, with randomized language order and calibrated batches of at least about 80 ms.
- C, Rust, and Ramos share a native C repetition harness with indirect function calls and checksums. Python uses a Python repetition loop calling its precompiled function. These measurements include harness overhead; they are not individual CPU-instruction timings.
- Python parsing/bytecode compilation is excluded from the in-process table.
- Native entry arguments are opaque to C and Rust optimizers to prevent constant-folding the whole answer. Disassembly confirms live computation and repeated harness calls.
- CLI measurements use 101 samples per language, randomized order, five warmups, and stdout verification.

### How Ramos was called in process

The CLI executables are entirely unmodified. For the separate in-process test, the benchmark loads the code from a Ramos executable produced from the same arithmetic source without its final print. It changes the initial `x = 1` instruction into an argument load and replaces the Linux process-exit sequence with a return of `x`. Both patches preserve instruction offsets. All arithmetic instructions, overflow checks, division guards, local-variable accesses, and relative-address positions remain unchanged.

The loaded memory is initially read/write and then changed to read/execute before invocation. This harness adapter is benchmark infrastructure, not a feature added to Ramos. Its results should be described as a kernel derived from current Ramos-generated code.

## Compiler settings

- C: GCC `-O3 -std=c11`; explicit `__builtin_mul_overflow` and `__builtin_add_overflow` checks.
- Rust: `-C opt-level=3 -C overflow-checks=yes -C panic=abort`.
- Ramos: the existing 0.2 compiler, with its default native arithmetic checks and no optimizing pass.
- Python: ordinary integer arithmetic in CPython. All benchmark values fit signed 64 bits, so arbitrary-precision arithmetic does not change the result.

C and Rust optimize constant modulo into multiplication/shifts and eliminate provably redundant checks. Ramos currently uses general signed division, stack operations, and retained guards. This explains part of the observed gap and identifies useful optimization work.

Official references: [GCC optimization settings](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html), [GCC checked arithmetic builtins](https://gcc.gnu.org/onlinedocs/gcc/Integer-Overflow-Builtins.html), [Rust code-generation settings](https://doc.rust-lang.org/rustc/codegen-options/index.html#overflow-checks).

## Timing variation

| Language | Calculation p10–p90 | CLI p10–p90 |
|---|---:|---:|
| C | 7.27–7.29 µs | 2.70–3.42 ms |
| Rust | 8.44–8.61 µs | 2.93–3.71 ms |
| Ramos | 13.46–13.59 µs | 1.50–1.74 ms |
| Python | 312.75–326.92 µs | 35.30–40.83 ms |

## Preliminary build timings

These are medians of only three builds, in fixed language order. They include process startup and linking/publication, and use unusually unrolled source with different source sizes. They do not establish general compiler-throughput ratios.

| Language | Build median | Source size |
|---|---:|---:|
| C | 2702.80 ms | 313,626 bytes |
| Rust | 12394.83 ms | 100,502 bytes |
| Ramos | 4.25 ms | 90,145 bytes |
| Python | No ahead-of-time native binary built | 98,381 bytes |

## Environment

- CPU: AMD Ryzen 5 4600H with Radeon Graphics
- Platform: Linux-7.1.5-200.fc44.x86_64-x86_64-with-glibc2.43
- gcc (GCC) 16.1.1 20260515 (Red Hat 16.1.1-2)
- rustc 1.97.1 (8bab26f4f 2026-07-14) (Fedora 1.97.1-1.fc44)
- Ramos 0.2.0 — native assembly compiler
- Python 3.14.6

## Reproduce

From this repository root, with GCC, Rust, and Python installed:

```sh
python3 benchmarks/run_benchmark.py --compiler ./ramos --work-dir work/benchmark --output-dir work/results
```

For another checkout, pass `--compiler`, `--work-dir`, and `--output-dir`. The script generates the input programs, builds native code, checks outputs, runs timed samples, and writes `results.json`. Raw samples and compiler commands are retained there. The script generates all source fixtures.
