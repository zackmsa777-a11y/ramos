# Ramos 0.17 text assembly measurement

This is a single Linux workload comparing two Ramos APIs, not an overall
language index or a comparison with C, Rust or Python. Both variants use the
same compiler and checked language semantics, append the same 64-byte ASCII
piece, and verify complete result content against `text_repeat` before exiting.

Measured 2026-10-11T02:59:20.997473+00:00 on Intel(R) Xeon(R) Platinum 8358 CPU @ 2.60GHz.
The elapsed time includes process startup and content verification; one warmup
and five measured runs alternate variant order. Medians are shown below.

| Appends | Result bytes | Repeated += (ms) | Builder (ms) | Ratio |
| --- | --- | --- | --- | --- |
| 1024 | 65536 | 16.046 | 1.884 | 8.52× |
| 2048 | 131072 | 26.947 | 3.641 | 7.40× |
| 4096 | 262144 | 72.015 | 6.397 | 11.26× |
| 8192 | 524288 | 287.006 | 13.787 | 20.82× |

On this machine, at 8192 appends / 512 KiB, the builder took about 13.8 ms versus
287 ms for repeated concatenation (20.8×). This result supports avoiding repeated
prefix copies in text assembly; it does not establish a universal speedup or
native Windows timing. The container was not CPU-isolated; raw timing variability
is retained in [text-builder.json](text-builder.json), along with machine and
compiler/library hashes. Historical 0.14 cross-language measurements are separate.

Reproduce on Linux from this version's checkout:

```sh
make
python3 benchmarks/text-builder/run.py --output build/text-builder-results.json
```

[Concat source](../text-builder/concat.ramos), [builder source](../text-builder/builder.ramos).
