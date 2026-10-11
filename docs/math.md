# Native float64 and essential math (0.18)

Ramos adds a `float64` value type on Linux x64 and Windows x64. Arithmetic emits
SSE2 instructions directly; decimal literal conversion is implemented in the
Ramos-written compiler. Python is only an independent test reference, not part
of compilation or execution. Integer arithmetic remains checked int64.

## A complete program

```ramos
weave "stdlib/math.ramos"
struct Point { x: float64, y: float64 }
fn main() {
    let p = Point(1.25, 2.5)
    let samples = array(float64, 2, 0.0)
    samples[0] = p.x
    samples[1] = p.y
    p.x += 0.5
    print(p.x)
    print(math_text(math_sqrt(2.0), 3))
    print(float_to_int(-2.9))
    print(samples[0] < samples[1])
}
```

Output: `1.750000`, `1.414`, `-2`, `true`, each on its own line. Keep `stdlib/`
beside this source, then use `ramos run app.ramos` or build a saved executable.

## Literals and types

`1.25`, `1.0`, `1e2`, `1.25e+2` and `1E-3` are float literals. A decimal point
requires digits on both sides: use `0.5`, not `.5`, and `1.0`, not `1.`.
An exponent requires digits after its optional sign. A sign is a unary operator.
Integer literals and the integer range syntax `0..n` keep their existing meaning.

Each literal admits at most 768 mantissa digits (including leading zeros) and
a written decimal exponent from -400 through 400. The exponent limit applies
before adjusting for fractional digits. Exact integer-rational conversion rounds
once to the nearest binary64 value, breaking halfway ties toward an even
significand. Literals rounding outside the finite range are compile errors;
tiny literals may round to a subnormal value or zero. `-0.0` retains its sign.

Bindings infer float64; function parameters/results, struct fields and nested
array types can explicitly use `float64`. Array elements occupy eight bytes.
Calls and assignment require matching types. `float64` is a new reserved keyword;
`float_to_int`, `float_to_text` and `float_sqrt` are reserved intrinsic names.
Older programs defining these names need renaming.

Two floats support `+`, `-`, `*`, `/`, unary signs, all six comparisons and
`+=`/`-=`. They follow the existing integer operator precedence. `%` is unsupported.
Mixed int/float operations are compile errors: write `float64(n) + 0.5`.
Booleans require explicit comparisons; floats cannot be range bounds or indices.
`+` does not implicitly format numbers or concatenate floats with strings.

## Finite arithmetic and errors

The representation is binary64: a sign, eleven exponent bits and 52 stored
fraction bits. See [the primary representation reference](https://docs.oracle.com/cd/E37069_01/html/E39019/z4000ac019269.html).
Ramos uses round-to-nearest/ties-to-even SSE2 arithmetic, with gradual underflow
and no fused multiply-add contraction. Decimal fractions such as 0.1 usually
have an approximation in this representation; exact equality compares the
stored numerical values. Positive and negative zero compare equal.

Ramos deliberately exposes finite values only. An operation producing infinity
or NaN, division by either signed zero, square root of a negative nonzero value,
an invalid conversion or a formatting precision outside 0..18 writes a Ramos
runtime error and exits 1. Previous output remains. There is no full IEEE-754
conformance claim, exposed NaN/infinity, exception flag API or rounding-mode API.
Underflow rounding to a subnormal or signed zero is allowed. Square root of
negative zero preserves negative zero. Integer overflow and bounds traps remain.

## Explicit conversions and printing

| Intrinsic | Contract |
| --- | --- |
| `float64(value: int64) -> float64` | Round an integer to nearest/ties-to-even binary64; integers larger than 2^53 in magnitude may lose precision |
| `float_to_int(value: float64) -> int64` | Truncate toward zero; input must be in [-2^63, 2^63), otherwise trap |
| `float_to_text(value: float64, places: int64) -> bytes` | Fresh decimal bytes with exactly 0..18 fractional digits, nearest/ties-to-even decimal rounding |
| `float_sqrt(value: float64) -> float64` | Hardware square root with checked domain and finite result |
| `print(value: float64)` | Fixed decimal with six fractional digits and LF |

`float_to_int(-2.9)` returns -2. `float64(9223372036854775807)` rounds to 2^63,
so converting that result back traps. The included lower bound -2^63 converts
successfully. There are no implicit conversions.

Formatting rounds the exact stored binary value using integer arithmetic;
it does not round an approximate decimal multiplication. Thus
`float_to_text(0.1 + 0.2, 18)` produces `0.300000000000000044`.
`float_to_text(2.5, 0)` produces `2`; `float_to_text(3.5, 0)` produces `4`.
Negative zero formats with `-`. Very large values use full fixed decimal notation.
Wrap with `string(...)` for UTF-8 string operations, or use `math_text`.

Fixed printing is not a shortest-decimal, scientific or lossless round-trip
format. Tiny values may print as zero at the chosen precision. Text-to-float
parsing is added by the [0.18.1 math library](math-input.md); trig/log/power
functions and arbitrary precision remain future work.

## Ramos math library

Weave `stdlib/math.ramos`. Its helpers use ordinary Ramos code:

- `math_abs(value)` normalizes either zero to positive zero.
- `math_min(a, b)` and `math_max(a, b)` return the first argument on equal values,
  including signed-zero ties.
- `math_clamp(value, low, high)` rejects reversed bounds with a library error/exit 1.
- `math_sqrt(value)` wraps the checked intrinsic.
- `math_text(value, places)` returns an immutable string with fixed decimal digits.

All numerical arguments above are float64; formatting precision is int64.
There are thirteen bundled libraries in 0.18.

## A numerical renderer

[examples/mandelbrot.ramos](../examples/mandelbrot.ramos) produces a grayscale P5
PGM image using native float arithmetic. It needs no GUI or external math library.

```sh
./ramos run examples/mandelbrot.ramos -- image.pgm 320 240 100
```

```powershell
.\ramos.exe run .\examples\mandelbrot.ramos -- image.pgm 320 240 100
```

Open the PGM with an image viewer that supports that format. This example defaults
to 320×240 and 100 iterations if only an output path is supplied. Explicit width
and height are 1..1024; iterations are 1..10000. Header plus pixel data must fit
1 MiB. Existing output is preserved; argument/size/I/O errors return 2. A 32×24,
40-iteration render is byte-checked against independently computed pixels on
both targets. It is an acceptance example, not a comparative speed benchmark.

## Verification and remaining limits

The twelve shared float tests cover independent binary literal encodings (95
cases), exact fixed formatting (256 cases), arithmetic (200 cases), recursion,
arrays/fields/GC, invalid operations, type/literal limits, formatting and the
renderer. The 0.18 milestone evidence is in [math-verification.json](math-verification.json),
with [Linux](bootstrap-proof.json) and [native Windows](windows-bootstrap-proof.json)
compiler fixed points. Existing memory, collection growth, call-depth and source
limits remain enforced; this release does not raise them. Networking APIs,
Linux desktop GUI and broader tooling remain future work. No new 0.18 comparative
performance score is claimed.
