# Byte buffers in Ramos 0.5

Buffers hold source text or arbitrary binary bytes. The type is bytes.
Use buffer(length) to create a fixed-length zero-filled buffer.
buffer_len(b) returns an int64 byte count. buffer_get(b, index) returns an
unsigned byte as int64 (0..255). buffer_set(b, index, value) writes an integer
byte and returns void. print(b) writes its exact contents, including NUL or
invalid UTF-8 bytes, then adds a newline. No implicit terminator is stored.

Locals infer bytes; function parameters and results can declare it.
String literals used in expressions allocate a fresh mutable buffer on every
evaluation. They decode UTF-8 and escapes \n, \t, \r, \", \\, \0.
Lengths and indices count bytes, not Unicode characters. Direct literal
printing uses immutable ELF data without allocation; parenthesized literals
and other buffer expressions follow ordinary allocation rules.

Bindings, parameters and return values copy a handle and alias the same contents.
let makes the binding immutable; its buffer may still be changed. var may be
assigned another buffer. Separate allocations/literal evaluations never alias.
There are no user-visible addresses or pointer conversions. Buffers cannot be
used in arithmetic, equality, ordering or boolean conditions.

All buffers are owned by the process and live until exit. Returning a local
buffer is safe. The runtime uses a single lazily mapped 16 MiB RW, non-executable
arena. Each allocation stores an 8-byte descriptor plus its payload and rounds
the total up to an 8-byte boundary. Empty buffers consume 8 bytes. A payload
may contain at most 1 MiB. Metadata and padding count toward the arena limit.
Anonymous memory starts zero-filled and allocations never reuse storage.

Negative lengths, lengths above the payload limit, exhausted arena or failed
mapping, indices outside 0 <= index < length, and byte values outside 0..255
produce a runtime diagnostic on stderr and exit status 1. Checks happen before
access or truncation. Previous output is preserved. There is no freeing,
resizing, collection or arena reset; allocation-heavy loops eventually fail.
File I/O will need explicit failure handling in a subsequent milestone.

Intrinsic names are reserved for function definitions. Local names may shadow
them, in which case calls through those names are rejected. Calls check exact
types and arity and evaluate arguments from left to right.

Run make buffers for a source-scanning example: it counts digits in stored
Ramos text and returns a buffer built inside another function.

## Implementation

buffers.inc defines intrinsic signatures and static argument checking.
buffer_codegen.inc emits native calls with opaque 64-bit handles, using the
existing expression stack and read-only literal fixups. buffer_runtime.inc
is copied with the position-independent runtime into generated executables.
Runtime register r12 tracks active Ramos calls; r13 stores arena base and
r14 stores allocated bytes. Generated functions preserve these registers.
