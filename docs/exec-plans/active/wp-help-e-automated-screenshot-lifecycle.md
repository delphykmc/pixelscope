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
4. **No false provenance:** existing seven images start as `legacy-unverified` with no invented capture SHA. Record exact capture source SHA, app version, scenario/environment fingerprint, approved PNG SHA-256 and an externally known PR/review approval reference **only after** the corresponding image is captured, checked and promoted. Derive the final image-introducing Git commit from repository history; do not embed its SHA in that same commit.
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
      "placement": "required",
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

Exact code owners/globs and real `ImageViewer` file path must be verified in E2; example keys are illustrative. `approved` is either null or a typed object `{capture_source_sha, application_version, comparison_profile_id, scenario_contract_id, image_sha256, approval_ref}`. `approval_ref` is an externally known PR/review reference, not the still-unknown merge/introducing commit SHA. `status` describes review/provenance state, **not file presence**. A candidate's status/provenance lives in an artifact-side `capture.json` and never overwrites `approved` in an unreviewed PR. If a human removes an image intentionally, retain its ID/optional marker, document the deletion, and report current presence as MISSING; any last-approved provenance describes historical bytes only, not current file existence. The existing PNG's SHA must match approved metadata when it is present.

Use a low-dependency MkDocs `on_page_markdown` hook (or equivalently narrow Markdown extension) to replace an explicit, parseable source marker such as `<!-- pixelscope:screenshot single-image -->` with a relative Markdown image when the manifest-named PNG exists, or with nothing if absent. Resolve relative paths from the owning Markdown page; do not emit a broken HTML `img`, a remote reference, a placeholder image, or an alternative guide text corpus. Rendered alt text belongs in a manifest field. The static source checker must scan **all** canonical guide Markdown, not only the MkDocs nav, and reject unknown/duplicate IDs, invalid marker syntax, stale hard-coded guide screenshot references after migration, missing/mislocated/duplicate PNG names, bad paths (including `..`, case mismatch, separators and symlinks outside the asset root), invalid JSON/schema, unregistered scenarios and orphan registered screenshots. Shared screenshot IDs across different pages are permitted; repeated identical ID within one page is permitted only if deliberately specified or otherwise rejected consistently. Retain normal Markdown links for non-screenshot images.

The existing seven images must remain visible throughout migration. E5 must remove the six hard-coded image embeds from the screenshot README and migrate topic image embeds to ID markers. Tests must remove **each** declared PNG in a temporary **full-repository** copy: `scripts/check_docs.py` and strict/offline MkDocs must both pass with only the relevant insertion omitted; a corrupt existing PNG, unknown ID, undeclared missing PNG or unrelated broken local link must fail. Narrowly delegate recognized markers to the manifest checker; never broadly disable Markdown link validation. Validate PNG dimensions, decode and SHA metadata where present; do not require a real GUI in Documentation CI.

### Bidirectional manifest/page ownership

For every Screenshot ID with `placement: required`, each declared `pages` entry must exist and contain exactly one matching marker, and every encountered marker must name an ID declaring that source page. Multiple explicitly declared pages may share an ID; duplicates on one page, page rename/removal drift, orphan approved PNGs, undeclared filenames and an approved PNG in `placement: planned` state fail validation. `placement: planned` reserves an ID for a future page and must have no approved/committed guide asset. Diagnostics-only capture scenarios are explicitly non-guide registry entries, not unreferenced approved screenshots. Missing *declared* PNGs are valid regardless of historical last-approved metadata, but are reported as MISSING in the coverage audit. Validate the actual marker↔page graph rather than trusting only the manifest list.

## E1 automated capture and Windows hosted-runner gate

