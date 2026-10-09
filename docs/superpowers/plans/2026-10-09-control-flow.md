# Typed Control Flow Implementation Plan

Goal: install and deliver Ramos 0.3 control flow in a feature-branch PR.
Architecture: extend the existing lexer and typed postfix IR, then emit bounded
native label fixups. Preserve the assembly bootstrap compiler.
Tech stack: GNU as/ld, Make, Python integration tests, x86-64 Linux.
Spec: docs/superpowers/specs/2026-10-09-control-flow-design.md

## Global constraints
- No external code-generation backend or compiler implementation dependency.
- int64 arithmetic stays checked; bool is a distinct inferred type.
- Nesting 128; existing arena limits and safe output publication stay enforced.

## Review focus
- Signed comparisons at INT64_MIN/MAX must not use overflow-prone subtraction.
- Skipped branch declarations must never become readable outside that scope.
- Nested continue/break must leave the generated expression stack balanced.
- Newline lookahead after an if must preserve statement separators.
- Deep blocks and large branch tables must fail cleanly without output.

## Task 1: typed expressions
- [x] Add failing integration tests for literals, comparisons, type errors.
- [x] Add tokens, precedence/type checks, boolean runtime output and emission.
- [x] Run the expression tests and existing suite.

## Task 2: structured control flow
- [x] Add failing execution tests for if/else, nested loops, break/continue,
      lexical scope, malformed blocks, nesting/resource limits.
- [x] Add bounded block parser, scoped symbol records and loop labels.
- [x] Add bounded label/jump IR and two-pass rel32 fixups.
- [x] Run all tests, inspect ELF and execute realistic loop examples.

## Task 3: delivery
- [x] Update syntax/version, examples, self-hosting roadmap and install target.
- [x] Clean build, full test suite, install and smoke test the installed binary.
- [ ] Commit, push feature branch and create PR.

Verification: clean build and 45 integration tests pass; native examples and
installed compiler smoke tests pass. Independent code review found no defects,
including 500 seeded typed expressions and collision-heavy scoped bindings.
