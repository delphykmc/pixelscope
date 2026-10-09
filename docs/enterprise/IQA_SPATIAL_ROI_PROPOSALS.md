# IQA spatial proposal engine — UX-2B (#148), PUBLIC-SAFE

This document describes a **client-side candidate-finding heuristic**, not
an official SNR calculation, producer protocol or server result schema. It
does not modify PUBLIC MAIN or the IQA producer's scientific output.

## Selection contract

Input: one validated `AttributeDisplay.spatial` with numeric signed block
means and `SpatialMap.valid_mask`. Exact source-grid origin/block geometry
is authoritative; invalid cells are excluded from numerator and denominator.

Proposed defaults:

| Parameter | Value | Meaning |
| --- | --- | --- |
| Window | 512×512 source pixels | Clamp to source geometry for small images |
| Stride | 128 source pixels | Include final right/bottom-aligned position |
| Minimum valid coverage | 80% of ROI pixels | Weight fractional boundary cells, no invalid-as-zero mean |
| Candidate count | 3 maximum | Fewer when coverage/difference insufficient |
| NMS | ROI intersection-over-union ≤ 0.10 | Prevent near-duplicate cards |
| Tie-break | Higher score, coverage; then y, x | Deterministic |
| Sign policy | Match known nonzero full-pair official sign | Use raw signed map GRID mean; never alter official scalar |
| Missing or zero official | Exploratory absolute-mean mode | Clearly label exploratory; no winner claim |

For an available nonzero OFFICIAL scalar, candidate score is
`sign(official_value) * GRID_DERIVED_area_weighted_mean`; only positive
scores qualify. This identifies spatially strong regions in the *same signed
direction*, but **does not mathematically establish how much a region
contributes to the official pair score** unless the producer later confirms
compatible aggregation. An exploratory missing/zero-sign candidate uses
`abs(GRID_DERIVED_mean)` and must be labeled accordingly.

Coverage and weighted mean use vectorized separable matrix multiplication
`(Y @ values) @ X.T`, with X/Y containing exact source-pixel overlap
of candidate windows with valid source-grid cells. No per-4K-pixel Python
loop, no display Gain/Range, no color clipping. The expected synthetic
4K 64px-cell grid has 60×34 cells and a few hundred candidate windows,
not a 4K-scale iteration.

## Deferred authoritative producer gate

Owner requested an eventual per-attribute validity criterion:
- The difference must exceed 0.3 dB.
- At least one of original-relative A/B signal levels must exceed -50 dB.

`AttributeDisplay` currently has neither separate A/B spatial original
signal levels nor producer-validated per-region signal eligibility. Therefore
this synthetic candidate engine uses **all prevalidated `valid_mask` cells**
without inventing regional signal levels from a difference map. Future
private adapter might supply A/B raw grids or an authoritative eligibility
mask, depending on contract review. This feature must keep OFFICIAL/global
and GRID-DERIVED/local separated irrespective of schema.

## UI handoff

UX-2C (#149) will place selected Attribute's Top-3 region cards in an
independent **bottom `QDockWidget` owned by the IQA `AnalysisWindow`**.
It should support hide/float, unique object name, isolated per-window
`QSettings` keys, and View menu visibility. This must not register with
the generic PixelScope host `QMainWindow` dock manager. Cards display
source-native equal-coordinate A/B crops with explicit stitched seam;
clicking a card sets the ROI and centers all three viewers. Optional
numbered spatial overlays can be hidden to restore native RGB image.

No unverified server/auth/file reader/export logic is in scope.

## Acceptance

Run `tests/enterprise/test_spatial_candidates.py` independently under
Python 3.10. Verify partial edges, no-data grids, negative OFFICIAL sign,
missing/zero OFFICIAL exploratory fallback, equal-score stable order,
ROI IoU suppression and 4K/64px grid. The corresponding Qt dock and source
crop runtime tests belong to separate UX-2C, including native Windows
PySide6 6.4.2 normal-GC lifecycle and FHD/4K screenshot review.
