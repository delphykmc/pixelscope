# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active — P3-E implementation; owner/local validation, independent review, and merge pending
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-10
Current merged P3 baseline: P3-D / PR #26 merge commit
`b16ecc558ac24225e9ddfddfca4e48e37fde61ca`

## Goal

Close P3 by validating the combined Difference, RAW/display, Display Gain, unified
input, Current Comparison Page, and runtime-resource contracts without introducing a
new analysis domain or P4 workflow state.

Native decoded samples remain authoritative. Presentation transforms do not redefine
analysis. Registration, selection, Current Comparison Page membership, presentation,
and residency remain separate ownership layers.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Status |
|---|---|---|
| 0 | P3-0 roadmap transition | Complete — PR #21 |
| 1 | P3-A Difference Gray / mixed-bit semantics | Complete — PR #22 |
| 2 | P3-B RAW native/display semantics | Complete — PR #24 |
| 3 | P3-C Display Gain extension | Complete — PR #25 |
| 4 | P3-D Unified Image Opening & RAW Profile Resolution | Complete — PR #26 |
| 5 | P3-E Integration, Presentation UI Polish & Phase Hardening | Active |

## Completed semantic foundation

### P3-A

- same-effective-depth Difference remains native code-domain;
- mixed effective depth uses independently normalized float32 `[0,1]` Difference;
- Gray, RGB/RGBA, and same-CFA Bayer are supported under explicit compatibility
  rules;
- RAW Black/White/display presentation does not enter Difference normalization.

### P3-B / P3-C

- native RAW source remains authoritative;
- RAW 1× uses effective native full scale;
- gain >1 uses `anchor + gain * (source - anchor)` with RAW Black-derived anchors;
- Bayer channel-specific Black Level is supported without a full-frame Black map;
- no full-frame float64 gain path;
- 1× reuses canonical preview and schedules no gain worker;
- ordinary Gray/RGB/RGBA and split-channel presentation share one session Display
  Gain control while Difference remains excluded;
- source, generation, Statistics, Histogram, Line Profile, Difference, and source
  residency are not redefined by Display Gain.

### P3-D

Merged as PR #26 at `b16ecc558ac24225e9ddfddfca4e48e37fde61ca`.

Authoritative hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page          # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

```text
Analysis Working Set = Current Comparison Page
Viewer Slot = 1..6 within Current Comparison Page
```

Key contracts:

- Open Images is selection-oriented; folder input is registration-oriented.
- Selected can exceed six; pages are derived in six-image chunks.
- Current Comparison Page is the shared analysis/load/protection authority.
- Selected alone is not a generic residency-protection owner.
- Ctrl+Left/Ctrl+Right is non-wrapping Comparison Page navigation.
- PageUp/PageDown remains Folder Position only and is unavailable for Selected >6.
- P2 preload remains +1 Folder Position, one group ahead, max one speculative worker.
- folder-registered unresolved RAW is lazy until foreground page entry; Cancel leaves
  it pending and suppresses passive immediate re-prompt.
- no Comparison Page preload or RAW profile inference/library was introduced.

## P3-E implementation scope

Branch: `feature/p3-e-integration-hardening`
Base: `b16ecc558ac24225e9ddfddfca4e48e37fde61ca`
Recommended PR title:
`[ChatGPT-assisted] Complete P3 integration and presentation hardening`

### 1. Presentation Control Row polish

Keep presentation-specific ownership above the image workspace:

```text
Layout [Auto / Single View / Multi View]
Page   [Previous] [index] [Next] [range / Selected total]
Display Gain [1× / 2× / 4× / 8× / 16×]
```

Implementation requirements:

- preserve Layout/Page/Display Gain command ownership;
- use shared `design_tokens.py` colors, spacing, borders, control height, and disabled
  palette conventions;
- replace character Previous/Next buttons in the production-composed row with compact
  icon-backed `QToolButton` controls;
- reuse PixelScope's programmatic high-DPI icon infrastructure with only the two
  minimal page-chevron icon kinds;
- keep buttons in stable layout positions and disable rather than hide unavailable
  directions;
- preserve Ctrl+Left/Ctrl+Right shortcut state and command ownership;
- provide tooltip, visible/semantic text, accessible name, and `NoFocus` mouse
  command behavior;
- keep Page index/range fixed-width and readable;
- keep Display Gain viewer-only on the right;
- keep the row distinct from the Main toolbar.

No pixel-perfect screenshot test is required. Tests assert widget type, hierarchy,
enabled/visible state, layout index stability, labels, accessibility, and control
height.

### 2. Cross-feature integration invariants

Verify the existing implementation/tests continue to establish:

- Display Gain cannot affect same-bit native or mixed-bit normalized Difference;
- Difference cache identity does not include Display Gain;
- RAW Black/White/display transforms do not enter P3-A normalization;
- Difference derived documents are excluded from generic Display Gain;
- pixel inspection, Statistics, Histogram, Line Profile, Split source authority,
  Difference, source generation, and residency use native source;
- Bayer channel-specific Black Level remains bounded without a full-size Black map;
- 1× remains no-work canonical preview; gain>1 remains float32/derived presentation;
- Split Channels remains transient presentation state, not Registered/Selected;
- explicit Difference pair ownership remains feature-specific and page-valid;
- identical numerical analysis requests retain P2-F dedup semantics.

