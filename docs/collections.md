# Collection capacity, release and integer sorting (0.21)

The existing `IntList` and `StringMap` already grow by doubling. Version 0.21
adds explicit reservation, recoverable capacity rejection and storage release.
These helpers are written in Ramos; no syntax, allocator, heap limit or native
backend changes are required.

```ramos
weave "stdlib/lists.ramos"
fn main() {
    let values = list_new()
    if list_reserve(values, 1000) != 0 { exit(2) }
    list_push(values, 42)
    list_push(values, -7)
    list_sort(values)
    print(list_get(values, 0))
    list_release(values)
}
```

## List helpers

| Helper | Contract |
| --- | --- |
| `list_capacity(list) -> int64` | Allocated element capacity, separate from logical length |
| `list_reserve(list, minimum) -> int64` | Grow to at least this capacity; never shrink or change logical length |
| `list_try_push(list, value) -> int64` | Append, or return -27 without changing the list if it already has 131072 elements |
| `list_release(list)` | Empty the list and detach its backing array; future pushes work normally |
| `list_sort(list)` | Sort the active prefix in ascending signed-int64 order, keeping duplicates and capacity |

Reserve returns 0 on success, -22 for a negative minimum and -27 above 131072.
Rejected requests leave length, capacity and elements unchanged. A request
smaller than existing capacity is a successful no-op. An explicit reservation
may be any valid count; subsequent growth doubles capacity, capped at 131072.
This handles non-power-of-two reservations without exceeding the array bound.

The existing `list_push` remains the convenient append operation. A full list
produces a library diagnostic and exit 1. Use `list_try_push` when exceeding the
bound is an expected input condition. Allocation failure still produces the
checked native runtime error; a successful capacity check does not guarantee
space in the live heap. Status results are direct return values and do not set
`io_error()` or `parse_error()`.

Sorting uses an iterative heapsort: O(n log n) comparisons, constant auxiliary
storage, no recursion or array allocation. Empty and singleton lists work.
Comparisons use signed ordering rather than subtraction, so INT64_MIN and
INT64_MAX sort correctly without an arithmetic-overflow exception. It sorts
only `[0, list_len(list))`; unused capacity remains untouched. It is not stable,
which makes no observable difference for a list of integers.

## Map helpers

| Helper | Contract |
| --- | --- |
| `map_capacity(map) -> int64` | Shared capacity of the key/value arrays |
| `map_reserve(map, minimum) -> int64` | Same minimum/status rules as list reservation; preserve all entries |
| `map_try_set(map, key, value) -> int64` | Insert/update; -27 rejects a new key at 131072 entries without mutation |
| `map_clear(map)` | Remove all entries and active string references; retain capacity |
| `map_release(map)` | Empty the map and detach both backing arrays |

`map_set` remains the convenient operation, exiting 1 on a full new insertion.
Replacing an existing key succeeds even at full capacity. Keys/values remain
immutable strings; matching and lookup are still linear. Reservation avoids
repeated array growth, not O(n) lookup. This is not a hash-map implementation.
Both newly resized arrays are prepared before the map fields are replaced.
Allocation failure retains the terminating native trap.

## Aliases and memory

Collection handles alias their mutable struct state: sorting, clearing,
reservation and release through one handle are visible through another.
Fields are implementation metadata; mutate contents through the library API.
The new capacity/reserve/release/sort operations check structural metadata,
and map clear also checks it. They do not validate uniqueness of manually
edited keys. Arbitrarily editing collection fields is not a supported use.

Growth creates new backing arrays and leaves separately retained old array
aliases unchanged. Release detaches the collection's arrays without
invalidating aliases that still hold them. Map clear writes empty strings into
the current arrays, so aliases of those arrays observe the cleared entries.
Independent immutable string values remain valid.

`list_clear` retains storage for reuse; `map_clear` additionally drops every
active key/value reference so removed strings can be collected. Release drops
owned storage. Neither is manual `free`: reclamation occurs normally when no
remaining reference keeps data alive. `collect()` can request collection;
`memory_used()` includes headers/padding and uncollected garbage. Conservative
stack/payload scanning means exact instantaneous reclamation is not promised.
The 16 MiB live-heap and 131072-element array limits remain unchanged.

## Real CLI example: rsort

```sh
./ramos build examples/rsort.ramos -o rsort
printf '3\n-4\n3\n0\n' | ./rsort
./rsort numbers.txt
```

Windows PowerShell:

```powershell
.\ramos.exe build examples/rsort.ramos -o rsort.exe
'3', '-4', '3', '0' | .\rsort.exe
.\rsort.exe numbers.txt
```

Input is one signed decimal int64 per line, using `text_to_int`'s checked parse
rules. LF/CRLF and a final line without a newline work. Empty input succeeds
with no output; blank/malformed/out-of-range number lines are errors. At most
131072 integers are retained. Output is one ascending number per line;
duplicates stay. Stdin and file input stream while the list retains numbers
needed for sorting. Unicode file paths work.

Usage, parse, input-limit and I/O failures exit 2. Parse/limit errors include the
line number. Input validation and sorting finish before output starts, so an
invalid input emits no sorted result. An output I/O failure can leave a partial
stream. Files close after normal reads and before reported parsing failures;
process exit provides OS cleanup for runtime traps. The app does not modify its
input or create an output file; redirect stdout deliberately if needed.

Tests compare sorting and CLI results with Python's independent integer sort,
cover exact/excess capacity, alias preservation, malformed metadata, Unicode
paths, signed extremes and repeated clear/release cycles exceeding cumulative
heap capacity. Both native targets and compiler fixed points remain release
checks. Collection-workload measurements are published separately; there is
no new general language speed score.