Refactor the current `review_document`, window setup, scenario methods, and widget grabbing instead of rebuilding UI stand-ins. Expose explicit `--scenario`, `--output` and `--metadata` options; run **one scenario per OS process**, create exactly one QApplication, use a fresh temporary QSettings root and isolated capture output, call real composition, wait on visible/realized UI geometry and the *specific* computation/result/worker state, capture `QWidget.grab()` and verify save + nonempty dimensions. Own and destroy the dialog/window/pools on the GUI thread, drain applicable deferred deletes without forcing cyclic GC, and return a distinct nonzero error for timeout, exception or native process crash. Existing `QSettings().clear()` before isolation is unsafe for owner-local defaults and must not be retained as a generic side effect.

The **first screenshot-CI PR is a PoC**, not an assumption: Windows GitHub-hosted runner, Python 3.10 x64, pinned runtime dependencies, default real Windows Qt platform (not `offscreen` if it hides a QWidget issue), stable 1680×980 client capture, explicit DPI/screen resolution/font/locale/theme/time-zone/input images, and safe transient paths. Prove at least Single View and a dialog from separate processes display actual nonblank PixelScope pixels and visible labels. Inspect the generated PNG artifact and record the host/runtime versions and repeatability across two fresh attempts. Capture scene geometry and screenshot PNG intrinsic dimensions separately; taskbar/window decorations must not leak into the saved widget region. If hosted rendering is not viable, record diagnostic evidence and propose an **owner-approved** self-hosted or owner-local manual-trigger alternative; do not claim full CI or silently fall back to a fabricated image. E1 may require changes to E2–E6 sequencing after this result.

For each attempted capture, persist complete SHA, app version from `pixelscope.version`, Python/Qt/PySide/pyqtgraph versions, OS/runner, capture profile version, DPI/device-pixel ratio, logical/pixel dimensions, fixture identity/hash, scenario ID and exit status. Avoid volatile timestamps/paths inside visible UI and keep timestamps outside pixel comparison.

### Capture metadata versus comparability fingerprint

Each capture records **provenance** (source HEAD SHA, app version, scenario implementation source commit, output/temp path, timestamp and runner identity) separately from its **rendering-comparability fingerprint**. The fingerprint contains actual pixel-relevant inputs: capture profile/schema, scenario behavior contract/revision, fixture content SHA(s), effective Python/Qt/PySide/pyqtgraph versions when rendering-relevant, DPI/DPR, font identities, locale, palette/theme, effective settings and logical/output pixel dimensions. Source SHA, application version, implementation commit ID, output path, timestamp and incidental runner identifiers must **never** participate in base/head fingerprint equality: they normally differ by design. An app-version-only change can still change *pixels* if the version is visible; that is an ordinary CHANGED result. A true DPI/font/rendering profile mismatch is ENVIRONMENT_MISMATCH; changed scenario semantics or fixture bytes without a common defensible baseline are INCOMPATIBLE_BASELINE, not UI regressions. Tests: ordinary code-only PR, version-only bump (including visible version label), DPI/profile mismatch, scenario revision and fixture revision. If base/head require different pinned Qt versions, report non-comparability instead of silently forcing an unsupported runtime.

## E3 impact selection

Collect `git diff --name-status -z --find-renames <pinned PR base SHA> <pinned PR head SHA>` for an explicit same-event main/head pair, including old/new names on rename and deletions. The analysis report records the SHA pair and **every** changed path with reason/selected screenshots. Model named feature/component groups with glob mappings in the manifest and a small globally shared group. `src/pixelscope/app/main_window.py`, `src/pixelscope/app/application.py`, shared window composition, shared fonts/styles/icons/theme/design tokens, selection/viewer/workspace base, Qt runtime dependency or capture fixture/profile changes conservatively select all affected/all screens. UI behavior changes beyond `ui/` (for example input registration/RAW/YUV/controller code) must map to their surface. Screenshot manifest/scene or screenshot Markdown changes select those declared images and enforce contract checking even when no GUI is triggered. A docs-only prose change with no screenshot implication may select none and must report why.

