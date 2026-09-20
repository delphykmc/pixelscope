# Execution plan: WP-Help-E — Automated Screenshot Lifecycle

Status: **E0 plan proposed / E1–E6 not implemented**
Owner: ChatGPT-assisted implementation; repository owner approval and Windows validation
Branch/PR: `docs/wp-help-e0-screenshot-lifecycle-plan` / E0 planning PR
Baseline: `main@aabc1fe338aed2fea9afd15db1275aff7b549109` (2026-09-21 KST)
Last updated: 2026-09-21

## Goal and acceptance boundary

Make screenshots in the canonical Markdown User Guide reproducible from the **real PixelScope QWidget UI**, detect PR-relevant visual changes against a pinned main baseline, and supply reviewable images/diffs without CI editing the PR or automatically approving documentation. Users must not have to arrange the app interactively to capture a supported scenario.

**This PR contains E0 planning only.** In particular, there is no Windows hosted-runner GUI PoC result, no new manifest implementation, no conditional MkDocs renderer, no screenshot workflow, and no assertion that Issue #81 is fixed. E1 is a technical feasibility gate before committing to an end-to-end hosted capture pipeline.

## Scope and preflight inventory

### Authoritative existing pieces

- `scripts/capture_ui_review.py` already instantiates real `MainWindow`/`RawOpenDialog`, generates deterministic RGB `ImageDocument` arrays, selects documents, changes layout, invokes Difference, displays Histogram/Line Profile, floats the dock, and captures `QWidget.grab()`. Reuse its scene construction; it currently runs **all ten scenes in one process**.
- The ten current output names are `empty_state.png`, `single_image.png`, `three_image_multiview.png`, `five_image_multiview.png`, `six_image_multiview.png`, `difference_analysis.png`, `histogram_docked.png`, `line_profile_docked.png`, `plots_floating.png`, and `raw_profile_dialog.png`. The seven tracked guide image filenames are instead `single-image.png`, `six-image-multiview.png`, `difference-analysis.png`, `histogram-docked.png`, `line-profile-docked.png`, `plots-floating.png`, and `raw-profile-dialog.png`: currently the two filename conventions do **not** agree. Empty/three/five scenes are generated but not tracked as guide images. Do not infer that a preexisting PNG was captured from a known SHA.
- `scripts/generate_test_images.py` supplies deterministic, public-safe file fixtures (RGB, Gray, RAW); `scripts/generate_yuv_manual_fixtures.py` and existing RAW/IQA test helpers are candidates for further reuse. Preserve seeded content and input semantics; use file-backed fixtures where the Files workspace needs real registration.
- `tests/ui/conftest.py` isolates QSettings when requested and drains Qt `DeferredDelete` between pytest-qt tests; targeted Settings/YUV/IQA/workspace tests are examples of real UI setup, **not** a license to run the full native UI suite in screenshot CI.
- `docs/user-guide/assets/screenshots/README.md` inventories seven tracked images and seven gaps: window overview, Files, exact ROI, Statistics, Settings, deployment-neutral IQA, native YUV dialog. User Guide pages currently embed literal relative PNG paths; there is no Screenshot ID manifest or conditional renderer.
- `mkdocs.yml` uses `docs/user-guide`, `use_directory_urls: false`, Material search/offline and a checked-in iframe-worker shim. `.github/workflows/user-guide.yml` runs Windows/Ubuntu documentation checks, network-blocked strict MkDocs and generated-site validation; `scripts/build_user_guide.py`, `scripts/check_user_guide_build_offline.py`, `scripts/check_user_guide_site.py`, `scripts/check_docs.py` and existing unit tests own that contract. Release packaging uses the validated `site/` as executable-relative `help/`, omitting the hosting-only 404. `.github/workflows/user-guide-publication.yml` is manual and verifies main/tag provenance; do not turn it into screenshot CI.
- WP-Help-A/B/C/D are merged as PRs #87/#90/#91/#92. Current `main` is their descendant; E0 preserves their Help, offline, search, publication, and release contracts.

