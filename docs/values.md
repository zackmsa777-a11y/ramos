# Strings, reusable memory, structs and arrays (0.10)

These features implement the first three priorities from the developer feedback.
Both native targets use the same checked semantics. Existing byte-buffer programs
keep their byte-literal and API behavior; discarded allocations can now be reclaimed.
`string`/`struct` are new keywords and the new intrinsic names are reserved for
function definitions. Older programs defining those names must rename them.
The compiler's old `string` helper was renamed `string_literal` for this reason.
The compiler remains written in Ramos and emits ELF/PE directly.

## Immutable UTF-8 strings

```ramos
fn join(a: string, b: string) -> string { return a + b }
fn main() {
    let greeting = join(s"Hello, ", s"🌍")
    print(greeting)
    print(len(greeting))              // 8 Unicode scalars
    print(slice(greeting, 7, 8))       // 🌍
    print(greeting == s"Hello, 🌍")   // true
}
```

| Operation | Contract |
| --- | --- |
| `s"..."` | Immutable `string`; same escapes as byte literals |
| `string(bytes)` | Validate strict UTF-8 and copy into a string |
| `to_bytes(string)` | Fresh mutable copy; mutating it cannot change the string |
| `a + b` | Concatenate two strings into a new string |
| `a == b`, `a != b` | Compare string contents, including embedded NUL |
| `len(string)` | Count Unicode scalar values |
| `slice(string, start, end)` | Copy scalar range `[start, end)`; bounds checked |
| `print(string)` | Write UTF-8 contents followed by LF |

Old `"..."` literals remain mutable `bytes`. Conversion is explicit, including
at byte-oriented file I/O boundaries. No implicit integer/string conversions
are added: use `string(int_to_text(n))` for decimal formatting.

Malformed UTF-8, overlong encodings, surrogate encodings and values above
U+10FFFF trap with a diagnostic and exit 1. NUL is valid string content.
Length and slicing count scalars, not bytes or grapheme clusters: `s"é"`
contains two scalars. Slicing allows an empty range at the end and rejects
negative, reversed or out-of-range indices. Each string has at most 1 MiB of
UTF-8 payload; an oversized concatenation traps before allocation.

Length/slicing scan the UTF-8 data; concatenation copies both operands.
Repeatedly growing a string by one character is not an amortized builder API.

## Structs

```ramos
struct Point { x: int64, y: int64 }
struct Player { name: string, position: Point }
fn main() {
    let player = Player(s"Ramos", Point(3, 4))
    player.position.x = 42
    print(player.name + s"!")
    print(player.position.x)
}
```

Fields require non-void types. Definitions may be referenced before they appear,
including from function signatures or other structs. Fields are separated by
commas or newlines. A trailing comma and empty structs are allowed. Constructors
use declaration order, evaluate arguments left to right, and check exact types
and arity. Duplicate names, missing types and unknown fields are compile errors.

Structs are mutable boxed values. Assignment, parameters and returns copy a
handle, so aliases observe field writes. `let` protects the binding while allowing
field changes, as it already does for bytes. String fields can be replaced, but
the string value itself remains immutable. Nested field/index assignment is
supported. There are no unchecked addresses, null references or implicit copies.

The checked limits are 64 struct types and 16 fields per type.

## Typed arrays

```ramos
fn main() {
    let points = array(Point, 2, Point(1, 2))
    points[1] = Point(3, 4)
    print(points[1].x)
    let more = array_resize(points, 3, Point(5, 6))
    print(array_len(more))
}
struct Point { x: int64, y: int64 }
```

| Operation | Contract |
| --- | --- |
| `[T]` | Array type; annotations may nest up to 16 levels |
| `array(T, count, initial)` | Fill a new typed array; all elements start with `initial` |
| `array_empty(T)` | Empty typed array without requiring an initial value |
| `array_len(a)` | Number of elements |
| `a[index]`, `array_get(a, index)` | Checked typed read |
| `a[index] = value`, `array_set(a, index, value)` | Checked typed write |
| `array_resize(a, count, initial)` | New array: preserve prefix, fill added elements |

Indices and counts are signed integers. Negative or out-of-range indices and
counts outside 0..131072 trap before access. Elements occupy eight bytes, so
the maximum payload is 1 MiB. Arrays of int64, float64 (since 0.18), bool, bytes, string, structs and
arrays are supported; void elements are rejected. There is no unchecked default
reference: every nonempty constructor/growth supplies a typed fill value.

Array handles alias their contents. Reference-type fill values are shared
across initial elements; construct separate values when independent records
are needed. Resizing copies elements and leaves the old array and its aliases
unchanged. It costs O(old/new length), not an amortized in-place growth operation.
`array_empty(Node)` allows a recursive struct to start with an empty link array.

## Reusable memory

Bytes, strings, structs and arrays use a nonmoving conservative mark/sweep heap.
When allocation cannot find space, it collects unreachable objects and retries.
`collect()` requests collection explicitly; `memory_used()` reports currently
allocated block bytes, including headers/padding and not-yet-collected garbage.
A reachable returned value, argument, active expression or aggregate field
remains valid. Unreachable cycles can be reclaimed. Every reused payload is
zeroed. Scope exit, break and continue clear ended local slots.

The heap holds at most 16 MiB of allocated blocks, plus an 8 MiB ownership map.
Each block needs a 32-byte header and alignment to eight bytes. Empty values
therefore consume 32 bytes. Mapped memory is RW and never executable. Stdin
retains its separate lazy 1 MiB + 12 KiB scratch mapping.

The collector scans active stack words/saved registers and object payload words.
An integer, float payload or byte sequence resembling an allocated address can retain that
object conservatively. This is not an exact memory-accounting or real-time GC
guarantee. There is no manual `free`, pointer cast, moving collection or dangling
alias API. A program whose reachable data exceeds the heap still traps; the
change removes the cumulative-allocation limit, not the bounded live heap.

## Run a real text tool

[examples/line_stats.ramos](../examples/line_stats.ramos) reads UTF-8 lines from
stdin, annotates them with a line number, and prints counts. Its `Stats` struct
holds totals and an integer array of recent line lengths. Temporary strings and
byte buffers are reclaimed while it streams input.

```sh
./ramos build examples/line_stats.ramos -o line-stats
printf 'hello\nمرحبا 🌍\n' | ./line-stats
```

```powershell
.\ramos.exe build .\line_stats.ramos -o .\line-stats.exe
Get-Content .\input.txt -Encoding utf8 | .\line-stats.exe
```

Redirected stdin must contain UTF-8 for `string(raw)`; PowerShell's pipe encoding
varies by version/settings. Native console input still follows the configured
Windows input code page. Empty and final unterminated lines follow `read_line`
semantics. A local Linux probe streamed 100,000 256-byte lines and reported
`lines=100000 characters=25600000 longest=256`.

Validation covers Unicode reference comparisons, immutable copies, bounds and
type failures, aliases, constructors/calls/returns, active-expression roots,
reused zeroed buffers, live-heap exhaustion and cyclic graph lifetimes.
Performance tables remain the historical 0.7.1 measurements; this release makes
no new comparative speed claim for 0.10. Subsequent releases add syntax conveniences,
weave/stdlib, authoring tools and [float64](math.md); assembly inspection remains future work.

The [native CI run](https://github.com/zackmsa777-a11y/ramos/actions/runs/38041196929)
passed 144 Linux tests and 94 Windows tests, with matching self-hosted compiler
rebuilds on both targets. See [recorded validation](values-verification.json),
[Linux proof](bootstrap-proof.json) and [Windows proof](windows-bootstrap-proof.json).
