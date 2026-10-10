# Ramos 0.5

A native x86-64 Linux compiler written entirely in assembly. Ramos source uses
braces and `.ramos` files. The compiler emits instruction bytes and ELF executable
headers directly, with no delegated code-generation backend.

Version 0.5 adds opaque byte buffers, string-valued expressions and checked
byte access. Buffers can be passed to functions, returned and printed. Version
0.4 typed functions and recursion, and 0.3 structured control flow remain.
The compiler is implemented in assembly; file I/O and compiler collections are
next on the [self-hosting roadmap](docs/self-hosting.md).

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

Install the compiler after building (the default prefix is `/usr/local`):

```sh
make install                         # use sudo if the prefix requires it
# Or install without root:
make install PREFIX="$HOME/.local"
```

The installed compiler needs no binutils or Python to compile Ramos programs.
Add your chosen prefix's `bin` directory to `PATH` if needed. Packaging may set
both `PREFIX` and `DESTDIR`.

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

- Exactly one parameterless `main` returning void is required. Other top-level
  functions may appear before or after it.
- `print` accepts a string literal, buffer, integer expression, or boolean expression
  and adds a newline. Booleans print as `true` or `false`.
- Integer expressions support `+`, `-`, `*`, `/`, `%`, unary `+`/`-`, and
  parentheses. Multiplication, division, and remainder bind more tightly than
  addition and subtraction. Binary operators at the same precedence associate
  left to right.
- Integers range from `-9223372036854775808` to `9223372036854775807`.
  `-9223372036854775808` is accepted as a directly negated literal; its positive
  magnitude cannot be used as an ordinary positive literal.
- `let` declares an immutable binding; `var` declares a mutable
  binding. Every binding must have an initializer. `int64`, `bool`, and `bytes` types
  are inferred and fixed for the lifetime of the binding.
- Assignment is supported only for `var`. Names must be declared before use;
  duplicate declarations in the same block are errors. Inner blocks may
  shadow outer names, and their bindings are invisible after the block ends.
  Identifiers use ASCII letters,
  underscores, and digits, with a letter or underscore first. Keywords are
  reserved. String-valued bindings hold mutable byte buffers.
- Separate statements with newlines; the final statement may directly precede
  `}`. Newlines after operators and opening parentheses are allowed. Semicolons
  and comments are not implemented.
- Input is UTF-8. String escapes are `\n`, `\t`, `\r`, `\"`, `\\`, and `\0`.
- Empty bodies, empty strings, LF, and CRLF are supported.
- Raw NUL source bytes, malformed UTF-8, unsupported escapes, and raw newlines inside
  strings are rejected. Diagnostics contain filename, line, and byte column.

## Booleans and control flow

```text
fn main() {
    var running = true
    var count = 0
    while running {
        count = count + 1
        if count == 5 {
            running = false
        } else {
            print(count)
        }
    }
    print(!running)
}
```

- `true` and `false` are distinct boolean literals; `!` negates a boolean.
- `<`, `<=`, `>`, and `>=` compare signed integers. `==` and `!=` compare
  two integers or two booleans. Mixing types is a compile-time error.
- From lowest to highest precedence: equality, ordering, addition/subtraction,
  multiplication/division/remainder, unary signs/`!`, and primary expressions.
  Operators at one level associate left to right. `1 < 2 < 3` is rejected;
  compare each pair in separate conditions. Arithmetic requires integers.
- `if condition { ... } else { ... }` and `while condition { ... }` require
  a boolean condition. `else` is optional and may follow on a new line.
  Branches use braces, including for a nested `if` in an `else` body.
- `while` reevaluates its condition before every iteration. `break` exits the
  innermost loop; `continue` reevaluates its condition. Both require a loop.
  `while true` runs until a `break` or a runtime failure; there is no implicit
  iteration limit. Code in skipped branches is type-checked but not executed.
- Bindings initialize whenever execution reaches their declaration. A shadowing
  initializer can refer to the outer binding. Blocks do not expose their locals.
- `&&`, `||`, `else if`, and `for` are not implemented.
  Separate statements with newlines, including after a compound statement.

Run `make control-flow` for a native Fibonacci/loop example.

## Functions

```text
fn factorial(n: int64) -> int64 {
    if n == 0 {
        return 1
    } else {
        return n * factorial(n - 1)
    }
}

fn main() {
    print(factorial(10))
    announce()
}

fn announce() {
    print("Functions work!")
}
```

Parameters require `int64`, `bool`, or `bytes` annotations and are immutable. A result
annotation is `-> int64`, `-> bool`, `-> bytes`, or `-> void`; omitting it means void.
Calls evaluate arguments left to right and require exactly matching types and
argument counts. Functions may call later definitions, themselves or each other.
A lexical binding can shadow a function name; that name then cannot be called.
`main` is the process entry and cannot be called by user code.

