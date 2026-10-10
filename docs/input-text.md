# Stdin and decimal text (0.9)

These typed native intrinsics work in Linux ELF and Windows PE programs. They
use the existing `bytes`, `int64` and `bool` types; no new syntax or dependencies.

| Intrinsic | Signature | Behavior |
| --- | --- | --- |
| `read_line` | `() -> bytes` | Read one line from stdin, removing LF or CRLF |
| `stdin_eof` | `() -> bool` | Whether a read has observed EOF; initially false, then sticky |
| `int_to_text` | `(int64) -> bytes` | Fresh mutable minimal signed ASCII decimal |
| `text_to_int` | `(bytes) -> int64` | Parse the whole buffer; return zero on failure |
| `parse_error` | `() -> int64` | Last `text_to_int` status; initially zero |

## Decimal conversion

`int_to_text` supports the entire signed 64-bit range, including
`-9223372036854775808`. Zero becomes `"0"`. It adds neither a terminator nor a
newline and leaves `parse_error` and `io_error` unchanged.

`text_to_int` accepts ASCII `[+-]?[0-9]+`, including leading zeroes. It rejects
empty input, a sign without digits, whitespace, NUL, non-ASCII digits, prefixes,
decimal points and trailing bytes. Check `parse_error()` immediately afterward:

- `0`: success, including a valid zero.
- `-22`: invalid decimal syntax.
- `-34`: valid decimal syntax outside the signed 64-bit range.

Invalid syntax takes precedence over overflow: `"999999999999999999999x"`
reports `-22`. Every byte is validated even after overflow. Parsing does not
allocate and has no digit limit beyond the existing 1 MiB buffer limit.
`parse_error` is independent of I/O status and changes only on `text_to_int`.

## Line input and EOF

`read_line` blocks until LF, EOF or a read failure. An empty line is a successful
empty buffer with `io_error() == 0` and `stdin_eof() == false`. A final line without
LF is returned in full and sets EOF true. Subsequent reads return empty bytes
with status zero. Process a nonempty final line even when EOF is already true:

```ramos
fn main() {
    var done = false
    while !done {
        let line = read_line()
        if io_error() != 0 {
            stderr("cannot read stdin\n")
            exit(1)
        }
        if buffer_len(line) == 0 && stdin_eof() {
            done = true
        } else {
            print(line)
        }
    }
}
```

LF and exactly one CR immediately before LF are removed. A bare CR at EOF is
retained. Other bytes, including NUL and invalid UTF-8, are preserved.

Payloads up to 1 MiB excluding LF/CRLF succeed. An oversized line is drained to
its next LF or EOF, then returns empty bytes with `io_error() == -27`. The next
line remains available. OS failures return empty bytes and a negative I/O status;
a consumed partial line is discarded. Failures do not themselves mark EOF.
Every `read_line` updates `io_error`, including resetting it after successful
reads or EOF; it does not change decimal parse status or file identity protection.

Input is read in 4 KiB chunks. A private lazy RW scratch mapping of 1 MiB +
12 KiB is reused outside the existing 16 MiB buffer arena. Returned lines are
fresh mutable arena allocations sized to their payload, so short lines do not
each consume 1 MiB. The arena is still finite and allocations still trap on
resource exhaustion. Do not mix this buffered API with another consumer of stdin.

Linux reads fd 0 directly and retries EINTR. Windows uses `GetStdHandle` and
`ReadFile`; broken pipe and handle EOF are treated as normal end of input.
Redirected files and pipes retain raw bytes. Windows console input follows its
configured input code page, unlike the UTF-8 command-line argument API; Ramos
does not promise UTF-8 console input. See Microsoft's
[ReadFile contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile).

## Try interactive input

```sh
./ramos build examples/input.ramos -o input --force
./input
```

On Windows:

```powershell
.\ramos.exe build .\input.ramos -o .\input.exe
.\input.exe
```

Type `21` and press Enter; the program prints `42`. The example checks input and
parse errors before arithmetic. Doubling remains checked and traps on overflow.

The shared tests cover integer boundaries and 180 seeded round trips, invalid
syntax and overflow precedence, independent statuses, live input before pipe
closure, binary data, CRLF and refill boundaries, exact limits and oversized
line recovery, 20,000 short lines, OS failures, preserved input-file protection,
and the interactive example. Both self-hosting proofs run these tests.
