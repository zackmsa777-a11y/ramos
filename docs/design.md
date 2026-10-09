# Ramos: proposed language and compiler design

Status: phase 1A and the first integer/binding portion of phase 1B are implemented
as Ramos 0.2. Broader CLI features and phase 2 remain roadmaps. See
`ramos/README.md` for the working compiler.

## Intent and agreed constraints

Create a language with simple brace-based syntax, very fast execution as a goal, and source files ending in `.ramos`. Build the compiler and its components from scratch in assembly. An existing assembler is allowed to bootstrap the compiler. Long-term applications include command-line tools, games, and websites. Phase 2 focuses on security.

Implementation choices: Ramos is the language name; “very fast” means program execution speed, with compiler speed also measured; x86-64 Linux is the first target.

## Approach

The compiler is written in x86-64 assembly and built with GNU `as` and `ld`, which were already installed. This replaces the originally proposed NASM bootstrap. These are bootstrap tools: generated Ramos programs do not require them. The compiler emits instruction bytes and ELF executable headers itself, without delegating code generation to a C compiler, LLVM, an external assembler, or an external linker.

The first compiler and its generated programs use Linux system calls directly. Linux supplies the process loader and operating-system interfaces. Building an operating system or replacing CPU hardware is outside this project.

Separate lexing, parsing, semantic checking, code generation, and executable emission. This is more work than a compiler that generates instructions while parsing, but gives errors and optimization a clear home. Initially emit straightforward correct code; measure optimizations against that baseline.

## Phase 1A: first executable

Input file: `example.ramos`.

```text
fn main() {
    print("Hello, Ramos!")
}
```

Proposed interface:

```sh
ramos build example.ramos -o example
./example
```

Supported grammar:

- Exactly one parameterless `fn main()` declaration with a brace-delimited body.
- Zero or more `print("literal")` statements.
- No semicolons. A newline or closing brace terminates a statement.
- Spaces, tabs, and LF or CRLF newlines between tokens.
- String escapes: `\n`, `\t`, `\r`, `\"`, and `\\`. Unknown escapes are errors.
- Source is UTF-8. The initial identifier and keyword set is ASCII; string content must contain valid UTF-8 and is emitted without normalization.
- Raw newlines inside string literals are errors; use supported escapes for line breaks. NUL bytes anywhere in source are errors. Comments are not supported in this milestone.
- Empty strings and an empty main body are valid.
- `print` writes the string followed by a newline. A normally completed program exits with status 0.

The first milestone implements no imports, user-defined parameters, arithmetic, mutable variables, or networking. Unsupported syntax produces an error, rather than being ignored.

## Compiler architecture

1. **Input and CLI:** validate arguments, read source, handle operating-system failures, and reject unsupported input sizes. The first source-size limit is 1 MiB.
2. **Lexer:** produce tokens with line and column locations; validate strings and escapes. Report columns as one-based byte positions and document this convention.
3. **Parser:** build a small syntax tree for the entry function and print statements; reject unexpected tokens and trailing source.
4. **Semantic validation:** the initial parser enforces the entry point and supported operations before output generation. A separate type checker comes with typed features.
5. **Code generator:** encode the x86-64 instructions for string output and process exit. Use explicit records for code offsets and data references.
6. **Executable writer:** resolve internal references and write a static ELF64 executable with separate executable and writable memory permissions; request a non-executable stack. No dynamic loader or shared-library dependency is required.
7. **Runtime:** implement process I/O and exit using assembly routines. Handle partial writes and interrupted writes; report unrecoverable failures with a nonzero exit status.

Use bounded allocations and checked size arithmetic within the compiler from the first milestone. The compiler keeps allocations in arenas that it releases when compilation finishes. Phase 1A uses a flat grammar to avoid recursive parsing of user expressions.

Validate the full input before creating the final executable. Open the destination directory and use a short independent temporary basename within it, set executable permissions, and rename it only after successful generation. Remove temporary output on failure. Replacing an existing destination requires `--force`; source and destination must not refer to the same file.

Errors identify the source filename, line, column, and cause when applicable. A failed build returns a nonzero status. Keep diagnostic text separate from normal program output.

## Phase 1B: useful CLI language

