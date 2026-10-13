# Explicit GUI scaling — implementation contract

This milestone adds an opt-in scaling API. `gui_open` keeps its existing policy:
GTK logical units on Linux, default DPI virtualization on Windows. No existing
program is silently opted into per-monitor Windows awareness.

`gui_open_scaled(title: string, width: int64, height: int64) -> int64` opens a
window in logical units (one unit is one pixel at 96 DPI). Existing bounds and
fallible opening statuses apply. Windows requires per-monitor-v2 support
(Windows 10 1703 or newer); missing support returns -38. Linux requires GTK3
and `--gui`, as before. There is no application scale override.

`gui_dpi() -> int64` returns the active window's native DPI, or a negative status
when inactive/unsupported. Success sets `io_error()` to zero. GTK reports
96 times its integer widget scale factor. Legacy Windows windows report 96.
The scaled Windows path supports native DPI 96..768; an unsupported actual
scale fails with -27. GTK scaling remains toolkit-owned.

For scaled windows, all existing control geometry, canvas commands and resize
width/height use logical units. Windows converts control boundaries with
nearest rounding, scales owned UI fonts and uses a native canvas transform.
GDI cosmetic outlines can retain a one-device-pixel stroke; raster edges need
not match Cairo. Positive logical dimensions remain at least one pixel.

`GuiEvent.kind == 6` is a scale change: `id` holds the new DPI; width/height are
the current logical client dimensions. GTK emits it on `notify::scale-factor`;
Windows handles actual `WM_DPICHANGED`, applies the OS-suggested outer rectangle,
rescales retained control geometry/fonts, and queues the event. Resize events
may precede it. No Ramos callback or managed allocation runs inside OS callbacks.
The checked 64-event queue still fails explicitly when full.

Windows saves the prior thread DPI context and restores it on successful close
and failed scaled opening. Scaled fonts are owned and deleted after controls
stop using them. Geometry is privately copied, GC-rooted, and reusable for DPI
changes even after callers mutate or discard property buffers. Native rendering
and managed resources retain their separate budgets.

Verification must distinguish initial DPI, genuine scale changes, simulated
messages, and resource stress. Initial Windows awareness/native placement and
resource counts can run in CI. Real multi-monitor Windows transitions require
an actual desktop whose display scale changes; simulated `WM_DPICHANGED` is not
that proof. Do not declare that acceptance completed without the native report.

Primary contracts: [Windows DPI messages](https://learn.microsoft.com/en-us/windows/win32/hidpi/wm-dpichanged),
[thread context restoration](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddpiawarenesscontext),
[window DPI](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdpiforwindow),
[GTK scale factor](https://docs.gtk.org/gtk3/property.Widget.scale-factor.html).
