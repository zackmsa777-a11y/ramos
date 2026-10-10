# Easier application code (Ramos 0.14)

Ramos 0.14 adds `else if`, ascending exclusive-range `for`, and the statement
operators `+=` and `-=`. It keeps checked arithmetic, native Linux/Windows
output and the self-hosted Ramos compiler. These are syntax conveniences over
the existing branch, loop and expression emitter, not an interpreter or backend.

```ramos
fn describe(n: int64) -> string {
    if n < 0 { return s"negative" }
    else if n == 0 { return s"zero" }
    else { return s"positive" }
}
fn main() {
    var total = 0
    for i in -2..4 {
        if i == 0 { continue }
        total += i
    }
    print(total)                  // 3
    print(describe(total))        // positive
    var message = s"Hello"
    message += s", Ramos!"
    print(message)
}
```

## Else-if chains

Write `if condition { ... } else if condition { ... } else { ... }`. Conditions
must be booleans. Only the first matching arm runs, and later conditions are
not evaluated after a match. All arms remain type-checked. Newlines/comments
can separate a closing brace, `else` and `if`.

Each arm has its own lexical block. A chain guarantees a value-function return
only when it has a final `else` and every arm guarantees return. A chain without
that final fallback does not prove that every input is covered. Chaining does
not consume another block-stack level for each arm; genuinely nested bodies
still obey the existing nesting limit.

## Ascending, end-exclusive ranges

`for name in start..end { ... }` evaluates `start` and then `end`, **once each**,
including when the range is empty. Both are int64 expressions. The counter takes
`start`, `start + 1`, and so on while strictly less than `end`. A range with
`start >= end` is empty, not descending. Parentheses, negative bounds, calls,
multiline expressions and comments are allowed.

The counter is an immutable int64 binding scoped to the loop body. It can shadow
an outer name, but the bounds still see that outer binding: the counter does not
exist until both bounds have been evaluated. A declaration in the same body
cannot redeclare it; a genuinely nested block may shadow it. No counter binding
leaks after the loop. Each iteration initializes body locals anew.

`break` exits the innermost `for` or `while`; `continue` goes to the next range
value or reevaluates a while condition. Body locals are cleared on either path.
Loop return analysis stays conservative: a loop by itself does not guarantee a
value-function return. There are no step/descending/inclusive-range variants.

The increment retains an overflow check. With an immutable counter and a
signed end-exclusive bound it cannot need to advance beyond INT64_MAX:
`9223372036854775806..9223372036854775807` runs once and finishes normally.

Each range reserves one source counter and one hidden bound slot. Both count
against the checked 4096-declaration budget; frame storage and cleared scope
slots remain part of the existing memory model. Active-call depth stays at 64;
this release does not raise it without a reviewed stack budget.

## Compound assignment

| Statement | Allowed destination/result |
| --- | --- |
| `destination += expression` | int64 addition or string concatenation |
| `destination -= expression` | int64 subtraction |

The operand types must match exactly. These are statements, not expressions;
`print(n += 1)` is invalid. `++`, `*=`, `/=` and wrapping arithmetic are not
added. Bytes and typed arrays do not acquire concatenation or arithmetic.

An ordinary destination binding must be `var`. A struct field or typed-array
element can be mutated through `let`, following the existing aliasing model:

```ramos
struct Item { count: int64, name: string }
fn main() {
    let item = Item(2, s"Ramos")
    item.count += 3
    item.name += s" book"
    let values = array(int64, 1, 9)
    values[0] -= item.count
    print(values[0])             // 4
}
```

Evaluate the destination reference and every index once, then read its current
value, then evaluate the right-hand expression and write the combined result to
that same destination. Bounds failure occurs before right-hand side effects.
A right-hand call that replaces an aggregate reference does not redirect the
pending write. The original aggregate/value stays rooted across allocations and
collection. String addition allocates a new immutable value; it is not an
amortized string-builder operation.

Overflow reports the ordinary arithmetic runtime error and exits 1. String
limits, UTF-8 validation, array bounds and heap limits are unchanged.

## Compatibility and a real tool

`for` and `in` are newly reserved words. Older user definitions/bindings with
those names need renaming. Existing valid programs without those identifiers
retain their behavior. Output protection and failed-build preservation remain.
The compiler itself still uses the retained seed's older syntax to bootstrap.

[The search tool](../examples/rgrep.ramos) now uses a range for its file arguments,
an else-if chain for line handling, and `line_number += 1`. Its behavior is
checked against the old implementation for help, binary/unterminated lines,
multiple inputs, no matches, missing inputs and exit/error status.

```sh
make cli-tools
./build/rgrep needle input.txt
```

```powershell
.\ramos.exe build .\examples\rgrep.ramos -o .\rgrep.exe
.\rgrep.exe needle .\input.txt
```

## Evidence

The focused native tests cover return analysis, long branch chains, bound
order/scope, signed integer edges, nested loop control, independent generated
range results, single evaluation, aliases, collection, traps and output-file
preservation. See `tests/test_syntax.py` and the Linux/Windows bootstrap reports.

Range conditions compare the counter directly with the saved bound, avoiding
an expression-stack round trip. A reproducible, independently checked
[while/range sum comparison](../benchmarks/0.14.0/range/results.json) records
17 interleaved samples and two warmups. Reproduce with
`python3 benchmarks/range_loop.py`; this single workload is not a general
language speed claim.

A fresh eight-task C/Rust/Python baseline was recorded before changing 0.13.
Existing workload binaries remain byte-identical for Linux and Windows; see
[the continuity report](syntax-codegen-continuity.json). The
[current measurements](../benchmarks/0.14.0/report.md) use the baseline's work
counts and verify every timed output. This syntax milestone makes no speedup
claim. Compiler rebuild and app-build timings are recorded separately in
[the acceptance evidence](syntax-verification.json).

Final native CI passed **209 Linux tests** (213 discovered, four Windows-only
skips) and **155 Windows tests**, including all 15 focused syntax checks.
Both compiler fixed points match. The downloaded CI compilers also match local
build hashes. See [the native run](https://github.com/zackmsa777-a11y/ramos/actions/runs/38063579492).
