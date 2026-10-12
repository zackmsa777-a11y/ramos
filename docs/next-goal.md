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

Version **0.11** implements the user's selected `weave` keyword and a small
standard library written in Ramos. See [libraries.md](libraries.md).

Version **0.12** implements the user's file-tool priority and terminal-interface
request: streamed I/O, CLI helpers, TUI controls and working copy/search/viewer
apps. See [cli-tui.md](cli-tui.md).

Version **0.13** adds the requested desktop GUI library, with a native Windows
backend, Unicode controls, resize/events and a working Notes app. Linux GUI
startup was unsupported in that release; 0.19 supplies an optional GTK3 backend. See
[gui.md](gui.md).

Version **0.14** adds `else if`, range `for`, and `+=`/`-=` with checked
semantics and an updated file-search tool. See [syntax.md](syntax.md). The next
application milestone shipped as **0.15**: directory iteration/creation, lexical
paths, environment lookup and direct child execution. See [system.md](system.md).
Version **0.16** delivers caret errors, formatting and native compile-and-run.
See [devtools.md](devtools.md). Version **0.17** ships reusable text builders and the streamed `rnumber` tool.
See [text-builder.md](text-builder.md). Version **0.18** ships finite float64 arithmetic, essential math and a numerical
renderer. See [math.md](math.md). Version **0.18.1** adds fallible decimal input
and the streamed `rstats` app; see [math-input.md](math-input.md). Collection growth and reviewed memory/recursion
limits remain a separate follow-up. Version **0.19** adds Linux GTK3 desktop
windows with the same Notes source and `run --gui`; see [gui.md](gui.md).
Version **0.19.1** adds checked rectangle/row/column/padding helpers, native
Open/Save path pickers and Notes Open/Save As. DPI policy and general drawing
remain follow-ups. Version **0.20** adds native monotonic timing and the
profiled rmatrix animation improvements. Version **0.21** adds reserve/release,
fallible full-collection handling and integer sorting with `rsort`; see
[collections.md](collections.md).

The target is a useful native application language with simple APIs. See the
[ordered application-language roadmap](roadmap-1.0.md) for the user's **simple**
and **fast** rules, proposed milestones, runnable acceptance examples and
performance measurements. Future features in that plan are not shipped features;
C/Rust feature/ecosystem parity is not claimed.

Original developer-feedback priorities still guide these slices:

1. Syntax conveniences: else-if, range for, assignment shortcuts and a reviewed call-depth limit.
2. Broader math and scientific/shortest decimal output for numerical programs.
3. Source-line/caret diagnostics, formatting and assembly output tooling.
4. Further optimization only after useful programs identify measured costs.

The benchmark index measures execution speed, not language quality. The user's
8/10 project and roughly 4/10 practical-language assessment is useful feedback,
not a score independently established here. Their Mandelbrot source was not
supplied, so its reported timings are not release benchmark evidence.

Each future slice should preserve simple syntax, checked semantics, native
Linux/Windows execution and deterministic self-hosting, with concrete semantics,
examples and tests before it is described as delivered.
