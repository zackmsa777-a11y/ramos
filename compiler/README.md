# Compiler written in Ramos

`ramos.ramos` is the executable compiler source. It has no generated
host-language parser. `main` calls `load_sources` (native reads, UTF-8 validation
and per-file lexing), `records`, `discover`,
`functions`, and `elf`, then publishes the binary with `write_file`.

The lexer keeps source spans in a token table and validates string escapes.
A signature pass permits forward and mutual calls. The parser checks types and
lexical scope while emitting instructions. Expressions use a shunting-yard
operator stack, typed value stack and call markers; blocks use explicit records
for scope restoration, branches, loops and guaranteed returns. Fixups resolve
function calls, branch labels and read-only literal addresses after emission.

The ABI matches the bootstrap: arguments are pushed left to right, a call creates
an independent rbp-relative frame, the callee copies parameters into immutable
local slots, and the caller removes argument slots. Expression values use native
pushes and pops, with immediate push/consume pairs removed when RAX is still live. Functions preserve process registers for call depth, buffer
allocation and argv/I/O state. Arithmetic remains checked.

## Packed representation

The compiler preserves seed-compatible byte-buffer source and uses signed 32-bit
cells for metadata with checked native int64 operations. Values requiring all
64 bits are parsed from source and emitted directly as little-endian immediates.
There are no handle-to-integer conversions or forged buffer pointers.

| Buffer | Layout |
| --- | --- |
| `s` | combined source, at most 1 MiB including boundary separators |
| `c` | 1 MiB compiler state and tables |
| `o` | 1 MiB generated executable arena |
| `d` | 1 MiB decoded literal bytes |
| `f` | 1 MiB fixups and label offsets |

`c` byte offsets: scalar state 0..255; 256 function records of 256 bytes at 256;
4,096 active symbol records of 24 bytes at 70,000; at most 50,000 token records
of 12 bytes at 200,000; 64 source records of 32 bytes at 801,000; path bytes
at 803,100..844,999; dependency edges at 845,000..849,095; 128 block records of 40 bytes at 850,000; type stack at
900,000; 64 struct records of 512 bytes at 857,000; operator/call records of 24 bytes at 910,000. Each region ends before
the next. Function parameters occupy sixteen 12-byte records at record offset
64. The symbol counter also tracks 4,096 total declarations across all functions.

Scalar state cell indices: 0 current token, 1 token count, 2 function count,
3 main function index, 4 output cursor, 5 fixup count, 6 label count, 7 active
symbols, 8 total declarations, 9 frame slots, 10 block depth, 11 operators,
12 expression types, 13 expression nesting, 14 decoded-data length, 15 diagnostic
source override, 16 selected target (0 Linux, 1 Windows), 17 literal-end cursor,
18 nonnegative int32 RHS literal value, 19 removable value-push end cursor,
20 struct count, 21 source count, 22 path-pool cursor, 23 combined-source bytes,
24 aggregate lexical-token count.
Token kinds preserve the bootstrap constants. Types are
0 int64, 1 bool, 2 void, 3 bytes, 4 string, 1000 + struct index; an array
adds 100000 to its element type (at most 16 levels). IDs 256..283 and 289 identify
public intrinsics; 290 is the compiler-only `_protect_input` binding;
512 + struct index identifies a constructor. Private runtime
aggregate helper offsets are never exposed as callable source intrinsics.

`f` holds up to 40,000 12-byte fixup records at zero and up to 40,000 4-byte label
positions at 600,000. Fixup kinds are 1 function, 2 branch, 3 literal. All rel32
values are emitted deterministically; paths and timestamps are not embedded.

Nesting is checked at 128, functions at 256, parameters at 16, and final output
including ELF/PE alignment and string data at 1 MiB. The bootstrap retains its
older 4 MiB output and postfix IR representation. Different resource limits do
not change accepted programs' runtime semantics.

## Native runtime data

`runtime_text` and `entry_text` contain position-independent x86-64 bytes; the
small address helper functions expose only emitter offsets. These are the native
OS/runtime boundary, not compilation logic. `tools/bootstrap_proof.py` checks
the bytes and offsets against the original assembly runtime on every proof.
Changes to the runtime must update those literals and constants together. Keep
the assembly compiler under `bootstrap/` as a reproducible recovery source.

