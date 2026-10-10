# Windows support (Ramos 0.7)

Ramos produces native Windows x64 console executables in PE32+ format. The same
language supports arithmetic, booleans, scopes, control flow, typed functions,
recursion, byte buffers, arguments and binary file I/O on Linux and Windows.
There is no interpreter, Python dependency or C runtime in generated programs.

## Use Ramos on Windows

Download `ramos.exe` from the Windows compiler artifact in the
[Self-hosting proof workflow](https://github.com/zackmsa777-a11y/ramos/actions/workflows/selfhost.yml).
Extract it and open PowerShell in that directory. Save a UTF-8 `hello.ramos`:

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
Programs are console applications; GUI/windowing bindings are future work.

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
and the buffer arena is read/write. No section is both writable and executable.
The PE advertises NX compatibility and ASLR, uses position-independent code and
contains no timestamps or build paths. The imports are Windows' built-in
`KERNEL32.dll` and `SHELL32.dll`; no compiler tool, CRT or interpreter is imported.

The private Ramos calling convention remains the same. A small native API bridge
aligns the stack and reserves Windows shadow space for system calls. Function
frames probe each stack page before reserving larger frames, preserving Windows
stack guard behavior. Arithmetic, buffer, allocation and call-depth checks remain.

Arguments use Windows' command-line parsing rules and are converted from UTF-16
to UTF-8. Paths are converted from UTF-8 to UTF-16 with invalid encodings rejected.
File reads reject non-disk files/directories and enforce the 1 MiB bound. Writes
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