**Conservative fallback:** unknown changes under `src/pixelscope/ui/**`, `src/pixelscope/app/**`, visual assets/styles, runtime UI requirements, or capture helpers select the entire manifest and raise a visible `unmapped-ui-impact` warning for owner classification. A UI-relevant changed file must never be an unreported no-op. Unmapped rendering-relevant changes under `src/pixelscope/core/**` and `src/pixelscope/io/**` (pixel values, decoding, RAW/YUV interpretation, image metadata, document semantics) must also enter mapped feature ownership or conservative full-capture fallback, not be dismissed by directory alone. Unknown unrelated test-only changes need not force GUI runs. Renames/deletions, shared transitive dependencies, and new files have explicit tests. Treat changes to **committed screenshot PNGs** as first-class inputs: added, modified, deleted and renamed PNGs (including `legacy-unverified`) require an explicit contract/impact report, matching approved/proposed state and review, not a silent docs-only skip. No network-accessed model is required for impact inference.

## E4 baseline / visual diff and result semantics

Both revisions must be captured on the **same Windows runner/job image, capture profile, and immutable synthetic fixtures**: checkout base SHA to a base worktree, PR HEAD to a separate worktree; install pinned compatible dependencies, do not mix modules/processes, and record each SHA in sidecars. Do not quietly use a moving `main` in one leg. PR base advancement requires a fresh workflow event/explicit rerun. Manifest evolution is reconciled by stable ID: added ID -> `NEW` if head capture succeeds, deleted ID -> `REMOVED/REVIEW`, changed scenario/fixture/profile -> `BASELINE_INCOMPATIBLE/REVIEW` unless reproducible common baseline is established. Never compare unrelated scenarios as if they were visual regressions.

For an eligible ID: capture exit + PNG decode/dimensions + **rendering-comparability fingerprint (defined below)** must all succeed before comparison. Exact decoded-pixel equality means `UNCHANGED`; changed geometry, pixel count, and optional fixed thresholded channel metrics (absolute changed pixels, max/mean error and changed-pixel fraction) mean `CHANGED` with base/head/side-by-side/diff PNGs. A threshold or antialiasing tolerance is **diagnostic only** until calibrated from reproducibility measurements; never silently hide changed labels. `CAPTURE_FAILED_BASE`, `CAPTURE_FAILED_HEAD`, `ENVIRONMENT_MISMATCH`, `INCOMPATIBLE_BASELINE`, and `UNMAPPED_UI_IMPACT` remain separately visible, not reclassified as changed images. Compare PR output also to the reviewed Git PNG/hash to reveal preexisting stale documentation independently of this PR's change.

Workflow permissions `contents: read`, checkout `persist-credentials: false`, no secrets, no remote IQA, and artifact upload only. For untrusted forks, explicitly skip/require owner-authorized safe workflow; never run fork code with write token or `pull_request_target`. Artifacts contain a machine-readable per-image report, readable summary and PNGs, `if: always()` on report/artifact steps, `if-no-files-found: error` for expected artifacts, and short retention (target 14 days, subject to organization policy). Do not commit/push, label PR with unreviewed verdict, upload to public hosting, or trigger the manual documentation publication action.

`CHANGED` itself is **not** a red build. Static contract failures, missing required capture, native crash, invalid PNG, or comparison infrastructure failure are red. Explicit `no affected screenshots` is a valid, visible outcome. A coverage warning without successful conservative fallback is red; with successful fallback it remains a documented review warning.

## E5 separate Documentation CI and Markdown rendering

Keep `.github/workflows/user-guide.yml` independent of Qt GUI realization, screen resolution, native UI crashes, screenshot artifacts, or Screenshot CI availability. Add fast stdlib-backed manifest/marker/registry contract checks and focused **full-repository-copy** render cases (present, absent including last-approved provenance, invalid ID, duplicate marker/ID, corrupted PNG, invalid path, page rename/removal, orphan scenario/approved asset) to the existing documentation matrix. Where scene registry imports PySide, extract/inspect its declarative scenario names without importing GUI in docs CI, or put the registry behind a Qt-free declaration checked against dynamically registered names in focused capture tests; never maintain a second manually edited scenario list.

