# Paths, directories, environment and child processes (0.15)

These APIs run natively on Linux x64 and Windows x64. Libraries are ordinary
Ramos source; weave only what you need. Compiled programs require no Python,
C compiler, shell or separate Ramos runtime.

## A small directory tool

```ramos
weave "stdlib/system.ramos"
weave "stdlib/path.ramos"
fn main() {
    let directory = directory_open(".")
    if directory.status != 0 { stderr("cannot open directory\n")
        exit(1) }
    while !directory.end {
        let entry = directory_next(directory)
        if !entry.end { print(path_join_bytes(".", entry.name)) }
    }
    let read_status = directory.status
    let close_status = directory_close(directory)
    if read_status != 0 || close_status != 0 { exit(1) }
}
```

`Directory` contains `handle`, `status`, `end`. `DirectoryEntry` contains
`name: bytes`, `kind: int64`, `end: bool`, `status: int64`. Kinds are 1 regular
file, 2 directory, 3 symbolic link / Windows reparse point (including junctions),
4 other, 0 no entry. Entries omit `.` and `..`; order is unspecified. A name is
one component, with no appended separator. An empty successful result ends
iteration. The iterator owns one OS handle and an 8 KiB buffer, irrespective
of directory size. Always close, including after early termination or error.
Garbage collection reclaims memory; it does not close OS handles.

`directory_create(path: bytes) -> int64` creates one new directory: parents
must already exist, and an existing destination returns -17. Linux uses mode
0755 subject to the process umask; Windows uses inherited security defaults.
No permission preservation or recursive creation is implied.

Low-level intrinsics:

| Signature | Result |
| --- | --- |
| `cwd() -> bytes` | Current working directory; empty on error |
| `env_get(name: bytes) -> bytes` | Inherited environment value; empty on missing/error or empty success |
| `dir_open(path: bytes) -> int64` | Positive iterator ID, or negative error |
| `dir_next(handle: int64) -> bytes` | Next name; empty on EOF/error |
| `dir_kind(handle: int64) -> int64` | Kind of latest returned entry, zero without an entry |
| `dir_close(handle: int64) -> int64` | Zero success or negative error; retires a valid ID even on close failure |
| `dir_create(path: bytes) -> int64` | Zero success or negative error |

All overwrite `io_error()` with zero on success or a negative status on error.
Capture it before another I/O operation. Directory IDs use the same increasing
generation counter as file streams, with separate lookup tables: file and
directory handles cannot be substituted. Closed IDs remain invalid after slot
reuse. There are 64 concurrently open directories, separately from 64 file
streams. Limit exhaustion is fallible (-24); invalid handles return -9.

Paths must be nonempty, NUL-free and at most 4095 input bytes. Windows validates
UTF-8 and uses wide APIs; Linux preserves arbitrary filename bytes. Host Windows
path-length and filesystem restrictions still apply; this release does not add
an extended-path prefix or a long-path opt-in manifest. A caller-supplied root
path may follow a link. Entries themselves are classified without following links.
Linux resolves unknown entry kinds with `fstatat(..., AT_SYMLINK_NOFOLLOW)`.
Missing paths return -2, non-directories -20, access denied -13; other native
Linux errno values are preserved. Windows maps unclassified failures to -5.

## Path helpers and environment

