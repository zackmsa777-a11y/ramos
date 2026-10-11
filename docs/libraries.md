# Simple libraries with `weave` (0.11)

Ramos uses **`weave`** to add a library at compile time. The name was chosen by
the project owner instead of the conventional `import` keyword.

```ramos
weave "stdlib/numbers.ramos"
weave "stdlib/text.ramos"
fn main() {
    print(s"Hello, " + text_repeat(s"🌍", 2))
    print(num_text(num_max(7, 42)))
}
```

A library is an ordinary UTF-8 `.ramos` source file containing functions,
structs and optional further `weave` statements. Call its functions normally.
There is no package manager, runtime module loader or separate library backend.
The Ramos-written compiler reads and lexes every source itself, then resolves
one set of typed definitions and emits one native executable.

## Resolution and names

Paths are relative to the file containing the `weave`, including inside another
library. They do not depend on the shell's current directory. Use `/` separators
on Linux and Windows. Spaces and UTF-8 names are supported. Paths must be
nonempty and relative; absolute/drive-relative paths, control characters and
backslashes in directives are rejected. `.` and `..` are normalized lexically.
The root CLI source can still use a normal absolute or relative host path.

Each normalized source path loads once, so repeated and shared dependencies
are allowed. ASCII case is folded for path comparison on Windows. Symlink
paths are not resolved to a universal canonical name; distinct alias paths can
still produce duplicate-definition errors. File identities are separately
protected against output overwrites.

Use one `weave "path.ramos"` per statement, terminated by newline or EOF.
It must occur at top level. Comments can surround it; directive-like text inside
comments/literals is ignored. Dependency cycles are compile errors with a source
location. Libraries cannot define `main`; the root executable defines it.

Definitions share one namespace. Functions/types may refer forward across
files, but duplicate names are errors. Prefix reusable library functions, as the
standard library does with `num_`, `text_`, `bytes_`, `list_` and `map_`.
Namespaces, aliases, selective exports and package registries are not part of
this small first library system. `weave` is a new reserved keyword; older user
functions/bindings using that name need renaming.

Diagnostics identify the original file, line and byte column, including lexer
and type errors inside libraries. A missing file reports the containing
`weave` site and requested path. Failed builds preserve existing output. With
`--force`, the compiler still refuses to replace any source identity it loaded,
including a source's hardlink/symlink alias.

## Standard library written in Ramos

Copy the repository's `stdlib` folder beside your program, then weave only the
files you use. Helpers are readable Ramos source; OS operations call documented
native intrinsics.
`text.ramos` itself weaves `bytes.ramos`; an explicit second weave of that file
reuses it. All functions are checked by the ordinary compiler.

| File | Helpers |
| --- | --- |
| `math.ramos` (0.18) | `math_abs`, `math_min`, `math_max`, `math_clamp`, `math_sqrt`, `math_text`; see [float contracts](math.md) |
| `numbers.ramos` | `num_min`, `num_max`, `num_abs`, `num_clamp`, `num_text`, `num_parse` |
| `text.ramos` | `text_starts`, `text_ends`, `text_find`, `text_contains`, `text_join`, `text_repeat` |
| `bytes.ramos` | `bytes_copy`, `bytes_equal`, `bytes_slice`, `bytes_put` |
| `lists.ramos` | `IntList`, `list_new`, `list_len`, `list_push`, `list_get`, `list_set`, `list_pop`, `list_clear` |
| `io.ramos` (0.12) | Streamed readers, lines, seeking, copy |
| `cli.ramos` (0.12) | Argument/option scan helpers |
| `tui.ramos` (0.12) | Full-screen terminal, colors, cursor, boxes and key input |
| `gui.ramos` (0.13) | Native Windows desktop controls and events |
| `system.ramos` (0.15) | Cwd/environment results, directory iteration and creation |
| `path.ramos` (0.15) | Lexical path joining, names and rooted-path checks |
| `process.ramos` (0.15) | Typed direct child execution and exit/OS status |
| `maps.ramos` | `StringMap`, `map_new`, `map_len`, `map_has`, `map_get`, `map_set`, `map_remove` (plus `map_index`) |

