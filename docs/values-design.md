# Values and reusable memory: implementation contract

This upgrade implements the developer-feedback priorities: strings, reclaimed
memory, structs and typed arrays, while preserving the old byte APIs. New
keywords/intrinsic names are reserved; conflicting old user names require renaming.

## Memory

The runtime replaces monotonic allocation with a nonmoving conservative mark/sweep
heap. It reclaims unreachable allocations automatically when allocation needs
space; `collect()` explicitly requests a collection and `memory_used()` reports
currently allocated blocks including metadata/padding. The 16 MiB live heap remains
bounded; an additional 8 MiB ownership map supports checked interior-pointer
root lookup. Anonymous memory is RW, never executable.

Roots are active native stack words and saved working registers. The collector
also traces object payload words, so aggregates can retain other objects and
cycles can be reclaimed. A word resembling an object address may conservatively
retain it. There is no manual free, moving collection, hidden pointer cast or
use-after-free contract. Newly allocated payloads are zeroed on every reuse.
Function frames and ended scopes clear unused slots to limit stale retention.

## Strings

`string` is an immutable UTF-8 type, separate from mutable binary `bytes`.
Old `"..."` literals remain bytes for compatibility; `s"..."` produces a string.
`string(bytes)` validates and copies; `to_bytes(string)` returns a fresh mutable
copy. `+` concatenates strings; `==`/`!=` compare content. `len(string)` counts
Unicode scalar values, and `slice(string, start, end)` uses scalar indices with
an exclusive end and checked bounds. Embedded NUL is valid. Grapheme clusters
are not the indexing unit. Existing byte APIs retain their byte indices.

## Aggregates

`struct Point { x: int64, y: int64 }` declares a boxed record. `Point(1, 2)`
constructs it; `point.x` reads and `point.x = value` writes a typed field. Handle
assignment aliases a record; let protects the binding, not record contents.
Definitions may be referenced forward; fields have checked declared types.

`[T]` is a typed array. `array(T, count, initial)` fills it with a typed value;
`a[i]`/`a[i] = value`, `array_empty(T)`, `array_get`, `array_set`, `array_len` and `array_resize` provide checked access
and fresh resizing (existing aliases keep their old array). A reference-type
initial value is shared across initial elements. Array storage and field values
remain traced by the collector. Arrays retain the 1 MiB payload bound.

## Acceptance

Existing 0.9 sources and checks still pass. New native tests exercise Unicode,
immutability, aliasing, bounds, type errors, returns/calls, live objects under
collection, zeroed reuse, cyclic aggregate graphs and repeated allocations far
beyond the old cumulative arena cap. A text-processing tool demonstrates reused
memory. Linux and native Windows tests and byte-identical self-hosting proofs
must pass before publishing. Existing speed measurements remain historical.