## Windows target

The parser and instruction selection are shared with Linux. `native_address`
and `native_builtin` select runtime entry offsets using state cell 16. `pe`
writes a PE32+ console image with 4096-byte file/section alignment: `.text` RX,
`.rdata` R, `.idata` RW at RVA 0x200000, and `.reloc` R at RVA 0x201000. Relative
code/literal offsets keep identical file offsets and RVAs. The import table's
fixed RVA lies beyond the bounded 1 MiB output arena, avoiding extra fixups.
The read-only section zero-fills the virtual space up to the import table so
section RVAs remain adjacent, as required by the Windows loader.
All code is position-independent; the relocation directory has only ABSOLUTE
padding entries, so there are no absolute code addresses to relocate.

`bootstrap/windows/runtime.s` implements the private-ABI Windows OS boundary.
`tools/runtime_data.py` reproducibly generates or checks the Linux/Windows
embedded bytes, native API imports and offsets. It is an audit tool, never a
backend used to compile Ramos programs. After changing an OS boundary, run
`python3 tools/runtime_data.py --write` followed by both bootstrap proofs.

## Instruction selection

Version 0.7.1 specializes positive constant division/remainder and immediate
arithmetic, removes local stack transfers and inlines checked buffer accesses.
See [the transformations and correctness argument](../docs/optimization.md).

## Comments, diagnostics and boolean branches

Version 0.8 recognizes line and non-nesting block comments while retaining their
newlines. Logical operators use token kinds 43/44. In operator records, field 16
holds the source byte offset for diagnostics; logical records use fields 4/8
for the short-circuit and merge labels (call records retain their own ID/count
meanings). The left value is consumed before the RHS is emitted; both paths
merge with one bool value. All label marks clear the removable-push record.
See [semantics and proof](../docs/usability.md).

## Stdin and decimal text

Version 0.9 adds five typed native intrinsics (IDs 268..272). `decimal` now uses
`int_to_text`, so the compiler exercises its own conversion API. Shared assembly
in `bootstrap/src/text_runtime.inc` handles decimal formatting/parsing and line
assembly; each OS supplies only scratch allocation and buffered read boundaries.
The process-state block is 128 bytes: offsets 48/56/64 hold parse status, sticky
stdin EOF and the lazy scratch pointer; Windows temporary-file uniqueness uses
its separate counter at 72. Existing argv and file identity fields are retained.
See [input/text semantics](../docs/input-text.md).

## Managed values

Version 0.10 adds token kinds 45..50 for string/struct, dot, brackets and string
literals. Struct discovery registers all names before resolving fields. Struct
records contain name spans, field count, definition token bounds and up to sixteen
field records. Operator/call record field 20 carries a typed-array result/element
type while arguments are checked; indexing uses its own delimiter marker.

The private native `heap_runtime.inc` and `values_runtime.inc` are shared by both
OS boundaries. Heap handles preserve the original length-at-handle/data-at-+8 ABI.
Physical block headers are 32 bytes; a uint32 ownership map resolves conservative
roots, including interior pointers. A cached next block accelerates allocation;
a complete scan and collection/retry handle fragmentation and exhaustion.
Generated frames start zeroed and ended scopes clear locals. Process-state offset
80 stores the allocation cursor. See [semantics and limits](../docs/values.md).

## Source libraries

Version 0.11 adds `weave` token kind 51. `load_sources` uses a bounded breadth-first
queue and dependency graph, lexes each normalized source path once, removes only
top-level directives from the merged token stream, and keeps each token's original
source span. Source records store begin/end offsets, path span, loaded state,
parent ID and requesting directive offset. `fail` translates combined offsets
back to the source's filename/line/byte column, including boundary positions.

The 1 MiB scratch lexer state is reused across files. Source paths and all limits
are checked before copies. Cycles are rejected through explicit graph reachability;
loader depth never consumes Ramos recursion. Libraries have no runtime initialization
or separate ABI. The standard library files are ordinary checked Ramos source.
Process-state offsets 88/96 hold the protected-input handle/count. The collector
roots that handle, and both native publishers compare destination identities
against the complete registered table. See [contracts](../docs/libraries.md).
