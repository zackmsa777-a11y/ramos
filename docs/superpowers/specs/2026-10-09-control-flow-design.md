# Ramos 0.3: typed control flow

Goal: extend the assembly bootstrap compiler toward the language needed for a
compiler written in Ramos, while preserving native ELF emission and hardening.

Expressions have inferred int64 or bool type. `true` and `false`, `!`, integer
`< <= > >=`, and same-type `== !=` produce canonical booleans. Arithmetic accepts
integers only; assignments preserve the declared type. `print(bool)` writes
`true` or `false` and a newline. Precedence: equality, ordering, sum, product,
unary, primary, from lowest to highest. No implicit integer/bool conversion.

`if condition { ... } else { ... }` and `while condition { ... }` require bool.
The optional else may follow its closing brace on the same or following lines.
`break` and `continue` target the innermost while and are errors outside a loop.
Blocks have lexical scope and permit shadowing outer names. Duplicate names in
one scope remain errors. Bindings initialize when execution reaches their
statement, including each loop iteration. No binding escapes its block.
Statements remain newline-separated, including after compound statements.

Use bounded postfix IR plus labels, unconditional jumps, and conditional jumps;
resolve native rel32 branches after emission. Conditions consume their stack
value, so every branch and loop boundary has a balanced expression stack.
Both expression and block nesting are limited to 128. Existing source, symbols,
IR, output, publication and memory-protection bounds remain enforced.

This milestone does not claim self-hosting or complete the existing Phase 2
security roadmap. Functions, byte buffers, owned strings, indexed collections,
CLI arguments, file I/O and a bootstrap parity test remain needed. Keep the
assembly compiler as stage 0 until stage 1 can compile itself reproducibly.
