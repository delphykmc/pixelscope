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
- P2 proceeds sequentially:
  **P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E** after the P2-0 documentation
  transition. Each slice starts from the latest merged prerequisite on `main`.
- P2-A1 is the application identity/resource foundation delivered by PR #14.
  P2-A2 owns typed settings, persistence, the Settings dialog, and
  Difference-cache startup injection.
- Settings domain models and persistence adapters are separate. QSettings is an
  adapter, not the application settings model.
- Performance settings are immutable startup snapshots. Changes to startup-only
  budgets or preload state require restart indication.
- The P2-A2 Difference-cache default is confirmed as 512 MiB.
- The current canonical PixelScope identity is a blue-gray image/scope/pixel mark
  with a restrained amber accent. The editable SVG, runtime PNG, and Windows ICO
  are colocated under `src/pixelscope/assets/icons/`; release naming or artwork
  may replace the triplet before P7, but duplicate canonical copies are not
  allowed.
- `scripts/generate_icon_assets.py` is the canonical derivative path. It uses the
  pinned Qt SVG renderer and must preserve transparent 16, 20, 24, 32, 40, 48,
  64, 128, and 256 px ICO frames in ascending order.
- Application icon lookup uses package-resource bytes and may not depend on the
  current working directory or a source-tree absolute path.
- Executable-file, pinned-shortcut, installer-shortcut, AppUserModelID, signing,
  and final shell-identity policy remain P7 concerns unless Windows source-run
  validation demonstrates an earlier runtime blocker.
- Decoded-source budgeting accounts native decoded `ImageDocument.source`
  arrays only. It excludes previews, Qt textures, Difference/derived caches, and
  transient worker arrays and is not total process memory.
- The decoded-source budget is a soft limit because protected documents may
  temporarily exceed it. P2-B extends the protected-set policy beyond the
  current visible-document and active-load-target inputs.
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

- The canonical SVG/PNG/ICO icon triplet, reproducible generator,
  package-resource loader, and `QApplication` assignment are P2-A1 boundaries.
- `DifferenceMapCache` is already byte-budgeted with diagnostics and a 512 MiB
  default.
- Frozen `PerformanceSettings` exists but is not loaded/injected at bootstrap.
- Decoded-source residency currently uses a fixed seven-document reloadable
  policy in `MainWindow`; P2-B moves policy ownership to a byte-budgeted manager.
- The current residency protection inputs are visible documents and active load
  targets. Selected and analysis protection are P2-B additions.

## Pending owner decisions

These recommendations are not accepted values until the owner confirms them:

- Decoded-source budget default — recommendation: 1024 MiB; pending before P2-B.
- Preload default — recommendation: Enabled; pending before P2-C.
