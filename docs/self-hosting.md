# Ramos 0.18.1: self-hosting proved

The compiler implementation is [compiler/ramos.ramos](../compiler/ramos.ramos).
It reads source files, lexes and checks tokens, discovers typed signatures,
resolves scoped symbols, emits native x86-64 instructions, resolves labels,
writes ELF64 or PE32+ headers, and publishes the resulting executable. It does not
interpret Ramos, launch another compiler, or delegate machine-code generation.

## Reproduce from a clean checkout

On x86-64 Linux with GNU binutils, Make and Python 3:

```sh
make clean all selfhost
```

The actual compilation chain is:

```sh
as --64 -o build/stage0.o bootstrap/src/ramos.s
ld -z noexecstack --build-id=none -o build/stage0 build/stage0.o
./build/stage0 build compiler/ramos.ramos -o build/stage1 --force
./build/stage1 build compiler/ramos.ramos -o build/stage2 --force
./build/stage2 build compiler/ramos.ramos -o build/stage3 --force
cmp build/stage2 build/stage3
sha256sum build/stage2 build/stage3
```

Stage 0 is the retained assembly compiler seed with the audited native runtime.
It supports the compiler source subset; application grammar and new OS intrinsic
names are provided by the Ramos-written compiler.
Stages 1, 2 and 3 are compiled from the same Ramos compiler source. Stage 1 can
differ in instruction selection from stage 2; the required fixed point is
**stage 2 = stage 3**. `make all` copies stage 2 to the normal `ramos` executable.

The proof harness additionally runs stage 2 with `PATH=/nonexistent`, verifies
that its output still matches stage 3, and runs the language/I/O corpus (the retained seed skips post-0.7 grammar tests)
with stages 0, 2 and 3 (the Linux-only assembly bootstrap skips target selection).
It writes hashes and checks to `build/bootstrap-proof.json`.
The GitHub Actions workflow rebuilds this chain and preserves the report and
native compiler as artifacts. A local proof snapshot is in
[bootstrap-proof.json](bootstrap-proof.json); CI is the reproducible authority.

## Implementation boundary

The entire compiler pipeline is Ramos source, including the machine-code and
ELF/PE emitters. The private native runtime is represented as a hexadecimal literal
inside that source. It provides checked arithmetic diagnostics, integer/boolean/float
printing, reclaimed values, string/aggregate operations, and native OS boundaries for arguments and file I/O.
The literal is instruction data, not an embedded compiler executable.

The runtime's assembly source remains in `bootstrap/src/runtime.inc`,
`buffer_runtime.inc`, `heap_runtime.inc`, `values_runtime.inc`, `io_runtime.inc`,
`text_runtime.inc`, `stdin_runtime.inc`, `float_runtime.inc`, `source_guard.inc`,
`stream_runtime.inc`, `stream_os.inc` and `terminal_os.inc`. The proof verifies every embedded byte
and native entry offset against the bootstrap's emitted runtime. Retaining an
assembly OS boundary does not mean the Ramos compiler invokes assembly at run
time; once stage 1 is seeded, the next stages require no assembler or linker.

The compiler uses byte buffers as packed token, function, symbol, operator,
block and fixup tables. A bounded iterative expression parser and explicit block
stack avoid depending on the generated runtime's 64-call limit for deep syntax.
The compiler deliberately retains byte-buffer source so the old grammar can
seed it. User programs can use the new structs and typed arrays; no preprocessing
or host-language parser is required.

The self-hosted compiler has tighter token/output limits than the bootstrap,
which are documented in [compiler/README.md](../compiler/README.md). Diagnostics
preserve filename, line and byte-column formatting and give specific reasons.
Native behavior, traps, output preservation, scopes, calls and ELF permissions
are covered by the shared corpus.

## GitHub's language label

Self-hosting is a compiler property. GitHub's language sidebar is a separate
Linguist classification service; it does not yet include Ramos. See
[GitHub language recognition](github-language.md). The bootstrap and Python test
harness are retained honestly rather than relabeled as Ramos.

## Windows fixed point

The same Ramos source builds the Windows compiler. `make windows` produces
`build/ramos.exe`; `tools/windows_proof.py` compiles it twice on Windows and
requires identical seed/stage-2/stage-3 PE binaries. The CI Windows job runs
shared language tests and records the native Windows proof. See
[Windows bootstrap instructions](windows.md).

The retained assembly seed implements the 0.7 grammar. The compiler source uses
compatible surface syntax while implementing the full 0.18.1 API and grammar itself. Tests
for comments, short-circuit booleans and managed-value syntax run on stages 2/3 and native Windows;
the seed explicitly skips them. The proof JSON records both discovered counts
and these skips. No source preprocessing or external backend is required.

Version 0.9 extends the seed with the same five typed input/text intrinsics.
The Ramos compiler itself uses `int_to_text` for decimal diagnostics. These
contracts run on the retained seed as well as both self-hosted stages. Linux
and Windows runtime bytes, entry offsets and fixed points are audited.

Version 0.10 adds shared heap collection, audited value operations and checked
struct/array typing. The retained seed shares the heap but explicitly skips the
new syntax tests; the proof records that separate count.

Version 0.11 reads library graphs using the Ramos-written `load_sources` pipeline.
The retained seed supplies the private source-identity guard but skips weave/stdlib
tests; both self-hosted stages and native Windows run them.

Version 0.16 keeps formatting, previews and compile-and-run orchestration in
Ramos. The retained seed recognizes `stdout` and `_run_file` so it can compile
this source; its own CLI explicitly skips the 14 development-tool tests. Native
self-hosted stages and Windows run them. See [devtools.md](devtools.md).

Version 0.17 adds only Ramos-written text helpers and the rnumber example.
Its six shared acceptance tests run on native self-hosted stages and Windows;
the retained seed skips the unsupported weave/struct grammar.

Version 0.18 implements exact decimal-to-binary literal conversion in Ramos,
adds typed float code generation and embeds the shared SSE2/decimal runtime.
The compiler source itself stays within the seed grammar; the seed skips the
12 float application tests. Native self-hosted stages and Windows run them.
The independent Python references exist only in the test harness, never in the
compiler pipeline. See [math contracts and verification](math.md).

Version 0.18.1 adds ordinary Ramos-written decimal parsing and the rstats CLI
example. The seven math-input tests run on native self-hosted stages and
Windows; the retained seed skips the unsupported application grammar.
The compiler change is only its version string; native float runtime bytes
and code generation are unchanged. See [math-input.md](math-input.md).
