# Versions, installation and compatibility

Ramos is still **pre-1.0**. Pin a compiler release and the matching standard
library when distributing a project. Minor releases can extend or change
contracts; read their release notes before updating. A patch release is intended
for corrections within the documented contract, and any behavior correction
must be identified. The release notes and contract documents describe what is
supported; a future roadmap entry does not make an API available.

## What a project needs

Keep the native compiler and the `stdlib/` snapshot from the release bundle.
Library paths in `weave` are relative to the file containing them. There is no
global library search path, registry or downloaded dependency resolution. A
simple project can keep `app.ramos` next to its own `stdlib/` directory:

```ramos
weave "stdlib/numbers.ramos"
fn main() { print(num_text(42)) }
```

Run `ramos run app.ramos` during development. Use `build app.ramos -o app`
(or `app.exe` on Windows) to distribute an executable. The compiler, source and
stdlib are not needed to run that executable. CLI/TUI programs include their
Ramos runtime; Linux GUI programs additionally need the documented system GTK3
libraries and a display. Windows GUI uses system controls and libraries.
The release's `SHA256SUMS` identifies downloadable assets.

## Update and rollback

Keep the previous compiler and stdlib snapshot until the project builds and
its application checks pass with the replacement. Rebuild executables when
updating so they contain the intended runtime. Rolling back means restoring
that pair and rebuilding, or restoring the previous complete executable.
There is no runtime module ABI to mix across releases. The private native call
ABI is a compiler implementation detail, not a C/Rust foreign-function ABI.

Check native behavior on each target. Cross-compilation verifies compilation;
it does not verify window interaction, terminal input or OS file behavior.
Do not describe Wine results as native Windows results.

## First stable release

The practical 1.0 goal requires the [application acceptance checks](roadmap-1.0.md),
installation proof, published current measurements and explicit resource limits.
It also needs a reviewed stable-language/library compatibility policy. That
policy is a remaining milestone; this document does not promise that all 0.x
APIs have been frozen. Broader graphics, genuine Windows DPI-transition acceptance and practical libraries
remain active work. A stable version would not imply all of C or Rust's APIs,
platforms, tooling or ecosystem.

Opt-in `gui_open_scaled` requires Windows per-monitor-v2 support (Windows 10
1703 or newer). It restores the previous thread DPI context on close. Existing
`gui_open` keeps default virtualization. Scaled coordinates are logical units;
read [scaling contracts](gui-scaling.md) before handling event kind 6.
