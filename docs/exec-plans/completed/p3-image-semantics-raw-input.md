# Execution plan: P3 — Image Semantics & RAW Processing

Status: Complete
Owner: repository owner + P3 orchestration agents
Completed: 2026-08-11
Final merge baseline: `835634a58609601605fd0fc18a3028b64225f535`

## Goal

Stabilize Difference domains, native RAW/display semantics, viewer-only Display Gain,
unified image/folder input, bounded Current Comparison Page ownership, lazy RAW
profile resolution, and final production composition without introducing a
processed-RAW analysis domain.

## Completed sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Slice | Outcome | PR | Merge SHA |
|---|---|---:|---|
| P3-0 | P2 closure and P3 roadmap transition | #21 | `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7` |
| P3-A | Difference Gray / Mixed Bit-Depth Support | #22 | `769588bf869847da844cfc0b77c008023d8b048b` |
| P3-B | RAW Native & Display Semantics | #24 | `1817490a08c61da9087efe9c3c6afd8bd85838f0` |
| P3-C | Display Gain Extension | #25 | `7f6bef73e6712f6a14a4d401820a915196e25da2` |
| P3-D | Unified Image Opening & RAW Profile Resolution | #26 | `b16ecc558ac24225e9ddfddfca4e48e37fde61ca` |
| P3-E | Integration, Presentation UI Polish & Phase Hardening | #27 | `835634a58609601605fd0fc18a3028b64225f535` |

P3 roadmap replanning also merged as docs-only PR #23 at
`4c7d1bbbb4476134f76a204578098d35a03feca2`, replacing the earlier speculative
demosaic/Profile Library sequence with the delivered native/display/input program.

## Durable P3 contracts

- Native `ImageDocument.source` is the numerical authority for pixel inspection,
  Statistics, Histogram, Line Profile, Split source data, Difference inputs,
  preload/reload identity, and source residency.
- Difference compatibility is family based: Gray↔Gray, RGB/RGBA↔RGB/RGBA with
  alpha ignored, and same-CFA Bayer↔Bayer.
- Same-effective-bit-depth Difference remains native code-domain. Mixed-effective-
  bit-depth Difference independently normalizes each source by effective full scale
  and stores float32 `[0,1]` Difference with `%FS` threshold semantics.
- RAW Black/White metadata and viewer presentation do not redefine Difference.
- RAW `1×` presentation uses native effective full scale. Gain above `1×` uses
  Black-anchored `B + G * (X - B)`, including CFA-specific Bayer Black anchors,
  without a full-frame Black map or full-frame float64 path.
- Display Gain is presentation-only. Ordinary Gray/RGB use anchor 0; RGBA gains RGB
  while preserving alpha; Difference is excluded from general Display Gain.
- `1×` reuses canonical preview and schedules no gained-preview worker. Gain>1 uses
  resident source and bounded float32 derived presentation with stale-result
  rejection.
- Unified input uses **Open Images...** for selection-oriented direct files and
  **Open Folder...** / folder drag-drop for registration-oriented folder input.
- Runtime ownership is explicitly separated:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
Presented
    ↓
Resident when required
```

- `Analysis Working Set = Current Comparison Page` and viewer slots are page-local
  `1..6`. Selected may exceed six and is paged without changing membership/order.
- Selected membership alone is not generic residency authority. Current Comparison
  Page plus correctness dependencies own bounded protection.
- Comparison Page navigation creates no speculative preload. P2 preload remains
  Folder Position `+1`, exactly one position deep, max-one speculative worker.
- Folder-registered unresolved RAW remains lazy until foreground Current Comparison
  Page work requires it. Cancel starts no worker and does not trigger immediate
  passive re-prompt.
- Difference cache ownership remains independent from decoded-source residency.
- P3-E hardened the production composition boundary: actual replacement page
  `QToolButton` click wiring, real Display Gain focus/shortcut ownership, Qt
  teardown/recreation, large-selection page ownership, and analysis-request
  independence from presentation-only gain.

## P3-E closure evidence

Independent review initially found one production-composition integration-test
blocker. Follow-up commits added actual page-button click wiring coverage, final
production Display Gain shortcut/focus coverage, and deterministic Qt
teardown/recreation; independent re-review reported the blocker resolved with no
remaining production/runtime/architecture blocker.

The repository owner reported the **full local Windows pytest suite PASS** for
code/test head `1af4f6703656028ca7d0e2bdaf369cce029e4bb1`.
The later head `b29963cbf91bf5c022a53d9562e36510e80112a2` changed only
`docs/AGENT_HARNESS_NOTES.md`, so that follow-up did not alter validated runtime or
tests. PR #27 then merged at the final P3 baseline above.

No Ruff, Ruff-format, mypy, pip-check, docs-check, or `git diff --check` PASS is
claimed here unless separately backed by repository evidence.

## Deferred / replaced scope

P3 did **not** deliver the earlier speculative processed-RAW/Profile Library scope:

- demosaic;
- white balance;
- CCM/color conversion;
- tone mapping;
- Profile Library/database;
- profile CRUD/favorites/search;
- fuzzy or size-only profile suggestion;
- sensor/Bayer inference;
- automatic Black/White estimation.

Exact same-basename JSON sidecars and the editable RAW Profile dialog remain the
deterministic file-local profile workflow. Deferred items should return only when
workflow evidence and a coherent numerical/product boundary justify them.

## Transition

The next active program is **P4 — Workflow & Session Productivity**, built on the
P2/P3 bounded working-set, native-analysis, and presentation-only transform
contracts.
