# Issue #210 W00 — detailed technical contract (design only)

Status: **PROPOSED / independent review required**. No product implementation, no W00 Complete.
Repository: `delphykmc/pixelscope`; pinned PUBLIC MAIN baseline: `473af64b0b40905683594d218470ca194d81242c` (2026-11-04 GitHub branch read). Parent: https://github.com/delphykmc/pixelscope/issues/210 ; policy/technical-direction comment: https://github.com/delphykmc/pixelscope/issues/210#issuecomment-6608504294 .
This document is a design, not evidence of Windows reproduction, test execution, or approval. Branch starts at pinned MAIN. Later changes must rebase/re-audit rather than assuming this SHA remains current.

## 1. Authority, audited evidence, and limitations

Read baseline `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/SESSION_CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, `docs/iqa/IQA_OWNERSHIP.md`; reviewed `ui/image_viewer.py`, `ui/multi_compare_view.py`, `ui/folder_display_tags.py`, `ui/analysis_export.py`, `io/analysis_export.py` plus Issue #210. Source code review is **targeted**, not a full repository-wide static audit; call-sites not enumerated below are an explicit verification gate for the first implementation PR.

- Source authority: Registered → Selected → Current Comparison Page (max six) → Presented → Resident. `MainWindow` owns registration, selection, page and worker/lifetime boundaries. A Review is NOT another source/residency/cache manager (`ARCHITECTURE.md` first 80 lines; `CURRENT_STATE.md` section “Authoritative local workspace model”).
- `ImageDocument` native samples are numeric authority. `SpatialSampling` maps transient reference coordinates to YUV chroma footprints/Bayer phase. ROI is sole `MainWindow._shared_roi` half-open reference-space rectangle; never create per-image clipped ROIs (`ARCHITECTURE.md` first 40 lines).
- `SESSION_CONTRACT.md` “File and compatibility boundary” specifies `.pixelscope`, UTF-8 JSON, `pixelscope-session` v1, normalized absolute path, no fuzzy relocation, atomic writes, legacy comparison-set v1 read. Session explicitly excludes viewer transforms, workers and calculated results (lines 108–123); its 17-stage restore reuses existing lifecycle, including exactly one *explicit* Difference Calculate for an eligible saved recipe.
- `MultiCompareViewState` already exists with `active_document_id` and `ranges`; `capture_view_state()` and `restore_view_state()` are live display-only methods (`ui/multi_compare_view.py` lines 16–22, 335–365). Do not add a second live state manager; W04 owns an adapter and selective extension.
- `ImageViewer.zoom_percent` currently derives `100 / viewPixelSize()[0]` (line 361); `zoom_100_percent` uses graphics viewport pixel dimensions and min(reference size, viewport) with `setRange` (lines 703–716). The observed 96% could reflect the graphics ViewBox effective rect, aspect lock or DPR, but **root cause is unverified**. Do not change label alone.
- `FolderDisplayTagController` already persists per-folder tags to QSettings and updates `document.display_name`; its method-hook installation/lifecycle needs careful explicit ownership review (`ui/folder_display_tags.py`). Design introduces no new runtime method replacement.
- `io/analysis_export.py` already writes Histogram, Line, Difference metric CSV and PNG. Histogram includes bounds; Difference CSV includes domain/bit depths; therefore U02 is **specifically Statistics ROI CSV**, not “all exports lack ROI”.
- Base/Reference/SUB boundary: no Base imports of Reference or Enterprise, no SUB namespace files, no IQA-specific scoring inferred from generic Review (`docs/iqa/IQA_OWNERSHIP.md` sections Ownership/Path ownership).
- CPython 3.10 x64, PyInstaller exactly 5.7 onedir. `core/` and `io/` remain Qt-free; bounded worker for I/O, digest, crop/encode; deterministic idempotent teardown and normal cyclic GC. No full pytest in hosted CI (`AGENTS.md`, `QUALITY.md`).

### U01–U11 evidence classification at this baseline

These categories describe **design disposition**, not newly executed reproduction. Direct observations are from Issue #210's documented original investigation; verification column is explicit.

| ID | Classification | Grounded evidence and disposition | Current W00 verification |
|---|---|---|---|
| U01 | unverified | Issue reports 96% after 1:1; code uses viewport-based range and `viewPixelSize`. Physical-pixel oracle/real DPI not checked. W01 reproduce then fix. | Not reproduced in this run |
| U02 | contract change | Issue's RAW Statistics ROI CSV omitted X/Y/W/H/scope/profile; other Histogram export already includes bounds. W02 additive context bundle; legacy CSV unchanged. | Issue observation only |
| U03 | proposed | Same-basename tile ambiguity observed; existing folder Display Tag functionality already exists. W03 reuse, extend disambiguation. | No fresh UI reproduction |
| U04 | contract change | Session v1 intentionally lacks findings/viewport; new separate Review v1. | Confirmed document contract |
| U05 | proposed | Individual CSV/PNG export exists, cohesive static report absent from documented flow; W10 aggregation, not replacement. | No full export traversal |
| U06 | contract change | Existing Primary reorder and derived Difference display are intentional; explicit presets and view continuity proposed. | No fresh UI reproduction |
| U07 | proposed | Issue records narrow-window Plots congestion/wide-toolbar spacing; design UX enhancement, not measured performance. | No new visual measurement |
| U08 | proposed | Issue records unwieldy RGB 12-row table; W07 pivot presentation while preserving raw metrics. | No new measurement |
| U09 | already fixed | Existing RAW profile Load/Save, stride automation and validation are already implemented; *reuse UX* is proposed W08. “already fixed” applies to baseline capabilities only. | Source/issue evidence, no new run |
| U10 | contract change | Native supported YUV is restricted 8-bit Y-first interleaved UV / BT.601 Full preview; expansion is conditional W11. | Existing documented contract |
| U11 | contract change | Folder navigation is natural ordinal, not scene matching. Matching is conditional W12, not a defect in ordinal. | Documented semantics |

No newly reported `reproduced` classification: code read and historical Issue observations do not constitute an independent reproduction. No claim is made that the 11 observations are all still defects. W01/U01 and UI layout must be verified on owner Windows.

## 2. Locked decisions and detailed decision table

D01 physical source-reference pixel ↔ one physical monitor pixel at 100%; D02 independent Review; D03 human-confirmed relocation; D04 offline static report ZIP are owner-approved. T01–T08 directions are fixed by Issue comment, while the following wire/API details are **proposed W00 technical choices for independent review**.

| ID | Proposed executable choice | Invariant / review gate |
|---|---|---|
| T01 | Use **effective ViewBox scene transform × devicePixelRatioF**, not outer viewport width, as physical scale authority. | Test 100/150/200% DPI + resize; ratio 1 within geometry rounding tolerance. |
| T02 | Persistent source key is Review-local UUID mapped to immutable captured locator/fingerprint; runtime document ID is ephemeral; alias is display-only. | Tag change never changes source/cache/generation identity. |
| T03 | Extend live `MultiCompareViewState` via adapter; write Qt-free `ReviewViewStateV1` center + physical scale + per-tile state when sync off. | Layout/mode restoration after terminal load & layout settle; no raw QWidget persistence. |
| T04 | UTF-8 JSON extension `.pxreview`, `kind=pixelscope-review`, `schema_version=1`, strict mandatory validation. | Never modify `.pixelscope` Session v1 reader/writer; future versions rejected read-only. |
| T05 | Bounded explicit candidate directory selection, SHA-256 exact verification before relink when available; user confirms every candidate. | Filename/size/mtime never confer verified status; unverified sources cannot silently restore findings. |
| T06 | Frozen numerical measurement snapshots carry request ID, per-source generation, pair/channel/ROI/domain/profile and metric revision. | No worker/array/QObject in serialized record, no implicit recalculation. |
| T07 | ZIP root manifest + static report + assets + machine-readable context/snapshot; deterministic paths and SHA-256 entry hashes. | No default private paths or full-resolution original bytes, offline HTML only, atomic publish. |
| T08 | Read/validate/stage, then canonical MainWindow transaction; cancellation/failure before commit leaves workspace untouched. | Preserve ownership, no implicit Difference Calculate on finding activation. |

## 3. Pixel-accurate geometry (W01 contract)

Let `r` be a reference-space coordinate; `T` the current Qt `ViewBox` reference→graphics-scene→viewport mapping, including aspect lock, actual ViewBox geometry and any axis transforms; `d=viewport.devicePixelRatioF()` (device pixel per Qt logical pixel). For a locally axis-aligned, non-sheared viewer, use basis vectors:

`s_x = d ||T(r+(1,0))-T(r)||_2`; `s_y = d ||T(r+(0,1))-T(r)||_2` physical pixels / reference pixel.

**Exact 100%** requires `s_x=s_y=1`, 200% → 2, 400% → 4. If graphics transforms are nonuniform, rotated or sheared, do not report “100%” as exact; reject/normalize through owning ViewBox transform. For native YUV chroma `reference_shape` refers to luma extent and mapped cells do *not* create a new 100% zoom authority; Bayer phase mapping similarly remains reference-space. The on-screen header computes `100*s_x` only when `s_x≈s_y`; otherwise display nonuniform/unknown instead of a misleading percentage.

Algorithm contract: `set_physical_zoom(viewer, percent, anchor_ref)` reads **effective** ViewBox rect after Qt layout, computes required reference units/logical pixel `d/(percent/100)`, applies range with `padding=0` and aspect lock preserved, then measures actual `T`; correct using bounded feedback (max two layout-settled passes) or report unavailable. Do **not** min-clamp requested range to image bounds: a small image can show canvas padding while still being exact 100%. Fit is distinct and may be any ratio. Multi View sync publishes canonical *reference-space center + physical scale*, not identical viewRanges across differently sized tiles; asymmetric tiles get differing visible bounds while matching physical scale and center. Existing `_apply_range` must be audited against this requirement. Include pixel-center convention at `(i+0.5,j+0.5)`; use high-DPI physical capture or transformed QPointF oracle at integer centers, checkerboard/impulse fixture and edge/bounds. Tolerance: physical scale relative error ≤0.5% after layout settle (implementation precision target), mapped pixel-center discrepancy ≤0.5 physical pixel; do not loosen to fit observed 96%. Fractional-DPR and odd viewport require a separate rounding record. Recompute on screenChanged/DPR/resize/Plots/layout changes. Guard zero-size/nonresident/closing viewers; fit stays available. This tolerance is proposed for design review, not an observed PASS.

API proposal (UI): `PhysicalZoomMeasurement(scale_x: float, scale_y: float, dpr: float, valid: bool)`; `measure_physical_zoom(viewer) -> PhysicalZoomMeasurement`; `set_physical_zoom(viewer, percent: float, center_ref: tuple[float,float]) -> ZoomApplyResult`. Never put Qt in core.

## 4. Identity, alias, and view-state DTOs (W03/W04)

`ReviewSourceV1`: `source_key` UUID string; `locator` (`basename`, optional user-approved *relative* path hint confined to chosen relocation root, optional original path only in local Review when explicit opt-in); `native_signature` (shape, layout, dtype, endian, strides, effective bits, alignment, channel/subsample/CFA, profile key/revision); `fingerprint` (`algorithm=sha256`, `digest` hex or null, `size_bytes`, `mtime_ns` advisory, `state=verified|unverified`); optional display tag snapshot. Never persist raw QObject, runtime `document_id`, preview or absolute private path in *shareable* reports.

`resolve_display_alias(sources, source_key, user_tag, path_components) -> DisplayLabel`: normalized nonblank explicit tag (where existing folder tag contributes) → unique shortest containing parent-directory suffix + basename → basename → stable short UUID suffix. Resolve uniqueness over *all current page sources*, using NFC and casefold collision detection; preserve original Unicode for display. Same explicit tag collisions receive unique path/suffix qualifiers, never silently identical labels. Role prefix (`Reference/Primary`, `Target`, `Active`, `Picked`) is a separate overlay and is neither identity nor cache key. On tag mutation re-render presentation only; preserve selection, analysis requests, Difference key and source generations. Existing folder tag/QSettings storage stays intact.

`ReviewViewStateV1`: `reference_source_key`, `page_source_keys` ordered (≤6), `active_source_key`, `primary_source_key`, `layout_kind`, `presentation_mode`, `sync_enabled`, `center_ref_xy` (finite reference pixel-center coordinates), `physical_scale` (>0 finite), `per_source` map of source_key→(center, physical scale) required when sync false; optional `visible_bounds_ref` diagnostic only. Preserve zoom+center, not frozen visible rect during resize. Single source/difference focus is presentation intent, not extra Selected authority. Unknown layout/mode or duplicate source keys: reject; absent source: mark unavailable, never map by slot ordinal alone.

Live adapter `capture_review_view_state(MultiCompareView, source_key_map)` returns DTO only after state settles; `restore_review_view_state(dto, resolved_sources, epoch)` stages source/page/role via canonical MainWindow, waits for terminal foreground load + Display Gain preview + final layout/resize, then applies sync, scale, center, Active, ROI and optional valid Difference visibility. Guard callbacks on `epoch`, close and source generation; one apply per epoch, no nested event loop; late viewport mutation is dropped. A missing/changed/reference-size-mismatched source produces explicit partial/not-restored reasons, not quiet clamp. **Difference recipe activation is NOT calculation**; if user explicitly chooses “Recalculate Difference”, use existing DifferencePanel Calculate path only, no direct provenance injection.

## 5. Review v1 JSON and compatibility (W09)

Minimal illustrative wire shape (unknown fields in required/critical objects rejected; optional future extensions permitted only under `extensions` and never executed):

```json
{
  "kind": "pixelscope-review",
  "schema_version": 1,
  "document_id": "uuid",
  "created_utc": "2026-11-04T00:00:00Z",
  "updated_utc": "2026-11-04T00:00:00Z",
  "sources": [],
  "workspace_intent": {"source_order": [], "page_anchor_key": null},
  "findings": [],
  "extensions": {}
}
```

Every finding: `id` UUID; `title` nonblank max 256; `note` max 32 KiB; `tags` array ≤32 of bounded UTF-8 strings; `source_keys` ordered nonempty; `roi_ref` null or strict integer `{x,y,width,height}` half-open with x,y≥0, width,height>0 and full reference-shape containment; `line_ref` nullable coordinates; `view_state` DTO; `analysis` array of immutable snapshot references; `captured_utc`; `difference_intent` nullable (exact pair/channel/mode/threshold, not cached map); `availability` machine-readable. A Review may contain a *copy of Session-intent fields as a typed adapter* but **must not embed an opaque `.pixelscope` file, change Session parser, or automatically cause Session restore**. Named findings may be edited as metadata, but analysis capture records are immutable/revisioned, not silently rewritten after a source change.

Parser: max JSON bytes (proposed 16 MiB), max 1000 findings, max 10000 source records, finite floats only, UUID uniqueness, no path traversal, no duplicate object keys, strict type checks (bool is not int), reject unknown future `schema_version>1` and unknown `kind` **without changing workspace or file**; no automatic migration or fallback to Session v1. Unknown future optional extension values may be preserved on roundtrip only if safe bounded JSON; they never change interpretation. Writer emits canonical UTF-8 no NaN, deterministic sort/order. Session v1 and legacy comparison-set goldens must remain byte/schema semantically compatible under their original readers; Review open must not route through Session handler.

## 6. Fingerprint, relocation, and restore transaction (W09)

On capture record `size_bytes`, `mtime_ns` advisory, semantic decode signature, full-file SHA-256 if already available or asynchronously hashed in bounded worker. A pending digest is recorded as `unverified`, not “same content”. Hash streams in chunks; never materialize full original merely for fingerprint; stat before/after hash and reject unstable file; size budget/progress/cancel reported. Recompute SHA-256 for selected relocation candidates, with owner consent for potentially long/network paths. Exact digest + decoder signature = verified; digest mismatch = changed (may allow explicit *new source* import, never silent rebind of previous measurements). Matching basename/mtime/size alone only produces candidate, not verification.

Resolution order: (1) registered runtime canonical source if fingerprint confirmed; (2) saved local locator if user explicitly permits local path; (3) user-selected directory roots, bounded depth/file-count and suffix/size candidate filtering worker; (4) present candidates with verification strength and resolved path; (5) explicit human confirmation for **each** relink, even a unique verified candidate. No recursive whole-disk search, no network discovery, no symlink escape from chosen root, no auto-overwrite. Missing candidates remain unresolved; ambiguous candidates require selection; 0 viable sources leaves existing workspace untouched. A source may be `verified`, `candidate-unverified`, `changed`, `missing`, `unsupported-profile`; source snapshots and old metrics always labeled “captured evidence”, never relabeled current.

Restore state machine: parse+validate document (read once) → validate bound limits → probe/hash/candidate search (worker) → user map confirmation → stage and validate all applicable source interpretations/ROI/line/pair without mutating UI → obtain MainWindow transaction epoch and input shield → commit canonical registration/selection/page (only if at least one usable selected source and commit preconditions still hold) → foreground terminal load → gain/split/layout settle → restore applicable ROI/line/view (validated against actual reference bounds), leave stale Difference uncalculated → release overlay. Before commit, cancel/error = *zero mutation*. After commit, partial load is explicitly reported, no claim of full rollback; replay is idempotent; new input cancels/revokes old epoch rather than interleaving. Close/shutdown invalidates epoch and releases workers/overlay without accessing deleted widgets. No nested modal event loop during asynchronous restoration. Reopen changed generations invalidates live result eligibility, not historic captured evidence.

Save: serialize validated immutable DTO to same-directory exclusive temporary name; write UTF-8, flush+fsync, `os.replace` to requested destination, fsync directory when platform supports, clean temp on failure. Post-extension path collision must be confirmed **after extension has been added** (never rely solely on native Save dialog confirmation). Refuse writing a Review or bundle over source image, legacy Session or existing unrelated file without explicit overwrite confirmation; do not touch directory on Cancel before staging. On Windows os.replace PermissionError/read-only/antivirus lock → preserve existing destination and report error, retry only via explicit action. Concurrent saves serialize per destination, no lost-update silent success.

## 7. Immutable analysis / request consistency (W02/W09/W10)

Qt-free `AnalysisSnapshotV1`: UUID snapshot id + capture UTC + `source_keys` and runtime generation **at capture** (generation is diagnostic, not durable source identity), per-source fingerprint verification, `request_id`, `request_epoch`, feature `statistics|histogram|line|difference`, exact pair order and profile keys, reference half-open ROI or full-image, native channel/domain/subsample/CFA phase, sample counts per plane, metric definitions/version, values with stable numeric serialization and explicit `finite|pos_inf|neg_inf|nan|unavailable` state, and presentation settings separately. Every `PresentedAnalysis` carries a completion token `(source ids + source generations + request id + ROI + channel + feature configuration + optional difference cache key)`. Capture only if this token still equals current presented result token and all referenced results share the same logical request context. Otherwise snapshot is `unavailable:pending|stale|mismatched|cancelled|uncomputed` and NO implicit Calculate/retry. Do not freeze mutable numpy arrays by dataclass alone: copy only bounded scalar/series values into frozen tuples or read-only defensively copied payload before worker release. Report later operates solely on frozen data and verified source crop handles; a live reanalysis requires explicit user action and creates a new snapshot revision.

For UI exports use `capture_analysis_snapshot(requested_scope) -> CaptureResult`; `serialize_analysis_context(snapshot) -> bytes`; no private path by default. Existing Statistics plain CSV remains untouched (including column order/encoding); W02 adds an additive `Analysis Bundle…` ZIP with `context.json` + existing CSV. This bundle uses the same snapshot/request validation and atomic ZIP writer as W10; W02 may introduce reusable `io/analysis_bundle.py`, W10 must consume rather than fork it.

## 8. Report ZIP and privacy (W10)

Fixed root layout:
```text
manifest.json
report.html
data/review.json
data/context.json
data/measurements.csv
data/measurements.json
assets/finding-<uuid>/source-<index>.png
assets/finding-<uuid>/difference.png      # only when valid explicit captured result
```
No paths with absolute prefix, backslash, `..`, symlink, duplicate names, or external references. `manifest.json`: `kind=pixelscope-report`, `schema_version=1`, app version, UTC time, source/findings counts, numeric definition revision, capture verification states, redaction policy `portable-default`, each entry path/size/SHA-256. Manifest hashes all entries except itself (avoid self-reference). `report.html` static escaped UTF-8 with inline or local stylesheet, CSP `default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'`, no JS, HTTP fetch, embedded local private paths or remote assets. All user note/title/tag values HTML-escaped, no filesystem URL. PNGs are **explicit selected ROI crops**, never unrequested original full-frame or decoded full-resolution attachments; retain channel/footprint/native-vs-preview scale in captions/JSON. For YUV/Bayer export native samples with correct footprint/phase and a separate clearly labeled display PNG; do not silently call preview RGB “native” or resample for numeric comparison. If ROI equals full image, default report must require explicit disclosure/crop permission or omit that source PNG (privacy). CSV is machine-readable capture metrics, not a recomputed or screen-rounded table; JSON preserves nonfinite/unavailable status. Export from frozen snapshot only; if crop sources changed since capture, omit affected crops with visible warning or fail based on explicit strict mode, never attach mismatched bytes.

