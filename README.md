# Ramos 0.25.1 preview — self-hosted compiler for Linux and Windows

The Ramos compiler is now written in [Ramos](compiler/ramos.ramos). Its lexer,
parser, type checker, x86-64 instruction emitter and ELF/PE writers compile
native Linux and Windows executables directly. There is no interpreter or
delegated compiler backend.

## Ramos project family

| Repository | Purpose |
| --- | --- |
| [ramos](https://github.com/zackmsa777-a11y/ramos) | Compiler source, runtime, standard library and releases |
| [ramos-docs](https://github.com/zackmsa777-a11y/ramos-docs) | Markdown book for agents and readable HTML for people |
| [ramos-examples](https://github.com/zackmsa777-a11y/ramos-examples) | Small runnable programs and terminal projects |
| [ramos-calculator](https://github.com/zackmsa777-a11y/ramos-calculator) | Scientific calculator with native CLI, REPL and Linux/Windows GUI |
| [ramos-benchmarks](https://github.com/zackmsa777-a11y/ramos-benchmarks) | Reproducible benchmarks and historical raw evidence |

Visit the [project hub](docs/ecosystem.md) or browse the shared
[`ramos` topic](https://github.com/topics/ramos). Existing release assets and
source/book URLs stay available. Application repos pin their compiler and stdlib.

**Self-hosting is verified:** the assembly bootstrap builds stage 1; stage 1
compiles the Ramos compiler into stage 2; stage 2 recompiles it into a byte-for-byte
identical stage 3. The full test suite runs against self-hosted stages 2 and 3; the retained
assembly seed runs its supported grammar subset in
[CI](https://github.com/zackmsa777-a11y/ramos/actions/workflows/selfhost.yml).

```sh
make                         # build the self-hosted compiler as ./ramos
make selfhost                # compare stages, run tests, record SHA-256 proof
./ramos --version
```

Version 0.25 adds **explicit GUI scaling**: `gui_open_scaled` uses logical
coordinates, `gui_dpi` reports native DPI, and event kind 6 reports a change.
Windows opts into per-monitor-v2 awareness and scales control boundaries, fonts
and canvas rendering; Linux follows GTK's native widget scale. Existing
`gui_open` keeps its policy. See [scaling contracts and Windows test commands](docs/gui-scaling.md)
and the [DPI demo](examples/scaling.ramos). The user-reported native Windows sequence
144 → 168 → 96 passed events/input/shutdown, but captures showed broken canvas
shapes; visual acceptance and the unavailable 200% preset remain unverified. Bounded resource probes
exercise 200 MiB of allocation churn; the 16 MiB live heap budget is unchanged.
Native baseline proofs pass **300 Linux tests and 241 Windows tests**, with matching
compiler fixed points. See [verification](docs/gui-scaling-verification.json).
The 0.25.1 repaint candidate completes child placement before requesting full
parent/child redraws. A real Windows visual retest is still required.
No new performance score.

Version 0.24 adds **exact scientific and compact numerical output** in the Ramos
math library. `math_scientific(value, places)` selects fractional mantissa digits;
`math_format(value, digits)` selects significant digits and preserves tiny values.
Seventeen significant digits round-trip finite binary64 values, including signed
zero. Fixed-decimal `math_text` and `print` keep their existing behavior.
Validation passes **297 Linux tests and 238 native Windows tests**, with both
compiler fixed points. See [output contracts](docs/math-output.md) and
[verification](docs/math-output-verification.json). No new syntax or speed claim.

Version 0.23 adds a **native drawing library**: reusable canvas commands for
lines, rectangles, circles and pixels on Linux and Windows. Displayed frames
remain stable when the app resets its buffer or garbage collection runs.
The [interactive plot](examples/plot.ramos) changes curves with a button and
redraws on resize. See [drawing contracts](docs/canvas.md).
Validation passes **293 Linux tests and 234 native Windows tests**, with both
compiler fixed points, native displayed pixels, snapshot/GC/resource checks,
and GTK at 1× and 2× scale. See [verification](docs/canvas-verification.json).
Explicit DPI policy is added in 0.25; Windows canvas transition acceptance remains incomplete. No new graphics-speed claim.

Version 0.22 adds **checked deeper recursion**: up to 1,024 active calls,
with a separate 4 MiB stack budget checked before each local frame allocation.
The scientific calculator uses it for 64 expression levels with recoverable
limit errors. Static Windows UTF-16 constants are now explicitly aligned,
and the Linux GUI harness reads complete Xvfb announcements. See the
[stack policy](docs/stack-budget.md) and [compatibility guidance](docs/compatibility.md).
Validation passes **289 Linux tests and 230 native Windows tests**, with both
compiler fixed points. See [verification](docs/recursion-verification.json) and
[fresh eight-task measurements](https://github.com/zackmsa777-a11y/ramos-benchmarks/blob/main/benchmarks/0.22.0/report.md).
Native installation checks exercise Unicode paths, an empty PATH, argument
and exit-status forwarding, and executables running without compiler/library files.

Version 0.21 adds **collection capacity and release controls** in the Ramos
standard library: reserve list/map storage, handle full collections with explicit
statuses, clear map references, release owned arrays and sort integer lists
without recursion or auxiliary arrays. The native `rsort` CLI sorts signed
integers from stdin or a streamed file. See [contracts and commands](docs/collections.md).
Existing list/map APIs remain available; live memory and array limits stay checked.
Validation passes **285 Linux tests and 225 native Windows tests**, with both
compiler fixed points. See [verification](docs/collections-verification.json) and
[measured collection evidence](https://github.com/zackmsa777-a11y/ramos-benchmarks/blob/main/benchmarks/0.21.0/collections/report.md);
reservation is not presented as an established speed gain.

Version 0.20 adds **native monotonic timing** for Linux and Windows:
`monotonic_ms()` supports elapsed-time animation and frame deadlines without
terminal/GUI setup or managed allocations. The rmatrix port uses changed-cell
rendering, cached HUD text and idle pause handling. Its workload measurements
are documented separately; this is not a new general language speed index.
See [timing contracts](docs/timing.md), [verification](docs/timing-verification.json)
and the [rmatrix project](https://github.com/zackmsa777-a11y/ramos-examples/tree/main/projects/rmatrix).
Validation passes **278 Linux tests and 218 native Windows tests**, with matching
compiler fixed points on both targets.

Version 0.19.1 adds **simple GUI layout and native file pickers** on Linux and
Windows. Use checked row/column/padding helpers and `gui_open_file` /
`gui_save_file` to choose paths with explicit success, cancellation and error
statuses. Notes now opens UTF-8 files and offers Save As while preserving its
exclusive save policy. See [API and examples](docs/gui.md) and
[release verification](docs/gui-dialogs-verification.json). Validation passes
**276 Linux tests and 216 native Windows tests**, with both compiler fixed points.

Version 0.19 adds **Linux desktop GUI support** through GTK3. The same Notes
source now runs on Linux and Windows: Unicode editing, native controls, colored
panels, resize events and atomic exclusive file saves. Use `ramos run app.ramos
--gui`, or build a distributable executable with `--gui`. Linux GUI apps require
GTK3 and a display. Its milestone validation passed **271 Linux tests and 212 native Windows
tests**, with both compiler fixed points. See [0.19 evidence](docs/portable-gui-verification.json).
The Linux compiler and ordinary Linux CLI programs remain
static; Windows programs still require no C runtime. See [GUI setup, API and limits](docs/gui.md).

Version 0.18.1 adds **fallible decimal input** in the Ramos math library. Parse
signed decimal/scientific text into a typed value/status result with exact
binary64 rounding. `rstats` computes summaries from stdin or streamed files.
The parser adds no syntax or native dependency. See [APIs and commands](docs/math-input.md).
Validation passes **265 Linux tests and 211 native Windows tests**, with matching
compiler fixed points. See [0.18.1 evidence](docs/math-input-verification.json).

Version 0.18 added **native float64 and essential math**: decimal/scientific literals,
finite checked arithmetic, explicit integer conversions, square root and exact
fixed decimal formatting. Floats work in functions, structs and arrays. The new
`math.ramos` library and Mandelbrot image renderer run on Linux and Windows.
See [semantics and runnable commands](docs/math.md). Its milestone validation passed
**258 Linux tests and 204 native Windows tests**, with matching compiler fixed
points and independent numerical reference checks. See [math evidence](docs/math-verification.json).

Version 0.17 adds **reusable UTF-8 text builders** to `stdlib/text.ramos`:
append pieces, take immutable snapshots, clear for reuse or release capacity.
`rnumber` numbers streamed text files with one reusable builder. No new syntax
or native dependency is needed. See [API and ownership](docs/text-builder.md).
Its milestone validation passed **246 Linux tests and 192 native Windows tests**, with
matching compiler fixed points. See [0.17 evidence](docs/text-builder-verification.json).

Version 0.16 added **easier development**: source-line/caret diagnostics with
specific type names, `ramos fmt` and `ramos run`. Run a source file directly with
arguments and inherited I/O; format a copy or check formatting in CI. All three
tools are native and written in Ramos. See [commands and contracts](docs/devtools.md).
Its milestone validation passed **240 Linux tests and 186 native Windows tests**,
with matching compiler self-rebuilds on both platforms. See
[0.16 evidence](docs/devtools-verification.json).

Version 0.15 added **native CLI OS libraries**: streamed directory iteration,
exclusive directory creation, path helpers, environment lookup and direct child
execution. `rfind` searches a directory tree; `rrun` passes argument values and
reports child exit status. Both run on Linux and Windows with fallible OS errors.
See [the contracts and examples](docs/system.md). Its milestone validation passed
226 Linux tests and 172 native Windows tests with both compiler fixed points.

Version 0.14 adds **easier application syntax**: `else if`, end-exclusive
`for i in 0..n`, and `+=`/`-=`. Bounds and destinations evaluate once; integer
operations stay checked. The file-search example uses the new syntax while
preserving output and exit behavior. See [the exact contracts](docs/syntax.md)
and [the runnable example](examples/easier_syntax.ramos). Native validation passes
**209 Linux tests and 155 Windows tests**, with both byte-identical compiler
fixed points retained.

Version 0.13 adds a **Windows desktop GUI library**: real windows, labels,
buttons, Unicode text inputs/editors, colored panels and resize/input events.
`--gui` builds an executable that launches without a console. The bundled
[Ramos Notes app](examples/notes.ramos) edits and saves UTF-8 text with native
controls. No external GUI toolkit or Python runtime is needed. Linux can
cross-compile GUI apps; Linux startup returned `-38` in that release.
The 0.19 Linux backend requires `--gui` and GTK3. Validation passes **194 Linux tests and 140 native Windows tests**,
with both self-hosting fixed points retained. See [the GUI library and commands](docs/gui.md).

Version 0.12 adds **streamed file I/O and terminal interfaces**. Build native
copy/search tools that process files larger than 1 MiB, and a colored, full-screen
file viewer with keyboard navigation. New Ramos libraries cover I/O, CLI helpers
and TUI layout/input. Validation passes **190 Linux tests and 134 native Windows
tests**, including real terminal/console interaction. Both self-hosting fixed
points match. See [the APIs and runnable tools](docs/cli-tui.md).

Version 0.11 adds **`weave "library.ramos"`** and a small standard library
written in Ramos: number/text/byte helpers, growable integer lists and string
maps. Nested paths resolve relative to the containing source, dependencies load
once, and errors retain the original filename. The native corpus passes 164 Linux
tests and 114 Windows tests. See [simple libraries](docs/libraries.md) and
[the example](examples/library_demo.ramos).

Version 0.10 adds immutable UTF-8 `string` values, automatic reclamation of
unused memory, mutable structs and typed arrays on both native targets. Old byte
literals and APIs stay compatible. The native corpus passes 144 Linux tests and
94 Windows tests. See [the value and memory contracts](docs/values.md) and
[the streaming text tool](examples/line_stats.ramos).

Version 0.9 adds buffered stdin line input and signed integer/text conversion,
with separate EOF, I/O and parse status checks. The native validation corpus
passes 121 Linux tests and 71 Windows tests. See [the contract and interactive
example](docs/input-text.md).

Version 0.8 added line/block comments, short-circuit `&&`/`||` and more helpful
diagnostics. See [the semantics and examples](docs/usability.md).

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
Read [The Ramos Book in HTML](https://zackmsa777-a11y.github.io/ramos-docs/)
or [the Markdown edition and AI agent guide](https://github.com/zackmsa777-a11y/ramos-docs)
for the language, libraries and runnable CLI/TUI/GUI examples.
The [application-language roadmap](docs/roadmap-1.0.md) sets the next milestones,
working examples and release checks under those rules.

GitHub's language sidebar cannot yet name Ramos because it is absent from
Linguist's registry. This repository keeps real `.ramos` sources and documents
[the prepared Linguist registration and remaining acceptance requirement](docs/github-language.md).
A [Ramos editor extension](https://github.com/zackmsa777-a11y/language-ramos/releases/tag/v0.18.0)
provides highlighting for `.ramos` files in VS Code today.

## Try it

Build the compiler with GNU binutils and Make, then run the calculator:

```sh
make
./ramos run examples/calculator.ramos
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

Format a copy or check a file without changing it:

```sh
./ramos fmt examples/hello.ramos -o formatted-hello.ramos
./ramos fmt formatted-hello.ramos --check
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

On Windows, download the native [ramos.exe](https://github.com/zackmsa777-a11y/ramos/releases/download/v0.19.0/ramos.exe):

```powershell
.\ramos.exe run .\hello.ramos
```

From Linux, cross-compile directly:

```sh
./ramos build examples/hello.ramos -o hello.exe --target windows
make windows                 # native Windows compiler: build/ramos.exe
```

Windows is the default target for the Windows compiler; Linux is the default for
the Linux compiler. Both can select either target explicitly. See
[Windows setup, runtime and self-hosting](docs/windows.md).

## File tools and terminal UI

```sh
make cli-tools
./build/rcopy source.bin new-copy.bin
./build/rgrep needle README.md
./build/rview README.md
```

`rview` displays a colored frame, highlighted lines and page status; use arrows,
j/k, Space/n, p and q. Programs use the same native compiler and the ordinary
Ramos-written `stdlib/io.ramos`, `cli.ramos` and `tui.ramos` libraries. Download
[the complete CLI/TUI bundle](https://github.com/zackmsa777-a11y/ramos/releases/download/v0.12.0/ramos-0.12.0-cli-tui.zip)
and keep its folders together. See [contracts, examples and limits](docs/cli-tui.md).

## Desktop GUI (Windows and Linux)

```powershell
.\ramos.exe build .\examples\notes.ramos -o .\notes.exe --gui
.\notes.exe
```

Linux desktop (install GTK3, for example `sudo apt install libgtk-3-0t64` on
Ubuntu 24.04):

```sh
./ramos run examples/notes.ramos --gui
./ramos build examples/notes.ramos -o notes --gui
./notes
```

Weave `stdlib/gui.ramos`, create controls and poll `gui_event`. Download the
[GUI bundle](https://github.com/zackmsa777-a11y/ramos/releases/download/v0.19.0/ramos-0.19.0-portable-gui.zip)
with both compilers, all thirteen libraries, examples and the ready-to-run Notes app.
See [API, lifecycle and current limits](docs/gui.md).

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
  functions and structs may appear before or after it. `weave` adds library
  definitions at top level.
- `print` accepts a string literal, buffer, integer, float64 or boolean expression
  and adds a newline. Booleans print as `true` or `false`; floats use six fractional digits.
- Integer expressions support `+`, `-`, `*`, `/`, `%`, unary `+`/`-`, and
  parentheses. Multiplication, division, and remainder bind more tightly than
  addition and subtraction. Binary operators at the same precedence associate
  left to right.
- Integers range from `-9223372036854775808` to `9223372036854775807`.
  `-9223372036854775808` is accepted as a directly negated literal; its positive
  magnitude cannot be used as an ordinary positive literal.
- `let` declares an immutable binding; `var` declares a mutable
  binding. Every binding must have an initializer. `int64`, `float64`, `bool`, `bytes`, `string`, struct and array types
  are inferred and fixed for the lifetime of the binding.
- Binding reassignment is supported only for `var`; fields and array elements can be mutated through `let`. Names must be declared before use;
  duplicate declarations in the same block are errors. Inner blocks may
  shadow outer names, and their bindings are invisible after the block ends.
  Identifiers use ASCII letters,
  underscores, and digits, with a letter or underscore first. Keywords are
  reserved. `"..."` produces bytes; `s"..."` produces immutable UTF-8 strings.
- Separate statements with newlines; the final statement may directly precede
  `}`. Newlines after operators and opening parentheses are allowed. Semicolons
  are not implemented. Comments use `//` or non-nesting `/* ... */`; newlines
  in block comments retain their statement-separator meaning.
- Input is UTF-8. String escapes are `\n`, `\t`, `\r`, `\"`, `\\`, and `\0`.
- Empty bodies, empty strings, LF, and CRLF are supported.
- Raw NUL source bytes, malformed UTF-8, unsupported escapes, and raw newlines inside
  strings are rejected. Diagnostics contain filename, line, byte column, an escaped source preview and a caret. See [authoring tools](docs/devtools.md).

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
- `<`, `<=`, `>`, and `>=` compare two signed integers or two floats. `==` and `!=` compare
  two integers, two floats, two booleans or two strings. Mixing types is a compile-time error.
- `&&` and `||` require booleans and short-circuit left to right; skipped operands
  still undergo type checking.
- From lowest to highest precedence: `||`, `&&`, equality, ordering, addition/subtraction,
  multiplication/division/remainder, unary signs/`!`, and primary expressions.
  Operators at one level associate left to right. `1 < 2 < 3` is rejected;
  combine pairwise comparisons with `&&`. Arithmetic requires matching numeric types; `+` also concatenates strings.
- `if condition { ... } else { ... }` and `while condition { ... }` require
  a boolean condition. `else` is optional and may follow on a new line.
  Branches use braces; `else if` chains test later conditions only when prior arms fail.
- `while` reevaluates its condition before every iteration. `break` exits the
  innermost loop; `continue` reevaluates its condition. Both require a loop.
  `while true` runs until a `break` or a runtime failure; there is no implicit
  iteration limit. Code in skipped branches is type-checked but not executed.
- Bindings initialize whenever execution reaches their declaration. A shadowing
  initializer can refer to the outer binding. Blocks do not expose their locals.
- `for name in start..end { ... }` evaluates int64 bounds once, then counts
  upward with an excluded end. The counter is immutable and local to the body;
  empty/reversed ranges do not run. `break`/`continue` target the innermost loop.
- `+=` accepts int64/float64/string, `-=` accepts int64/float64, and both are statements with
  matching operand types. Destinations and indices evaluate once, before the RHS.
  Bindings require `var`; fields/elements retain mutation through `let`.
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

Parameters require non-void type annotations and their bindings are immutable.
Results can declare any value type or `void`; omitting the result means void.
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

Every call has its own local frame. At most 1,024 Ramos calls may be active,
including `main`; attempting the next call reports a runtime error and exits 1.
Normal returns release the frame and restore the active-call counter. A second guard checks a 4 MiB stack
budget before allocating each frame. Use an OS stack of at least 8 MiB; see
[the full stack policy](docs/stack-budget.md).

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

Buffers share the reclaiming heap with strings, structs and arrays: 16 MiB of
allocated blocks plus an 8 MiB ownership map, and at most 1 MiB per payload.
Metadata and alignment count toward the heap limit. Invalid sizes, indices,
byte values or allocation failures report a runtime error and exit 1.
Unreachable allocations can be collected automatically or with `collect()`.
See [buffer semantics](docs/buffers.md).

## Strings, structs and arrays

```ramos
struct Point { x: int64, y: int64 }
fn main() {
    let title = s"Hello, " + s"🌍"
    print(title)
    print(slice(title, 7, 8))
    let points = array(Point, 2, Point(0, 0))
    points[1] = Point(3, 4)
    print(points[1].x)
}
```

Strings support concatenation, content equality, Unicode scalar length and
slicing. `string(bytes)` validates/copies UTF-8; `to_bytes(string)` makes a mutable
copy. Structs and arrays are typed mutable references; assigning them aliases
their contents. `array_resize` returns a fresh resized array. The runtime reclaims
unreachable values, including cycles, while keeping active values valid.
See [the complete contracts and limits](docs/values.md).

## Libraries

```ramos
weave "stdlib/numbers.ramos"
weave "stdlib/lists.ramos"
fn main() {
    let scores = list_new()
    list_push(scores, num_max(7, 42))
    print(list_get(scores, 0))
}
```

Copy `stdlib/` beside your source. `weave` paths are relative to that source,
including in nested libraries. Libraries share a checked namespace and compile
into the executable; no runtime package loader is needed. Repeated dependencies
load once, cycles fail, and output protection covers every source. Run
`make library-demo` or see [library semantics and APIs](docs/libraries.md).

## Numerical programs

```sh
./ramos run examples/mandelbrot.ramos -- image.pgm 320 240 100
```

Use `float64(n)` for explicit integer conversion, `float_sqrt(x)` for square root,
and `float_to_text(x, places)` for 0..18 fixed fractional digits. Floating-point
arithmetic traps on non-finite results or division by zero; gradual underflow
is allowed. See [all float rules and the math library](docs/math.md).

## Arithmetic behavior

The following overflow rules apply to int64. Float64 has the separately documented
finite-value policy above.


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
non-executable. No region is both writable and executable. Linux CLI output is static; `--gui` Linux output dynamically links GTK3, GLib,
GObject and Cairo (including their system dependencies). Windows uses system DLLs with NX/ASLR protections and requires no C runtime.

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
fallible; `io_error()` reports the last file or stdin operation's negative error status
(or zero). `read_file` returns an empty buffer on failure, so check the status
before interpreting an empty result. `write_file` publishes atomically and
returns zero or negative errno. Flags are 0 for a new ordinary file, 1 for a new
executable, 2 for replacement, and 3 for replacement with executable permissions.
`platform()` identifies the host (0 Linux, 1 Windows). Windows maps failures to
common negative statuses and accepts the executable flag without POSIX modes.
It refuses to replace the most recent successfully read file or an alias of it,
including with replacement enabled. See [the I/O contract](docs/io.md).

## Stdin and decimal text

```ramos
fn main() {
    let line = read_line()
    if io_error() != 0 { exit(1) }
    let value = text_to_int(line)
    if parse_error() != 0 { exit(1) }
    print(int_to_text(value))
}
```

`read_line()` removes LF or CRLF. Check `stdin_eof()` to distinguish EOF from
a blank line; a nonempty final line is returned even without a newline.
`text_to_int()` validates the whole buffer and distinguishes invalid syntax
from signed overflow. See [the full contract](docs/input-text.md) and
[examples/input.ramos](examples/input.ramos).

## Current limits and next work

The self-hosted compiler accepts up to 64 regular source files totaling 1 MiB
(with boundary separators), at most 50,000
tokens including EOF, 4,096 total declarations including parameters and ended
blocks and hidden range-bound slots, 256 functions and 16 parameters per function. Structs are limited to 64
types with 16 fields each; array type nesting to 16. Expression and block
depth remain bounded at 128; generated programs allow 1,024 active calls within a checked 4 MiB stack budget.
Its output and decoded string-data arenas are each 1 MiB; labels and fixups each
have a 40,000-entry bound. These are checked limits. The retained bootstrap has
the older 4 MiB output and IR limits. See [compiler representation limits](compiler/README.md).

The compiler is self-hosted; namespaces, more library types, wrapping arithmetic,
broader optimization and additional targets remain future work. Performance claims need
new repeatable measurements. The runtime provides checked arithmetic and bounded
buffers, but generated programs execute with the caller's operating-system
permissions. Images, menus, multiple windows, automatic layout/DPI policy, games and
browser support need further work. Linux GUI is verified on X11; Wayland is not yet verified.

## Benchmarks

Ramos 0.14 has a recorded eight-task comparison with optimized checked C, Rust
and CPython on the recorded Linux VM. The execution index is **Ramos 37.48,
C 100, Rust 118.73 and Python 2.52** (higher is faster).
Across this suite Ramos is **14.88× faster than Python** and takes
**2.67× C's time**. These geometric means describe this suite and shared
machine, not all programs or a language-quality score. No Windows timing claim.

Every timed output is checked; the report includes nine randomized samples,
source/compiler hashes, toolchain flags and separately reported startup/build
costs. See [the 0.14 report](benchmarks/0.14.0/report.md),
[raw samples](benchmarks/0.14.0/results.json) and
[the fresh pre-change 0.13 baseline](benchmarks/baseline-0.13.0/report.md).
The syntax milestone makes no general speedup claim: existing workload binaries
remain [byte-identical on both targets](docs/syntax-codegen-continuity.json).
A [targeted range/while comparison](benchmarks/0.14.0/range/results.json) measures
one equivalent checked loop, not a general language ranking.

```sh
make
python3 benchmarks/run_suite.py --output-dir work/benchmark-current
python3 benchmarks/run_suite.py --validate-only
python3 benchmarks/range_loop.py
```

The [0.7.1 report](benchmarks/report.md),
[0.7.0/0.7.1 optimization comparison](benchmarks/optimization.md) and
[historical 0.2 report](benchmarks/report-0.2.md) remain available for audit.
Measurements from different machines or runs are not directly interchangeable.

The 0.18 math, 0.17 text APIs, 0.16 authoring tools and 0.15 OS APIs are validated for behavior, resource lifetime and deterministic
self-hosting. The 0.14 benchmark table above is historical evidence; no 0.18
C/Rust/Python comparison or overall score is claimed. A separate
[0.17 text-assembly measurement](benchmarks/0.17.0/text-builder.md) compares
repeated string concatenation with the new builder: about 20.8× lower elapsed
time for 8192 appends / 512 KiB on the recorded Linux machine. This is one
application workload, not a general language speed claim.
