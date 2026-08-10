# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Files workspace, ordered selection, synchronized cursor/range/ROI/line state,
  Folder Position navigation, and fixed one-to-six-image presentation layouts.
- Statistics, Histogram, Line Profile, Difference, Split Channels, structured
  status, and persisted workspace/Plots state.
- RAW10/12/14 plus unpacked uint8/uint16 decoding with deterministic fixtures.
- P1-D/P1-E/P1-F workspace-polish program completed as PR #10–#12.
- Historical P1 plan:
  `docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`.

### P2 — Runtime Foundation, Settings & Performance — Complete

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

- P2-0 merged as PR #13.
- P2-A1 identity/resources merged as PR #14.
- P2-A2 typed settings/runtime integration merged as PR #15.
- P2-B byte-budgeted decoded-source residency merged as PR #16.
- P2-C bounded next-position preload merged as PR #17.
- P2-D deterministic runtime diagnostics merged as PR #18.
- P2-E RUNNING preload foreground reuse merged as PR #19.
- P2-F performance characterization/hardening merged as PR #20 at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.

P2 closes with settings schema v5, independent source/Difference memory budgets,
protected soft-budget source residency, +1 one-position max-one preload, RUNNING
preload authority promotion, deterministic sanitized diagnostics, and
hardware-independent correctness/resource/lifecycle merge gates.

Historical P2 plan:
`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`.

## Revised forward sequence

`P3 Image Semantics & RAW Processing`
→ `P4 Workflow & Session Productivity`
→ `P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

Image-analysis and RAW/input semantics are stabilized before persistent sessions
or remote/release layers are built around them.

## P3 — Image Semantics & RAW Processing

P3-0 merged as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`. P3 roadmap replanning merged as
PR #23 at `4c7d1bbbb4476134f76a204578098d35a03feca2`.

### P3-A — Difference Gray / Mixed Bit-Depth Support — Complete

Merged as PR #22 at `769588bf869847da844cfc0b77c008023d8b048b`.

Delivered:

- Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA Bayer ↔ Bayer;
- explicit rejection of cross-family/size/CFA mismatch;
- native code-domain Difference for equal effective bit depth;
- independently normalized float32 `[0,1]` Difference for mixed effective depth;
- `%FS` normalized threshold semantics;
- bounded mixed-bit metrics/quantiles and cache domain metadata;
- RAW Black/White and display transforms excluded from Difference normalization.

### P3-B — RAW Native & Display Semantics — Complete

Merged as PR #24 at `1817490a08c61da9087efe9c3c6afd8bd85838f0`.

Delivered:

- native decoded RAW remains authoritative source;
- 1× RAW display maps effective native full scale without subtracting Black or
  using White as display maximum;
- generic float32 anchor-based display core:
  `display = anchor + gain * (source - anchor)`;
- RAW gain >1 uses Black-derived anchors, including per-CFA Bayer Black levels;
- no full-frame Bayer Black map and no full-frame float64 gain math;
- 1× canonical-preview fast path, async viewer-local gain>1 path, stale-result
  rejection, and hidden-view derived-buffer release;
- native analysis/residency/Difference semantics remain independent of gain.

### P3-C — Display Gain Extension — Complete

Merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

Delivered:

- one application-session Display Gain state/control at 1×/2×/4×/8×/16×;
- ordinary Gray/RGB and RGB split channels use anchor 0;
- RGBA gains RGB only and preserves canonical alpha;
- RAW keeps P3-B 1× and Black-anchored gain semantics;
- Difference remains excluded from general Display Gain;
- 1× remains no-work canonical-preview reuse;
- gain>1 uses resident source and shared numerical workers with stale rejection;
- Display Gain remains presentation-only and is not persisted.

### P3-D — Unified Image Opening & RAW Profile Resolution — In progress

P3-D replaces the earlier speculative Profile Library/suggestion slice with the
actual input-workflow contract. Its authoritative runtime hierarchy is:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page        # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.
Viewer slots are local `1..6` inside the Current Comparison Page; global Selected
ordinal and viewer slot are separate concepts.

Registration and logical selection are not constrained by six. The six-image
boundary now belongs to the Current Comparison Page working set.

#### P3-D input policy

- **Open Images...** is selection-oriented. Multi-file input registers every
  supported direct image and makes those files the ordered Selected set.
- Selected may exceed six without loss. The initial Current Comparison Page is the
  first six Selected images.
- **Open Folders...** replaces singular Open Folder. It is registration-oriented,
  supports multiple existing directories, deterministically deduplicates resolved
  folder paths, and imposes no six-folder limit.
- Folder registration adds supported contents to Files without changing Selected,
  Current Comparison Page, presentation, layout, active/primary state, ROI, Line
  Profile, Difference, Display Gain, zoom/pan preservation state, source residency,
  or Difference cache.
- Folder registration never auto-selects the first image and exactly two folders
  never create an implicit comparison group.
- Direct image-file D&D uses register + select intent.
- Folder D&D uses registration-only intent for any folder count.
- Mixed D&D selects only the explicitly dropped files while registering folder
  contents without adding them to Selected.
- A registered-but-unselected workspace is valid and prompts the user to select an
  image from Files.
- Unsupported files and standalone `.json` sidecars are ignored. Empty/no-image
  folders do not fail other selected folders.
- obsolete exactly-two-folder pairing helpers are removed from the supported input
  model.

