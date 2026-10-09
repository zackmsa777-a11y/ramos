# Ramos 0.4 functions

Goal: provide the native function machinery needed by a compiler written in
Ramos. Preserve all 0.3 language semantics, bounds and safe ELF publication.

Syntax: `fn add(a: int64, b: int64) -> int64 { return a + b }`.
Parameter and result types are int64, bool and (results only) void. Omitted
result annotation means void. Exactly one `fn main()` returning void is required.
Functions may appear in any order; direct and mutual recursion are supported.
No nested function declarations, overloads, closures or string parameters.
Names have a global function namespace; lexical bindings shadow function names
and a shadowed function cannot be called. Main cannot be called from user code.
Parameters are immutable bindings in the function's root block. Local frames
are independent between calls. Function-local bindings do not escape.

Calls evaluate arguments left to right and require exact arity and types.
Void calls are statements only. A value call used as a statement discards the
result. `return expression` must match the declared value type; bare return is
allowed only in void functions. Every value function must conservatively return
on every path: return statements and if/else with both arms returning count;
loops never establish guaranteed return. Unreachable code is still checked.

Native ABI: arguments are pushed left to right, the caller removes argument
slots, rax contains the result, rbp/rsp delimit a private frame. The generated
runtime reserves r12 as the active Ramos-call counter and never clobbers it.
Each function copies stack arguments into immutable local slots. The executable
entry initializes the counter, calls main, then exits with status zero. A normal
return restores rbp/rsp and decrements the counter. Runtime error paths exit 1.
This is a private Ramos ABI, not a C/System V foreign-function interface.

Limits: 256 functions including main, 16 parameters per function, 64 active
Ramos calls including main, 4096 total declarations including parameters across
the source. Existing source/statement/IR/output/block/expression limits remain.
Function signatures are discovered in a lexer pass before body checking. Native
calls reuse bounded label fixups. Strings decoded by the signature pass are
cleared before body parsing. Frame slots are local to each function.

Self-hosting remains future work: buffers, owned strings/collections, CLI and
file I/O must precede a Ramos-written stage-1 compiler and bootstrap parity.
