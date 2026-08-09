# PixelScope UI/performance iteration status

Snapshot date: 2026-08-09
Current merged runtime baseline: P3-C / PR #25
Merge commit: `7f6bef73e6712f6a14a4d401820a915196e25da2`
Active slice: P3-D — Unified Image Opening & RAW Profile Resolution

## Completed iterations

| Phase/PR | State | Main result |
|---|---|---|
| P0-A / #1 | Complete | Fixed Multi View layouts and primary behavior foundation |
| P0-B / #2 | Complete | Difference byte LRU and chunked metrics |
| P0-C / #3 | Complete | Toolbar/primary icons and action states |
| P0-D / #4 | Complete | Split loading, disabled menus, Difference ordering |
| P1-A / #5 | Complete | Files, Statistics, responsive headers |
| P1-B1 / #6 | Complete | Histogram modes and plot text |
| P1-B2 / #8 | Complete | Line Profile reference and legends |
| P1-C / #9 | Complete | RAW profile workflow and MIPI decoding |
| P1-D / #10 | Complete | Primary ordering, atomic Split transitions, folder navigation |
| P1-E / #11 | Complete | Plots persistence, gestures, Statistics workspace |
| P1-F / #12 | Complete | Fixed-layout compatibility cleanup |
| P2-0 / #13 | Complete | P2 transition and roadmap |
| P2-A1 / #14 | Complete | Application identity and packaged resources |
| P2-A2 / #15 | Complete | Typed Settings/runtime integration |
| P2-B / #16 | Complete | Byte-budgeted decoded-source residency |
| P2-C / #17 | Complete | Bounded next-position preload |
| P2-D / #18 | Complete | Deterministic runtime diagnostics |
| P2-E / #19 | Complete | RUNNING preload foreground reuse |
| P2-F / #20 | Complete | Runtime characterization/hardening |
| P3-0 / #21 | Complete | P3 program transition |
| P3-A / #22 | Complete | Gray + mixed-bit Difference semantics |
| P3-B / #24 | Complete | Native RAW display semantics + generic gain core |
| P3-C / #25 | Complete | Display Gain generalized to Gray/RGB/RGBA |
| P3-D | Active | Unified image opening + deterministic RAW profile resolution |

## Current UI behavior

### Files and workspace

- Files tree exposes loading/resident/error indicators and folder grouping.
- Ordered selection drives fixed one-to-six-image layouts.
- Difference selectors are the comparison-pair authority.
- Split Channels supports RGB/Bayer placeholders and fixed component order.
- Every regular two-to-six-image Multi View exposes primary behavior. Promotion
  preserves Files order and logical identity.
- Two/four/six views remain equal; three/five enlarge the first tile.
- PageUp/PageDown atomically moves one-to-six distinct registered folders by one
  Folder Position. Left/Right remains selected-image navigation and Up/Down
  remains native Files-tree row navigation.
- `_fixed_geometry()` remains the sole Multi View geometry contract.
- Esc clears ROI; Shift+Esc clears Line Profile; Ctrl+drag creates ROI;
  Shift+drag creates Line Profile; Alt+drag creates neither.

### Unified image opening

P3-D makes the visible opening actions:

```text
Open Images...
Open Folder...
```

The previous **Open RAW with Profile...** File action and Empty Workspace RAW
button/signal are removed. Open Images uses one exact supported-family picker:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

`io.path_discovery.ImageInput` remains the common file/folder/drop registration
contract. Ordinary PNG/BMP/JPEG bypass RAW profile UI. `.json` is never an image
entry; for RAW it is attached only when it is the exact same-basename sidecar.

RAW profile resolution remains per file:

- valid sidecar → existing confirmation and exact/minimum-size policy;
- no sidecar → editable RAW Profile dialog;
- invalid sidecar → warning and editable fallback;
- cancel → no incorrect RAW registration;
- multiple RAW files → each profile resolved independently.

The RAW dialog now says **Load Profile...** / **Save Profile...** while retaining
JSON storage/schema migration. No profile library, profile CRUD UI, size-only or
fuzzy suggestion, sensor inference, or automatic Black/White estimation is added.

### Analysis

- Statistics supports Full image and Active ROI with stable copy/CSV behavior.
- Histogram exposes explicit bins and Count/Normalized/Log count modes.
- Line Profile exposes compact legends and explicit Difference reference.
- P3-A Difference supports Gray, RGB/RGBA, and same-CFA Bayer; mixed effective bit
  depth uses normalized `[0,1]` float32 Difference and `%FS` threshold semantics.
- Source residency and Difference-cache ownership remain independent.
- Floating Plots geometry and selected tab persist; title double-click
  maximizes/restores.

### Display Gain / RAW

- One session-local Display Gain control exposes 1×/2×/4×/8×/16×.
- Ordinary Gray/RGB use zero-anchored gain; RGBA gains RGB only and preserves
  canonical alpha.
- RAW 1× maps effective native full scale. Gain >1 remains
  `B + G * (X - B)` with Gray/Bayer Black-anchor policy from P3-B.
- Gain 1× reuses canonical preview with no full-frame gained-preview worker.
- Gain >1 is viewer-local presentation generated from resident native source.
- Pixel readout, Statistics, Histogram, Line Profile, Split Channel source,
  Difference, generation, source residency, and cache identity remain native and
  independent of Display Gain.
- Viewer `+` / `-` steps gain only inside the presentation subtree; Files keeps
  native expand/collapse.
- RAW profile supports unpacked uint8/uint16 and MIPI RAW10/12/14, profile JSON
  migration, exact/minimum source-size policy, same-path reload, Bayer pattern,
  and Black/White metadata.
- Bayer remains native mosaic analysis; demosaic is not implemented.

## Current performance/settings boundary

- Settings schema remains v5.
- Difference Map Cache and Decoded Source Memory remain separate startup budgets.
- Decoded Source Memory uses exact native `source.nbytes` with protected
  soft-budget LRU semantics.
- Preload remains exactly one registered Folder Position ahead, max-one dedicated
  worker, after foreground loading is idle.
- Exact matching RUNNING preload may transfer foreground authority without a
  duplicate decode.
- Runtime diagnostics remain deterministic, bounded, sanitized, and
  observation-only through **Help > Copy Diagnostics**.
- P3-D adds no runtime memory/resource setting, worker pool, Settings key, or
  profile-library persistence owner.

## P3-D validation state

Focused tests are present for menu/Empty Workspace cleanup, supported filter,
ordinary bypass, RAW valid/no/invalid sidecars, cancel safety, multi-RAW profile
identity, exact/minimum-size policy, mixed folder/drop discovery, and profile
terminology.

Tests were not run by this Chat implementation agent. Owner/local Windows validation is pending.