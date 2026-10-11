# Ramos 0.16: diagnostics, format and run

The compiler, formatter and compile-and-run driver are written in Ramos. The
native OS boundary only publishes a temporary executable, runs it and cleans up.
No interpreter, shell, Python, C compiler or separate backend is needed.

## Run a source file

Linux:

```sh
./ramos run examples/hello.ramos
./ramos run examples/rgrep.ramos -- needle README.md
```

Windows PowerShell:

```powershell
.\ramos.exe run .\examples\hello.ramos
.\ramos.exe run .\examples\rgrep.ramos -- needle README.md
```

`run SOURCE.ramos [-- ARG...]` compiles for the OS running the compiler, using
the same checks, source-relative `weave` loading and machine-code generation as
`build`. Program arguments follow an explicit `--`; empty arguments, spaces,
Unicode, quotes and shell metacharacters remain individual values. No shell or
PATH lookup is involved. Stdin, stdout, stderr, environment and working directory
are inherited. The compiler prints nothing on success beyond the program's output.

Use `build` for distributable executables, cross-compilation or `--gui` output;
`run` accepts none of those build options and creates no output in your project.
It waits for the program and forwards exit statuses 0..255. Larger Windows
exit codes map to 1; Linux signal termination is represented as 128 plus the
signal number. Compiler, launch or cleanup failures return 1 with an error.
`arg(0)` is the temporary executable path on Linux and `ramos-run` on Windows;
user argument values start at `arg(1)` on both platforms.

The argument limit is 256 user values and 32767 packed UTF-8 bytes. Linux counts
NUL separators; Windows counts the quoted command line including its placeholder
argument zero. Embedded NUL is rejected. All existing source, code, memory and
call-depth limits remain enforced.

### Temporary executable lifetime

Compilation finishes before any temporary executable is created. Linux uses
nonempty `TMPDIR`, otherwise `/tmp`; Windows uses `GetTempPathW` (TMP, TEMP,
USERPROFILE, then the Windows directory). The base must exist and permit directory
creation and executable launch. Each run exclusively creates its own
`ramos-run-…` directory; an existing candidate is never reused. Linux permissions
are 0700. Windows directory permissions follow the base directory's security
settings. A bounded 16 attempts avoids an unbounded collision loop.

The driver atomically publishes `app.exe` inside this directory, launches it
directly, waits, deletes the executable and removes the empty directory. The
same cleanup runs after launch/write failures and handled child runtime errors.
Cleanup errors are reported. It never recursively deletes child-created files.
Abrupt compiler termination or a machine crash can leave temporary files;
crash durability and cleanup after forced termination are not promised.

## Format a file

```sh
./ramos fmt app.ramos
./ramos fmt app.ramos --check
./ramos fmt app.ramos -o formatted.ramos
./ramos fmt app.ramos -o formatted.ramos --force
```

Use `.\ramos.exe` for the same commands in PowerShell. The default writes exact
formatted UTF-8 bytes to stdout. `--check` writes nothing and returns 0 for an
unchanged file, or reports `needs formatting: FILE` and returns 1 for a change.
Read, lexical or output errors also return 1.

`-o` writes a new non-executable file atomically. An existing destination requires
`--force`. Source identities, hardlink aliases and symlink aliases are protected
even with `--force`; failed formatting preserves an existing destination. There
is no in-place mode. Avoid redirecting stdout back to the source, because a shell
can truncate it before the compiler reads it. Prefer `-o` for a new copy.

The first formatter normalizes horizontal spacing and uses four spaces per brace
level, plus one continuation level inside multiline parentheses/brackets. It
preserves token spelling, string literal bytes, comment content (including comment
trailing spaces), and existing LF/CRLF line breaks. One-line bodies remain one
line. Nonempty input receives a final newline if missing, using the first existing
line-ending style or LF. Empty input stays empty. Formatting is idempotent.

It formats one source file without loading woven files and does not require a
`main` function. UTF-8, escapes, comment termination, NUL and token bounds are
checked; full grammar and types are checked by `build` or `run`. The input and
formatted output limits are each 1 MiB; expansion beyond the output limit fails
before publication. Statement-separating newlines inside block comments are
retained. Separate operator tokens in unfinished code stay separate.

## Read a compiler error

```text
app.ramos:2:12: error: expected bool, found int64
  |     if 123 { print(1) }
  |            ^
```

Errors retain the original woven filename, line and byte column, then show the
relevant source line and a caret. Type messages name arrays and declared structs,
for example `expected [int64], found [string]` or `expected Point, found Player`.
The caret identifies the compiler's failing token/location; it is not necessarily
the start of the expression causing a type error.

Tabs display as four spaces. Non-ASCII and control bytes display as `\xNN` so
terminal controls cannot execute and caret alignment is deterministic; Unicode
text is byte-escaped in this first preview. Long lines show at most 80 source
bytes on either side of the location, with ellipses for omitted text. Columns
remain byte-based rather than terminal display-cell positions.

## Verification and limits

The shared [development-tool tests](../tests/test_devtools.py) check caret/type
messages, original library locations, EOF/control escaping, formatter idempotence,
comments/literals/CRLF, byte-identical compiled output before/after formatting,
atomic publication and source protection, argument quoting, inherited I/O,
exit codes, temporary cleanup, error paths, repeated runs and an empty tool PATH.
The native Linux and Windows [self-hosting workflow](https://github.com/zackmsa777-a11y/ramos/actions/workflows/selfhost.yml)
runs the shared corpus and verifies byte-identical compiler fixed points.

Release validation passes **240 Linux tests** (245 discovered, five platform
skips) and **186 native Windows tests** (187 discovered, one Linux fixture
skip), with both byte-identical compiler fixed points and an empty-PATH Linux
rebuild. See [release evidence](devtools-verification.json).

See [self-hosting](self-hosting.md) for proof JSON and [the roadmap](roadmap-1.0.md)
for future work. Floats, Linux desktop GUI and `--emit-asm` are still proposals.
This release makes no comparative performance or speedup claim.