### Captures to support, phased

| Screenshot ID (proposed stable key) | Tracked output / desired page | Existing scene | Priority |
|---|---|---|---|
| `single-image` | `single-image.png` / `features/image-view.md` | `single_image` | E1/E2 |
| `six-image-multiview` | `six-image-multiview.png` / Image View or comparison workflow | `six_image_multiview` | E1/E2 |
| `difference-analysis` | `difference-analysis.png` / `features/difference.md` | `difference_analysis` | E1/E2 |
| `histogram-docked` | `histogram-docked.png` / `features/histogram.md` | `histogram_docked` | E1/E2 |
| `line-profile-docked` | `line-profile-docked.png` / `features/line-profile.md` | `line_profile_docked` | E1/E2 |
| `plots-floating` | `plots-floating.png` / Plots page (when referenced) | `plots_floating` | E1/E2 |
| `raw-profile-dialog` | `raw-profile-dialog.png` / RAW page (when referenced) | `raw_profile_dialog` | E1/E2 |
| `window-overview`, `files-workspace`, `roi-exact`, `statistics-workspace`, `settings-dialog`, `iqa-neutral`, `yuv-profile-dialog` | proposed PNGs / matching topic pages | **Missing**, require UI-specific setup | E2 extensions, not E0 |

Existing `empty_state`, three-image and five-image scenes remain optional registered diagnostics rather than creating unnecessary guide PNGs. E2 must settle whether to register each as a non-guide scene or retire it explicitly; avoid forcing all generated scenes into the User Guide.

## Design invariants

1. **One canonical source:** topic Markdown + single machine-readable manifest + registered scene implementations. Screenshot ID, page associations, output name, feature/dependency mapping and capture settings live in the manifest, **not** a second filename/name list in capture code or Markdown. A scene registry maps scenario keys to functions; validation compares registry keys with manifest scenario keys, including intentionally shared scenarios.
2. **Two image states:** committed, owner-reviewed guide PNGs versus ephemeral proposed PNGs/diffs/reports in CI artifacts. An absent *declared* PNG is valid; an unknown ID, damaged existing PNG or inconsistent mapping is an error. Presence is derived from the filesystem, not manually maintained as mutable manifest state.
3. **Reproducible inputs:** deterministic synthetic data; no private source directories, usernames, production settings, remote IQA/SSO, SMB, provider endpoints, telemetry, or network needed to photograph UI. Do not use image generation to synthesize a screenshot.
4. **No false provenance:** existing seven images start as `legacy-unverified` with no invented capture SHA. Record exact capture source SHA, app version, scenario/environment fingerprint, approved PNG SHA-256 and approval PR/SHA **only after** the corresponding image is captured, checked and promoted.
5. **No lifecycle masking:** Issue #81 remains open; PR #89 remains draft and has no established complete crash fix. Native `0xc0000005`/`0xc0000374` and pyqtgraph/PySide event-loop exceptions are failures, not visual changes. No sleep/GC/global pool workaround, crash suppression or hidden full-suite dependency. The historical capture script's fixed `QTest.qWait` and global-pool `waitForDone` require replacement with bounded condition-driven waits and owner-scoped cleanup after behavior is characterized.
6. **Existing delivery:** strict, offline, locally navigable `file://` Help and manual online publication remain the same. No runtime GUI/MkDocs dependency added for installed users.

## E2 manifest and document reference proposal

Use `docs/user-guide/assets/screenshots/manifest.json` (stdlib JSON; versioned schema) unless E1 discovers a compelling repository convention. Example *design*, not a file created in E0:

```json
{
  "schema_version": 1,
  "capture_profile": "windows-guide-v1",
  "screenshots": [
    {
      "id": "single-image",
      "filename": "single-image.png",
      "pages": ["features/image-view.md"],
      "scenario": "single_image",
      "features": ["image-view", "common-shell"],
      "source_globs": ["src/pixelscope/ui/image_viewer.py"],
      "viewport": {"width": 1680, "height": 980},
      "status": "legacy-unverified",
      "approved": null
    }
  ]
}
```

