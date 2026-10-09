# Ramos 0.2

A native x86-64 Linux compiler written entirely in assembly. Ramos source uses
braces and `.ramos` files. The compiler emits instruction bytes and ELF executable
headers directly, with no delegated code-generation backend.

Version 0.2 adds signed 64-bit integers, checked arithmetic, local bindings,
assignment, and decimal printing. Conditions, loops, user-defined functions,
arguments, and file operations are subsequent milestones.

## Try it

Build the compiler with GNU binutils and Make, then run the calculator:

```sh
make
./ramos build examples/calculator.ramos -o calculator --force
./calculator
```

Output:

```text
Initial total:
60
Updated total:
100
Arithmetic:
20
-2
2
```

The hello example can also be compiled:

```sh
./ramos build examples/hello.ramos -o hello --force
./hello
```

Existing output requires `--force`. The compiler rejects destinations that refer
to the input, including hardlinks and symlink aliases. Failed builds preserve an
existing destination and remove their unpublished temporary output.

## Syntax

```text
fn main() {
    let price = 20
    var count = 3
    print(price * count)

    count = count + 2
    print("Updated total:")
    print(price * count)
}
```

- Exactly one parameterless `main` function.
- `print` accepts a string literal or integer expression and adds a newline.
- Integer expressions support `+`, `-`, `*`, `/`, `%`, unary `+`/`-`, and
  parentheses. Multiplication, division, and remainder bind more tightly than
  addition and subtraction. Binary operators at the same precedence associate
  left to right.
- Integers range from `-9223372036854775808` to `9223372036854775807`.
  `-9223372036854775808` is accepted as a directly negated literal; its positive
  magnitude cannot be used as an ordinary positive literal.
- `let` declares an immutable integer binding; `var` declares a mutable integer
  binding. Every binding must have an initializer. Types are inferred.
- Assignment is supported only for `var`. Names must be declared before use;
  duplicate declarations in `main` are errors. Identifiers use ASCII letters,
  underscores, and digits, with a letter or underscore first. Keywords are
  reserved. String-valued and boolean-valued bindings are not implemented.
- Separate statements with newlines; the final statement may directly precede
  `}`. Newlines after operators and opening parentheses are allowed. Semicolons
  and comments are not implemented.
- Input is UTF-8. String escapes are `\n`, `\t`, `\r`, `\"`, and `\\`.
- Empty bodies, empty strings, LF, and CRLF are supported.
- NUL bytes, malformed UTF-8, unsupported escapes, and raw newlines inside
  strings are rejected. Diagnostics contain filename, line, and byte column.

## Arithmetic behavior

Generated native instructions check signed overflow for addition, subtraction,
multiplication, and negation. Division truncates toward zero; a remainder has the
dividend's sign. Division or remainder by zero, and either operation on
`INT64_MIN` with divisor `-1`, fail explicitly.

A failed arithmetic operation writes a runtime diagnostic to stderr and exits
with status 1. It never silently wraps or depends on an unhandled CPU divide
fault. Successfully completed programs exit with status 0. Earlier output is
retained if a later operation fails.

## Build and test

GNU binutils (`as`, `ld`) and Make build the compiler. The source is GNU assembler
Intel syntax; these tools bootstrap the compiler itself. They are not needed
when the built compiler translates a `.ramos` file.

```sh
make
make calculator
make test
```

Python 3 is used only for the integration tests. The compiler has no libc,
LLVM, C implementation, or interpreter dependency. Actual generated programs
are executed in the tests, including arithmetic edge cases, binding semantics,
UTF-8 strings, large programs, file protection, and executable permissions.

Implementation files:

- `src/ramos.s`: CLI, input, UTF-8 validation, lexing, ELF headers, publication.
- `src/parsing.inc`: recursive-descent expressions, typed postfix IR, hashed
  local symbol table, and semantic checks.
- `src/codegen.inc`: bounded instruction encoding and relative-address fixups.
- `src/runtime.inc`: position-independent I/O, integer conversion, and errors.

The executable runs native instructions. Locals occupy stack slots; expressions
use balanced pushes and pops. Code is read/execute, string data is read-only,
and the stack is explicitly non-executable. No writable/executable load segment
or dynamic loader is needed.

## Current limits and next work

The compiler accepts readable regular files up to 1 MiB. Limits are 65,536
statements, 4,096 bindings, expression depth 128, 262,144 IR records, and 4 MiB
generated output. Complex programs may reach an IR or output limit before the
source-size limit. Standard input and device files are not supported.

```sh
./ramos --help
./ramos --version
```

Next: comparisons, conditions, loops, and functions, followed by CLI arguments
and files. Performance claims need repeatable workload benchmarks and later
optimization. Native code and assembly implementation alone do not establish a
speed advantage over mature languages.

Phase 2 focuses on memory ownership, bounds checks, further hardening, and
adversarial testing. Arithmetic checks and compiler bounds are already present.
Generated programs run with the caller's permissions; no sandbox is provided.
Games, web servers, and a separate browser target are later platform projects.

## Benchmarks

See [the measured 0.2 comparison](benchmarks/report.md) for Ramos, C, Rust,
and Python, including raw timings and reproduction instructions.
