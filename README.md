# Ramos 0.7.1 — self-hosted compiler for Linux and Windows

The Ramos compiler is now written in [Ramos](compiler/ramos.ramos). Its lexer,
parser, type checker, x86-64 instruction emitter and ELF/PE writers compile
native Linux and Windows executables directly. There is no interpreter or
delegated compiler backend.

**Self-hosting is verified:** the assembly bootstrap builds stage 1; stage 1
compiles the Ramos compiler into stage 2; stage 2 recompiles it into a byte-for-byte
identical stage 3. The complete test suite runs against stages 0, 2 and 3 in
[CI](https://github.com/zackmsa777-a11y/ramos/actions/workflows/selfhost.yml).

```sh
make                         # build the self-hosted compiler as ./ramos
make selfhost                # compare stages, run tests, record SHA-256 proof
./ramos --version
```

Version 0.7.1 optimizes constant arithmetic, stack transfers and checked buffer
accesses without changing language syntax. See [the emitter changes](docs/optimization.md)
and the [separate practicality goal](docs/next-goal.md).

Version 0.7 adds native Windows executables, a Windows-native self-hosted compiler,
and `--target linux|windows` selection. See [Windows instructions](docs/windows.md).
Version 0.6 added command-line arguments, fallible binary file I/O, diagnostic
stderr and explicit exit status. It retains the byte buffers from 0.5, typed
functions and recursion from 0.4, and structured control flow from 0.3.
The small native OS runtime is embedded as instruction data; its assembly
source and the original compiler are retained under `bootstrap/` for auditing
and recovery. Python is only a test/proof harness.

The language keeps its core rules: **simple syntax and fast native execution**.
New performance claims require measurements; native output alone is not a benchmark.

GitHub's language sidebar cannot yet name Ramos because it is absent from
Linguist's registry. This repository keeps real `.ramos` sources and documents
[what is needed for GitHub recognition](docs/github-language.md).

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

## Windows

On Windows, download the native [ramos.exe](https://github.com/zackmsa777-a11y/ramos/releases/download/v0.7.0/ramos.exe):

```powershell
.\ramos.exe build .\hello.ramos -o .\hello.exe
.\hello.exe
```

From Linux, cross-compile directly:

```sh
./ramos build examples/hello.ramos -o hello.exe --target windows
make windows                 # native Windows compiler: build/ramos.exe
```

Windows is the default target for the Windows compiler; Linux is the default for
the Linux compiler. Both can select either target explicitly. See
[Windows setup, runtime and self-hosting](docs/windows.md).

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

## Build, test and self-host

The initial bootstrap needs x86-64 Linux, GNU binutils and Make. Python 3 runs
integration tests and writes the proof report. Once built, `ramos` needs none of
these tools to compile programs or rebuild itself.

```sh
make clean all selfhost
make demo calculator control-flow functions buffers
make test
```

`make all` installs stage 2 as `./ramos`. `make selfhost` verifies that stage 2 and
stage 3 match, runs the corpus against stages 0, 2 and 3, verifies the embedded
runtime against its bootstrap source, and writes `build/bootstrap-proof.json`.
It also recompiles with an empty tool `PATH` and requires the same output.
See [the bootstrap commands and implementation boundaries](docs/self-hosting.md)
and [the compiler layout](compiler/README.md).

Implementation:

- `compiler/ramos.ramos`: complete compiler pipeline and embedded runtime bytes.
- `bootstrap/src/`: original assembly compiler plus OS intrinsics used to seed stage 1.
- `tools/bootstrap_proof.py`: reproducibility and corpus harness; no compilation logic.
- `tests/`: native end-to-end language, file I/O and malformed-input tests.

Generated programs are x86-64 Linux ELF or Windows PE32+ executables. Code is read/execute,
string data is read-only, buffer mappings are read/write, and the stack is
non-executable. No region is both writable and executable. Linux output is static; Windows
uses system DLLs with NX/ASLR protections and requires no C runtime.

## Arguments and file I/O

```text
fn main() {
    if arg_count() != 3 {
        stderr("usage: copy INPUT OUTPUT\n")
        exit(1)
    }
    let content = read_file(arg(1))
    if io_error() != 0 {
        stderr("cannot read input\n")
        exit(1)
    }
    if write_file(arg(2), content, 0) != 0 {
        stderr("cannot write output\n")
        exit(1)
    }
}
```

`arg_count()` includes the executable name at `arg(0)`. Reads and writes are
fallible; `io_error()` reports the last file operation's negative error status
(or zero). `read_file` returns an empty buffer on failure, so check the status
before interpreting an empty result. `write_file` publishes atomically and
returns zero or negative errno. Flags are 0 for a new ordinary file, 1 for a new
executable, 2 for replacement, and 3 for replacement with executable permissions.
`platform()` identifies the host (0 Linux, 1 Windows). Windows maps failures to
common negative statuses and accepts the executable flag without POSIX modes.
It refuses to replace the most recent successfully read file or an alias of it,
including with replacement enabled. See [the I/O contract](docs/io.md).

## Current limits and next work

The self-hosted compiler accepts regular source files up to 1 MiB, at most 50,000
tokens including EOF, 4,096 total declarations including parameters and ended
blocks, 256 functions and 16 parameters per function. Expression and block
depth remain bounded at 128; generated programs allow 64 active calls.
Its output and decoded string-data arenas are each 1 MiB; labels and fixups each
have a 40,000-entry bound. These are checked limits. The retained bootstrap has
the older 4 MiB output and IR limits. See [compiler representation limits](compiler/README.md).

The compiler is self-hosted; imports, richer collections, wrapping arithmetic,
broader optimization and additional targets remain future work. Performance claims need
new repeatable measurements. The runtime provides checked arithmetic and bounded
buffers, but generated programs execute with the caller's operating-system
permissions. Games and browser support need further platform work.

## Benchmarks

The Ramos 0.7.0 baseline has a reproducible eight-task comparison with optimized checked C,
Rust and CPython. On the recorded Linux VM, the execution index is **Ramos 19.93,
C 100, Rust 119.04 and Python 2.53** (higher is faster). Ramos is **7.89× faster
than Python** across this suite and takes **5.02× C's time**. These are geometric
means of per-task median ratios, not a general language ranking.

The suite checks outputs against independent references, runs nine randomized
samples per task, and records raw timings, build commands and source hashes.
Startup and build times are reported separately. See the
[full report and methodology](benchmarks/report.md), [raw samples](benchmarks/results.json)
and [workload sources](benchmarks/fixtures/).

```sh
make
python3 benchmarks/run_suite.py                 # measure all eight tasks
python3 benchmarks/run_suite.py --validate-only # output checks without timing
```

![Ramos 0.7 execution index](benchmarks/score.png)

The [historical 0.2 comparison](benchmarks/report-0.2.md) used another machine
and one unrolled workload; it is not directly comparable. Its legacy script
still requires the 0.2 compiler and writes to `work/results-0.2` by default.