Streaming ZIP on bounded worker to temporary sibling file; validate entry count, aggregate uncompressed size / compression ratio / PNG max geometry, hash entries and write manifest, close ZIP, fsync and replace atomically. Abort and delete temp on cancel/hash mismatch/I/O failure, never publish incomplete destination. ZIP reopen verification checks manifest hashes and safe paths, strictly not extraction to arbitrary paths. PDF engine excluded. Test final HTML through local offline browser and actual ZIP extraction on Windows before W10 acceptance.

## 9. Unresolved decisions / risk register for independent review

| Risk | Severity | Owner / action |
|---|---|---|
| `zoom_100_percent` clamps smaller-than-viewport images; aspect/resize physical scale could vary | blocker for W01 | W01 geometry oracle, confirm exact Qt coordinate chain and DPIs. |
| Source `document_id` runtime identity / generation changes upon explicit reopen | high | W03/W04/W09 trace call sites; ensure durable UUID mapping and no slot-based relink. |
| Existing folder-display tag uses runtime hooks on MainWindow | high | W03 lifecycle owner audit existing hooks, never add new retained QObject cycle; use typed connection. |
| Session v1 restore transaction lacks Cancel/rollback | high | W09 own separate Review transaction, do not silently modify Session. |
| User-approved Review path hint could be privacy-sensitive | high | independent review of local opt-in and never include in report; design default relative-only. |
| Report captures PNG at changed generation / asynchronously reloaded source | blocker W10 | source fingerprint/generation gate immediately before crop and before publication. |
| Full SHA-256 over SMB/huge RAW can block | medium | bounded worker, cancellation/progress, user-selected scope; never GUI thread. |
| W11 YUV byte-layout prioritization and W12 matching key are unknown | conditional | evidence-backed support/scene matrix and separate contract review before implementation. |
| `physical_scale` per-tile with sync disabled and Difference pane | high | W04 explicit 2/4/6 & A/B/Diff manual tests; no silent collapse to shared range. |
| Parser limits / 0.5px and 0.5% geometry tolerances are design proposals | review required | reviewer ratifies or records alternate numerical oracle; do not hardcode before approval. |

