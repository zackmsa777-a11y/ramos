# Desktop GUI library (Ramos 0.19.1)

`weave "stdlib/gui.ramos"` adds real desktop windows and native controls on
**Windows x64 and Linux x64**, using the same application source. Windows uses
system USER32/GDI32/COMDLG32 APIs and needs no C runtime or extra toolkit. Linux GUI
executables dynamically link system **GTK3, GObject, GLib and Cairo**, including
their libc/platform dependencies. The library and application logic are ordinary
Ramos; its compiler emits x86-64 instructions and ELF/PE imports directly, with
no C/Python helper, external linker or delegated compiler backend.

The compilers and ordinary Linux CLI/TUI output remain static. Linux GUI is
opt-in with `--gui`; GUI startup in a static build still returns `-38`.
Install GTK3 before launching a Linux GUI executable: on Ubuntu 24.04,
`sudo apt install libgtk-3-0t64`; on Debian 12, `sudo apt install libgtk-3-0`.
Development headers are not required. A running desktop display and installed
fonts are required. Missing shared libraries are reported by the system loader
before Ramos starts; a missing display returns `-19` from `gui_open`.
Verification covers X11/Xvfb on Ubuntu 24.04 and native Windows. GTK chooses its
available display backend; Wayland has not been verified for this release.

## A complete app

```ramos
weave "stdlib/gui.ramos"
fn main() {
    gui_check(gui_open(s"My first Ramos window", 360, 180))
    gui_label(1, 20, 20, 320, 24, s"Hello, desktop!")
    gui_button(2, 20, 60, 120, 32, s"Click me")
    var running = true
    while running {
        let event = gui_event(-1)
        if event.kind == 1 { running = false }
        if event.kind == 2 && event.id == 2 {
            gui_set(1, s"The button works")
        }
    }
    gui_check(gui_close())
}
```

Keep `stdlib/` beside the source. On Windows, with the full release extracted:

```powershell
.\ramos.exe build .\examples\notes.ramos -o .\notes.exe --gui
.\notes.exe
```

On Linux with GTK3 installed:

```sh
./ramos run examples/notes.ramos --gui
./ramos build examples/notes.ramos -o notes --gui
./notes
# Cross-compile the same source for Windows:
./ramos build examples/notes.ramos -o notes.exe --target windows --gui
```

`ramos run SOURCE.ramos --gui [-- ARG...]` compiles for the host, waits for the
app and removes its temporary binary. `build --gui` selects a desktop PE subsystem
on Windows (no console) or a GTK3-linked ELF on Linux. Linux builds without that
flag retain the unsupported GUI stub. Repeated flags are rejected. Existing
output still needs `--force`, and every source remains protected from accidental
replacement. Windows GUI apps launched from Explorer should report errors in
controls instead of relying on inherited stdout/stderr handles.

The included **Ramos Notes** app supports Unicode editing, a file-path input,
Open, Save, Save As and Clear buttons, a colored panel and resizing. Open reads a
selected UTF-8 file; cancellation, I/O failure, invalid UTF-8, embedded NUL or
text beyond the 32767-byte setter limit leaves the current editor and path intact.
Save and Save As create a new UTF-8 file atomically and refuse to overwrite an
existing file. File errors appear in the status label. Opening a valid file
replaces the current note immediately; unsaved-change confirmation and autosave
are not implemented.

## Library API

Coordinates and dimensions are integer client-area pixels. The native toolkit supplies
font rendering, focus, Tab navigation, button activation, text selection and
editing. Native control appearance and available glyphs depend on the OS/toolkit and
installed fonts. These are native desktop controls, not terminal escape codes.

| Function | Behavior |
| --- | --- |
| `gui_open(title, width, height) -> int64` | Open one resizable window; zero succeeds, negative status fails |
| `gui_label(id, x, y, w, h, text)` | Native text label |
| `gui_button(id, x, y, w, h, text)` | Native clickable button |
| `gui_input(id, x, y, w, h, text)` | Single-line editable Unicode text |
| `gui_editor(id, x, y, w, h, text)` | Multiline editor with vertical scrolling |
| `gui_panel(id, x, y, w, h, color)` | Solid colored rectangular panel; The toolkit repaints it automatically |
| `gui_rgb(r, g, b) -> int64` | Construct an opaque color; each component is 0..255 |
| `gui_set_bytes(id, text: bytes) -> int64` | Fallible UTF-8 setter; validation failure preserves current text |
| `gui_set(id, text)` | Update a label, button or editor's text |
| `gui_text(id) -> string` | Read label/button/editor text as validated UTF-8 |
| `gui_move(id, x, y, w, h)` | Move or resize a control |
| `gui_rect(x, y, w, h) -> GuiRect` | Checked explicit rectangle |
| `gui_inset(w, h, padding) -> GuiRect` | Rectangle inside uniform padding |
| `gui_row(bounds, index, count, gap) -> GuiRect` | One horizontal cell, indexed from zero |
| `gui_column(bounds, index, count, gap) -> GuiRect` | One vertical cell, indexed from zero |
| `gui_move_to(id, bounds)` | Move a control to a checked rectangle |
| `gui_open_file(title, initial) -> GuiPath` | Select one existing local file path |
| `gui_save_file(title, initial) -> GuiPath` | Select a local destination path; does not write it |
| `gui_event(timeout_ms) -> GuiEvent` | Pump messages and retrieve one typed event |
| `gui_close() -> int64` | Destroy the window and its controls; repeated close succeeds |
| `gui_check(status)` | Close the GUI and exit 1 with a diagnostic on failure |

