# Monotonic timing (0.20)

`monotonic_ms() -> int64` reads a native monotonic clock in integer milliseconds.
Use differences between readings to measure elapsed time or schedule frames.
It takes no arguments, allocates no managed memory and works without terminal
or GUI initialization, including when stdin/stdout are redirected.

```ramos
fn main() {
    let start = monotonic_ms()
    if io_error() != 0 { stderr("clock unavailable\n")
        exit(1) }
    // Do work here, then subtract the same clock's next reading.
    let finish = monotonic_ms()
    if io_error() != 0 { stderr("clock unavailable\n")
        exit(1) }
    print(finish - start)
}
```

Success returns a nonnegative value and resets `io_error()` to zero. Failure
returns -1: Linux reports the negative syscall error; Windows reports -5 for a
failed/invalid counter; conversion beyond signed milliseconds reports -75.
Inspect `io_error()` immediately. The origin is unspecified; values are not
Unix timestamps, dates, durations since program start or portable saved data.
Readings can repeat within one millisecond. OS clock resolution and scheduling
still determine actual timing; millisecond units do not promise exact deadlines.
Suspend/resume semantics are OS-dependent. Do not compare clocks across machines.

Linux x64 uses `clock_gettime(CLOCK_MONOTONIC)` directly, with static executables
and no libc dependency. Windows x64 uses `QueryPerformanceCounter` and
`QueryPerformanceFrequency` from the existing KERNEL32 import table, converting
quotient and remainder separately to avoid multiplying an entire uptime counter.
No external application backend, interpreter or GUI toolkit is added.

For animation, keep the next frame deadline and wait only for the time remaining
before it. Rendering/output consume that budget. Advance simulation time from
elapsed milliseconds, not a guessed number of frames. Diff the last displayed
cells and skip writes when the UI is unchanged. Slow terminals can still limit
rendering; a clock cannot make terminal output instantaneous.

The Ramos rmatrix port demonstrates those techniques. Its twelve scenes retain
bounded ASCII/basic-color rendering and fixed-point approximations; it is not
a feature-complete replacement for Rust nmatrix's truecolor renderer.
