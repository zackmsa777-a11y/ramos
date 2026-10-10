# Ramos milestones and remaining practicality work

The requested optimization goal shipped as **0.7.1**: measured 2.05× overall
execution gain on the eight-task suite, with checked semantics and both native
self-hosting proofs retained. The separate follow-up selected by the user shipped
as **0.8**: comments, more helpful diagnostics and short-circuit boolean operators.

The next approved slice shipped as **0.9**: buffered fallible stdin input,
EOF checks and signed integer/text conversion with independent parse status.
See [the semantics and example](input-text.md).

The first three developer-feedback priorities ship as **0.10**: immutable UTF-8
strings, automatic reclamation, structs and typed arrays. See [values.md](values.md).

Remaining priorities, in the feedback's order:

1. Syntax conveniences: else-if, range for, assignment shortcuts and a reviewed call-depth limit.
2. Imports and a small standard library written in Ramos.
3. Floats for graphics and numerical programs.
4. Source-line/caret diagnostics, formatting and assembly output tooling.
5. Further optimization only after useful programs identify measured costs.

The benchmark index measures execution speed, not language quality. The user's
8/10 project and roughly 4/10 practical-language assessment is useful feedback,
not a score independently established here. Their Mandelbrot source was not
supplied, so its reported timings are not release benchmark evidence.

Each future slice should preserve simple syntax, checked semantics, native
Linux/Windows execution and deterministic self-hosting, with concrete semantics,
examples and tests before it is described as delivered.