Keep `python scripts/check_docs.py`, `mkdocs build --strict`, `scripts/check_user_guide_build_offline.py`, `scripts/check_user_guide_site.py` and Help-package tests authoritative. Network-blocked builds cannot fetch a missing image. Missing declared PNGs are omitted without triggering broken links anywhere in the full-repository docs checks (including the migrated screenshot README); unrelated Markdown links and undeclared image paths remain strictly required. Present valid PNGs are preserved through `site/`, the installer `help/` tree and optional publication artifact. The generated 404 stays hosting-only. Update workflow path filters for manifest, hook, test and screenshot documentation changes while keeping Screenshot CI independent.

### Non-self-referential provenance and post-merge identity

The manifest stores `capture_source_sha`, PNG SHA-256, application version, comparable profile/scenario contract and an **already-existing external approval PR/review reference** bound to those exact image bytes and source identity. A candidate artifact is not approved just because it has an approval URL: the owner must explicitly review the candidate hash and source, then promote it in a reviewed PNG/manifest PR. If the PR number is unknown at first staging, add its reference only after it exists and ensure the final review covers the resulting exact PNG hash/source; a changed image or source requires renewed approval. Never store `approval_commit`, a guessed merge SHA or a placeholder self-commit SHA inside the very commit whose hash depends on the manifest. Derive the introducing/changing commit and relevant blob history from the **merged ref** after integration; Git merge/squash/rebase can alter the introducing SHA while preserving reviewed content identity. Validate merged history with PNG blob hashes, not Git-SHA equality with a pre-merge prediction. Tests cover normal merge, squash, rebase/reword, exact-image preservation and changed-image approval invalidation.

### Seven-gap completion gate

The initial seven gaps (overview, Files, exact ROI, Statistics, Settings, neutral IQA, native YUV) remain a tracked coverage inventory. E2 may complete the schema with some scenes still pending, but **WP-Help-E cannot be declared fully complete** until E6 records for **each** gap either a verified real-UI capture with test evidence or an explicit deferred decision stating technical reason, owner approval and future follow-up. A generic assertion that optional scenes are out of scope is not sufficient.

## E6 review, promotion, provenance and release policy

A human examines base/head/diff/candidate plus semantic context, confirms absence of private or misleading content and decides to (a) promote candidate bytes unchanged with the reviewed capture metadata, (b) reject, (c) defer for owner-local recapture, or (d) mark a documented intended visual change that requires no guide update. A dedicated local import/verification command should verify ID, artifact PNG hash, captured source SHA, app version, environment, current image hash (if present), declared page use, no unapproved unrelated changes and explicit review reference before staging a PNG/manifest update. It must not invent SHA for old images, auto-commit, force-push or auto-merge.

Only accepted assets under `docs/user-guide/assets/screenshots/` enter Git and hence the strict offline site/release bundle. Persist approved **capture source SHA** (which may differ from the subsequent docs/merge commit), PNG SHA, app version, scenario/profile version and a known **external** approval reference. Derive the final introducing commit from Git history; do not attempt to embed a SHA of the commit currently being created. Use Git history for prior versions, do not overwrite old revision metadata or generate new screenshots solely because the app version incremented. For release tags, the release build uses exactly the PNGs and manifest in the approved tag; stale-coverage audit/report is separate from static build success. On later UI changes reselect by mapping; tracked images stay until reviewed replacements arrive. Artifact retention is not durable archiving; Git is the approved image record. No P7 bundle shape, publication authority or actual online URL changes.

## Implementation packages, dependency gates and acceptance tests