Implemented in 0.2: signed 64-bit literals, native checked `+`, `-`, `*`, `/`, `%`,
unary signs, parentheses, decimal integer printing, immutable `let`, mutable
`var`, and assignment. Addition, subtraction, multiplication, and negation
overflow produce runtime errors. Division truncates toward zero; zero divisors
and `INT64_MIN` divided or reduced modulo `-1` produce runtime errors. The
compiler rejects undeclared names, duplicate bindings, and assignment to `let`.
It uses a bounded hashed symbol table, typed postfix IR, checked emission,
relative-address fixups, and native stack slots. Boolean values are future work.

Expand in small, independently verified milestones:

1. Signed 64-bit integers, booleans, arithmetic, and printing integers.
2. Immutable `let` bindings and mutable `var` bindings, with inferred local types.
3. Conditions and loops.
4. Functions with explicit parameter types and declared return types.
5. Command-line arguments, owned strings, file operations, and collections.

Static checking begins with the first typed features. The first arithmetic milestone must specify overflow, division by zero, and signed division edge cases before implementation. The string and collection milestone must specify allocation, ownership, lifetimes, and index behavior before implementation. Runtime checks and memory rules required for correctness are part of those milestones, even though phase 2 adds broader security work.

Optimize only after functional behavior and baseline measurements are established. Candidate improvements include constant folding, fewer redundant loads, and register allocation. Every optimization must preserve the specified behavior and relevant safety checks.

## Performance goals and evidence

Native machine-code output is a design choice, not a guarantee of exceptional performance. Assembly as the compiler implementation language does not determine generated-program speed.

Measure executable startup, integer computation, memory allocation, text processing, and file processing once the required features exist. Also measure compiler throughput and peak memory usage. Include correctness checks, repeatable inputs, multiple runs, and equivalent work when comparing implementations. Record hardware and build settings with results.

Phase 1A succeeds by producing correct standalone executables. A performance claim requires later benchmark results; no numerical performance guarantee is part of this draft.

## Phase 2: security

Security here means hardening the compiler and language runtime, with safer default behavior. It does not promise that every application is secure or provide a sandbox for generated executables.

The phase 2 design will address:

- Bounds checks for arrays, strings, and slices.
- Memory lifetime and ownership rules, or another explicitly defined memory-management model, before exposing user-controlled references.
- Checked allocation sizes, allocation failures, and resource exhaustion.
- Defined integer overflow behavior and explicit operations where wrapping is intended.
- Structured errors for fallible operations; no silently ignored file or network errors.
- No unchecked pointers in the default safe language subset.
- Fuzzing and malformed-input tests for lexing, parsing, semantic checking, and binary generation.
- Limits for input size, nesting, token counts, and output sizes as the grammar grows.
- Preservation of executable memory protections during optimization and feature expansion.

Each item must become a concrete design and testable requirement when its feature is introduced. Package signing, a package repository, sandboxing, and application authentication are separate projects if requested later.

## Games and websites

After a useful CLI compiler, add graphics, input, audio, and predictable allocation behavior for games. Use operating-system and graphics interfaces with routines we write.

For web servers, implement networking and HTTP support in later scoped projects. Browser applications need a separate target, such as our own WebAssembly emitter, plus bindings to browser APIs. An x86-64 Linux executable alone is not browser support.

New CPU architectures and operating systems require additional code generation and platform layers. They are not part of the first milestone.

## First-milestone acceptance criteria

- Assemble and link the compiler successfully with GNU `as` and `ld`.
- Compile the example and execute the generated program on x86-64 Linux.
- Confirm output is exactly `Hello, Ramos!` followed by a newline, with exit status 0.
- Verify empty bodies, multiple prints, escaped strings, UTF-8 string content, and LF/CRLF source.
- Inspect the emitted ELF file: correct architecture and entry point, sensible segments, no dynamic-loader requirement, no writable/executable load segment, and a non-executable stack request.
- Verify errors for malformed strings, invalid UTF-8, missing delimiters, duplicate entry functions, unsupported constructs, trailing tokens, and oversized source.
- Verify missing input, invalid output paths, existing-output protection, and source/destination identity checks.
- Verify failed builds preserve any existing destination and remove temporary output.
- Exercise large accepted inputs and repeated builds to detect size, offset, and allocation mistakes.

## Next milestone

Add comparison operators, boolean conditions, `if`/`else`, and `while` loops.
Specify branching, block scope, and runtime behavior before extending the native
instruction emitter. Keep CLI support first, performance evidence concrete,
and phase 2 security work explicit.
