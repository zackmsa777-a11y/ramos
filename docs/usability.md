# Ramos 0.8: comments, boolean operators and diagnostics

Ramos 0.8 adds `//` line comments, `/* ... */` block comments and the boolean
operators `&&` and `||`. It keeps the existing checked integer/buffer semantics,
small syntax and direct Linux ELF / Windows PE emitter.

## Comments

Line comments end before LF or CRLF, or at the end of the file. Block comments
end at the first `*/`; they do not nest. Comment markers inside string literals
are ordinary bytes, and `/` still means integer division outside comments.

Comments act as token separators, not source concatenation. Newlines inside
block comments remain newlines for statement separation. A multiline comment
inside a parenthesized expression or after an operator follows the usual
expression continuation rules. Source must still be valid UTF-8 with no raw
NUL bytes, including inside comments. Unterminated block comments point to the
opening `/*` and report the expected terminator.

```text
// A line comment.
fn main() {
    let name = "Ramos" /* A block comment. */
    print(name)
}
```

## Short-circuit booleans

Both operands of `&&` and `||` must be `bool`; the result is `bool`.
`a && b` evaluates `b` only if `a` is true. `a || b` evaluates `b` only if `a`
is false. Evaluation proceeds left to right. Skipped expressions are still
parsed and type-checked, including names, calls and argument types.

From lowest to highest precedence: `||`, `&&`, equality (`==`, `!=`), ordering,
addition/subtraction, multiplication/division/remainder, unary signs/`!`, and
primary expressions. Operators at the same precedence associate left to right.

```text
fn main() {
    let text = "abc"
    var i = 0
    while i < buffer_len(text) && buffer_get(text, i) != 0 {
        i = i + 1
    }
    print(i)
    print(true || (1 / 0 == 0)) // true; the division does not execute.
}
```

This makes bounds guards practical without weakening buffer checks. A bare
`&` or `|` is rejected with a hint to use the corresponding boolean operator;
bitwise arithmetic is not added by this milestone.

## Diagnostic improvements

Diagnostics retain `file:line:byte-column: error:`. Common failures now explain
what is wrong, for example:

- An integer condition: `expected bool, found int64`.
- An invalid boolean operand: `boolean operators require bool operands`, at
  the operator position.
- Unresolved names: `unknown variable` or `unknown function`.
- Missing function arguments: `too few function arguments`.
- Invalid escapes: `unsupported string escape`.
- Missing comment terminator: `unterminated block comment; expected '*/'`.
- Assigning to `let`: `cannot assign to an immutable let binding`.

Other improvements cover argument/return/assignment types, delimiters, main's
signature, duplicate names, invalid UTF-8, source NUL bytes, illegal characters,
and loop-control context. Some malformed syntax still receives the general
`unexpected token` message. Failed builds preserve existing outputs even when
`--force` is present.

## Implementation and proof

The compiler remains one Ramos source file. The shunting-yard parser stores two
branch labels for each logical operator. It consumes the left value and emits
a conditional branch before emitting the right expression, then joins both
paths with exactly one boolean result. These labels use the same bounded fixup
arena as existing control flow. The local value-push optimization clears its
record at each label, preserving the branch destination.

The original assembly seed retains the 0.7 grammar. The compiler source itself
uses that compatible surface syntax so the seed can build the full 0.8 compiler;
no Python preprocessing or external compiler is involved. The 0.8 feature tests
run on self-hosted stages 2 and 3 and on the native Windows compiler. The seed
runs the existing contracts and explicitly skips the new grammar tests.

The new tests include boolean truth tables, precedence, all relevant evaluation
paths, skipped runtime failures, left-to-right call traces, 80 seeded expression
trees checked by an independent evaluator, long chains, loop guards, comments,
source locations and diagnostic reasons. Both targets must still reach their
byte-identical self-hosting fixed point and pass the runtime audit.

The 0.7.1 performance measurements remain labeled 0.7.1. The 0.8 compiler
produces byte-identical output for all nine benchmark fixtures on both targets:
[code-generation continuity proof](codegen-continuity.json). This preserves the
measured program code; it does not measure compilation speed or establish new
Windows timing claims.
