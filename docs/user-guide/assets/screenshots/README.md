# Screenshot Strategy

This directory contains only screenshots captured from the real PixelScope application and already present in the repository. Do not create mock UI screenshots to fill missing coverage.

## Approved captures

- `single-image.png` — main Image View / single-image state.
- `six-image-multiview.png` — six-slot Multi View.
- `histogram-docked.png` — Histogram workspace.
- `line-profile-docked.png` — Line Profile workspace.
- `difference-analysis.png` — Difference analysis.
- `plots-floating.png` — floating Plots workspace.
- `raw-profile-dialog.png` — RAW profile dialog.

## E6 coverage captures

The following were added from owner-reviewed, release-representative real-application captures in E6:

- Main window overview with workspace labels visible.
- Files workspace focused on registration/selection.
- ROI creation and exact X/Y/Width/Height entry.
- Statistics workspace.
- Settings dialog.
- IQA workspace in a deployment-neutral state.
- Native YUV interpretation dialog if the current UI can be shown without deployment-specific data.

The manifest records the capture source SHA, application version, scenario/profile identity, PNG SHA-256 and approval reference for every image. Future replacements require the same review and must avoid private paths, company-internal data, credentials, hostnames, or user-identifying content.

## Screenshot ID examples (conditional)

The topic-page insertions use exact manifest markers instead of hard-coded image
links. This strategy README records their stable IDs without embedding an image that
becomes a broken Markdown link when the corresponding PNG is intentionally absent:

- `single-image` — Image View.
- `six-image-multiview` — Quick start.
- `histogram-docked` — Histogram.
- `line-profile-docked` — Line Profile.
- `difference-analysis` — Difference.
- `raw-profile-dialog` — RAW.
- `plots-floating` — Plots workspace.

The canonical, searchable topic Markdown owns the actual placement. The MkDocs E5 hook expands a valid `pixelscope:screenshot` HTML-comment marker
with its literal manifest ID to a local image only when the manifest-declared
file exists, and otherwise emits nothing. The hook does not
generate, replace or approve any PNG.

## Automated lifecycle: E0–E5 merged / E6 reviewed promotion

The [WP-Help-E execution plan](../../../exec-plans/active/wp-help-e-automated-screenshot-lifecycle.md)
documents the manifest, real-QWidget scene registry, Windows hosted capture
feasibility gate, main/PR visual comparisons, conditional Markdown insertion, and
human-reviewed promotion. The fourteen original E6 PNGs were captured from the real application and have exact provenance in the manifest. The v0.2.1 refresh adds six registered real-UI scenes; all twenty refreshed PNGs now have owner approval recorded below. The legacy `scripts/capture_ui_review.py` remains historical input ownership; isolated capture uses manifest scenarios and guide filenames.

E1 proved hosted Windows capture for real Single View and RAW Dialog in separate processes (PR #94). E2 introduced the versioned [Screenshot Manifest](manifest.json), capture ownership and three non-guide diagnostic outputs. E3 provides conservative screenshot impact selection, E4 provides pinned native Windows candidate comparison, and E5 converts topic embeds to conditional ID markers. E6 adds isolated coverage for all fourteen guide scenes and records the owner-reviewed promotions. A PR-produced
candidate is never an approved User Guide image until its content and provenance have
been checked and the PNG plus manifest changes have been committed through review.

## Manifest schema: provenance versus future targets

`target_capture_profile` names the **intended** Windows rendering profile for newly captured candidates. It is not the capture environment, app version, original SHA, or a comparable E4 baseline for any existing `legacy-unverified` PNG, nor proof that a planned scenario exists. E4 must compare actual per-capture rendering fingerprints and scenario contracts for both pinned base and head; E6 must separately approve candidate bytes and their observed capture source.

`capture_mode: planned` has no registered real-UI builder. After a real isolated builder is implemented and validated, a *new* scene can transition to `capture_mode: isolated`, `placement: required`, and `status: capture-ready` **without `legacy_output`**. That status reserves an insertion marker but does not authorize committing an unapproved PNG. `legacy_output` is required only for genuinely historical/manual assets and must match the exact old script scene output. Existing guide PNGs retain `legacy-unverified` unless approved through E6. The three diagnostics are disjoint from guide-owned manual output names.

The E2 PNG validator intentionally accepts only verified non-interlaced 8-bit RGB/RGBA encodings, checking CRC, bounded IDAT decompression, scanline length and filters. Indexed/Adam7/other formats are rejected **even if otherwise legal PNG** until supported by an explicit decoder contract and regression tests. This is a conservative documentation-image format gate, not a general-purpose PNG decoder.

## Core v0.2.1 Windows refresh

From the clean candidate branch, install the pinned runtime and documentation dependencies. Run `python scripts/refresh_user_guide_screenshots.py capture --packet-dir build/guide-captures-v021`. Each manifest scene is captured in two fresh native processes; the local packet contains a before/after `review.html`, exact `approval.md` hashes, and a real generated Memo report. A rerun resumes valid captures at the same source SHA. Review each original-size candidate and its privacy before posting the approval hash list in the PR.

After explicit owner approval, run `python scripts/refresh_user_guide_screenshots.py promote --packet-dir build/guide-captures-v021 --approval-ref <owner-PR-comment-URL>` (replace the placeholder). The script verifies the packet, copies exact approved bytes, updates the manifest and coverage decisions, and validates the results before returning. The approval reference is supplied by the owner, not independently fetched by the script. Commit only the approved PNGs, manifest, coverage decisions and updated guide/release text. Do not commit the capture packet or local logs. Memo HTML is available for visual review, not a registered browser screenshot.

## E6 owner-reviewed refresh

The v0.2.1 owner-approved refresh replaces the fourteen earlier PNGs and adds six
new scenes, for twenty current images. Exact hashes, capture source and the
owner's chat approval are retained in the
[v0.2.1 approval record](../../../exec-plans/active/v0.2.1-screenshot-approval.md).
This promotion used that explicit chat approval and verified packet directly;
the CLI's PR-comment-only approval input was not used and no GitHub approval
comment was fabricated. The original E6 history below remains historical.

On 2026-09-25 the owner reviewed the complete temporary guide and approved all fourteen refreshed screenshots. They were captured from source `631779bb91278e846f39e376dd1bef8210df1e5c` in two independent processes per scene with identical pixels and public-safe fixtures. The approval reference and per-image hashes are stored in the manifest; future staleness is selected by E3 ownership mapping rather than inferred from file age.