`stdlib/path.ramos` provides `path_join(parent: string, child: string) -> string`,
`path_name(path: string) -> string`, `path_absolute(path: string) -> bool`, and
byte-preserving counterparts `path_join_bytes`, `path_name_bytes`,
`path_absolute_bytes`. These helpers are lexical: no filesystem access or `..`
normalization. A rooted child replaces its parent; joining an empty child
returns the parent. Linux recognizes `/`; Windows also recognizes `\` and
`C:/...`. Windows rooted paths such as `/x` are drive-rooted, and `C:file` stays
drive-relative: `path_absolute` means rooted, not a canonical full path.
`path_name` strips trailing separators and returns the last component; a root
made only of separators has an empty name. Generic helpers retain the ordinary
1 MiB value limit; native OS calls enforce their narrower path limits.

`stdlib/system.ramos` provides `system_cwd() -> SystemValue` and
`system_env(name: string) -> SystemValue`, with `value: bytes` and `status: int64`.
Missing environment names return -2; an existing empty value has status zero.
Empty names, embedded NUL and `=` are invalid (-22). Values are limited to
32767 bytes (-27 when exceeded); Linux names over 32767 bytes are invalid,
Windows oversized UTF-8 name input returns -27. Lookup follows native OS case
rules (case-sensitive Linux, case-insensitive Windows). Values remain bytes;
call `string(result.value)` when UTF-8 is required. No environment setter is
introduced; children inherit the parent environment.

## A direct command runner

```ramos
weave "stdlib/process.ramos"
fn main() {
    let arguments = array(string, 1, s"--version")
    let result = process_run(string(arg(1)), arguments)
    if result.status != 0 { stderr("cannot start or wait for process\n")
        exit(1) }
    print(result.code)
}
```

`process_run(executable: string, arguments: [string]) -> ProcessResult` waits
synchronously and returns `code: int64`, `status: int64`. Success has status zero,
even when the child exits nonzero. OS failure has negative status and code -1.
On Linux, normal exit codes are 0..255 and signal termination maps to 128+signal.
Windows returns the unsigned 32-bit process exit code in int64.

Supply an executable path, with `.exe` on Windows. No PATH search, shell,
command-string evaluation, implicit interpreter or batch-file handling is added.
The child inherits cwd, environment, stdin/stdout/stderr. Existing redirection
and pipes on those standard streams work; output streams are not captured in
managed memory. Nonstandard Ramos file/directory handles are not inheritable.
Close active TUI/GUI state before running an interactive child. There is no
asynchronous spawning, process cancellation, redirection API or timeout yet.

Arguments preserve Unicode, empty values, spaces, tabs, quotes, backslashes and
shell characters as values. Embedded NUL returns -22. The limit is 256 argument
values, plus argv[0], and 32767 packed UTF-8 bytes; exceeding the public library
limit returns -7. On Windows this count includes executable quoting, spaces and
escaping, and UTF-16 conversion is also bounded. Quoting follows the
[Microsoft CRT argument rules](https://learn.microsoft.com/en-us/cpp/c-language/parsing-c-command-line-arguments)
and is tested with Ramos and Python children. A Windows child with its own
nonstandard parser may interpret its command line differently.

The internal `_process_run(executable: bytes, packet: bytes)` is an OS boundary,
not the library contract. Linux packets are NUL-separated arguments with a final
NUL (empty packet means no arguments). Windows packets contain the fully quoted
UTF-8 command line including argv[0]. Prefer the typed `process_run` helper.
Linux uses fork/execve/wait4 and a close-on-exec pipe so exec failures cannot be
confused with child exit 127. Windows uses explicit `lpApplicationName` with
[CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw),
waits, reads the exit code and closes both returned handles.

## Run the real tools

```sh
./ramos build examples/rfind.ramos -o rfind
./rfind ./examples .ramos
./ramos build examples/rrun.ramos -o rrun
./rrun /bin/echo "one argument" "; still one argument"
./ramos build examples/rcopy.ramos -o rcopy
./rcopy large-input.bin new-copy.bin
```

```powershell
.\ramos.exe build .\examples\rfind.ramos -o .\rfind.exe
.\rfind.exe .\examples .ramos
.\ramos.exe build .\examples\rrun.ramos -o .\rrun.exe
.\rrun.exe .\ramos.exe --version
```

`rfind` searches regular-file names recursively using an iterative work stack,
holding only one directory handle at a time. Links, junctions and other entries
are skipped. The root may be an explicitly supplied link. At most 8192 pending
directories are retained, subject to the existing live heap; errors exit 2.
Traversal is not a snapshot or a security boundary: another process changing a
path between listing and opening can change what is visited. `rrun` forwards
child exit codes up to 255, maps larger Windows codes to exit 1, and exits 2 on
usage or spawn/wait errors. `rcopy` remains the streamed, exclusive-create file
copy tool; this milestone does not claim a recursive backup or metadata copier.

Verification includes multichunk iteration across garbage collection, early
close, generation/capacity checks, Unicode directory creation, junction/symlink
cycles, exact child arguments, inherited streams/environment and child failures.
See [release evidence](system-verification.json), [Linux bootstrap proof](bootstrap-proof.json)
and [Windows bootstrap proof](windows-bootstrap-proof.json). Historical 0.14
benchmark scores are not performance measurements of 0.15; no speedup is claimed.
