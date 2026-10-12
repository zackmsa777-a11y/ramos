# Portable canvas implementation design

Implement native canvas controls and an ordinary Ramos drawing-command library.
No new language syntax. `weave "stdlib/draw.ramos"` supplies a reusable `Canvas`
command buffer, reset, clear, rectangle/box, line, circle/disk and pixel helpers.
`gui_canvas(id,x,y,width,height)` creates a canvas; `draw_present(id,canvas)` is
fallible and snapshots the active commands for native repaint. A canvas begins
with a white background. Resizing clips/reveals the recorded scene; it does not
stretch coordinates or recompute app geometry. Apps may redraw on resize events.

Library/native contracts:

- At most 1,024 ordered commands in a reusable 49,160-byte buffer.
- Signed coordinates -8192..8192; rectangle dimensions 1..8192; circle radius
  1..8192; opaque `gui_rgb` colors. Native code revalidates all packet fields.
- Negative coordinates and shapes extending beyond the canvas are clipped.
- Malformed packets, unsupported operations/invalid dimensions return -22;
  absent/wrong control IDs return -9. A rejected present retains the prior frame.
- A private active-prefix copy prevents later buffer mutation or reset from
  changing the displayed scene. It remains a managed root while the control
  exists; replacing/closing permits normal reclamation. Allocation failures
  keep the checked managed-heap trap; no false fallible-OOM promise.
- Painting callbacks allocate no Ramos objects, invoke no Ramos callbacks and
  borrow their native Cairo/GDI context only for the repaint. Native paint
  failures surface through the existing event error channel.
- Linux Cairo and Windows GDI use native rasterization. Interior fill colors
  and geometry are checked on both desktops; edge rasterization may differ.
- Use the existing coordinate policy for this first slice: GTK coordinates are
  logical widget units; Windows remains in its default DPI-virtualized units.
  Do not claim per-monitor DPI support. Explicit DPI events/control policy is
  the next slice. Verify GTK scaling with GDK_SCALE=2 as well as its default.

Native boundary: extend `_gui_control` operations 8 (create canvas) and 9 (present).
The packet payload is count followed by six signed 64-bit words per command:
operation, x, y, width-or-x2, height-or-y2, color. Circle uses third coordinate
as radius and a reserved zero fourth coordinate; clear uses all-zero geometry.
Public library helpers own this encoding; application code should not edit it.
A shared validator/copy helper precedes either backend's publication.

Acceptance: independently check packet/limit semantics, raw-invalid rejection,
root/alias/lifetime behavior, native displayed pixels, repaint after buffer
mutation/GC, resizing/clipping, clear/replacement, native resource cleanup,
existing Notes/calculator controls and both compiler fixed points. Ship a small
interactive drawing/plot app as a consumer. Publish only after native Linux
and Windows gates pass; update all five repositories and the book.

Primary platform references:
- https://docs.gtk.org/gtk3/class.DrawingArea.html
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-drawitemstruct
- https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-setdcpencolor
