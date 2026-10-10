# Byte buffers in Ramos (0.10)

Buffers hold source text or arbitrary binary bytes. The type is bytes.
Use buffer(length) to create a fixed-length zero-filled buffer.
buffer_len(b) returns an int64 byte count. buffer_get(b, index) returns an
unsigned byte as int64 (0..255). buffer_set(b, index, value) writes an integer
byte and returns void. print(b) writes its exact contents, including NUL or
invalid UTF-8 bytes, then adds a newline. No implicit terminator is stored.

Locals infer bytes; function parameters and results can declare it.
Byte literals (`"..."`) used in expressions allocate a fresh mutable buffer on every
evaluation. They decode UTF-8 and escapes \n, \t, \r, \", \\, \0.
Lengths and indices count bytes, not Unicode characters. Byte literals are fresh mutable allocations, including when printed.
Use `s"..."` for the separate immutable string type.

Bindings, parameters and return values copy a handle and alias the same contents.
let makes the binding immutable; its buffer may still be changed. var may be
assigned another buffer. Separate allocations/literal evaluations never alias.
There are no user-visible addresses or pointer conversions. Buffers cannot be
used in arithmetic, equality, ordering or boolean conditions.

Returning a local buffer is safe. All values use the reclaiming heap described
in [values.md](values.md): 16 MiB of blocks plus an 8 MiB ownership map, mapped RW
and never executable. Blocks have 32 bytes of metadata and round up to an
8-byte boundary. Payloads remain bounded at 1 MiB. Unreachable buffers can be
collected automatically or with `collect()`; reused contents are zero-filled.

Negative or oversized lengths, live-heap exhaustion, failed mappings, indices
outside 0 <= index < length, and byte values outside 0..255 report a runtime
diagnostic and exit 1 before access/truncation. Bytes remain fixed length;
copy into a new buffer to resize. File I/O failures use explicit status checks.

Intrinsic names are reserved for function definitions. Local names may shadow
them, in which case calls through those names are rejected. Calls check exact
types and arity and evaluate arguments from left to right.

Run make buffers for a source-scanning example: it counts digits in stored
Ramos text and returns a buffer built inside another function.

## Implementation

buffers.inc defines intrinsic signatures and static argument checking.
The retained buffer_codegen.inc emits native calls with opaque 64-bit handles, using the
existing expression stack and read-only literal fixups. buffer_runtime.inc and heap_runtime.inc
are copied with the position-independent runtime into generated executables.
Runtime register r12 tracks active Ramos calls; r13 stores heap base and
r14 stores allocated bytes. Generated functions preserve these registers.