Every control gets a unique ID **1..64**. Creation order determines the native
Tab order. There is one top-level window per process; close it before opening
another. IDs are local to the current window and can be reused after close;
applications must not retain old IDs as references to old windows. Call
`gui_event` regularly: it dispatches OS painting, keyboard and control messages.
There are no arbitrary callbacks into Ramos or exposed native handles.

`GuiEvent` has `kind`, `id`, `width`, `height` fields:

| Kind | Meaning | Fields |
| --- | --- | --- |
| 0 | Timeout | Other fields zero |
| 1 | Close requested | App should finish its loop and call `gui_close` |
| 2 | Button activated | `id` is the control ID |
| 3 | Client resized | `width`, `height` are current client pixel dimensions |
| 4 | Parent window key-down | `id` is a Windows virtual-key code on Windows; Linux uses GDK keyvals with common letters, arrows, Backspace, Tab, Enter and Escape normalized to those codes |
| 5 | Editor text changed | `id` is the control ID; programmatic `gui_set` can also cause this |

Text inputs consume normal editing keys themselves; kind 4 is not a global
keyboard hook. Native controls handle mouse input and activation; raw pointer
motion, canvas drawing, images, menus and multiple windows are not
part of this first API. Colored panels provide basic rectangular drawing.
Resize events include the initial layout; Windows also reports minimization as zero dimensions.
Control layout is explicit; there is no automatic layout manager or DPI scaling.
Apps should handle small dimensions without requesting zero-sized controls.
The Notes example keeps a minimum logical layout of 360x240 and clips when the
client is smaller. Clipboard/editing behavior belongs to the native controls.

Timeouts are `-1` for indefinite wait, `0` for immediate polling, or
`1..2147483647` milliseconds. Waiting uses the native message wait API rather
than spinning. Calling poll after close is an error. Resize/paint/focus events
can exist before user input; don't assume the first event is a button press.

## Simple layout

`GuiRect` has integer `x`, `y`, `width`, `height` fields. For a resize event:

```ramos
let bounds = gui_inset(360, 180, 20)
let first = gui_row(bounds, 0, 2, 12)
let second = gui_row(bounds, 1, 2, 12)
gui_move_to(1, first)
gui_move_to(2, second)
```

Use the actual client dimensions, with a sensible minimum as Notes does. Rows
and columns split the available axis equally after gaps and distribute remainder
pixels at cell boundaries: the cells and gaps exactly fill that axis. Indices
are `0..count-1`, count is `1..64`, and gap/padding is `0..8192`. Every cell must
have positive dimensions. Rectangles have nonnegative origins, dimensions
`1..8192`, and right/bottom extents at most 8192. Helpers recheck mutable structs.
Invalid geometry exits 1 with a layout diagnostic. Pure geometry helpers need no
active window. They provide explicit pixel geometry; automatic layout and DPI
scaling remain application responsibilities.

## Open and Save paths

```ramos
let chosen = gui_open_file(s"Open a document", s"")
if chosen.status == 0 {
    let contents = read_file(to_bytes(chosen.path))
    if io_error() == 0 {
        let status = gui_set_bytes(4, contents)
        // Handle status without losing the previous editor text on validation failure.
    }
}
```

`GuiPath` has `path: string` and `status: int64`. Status **0** means an absolute
UTF-8 path was selected, **1** means cancellation, and a **negative** value means
failure. Cancellation/failure returns an empty path. Handle these statuses
explicitly; cancellation is not an error to pass to `gui_check`.

The window must already be open. Both pickers select a single local path and
pump native modal dialog events until selection or cancellation; Ramos code
resumes afterwards. Parent events can be queued meanwhile. Pickers do not read,
create or overwrite files. Save has no overwrite confirmation because it only
returns a path: use `write_file` or stream APIs with an explicit publication
policy. Notes keeps exclusive creation even when an existing path is selected.

