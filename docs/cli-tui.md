# File tools and terminal interfaces (0.12)

Ramos 0.12 adds streamed regular-file I/O, exact stdout, command-line helpers,
and a terminal UI library written in Ramos. These are concrete building blocks
for native CLI tools on Linux and Windows x64. The compiler remains self-hosted
and emits ELF/PE directly.

## Run the tools

Extract the complete `ramos-0.12.0-cli-tui.zip` archive; keep `stdlib/` beside
`examples/`. On Linux:

```sh
chmod +x ramos-linux-x86_64
./ramos-linux-x86_64 build examples/rcopy.ramos -o rcopy
./ramos-linux-x86_64 build examples/rgrep.ramos -o rgrep
./ramos-linux-x86_64 build examples/rview.ramos -o rview
./rcopy source.bin new-copy.bin
./rgrep needle README.md
./rview README.md
```

On Windows (PowerShell, in a real console or Windows Terminal):

```powershell
.\ramos.exe build .\examples\rcopy.ramos -o .\rcopy.exe
.\ramos.exe build .\examples\rgrep.ramos -o .\rgrep.exe
.\ramos.exe build .\examples\rview.ramos -o .\rview.exe
.\rcopy.exe .\source.bin .\new-copy.bin
.\rgrep.exe needle .\README.md
.\rview.exe .\README.md
```

In a repository checkout, `make cli-tools` builds all three under `build/`.
`--help` describes each tool. Copy refuses an existing destination. Search is a
literal byte-pattern search, prints `file:line:contents`, accepts multiple files
and `--` before its pattern, and uses exit 0 for matches, 1 for none, 2 for errors.
It preserves NUL/invalid UTF-8 in matching lines. Viewer shows a colored frame,
filename, highlighted selection and page/line status. Arrows or j/k select a
line, Space/n/PageDown advances, p/PageUp goes back, Home/End selects the page's
first/last line, and q/Escape exits. Ctrl+C exits 130.

Viewer reads pages of twenty lines and retains only the displayed page, input
chunk and a bounded list of page offsets; it seeks when going back. It adjusts
the viewport when resized. File contents are clipped to 240 bytes per displayed
line; control/non-ASCII bytes become `?`, preventing embedded terminal escapes
from taking over the screen. This first example uses an ASCII preview; the TUI
library itself can write UTF-8 strings. Lines above 1 MiB report an error. The
page-index limit is 131072 entries, subject to the existing live heap limit.

## Native stream API

Paths are `bytes`, with the existing nonempty/no-NUL/4095-byte contract. Linux
accepts host path bytes; Windows validates UTF-8 and converts to UTF-16. Stream
IDs are positive opaque generation numbers, not OS descriptors or addresses.
At most 64 streams can be open. Closed IDs cannot act on a reused slot.

| Intrinsic | Signature | Result |
| --- | --- | --- |
| `stdout` | `(bytes) -> int64` | Exact bytes, no added newline; zero or negative status |
| `file_open` | `(bytes, int64) -> int64` | Positive ID or negative status |
| `file_read` | `(int64, int64) -> bytes` | Up to requested bytes; check `io_error()` |
| `file_write` | `(int64, bytes) -> int64` | Full-buffer write; zero or negative status |
| `file_eof` | `(int64) -> bool` | Sticky EOF observed by a positive-size read |
| `file_seek` | `(int64, int64) -> int64` | Absolute nonnegative read offset, or negative status |
| `file_close` | `(int64) -> int64` | Close once; zero or negative status |

Open modes are 0 read-only, 1 create a **new** write-only file, 2 write-only append
(create if missing). Reads/seek/EOF require read mode; writes require write mode.
Non-regular files/directories are rejected. Linux opens nonblocking/close-on-exec
and validates file type, so a FIFO cannot block. Each read is 0..1 MiB; a file's
total size is not capped at 1 MiB. Short reads are allowed. Zero-length reads do
not observe EOF. A positive-size zero-byte read sets EOF; a successful seek
clears it. EOF is observed by reading, not predicted from a sampled file size.

All stream operations update `io_error()`, including successful EOF checks.
Invalid IDs or wrong modes report -9, invalid counts/offsets/modes -22, and a
full registry -24. Other OS failures use negative statuses; Windows retains
its common error mapping. Parse status remains independent. Close retires the
ID even if the OS reports an error, preventing double-close/reuse mistakes.
Applications must close resources; memory collection does not close a stream.
The operating system releases remaining handles when the process ends.

Append and `write_file` replacement reject identities of **all active input
streams**, the last successfully opened/read input and compiler-protected source
files. That includes hardlink aliases. Closing an input removes its active-stream
protection; most-recent-input protection remains. Creation never truncates an
existing file. Callers control the destination directory, as with existing I/O.

Streaming writes are immediate, not atomic transactions. A failed copy may
leave a partial **new** destination; `rcopy` reports this and exits 1. Existing
`write_file` remains the atomic bounded publisher, with its old flags and
failure-preservation contract. `read_file` keeps its 1 MiB whole-file limit.
Linux ignores SIGPIPE so fallible stdout can report -32; existing print/stderr
still exit 1 when writing fails. Neither API promises power-loss durability.

```ramos
fn main() {
    let input = file_open(arg(1), 0)
    if input < 0 { exit(1) }
    var done = false
    while !done {
        let chunk = file_read(input, 65536)
        if io_error() != 0 { file_close(input)
            exit(1) }
        if buffer_len(chunk) == 0 { done = true }
        else { if stdout(chunk) != 0 { file_close(input)
            exit(1) } }
    }
    if file_close(input) != 0 { exit(1) }
}
```

## Ramos libraries

