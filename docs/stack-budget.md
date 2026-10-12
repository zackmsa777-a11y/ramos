# Checked deeper recursion (0.22)

Generated programs support **1,024 active Ramos calls**, including `main`.
A second guard checks stack use before allocating each function's local frame.
The first guard exceeded prints either `Ramos runtime error: call depth limit
exceeded` or `Ramos runtime error: stack budget exceeded`, restores terminal
state through the existing failure path, and exits 1.

The stack guard measures the distance from the process-entry context (`r15`)
to the current `rsp`, adds the complete prospective rounded local frame, saved
`rbp` (8 bytes), and 16 KiB of expression scratch, and requires the result to
be at most **4 MiB**. Pending arguments, expression values, return addresses
and caller frames are therefore included by their actual stack addresses.
The compiler's 1,024-value expression type stack bounds expression scratch;
indexed destinations and temporary arithmetic operands fit within the extra
16 KiB allowance. Runtime helpers and OS/toolkit calls use the remaining
stack headroom; they do not increment the Ramos call counter.

Windows PE already reserves 8 MiB (4 KiB initially committed); the existing
page probes remain before large frame allocations. Use an ordinary Linux
stack of at least 8 MiB. A deliberately smaller OS stack can still exhaust
before the guard, and callbacks/third-party GUI libraries have their own
stack requirements. This is a bounded language stack policy, not an OS stack
size detector or a proof about arbitrary toolkit internals.

Small frames can reach the 1,024-call boundary. Functions with large frames
stop earlier: the shared tests run 221 active 16 KiB recursive frames and
reject a request for 301 with a clean stack-budget error on each target.
The unchanged 4,096 declaration cap includes declarations across functions;
slot reuse and frame rounding remain unchanged. Normal returns restore `rsp`
and decrement the counter, so repeated deep calls do not accumulate usage.
Managed values in deeper frames remain GC roots under the existing stack scan.

The retained assembly seed still generates its historical 64-call ABI. It
builds the first Ramos compiler; all later compiler generations emit both
new guards. There is no new user keyword, runtime option or allocation API.

## Practical example

The scientific calculator uses the extra headroom to support 64 recursive
expression levels, with a recoverable error when an expression exceeds that
app limit. Its parser and scientific helpers are ordinary Ramos source.
The app's own limit is intentionally lower than the compiler's active-call
limit because one expression level can involve several Ramos functions.

## Validation

Shared Linux/Windows tests exercise the exact active-call boundary, repeated
returns, mutual recursion with pending expression values, large-frame success
and failure, and collection while hundreds of managed values remain rooted.
The deterministic compiler fixed points and the full language/application
corpus are release gates. Fresh eight-task measurements accompany this change:
every generated function now performs an extra stack-budget check, so older
performance reports cannot establish this release's speed.