`return expression` must match the declared value type; bare `return` is for void
functions, including `main`. A value function must return on every statically
checked path. Both arms of an `if`/`else` may establish that guarantee. Loops are
checked conservatively, so even a `while true` needs a return after it for a
value function. Unreachable statements are still type-checked. Void calls may
be statements; value calls used as statements discard their result.

Every call has its own local frame. At most 64 Ramos calls may be active,
including `main`; attempting the next call reports a runtime error and exits 1.
Normal returns release the frame and restore the active-call counter. This
check assumes an ordinary Linux process stack; it cannot compensate for an
unusually small stack limit selected by the caller.

Run `make functions` for factorial, a digit classifier and a void helper.
See [the native calling convention](docs/functions.md) for compiler details.

## Byte buffers

```text
fn main() {
    let source = "let answer = 42"
    print(buffer_len(source))
    print(buffer_get(source, 0))
    buffer_set(source, 0, 76)
    print(source)
}
```

`buffer(length)` allocates zero-filled bytes. `buffer_len`, `buffer_get`, and
`buffer_set` provide length, checked reads, and checked writes. Indices count
bytes; reads return 0..255 and writes accept only that range. String literals
in expressions allocate fresh buffers. Bindings and function values alias their
buffer; `let` protects the binding while allowing content changes.

Buffers live until process exit in a bounded 16 MiB arena, with at most 1 MiB
payload per buffer. Descriptors and alignment count toward the arena limit.
Invalid sizes, indices, byte values or failed allocation report a runtime error
and exit 1. There is no freeing or resizing in this milestone. Direct string
literal printing avoids allocation. Run `make buffers` to scan stored source
text and return a buffer from a function. See [buffer semantics](docs/buffers.md).

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
make control-flow
make functions
make buffers
make test
```

Python 3 is used only for the integration tests. The compiler has no libc,
LLVM, C implementation, or interpreter dependency. Actual generated programs
are executed in the tests, including arithmetic edge cases, binding semantics,
UTF-8 strings, large programs, file protection, and executable permissions.

Implementation files:

- `src/ramos.s`: CLI, input, UTF-8 validation, lexing, ELF headers, publication.
- `src/parsing.inc`: recursive-descent expressions, typed postfix IR, hashed
  scoped local symbol table, and semantic checks.
- `src/codegen.inc`: bounded instruction encoding, relative-address fixups,
  and branch-label fixups.
- `src/functions.inc`: signature discovery, typed arguments, calls and returns.
- `src/function_codegen.inc`: private frames, argument copying and native calls.
- `src/runtime.inc`: position-independent I/O, integer conversion, and errors.
- `src/buffers.inc`: typed intrinsic lookup and argument checking.
- `src/buffer_codegen.inc`: buffer calls and mutable literal copies.
- `src/buffer_runtime.inc`: bounded allocation, byte access and buffer output.

The executable runs native instructions. Locals occupy stack slots; expressions
use balanced pushes and pops. Code is read/execute, string data is read-only,
and the stack is explicitly non-executable. No writable/executable load segment
or dynamic loader is needed.

## Current limits and next work

The compiler accepts readable regular files up to 1 MiB. Limits are 65,536
statements, 4,096 total declarations (including blocks that have ended),
expression depth 128, block depth 128 (including `main`), 262,144 IR records,
and 4 MiB
generated output. There are at most 256 functions, 16 parameters per function
and 64 active calls. The declaration limit includes all function parameters. Complex programs may reach an IR or output limit before the
source-size limit. Standard input and device files are not supported.

```sh
./ramos --help
./ramos --version
```

Next: CLI arguments, fallible file I/O, compiler collections and wrapping arithmetic. See the [bootstrap milestones](docs/self-hosting.md).
Performance claims need repeatable workload benchmarks and later
optimization. Native code and assembly implementation alone do not establish a
speed advantage over mature languages.

Phase 2 focuses on memory ownership, bounds checks, further hardening, and
adversarial testing. Arithmetic checks and compiler bounds are already present.
Generated programs run with the caller's permissions; no sandbox is provided.
Games, web servers, and a separate browser target are later platform projects.

## Benchmarks

The historical 0.2 results have not been remeasured for 0.5. The old benchmark
script requires a 0.2 compiler because its binary adapter uses that version's
entry layout; it rejects later versions before timing or modifying generated code. See
[the measured 0.2 comparison](benchmarks/report.md) for Ramos, C, Rust,
and Python, including raw timings and reproduction instructions.
