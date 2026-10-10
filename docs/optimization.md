# Ramos 0.7.1 instruction selection

This release improves the existing x86-64 emitter shared by Linux and Windows.
It adds no language syntax, intermediate representation, optimization flags,
external backend or runtime dependency. The assembly bootstrap remains the
unoptimized recovery compiler. Arithmetic and buffer errors keep their existing
runtime messages, exit status and evaluation order.

## Local instruction selection

A literal RHS between zero and INT32_MAX can use immediate add/subtract/multiply
or compare instructions. Arithmetic retains the overflow branch. The emitter
recognizes only a literal whose recorded output end still equals the cursor;
computed expressions and negative/wide constants use the general path.

For division/remainder by a positive literal in that range:

- Division by one returns the dividend; remainder by one returns zero.
- Powers of two use a signed bias followed by a shift or mask. The bias is
  `(dividend < 0 ? divisor - 1 : 0)`, so division truncates toward zero and
  remainder has the dividend's sign, including INT64_MIN.
- Other divisors use the unsigned magnitude `u` and the high half of
  `u * floor(2^64 / divisor)`. This quotient estimate is exact or one too small:
  the reciprocal error is less than one, and `u <= 2^63`, so the real quotient
  error is less than one. Compute the remainder, correct once if it is at least
  the divisor, and restore the original sign. The magnitude 2^63 for INT64_MIN
  is handled as an unsigned bit pattern. Internal machine operations implement
  this proven transform; they do not expose wrapping Ramos arithmetic.

The compiler itself computes the reciprocal without an unsigned type or a
2^64 literal: let `half = INT64_MAX / divisor` and
`r = INT64_MAX % divisor`; the multiplier is `2*half + (2*r + 2)/divisor`.
For non-power divisors at least three and at most INT32_MAX, those calculations
fit signed int64. Zero, negative, wide and runtime divisors retain checked idiv.

## Stack values and buffers

Expression values still use the existing stack ABI. When consuming a value
immediately after its recorded `push rax`, the emitter removes that push and
uses the live RAX value, or moves it to RCX/RDX. Marking any branch target clears
the record, so a rewrite cannot erase an instruction reached by another path.
Function arguments still occupy stack slots, and values are not kept in scratch
registers across user calls.

`buffer_len`, `buffer_get` and `buffer_set` inline their short successful paths.
Unsigned index comparisons reject negative indices too. Writes check index
before byte range, just as the runtime does. Failure branches enter the existing
runtime intrinsic with the original arguments; it checks the same invalid input
and exits with the existing diagnostic. Valid typed buffers have immutable
length headers, so a failing check cannot return from that path.

## Evidence

The Linux corpus has 96 tests and runs against the assembly seed and both
self-hosted stages. New cases compare constant and dynamic division/remainder
for 532 signed boundary and seeded values, using Python integer arithmetic as
an independent reference. They cover powers of two, reciprocal correction,
INT64_MIN, INT64_MAX, wide fallback divisors, overflow, zero division,
left-to-right side effects, buffer error ordering, loops and recursive arguments.
These six added tests also run with the native Windows compiler.

Both targets must retain byte-identical self-recompilation and the runtime audit
must still match the retained assembly. Performance evidence is in the
[eight-task report](../benchmarks/report.md) and
[paired old/new comparison](../benchmarks/optimization.md). Measurements apply to
those workloads and machine; native Windows correctness does not establish
Windows performance.
