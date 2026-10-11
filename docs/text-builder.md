# Ramos 0.17: reusable text builders

`weave "stdlib/text.ramos"` now provides a reusable UTF-8 text builder. Append
new pieces without repeatedly concatenating the entire existing prefix. The
builder, growth and copy logic are ordinary Ramos; no new syntax, intrinsic or
native runtime dependency is added.

```ramos
weave "stdlib/text.ramos"

fn main() {
    let out = text_builder()
    text_builder_append(out, s"Hello, ")
    text_builder_append(out, s"Ramos! 🚀")
    let message = text_builder_finish(out)
    text_builder_clear(out)
    print(message)
}
```

These fixed small appends fit within the bound. For variable-sized user input,
check the return status of each append before using a result.

## API and ownership

| Function | Contract |
| --- | --- |
| `text_builder() -> TextBuilder` | Empty builder with 64-byte initial capacity |
| `text_builder_append(builder, text: string) -> int64` | Append UTF-8 bytes; return 0, or -27 if total would exceed 1 MiB |
| `text_builder_bytes(builder) -> int64` | Current byte count, not Unicode scalar count |
| `text_builder_finish(builder) -> string` | Independent immutable snapshot; keeps builder content |
| `text_builder_clear(builder)` | Empty content and keep capacity for reuse |
| `text_builder_release(builder)` | Empty content and drop owned backing storage; future appends still work |

`TextBuilder` is a mutable struct with `data: bytes` and `count: int64`. Aliases
of the builder share its state. Treat those fields as implementation storage;
use the functions for mutation. Counts outside 0..capacity produce a library
error and exit 1 before access. `finish` validates UTF-8 through the existing
`string` conversion, including when application code directly corrupts storage.

Snapshots do not share mutable storage with the builder. Clearing, appending or
releasing it cannot change an earlier result. Empty text, embedded NUL and valid
Unicode are supported. No partial UTF-8 append is exposed because the input is a
checked string. A size rejection leaves content and capacity unchanged; it is
not a sticky error, so later smaller appends can succeed. The result limit includes
all UTF-8 bytes, not scalar count. Allocation exhaustion retains the native
checked runtime error; -27 does not mean allocation failures are recoverable.

Capacity doubles until sufficient, capped at 1 MiB. Appending copies the new
piece; only growth copies the old storage. `to_bytes` still copies each input
string, and `finish` copies/validates the result. This is an amortized linear
assembly API, not zero-copy text. Taking a snapshot after every append still
copies every prefix. Reuse `clear` for records of similar size; use `release`
after a large record when retaining its capacity is unnecessary.

Release drops the builder's reference; collection reclaims unreachable managed
storage normally. Any separate alias of its raw `data` keeps that buffer alive.
This is not manual pointer freeing. `collect()` can request collection, and
existing 16 MiB managed arena / 1 MiB individual-value limits remain enforced.

## A real streamed file tool

[examples/rnumber.ramos](../examples/rnumber.ramos) numbers UTF-8 lines while
reusing one builder. It processes files larger than the heap in bounded chunks.

```sh
./ramos run examples/rnumber.ramos -- input.txt
./ramos build examples/rnumber.ramos -o rnumber
./rnumber input.txt
```

Windows PowerShell:

```powershell
.\ramos.exe run .\examples\rnumber.ramos -- .\input.txt
```

Input `é🚀`, an empty line and a final unterminated `last` produce these output lines (shown quoted to make the empty payload visible):

```text
"1: é🚀"
"2: "
"3: last"
```

LF/CRLF terminators normalize to LF output. Empty files produce no lines. An
input line or numbered output line exceeding 1 MiB returns 2 before emitting that
line. Missing files, read/close failures and fallible stdout failures also return
2. Previously emitted lines remain emitted. Malformed input UTF-8 invokes the
existing conversion trap (exit 1), so this is a text tool rather than a binary
copy API. Files close on ordinary error/exit paths; forced termination follows
OS process cleanup. There is no file replacement mode.

## Measurements and release checks

[The focused benchmark](../benchmarks/text-builder/run.py) compares repeated
string `+=` with the builder on the same compiler and machine. It appends 64-byte
pieces, then independently checks all result bytes using `text_repeat`. One
warmup and five alternating-order measurements include process startup and
verification. Raw samples, machine and binary/library hashes are recorded in
[the raw report](../benchmarks/0.17.0/text-builder.json) and
[measured table](../benchmarks/0.17.0/text-builder.md). At 8192 appends / 512 KiB,
the recorded Linux medians were 287 ms for concatenation and 13.8 ms for the
builder (about 20.8×). This measures one Linux text
assembly workload; it is not a C/Rust/Python comparison or an overall language
score. Historical 0.14 comparative results remain historical.

[Shared tests](../tests/test_text_builder.py) cover Unicode/NUL/empty values,
shared builder aliases, immutable snapshots, capacity reuse/release, exact-limit
success and nonmutating rejection, invalid counts, automatic reclamation across
6000 results, CRLF/empty/final lines, large streamed files and fallible size/I/O
errors. Native Linux and Windows compiler fixed-point proofs remain required.

Release validation passes **246 Linux tests** (251 discovered, five platform
skips) and **192 native Windows tests** (193 discovered, one Linux fixture skip),
with byte-identical compiler fixed points on both targets. See
[release evidence](text-builder-verification.json).

The broader data/math milestone was split to keep releases reviewable: this
release ships builders only. Float64 and essential math, reviewed collection and
recursion limits, and Linux GUI remain future work. See [roadmap](roadmap-1.0.md).