Exact code owners/globs and real `ImageViewer` file path must be verified in E2; example keys are illustrative. `approved` is either null or a typed object `{capture_commit, application_version, environment_profile, image_sha256, approval_pr, approval_commit}`. `status` describes review/provenance state, **not file presence**. A candidate's status/provenance lives in an artifact-side `capture.json` and never overwrites `approved` in an unreviewed PR. If a human removes an image intentionally, retain its manifest ID and optional Markdown reference; clear/adjust approved provenance in the same reviewed change.

Use a low-dependency MkDocs `on_page_markdown` hook (or equivalently narrow Markdown extension) to replace an explicit, parseable source marker such as `<!-- pixelscope:screenshot single-image -->` with a relative Markdown image when the manifest-named PNG exists, or with nothing if absent. Resolve relative paths from the owning Markdown page; do not emit a broken HTML `img`, a remote reference, a placeholder image, or an alternative guide text corpus. Rendered alt text belongs in a manifest field. The static source checker must scan **all** canonical guide Markdown, not only the MkDocs nav, and reject unknown/duplicate IDs, invalid marker syntax, stale hard-coded guide screenshot references after migration, missing/mislocated/duplicate PNG names, bad paths (including `..`, case mismatch, separators and symlinks outside the asset root), invalid JSON/schema, unregistered scenarios and orphan registered screenshots. Shared screenshot IDs across different pages are permitted; repeated identical ID within one page is permitted only if deliberately specified or otherwise rejected consistently. Retain normal Markdown links for non-screenshot images.

The existing seven images must remain visible throughout migration. Tests should remove one valid PNG in a temporary guide copy and confirm a successful strict/offline build **with only that insertion omitted**; a corrupted existing PNG must still fail. Validate PNG dimensions, decode and SHA metadata where present; do not require a real GUI in Documentation CI.

## E1 automated capture and Windows hosted-runner gate

Refactor the current `review_document`, window setup, scenario methods, and widget grabbing instead of rebuilding UI stand-ins. Expose explicit `--scenario`, `--output` and `--metadata` options; run **one scenario per OS process**, create exactly one QApplication, use a fresh temporary QSettings root and isolated capture output, call real composition, wait on visible/realized UI geometry and the *specific* computation/result/worker state, capture `QWidget.grab()` and verify save + nonempty dimensions. Own and destroy the dialog/window/pools on the GUI thread, drain applicable deferred deletes without forcing cyclic GC, and return a distinct nonzero error for timeout, exception or native process crash. Existing `QSettings().clear()` before isolation is unsafe for owner-local defaults and must not be retained as a generic side effect.

The **first screenshot-CI PR is a PoC**, not an assumption: Windows GitHub-hosted runner, Python 3.10 x64, pinned runtime dependencies, default real Windows Qt platform (not `offscreen` if it hides a QWidget issue), stable 1680×980 client capture, explicit DPI/screen resolution/font/locale/theme/time-zone/input images, and safe transient paths. Prove at least Single View and a dialog from separate processes display actual nonblank PixelScope pixels and visible labels. Inspect the generated PNG artifact and record the host/runtime versions and repeatability across two fresh attempts. Capture scene geometry and screenshot PNG intrinsic dimensions separately; taskbar/window decorations must not leak into the saved widget region. If hosted rendering is not viable, record diagnostic evidence and propose an **owner-approved** self-hosted or owner-local manual-trigger alternative; do not claim full CI or silently fall back to a fabricated image. E1 may require changes to E2–E6 sequencing after this result.

For each attempted capture, persist complete SHA, app version from `pixelscope.version`, Python/Qt/PySide/pyqtgraph versions, OS/runner, capture profile version, DPI/device-pixel ratio, logical/pixel dimensions, fixture identity/hash, scenario ID and exit status. Avoid volatile timestamps/paths inside visible UI and keep timestamps outside pixel comparison.

## E3 impact selection