Number operations keep checked int64 semantics: `num_abs(INT64_MIN)` traps.
`num_parse` uses `text_to_int` and leaves its status in `parse_error()`; always
check that status before using the result. `num_clamp` rejects reversed bounds.

Text indices count Unicode scalars. `text_find` returns -1 for a missing match
and 0 for an empty needle; empty prefixes/suffixes match. Search uses a simple
scan and can be quadratic. Join/repeat allocate one result byte buffer and copy
pieces into it, then validate/copy into an immutable string. Output still has a
1 MiB payload cap. Repeat rejects negative counts; an empty string repeats to
empty even for a large count.

Byte slicing uses `[start, end)`. `bytes_put(destination, start, source)` checks
the destination range and copies forward; overlapping ranges are not a memmove
operation. String conversions and byte copies produce independent storage.

Lists hold integers, enforce logical bounds, and grow capacity by doubling
starting at four. `list_pop` rejects an empty list; `list_clear` retains capacity.
The array limit bounds capacity at 131072 elements, subject to the live heap.
List handles alias, so changes through one alias are visible through another.

Maps hold string keys and string values. Keys compare by contents; set replaces
an existing value without increasing length. `map_get(map, key, fallback)` avoids
null or unchecked missing-value defaults. Remove returns bool and releases the
removed references, using the final entry to fill the gap. Iteration order is
not promised. Lookup is linear; capacity doubles starting at four. Keys and
values are immutable strings; map handles alias. Treat collection metadata
fields as implementation state and mutate through the helper functions.

Contract violations in pure helpers print a diagnostic and exit 1; expected
OS failures in I/O and system/process libraries return explicit statuses. Ordinary arithmetic, array
bounds, allocation and UTF-8 checks retain the native Ramos traps. The standard
library introduces no unbounded allocator or relaxed safety mode.

## Run and install

```sh
make library-demo
./ramos build examples/library_demo.ramos -o library-demo --target windows
```

The release's `ramos-0.11.0-libraries.zip` contains both compilers, `stdlib/`,
`examples/library_demo.ramos` and this guide. Extract the whole archive so
source-relative paths keep working. On Windows:

```powershell
.\ramos.exe build .\examples\library_demo.ramos -o .\library-demo.exe
.\library-demo.exe
```

`make install` installs the compiler and library files to
`PREFIX/share/ramos/stdlib` (default `/usr/local/share/ramos/stdlib`). Copy that
folder into a project's source tree. There are no implicit search paths or
machine-specific paths embedded in binaries.

## Checked limits and proof

A build allows at most 64 source files including the root, 1 MiB of combined
source including boundary separators, and 50,000 lexical tokens including EOF.
Each normalized path is at most 4095 bytes/512 components; all stored paths
share a 41900-byte pool. Existing function, struct, declaration, output and
runtime limits still apply. Dependencies are processed with an explicit queue,
so a 63-library chain does not consume recursive loader call depth.

The compiler stores source spans/path metadata alongside its token tables.
The internal `_protect_input()` binding records up to 64 successfully read file
identities in a heap-rooted table; the native atomic publisher checks all of
them before writing. This binding is reserved compiler machinery, not a stable
standard-library API. Ordinary `read_file` programs keep their previous contract
unless that internal guard is invoked.

The retained assembly seed still has the older surface grammar. The compiler
source stays compatible with that grammar and implements `weave` directly in
Ramos. Library tests run on both self-hosted Linux stages and native Windows.
Bootstrap fixed points and embedded OS-boundary bytes remain audited. Saved
0.7.1 speed tables are historical; this release makes no new speed claim.

[Native CI](https://github.com/zackmsa777-a11y/ramos/actions/runs/38043340397)
passed 164 Linux tests and 114 Windows tests. See
[recorded validation](libraries-verification.json), [Linux proof](bootstrap-proof.json)
and [Windows proof](windows-bootstrap-proof.json).

Version 0.12 expands the bundle with [CLI and TUI libraries](cli-tui.md).

See [0.15 OS contracts](system.md) for the new system, path and process helpers.

## Reusable text assembly (0.17)

The existing `text.ramos` library now provides `TextBuilder` for appending checked
UTF-8 pieces, immutable snapshots, capacity reuse and dropping backing storage.
See [complete ownership/limit contracts and a streamed file tool](text-builder.md).
