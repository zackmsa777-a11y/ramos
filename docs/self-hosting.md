# Ramos 0.11: self-hosting proved

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

Stage 0 is the retained assembly bootstrap with the new typed OS intrinsics.
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
inside that source. It provides checked arithmetic diagnostics, integer/boolean
printing, reclaimed values, string/aggregate operations, and native OS boundaries for arguments and file I/O.
The literal is instruction data, not an embedded compiler executable.

The runtime's assembly source remains in `bootstrap/src/runtime.inc`,
`buffer_runtime.inc`, `heap_runtime.inc`, `values_runtime.inc`, `io_runtime.inc`,
`text_runtime.inc`, `stdin_runtime.inc` and `source_guard.inc`. The proof verifies every embedded byte
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
compatible surface syntax while implementing the full 0.11 API and grammar itself. Tests
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