A P3-E focused regression additionally verifies that changing Display Gain alone does
not reissue Statistics, Difference-input, or Line Profile document requests when the
native Current Comparison Page is unchanged.

### 3. Large-selection hardening

Canonical counts:

```text
1, 2, 6, 7, 15, 50
```

The 50-image case is deterministic ownership testing, not a wall-clock benchmark or
50-source residency stress test.

Verify:

- Registered/Selected identity and global ordering survive paging;
- six-image chunks define Current Comparison Page;
- final short page clears stale slots while keeping six-slot large-selection geometry;
- viewer slots remain page-local 1..6;
- page movement does not mutate Selected;
- foreground `_ensure_loaded` requests are page-bounded;
- Current Comparison Page is protected while off-page Selected is not generically
  protected;
- page revisit can follow normal eviction/reload ownership;
- no selected-wide eager decode or selected-wide preload plan is introduced.

### 4. Navigation / preload / residency preservation

- Ctrl+Left/Ctrl+Right: Comparison Page only, non-wrapping, endpoint shortcut state
  matches buttons/actions.
- Left/Right: fine Selected-image navigation.
- PageUp/PageDown: Folder Position only.
- Selected <=6: preserve P2 +1 Folder Position preload and RUNNING promotion.
- Selected >6: Folder Position unavailable and no Comparison Page preload plan.
- preserve exact `source.nbytes`, protected soft-budget LRU, oversized protected
  source policy, independent Difference cache, and stale token/generation authority.

### 5. RAW / Split / Difference lifecycle preservation

- off-page unresolved folder RAW: no prompt/decode/residency requirement;
- foreground entry: profile resolution then decode after acceptance;
- Cancel: no worker and no immediate passive re-prompt; later explicit foreground
  retry remains possible;
- direct RAW sidecar/no-sidecar/invalid/cancel/multi-RAW behavior remains unchanged;
- Split RGB/RGBA and Bayer channel sets remain presentation-only and Files continues
  to represent the native source;
- Difference fresh/cache-hit presentation remains pair/page validated and Difference
  cache residency remains independent.

## Explicit P4 handoff — not implemented in P3-E

### P4-A — Review Selection & Curation

```text
Registered
↓
Selected
↓
Current Comparison Page
↓
temporary Review Pick Set
↓ Apply
new Selected subset
```

Future UX may include Review Select mode, tile Pick/Unpick, persistent cross-page
picks, picked border/check affordance, pick count, Clear Picks, and Keep Picked.
Non-picked images remain Registered and Files reflects the final Selected subset after
Apply. Zero-pick Apply is disabled. The Pick Set must not own residency, analysis,
Difference, or source loading.

P3-E must not create any of this runtime state.

## Explicit exclusions

- Review Selection / Pick / Keep Picked;
- persistent sessions, Recent Files/Folders, Saved ROI, arbitrary-angle line,
  alpha overlay;
- Profile Library/CRUD, fuzzy/size-only suggestion, sensor/Bayer/Black/White
  inference;
- demosaic, white balance, CCM, tone mapping;
- new Difference mode or gain persistence;
- Settings schema bump;
- Comparison Page preload or preload concurrency expansion;
- residency-policy redesign or broad MainWindow rewrite;
- packaging, signing, installer, updater.

## Validation policy

The Chat implementation agent writes source/tests/docs and performs static review only.
It does not create/search for a virtual environment, install dependencies, or claim a
local Windows PASS.

Owner full Windows validation:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Focused P3-E tests should include the new integration-hardening module plus existing
P3-A/P3-B/P3-C/P3-D, residency/preload, and P2-F request-dedup suites.

### Windows manual characterization

Presentation:

1. Layout selector visual/alignment.
2. Previous/Next page icons.
3. first/middle/last page button states.
4. page count/range readability.
5. Display Gain alignment.
6. dark-theme contrast.
7. narrow/wide resize.
8. Windows 100% scaling.
9. if available, 125%/150% scaling clipping.

Input/paging:

10. Open 15 images.
11. Open 50 images.
12. navigate first/middle/final pages.
13. Single View cross-page Left/Right.
14. number keys on page 2+.
15. folder registration with current selection preserved.

Analysis:

16. Statistics.
17. Histogram.
18. ROI.
19. Line Profile.
20. Difference same-bit.
21. Difference mixed-bit.
22. Split Channels.
23. Display Gain.

Runtime:

24. small source budget page revisit.
25. Folder Position + preload on Selected <=6.
26. PageUp/PageDown unavailable on Selected >6.
27. Help > Copy Diagnostics.

RAW:

28. valid sidecar.
29. missing sidecar.
30. invalid sidecar.
31. lazy folder RAW foreground resolution.
32. Cancel/retry behavior.

## Current validation state

P3-D owner/local Windows validation and independent review are complete; PR #26 is
merged at `b16ecc558ac24225e9ddfddfca4e48e37fde61ca`.

P3-E source/tests/docs are being implemented on the feature branch. Tests were not
run by this Chat implementation agent. Owner/local Windows validation is pending.
Independent review and merge are pending. P3-E must not be marked Complete or moved
to the completed exec-plan archive until merge.
