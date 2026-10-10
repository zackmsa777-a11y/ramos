# Compiler written in Ramos

`ramos.ramos` is the executable compiler source. It has no imports or generated
host-language parser. `main` calls `read_file`, `utf8`, `lex`, `discover`,
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
pushes and pops. Functions preserve process registers for call depth, buffer
allocation and argv/I/O state. Arithmetic remains checked.

## Packed representation

The language currently has byte buffers, so the compiler uses signed 32-bit
cells for metadata with checked native int64 operations. Values requiring all
64 bits are parsed from source and emitted directly as little-endian immediates.
There are no handle-to-integer conversions or forged buffer pointers.

| Buffer | Layout |
| --- | --- |
| `s` | input source, at most 1 MiB |
| `c` | 1 MiB compiler state and tables |
| `o` | 1 MiB generated executable arena |
| `d` | 1 MiB decoded literal bytes |
| `f` | 1 MiB fixups and label offsets |

`c` byte offsets: scalar state 0..255; 256 function records of 256 bytes at 256;
4,096 active symbol records of 24 bytes at 70,000; at most 50,000 token records
of 12 bytes at 200,000; 128 block records of 40 bytes at 850,000; type stack at
900,000; operator/call records of 24 bytes at 910,000. Each region ends before
the next. Function parameters occupy sixteen 12-byte records at record offset
64. The symbol counter also tracks 4,096 total declarations across all functions.

Scalar state cell indices: 0 current token, 1 token count, 2 function count,
3 main function index, 4 output cursor, 5 fixup count, 6 label count, 7 active
symbols, 8 total declarations, 9 frame slots, 10 block depth, 11 operators,
12 expression types, 13 expression nesting, 14 decoded-data length, 15 diagnostic
source override, 16 selected target (0 Linux, 1 Windows). Token kinds preserve the bootstrap constants. Types are
0 int64, 1 bool, 2 void, 3 bytes. Callable IDs 256..267 identify OS/buffer intrinsics.

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
All code is position-independent; the relocation directory has only ABSOLUTE
padding entries, so there are no absolute code addresses to relocate.

`bootstrap/windows/runtime.s` implements the private-ABI Windows OS boundary.
`tools/runtime_data.py` reproducibly generates or checks the Linux/Windows
embedded bytes, native API imports and offsets. It is an audit tool, never a
backend used to compile Ramos programs. After changing an OS boundary, run
`python3 tools/runtime_data.py --write` followed by both bootstrap proofs.