## 10. Completion / evidence gates

W00 design completion only after exact-SHA independent read-only review of this PR, actionable findings resolved with new HEAD re-review, no drift from D01–D04/T01–T08, and executor cards/tests/ownership accepted. `W00 Complete` remains unchecked until that gate. No product-code tests were executed in this documentation task. Required doc checks (`scripts/check_docs.py`, `git diff --check`) are planned for owner/local unless GitHub CI actually reports success. Detailed dependencies/cards/matrix: [W00 execution plan](issue-210-w00-execution-plan.md).


## 11. Independent review corrective contract (PR #211, B1/B2/H1/H2/H3/M1)

This section **supersedes any less restrictive or ambiguous wording above**. Status: revised proposal for *new exact-HEAD independent review*, not accepted or tested. Original review: https://github.com/delphykmc/pixelscope/pull/211#pullrequestreview-5755504410 (reviewed `54935415e7358798c994eb820786dafe24942038`).

### B1 — Explicit source resolution/restore permission matrix

The single source-key resolution outcome is a discriminated `SourceResolutionV1` with `status: verified | candidate_unverified | changed | missing | unsupported_profile`, `candidate_path` optional, `confirmed_by_user: bool`, `verification: digest_match | digest_mismatch | unavailable`, and `reason`. A path confirmation records **only approval to inspect/open a candidate**, never content identity. Review source-key binding is a distinct operation and is permitted **only for verified sources**.

