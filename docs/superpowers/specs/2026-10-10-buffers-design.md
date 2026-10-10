# Ramos 0.5: bounded byte buffers

The user authorized continuing the self-hosting roadmap. This increment lets
Ramos programs hold, scan and mutate source bytes. The compiler remains assembly.

## API and types

Add opaque `bytes` values, inferred for locals and explicit in function
parameters/returns. String literals in expressions create independent mutable
buffers containing decoded UTF-8 bytes. Keep direct literal printing efficient.
Add `\0` to literal escapes to represent binary zero; raw NUL source stays invalid.

Reserved intrinsic function names (cannot define user functions with these names):

| Operation | Signature | Behavior |
| --- | --- | --- |
| `buffer` | `(int64) -> bytes` | Fixed-length, zero-filled allocation |
| `buffer_len` | `(bytes) -> int64` | Length in bytes |
| `buffer_get` | `(bytes, int64) -> int64` | Unsigned byte 0..255 |
| `buffer_set` | `(bytes, int64, int64) -> void` | Write a byte 0..255 |

Intrinsic arguments evaluate left to right. Local bindings may shadow intrinsic
names, following existing function-name rules; a shadowed call is rejected.
`print(bytes)` writes all bytes (including zero) then a newline. Buffers cannot
participate in arithmetic, comparisons, equality or conditions. Assignment,
parameters and returns require exact types. `let` protects a binding, not its
buffer contents. Copies/arguments/returns alias the same buffer; separate
allocations and separate literal evaluations are independent.

## Lifetime, allocation and runtime

Use a process-owned, lazily mapped 16 MiB arena, readable/writable and never
executable. No user pointers, freeing, slices, resizing or general arrays yet.
All buffers live until process exit, so returned locals and aliases remain valid.
This is bounded monotonic allocation, not reference counting or manual ownership.
Each buffer holds an internal 8-byte length followed by payload; allocation size
is aligned to 8 bytes. Maximum payload per buffer is 1 MiB. All descriptors and
padding count toward the arena limit. An empty buffer consumes 8 bytes.

Check signed lengths before arithmetic and cap addition before allocation.
Reject negative indices and indices >= length before touching payload. Reject
values outside 0..255 before byte truncation. Invalid sizes, arena exhaustion,
mapping failure, bad indices and invalid bytes terminate with a clear stderr
runtime diagnostic and status 1. Preserve current arithmetic and call-depth
checks. Runtime state uses dedicated registers r13 (arena base), r14 (used bytes)
alongside r12 (call depth); generated functions and helpers preserve this state.

Literal data stays in the ELF read-only segment and is copied into mutable
storage on evaluation. Only checked memory and runtime calls are emitted, using
the existing bounded IR and fixup infrastructure. No external backend.

## Acceptance and scope

Integration tests cover zero filling, binary bytes, UTF-8 byte lengths, aliases,
independent buffers/literals, function arguments/returns, recursion, nested
calls/evaluation order, compile-time type/arity errors and name shadowing,
allocation/bounds/value extremes, arena accounting and output failures. Inspect
ELF permissions and verify a Ramos example counts digits in stored source text.
Run the complete existing corpus and independent review before delivery.

Next: fallible file I/O and arguments, then broader compiler collections and
explicit wrapping arithmetic, then the Ramos-written compiler and bootstrap proof.
