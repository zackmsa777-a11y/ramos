# Windows support (Ramos 0.15)

Ramos produces native Windows x64 console executables in PE32+ format. The same
language supports arithmetic, booleans, scopes, control flow, typed functions,
recursion, byte buffers, arguments and binary file I/O on Linux and Windows.
There is no interpreter, Python dependency or C runtime in generated programs.

## Use Ramos on Windows

Download [ramos.exe from the 0.15 release](https://github.com/zackmsa777-a11y/ramos/releases/download/v0.15.0/ramos.exe)
and open PowerShell in its directory. CI artifacts are also available from the
[Self-hosting proof workflow](https://github.com/zackmsa777-a11y/ramos/actions/workflows/selfhost.yml). Save a UTF-8 `hello.ramos`:

```text
fn main() {
    print("Hello, Windows!")
}
```

Compile and run:

```powershell
.\ramos.exe build .\hello.ramos -o .\hello.exe
.\hello.exe
```

Windows is the default target when the compiler runs on Windows. Existing output
requires `--force`. Use `.exe` for Windows output filenames. The target is x64;
32-bit Windows and a native ARM64 backend are not supported by this milestone.
Programs default to console applications. Version 0.13 adds `--gui` and the
[native desktop GUI library](gui.md); build the Notes example with:

```powershell
.\ramos.exe build .\examples\notes.ramos -o .\notes.exe --gui
.\notes.exe
```

## Cross-compile from Linux

```sh
make
./ramos build examples/hello.ramos -o hello.exe --target windows
make windows                 # build the native Windows compiler as build/ramos.exe
```

The Windows compiler can also emit Linux executables with `--target linux`.
No target assembler, linker or cross-toolchain is used to compile Ramos sources.
Only the initial assembly runtime/bootstrap audit uses GNU binutils.

## Runtime and executable format

The Ramos emitter writes PE headers, sections, imports and a relocation directory
itself. Code is read/execute, literals are read-only, import slots are read/write,
and the value heap is read/write. No section is both writable and executable.
The PE advertises NX compatibility and ASLR, uses position-independent code and
contains no timestamps or build paths. The imports are Windows' built-in
`KERNEL32.dll` and `SHELL32.dll`; no compiler tool, CRT or interpreter is imported.
GUI startup loads USER32/GDI32 from System32 through `LoadLibraryExW`; ordinary
CLI programs never initialize a GUI. Control creation and rendering use native
system calls, and the default console subsystem remains unchanged.

The private Ramos calling convention remains the same. A small native API bridge
aligns the stack and reserves Windows shadow space for system calls. Function
frames probe each stack page before reserving larger frames, preserving Windows
stack guard behavior. Arithmetic, buffer, allocation and call-depth checks remain.

Arguments use Windows' command-line parsing rules and are converted from UTF-16
to UTF-8. Paths are converted from UTF-8 to UTF-16 with invalid encodings rejected.
Whole-file `read_file` rejects non-disk files/directories and enforces the 1 MiB bound;
0.12 streams process regular files in bounded chunks. Atomic `write_file` writes
use a separate same-directory temporary file, handle partial writes, close the
file and publish it with `MoveFileExW`. Existing output requires the replacement
flag, and source/hardlink aliases are rejected even with replacement enabled.
Temporary files are cleaned up on failure. Windows output paths are made absolute
once before publication; unlike the Linux publisher, directory-handle anchoring
is not implemented. Both publishers assume the caller controls the destination
directory; neither promises crash durability.

`platform()` returns 0 on Linux and 1 on Windows. All other intrinsic signatures
remain unchanged. Windows maps OS errors into common negative statuses: -2
missing file/path, -13 access denied, -17 already exists, -22 invalid path or
source alias, -27 oversized/growing input, -36 path too long, and -5 other I/O
failures. File-operation status stays fallible. The executable flag to
`write_file` is accepted on Windows; executable format and `.exe` naming determine
how it is launched, rather than POSIX permission bits.

## Prove Windows self-hosting

Using the native compiler on Windows:

```powershell
.\ramos.exe build .\compiler\ramos.ramos -o .\stage2.exe --force
.\stage2.exe build .\compiler\ramos.ramos -o .\stage3.exe --force
(Get-FileHash .\stage2.exe).Hash -eq (Get-FileHash .\stage3.exe).Hash
```

`tools/windows_proof.py` does this, also compares the Linux-built seed with the
Windows-built stages, and runs native programs against shared language tests,
PE permissions, binary I/O, Unicode paths, arguments, source aliases, replacement,
checked runtime failures and large stack frames. CI runs it on `windows-latest`
and uploads `windows-bootstrap-proof.json` with the executable. Linux developers
can run the same harness under Wine using `make test-windows` with an isolated
`WINEPREFIX`. Wine is a development test runner; end users do not need it.

Version 0.9 adds native buffered stdin and signed decimal conversions. Console
input uses the configured input code page; redirected input preserves bytes.
See [input and conversion semantics](input-text.md).

Version 0.10 adds strings, reclaimed heap memory, structs and typed arrays with
the same contracts as Linux. See [values and memory](values.md).

Version 0.11 supports source-relative `weave` libraries and the Ramos standard
library. Extract the libraries archive before building its examples; use `/` in
directives even on Windows. See [libraries.md](libraries.md).

Version 0.12 adds regular-file streams and TUI console controls. The Windows
runtime enables VT output, reads native key events, and restores console modes
on return, exit and Ramos traps; its control callback also attempts cleanup
on OS control termination. Use Windows Terminal or a
real interactive console; redirected handles are rejected for TUI startup.
See [file tools and terminal interfaces](cli-tui.md).

Version 0.15 adds wide-API directory iteration/creation, cwd and environment
lookup, and direct native child execution. See [OS libraries](system.md) for
argument quoting, status handling, resource ownership and current limits.