| Outcome | Register in canonical catalog | Present as historical source | Restore saved ROI/view/roles | Attach prior finding to current content | Historical numeric evidence |
|---|---|---|---|---|---|
| Verified (matching stored SHA-256 AND compatible native decode signature; user-confirmed if relocated) | yes | yes | yes, after actual bounds/load validation | yes, marked captured/historical, never current calculation | visible as **captured** with verified-source badge |
| Candidate unverified (digest absent/pending; includes user-approved filename/size/mtime candidate) | no as historical source; optional explicit **separate new source import** | no | no | no | available in read-only finding history, **unbound**, warning `source identity unverified` |
| Changed (digest differs or native signature incompatible) | no as historical source; optional new identity by explicit import | no | no | no | read-only historic values **unbound**; never compare as current without new explicit analysis |
| Missing | no | no | no | no | read-only historic values **unbound** and missing-source warning |
| Unsupported profile / undecodable | no | no | no | no | read-only historic values **unbound** and profile error |

A candidate with a matching digest but an incompatible native interpretation is **not verified**; treat as `unsupported_profile` or `changed`, with a reason. Existing *runtime* same-path documents also require fingerprint validation when restoring historical findings; runtime registration identity is insufficient proof.

**Mixed finding rule:** only the subset of confirmed verified sources may be registered for workspace reconstruction; never rewrite finding source-key lists, pair order or original snapshot. Finding restore is **all-or-nothing** for its exact referenced source set: if any required source is unverified/missing/changed/unsupported, do not activate that finding's saved ROI/view/pair/roles. Render it as read-only history with per-source failure reasons. Additional unaffected findings requiring only verified sources may restore normally. **Reference/Primary missing** blocks that finding's entire activation even when targets remain verified; no silent reassignment to first available target. If no verified selected source exists, abort before workspace commit with zero mutation. If a separate approved new-source import occurs, allocate a new source key/generation, do not attach old measurements or coordinates; require newly captured finding. A Review can still open as an offline **read-only library** without altering Selected, Active or current page.