`weave "stdlib/io.ramos"` supplies `FileReader`, `io_reader(path)`, `io_byte`,
`io_line`, `io_seek`, `io_close` and `io_copy(source, destination)`. A reader
keeps a 64 KiB chunk and exposes `status`, `eof` and consumed-byte `offset`.
`io_line` strips LF/CRLF, preserves other bytes, and grows a bounded byte builder.
An oversized line is drained and reports -27; another `io_line` recovers. OS
errors remain sticky until a successful seek. Check reader status immediately;
process a nonempty final line even when EOF is true. `io_copy` returns its first
failure rather than relying on a later native operation's global status.
`bytes_find(haystack, needle)` adds literal binary search (0 for empty, -1 absent).

`weave "stdlib/cli.ramos"` adds `cli_arg`, `cli_has`, `cli_value` and `cli_fail`.
The first three use UTF-8 strings. `cli_has` checks an exact option name;
`cli_value` accepts `--name=value` or `--name value`, returns a supplied fallback,
and exits 2 for a missing value. Both stop at `--`. These scan helpers are not a
schema parser: the application checks unknown options and positional arguments.
For arbitrary Linux argv/path bytes, use `arg` directly, as the file tools do.

## TUI API and lifecycle

```ramos
weave "stdlib/tui.ramos"
fn main() {
    if tui_begin() != 0 { stderr("interactive terminal required\n")
        exit(1) }
    tui_color(6, 0)
    tui_box(1, 1, 40, 8)
    tui_at(3, 3, s"Hello from Ramos")
    tui_at(6, 3, s"Press q to quit")
    var done = false
    while !done {
        let key = tui_key(100)
        if io_error() != 0 { tui_end()
            exit(1) }
        if key == 113 || key == 27 || key == 3 { done = true }
    }
    if tui_end() != 0 { exit(1) }
}
```

`tui_begin` starts native terminal input and enters an alternate screen, hides
the cursor and clears. `tui_end` resets color/cursor/screen and restores saved
native input/output modes; stopping twice succeeds. Additional helpers:
`tui_write`, `tui_at(row,column,text)`, `tui_move`, `tui_color(fg,bg)`, `tui_reset`,
`tui_clear`, `tui_box(row,column,width,height)`, `tui_safe(bytes,width)` and
`tui_key(timeout_ms)`. Coordinates are 1-based. Colors 0..7 are black, red, green,
yellow, blue, magenta, cyan, white. Text does not add a newline. Callers clip
layout to the screen; Unicode scalar length is not terminal display-cell width.

Native primitives are `terminal_start/stop() -> int64`,
`terminal_width/height() -> int64`, and `terminal_key(timeout_ms) -> int64`.
Start requires both stdin and stdout to be interactive; failure preserves
existing modes. Starting twice reports -16. Dimensions report zero with a
negative I/O status when unavailable. A key timeout is -1 with status zero;
a read failure is -1 with negative status. Timeout is -1 (block) or
0..2147483647 milliseconds. Calling key input without start reports -25.

The first key contract supports ASCII/control keys and navigation. Linux's
native primitive returns input bytes; `tui_key` decodes common VT arrow,
Home/End/Page/Delete sequences with a 30 ms escape-sequence grace period.
Windows reads native key-down console events and maps navigation directly.
Codes: Up 256, Down 257, Right 258, Left 259, Home 260, End 261, PageUp 262,
PageDown 263, Delete 264; Escape 27, Enter 13, Ctrl+C 3. Non-ASCII Windows text
input is ignored; Linux non-ASCII bytes are not assembled into Unicode keys.
Unknown/incomplete escape sequences return Escape and may consume their prefix.
Do not mix this input with `read_line` or another stdin reader.

Normal return, explicit exit and Ramos runtime traps restore the terminal.
Linux also restores on SIGHUP/SIGINT/SIGTERM; Windows installs a console control
handler that attempts cleanup on OS control termination (tested with Ctrl+Break). Ctrl+C is delivered as a key during raw
input, so a custom TUI must handle it (the viewer does). Uncatchable termination
such as SIGKILL cannot run cleanup. Applications must be foreground terminal
processes. Suspended/background terminal job control is not implemented here.

Linux uses [tty ioctls](https://man7.org/linux/man-pages/man2/TCGETS.2const.html)
and poll/read syscalls. Windows uses
[console modes](https://learn.microsoft.com/en-us/windows/console/setconsolemode),
[key events](https://learn.microsoft.com/en-us/windows/console/key-event-record-str)
and console control callbacks. There is no curses dependency, delegated renderer,
GUI toolkit or runtime host language. TUI means a terminal interface; desktop
windows/widgets require a future API.

## Verification and remaining work

The corpus includes a 25.6 MB binary copy, large multi-file search, aliases,
64-slot exhaustion/generation reuse, 2,000 opens across collections, exact line
limits/recovery and status/type errors. Real Linux pseudo-terminals verify
input, arrows, Escape, timeouts, navigation, Ctrl+C, SIGTERM and cleanup after
normal return, explicit exit and native traps. Native Windows CI additionally
creates isolated consoles, observes drawing, injects a key event and checks
restored modes after exit/traps and a control event. Saved results are in
[cli/tui verification](cli-tui-verification.json) and the bootstrap proof files.

This milestone makes file-processing CLI tools and keyboard-driven terminal
interfaces runnable. Further practical-language work remains: syntax
conveniences, reviewed recursion/stack budgets, directory/environment/process
APIs, richer diagnostics, floats, generic collections and packaging/tooling.
See [the staged roadmap](next-goal.md). No new speed comparison is claimed.

[Native release CI](https://github.com/zackmsa777-a11y/ramos/actions/runs/38051519258)
passed: 192 Linux tests discovered, 190 passed and two Windows-only checks
skipped; 134 native Windows tests passed, including both isolated-console
checks. Both self-hosting targets reached their byte-identical fixed points.
