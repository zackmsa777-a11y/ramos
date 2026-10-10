# Native arguments and file I/O (0.6)

These intrinsics use Linux x86-64 syscalls directly. They are checked and typed in
both compilers. No C library, shell, subprocess or external compiler is involved.

| Intrinsic | Signature | Behavior |
| --- | --- | --- |
| `arg_count` | `() -> int64` | argc, including the executable name |
| `arg` | `(int64) -> bytes` | fresh copy of an argument; invalid index traps |
| `read_file` | `(bytes) -> bytes` | bounded regular-file read; empty bytes on failure |
| `write_file` | `(bytes, bytes, int64) -> int64` | atomic publication; zero or negative errno |
| `io_error` | `() -> int64` | last read/write status; zero or negative errno |
| `stderr` | `(bytes) -> void` | exact bytes to fd 2, with no added newline |
| `exit` | `(int64) -> void` | terminate with status 0..255; invalid status traps |

Arguments are raw operating-system bytes and may be empty or invalid UTF-8.
Paths must be nonempty, shorter than 4096 bytes, and contain no NUL. All byte
buffers retain the 1 MiB payload and 16 MiB process-arena limits. Allocations
still trap on resource exhaustion; OS file failures are explicitly fallible.
`arg` returns a fresh mutable copy, not a pointer into the kernel argv stack.

`read_file` opens with nonblocking and close-on-exec flags and checks regular-file
status before reading, so a FIFO cannot hang the program. It retries interrupted
reads, allows files that shrink, and fails if a file grows beyond its sampled
size. The limit is 1 MiB. The descriptor is closed on success and failure. A
successful empty read is distinguished from failure using `io_error()`.
The identity of the most recent successful input (device and inode) is retained
as an output safeguard. A failed read does not erase that protection.

`write_file` flags are bit 0 = executable and bit 1 = replacement. Other values
are rejected. Normal output mode is 0644, executable output mode is 0755. Output
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