#### P3-D Current Comparison Page policy

- `Selected <= 6` → `Current Comparison Page = Selected`; existing
  Auto/Single/Multi behavior is preserved.
- `Selected > 6` → pages are derived in six-image chunks without changing Selected
  membership/order.
- Multi View uses the Current Comparison Page as its workspace; large-selection
  pages retain six-slot `Grid 3x2` geometry, including short final pages with empty
  unused slots.
- Single View presents one active page-local slot while its analysis/load context
  remains the full Current Comparison Page.
- number keys `1..6` always mean local page slots.
- Left/Right remains fine Previous/Next Selected Image navigation and may cross a
  page boundary automatically.
- Ctrl+Left/Ctrl+Right provides separate non-wrapping Previous/Next Comparison Page
  navigation with a compact range affordance such as `7–12 of 15`.
- page navigation preserves active local slot when possible and clamps it on a
  short final page.
- primary/focus ordering is page-local and cannot alter Selected ordering/page
  membership.
- Statistics, Histogram, Line Profile, selection-derived Difference inputs,
  ROI/Line normalization, current-page loading, residency protection, and local
  slot mapping use one Current Comparison Page authority.
- explicit Difference pair/reference ownership remains feature-specific.
- PageUp/PageDown remains Folder Position only. `Selected > 6` makes Folder
  Position unavailable rather than applying it to a partial page.

#### P3-D RAW resolution

- ordinary PNG/BMP/JPEG bypass RAW profile UI;
- direct RAW with exact same-basename `.json` sidecar preserves validation,
  confirmation suppression, and exact/minimum-size policy;
- direct RAW without sidecar opens editable RAW Profile entry;
- invalid sidecar warns and falls back to editable entry;
- direct RAW cancel prevents erroneous registration;
- direct multi-RAW resolves each file independently;
- folder registration is lazy for RAW: path and deterministic sidecar identity may
  be registered pending;
- Selected-but-off-page unresolved RAW does not prompt, decode, or require
  residency;
- profile resolution occurs when RAW enters a foreground Current Comparison Page;
- one foreground attempt prompts an unresolved RAW at most once; Cancel leaves it
  pending with no worker and passive rerenders do not immediately retry;
- later explicit foreground intent may retry;
- unresolved RAW is not speculatively preloaded until a profile is resolved;
- no profile is inferred from file size, sensor guess, or weak matching evidence;
- existing RawProfile migration, packed/unpacked validation, Bayer pattern,
  Black/White metadata, exact-size policy, same-path reload, and P2
  preload/residency identity remain intact;
- profile UI uses **Load Profile...** / **Save Profile...** terminology while JSON
  remains the storage format.

#### P3-D runtime/resource refinement

P2's exact `source.nbytes` accounting and protected soft-budget semantics remain
authoritative. P3-D narrows generic large-selection protection so **Selected alone
is not a residency owner**. Current Comparison Page plus correctness dependencies
(foreground loads, promoted preload, Difference dependencies, non-reloadable
sources) are protected. Selected-but-off-page sources may be evicted and normally
reload when revisited.

P2 preload remains exactly +1 Folder Position, max-one worker. P3-D does not add a
Comparison Page preload system.

P3-D explicitly does not add a global Profile Library/database, profile CRUD,
favorites/search, last-profile reuse, apply-to-all, size-only/fuzzy suggestion,
sensor/Bayer inference, automatic Black/White estimation, a new profile schema
version, demosaic, white balance, CCM, tone mapping, a new Difference mode,
Display Gain redesign, or broad worker/persistence redesign.

### P3-E — Integration & Hardening

- Cross-check native/normalized Difference with RAW native/display ownership and
  unified input/profile resolution.
- Characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations.
- Verify `Registered → Selected → Current Comparison Page → Presented → Resident`
  ownership under large catalogs, page navigation, Folder Position, preload,
  eviction/reload, Difference cache, and Display Gain.
- Verify Selected<=6 behavior remains production-equivalent.
- Preserve P2 residency/preload/diagnostics contracts.
- Complete automated/Windows validation and durable P3 documentation.

P3 excludes persistent sessions, remote/authentication work, release engineering,
speculative preload-policy expansion, native optimization without profiling
evidence, and demosaic/white-balance/color/tone processing unless separately
approved.

## P4 — Workflow & Session Productivity

- Persistent comparison sessions.
- Recent Files/Folders.
- Saved ROI manager.
- Arbitrary-angle line sampling.
- Alpha overlay.
- Additional productivity/export workflows.

## P5 — Remote IQA Platform

- Remote submission and result workflow.
- Server/job API.
- GPU worker.
- Artifact, heatmap, and result comparison.

## P6 — Identity, Access & Remote Operations

- Login and SSO.
- Token/credential lifecycle.
- Permission/access policy.
- Operational administration.

## P7 — Release Engineering & Distribution

- Exactly PyInstaller 5.7 `onedir`.
- Portable ZIP.
- Inno Setup.
- Clean-PC smoke testing.
- Signing.
- Update strategy.
- Repeatable release process.

## Deferred optimization outside the phase sequence

Schedule only when profiling/user-visible latency demonstrates need:

- preload concurrency one versus two;
- directional/bidirectional or deeper Folder Position preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry;
- coalescing/debounce/cancellable chunking for large-image Display Gain stepping;
- native/SIMD gain optimization beyond current float32 fused affine processing.
