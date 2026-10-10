# Native arguments, file I/O and stdin (0.9)

On Linux these intrinsics use x86-64 syscalls directly; on Windows they use
the native Windows API boundary described in [windows.md](windows.md). They are checked and typed in
the bootstrap and self-hosted compilers. No C library, shell, subprocess or external compiler is involved.

| Intrinsic | Signature | Behavior |
| --- | --- | --- |
| `arg_count` | `() -> int64` | argc, including the executable name |
| `arg` | `(int64) -> bytes` | fresh copy of an argument; invalid index traps |
| `read_file` | `(bytes) -> bytes` | bounded regular-file read; empty bytes on failure |
| `write_file` | `(bytes, bytes, int64) -> int64` | atomic publication; zero or negative errno |
| `read_line` | `() -> bytes` | buffered stdin line read; empty bytes on failure |
| `stdin_eof` | `() -> bool` | sticky EOF observed by a stdin read |
| `io_error` | `() -> int64` | last read/write status; zero or negative errno |
| `stderr` | `(bytes) -> void` | exact bytes to fd 2, with no added newline |
| `platform` | `() -> int64` | host OS: 0 Linux, 1 Windows |
| `exit` | `(int64) -> void` | terminate with status 0..255; invalid status traps |

On Linux, arguments are raw operating-system bytes and may be empty or invalid
UTF-8. Windows arguments are UTF-8 copies of the native UTF-16 command line.
Paths must be nonempty, shorter than 4096 bytes, and contain no NUL. All byte
buffers retain the 1 MiB payload and 16 MiB process-arena limits. Allocations
still trap on resource exhaustion; OS file failures are explicitly fallible.
`arg` returns a fresh mutable copy, not a pointer into the kernel argv stack.

On Linux, `read_file` opens with nonblocking and close-on-exec flags and checks regular-file
status before reading, so a FIFO cannot hang the program. It retries interrupted
reads, allows files that shrink, and fails if a file grows beyond its sampled
size. The limit is 1 MiB. The descriptor is closed on success and failure. A
successful empty read is distinguished from failure using `io_error()`.
The identity of the most recent successful input (device and inode) is retained
as an output safeguard. A failed read does not erase that protection.

`write_file` flags are bit 0 = executable and bit 1 = replacement. Other values
are rejected. On Linux, normal output mode is 0644 and executable output mode is 0755. Output
is first written into a private 0600 temporary file under the opened destination
directory, with an independently generated short basename. Partial writes and
EINTR are handled, permissions are set, and the closed file is published using
`renameat2`. Without replacement, `RENAME_NOREPLACE` also protects against a
concurrent destination appearing. Failures remove the temporary file and leave
existing output unchanged. Maximum-length destination basenames are supported.

Source/destination identity is checked before creation and again before
publication. Hardlink and symlink aliases to the last successful input are
rejected even with replacement enabled. This contract protects one most recent
input, not every file ever read by an application. Atomic publication is not a
power-loss durability guarantee: the implementation does not perform fsync.

Output failures from `print` or `stderr`, invalid argument indices, invalid exit
statuses and buffer misuse terminate with status 1 as in the existing runtime.

Windows preserves the signatures and bounds with UTF-8 arguments and UTF-16
path conversion. `io_error` maps Windows errors into common negative statuses.
Publication uses a same-directory temporary file and `MoveFileExW`; Windows
does not use POSIX executable permission bits. See [Windows I/O details](windows.md).

Stdin, integer/text conversion, line limits and error precedence are specified
in [input-text.md](input-text.md). Stdin reads preserve the most recent successful
file identity, and file writes do not change decimal parse status.
