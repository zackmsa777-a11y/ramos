# From the assembly bootstrap to a Ramos-written compiler

Self-hosting means the Ramos compiler's implementation is Ramos source and a
Ramos compiler can compile that source. It is not achieved merely by compiling
native programs, or by launching the assembly compiler from Ramos.

## Current stage: 0.4 typed functions

The stage-0 compiler is implemented in assembly. It emits checked int64
arithmetic, typed booleans, comparisons, assignments and structured branches and
loops directly into static x86-64 Linux ELF executables. Version 0.4 adds typed
function parameters and returns, forward/mutual calls, independent frames,
return-path checks and a bounded active-call counter. Lexical block scopes,
bounded parsing and branch/call fixups are in place. No interpreter or delegated
code-generation backend is introduced.

## Remaining milestones

1. **Compiler data structures:** owned byte buffers and strings, arrays/slices,
   index bounds checks, checked allocation sizes and a defined lifetime model.
   Add explicit wrapping arithmetic for hashes without weakening checked default
   arithmetic. Define byte conversion and binary-output operations.
2. **CLI and file I/O:** arguments, fallible reads/writes, diagnostic stderr,
   exit status, safe destination publication and explicit error propagation.
   Acceptance example: read a `.ramos` file and write a binary with verified
   bytes, preserving existing output on failure.
3. **Stage 1 in Ramos:** port the lexer, parser, scoped symbol table, IR,
   instruction emitter and ELF writer module by module. Bootstrap its executable
   with the retained assembly stage 0. Run the existing end-to-end corpus against
   both implementations, including malformed input, resource limits, arithmetic
   traps and output-file protections.
4. **Bootstrap proof:** stage 0 builds the Ramos-written compiler (stage 1);
   stage 1 compiles the same compiler source (stage 2); stage 2 compiles it again
   (stage 3). Require stage-2/stage-3 executable equality under deterministic
   output, equivalent diagnostics and a green corpus with both compilers.
   Record build commands and hashes in CI before claiming self-hosting.

Keep stage 0 as a reproducible bootstrap and recovery path. Do not replace it
until native output, semantic parity, bounds checks and failure behavior pass.
The Phase 2 security roadmap in `design.md` applies to each new capability; this
function milestone does not yet expose arrays, pointers or user allocation.

The function milestone is complete. The next increment should define owned byte
buffers and bounds-checked byte access so a Ramos program can hold and scan
source text. File input/output then enables a first compiler implementation.
