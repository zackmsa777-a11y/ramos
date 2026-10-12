# Ramos function semantics and ABI (current self-hosted compiler)

The language supports top-level functions with explicitly typed parameters and optional
return annotations (including current string, float64, struct and array types), and inferred local
bindings. An omitted result annotation is void. Main must take no parameters
and return void. No closures, overloads or foreign function interface exist.

## Compilation

A lexer pass discovers up to 256 signatures and their parameter source slices.
It validates headers, checks duplicate names and finds the single main. A second
pass checks bodies and emits typed postfix IR, including function, call, return
and discarded-value operations. The decoded-string arena is reset between passes.
Calls can refer to later functions and form recursive cycles.

A parameter is an immutable root-block binding. Parameters and body locals
share a scope; a nested block may shadow a parameter. Bindings also shadow
function names. Local symbol records keep globally bounded identities and
function-local stack slot numbers separately. Leaving each root block clears
its parameters and locals from the active symbol table.

Return analysis accumulates guaranteed returns across each statement sequence.
A direct return guarantees the rest of that path cannot fall through. An
if/else guarantees return only when both blocks do. A loop does not establish
that guarantee, even when its condition is a constant. Every value function
must pass this check; a void function may fall through. Skipped and unreachable
source is still checked for type/scope errors.

## Private native ABI

- Process entry initializes r12 (call depth), r13 (buffer arena base) and r14
  (used arena bytes) to zero, clears the direction flag, calls main and exits
  with status zero.
- Caller argument expressions run left to right. Each result occupies one
  eight-byte expression-stack slot, in that evaluation order.
- `call rel32` pushes the return address. The callee checks/increments the r12
  call counter, saves rbp, sets rbp to rsp and reserves its rounded local frame.
- The last argument is at rbp+16, the preceding one at rbp+24, and so on.
  Arguments are copied into immutable negative-offset local slots in source
  parameter order. Additional local slots follow them. No slots alias another
  function's frame, even during recursion.
- rax carries the result. Void returns use internal zero, which source cannot
  read as a value. A return expression is popped into rax before the epilogue.
- `leave; dec r12; ret` restores the caller's frame and counter. The caller
  removes its argument slots and pushes the result. A call statement pops and
  discards that internal result, including for void calls.
- Earlier expression values remain on the caller's stack while callees run.
  Generated arithmetic/runtime routines may clobber ordinary scratch registers;
  rbp, rsp's frame discipline and the reserved r12 counter survive all calls.
  r13/r14 persist across all functions and runtime helpers; only the buffer
  allocator updates them. bytes results occupy one opaque eight-byte handle.

The active-call limit is 1,024 including main. The self-hosted compiler also
checks a 4 MiB stack budget before reserving each complete local frame; see
[the stack policy and platform assumptions](stack-budget.md). A deeper attempt writes a stderr
call-depth diagnostic and exits 1 before allocating another local frame.
Arithmetic failures keep the existing checked behavior and exit 1. These paths
terminate the process rather than unwinding. Normal returns restore both the counter and frame. Use an OS stack of at least
8 MiB; a smaller caller-selected OS stack may fail before the language guard.

This ABI is internal to Ramos and does not claim System V/C interoperability.
All code and fixups remain statically generated, within the bounded output arena.