Test: 1 verified + 1 missing, 1 verified + 1 changed, missing reference, all missing, renamed with digest match and explicit confirmation, digest match but altered decoder/profile, declined relink, confirmed but unverified, two ambiguous candidates, casefold basename collision; assert unchanged historical values/keys, blocked finding activation, no silent new source selected. SHA-256 calculation and native layout interpretation must use the same stable file revision or return unverified.

### B2 — Explicit portable-report projection and leakage policy

Define separate **local** `ReviewDocumentV1` and **portable** `PortableReviewProjectionV1`. The latter is *not* a serialized copy with fields removed afterward. Construct each output from a fixed positive allowlist of typed values. Reject/omit unknown fields, local locator paths, local `extensions`, raw profile sidecar filenames, free-form backend dictionaries, runtime IDs, timestamps from private filesystem path metadata, and unvetted nested data; never pass through original JSON blobs. No local absolute path, drive/UNC prefix, home directory, source relative directory hint, raw profile path, URL, embedded image bytes or source filename path components. The basename is potentially sensitive too: replace it by non-reversible report-local pseudonym `Source 1` ... by default, unless explicit source-name disclosure is separately opted into at report generation.

`data/review.json` allowlist: `kind=pixelscope-portable-review`, `schema_version=1`, report-local pseudonymous `source_id`, ordered roles, finding UUID (not original machine path), user-approved title/note/tags according to text policy, reference ROI and line geometry, numeric/domain/profile **normalized non-path** attributes, snapshot references and `availability` state. `data/context.json` allowlist: only public-safe source IDs, native shapes, channel/subsample/CFA/effective bits, ROI/scope, metric definitions/versions, captured values and verification states. `data/measurements.json` and CSV use the **same DTO projection**; HTML is rendered from it, never from raw local Review or raw dict. Hash manifest lists only safe ZIP entry names and sizes/digests; `manifest.json` cannot contain local paths.

