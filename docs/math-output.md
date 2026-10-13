# Exact numerical output — Ramos 0.24

Weave `stdlib/math.ramos`; these helpers are written in Ramos. They format the
exact finite binary64 value with decimal rounding to nearest, ties to even.
They do not repeatedly multiply a float by ten and round the approximation.

| API | Precision | Result |
| --- | --- | --- |
| `math_scientific(value: float64, places: int64) -> string` | 0..18 digits after the mantissa point | One leading digit, exactly `places` fractional digits, lowercase `e`, explicit exponent sign, no exponent padding |
| `math_format(value: float64, digits: int64) -> string` | 1..17 significant digits | Trailing insignificant zeros removed; plain notation when the rounded exponent is `-4 <= exponent < digits`, scientific otherwise |

```ramos
weave "../stdlib/math.ramos"
fn main() {
    print(math_scientific(1e-100, 5)) // 1.00000e-100
    print(math_format(1e-100, 17))    // 1e-100
    print(math_format(3.5, 17))      // 3.5
    print(math_scientific(2.5, 0))   // 2e+0 (even tie)
    print(math_scientific(3.5, 0))   // 4e+0 (even tie)
    print(math_format(9999.5, 4))    // 1e+4 (carry changes notation)
    print(math_format(5e-324, 17))   // 4.9406564584124654e-324
}
```

The weave path is relative to the source file. For a source at the repository
root, use `weave "stdlib/math.ramos"`.

Both helpers preserve negative zero: `math_format(-0.0, 17)` is `s"-0"` and
`math_scientific(-0.0, 2)` is `s"-0.00e+0"`. Invalid precision produces a Ramos
library error on stderr and exit 1; even extreme int64 precision arguments are
validated before arithmetic. Successful formatting leaves `io_error()` and
`parse_error()` unchanged. Output is an ordinary immutable UTF-8 string.

Use `math_format(value, 17)` with `math_parse` to preserve every finite binary64
value. This is **not a shortest-decimal algorithm**: `math_format(0.1, 17)` is
`s"0.10000000000000001"`. Lower precision rounds for display and can lose
information. A rounded scientific representation of a value near the finite
maximum can exceed the finite parsing range at low precision; only compact
17-digit output has the round-trip contract.

`math_text`, `float_to_text`, and `print(float64)` retain their fixed-decimal
contracts. No NaN, infinity, arbitrary-precision public type, or implicit
conversion is added. The private conversion uses at most 512 base-65536 limbs
and a 900-byte decimal work buffer; these fit all finite binary64 values and
remain subject to the normal managed heap/GC limits.

Verification uses Python's independent `Decimal.from_float` and ties-even
quantization for 2,304 outputs, covering 256 binary64 inputs and nine precision
choices. Separate tests verify 17-digit parsing round trips, signed zeros,
subnormal/maximum values, carry transitions, invalid precisions, status
independence, live aliases, and 6,000 iterations of allocation/recovery.
Native platform and bootstrap evidence is in
[math-output-verification.json](math-output-verification.json): 297 Linux and
238 native Windows tests pass, with matching compiler fixed points on each OS.
No new comparative speed claim is made.
