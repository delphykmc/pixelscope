# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
Current merged P3 baseline: P3-C / PR #25 merge commit
`7f6bef73e6712f6a14a4d401820a915196e25da2`

## Goal

Stabilize image-comparison, viewer-presentation, RAW-profile resolution, and RAW
native-data semantics while keeping PixelScope an engineering inspection tool.
Native decoded samples remain authoritative; presentation and input convenience
must not silently redefine analysis domains or grow into an implicit RAW
processing/profile-inference pipeline.

P3 deliberately precedes Workflow & Session Productivity. Session persistence and
workflow features should capture stable image/input semantics rather than encode
compatibility paths that are about to change.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Purpose | Status / prerequisite |
|---|---|---|---|
| 0 | P3-0 roadmap transition | Close/archive P2 and establish P3 | Complete — PR #21 |
| 1 | P3-A Difference domain extension | Gray + mixed-bit Difference semantics | Complete — PR #22 |
| 2 | P3-B RAW native/display semantics | Native RAW authority + generic gain core + RAW activation | Complete — PR #24 |
| 3 | P3-C Display Gain extension | Ordinary Gray/RGB/RGBA gain + RAW regression | Complete — PR #25 |
| 4 | P3-D Unified Image Opening & RAW Profile Resolution | One input UX + deterministic RAW profile resolution | Active |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | After P3-D |

Each implementation slice starts from the latest merged prerequisite on `main`.
The semantic ordering above is authoritative unless a new owner decision changes
it.

## Completed P3 foundation

### P3-0 — Program transition

Complete — PR #21 at `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.

### P3-A — Difference Gray / Mixed Bit-Depth Support

Complete — PR #22 at `769588bf869847da844cfc0b77c008023d8b048b`.

Production invariants:

- `GRAY ↔ GRAY`, `RGB/RGBA ↔ RGB/RGBA`, and same-CFA Bayer ↔ Bayer;
- reject cross-family/dimension/CFA mismatch;
- native Difference for equal effective depth;
- independent effective-full-scale normalization to `[0,1]` for mixed depth;
- `%FS` normalized threshold semantics;
- bounded float32 normalized computation and explicit cache-domain metadata;
- RAW Black/White, Display Gain, preview, and demosaic do not participate in
  Difference-domain selection.

### P3-B — RAW Native & Display Semantics

Complete — PR #24 at `1817490a08c61da9087efe9c3c6afd8bd85838f0`.

Production invariants:

- `ImageDocument.source` remains native RAW authority;
- RAW 1× maps effective native full scale; Black is not subtracted and White is
  not display maximum;
- generic presentation core is `display = anchor + gain * (source - anchor)`;
- RAW gain >1 uses Black-derived anchors, including CFA-specific Bayer Black;
- generic affine processing is float32/fused where practical, with no full-size
  Bayer Black map and no full-frame float64 gain path;
- gain changes do not alter native analysis, generation, source residency, or
  Difference identity;
- 1× canonical-preview fast path and presentation-scoped `+` / `-` key ownership
  are retained.

### P3-C — Display Gain Generalization

Complete — merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

Production invariants:

- one QApplication-session Display Gain state provides 1×/2×/4×/8×/16×;
- ordinary Gray/RGB and ordinary RGB split channels use `anchor=0`;
- RGBA gains RGB only and preserves canonical 1× alpha exactly;
- RAW P3-B Black-anchor semantics are unchanged;
- Difference is excluded from general Display Gain;
- 1× schedules no full-frame gain worker and retains no extra gained preview;
- gain>1 uses resident source/shared numerical workers with stale-result rejection;
- hidden/replaced viewer-local gained previews are released;
- Statistics, Histogram, Line Profile, Difference, Split Channel source,
  generation, residency, and cache identity remain independent of Display Gain;
- Settings schema remains v5 and Display Gain is not persisted.

Owner/local Windows validation completed before PR #25 merged. Additional RAW
clipping/highlight/shadow/Bayer observability remains optional/deferred. Demosaic
remains deferred pending a coherent processed-preview boundary.

