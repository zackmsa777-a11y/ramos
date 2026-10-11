# Fallible decimal input and streamed statistics (0.18.1)

Weave `stdlib/math.ramos` to parse numbers from arguments, stdin or files. The
parser is ordinary Ramos code and uses the existing native float64 operations.
This release adds no syntax, native intrinsic, delegated backend or dependency.
The compiler, runtime and thirteen-library structure retain their 0.18 contracts.

## A complete input program

```ramos
weave "stdlib/math.ramos"
fn main() {
    let line = read_line()
    if io_error() != 0 { stderr("input failed\n")
        exit(2) }
    let parsed = math_parse_bytes(line)
    if parsed.status != 0 { stderr("expected a decimal number\n")
        exit(2) }
    print(math_text(parsed.value * 2.0, 3))
}
```

Keep `stdlib/` beside this source, build with `ramos build double.ramos -o double`
and enter `1.25` followed by Enter. Output is `2.500`. On Windows use
`ramos.exe` and `-o double.exe`. As with every float operation, doubling a very
large finite value may trigger the checked non-finite-result trap.

## Typed results

| API | Contract |
| --- | --- |
| `math_parse(text: string) -> FloatResult` | Copy UTF-8 text to bytes, then parse the whole value |
| `math_parse_bytes(text: bytes) -> FloatResult` | Parse the entire buffer without modifying it; suitable for raw file/stdin bytes |
| `FloatResult.value: float64` | Parsed finite value on success; positive zero on any failure |
| `FloatResult.status: int64` | 0 success, -22 syntax, -27 supported input limits, -34 finite range |

Check `status` before using `value`. A zero value alone cannot distinguish
failure from successful zero/underflow. Results are ordinary structs; keeping
one remains safe across later parses and collections. Neither parsing function
changes `parse_error()` or `io_error()`. Those globals still belong to integer
conversion and I/O, respectively. No parse failure writes stderr or exits.

## Grammar, limits and rounding

Whole-buffer ASCII `[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?` accepts
`1`, `+001.25`, `-0`, `1e2` and `1.25E-3`. A decimal point needs digits on both
sides. Empty input, a lone sign, `.5`, `1.`, whitespace, NUL, non-ASCII digits,
hex prefixes, underscores, NaN/infinity and trailing bytes are syntax errors.
Applications may deliberately trim or skip lines before parsing; the library
does neither implicitly.

At most 768 mantissa digits (including leading zeros) and a written exponent
from -400 through 400 are supported, matching the source-literal caps. The
exponent magnitude counts its numerical value, not its digit count: leading
exponent zeros are allowed up to the existing 1 MiB value limit. A fractional
digit count adjusts the exponent only after checking the written cap.

Status precedence is syntax (-22), then limits (-27), then finite range (-34).
The whole syntax is validated even after a limit is exceeded. Thus `1e401` is
-27, `1e309` is -34, and either value with trailing `x` is -22. `0e401` still
exceeds the written exponent cap. Failure returns positive zero.

Exact integer-rational conversion rounds once to nearest binary64, breaking
halfway ties toward an even significand. The library uses bounded base-65536
work arrays, then scales the rounded integer significand by exact powers of
two using existing native float operations. There is no approximate repeated
decimal multiplication or raw bit-cast API. Signed zero, gradual subnormal
underflow and finite overflow follow [the float contracts](math.md): `-1e-400`
succeeds as negative zero, `5e-324` succeeds as the smallest positive subnormal,
and unsupported non-finite results return -34 rather than trapping.

Successful conversion allocates bounded temporary managed arrays/records;
unreachable work is reclaimed normally. Syntax/limit rejection occurs before
allocating that work. Input scanning is linear in its byte length; conversion
work is bounded by the digit/exponent caps. Exhausting the live managed heap
still causes the ordinary allocation trap, rather than a fallible parse status.
`MathMagnitude` and `math_decimal_*` are implementation helpers; applications
should use the two parsing functions and the result fields.

Fixed `math_text`/`float_to_text` formatting is unchanged and is not a universal
lossless round-trip format. Scientific/shortest output and trig/log/power are
still future work. The existing 0.18 editor grammar covers this release.

## Streamed numerical CLI app

[examples/rstats.ramos](../examples/rstats.ramos) reads one number per line,
then reports count, minimum, maximum, sum and arithmetic mean. It accepts stdin
with no argument or a regular file path as its one argument:

```sh
./ramos run examples/rstats.ramos -- numbers.txt
```

```powershell
.\ramos.exe run .\examples\rstats.ramos -- .\numbers.txt
```

For this input, including LF/CRLF or a final unterminated line:

```text
1.25
-2.5
3e1
```

Output:

```text
count=3
min=-2.500000
max=30.000000
sum=28.750000
mean=9.583333
```

A file may exceed 1 MiB in total; lines are streamed and retain the existing
1 MiB line bound. Numeric mantissas still have the smaller 768-digit cap.
Blank/whitespace-only lines are invalid numbers. Empty input, bad arguments,
parse failures, I/O errors or output failure return 2. Parse diagnostics include
the one-based line and status; the summary is produced only after successful
input and file close. Input files are never modified. Six fixed fractional
digits are a display choice, not a precision or round-trip guarantee.

Summation is sequential binary64 addition, not compensated summation. Rounding
and cancellation can affect the mean. A non-finite sum (for example two `1e308`
lines) triggers the normal float runtime trap/exit 1, with no summary. It is not
a statistics package or a promise of stable aggregation for arbitrary data.

## Verification

Seven shared tests cover 264 independently normalized binary64 reference values,
normal/subnormal halfway ties, signs, boundaries, syntax/status precedence,
whole-buffer validation, unchanged input/status globals and 6,000 repeated parses
with collection. The app tests Unicode paths, stdin, files, LF/CRLF, final lines,
a 1,078,272-byte input, invalid/non-ASCII numbers, oversized lines and checked
summation overflow. The complete Linux/Windows corpora and compiler fixed points
are recorded in [math-input-verification.json](math-input-verification.json),
[Linux proof](bootstrap-proof.json) and [native Windows proof](windows-bootstrap-proof.json).
No new comparative timing or language score is claimed.
