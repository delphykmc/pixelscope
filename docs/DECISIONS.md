# Engineering decisions

## Platform and implementation constraints

- CPython 3.10 x64 is fixed.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image and plot
  primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup is
  the planned installer layer.
- NumPy/OpenCV implementations come first. Native C/C++ optimization requires
  profiling evidence and remains behind numerical/RAW interfaces.
- Expensive I/O and analysis run in bounded workers; widgets do not own decode or
  Difference algorithms.
- Source pixels retain native dtype/channel meaning; overflow-prone arithmetic
  promotes operands first.

## Current product decisions

- Ordered selection is the comparison model; Difference may select any two
  current images.
- Multi View has one fixed layout policy. `_fixed_geometry()` is the sole
  geometry authority; P1-F removed arrangement compatibility state.
- Primary-image reference priority is primary, active, then first displayed.
- Difference caches one native absolute map and derives views/metrics from it.
- RAW storage format, sample container, effective bit depth, endian, and
  alignment remain separate concepts.
- Remote evaluation uses a versioned REST job API boundary.

## Accepted P2 program decisions

- P2 is named **Runtime Foundation, Settings & Performance**.
- P2 proceeds sequentially: P2-A → P2-B → P2-C → P2-D → P2-E after the P2-0
  documentation transition. Each phase starts from the latest merged `main`.
- Settings domain models and persistence adapters are separate. QSettings is an
  adapter, not the application settings model.
- Performance settings are immutable startup snapshots. Changes to startup-only
  budgets or preload state require restart indication.
- Difference-cache default remains 512 MiB unless the repository owner records a
  replacement decision.
- Decoded-source budgeting accounts native decoded `ImageDocument.source`
  arrays only. It excludes previews, Qt textures, Difference/derived caches, and
  transient worker arrays and is not total process memory.
- The decoded-source budget is a soft limit because visible, selected, analysis,
  and active load-target documents may be protected.
- Preload has bounded ownership separate from normal load and may not starve
  interactive work.
- Cancellation and stale-result rejection are distinct; obsolete results must
  not apply even when a decoder cannot stop immediately.
- Diagnostics redact full paths and sanitize failures by default. They contain no
  credentials, bearer tokens, pixel content, or unbounded raw traceback and do
  not start expensive work.
- Packaging, signing, update strategy, and release engineering are P7.
- Login, SSO, token/credential lifecycle, access policy, and remote operations
  administration are P6. P2 does not introduce credentials.

## Current versus planned resource policy

- `DifferenceMapCache` is already byte-budgeted with diagnostics and a 512 MiB
  default.
- Frozen `PerformanceSettings` exists but is not loaded/injected at bootstrap.
- Decoded-source residency currently uses a fixed seven-document reloadable
  policy in `MainWindow`; P2-B moves policy ownership to a byte-budgeted manager.

## Pending owner decisions

These recommendations are not accepted values until the owner confirms them:

- Canonical PixelScope icon design/asset — pending before P2-A.
- Difference-cache default — recommendation: retain 512 MiB; owner confirmation
  pending before P2-A.
- Decoded-source budget default — recommendation: 1024 MiB; pending before P2-B.
- Preload default — recommendation: Enabled; pending before P2-C.