## P3-D — Unified Image Opening & RAW Profile Resolution

Status: Active on `feature/p3-d-unified-open`.

### Owner decision

The earlier P3-D plan for a reusable Profile Library/profile suggestion subsystem
is replaced by a narrower product need: unify how supported images enter
PixelScope while retaining deterministic RAW profile semantics already implemented
in P1/P2/P3.

No global profile library, CRUD manager, favorites, profile search, file-size-only
or fuzzy suggestion, sensor inference, Bayer-pattern inference, automatic
Black/White estimation, or new profile version field belongs in P3-D.

### Unified user entry points

Final File/Empty Workspace actions:

```text
Open Images...    Ctrl+O
Open Folder...    Ctrl+Shift+O
```

Remove the separate **Open RAW with Profile...** command, Empty Workspace RAW
button, RAW-only signal, and redundant `MainWindow.open_raw()` path.

Open Images supports exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

Picker label:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

Do not expose `*.*` as a RAW selection filter. Unsupported extensions must not be
silently treated as RAW.

### Authoritative input contract

`io.path_discovery` owns the supported extension/filter contract. `ImageInput`
remains the common path plus optional sidecar identity. Open Images, Open Folder,
drag/drop, folder discovery/registration, Folder Position workflows, preload,
reload, and sidecar reload should converge on existing registration/identity
logic rather than adding UI-specific RAW branches.

`.json` is metadata only. It must not appear as an image entry in the Files tree.
Ordinary PNG/BMP/JPEG must bypass RAW profile dialog construction and use the
ordinary decoder.

### RAW profile resolution

For each RAW input:

1. Exact same-basename sidecar exists:
   - parse and validate the JSON profile;
   - preserve legacy profile migration;
   - preserve current confirmation-suppression behavior;
   - preserve exact/minimum RAW source-size policy.
2. No sidecar:
   - open editable RAW Profile dialog;
   - register/load only if accepted.
3. Invalid sidecar:
   - show a clear warning;
   - open editable fallback;
   - never silently apply the invalid profile.
4. Cancel:
   - do not register a new RAW document.
5. Existing path:
   - retain same-path document/profile reload identity.
6. Multi-file RAW selection:
   - resolve every RAW independently;
   - do not add last-profile reuse, size-match reuse, or apply-to-all UI.

The same exact-size policy must remain authoritative for sidecar auto-approval,
foreground load, preload, and promotion identity.

### Profile UI and compatibility

Use **Load Profile...** / **Save Profile...** as user-facing button labels. The
file dialog may remain `JSON (*.json)` because JSON is still the storage format.
Do not change `RawProfile` schema without need. Retain packed/unpacked validation,
effective bit depth, stride/offset/endian/alignment, Bayer pattern, Black/White
metadata, legacy storage-field migration, and Settings schema v5.

### Empty Workspace cleanup

Keep only Open Images/Open Folder primary actions and the existing format hint.
The gesture hint must say **Shift+drag** for Line Profile; stale Alt+drag guidance
must not remain.

### Test coverage

P3-D focused tests must cover:

- File menu/Empty Workspace contain only unified Open Images/Open Folder actions;
- exact supported picker filter and absence of RAW wildcard;
- PNG/JPEG/BMP ordinary route never calls RAW profile dialog;
- valid same-basename sidecar resolution;
- current sidecar confirmation and exact/minimum-size policy;
- no-sidecar dialog accept and cancel-before-registration;
- invalid-sidecar warning/edit fallback;
- multiple RAW files preserve per-file profile identity;
- mixed ordinary/RAW folder discovery and drag/drop use the same resolver;
- JSON sidecars/unsupported extensions are not image entries;
- profile Load/Save user terminology;
- existing folder navigation/preload/reload/residency/Difference/Display Gain/
  Statistics/Histogram/Line Profile/Split Channels regression suites remain green.

### Explicit exclusions