Collect `git diff --name-status -z --find-renames <pinned PR base SHA> <pinned PR head SHA>` for an explicit same-event main/head pair, including old/new names on rename and deletions. The analysis report records the SHA pair and **every** changed path with reason/selected screenshots. Model named feature/component groups with glob mappings in the manifest and a small globally shared group. `src/pixelscope/app/main_window.py`, `src/pixelscope/app/application.py`, shared window composition, shared fonts/styles/icons/theme/design tokens, selection/viewer/workspace base, Qt runtime dependency or capture fixture/profile changes conservatively select all affected/all screens. UI behavior changes beyond `ui/` (for example input registration/RAW/YUV/controller code) must map to their surface. Screenshot manifest/scene or screenshot Markdown changes select those declared images and enforce contract checking even when no GUI is triggered. A docs-only prose change with no screenshot implication may select none and must report why.

**Conservative fallback:** unknown changes under `src/pixelscope/ui/**`, `src/pixelscope/app/**`, visual assets/styles, runtime UI requirements, or capture helpers select the entire manifest and raise a visible `unmapped-ui-impact` warning for owner classification. A UI-relevant changed file must never be an unreported no-op. Unknown unrelated test-only changes need not force GUI runs. Renames/deletions, shared transitive dependencies, and new files have explicit tests. No network-accessed model is required for impact inference.

## E4 baseline / visual diff and result semantics

Both revisions must be captured on the **same Windows runner/job image, capture profile, and immutable synthetic fixtures**: checkout base SHA to a base worktree, PR HEAD to a separate worktree; install pinned compatible dependencies, do not mix modules/processes, and record each SHA in sidecars. Do not quietly use a moving `main` in one leg. PR base advancement requires a fresh workflow event/explicit rerun. Manifest evolution is reconciled by stable ID: added ID -> `NEW` if head capture succeeds, deleted ID -> `REMOVED/REVIEW`, changed scenario/fixture/profile -> `BASELINE_INCOMPATIBLE/REVIEW` unless reproducible common baseline is established. Never compare unrelated scenarios as if they were visual regressions.

For an eligible ID: capture exit + PNG decode/dimensions + environment fingerprint must all succeed before comparison. Exact decoded-pixel equality means `UNCHANGED`; changed geometry, pixel count, and optional fixed thresholded channel metrics (absolute changed pixels, max/mean error and changed-pixel fraction) mean `CHANGED` with base/head/side-by-side/diff PNGs. A threshold or antialiasing tolerance is **diagnostic only** until calibrated from reproducibility measurements; never silently hide changed labels. `CAPTURE_FAILED_BASE`, `CAPTURE_FAILED_HEAD`, `ENVIRONMENT_MISMATCH`, `INCOMPATIBLE_BASELINE`, and `UNMAPPED_UI_IMPACT` remain separately visible, not reclassified as changed images. Compare PR output also to the reviewed Git PNG/hash to reveal preexisting stale documentation independently of this PR's change.

Workflow permissions `contents: read`, checkout `persist-credentials: false`, no secrets, no remote IQA, and artifact upload only. For untrusted forks, explicitly skip/require owner-authorized safe workflow; never run fork code with write token or `pull_request_target`. Artifacts contain a machine-readable per-image report, readable summary and PNGs, `if: always()` on report/artifact steps, `if-no-files-found: error` for expected artifacts, and short retention (target 14 days, subject to organization policy). Do not commit/push, label PR with unreviewed verdict, upload to public hosting, or trigger the manual documentation publication action.

`CHANGED` itself is **not** a red build. Static contract failures, missing required capture, native crash, invalid PNG, or comparison infrastructure failure are red. Explicit `no affected screenshots` is a valid, visible outcome. A coverage warning without successful conservative fallback is red; with successful fallback it remains a documented review warning.

## E5 separate Documentation CI and Markdown rendering

