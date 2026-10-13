# Ramos application-language goal

**Goal:** make Ramos a simple native language for useful CLI, TUI and desktop
applications on Windows x64 and Linux x64. A beginner should be able to build
and run a small tool from a short example; larger tools should have the libraries,
diagnostics and resource handling needed to keep working.

This development plan starts from 0.13. The 0.14 syntax, 0.15 OS libraries, 0.16 authoring tools, 0.17 text builders and 0.18 float/math and 0.18.1 decimal input plus 0.19 Linux GUI and 0.19.1 layout/file pickers plus 0.20 monotonic timing and 0.21 collection controls plus 0.22 checked recursion and 0.23 canvas drawing plus 0.24 exact numerical output and 0.25 preview opt-in GUI scaling are now
implemented; all remaining milestones below are proposals. Proposed version labels below describe order, not deadlines.
Keep each release small enough to implement and verify completely; split a
milestone if necessary. Python-like ease and Rust/C-like native performance
are design aims, not promises of ecosystem parity or benchmark superiority.

## The user's rules

**1. Simple.** Keep a small, readable syntax and one clear way to perform common
tasks. Preserve `weave` for libraries. Put ordinary helpers in Ramos libraries
instead of growing the compiler for every convenience. Prefer inferred local
types, useful defaults and examples over configuration. Common text, file and
GUI operations should not require hand-written byte manipulation.

**3. Fast.** Keep direct native ELF/PE generation and the self-hosted compiler.
Measure speed rather than infer it from native output. Avoid needless copying,
allocations and idle polling. Optimize costs observed in real applications;
performance claims must identify the release, machine, workload and measurement.

No rule 2 was supplied. Correctness remains a release prerequisite: preserve
checked arithmetic, bounds, UTF-8 contracts, resource cleanup and deterministic
self-hosting. Any change in those contracts must be explicit and tested.

## Starting point

0.13 already has immutable strings, reusable managed memory, structs, typed
arrays, `weave`, a small standard library, streamed files, stdin, CLI/TUI tools
and a Windows GUI library. Those foundations should be extended, not rebuilt.
0.19 adds a GTK3 Linux desktop backend; 0.19.1 supplies simple layout helpers and file pickers; automatic layout/DPI policy remains missing. Live memory, individual values,
recursion and source size have documented limits. The published comparative
timings are historical; they are not a performance result for 0.13.

## Ordered milestones

| Proposed milestone | Work | Runnable acceptance example |
| --- | --- | --- |
| 0.14: easier code (implemented; see [contracts](syntax.md)) | `else if`, exclusive-range `for`, `+=` and `-=`; updated syntax documentation and highlighting | Simplify an existing search/viewer example while preserving its output and behavior on both OSes |
| 0.15: useful OS libraries (implemented; see [contracts](system.md)) | Directory iteration, paths, environment access and direct child-process execution | Recursive name search, streamed exclusive file copy and a direct command runner; recursive backup is not shipped |
| 0.16: easier development (implemented; see [contracts](devtools.md)) | Source-line/caret errors, a formatter and a compile-and-run command | A new user can run a file, correct a reported error and format it using the documented commands |
| 0.17: reusable text (implemented; see [contracts](text-builder.md)) | UTF-8 builder, immutable snapshots, capacity reuse/release | Streamed UTF-8 line numbering with a reusable builder; exact-size/rejection and long-running memory checks |
| 0.18: native math (implemented; see [contracts](math.md)) | Finite `float64`, explicit conversions, square root, exact fixed formatting and Ramos math helpers | Native Mandelbrot image renderer, independently checked numerical results on both OSes |
| 0.18.1: numerical input (implemented; see [contracts](math-input.md)) | Fallible decimal parsing with exact rounding in the Ramos math library | Streamed file/stdin statistics, independent references and long-running memory checks |
| 0.21: collection controls (implemented; see [contracts](collections.md)) | Reservation, fallible full-capacity status, storage release, integer sorting; limits remain unchanged | Native `rsort`, alias/boundary and long-running memory checks |
| 0.22: recursion review (implemented; see [stack policy](stack-budget.md)) | 1,024 active calls within a checked 4 MiB stack budget; heap cap stays explicit | Deep managed roots, large-frame rejection, 64-level calculator expressions |
| Live-memory follow-up | Profile real live-data workloads before changing the 16 MiB heap budget | Measured bounded and heap-pressure workloads |
| 0.19: portable GUI (implemented; see [contracts](gui.md)) | GTK3 Linux backend, existing native controls/events/panels, `run --gui` | The same Notes source opens/saves Unicode files and remains responsive while resizing on Windows and Linux |
| 0.19.1: GUI helpers (implemented; see [contracts](gui.md)) | Checked rectangles, padding, rows/columns and native Open/Save path pickers | Notes opens Unicode files, cancels safely and saves new files on both OSes |
| 0.23: canvas drawing (implemented; see [contracts](canvas.md)) | Bounded reusable commands, native shapes/pixels, retained repaint snapshots | Interactive plot and actual native pixels, clipping, GC, resize and resource checks on both OSes |
| 0.24: numerical output (implemented; see [contracts](math-output.md)) | Exact scientific/compact formatting in Ramos, fixed output preserved | Tiny calculator values remain visible; independent rounding and binary64 round trips on both OSes |
| 0.25 preview: explicit scaling (see [contracts](gui-scaling.md)) | Opt-in logical geometry, native fonts/canvas and DPI events; bounded resource probes | Genuine GTK 1× → 2× → 1×; Windows native initial state and resource checks; actual Windows display transition pending |
| GUI acceptance follow-up | Adjustable-display Windows report and genuine multi-monitor movement | Keep the same demo open through actual OS scale changes |
| 1.0 candidate: reliability and measured speed | Profile the acceptance apps, fix demonstrated costs, polish installation and packaging, document compatibility | Build, run and package the CLI/TUI/GUI examples from a clean installation on both OSes |

