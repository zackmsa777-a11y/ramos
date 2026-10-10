# Ramos 0.7.1 optimization measurements

Ramos 0.7.1 executes these eight tasks **2.05× faster** than the saved 0.7.0 compiler (equal-weight geometric mean of median time ratios).

| Task | 0.7.0 ms | 0.7.1 ms | Speedup |
|---|---:|---:|---:|
| Serial integer arithmetic / modulo | 82.328 | 45.902 | 1.79× |
| Data-dependent branches | 102.195 | 56.226 | 1.82× |
| Euclidean GCD | 106.645 | 65.388 | 1.63× |
| Runtime-seeded recursive tree | 144.258 | 84.579 | 1.71× |
| Rolling byte-buffer hash | 108.727 | 60.181 | 1.81× |
| Insertion sort of 128 bytes | 560.437 | 232.730 | 2.41× |
| 16×16 byte matrix multiplication | 1188.954 | 474.920 | 2.50× |
| Scan 16 KiB ASCII text | 464.898 | 145.521 | 3.19× |

Within-run bootstrap 95% interval: 2.00–2.07×. It excludes machine/task-selection uncertainty.

Both compilers build the same source hashes and use the same work counts, seeds and independent reference outputs as the published baseline. Each pair has two verified warmups and 9 timed rounds with randomized old/new order on one pinned logical CPU. Every timed output is verified. The compiler hashes, binary hashes, ordering and raw samples are in [optimization.json](optimization.json). The host is the same shared Xeon Linux VM as the [four-language report](report.md). No Windows performance claim.

The old compiler is preserved by SHA-256 from the [0.7.0 baseline](baseline-0.7.0/results.json). This interleaved comparison gives stronger evidence for the change than comparing timings recorded in separate runs. The [current C/Rust/Python comparison](report.md) uses those same workloads, with fresh samples. This is an execution index, not a language-quality grade.

## Reproduce

```sh
git worktree add work/baseline-source v0.7.0
make -C work/baseline-source
make
python3 benchmarks/compare_versions.py --baseline-compiler work/baseline-source/ramos
```

See [instruction selection and correctness](../docs/optimization.md).
