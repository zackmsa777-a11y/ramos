# Ramos 0.4 Functions Implementation Plan

Goal: deliver typed native functions and recursion in Ramos 0.4.
Architecture: discover bounded signatures, type-check bodies/calls, emit private
stack frames and calls using the existing label fixups. Retain assembly stage 0.
Tech stack: GNU as/ld, Python end-to-end tests, static x86-64 Linux ELF.
Spec: docs/superpowers/specs/2026-10-09-functions-design.md

## Constraints and review focus
- Arguments are evaluated left to right; earlier expression operands survive calls.
- Per-function slot numbers and symbol scopes cannot leak between functions.
- Signature discovery must clear decoded string data before body emission.
- Recursive calls must trap at 64 active calls; returns restore the counter.
- Void calls, argument types and all-path return checking must reject invalid input.
- Keep existing compiler limits, checked arithmetic, publication and ELF protections.

## Tasks
- [x] Add failing tests for forward/mutual calls, return types, side effects,
      independent frames, scope/type failures and resource limits.
- [x] Extend tokens and add src/functions.inc for signatures, calls and returns.
- [x] Extend scoped parsing for parameters, local slot indices and return paths.
- [x] Add src/function_codegen.inc for frames, parameter copies and bounded calls.
- [x] Add runtime depth checks and preserve r12 across all runtime paths.
- [x] Run the full suite and review the implementation with an independent reviewer.
- [x] Update examples, syntax/ABI docs and the self-hosting roadmap; install/smoke test.
- [x] Commit and publish, or save the deliverable if GitHub write access is blocked.


Validation: clean build; 60 integration tests pass; all native examples and
installed compiler pass. ELF remains RX code, read-only data, non-executable
stack. Independent review found no blocking issue after 100 additional seeded
nested-call programs and exact function/declaration boundaries. Its observed
benchmark test failure was the expected red phase; the implemented version
guard now passes and preserves the historical 0.2 measurement contract.

Publishing remains conditional on actual repository write access. The local
branch is preserved if the GitHub integration rejects its tree upload.