### 0.14: specify the small syntax changes first

Define range bounds as evaluated once, with the upper bound excluded. Specify
loop-variable scope, `break`, `continue` and checked iteration overflow. Define
compound assignment so its destination is evaluated once, including fields and
array indices. Retain checked arithmetic and useful errors.

Start with `+=` and `-=`; do not also add `++` merely to duplicate the same task.
Review per-function stack requirements before increasing recursion depth. A
larger constant alone does not solve stack safety.

Record a fresh 0.13 performance baseline before compiler changes. Existing
programs must still compile, and the simplified example must have matching
output. Measure compile time as well as the affected runtime workloads.

### 0.15: file tools as the first practical application target

Directory iteration must stream entries and release handles when stopped early.
Specify Unicode paths, missing files, permission failures and traversal policy,
including symbolic links, so recursive tools cannot accidentally loop forever.
Use fallible results for expected OS failures, consistent with existing I/O.

Child processes receive an executable and argument values directly. Shell
interpretation should require an explicit separate choice. Specify inherited
or redirected stdin/stdout/stderr, waiting and exit status. Avoid capturing
unbounded output into the managed heap.

Test empty directories, Unicode filenames, large streamed files, failed copies,
early exit and child failures on native Windows and Linux.

### 0.16: make common mistakes easy to fix

Errors should show filename, line, column, the relevant source line and a caret,
with the expected construct or type. Preserve original library locations.
The formatter must preserve comments and program meaning and be idempotent.

Design `ramos run app.ramos` as compile-and-run using a temporary native binary,
with program arguments, exit-status forwarding and cleanup. Keep `build` for
distributable executables. Update editor support alongside new syntax. Evaluate
`--emit-asm` after the core authoring work; an inspection feature needs a clear
contract and should not become a second code-generation backend.

### 0.18: remove the walls using measured application needs

0.18 now specifies and implements finite binary64 literals, comparisons, conversions,
division, square root and fixed printing. Integer overflow checks stay intact.
Numerical results are verified against independent references on both targets.
See [the exact contracts](math.md); [0.18.1 decimal input](math-input.md) now fills the text-to-float gap;
trig/log functions and broader numeric output remain future work.

0.17 delivered a string builder; next review amortized collection growth with clear aliasing and
lifetime rules. Keep immutable string values and low-level bytes available.
Profile collection and heap behavior before redesigning the allocator or GC.
Use long-running allocation tests and actual live-data workloads to choose
larger or configurable limits; do not silently remove checks. Ordinary code
should not need manual freeing. Explicit release remains necessary for OS
resources such as files, processes and windows.

Generics and broader containers come later if concrete apps need them; they
should not block useful strings, arrays and number handling.

### 0.19: one GUI API with real desktop evidence

Choose and document the initial Linux display backend and its OS dependencies.
Keep platform details behind `stdlib/gui.ramos`. Add layout, scaling, dialogs
and drawing in small tested slices. Verify events, focus, input, close, resize,
resource lifetime and Unicode on actual desktop sessions, including Windows.
Cross-compilation alone is not proof that a GUI works.

Retain an idle-blocking event loop. Multi-window support, menus, images and
advanced widgets can follow demonstrated app needs.

## Performance evidence

Use at least eight workloads spanning integer arithmetic, recursion, arrays,
strings, allocation, file streaming, parsing/search and numerical rendering.
Compare equivalent C, Rust and Python implementations on the same machine;
verify results before timing, record toolchain versions and build flags, repeat
runs and report medians and variability. Explain semantic differences, including
checked arithmetic. Benchmark input must be large enough to separate useful
work from process startup.

For a C-relative execution index, define C as 100 and each Ramos task score as
`100 * C_time / Ramos_time`; the overall score is the geometric mean of the
task scores. Report per-task results and Rust/Python ratios too. A score above
100 means faster on this suite, not a better language. Track startup time,
compile time, binary size and peak memory separately from the speed index.

Investigate regressions outside measured variability and explain any deliberate
tradeoff. Never reuse old benchmark numbers as evidence for a new release.
Documentation-only edits do not require rerunning the performance suite.

## Completion checks

A feature milestone is complete when its behavior is specified, an application
uses it, relevant success/failure tests pass natively on Windows and Linux,
both deterministic self-hosting proofs still match, and the downloadable package
contains the working compiler, libraries, examples and instructions. Platform
features additionally need execution on the platform they target.

The 1.0 goal is complete when a clean-install user can build and run recursive
file tools, an interactive TUI and the portable Notes GUI; a numerical example
exercises the math support; long-running examples stay within their documented
resource behavior; and current performance measurements and remaining limits
are published. This is useful application capability, not all of Python or Rust.

Package registries, async runtimes, advanced generics and ecosystem expansion
remain follow-up goals. GitHub Linguist recognition is independent of language
correctness and application readiness.