Keep `.github/workflows/user-guide.yml` independent of Qt GUI realization, screen resolution, native UI crashes, screenshot artifacts, or Screenshot CI availability. Add fast stdlib-backed manifest/marker/registry contract checks and focused temporary-copy render cases (present, absent, invalid ID, duplicate, corrupted PNG, invalid path, orphan scenario) to the existing documentation matrix. Where scene registry imports PySide, extract/inspect its declarative scenario names without importing GUI in docs CI, or put the registry behind a Qt-free declaration checked against dynamically registered names in focused capture tests; never maintain a second manually edited scenario list.

Keep `python scripts/check_docs.py`, `mkdocs build --strict`, `scripts/check_user_guide_build_offline.py`, `scripts/check_user_guide_site.py` and Help-package tests authoritative. Network-blocked builds cannot fetch a missing image. Missing declared PNGs are omitted; present valid PNGs are preserved through `site/`, the installer `help/` tree and optional publication artifact. The generated 404 stays hosting-only. Update workflow path filters for manifest, hook, test and screenshot documentation changes while keeping Screenshot CI independent.

## E6 review, promotion, provenance and release policy

A human examines base/head/diff/candidate plus semantic context, confirms absence of private or misleading content and decides to (a) promote candidate bytes unchanged with the reviewed capture metadata, (b) reject, (c) defer for owner-local recapture, or (d) mark a documented intended visual change that requires no guide update. A dedicated local import/verification command should verify ID, artifact PNG hash, captured source SHA, app version, environment, current image hash (if present), declared page use, no unapproved unrelated changes and explicit review reference before staging a PNG/manifest update. It must not invent SHA for old images, auto-commit, force-push or auto-merge.

Only accepted assets under `docs/user-guide/assets/screenshots/` enter Git and hence the strict offline site/release bundle. Persist approved capture SHA (which may differ from the subsequent docs/merge commit), PNG SHA, app version, scenario/profile version and approval reference. Use Git history for prior versions, do not overwrite old revision metadata or generate new screenshots solely because the app version incremented. For release tags, the release build uses exactly the PNGs and manifest in the approved tag; stale-coverage audit/report is separate from static build success. On later UI changes reselect by mapping; tracked images stay until reviewed replacements arrive. Artifact retention is not durable archiving; Git is the approved image record. No P7 bundle shape, publication authority or actual online URL changes.

## Implementation packages, dependency gates and acceptance tests

| WP | Deliverable / dependencies | Exit criteria and focused test evidence |
|---|---|---|
| **E0** | This plan; baseline inventory; append pointers to follow-up/screenshot strategy; independent review. | E1 feasibility question, manifest/CI boundaries, risk and each WP criterion documented. Docs only; no GUI PASS claimed. |
| **E1** | Refactor existing capture helper; deterministic process-isolated single-scenario command; hosted Windows PoC. | Verified *real* Single View + dialog PNG artifacts across fresh runs; proper nonzero failure paths; settings unchanged; metadata/Qt cleanup; owner/CI PoC observations recorded. If blocked, revise downstream plan before E2. |
| **E2** | Manifest schema/validator, single scenario registry, seven legacy mappings and missing-page ID inventory; progressively add seven absent scenes. Depends E1 contract. | Unknown/duplicate IDs, names, owners, invalid paths, missing registry keys and bad PNG rejected. Legacy provenance honestly `legacy-unverified`. Each added scenario captures reproducibly in isolation; do not block E2 schema on all optional scenes. |
| **E3** | Diff/rename-aware feature mapping selector + reason report. Depends E2. | Fixtures for single-feature, global-shell, style, RAW/YUV, docs-only, unmapped UI, new/deleted/renamed path and scene-only change; no relevant change silently omitted. |
| **E4** | Pinned-base/head capture, decoded visual diff, artifact report and permissions-limited PR workflow. Depends E1–E3. | Equal/change/new/removed/failed/incompatible scenarios tested; changed PNG alone does not fail; native capture failure does; artifact has SHA/provenance; baseline and head captured in same runner profile; no CI commit. |
| **E5** | Markdown ID hook and independent docs validation / missing-image behavior. Depends E2; may run in parallel with E3/E4 after schema settles. | Present/absent/bad-ID/damaged-image cases; strict network-blocked build on Windows/Ubuntu; generated HTML `file://` assets and P7 Help validator unaffected. |
| **E6** | Owner-reviewed promotion helper, provenance/staleness audit, operating instructions and release checks. Depends E4/E5. | Promoted PNG hashes/SHAs verified, missing or stale capture explicitly reported, no silent update, human approval/rollback/release-tag tests and owner Windows packaged Help smoke. |

