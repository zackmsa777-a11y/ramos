# Native canvas drawing (0.23)

Use `weave "stdlib/draw.ramos"` with a GUI build. The library adds an ordinary
`Canvas` struct and helpers; there is no new language syntax or foreign app code.
Linux uses the existing GTK3/Cairo dependency; Windows uses native GDI.

```ramos
weave "stdlib/draw.ramos"
fn main() {
    gui_check(gui_open(s"Drawing",320,240))
    gui_canvas(1,10,10,300,200)
    let canvas = draw_new()
    draw_clear(canvas,gui_rgb(245,247,250))
    draw_rect(canvas,20,20,80,40,gui_rgb(220,70,40))
    draw_line(canvas,0,100,250,140,0)
    draw_disk(canvas,160,60,20,gui_rgb(40,110,220))
    gui_check(draw_present(1,canvas))
    while gui_event(-1).kind != 1 {}
    gui_check(gui_close())
}
```

Build with `ramos build app.ramos -o app --gui` on Linux, or
`ramos build app.ramos -o app.exe --target windows --gui` for Windows.
`ramos run app.ramos --gui` compiles and opens the app. Static Linux binaries
return -38 from GUI operations. See [the GUI contract](gui.md) for prerequisites,
events and errors, and [the interactive plot](../examples/plot.ramos) for resizing.

| Helper | Behavior |
| --- | --- |
| `draw_new()` | New reusable command buffer; empty scene |
| `draw_reset(canvas)` | Clear recorded commands; keep buffer capacity |
| `draw_clear(canvas,color)` | Append a whole-canvas background fill |
| `draw_rect(canvas,x,y,width,height,color)` | Filled rectangle |
| `draw_box(canvas,x,y,width,height,color)` | Outlined rectangle |
| `draw_line(canvas,x,y,x2,y2,color)` | One-unit line |
| `draw_circle(canvas,cx,cy,radius,color)` | Outlined circle |
| `draw_disk(canvas,cx,cy,radius,color)` | Filled circle |
| `draw_pixel(canvas,x,y,color)` | Filled 1×1 rectangle |
| `gui_canvas(id,x,y,width,height)` | Create a canvas in the existing 64-ID GUI table |
| `draw_present(id,canvas)` | Validate and snapshot recorded commands; return status |

Commands draw in order. An empty scene repaints white. A later `draw_clear`
replaces earlier drawing in that frame. Colors are opaque `gui_rgb` values;
there is no alpha, image loading, font drawing or user drawing callback yet.
The canvas has no separate mouse event API in this release.

## Limits, ownership and errors

Each canvas owns a reusable 49,160-byte buffer, holding up to 1,024 commands.
Signed drawing coordinates and line endpoints are -8192..8192; rectangle
width/height and circle radius are 1..8192. Shapes crossing the canvas bounds
are clipped, including negative coordinates. Window/control geometry retains
its existing nonnegative domain. Library misuse exits with `Ramos drawing error`;
checked arithmetic and heap limits still apply.

`draw_present` returns 0 on success, -9 for an absent ID or a control that is
not a canvas, and -22 for a malformed drawing packet. Other native OS failures
remain possible. Use `gui_check` when the app cannot recover. Native code checks
the full active packet before publication; rejection preserves the displayed
frame. `io_error()` also reports the status. Canvas controls cannot be read or
changed using the GUI text API.

Presentation copies only the active command prefix into a private managed
snapshot. Reusing/resetting the caller's buffer, editing its bytes or collecting
garbage does not change the published scene. Replacing a frame or closing the
window releases that snapshot's root for normal managed reclamation. Painting
uses no Ramos allocation or application callback. GDI stock objects are borrowed
and the device context is restored; Cairo/GDI drawing failures use status -5 in the event
error channel (queue overflow retains -75). Out-of-memory still follows the checked managed-heap trap.

Public `Canvas` handles alias like other structs. Sharing the handle shares its
recorded commands. Native display snapshots are independent. Applications should
use helpers rather than mutate the packet's `data`/`count` fields.

## Resize and scaling

Coordinates are local to the canvas. Resizing clips or reveals recorded geometry;
it does not stretch the picture. To reflow a plot, handle resize events, call
`gui_move`, record the new scene and present it. Linux uses GTK logical units;
Windows retains its default DPI virtualization. Explicit per-monitor DPI events
and policy are future work. X11 is verified; Wayland remains unverified.

Cairo and GDI rasterize boundaries differently. Filled interiors, order, clipping
and repaint behavior have the same contract; edge pixels and circle outlines
are not promised to be byte-identical between desktops. This release adds no
comparative graphics-speed claim.

The tests inspect actual native windows: negative clipping, interior colors,
lines, circles, boxes and single pixels; reset/GC repaint; resize; replacement;
empty-frame white; repeated maximum-size snapshots; close. GTK is exercised at
1× and 2× scaling. Native Windows also checks GDI resource stability. See
[canvas verification](canvas-verification.json) for the exact published build.