P3-D adds no Profile Library, profile CRUD manager, fuzzy/size-only selection,
demosaic, white balance, CCM, tone mapping, Black/White estimation, new Difference
mode, Display Gain redesign, session persistence, Recent Files/Folders, Settings
schema bump, residency/preload redesign, broad MainWindow rewrite, packaging, or
signing.

## P3-E — Integration & Hardening

Close P3 over the completed Difference/display/RAW/input semantics.

- Cross-check native/normalized Difference and Display Gain independence.
- Characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Verify unified input/profile resolution through navigation, preload, reload, and
  existing-path identity.
- Verify Statistics/Histogram/Line Profile/Difference/Split Channels regressions.
- Complete Windows characterization and durable P3 documentation.
- Do not add unrelated workflow/session or processed-RAW features during closure.

## Cross-phase invariants

P3 builds on, and must preserve unless explicitly redesigned:

- P2 Settings schema v5 migration/future-schema safety;
- exact native decoded-source residency accounting and protected soft-budget LRU;
- independent Difference Map Cache budget ownership;
- `+1`, one-position, max-one preload with foreground priority;
- exact RUNNING preload promotion without duplicate decode;
- advisory cancellation plus token/generation/request stale-result authority;
- observation-only sanitized **Help > Copy Diagnostics**;
- idempotent identical Statistics/Histogram numerical requests;
- expensive I/O/numerics off the UI thread;
- source dtype/channel meaning explicit and overflow-safe arithmetic;
- native source remains recoverable and authoritative when viewer transforms are
  active;
- presentation shortcuts do not override native sibling-widget navigation unless
  explicitly decided and regression-covered;
- input UX does not create a second RAW profile/decode authority.

## Validation policy

For P3-D, the Chat implementation agent writes tests but does not spend time
bootstrapping/running a local virtual environment. The repository owner runs the
Windows `.venv` validation contract:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Do not claim PASS without observed output.

Tests were not run by this Chat implementation agent. Owner/local Windows validation is pending.

Owner manual validation should cover at least:

1. File > Open Images with PNG.
2. JPEG/BMP ordinary images.
3. RAW selectable through File > Open Images.
4. RAW + valid same-basename sidecar.
5. RAW without sidecar → Profile dialog.
6. Invalid sidecar → warning/edit flow.
7. No separate Open RAW File-menu action.
8. No Empty Workspace Open RAW button.
9. Mixed ordinary/RAW folder.
10. RAW drag/drop.
11. Folder navigation/preload with RAW.
12. Display Gain for RAW and ordinary images.
13. Statistics/Difference and other existing analysis regression.

## P3 exit criteria

P3 is complete when:

- P3-A Gray/mixed-bit Difference semantics remain stable;
- native samples remain authoritative and viewer presentation cannot be confused
  with analysis processing;
- generic anchor-based Display Gain remains deterministic/shared by RAW and
  ordinary presentation;
- RAW Black-anchored and ordinary zero-anchored gain remain regression-covered;
- unified image opening has one supported-extension contract and RAW profile
  resolution remains deterministic across all input/runtime paths;
- no speculative profile inference is introduced without evidence;
- existing P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs describe final Difference, Display Gain, RAW, and image-opening
  domains without ambiguity.

Demosaic is not required for P3 completion under the current owner decision.

## Later roadmap after P3

- **P4 — Workflow & Session Productivity:** persistent comparison sessions,
  Recent Files/Folders, saved ROI manager, arbitrary-angle line sampling, alpha
  overlay, and broader productivity/export workflows.
- **P5 — Remote IQA Platform:** remote submission/results, server/job API, GPU
  worker, artifact/heatmap/result comparison.
- **P6 — Identity, Access & Remote Operations:** login/SSO, token lifecycle,
  permissions, and operational administration.
- **P7 — Release Engineering & Distribution:** PyInstaller 5.7 `onedir`, portable
  ZIP, Inno Setup, clean-PC smoke, signing, updater/release process.