**User-authored title/note/tag privacy:** default export **excludes free-text notes and arbitrary tags**; optional explicit UI review step presents exact text to include, highlights detected path/email/URL-like tokens, and requires user opt-in for inclusion. No automated redaction can guarantee privacy, so unreviewed arbitrary text is never silently exported. HTML escaping applies after this disclosure gate; opt-in does not override prohibition on machine-local path fields. Any pasted paths in opt-in notes are user-disclosed text and must be labeled as such in manifest `user_text_included=true`. To keep a strict `portable-default` guarantee, the default export path strips them. Finding title defaults to a generated `Finding n`, with explicit title inclusion at the same review step.

Implement `project_report(review, snapshots, disclosure: DisclosurePolicy) -> PortableReportV1` as an allowlist builder with no access to native document serialization shortcuts. A ZIP-wide deterministic leak sentinel test scans **all uncompressed entries**, including PNG metadata and EXIF/text chunks, for fixture-specific absolute Windows/POSIX paths, UNC roots, source basename, email, URL, relative folder hints and profile-sidecar path strings; also assert every JSON object key belongs to its allowlist and HTML contains no external fetch. PNG encoder strips metadata. Test with adversarial `extensions` and user text; opt-in test separately verifies disclosure markers and intended text. ZIP-wide scanning does not replace schema allowlist tests.

