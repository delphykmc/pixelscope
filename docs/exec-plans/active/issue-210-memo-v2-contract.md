# Memo v2 — Multi-ROI Annotation & Offline Evidence (2026-11-06)

**Priority:** critical independent product work. **Stacked base:** W09b PR #222, not the W05/W06 retirement PR. W09b v1 is NOT sufficient for the requested Memo workflow. This draft initially supplies the Qt-free self-contained archive exporter and tests; **no new GUI is claimed complete**.

## User job and target interaction

Repeatedly mark different regions within an image or a comparison page, attach an individual title/note, retain a numbered visual ROI overlay and list, inspect or edit/delete any one region, save all text **and cropped pixel evidence together**, restart and reopen with or without the original files, then output a static HTML report for colleagues without PixelScope.

- Existing Ctrl+drag sets *working* shared reference ROI; it must never overwrite previous recorded ROIs.
- **Add ROI** freezes region ID, reference-space x/y/w/h, selected source identities, W04 center/physical zoom/sync and **one full-resolution RGB8 display-preview PNG crop per image on the current page**. No overlays or modified original bytes. Preserve native dtype/profile only as provenance, never treat preview RGB8 as a native IQA measurement.
- A numbered list with thumbnails shows stored regions (for example 01 Color bleeding, 02 Texture loss, 03 Halo). Selecting a row or its viewer overlay navigates to its ROI and viewport via the *existing W09b source verification/restore*; if originals are unavailable, continue to show the historical note and archived crop with an explicit **Historical screenshot** badge.
- **Update Note** edits only text. **Replace ROI** must be an explicit separate action if implemented. **Delete ROI** deletes only that record/crop from the next saved bundle (offer Undo or confirmation). Never delete source files.
- **Save Memo…** creates an immutable-capable private local `.pxmemo` ZIP archive including manifest, individual PNGs and static `index.html`. A selected source's original path can be kept in optional `sources.local.json` for verified reopen, but this archive must be described as **private**; it is not a sanitized report.
- **Open Memo…** reads `.pxmemo`; when opening older `.pxreview` v1, retain legacy notes and require the original source before any new crop is manufactured. Never pretend a missing crop was archived; show a clear upgrade status.
- **Export HTML…** writes `index.html` and relative `images/*.png`. Export ONLY the safe HTML and stored crop bytes: never private paths, source SHA, native profile, QSettings or executable scripts. Works with originals removed and without PixelScope.
- No implicit Difference Calculate, stale Statistics/IQA results, new selection authority, or changes to Session v1.

## Precise dock ownership and screen layout

Use the **existing QMainWindow Dock** system; the Base Memo must not import Enterprise/Reference IQA components.

At 1400×880 logical pixels, Memo and IQA share the **right dock area as tabs**, not vertically split by default; otherwise both scrollable IQA diagnostics and a multi-ROI editor lose usable height. Opening Memo does not activate another workspace preset and does not resize image content except Qt's native dock allocation. Do not add a placeholder IQA dock when IQA is absent.

Provide a neutral `DockPlacementHint(role="memo", tab_peer="iqa")` at contributed dock registration. When both docks exist and **no user-restored dock state** overrides placement, call `QMainWindow.tabifyDockWidget(iqaDock, memoDock)`. The contributing plugin registers its own role rather than Base searching for private IQA classes. Late IQA activation must use the same docking coordinator; a visible Memo remains an available tab. Do not automatically tabify after the user has manually floated/stacked a dock. Do not trigger geometry changes simply by activating a Memo entry.

At large displays, users may split IQA above Memo using ordinary Qt dock dragging; persist native topology. Do not introduce another Compare/Analyze/Review preset or special toolbar button. Memo editor contains list/thumbnail view, Title/Note, Add ROI, Update Note, Delete ROI and the file/export actions; use a scrollable body and minimum usable width around 320 logical pixels.

## Artifact contract (this draft's implemented core slice)

- `manifest.json`: `pixelscope-memo-bundle` version 1, positive-listed records: region ID/title/note, half-open reference ROI, optional W04 view center/physical zoom, per-source crop label/asset/SHA256.
- `images/<opaque-hash>.png`: only capture-time canonical 8-bit preview crops. PNG width/height must equal ROI reference width/height. No overlays.
- `sources.local.json`: optional private path hints, omitted when exporting HTML. All live source binding still requires W09a verification and native interpretation matching.
- `index.html`: generated offline, no JavaScript, escaped user strings, relative assets, restrictive CSP.
- create-only atomic same-directory publication, overwrite rejection and full validation before memory-bound archive output. Limit 1000 region notes, 6 crops per note, 64MiB per crop, 512MiB total uncompressed, deny arbitrary ZIP paths/duplicates.
- Keep existing W09b `.pxreview` schema/repository intact. `.pxmemo` becomes the user-facing portable local bundle only after UI/adapter integration. An existing v1 review is not silently converted or overwritten.

## Implementation slices and acceptance

**M1 (current draft):** pure `io/memo_bundle.py`, offline archive/HTML exporter and negative tests; no Qt integration and no UI screenshots yet.

**M2:** W09b coordinator adapter captures PNG crop for EACH saved ROI, bounded TaskWorker and immutable source/ROI epoch fence. Source-key mapping, W04 snapshot, schema migration and optimistic save revisions; integrate `.pxmemo` Save/Open. Never perform cv2 encode/write on UI thread.

**M3:** Memo list with thumbnails, numbered overlays on one or many ImageViewers, selection/restore, Delete ROI and explicit Replace ROI, dirty/unsaved prompts, Undo or delete confirmation, capture failure states. UI signals must not store strong QObject cycles or race active sources.

**M4:** plugin-neutral IQA/Memo right-dock tabification through contributed dock metadata, respecting saved native layout and late plugin registration. Test IQA absent/present, startup/restart, hidden/floating/manual split and high-DPI, and do not import private IQA in Base.

**M5:** real Windows 1400×880/1920×1080 screenshots: (a) at least 3 ROIs on one image, (b) Memo/IQA tabs, (c) reopened offline crop and HTML with original removed. Native 2/4/6 source, Bayer/YUV, zoom/sync, folder/page, invalid/out-of-bounds ROI and normal-GC full suite plus independent exact-HEAD review.

### Release gate

All M1–M5 including actual Qt integration and full Windows normal-GC acceptance must pass before describing Memo as complete. Existing W09b #222 is a separate underlying requirement, not an excuse to mark this PR merged. W05/W06 retirement PR must be rebased and merged in a controlled sequence before the finished Memo integration.

Co-authored-by: ChatGPT <noreply@openai.com>
