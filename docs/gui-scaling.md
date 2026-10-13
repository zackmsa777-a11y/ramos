# Explicit GUI scaling — 0.25.1 repaint preview

This preview adds an opt-in scaling API. The 13 October Windows 0.25.0 report confirms genuine
144 → 168 → 96 DPI events, editable input and clean shutdown, but reports broken
canvas shapes in captures. Visual acceptance remains incomplete; the cause has
not been independently confirmed. The 200% preset was unavailable. See the
[reported evidence and limitations](gui-scaling-windows-report-2026-10-13.json). `gui_open` keeps its existing policy:
GTK logical units on Linux, default DPI virtualization on Windows. No existing
program is silently opted into per-monitor Windows awareness.

Version 0.25.1 finishes all native child placements before invalidating the
whole parent and each child. This prevents preserved old-scale canvas pixels
from surviving merely because their client region was unchanged. It addresses
a plausible repaint mechanism; it does not establish the cause of the reported
captures or complete real-display visual acceptance. The diagnostic below can
also be run on 0.25.0 before trying the candidate. See the native
[MoveWindow repaint contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-movewindow)
and [full-client invalidation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-invalidaterect).

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

## Real Windows test for an agent

Use a Windows x64 desktop whose display scale can be adjusted. Start at **100%**.
Use the matching compiler, `stdlib/` and `examples/` from the release bundle.
Record the original display scale so it can be restored after closing.
Run in PowerShell from the extracted bundle. Choose a fresh output name; the
bundle already includes `scaling.exe`:

```powershell
.\ramos.exe --version
.\ramos.exe build .\examples\scaling.ramos -o .\dpi-test.exe --gui
if ($LASTEXITCODE -ne 0) { throw 'Demo build failed' }
Get-FileHash .\ramos.exe, .\dpi-test.exe -Algorithm SHA256
$demo = Start-Process -FilePath "$PWD\dpi-test.exe" -PassThru `
    -RedirectStandardOutput "$PWD\dpi.log" `
    -RedirectStandardError "$PWD\dpi-error.log"
Start-Process 'ms-settings:display'
```

Keep the same demo window open. In **Settings → System → Display → Scale**, set
**150%**, then **200%**, then **100%**, waiting for the demo label to update each
time. Stay on the display you changed. Do not use custom scaling that requires
signing out; that cannot demonstrate a running-window transition. If these
preset values are unavailable, record the actual offered values instead.

At each scale, check that the input stays editable, Arabic/emoji remain intact,
controls do not overlap, the blue box/red disk/green line remain visible, and
text stays crisp. A geometry comparison should use client coordinates and the
native DPI, not the outer window frame. Logical dimensions may differ slightly
because Windows chooses the suggested rectangle and the user may resize.

Close with the demo's **Close** button, then run:

```powershell
$demo.WaitForExit()
Get-Content .\dpi.log
Get-Content .\dpi-error.log
if ($demo.ExitCode -ne 0) { throw "Demo exited $($demo.ExitCode)" }
$events = Get-Content .\dpi.log | Where-Object { $_ -match '^scale ' }
$events
# Set this to the exact presets you actually selected, in order.
# For 100% -> 150% -> 175% -> 100%, use @(150, 175, 100).
$selectedPresets = @(150, 200, 100)
$expected = @($selectedPresets | ForEach-Object { [int](96 * $_ / 100) })
$actual = @($events | ForEach-Object { [int](($_ -split ' ')[1]) })
if (($actual -join ',') -ne ($expected -join ',')) {
    throw "DPI events differ: expected $expected; got $actual"
}
if ((Get-Content .\dpi.log | Select-Object -Last 1) -ne 'closed -9') {
    throw 'Window did not close cleanly'
}
if ((Get-Item .\dpi-error.log).Length -ne 0) { throw 'Unexpected runtime error' }
```

Restore the original display scale after the demo closes. An unavailable preset
is **untested**, not a missing event for a change you actually performed. A
substitute preset does not certify the unavailable 200% / DPI 192 transition.

Return the log, compiler hash, Windows version, actual display scaling sequence,
and visual observations. Missing genuine events or an unusable control is a
failure, even if compilation succeeded. Record a sign-out-only setup as unable
to perform this transition test. This test does not prove multi-monitor movement;
that needs two real displays at different scales and the same checks while
moving the open window between them. Never send fabricated `WM_DPICHANGED`
messages as a substitute.

## Automated resource scope

The native probes exercise 200 acknowledged allocation/control-update steps
(200 MiB of transient managed buffers with less than 256 KiB retained after
each collection). Windows also alternates 20 scaled/default windows and checks
native geometry, fonts, canvas/panel pixels, GDI/USER objects and process handles.
Linux changes the real GTK XSETTINGS scale 1 → 2 → 1 and checks pixels,
open file descriptors and resident-memory growth after warm-up. These are
bounded churn and lifetime checks, not a claim of hours-long soak testing or
support for more than the existing 16 MiB live managed-memory budget.

## Diagnose incomplete canvas captures

Keep the same demo process alive and fully visible, without another window
covering it. At a scale where shapes look broken, record whether the defect is
visible directly on the screen as well as in the automation screenshot.

The repository's `tools/canvas_capture.py` is a Windows-only Python diagnostic,
not part of a Ramos program or runtime. Using Python 3, run:

```powershell
py -3 .\tools\canvas_capture.py --pid $demo.Id --output .\capture-175
```

It captures the canvas via native GDI **before** requesting any repaint, renders
an independent GDI reference for the public demo's box/disk/line, then requests
a full canvas repaint and captures again. It writes `before.bmp`,
`reference.bmp`, `after-redraw.bmp`, and `capture.json`. It does not change DPI,
edit the process's private memory or fabricate a DPI notification. The demo
remains open; closing/restoring scale is still your responsibility.

Return all four files alongside the scale log. If the before image differs but
the image after repaint matches, that supports stale painting as the cause. If
both match despite a broken automation screenshot, investigate capture artifacts.
If both differ, inspect the independent images before diagnosing a drawing error.
CI's full-canvas comparison at its initial DPI does not certify a real transition.