### H1 — Full transformed-image pixel geometry authority

The composed mapping is explicitly:

`r (reference coordinate) → M_reference_to_native/preview → M_ImageItem_local → M_ImageItem_itemTransform → M_ViewBox_scene → M_QGraphicsView_viewport → M_device(DPR)`.

For reference pixels whose native sample maps to a cell (YUV chroma) or a CFA phase point (Bayer), `M_reference_to_native/preview` is a **spatial-sampling-aware geometry transform**, not an assumption that one chroma sample equals one reference pixel. Define `F(r)` as the composed mapping in physical monitor pixel coordinates. Let `J_F(r)` be its two-column local Jacobian; exact 100% requires each reference basis vector maps to one physical pixel, with orthogonality and orientation preserved (nonuniform rotation/shear fails accuracy). In axis-aligned cases `s_x=||F(r+e_x)-F(r)||`, `s_y=||F(r+e_y)-F(r)||`; report scale only if agreement within approved tolerance. Inspect `ImageItem` transforms, axis inversion, ViewBox content rect, graphics viewport margins, dynamic plot presence, QGraphicsView transform, screen DPR and Qt rounding at **both** item/viewport/device boundaries. Separately confirm screen-level physical pixels with per-monitor capture; model DPR and OS scaling may differ from a screenshot API's sampling.

`measure_physical_zoom()` must use the **displayed image item's composed mapping**, while an independent oracle calculates expected mapped pixel-center distances using a separate scene/device-coordinate route or high-DPI screenshot and a 1px checker/impulse pattern; never verify a function using its own output. Include transformed ImageItem (translation + non-unit scaling, mirrored orientation rejection), asymmetric tile sizes, sync on/off, RGB/Gray, Bayer split/phase, YUV420 native U/V footprint, small image, fractional 1.25/1.5/1.75 DPR, 100/150/200% and physical cross-monitor move/screenChanged. Labels must derive from measured transform and agree with oracle; measure after layout settles, not only toolbar command return. Previous ≤0.5% scale and ≤0.5 physical px center tolerances remain **unratified** and cannot be reported as empirically achieved.

### H2 — Crop content revision and snapshot/asset binding (TOCTOU)

`EvidenceAssetV1` has `asset_id`, `finding_id`, `analysis_snapshot_id`, `source_key`, `source_fingerprint_sha256`, `native_signature_digest`, `request_id`, `roi_ref`, `channel/domain`, `asset_sha256`, `capture_state: verified_same_content | unavailable | changed | unverified`, `reason`, and bounded native/reference dimensions. Asset creation captures a **stable revision** of each source: record stat/file identity before open, compute full SHA-256 on the actual bytes read (stream/decode, bounded worker), record stat/file identity after read; reject if changing during read. A preflight path hash alone is NOT sufficient proof. Before publication, confirm asset payload hash and correspondence to frozen snapshot's stored fingerprint/native profile; if earlier snapshot SHA is pending/missing, do not create a `verified_same_content` association. Recheck source identity/revision just before committing ZIP; if any check fails, omit asset with explicit HTML/JSON `unavailable` reason by default; strict report option fails entire export. Do not silently produce a current crop next to prior metrics. A newly captured crop after an explicit user re-capture may link to a **new** snapshot ID only.

When source is verified by exact SHA but a race permits mutation and replacement back to same metadata, the crop must be computed from the **same verified byte stream/revision** or a securely staged immutable private scratch copy (bounded, explicit disk policy, cleaned on failure); stat comparisons alone are advisory. No full-resolution copy in ZIP. If the platform cannot guarantee bytes used by native decode match those hashed, classify `unverified` and omit the PNG. At report compose, ensure every emitted PNG has one manifest-linked `EvidenceAssetV1` and source/finding/snapshot identities match the metric row; any missing/stale asset is a displayed omission, not a substitute. Mutation-between-preflight-and-open, during-read, after-decode-before-crop, before-publish, and replaced-same-size/mtime tests must reject or omit contradictory crops. Worker cancellation aborts publication.

### H3 — After-commit cancellation, replacement and shutdown