**Cross-cutting checks per implementation PR:** relevant focused unit/UI tests; `ruff check .`, `ruff format --check .`, `mypy src` if production code changes, `scripts/check_docs.py`, `git diff --check`, the existing strict/offline docs build and site validation. Record exact environment/commit per observed test. Issue #81 demands repeated isolated Windows GUI PoC/scene loops with normal GC and no native crash; a green docs job is not evidence of GUI or installer stability. Owner-local Windows full suite and packaged installer/portable/browser smoke are separate explicit gates when appropriate, not retrospectively claimed from hosted runs.

## Risks and mitigations

| Risk | Detection | Mitigation / owner decision |
|---|---|---|
| Windows runner has no reliable GUI/consistent DPI | E1 actual PNG inspection, rerun pixels, logs | Stop hosted E4 assumption; owner-approved alternate runner/local trigger and revise plan |
| Issue #81 native crash or callback exception | per-process exit, stderr, event-loop exception capture, repeated run | isolate scenarios; report capture failure; leave #81 investigation separate, no GC/sleep masking |
| Current screenshot differs from current code for historical reasons | tracked PNG vs pinned-main capture + unknown old metadata | separate `legacy/stale` report; no fabricated attribution or auto-replacement |
| Scene name/page mapping drift | static manifest/Markdown/registry contract | fail before guide publication; one manifest drives names and paths |
| Filesystem/host/locale noise changes pixels | pinned runner/profile, locale, fixture hashes, event-driven geometry waits | baseline/head same environment; diagnostic repeatability and explicit incompatible status |
| CI executes malicious PR code | least-privilege same-repo PR policy, no tokens/secrets after checkout | skip untrusted fork until approved isolated workflow; no `pull_request_target` head execution |
| Large artifact sizes / runtime | changed-only candidate + bounded report, selective scene execution | global fallbacks remain correct; measure before optimization |
| Release silently ships missing screenshot | intentional marker omission + strict checks of all *existing* resources | expected absence is allowed; unknown/malformed references fail; release audit tracks desired coverage |

## Decisions requiring E1/E2 evidence

- Hosted Windows GUI viability, exact capture resolution/DPI/font availability, and reproducibility tolerance.
- Authoritative source-file glob ownership after complete UI module inventory; the example manifest is not a verified comprehensive mapping.
- Whether the three existing non-guide diagnostic scenes remain registry-only or receive manifest entries with no page associations.
- How to represent non-automatable deployment-neutral IQA/YUV states without connecting a corporate service or inventing a UI.
- Whether any high-churn style/theme behavior requires a profile-major baseline reset; profile changes are never silently treated as ordinary visual diff.

## Progress log

- **2026-09-21 E0:** Inspected merged main, #81/#89 status, capture/test scripts, seven checked-in screenshot assets, User Guide pages, documentation CI/MkDocs, deployment/release boundaries. Identified ten script outputs versus seven differently named committed PNGs, seven stated coverage gaps, and the current script's process-wide fixed waits/Settings clearing. Documented the E1 proof gate and E2–E6 proposal; **no implementation or local/hosted GUI validation performed**.

## Completion summary (E0 only)

- Delivered behavior: plan and references; no runtime behavior change.
- Validation results: GitHub source review only; no test command or Windows-hosted PoC executed in E0.
- Remaining limitations: exact capture UI reliability, per-feature mapping and new scenarios are implementation work.
- Durable docs: this file, `docs/USER_GUIDE_FOLLOW_UP.md`, screenshot strategy README.
