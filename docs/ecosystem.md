# Ramos project hub

Ramos is one language project with five focused repositories, under the same
owner. They share the [`ramos` GitHub topic](https://github.com/topics/ramos).
The source repository keeps its existing name, releases and download URLs;
the book keeps its existing Pages URL. No organization transfer is required.

| Repository | Role | Work here |
| --- | --- | --- |
| [ramos](https://github.com/zackmsa777-a11y/ramos) | Source | Compiler, runtime, standard library, tests and language releases |
| [ramos-docs](https://github.com/zackmsa777-a11y/ramos-docs) | Book | Canonical Markdown and generated human-readable HTML |
| [ramos-examples](https://github.com/zackmsa777-a11y/ramos-examples) | Examples | Small runnable programs and portable application patterns |
| [ramos-calculator](https://github.com/zackmsa777-a11y/ramos-calculator) | Showcase | Scientific calculator: shared native CLI, REPL and desktop GUI |
| [ramos-benchmarks](https://github.com/zackmsa777-a11y/ramos-benchmarks) | Benchmarks | Four-language workloads, raw results and historical performance evidence |

## Start using Ramos

1. Download a native compiler from the
   [0.19.1 release](https://github.com/zackmsa777-a11y/ramos/releases/tag/v0.19.1).
2. Read the [HTML book](https://zackmsa777-a11y.github.io/ramos-docs/), or the
   [Markdown agent guide](https://github.com/zackmsa777-a11y/ramos-docs/blob/main/book/16-agent-guide.md).
3. Clone [examples](https://github.com/zackmsa777-a11y/ramos-examples) for small
   programs, or [calculator](https://github.com/zackmsa777-a11y/ramos-calculator)
   for a larger application with CLI and real desktop interfaces.
4. Use [benchmarks](https://github.com/zackmsa777-a11y/ramos-benchmarks) to validate
   workloads before making measured performance claims.

The calculator's expression parser and bounded scientific functions are written
in Ramos. Python in the application repositories is setup/test tooling only;
compiled programs run natively. Linux GUI needs GTK3 and a display; Windows
uses native system controls. Read each repository's commands and limits.

## Ownership and compatibility

- Compiler/runtime/stdlib changes and self-hosting proofs belong here in `ramos`.
- Book chapters belong in `ramos-docs/book/`; regenerate the HTML from Markdown.
- New independent examples belong in `ramos-examples`.
- Calculator features and end-to-end app tests belong in `ramos-calculator`.
- Benchmark fixtures, future measured reports and methodology belong in
  `ramos-benchmarks`.

The new repositories begin with source pinned to **0.19.1**, commit
`6c263c5023bc8a71c036d9b8151b82dc558adfde`. Each `upstream.json` records copied
files and SHA-256 hashes. Standard-library copies are reviewed snapshots; the
source repository remains authoritative. A compiler upgrade requires reviewing
contracts, updating the pin/snapshot together and running that repository's checks.

This is an additive split. Existing `examples/` and `benchmarks/` paths here
remain release/test snapshots, because compiler validation, release packaging
and historical links still consume them. Historical reports keep their original
version/machine labels; copying a report is not a new measurement. Future
upstream release fixtures can still be synchronized deliberately.

Rollback means returning to the retained source/book paths and removing the
new hub links. There is no rewritten Git history, deleted old tree, renamed
release asset or transferred owner to undo. Retiring legacy paths would be a
separate migration after their build/release consumers have been updated.

## Project rules

Keep programming simple. Keep runtime code native. Preserve checked arithmetic
and fallible I/O. Measure speed before claiming it. Shared ownership and copies
of this project's examples do not count as independent language adoption.

[ecosystem.json](ecosystem.json) provides the same repository map for tooling.