Use explicit restore phases `PREPARING`, `READY_TO_COMMIT`, `COMMITTED_LOADING`, `SETTLING`, `COMPLETED`, `ABORTED_PRECOMMIT`, `INTERRUPTED_POSTCOMMIT`, `CLOSED`. Before canonical registration commit, cancel/new input/failure leaves **all** workspace state untouched. After commit has started there is **no rollback promise**, even when loading is pending. On user cancel after commit (if UI supports it), new user input, or shutdown: atomically revoke restore epoch, cancel its queued/pending worker publications, stop restore-specific forward steps, dismiss owned overlay and leave already committed canonical Registered/Selected/page/Active/Primary as the **current state** (partially loaded sources may remain unloaded/failed). Do not attach saved ROI/Line/view or mark finding activated unless all required sources reach verified terminal status and view-state settle succeeded. If ROI/view/roles were already applied before interruption, remove the **restore-owned pending overlay/action**, but do not silently roll back user state; explicitly mark `interrupted: partial workspace restored` with what was applied and maintain canonical MainWindow invariants. Cancellation never clears unrelated existing source registrations and never forces Difference calculation. New user input takes authority *only after* epoch revocation and is applied using the normal selection pipeline. Late foreground/preview/difference callbacks check `epoch == active_epoch` **and** owner alive and matching source generations before any UI/write; destroyed MainWindow has no callback access. Shutdown schedules no new workers, releases overlay and does not await synchronous network I/O on UI thread.

Acceptance negative tests: cancel before/after commit, new selection after commit but before foreground load, shutdown after partial registration, late gain/analysis/difference result after revocation, two overlapping restore attempts, requested view on failed source, exception after page switch. Assert complete no-mutation precommit, canonical (possibly partial) committed state postcommit, no stale ROI/view/finding binding, no deleted-QObject access.

### M1 — Freeze producer/consumer APIs, state token and file handoff

Public **design** API signatures to implement/ratify before independent coding:

```python
# Qt-free value objects in core/review_analysis.py (W02); source token producer UI/controller.
@dataclass(frozen=True)
class PresentedAnalysisTokenV1:
    feature: str
    request_id: str
    request_epoch: int
    source_documents: tuple[tuple[str, int], ...]  # (runtime document ID, generation)
    source_keys: tuple[str, ...]                    # ordered durable Review source keys
    roi_ref: tuple[int, int, int, int] | None
    channel: str
    domain: str
    profile_signatures: tuple[str, ...]
    difference_cache_key: str | None

def capture_presented_analysis(
    panel: "AnalysisPanelAdapter", expected: PresentedAnalysisTokenV1
) -> "CaptureResult[AnalysisSnapshotV1]": ...
def serialize_analysis_context(snapshot: "AnalysisSnapshotV1") -> bytes: ...
def project_report(
    review: "ReviewDocumentV1",
    snapshots: tuple["AnalysisSnapshotV1", ...],
    disclosure: "DisclosurePolicy",
) -> "PortableReportV1": ...
```

**Production responsibility:** the current analysis-owning controller (`comparison_analysis_panel`, Line panel or DifferencePanel) produces and publishes the token **when a numerical result becomes presented**; W02 defines the Qt-free token DTO and read-only extraction adapter; W07 consumes tokens for pivot presentation **without** modifying them or inventing token identity. MainWindow owns canonical document-id→source-key mapping, generation and current-page authority; W09 owns Review durable identity mapper; W10 consumes frozen snapshots and portable report projection. The token is **ephemeral**; `source_documents` and `request_epoch` are never treated as durable source identity. UI producer must expose an immutable `get_presented_analysis_token() -> PresentedAnalysisTokenV1 | None`; W02 validates equality at capture against the exact result displayed, and rejects stale/cross-request values before serializing.

**File locks / explicit release gates:** (i) W01 exclusively owns `image_viewer.py`/`multi_compare_view.py`; it publishes `measure_physical_zoom`, `set_physical_zoom`, and oracle fixtures + merged SHA before W04 editing them. W04 publishes `capture_review_view_state`/`restore_review_view_state` signature and verified restore lifecycle before W05 changes view-mode wiring. (ii) W02 exclusively owns `comparison_analysis_panel.py` export/token seam until its PR is reviewed/integrated and publishes DTO + read-only `get_presented_analysis_token` protocol; W06 may edit its **layout** only after W02 handoff; W07 edits analysis/pivot only after both W02 and W06 handoffs. (iii) W05 owns `presentation_controls.py` preset semantics first; W06 may edit it for command hierarchy only **after W05 integration**, regardless of W03 being ready. W06's completion and thus W07 must wait for W05 for that file; independent W06 layout-only work may proceed earlier in disjoint modules. (iv) orchestrator alone edits `main_window.py`, `bootstrap.py`, central Session/settings/doc authority; adapter hook merge into them is serial and separately reviewed. A handoff contains exact base/head SHA, exported signatures, unit contract tests, files relinquished, and unresolved conflicts. Agents must not concurrently commit shared paths even in separate worktrees.

No W00 independent approval means none of these signatures is asserted to be already implemented. Freeze applies to **implementation inputs after design review**, not a code API claim.
