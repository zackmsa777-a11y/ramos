# Follow-up goal: Ramos practicality

The current milestone is measured optimization of the 0.7 compiler. Its
benchmark index measures execution speed; it is not a general language-quality
score. The user's 8/10 project and roughly 4/10 practical-language assessment
is useful feedback, rather than a score this repository has independently
established.

A separate language-usability goal should preserve small syntax, checked
semantics, native Linux/Windows execution and deterministic self-hosting.
The reported needs are:

1. Comments and helpful diagnostics; short-circuit boolean operators and an
   ergonomic else-if form, with explicit evaluation semantics.
2. Integer-to-text and text-to-integer conversion, plus fallible stdin input.
3. Imports and a small reusable standard library so programs need less repeated
   manual buffer code.
4. Decide whether checked shifts, a for form, floats and larger resource limits
   justify their syntax and implementation cost using real programs.

The 0.7.1 emitter already specializes division by power-of-two constants used
in fixed-point programs. That optimization does not add shifts or floats to the
language. The user's reported Mandelbrot program and timings were not supplied
as a reproducible artifact, so they are not benchmark evidence for this release.

Each follow-up slice needs concrete semantics, examples, Linux/Windows tests and
fresh self-hosting proof before being described as delivered. No item above is
implemented merely by listing it here.
