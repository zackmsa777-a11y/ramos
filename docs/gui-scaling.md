# Explicit GUI scaling — 0.25 preview

This preview adds an opt-in scaling API. Genuine Windows display-transition
acceptance remains pending a native adjustable-display report. `gui_open` keeps its existing policy:
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

## Real Windows test for an agent

Use a Windows x64 desktop whose display scale can be adjusted. Start at **100%**.
Use the matching compiler, `stdlib/` and `examples/` from the release bundle.
Run in PowerShell from the extracted bundle:

```powershell
.\ramos.exe --version
.\ramos.exe build .\examples\scaling.ramos -o .\scaling.exe --gui
if ($LASTEXITCODE -ne 0) { throw 'Demo build failed' }
Get-FileHash .\ramos.exe, .\scaling.exe -Algorithm SHA256
$demo = Start-Process -FilePath "$PWD\scaling.exe" -PassThru `
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
foreach ($dpi in 144, 192, 96) {
    if (-not ($events -match "^scale $dpi ")) { throw "Missing real DPI event $dpi" }
}
if ((Get-Content .\dpi.log | Select-Object -Last 1) -ne 'closed -9') {
    throw 'Window did not close cleanly'
}
if ((Get-Item .\dpi-error.log).Length -ne 0) { throw 'Unexpected runtime error' }
```

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