Title and initial hint are valid UTF-8 without NUL, at most 4095 bytes each.
An empty hint uses the platform default. Hints are best effort: Linux Open can
preselect an absolute file; Linux Save suggests the leaf filename, while Windows
can use the supplied path. The toolkit chooses the starting folder. Selected
paths are limited to 32767 UTF-8 bytes; Windows uses a 32768-unit UTF-16 native
buffer. Linux filenames that are not UTF-8 return `-22`, preserving the raw path
contract rather than changing filename bytes. No file filters, multiple
selection or directory picker are exposed. A selection does not guarantee a
later I/O operation will succeed. Pickers preserve the process working directory.

## Limits, statuses and lifetime

Window titles are at most 4095 UTF-8 bytes. Text passed to controls is at most
32767 UTF-8 bytes. Native editing is capped at 32767 UTF-16 units on Windows
and 32767 Unicode scalars on GTK. Reading can therefore produce more than 32767 UTF-8 bytes. Invalid UTF-8
and embedded NUL are rejected at the native boundary. Strings stay validated;
empty labels and edits are allowed. Initial client width is 160..4096 and height
80..4096. Control positions are 0..8192 and dimensions 1..8192; drawing is clipped
by the native client area. There are at most 64 controls and 64 queued events.
A full queue fails explicitly instead of silently losing user actions.

`gui_open` and `gui_close` return fallible statuses. Creation/event helpers call
`gui_check`, so they fail with a diagnostic and exit 1. Low-level `_gui_*`
intrinsics are reserved library machinery; file selection additionally reports
cancellation as `io_error() == 1`. Other failures return negative statuses (or
empty bytes with `io_error`) and validate every property independently:
`-9` inactive window/unknown control, `-19` unavailable Linux display, `-16` second active window, `-17` duplicate
ID, `-22` invalid argument/encoding, `-27` oversized read, `-38` missing platform
backend, `-75` event queue overflow, and native errors mapped to existing I/O
statuses. The old checked arithmetic, allocation and bounds contracts remain.

The reclaiming heap roots the GUI state. Collection does not close native
windows. Close releases each native widget tree and owned Windows brushes. System DLLs,
GTK libraries, font caches and toolkit worker threads are process-owned. GTK
allocations are separate from the 16 MiB Ramos managed heap; that cap does not
limit total process memory. Linux exits terminate all process threads. Normal main return, `exit`
and native Ramos traps attempt GUI cleanup automatically. Process termination
also releases OS resources; no durability or user-data save is promised on an
abrupt termination. GUI calls run on the program's single main thread.

## Validation

0.19.1 exercises exact row/column fill for all counts 1..64, invalid geometry,
mutated rectangles, private intrinsic typing, and inactive/static GUI behavior.
Real GTK and native Windows Notes tests open Arabic/emoji filenames, cancel
pickers, reject invalid text without losing the note, save to new Unicode paths,
refuse existing destinations, resize and open another dialog. The GTK fixture
also verifies cancellation/error statuses, managed collection between pickers,
unchanged working directory and that Save selection creates no file.

The retained desktop corpus covers native keyboard/clipboard editing, colored
panel pixels, lifecycle/GC, queue limits, headless errors and process cleanup.
Linux `run --gui` is tested with a real window and temporary-file cleanup; ELF
checks validate imports, ordering, alignment and W^X. Test-only tools are Xvfb,
xdotool, xclip, Python and libX11; none implement application behavior. See
[0.19.1 verification](gui-dialogs-verification.json) and the current
[Linux/Windows self-hosting proofs](bootstrap-proof.json). No new speed claim.

### Retained Windows acceptance (introduced in 0.13)


The focused corpus checks raw argument/type errors, PE subsystem selection,
existing-output preservation and static Linux unsupported behavior. Real desktop
tests create native controls, inspect the actual panel color, inject Unicode text
and an editing key, activate buttons, change the actual client size, and verify
relayout, file contents and refusal to overwrite. A stress fixture opens/closes
12 windows, collects after 40 MiB of temporary allocations and checks cleanup on
return, explicit exit and arithmetic trap. CI runs these on native Windows;
Wine is an additional development runner, not a user dependency.

Use `python tools/windows_proof.py` on Windows. For development under Wine, set
`RAMOS_GUI_WINE_PYTHON` to a Windows Python executable used only by the test
harness, keep one isolated `WINEPREFIX` per X display, and set `DISPLAY`.
The harness reads another process's editor with `WM_GETTEXT`, as required by
[Microsoft's API contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtextw).
Native CI passed **194 Linux tests and 140 Windows tests**, including the GUI
corpus and both compiler fixed points. See [verification evidence](gui-verification.json)
and [the successful run](https://github.com/zackmsa777-a11y/ramos/actions/runs/38057232751).
No new speed claim is made.