| WP | Deliverable / dependencies | Exit criteria and focused test evidence |
|---|---|---|
| **E0** | This plan; baseline inventory; append pointers to follow-up/screenshot strategy; independent review. | E1 feasibility question, manifest/CI boundaries, risk and each WP criterion documented. Docs only; no GUI PASS claimed. |
| **E1** | Refactor existing capture helper; deterministic process-isolated single-scenario command; hosted Windows PoC. | Verified *real* Single View + dialog PNG artifacts across fresh runs; proper nonzero failure paths; settings unchanged; metadata/Qt cleanup; owner/CI PoC observations recorded. If blocked, revise downstream plan before E2. |
| **E2** | Manifest schema/validator, single scenario registry, seven legacy mappings and missing-page ID inventory; progressively add seven absent scenes. Depends E1 contract. | Unknown/duplicate IDs, paths, missing registry keys, page-rename drift, one-way marker/page mapping and orphan approved assets rejected. Legacy provenance honestly `legacy-unverified`. Each added scenario captures reproducibly; E2 schema need not block on all missing scenes, but E6 must close their inventory. |
| **E3** | Diff/rename-aware feature mapping selector + reason report. Depends E2. | Fixtures for single-feature, global-shell, style, `core/**`/`io/**` rendering and RAW/YUV, docs-only, unmapped UI, committed screenshot PNG add/modify/delete/rename (including legacy-unverified), new/deleted/renamed source path and scene-only change; no relevant change silently omitted. |
| **E4** | Pinned-base/head capture, decoded visual diff, artifact report and permissions-limited PR workflow. Depends E1–E3. | Equal/change/new/removed/failed/incompatible scenarios tested; code-only and version-only changes with identical comparable inputs reach pixel diff; true DPI/profile mismatch and scenario/fixture revisions are separately reported. Changed PNG alone does not fail; native capture failure does; same-runner artifact has provenance; no CI commit. |
| **E5** | Markdown ID hook, migrate README's six literal screenshot embeds, narrowly adapt whole-repo docs checker and validate missing-image behavior. Depends E2; parallel with E3/E4 once schema settles. | For each declared PNG removed from a temp **full repository**, `check_docs.py` and strict offline MkDocs pass with exactly the insertion absent; unknown ID, undeclared image, corrupt existing PNG and unrelated broken link fail. Windows/Ubuntu and `file://` / P7 Help contracts unaffected. |
| **E6** | Owner-reviewed promotion, history-derived introducing SHA, provenance/staleness audit, **seven-gap coverage closeout**, instructions and release checks. Depends E4/E5. | Image hash + source SHA bound to approval reference; normal merge/squash/rebase tested without self-referential SHA. Missing/stale capture reported; **all seven gaps either verified or individually deferred with technical reason and owner decision**; rollback/release-tag tests and owner Windows packaged Help smoke. |

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

- **2026-09-21 E0 second re-review:** No remaining blocker; incorporated E3/E6 implementation watchpoints covering rendered-value changes in `core/**`/`io/**` and committed screenshot PNG add/modify/delete/rename including legacy-unverified images. Docs-only clarification before owner-approved merge.
- **2026-09-21 E0 review correction:** Incorporated independent review's three P1s (circular approval commit, README/check_docs missing PNG conflict, provenance versus comparison fingerprint) and two P2s (bidirectional placements and seven-gap closeout; Help-D status in follow-up). Planning changes only, no E1 PoC or test run.
- **2026-09-21 E0:** Inspected merged main, #81/#89 status, capture/test scripts, seven checked-in screenshot assets, User Guide pages, documentation CI/MkDocs, deployment/release boundaries. Identified ten script outputs versus seven differently named committed PNGs, seven stated coverage gaps, and the current script's process-wide fixed waits/Settings clearing. Documented the E1 proof gate and E2–E6 proposal; **no implementation or local/hosted GUI validation performed**.

## Completion summary (E0 only)

- Delivered behavior: plan and references; no runtime behavior change.
- Validation results: GitHub source review only; no test command or Windows-hosted PoC executed in E0.
- Remaining limitations: exact capture UI reliability, per-feature mapping and new scenarios are implementation work.
- Durable docs: this file, `docs/USER_GUIDE_FOLLOW_UP.md`, screenshot strategy README.

## E1 implementation log (separate from completed E0)

- E0 plan merged from PR #93 at `main@92189bd71f9bfcf9d45b339ba3ff273259f090af` after independent blocker-free re-review and owner approval.
- E1 branch: `feature/wp-help-e1-isolated-capture-poc`; **PoC feasibility pending**.
- New `scripts/capture_ui_scene.py` reuses `scripts/capture_ui_review.py::review_document` and actual application composition, with isolated temporary INI QSettings and two explicit scenarios: Single View and RAW profile dialog. The original ten-scene manual-review script remains available; E2 owns unification into a manifest-driven registry. No PNG file names/IDs have yet been migrated.
- `scripts/run_ui_capture_poc.py` runs both scenes in two independent fresh Python processes each, with separate PNG and JSON metadata per attempt; it checks content variation, exact source identity, PNG integrity and changed-pixel fraction. A native process exit/timeout is distinct from a visual difference; the runner must still archive diagnostics.
- `.github/workflows/ui-screenshot-poc.yml` is a limited read-only Windows-hosted PR/manual probe, not PR-wide impact analysis or a permanent Screenshot CI. It has no PR write permission, secrets, artifact promotion or public documentation publishing.
- `tests/unit/test_ui_capture_poc_contract.py` exercises synthetic valid/blank/corrupt PNG inputs and repeatability calculations, independently of Qt.
- **Unverified until real Actions results and artifact inspection:** Windows GUI availability, actual Single View/dialog content and labels, repeated pixel stability, Qt process teardown and Issue #81 behavior. A green documentation test does not advance this gate. If the hosted PoC fails or cannot establish faithful images, record the failure and revise E2–E6 environment assumptions with the owner rather than declaring success.

### Observed Windows-hosted E1 PoC evidence (2026-09-21)

- **Source:** `c700bb3b290a8e69e54a1b2271475f2316e68261`; [Screenshot PoC workflow run](https://github.com/delphykmc/pixelscope/actions/runs/35570578220), 14-day [artifact #10625896512](https://github.com/delphykmc/pixelscope/actions/runs/35570578220/artifacts/10625896512). Hosted Windows Python 3.10.11, pinned PySide6 6.4.2 / pyqtgraph 0.13.7; profile `windows-e1-poc-v1`, logical DPI 96, DPR 1.0, HyperVMonitor desktop 1024×768.
- **Verified visual content by artifact inspection:** `single_image-1.png` is a genuine 1680×980 `MainWindow` showing the synthetic RGB gradient, selected Files entry, image header, toolbar and Statistics; `raw_profile_dialog-1.png` is a genuine 520×620 `RawOpenDialog` displaying RAW dimensions/stride/pixel layout and controls. They were captured through actual `QWidget.grab()`, not from generated mock UI. A Windows hosted runner auto-clamped the original `resize(1680, 980)` to 1028×749; `setFixedSize(1680, 980)` restored the intended intrinsic PNG size even on the smaller desktop. Future profile evolution should check this invariant.
- **Four separate process attempts:** Single View 2/2 exit 0; RAW dialog 2/2 exit 0. No native crash observed in these attempts. The repeated decoded-pixel changed fractions were `0.000010933` (Single) and `0.000452854` (RAW dialog), respectively; **not bitwise-identical**, though below the E1 diagnostic 1% tolerance. Raw GUI passes do not establish full-suite Issue #81 resolution. The differing pixels have **maximum per-channel absolute delta = 1** and are localized to small UI icon regions (Single View near the Files tree, RAW dialog near information icons). E2/E4 must treat this measured same-source jitter as a visual-diff calibration input, not assume same-head PNGs are byte/pixel identical or suppress all one-level changes without an owner-reviewed policy.
- **Workflow:** screenshot job SUCCESS, independent User Guide validation job SUCCESS at this head ([documentation run](https://github.com/delphykmc/pixelscope/actions/runs/35570578118)). The focused PNG-unit tests passed. The same artifact includes `report.json`, per-attempt metadata, runner information and PNGs. The later geometry-contract/test follow-up remains to be validated at its own HEAD before PR review closure.
- **Not performed:** owner-local Windows full pytest or installer/portable Help smoke; main/base visual diff, seven-scene inventory closeout, CI promotion or documentation PNG updates. All of these remain outside E1.
