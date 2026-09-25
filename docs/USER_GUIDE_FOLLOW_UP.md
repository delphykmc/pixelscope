# User Guide follow-up work packages

The searchable User Guide foundation is now merged. Follow-up work keeps application Help integration, release packaging, hosting, and agent-facing extensions as separate contracts.

## WP-Help-A — Application Help integration

Status: **merged in PR #87**.

- **Help > User Guide** is installed by the production application composition.
- Frozen/release builds resolve the local entry point relative to the executable as `help/index.html`; the application does not depend on the process working directory.
- Source runs can open an already-built `site/index.html` and may also consume a local `help/index.html` bundle.
- The local page is handed to the platform through `QDesktopServices` rather than embedding a browser engine or introducing QtHelp/QCH.
- A build without a local bundle reports that the User Guide is unavailable instead of guessing an online location.
- Focused tests cover path resolution, Help-menu placement, idempotent installation, and local-file URL handoff.

Online Documentation remains dependent on an explicitly approved authoritative HTTPS deployment URL. At the time of WP-Help-A, F1/context-sensitive routing was deferred; it was subsequently delivered in WP-Help-E7 / PR #101.

## WP-Help-B — Fully local documentation build and packaging — merged in PR #90

**Non-negotiable security contract:** the User Guide must build from checked-in files plus a
preinstalled documentation toolchain, even when individual external URLs are blocked. A
previously warmed MkDocs privacy cache, permitted CDN access, symlink privileges, or
internet access on the release machine must not be prerequisites.

- Replace the current CDN-based iframe-worker polyfill with a versioned, checked-in local
  JavaScript asset. Preserve working `file://` search; do not disable the offline plugin,
  substitute a no-op shim, or merely silence privacy-plugin warnings.
- Investigate the current build-time Mermaid CDN fetch. If no supported User Guide page
  uses Mermaid, remove its dependency without introducing an unbundled runtime URL.
  Otherwise vendor the exact required script locally.
- Record upstream version, source, license/attribution, and a reproducible content hash
  for each vendored third-party asset. Avoid downloading arbitrary mutable CDN content
  during routine documentation builds.
- Make `mkdocs build --strict` work after clearing `site/` and
  `.cache/plugin/privacy/` with outbound network access blocked. Include a deterministic
  test/CI job that prevents outbound requests during the build, not just an assertion
  that HTML is free of CDN links after a network-enabled build.
- Extend the generated-site contract to cover all runtime-loaded HTML, CSS, and JS
  references and to detect missing relative assets, especially the search shim.
- Consume the validated, self-contained `site/` as a release input for the offline
  `help/` bundle. Include it in portable ZIP and Inno Setup artifacts at the exact
  executable-relative path `help/index.html`.
- Validate offline search, navigation, screenshots, and relative links in installed
  and portable builds on Windows without network access.
- Documentation packages remain build-time dependencies, never PixelScope runtime
  dependencies. If the package installation itself must occur air-gapped, provide an
  approved internal package index or a prebuilt, pinned wheelhouse; this bootstrap is
  separate from the requirement for a network-free MkDocs build once installed.

Implementation notes for this work package:

- An exact published iframe-worker 1.0.4 shim is checked in with MIT license,
  upstream provenance, and an executable SHA-256 integrity check. The configured
  polyfill points to the local file and the privacy plugin is no longer needed.
- The existing User Guide does not use Mermaid diagrams; no CDN-based Mermaid
  file is part of the normal documentation build. Future Mermaid usage must
  preserve the same network-free build contract.
- CI invokes strict MkDocs with socket connections denied on both Windows and
  Ubuntu, after deleting generated site and privacy cache.
- Release build generates the site using the documentation environment, then
  copies the validated files to `dist/PixelScope/help/` beside the executable.
  The existing portable/installer pipelines retain the single canonical onedir
  payload; artifact validation requires the bundled Help.
- The generated 404.html is reserved for hosted documentation, excluded from
  the local executable-relative bundle because its root-relative URLs do not
  work through `file://`.
- The owner reported the full Windows release/portable/installer smoke PASS
  for PR #90; GitHub's documentation CI is not evidence of an installer smoke run.

## WP-Help-C — Optional documentation publication — merged in PR #91

- Produce an explicitly initiated, validated and version-identified static site
  artifact from the existing User Guide source. Preserve release provenance
  independently of P7 application release artifacts.
- Support manual GitHub Pages publishing **only** when the repository owner
  enables the Pages destination and explicitly opts in. Otherwise the same
  site artifact can be moved to an approved enterprise/internal static host;
  docs build, release and local Help remain independent of Pages.
- Restrict publication source to merged `main` or the matching canonical
  `v<version>` release tag and record the exact commit, version, inventory
  and hashes. Do not automatically create tags or claim permanent HTML archives.
- Define 14-day Actions transfer-artifact retention (or stricter platform
  policy), manual rollback, and the distinction between current live docs
  and historical source in Git. See `docs/USER_GUIDE_DEPLOYMENT.md`.
- Prepare a separately gated **Online Documentation** action, which remains
  disabled until an actual approved HTTPS site URL is configured in a
  reviewed code change. Never fall back from local Help or reuse SSO tokens.
- Fix the prior #90 reviewer P1: validate all local HTML navigation links,
  not just generated `llms.txt` routes and resource references; reject
  hosting-only 404 pages in an offline installed bundle.

## WP-Help-D — Agent interface — merged in PR #92

The merged WP-Help-C offline/static publication pipeline was the prerequisite.
WP-Help-D delivered an agent-facing **retrieval interface**, not a chatbot:

- Expand the existing static `llms.txt` to cover every canonical User Guide
  navigation route and keep its generated HTML paths under the same strict
  site validation. Do not invent a new protocol or duplicate Markdown.
- Provide a deterministic repository-local User Guide search CLI with text and
  bounded JSON results, source-relative path/line citations and generated site
  routes. It reads the canonical Markdown only and needs no network, credentials,
  local image files, embeddings, or runtime application dependency.
- Lock down coverage with focused tests and documentation CI; keep offline Help,
  manual publication, and P7's release-bundle contract unchanged.
- Evaluate Ask PixelScope separately in
  [Agent interface](USER_GUIDE_AGENT_INTERFACE.md). An optional model/RAG
  experience requires a justified UX, source grounding, privacy/security design,
  provider approval, and a distinct owner decision. Do not add one by default.

The repository-side search tool is not shipped as a new application feature;
installed users retain their existing local Help/search without an AI service.

## Help/navigation follow-up — completed by WP-Help-E7

- F1/context-sensitive Help is an application UI navigation feature, not WP-Help-D agent work.
- E7 / PR #101 adds real-key Qt shortcut regression coverage and exact, unchanged missing-bundle/browser-open failure messages. The original WP-Help-A deferral above is historical.

## Deferred/non-goals

WP-Help-A did not include an embedded PyQt Help window, QWebEngineView, QtHelp/QCH, chatbot, RAG server, Remote LLM API, implicit online fallback, or context-sensitive F1 routing; **F1 was delivered later in E7**, not retroactively in A. Installer bundle integration is owned by WP-Help-B.

## WP-Help-E — Automated Screenshot Lifecycle — E0–E5 merged / E6 final acceptance recorded

E0 is a planning-only follow-up to merged WP-Help-A/B/C/D (#87/#90/#91/#92).
The [WP-Help-E execution plan](exec-plans/active/wp-help-e-automated-screenshot-lifecycle.md)
records the existing real-QWidget capture implementation, tracked screenshots and
missing scenes; a single Screenshot ID manifest; PR impact selection and conservative
fallback; pinned-main/head visual diff; separate Documentation CI and Screenshot CI;
reviewed image provenance; security, Windows Qt lifecycle and release boundaries.

**Gate:** E1 first proves real screenshot capture on a Windows GitHub-hosted runner
using isolated scenarios. No hosted-GUI feasibility or Issue #81 native-crash fix is
claimed by E0. If the PoC fails, revise the remaining WP sequence and obtain owner
approval for another execution environment before implementing a full screenshot CI.

The proposed sequence is E0 plan → E1 isolated capture/Windows PoC → E2 manifest/
scenario contract → E3 conservative impact analysis → E4 pinned baseline/head visual
diff and PR artifacts → E5 conditional MkDocs screenshot rendering and independent
documentation validation → E6 human approval/provenance/release policy. E5 can proceed
in parallel with E3/E4 after E2 settles the manifest schema. Each implementation WP
uses a separate reviewed PR; image candidates never auto-commit and PRs never
self-merge. Existing screenshot guidance remains at
[user-guide/assets/screenshots/README.md](user-guide/assets/screenshots/README.md).

E0 planning was merged as PR #93. E1 implements a limited, isolated Windows real-GUI
capture feasibility probe for Single View and RAW profile dialog, with two fresh
capture attempts per scenario, PNG/metadata artifacts and explicit native-failure
reporting. It does **not** yet replace the seven approved guide screenshots,
produce a manifest or activate change-impact Screenshot CI. E1 success requires
inspection of actual hosted Windows PNGs and repeatability; static checks alone
are not evidence of GUI availability or a fix for Issue #81.

E1 was owner-approved and merged as PR #94 at `main@ec8563df821a77b270363b00cff83e6c97e9db07` after Windows-hosted PoC, documentation CI and reported owner Windows validation. This proves only the two isolated capture scenes; Issue #81 is not marked resolved. E2 introduces a versioned seven-legacy/seven-planned Screenshot Manifest, classifies legacy-only scenes and three diagnostics, and adds Qt-free inventory/PNG/reference checks. E2 **does not yet** enable Screenshot ID Markdown insertion, missing-PNG omission, E3 impact mapping, E4 visual baselines or E6 promotion; these retain their separate review gates.

### E2 completed / E3 impact selector

E2 PR #95 merged at `main@415dab7cf4742cce0d6369024cdc91da652556d7` after owner full-pytest and live Help/image-rendering smoke PASS. Owner also observed that **some existing guide screenshots appear older than current UI**. This is tracked as screenshot-content review/replacement debt in E4–E6, not proof that guide instructions are incorrect; existing `legacy-unverified` PNGs must not be called current, automatically replaced or assigned invented capture commits.

E3 owns Qt-free source-file change impact inference with verified per-scene ownership, shared shell/fixture mapping, conservative unknown UI/core/io fallback, renames/deletions and committed PNG changes. It is distinct from actual E4 Windows comparison and E5/E6 User Guide image migration/promotion.


### E3/E4 merged; E5 source-marker migration

E3 impact-selection PR #96 merged at `main@5e5a418d19393560f484f332d2c64a5cc0149526`.
E4 pinned real-Windows baseline/HEAD comparison PR #97 merged at
`main@985e69d6dd1840cbf5b0739be8ca29b758c36cdc`, following independent
blocker-free review and owner-reported full local Windows pytest PASS. E4
generates read-only, inspectable candidate PNGs/reports; it does **not** prove
seven legacy screenshot captures are current or approve/promote any of them.

E5 migrates the six topic-page literal PNG image links to canonical manifest
Screenshot ID markers. The Qt-free manifest checker verifies source placements
and real committed PNGs; the same checker executes before direct strict MkDocs
builds. A declared missing PNG is omitted from web and installed offline HTML
without a broken link or altered source explanation. All unrelated documentation
links remain under the existing whole-repository `check_docs.py` validator.
E5 separately tests all seven declared historical PNGs removed one at a time
from a full repository copy under network-blocked strict MkDocs builds. The
floating Plots PNG stays declared but has no invented topic placement.

E6 still owns fresh current-UI candidate review, explicit owner approval,
screenshot byte promotion, trustworthy provenance and per-gap closeout of the
seven not-yet-automated scenes. E5 was owner-approved and merged as PR #98 at
`main@0381d4e69df82f060dc4917b4117f68b8cebc574`. The new
[E6 owner review procedure](exec-plans/active/wp-help-e6-owner-review.md) and
[14-ID decision inventory](exec-plans/active/wp-help-e6-coverage-decisions.json)
deliberately record no blanket acceptance: `python scripts/audit_ui_screenshot_coverage.py`
reports unresolved images without inventing approvals, and
`--require-complete` fails until per-ID review decisions are made. Neither E5 nor CI changes approved PNGs
automatically; Issue #81 remains a separate lifecycle task.

### E6 screenshot promotion and owner release closeout — 2026-09-25

E6 PR #99 provides 14/14 real-UI, source-and-hash-attested, owner-approved screenshot promotions (seven replaced historical images and seven newly covered topics), with original owner-local capture-packet verification and independently reviewed provenance/coverage audits. All fourteen decision records are `promoted`; the owner also confirmed the installed Guide opens normally and that the replaced screenshots render correctly after successful local tests and release-candidate validation: [owner final acceptance](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5831061914). The independent review found no remaining code-review blocker, and the owner authorized merge after documentation closeout. Earlier E5-era references to seven planned screenshots and unresolved approval above are preserved as *historical stage descriptions*, not the present inventory.

After merge, run `scripts/audit_ui_screenshot_git_history.py --ref origin/main` against the actual merged history. An eventual release tag must separately pass the per-ref image/manifest/rollback audit when that tag exists. This is not permission for automatic website publication or a statement that Issue #81 native crash is solved.

## WP-Help-E7 — Context-sensitive offline Help and error-message regression — completed in PR #101

Status: **Implementation complete, independently re-reviewed without remaining E7 blockers and owner-accepted on 2026-09-26** in [PR #101](https://github.com/delphykmc/pixelscope/pull/101) at reviewed code HEAD `d4ddf75379b684e22f0efb68102181dfb9b78668`. The PR merge record is authoritative for the final `main` merge SHA.
Depends on the merged E6 screenshot/Guide integration in PR #99.

- Keep **Help > User Guide** opening the local guide index. Add a separate **Help > Context Help (F1)** action that routes the focused Files, Image View, Statistics/Difference, Histogram/Line Profile or IQA workspace to its existing MkDocs HTML topic. Where focus is ambiguous or no topic is available, open the local index.
- Provide scoped F1 Help on the existing Settings, RAW Profile and native YUV dialogs. Preserve Qt object ownership and do not install a global event filter, embedded browser, network fallback, online URL, or duplicate documentation source.
- Resolve topic paths relative to the already-authoritative local `help/index.html` (frozen) or `site/index.html` / `help/index.html` (source). Restrict navigation to the local bundle; a missing topic falls back to its index; a missing bundle and browser-open failure retain the current explicit messages.
- Extend existing `tests/ui/test_user_guide_help.py` to verify **exact error titles and bodies**, no online fallback, F1 route selection, action idempotence, dialog shortcut ownership, and safe page fallback. Update the shortcut reference. Check documentation links and release Help packaging; visually smoke F1 in installed Portable/Installer before owner merge acceptance.
- **Completion evidence:** initial P1/P2 review findings were addressed and all five original threads resolved; exact reviewed HEAD [Windows/Ubuntu User Guide CI #36158028297](https://github.com/delphykmc/pixelscope/actions/runs/36158028297) and [E4 Windows GUI screenshot comparison #36158028316](https://github.com/delphykmc/pixelscope/actions/runs/36158028316) passed. Windows E7 UI suite: **23 passed**, docs-focused suite: **145 passed**, Windows release-artifact unit suite: **31 passed**; Ruff, full-source mypy and strict network-blocked offline site checks passed. These are not claims of owner-local full pytest or actual Installer/Portable build automation.
- **Owner acceptance:** the owner reported pressing F1 in the actual PixelScope application and observing normal Help behavior, then authorized E7 merge. No separate per-distribution/per-dialog Owner smoke result is inferred beyond that report.
- E7 does not change Issue #81 lifecycle/native-crash root-cause status; online publication remains manually gated.

## WP-Help-E8 — Screenshot-rendering test performance follow-up — Issue #100

Status: **E8 A/B screenshot-test optimization and owner Windows timing completed; independent A/B review found no P1/P2 blocker. CI cost improvements (E4 early selection and Docs push/PR duplication) are being evaluated on `perf/wp-help-e8-screenshot-rendering-tests`; final CI/independent review, owner acceptance and merge remain pending. [Issue #100](https://github.com/delphykmc/pixelscope/issues/100) OPEN.**

The owner-local Windows screenshot-rendering test baseline is **18 passed in 138.72 s**. The module-scoped repository-copy fixture costs **58.85 s setup**; separate full integration calls are **20.51 s** (all PNGs absent), **19.98 s** (all present), **16.64 s** (corrupt PNG), and **16.38 s** (hook-only test that copies the repository). Issue [#100](https://github.com/delphykmc/pixelscope/issues/100) is authoritative for phase-level profiling, measured optimization, preserved 14-ID/strict-offline/source-link coverage, review and owner Windows acceptance. Close #100 only with reviewed, validated, merged E8 work and a measured closeout comment. Do not use `--skip-pytest` as a substitute for E8 test evidence.

Resolution-aware FHD/UHD viewer synchronization is explicitly not part of E7 or E8 and will be planned in a separate session.

### E8 CI-cost slice — pinned E4 preflight and conservative Docs-run deduplication

Following the [independent optimization review of PR #102](https://github.com/delphykmc/pixelscope/pull/102#issuecomment-5836331537) and the owner's request, CI cost is included in the same E8 PR, in separate commits after A/B. The optimizer observed a same-HEAD **E4 Windows job ~79 s, installation ~45 s, GUI capture step ~1 s** for a mostly non-rendering change; earlier screenshot-affecting E4 runs legitimately spent much longer in real capture. It also identified repeated same-SHA `push` and `pull_request` User Guide runs. These are **historical observations**, not guaranteed savings on every future PR.

- **E4:** Both same-repo base/head commits are still independently checked out at exact 40-character SHAs with read-only credentials. Python 3.10 runs the existing stdlib E3 selector **before installing the application, Pillow, pytest, Ruff or Qt**. The new fail-closed preflight allows no native GUI only with matching pinned SHAs, schema v1, an explicitly empty `selected_ids`, no warnings/manifest review/PNG change/removed-ID/profile-change flags, and an explicit no-selection reason. It writes `selection.json`, `report.json`, and `summary.md` to the original E4 artifact location. A selection error fails the job; **any selected ID, including removed/deferred IDs, retains the existing install, comparator regressions and genuine base/head GUI capture/review path**. Conservative E3 ownership/fallback and screenshot approval/provenance remain untouched; the broad E4 PR path trigger stays in place. The E8 PR itself modifies `ui-screenshot-diff.yml`, which E3 deliberately treats as screenshot-automation impact and may cause full GUI work **for this PR**. Unit regressions cover empty/pinned/mismatch/warnings/removed/deferred paths; do not infer a measured empty-path workflow speedup until it actually executes on a qualifying PR.
- **Docs validation:** Preserve `push` **and** `pull_request` triggers, their identical path filters, all required PR Windows/Ubuntu checks, and the post-merge `main` push. A branch-only push with no open matching same-repository PR still runs the full matrix. For non-`main` pushes only, a read-only API guard skips expensive steps **only after an actual User Guide `pull_request` workflow run for that exact HEAD SHA/branch/open PR exists**. An open PR by itself, PR event path-filter omission, API error, missing token, cancelled/skipped PR run or push/PR enqueue race **does not justify skipping**; the push runs normally when no equivalent run is proven. The required PR job is never cancelled. Push/PR path filters were aligned (including `test_user_guide_packaging.py`) and expanded for the new E8 helpers/tests. Both matrix jobs still consume checkout/setup and a small API lookup on a proven duplicate; the saving is the dependency install and real test/build steps, not zero runner time.
- **Unchanged:** Full Docs CI checks on the PR, strict network-blocked cold-cache MkDocs, E4 unknown-impact conservatism, E1 PoC, release validation, and manually dispatched User Guide publication/Pages approval. No opportunistic `--skip-pytest`, screenshot PNG/manifest byte change, or production UI edit. Independent CI-policy review and exact-HEAD CI are additional gates for these new workflow edits.

### E8 implementation checkpoint — instrumentation first (2026-09-26)

The independent optimizer's [Issue #100 review](https://github.com/delphykmc/pixelscope/issues/100#issuecomment-5835678722) sets the order: measure distinct phases first, then A (hook-only full-clone removal), B (safe reusable full-repo fixture), C (per-ID duplicate validator calls only with mutation-based equivalent coverage), and finally CI event/selector improvements if justified by measured cost and conservative impact contracts. E7 merged `main@31275ec0855037dcfe90a8e09fe908bbe15c204b` is the frozen baseline for this branch.

#### Windows owner Phase 0 measurements — pre-optimization (`0478953d8`)

The owner supplied three fresh-process `phase-1.log` / `phase-2.log` / `phase-3.log` captures from the **opt-in instrumented, unoptimized** E8 HEAD `0478953d8c680004a1177850312682639a6ffd93`. All three report **18 passed**. Reconstructed exclusive top-level phase observations:

| Windows local measurement | Run 1 (s) | Run 2 (s) | Run 3 (s) | Median (s) |
|---|---:|---:|---:|---:|
| Entire pytest invocation | 108.81 | 110.33 | 101.87 | **108.81** |
| Full repository copy, 5 times combined | 83.27 | 85.76 | 78.30 | **83.27** |
| Opt-in file count/byte inventory, 5 times | 8.27 | 8.10 | 7.76 | **8.10** |
| 14 per-ID `check_docs` calls | 4.38 | 4.27 | 4.04 | **4.27** |
| 14 per-ID `on_pre_build` calls | 2.07 | 1.95 | 1.93 | **1.95** |
| All PNGs absent: offline-build subprocess | 4.34 | 3.66 | 3.48 | **3.66** |
| All PNGs present: offline-build subprocess | 3.60 | 3.91 | 3.67 | **3.67** |
| Corrupt PNG: expected-failing strict build | 0.95 | 0.92 | 1.04 | **0.95** |

Each copy measured **7,823 files / 1,053,048,342 bytes (~1.05 GB)** in about 15–18 seconds. The initial fixture and the four separate integration tests create **five copies**; this is the measured dominant expense, not image marker substitution. The original, profiler-OFF **138.72 s** run and the opt-in instrumented **108.81 s median** were performed under different conditions; their difference is *not* a measured optimization effect. Nested child `offline-strict-mkdocs` and `offline-generated-site-validation` are already included in the parent subprocess timer and must not be counted twice. The corrupt-PNG traceback is an intentional PASS of the negative regression.

On this evidence A/B fixture reuse was implemented in separate commits with per-test approved PNG SHA-256 and original Markdown byte checks, reversible image mutation in `try/finally`, generated-site cleanup and explicit negative-link/error-recovery regressions. The original 14 per-ID tests and all three actual build regimes remain mandatory. This stage was documented in [Issue #100](https://github.com/delphykmc/pixelscope/issues/100#issuecomment-5835985205).

#### Windows owner Phase 1 — after A/B reuse (`8062e7de`)

Owner supplied three fresh-process logs from the A/B implementation HEAD `8062e7de4686dd41f46603a93411134017b9c34b`: **20 passed in 30.46, 34.98 and 35.54 s** (median **34.98 s**, range **30.46–35.54 s**). An additional profiler-OFF owner run reports **20 passed in 36.24 s**. The four observed totals have median **35.26 s** (range **30.46–36.24 s**). The three attached post-change files contain pytest duration tables but **no `PIXELSCOPE_E8_PHASE` markers**: treat them as pytest wall-time observations, not as a post-change phase profile. Their first module-fixture setup costs **15.22, 17.16 and 17.96 s** (median **17.16 s**), consistent with the intended single full repository clone. All-present real offline builds cost 3.86/4.49/4.51 s and all-absent builds 3.70/4.30/4.30 s. The corrupt-PNG negative build still passes and the two new recovery/link regressions pass.

The historical, uninstrumented **138.72 s for 18 tests** versus post-A/B **34.98 s median for 20 tests** is an **indicative 103.74 s / 74.8% wall-time reduction (~3.97× faster)**, but not a perfectly matched environment/process baseline; the strongest causal attribution is the independently measured pre-change **5 copies / 83.27 s median** versus the implemented one-copy fixture and post-change first setup **17.16 s median**. Do not compare opt-in **108.81 s** with profiler-OFF **34.98 s** as if the diagnostic inventory were free. Run data and interpretation are recorded in Issue #100 and PR #102. **No further owner phase sampling is required solely to accept the already demonstrated A/B wall-time result**; request more instrumentation only for a specific subsequent code change or unresolved performance question.

The first E8 commits added **opt-in diagnostic timing** to the original screenshot-rendering tests and the cold-cache network-blocked documentation build script. `PIXELSCOPE_E8_PROFILE=1` prints `PIXELSCOPE_E8_PHASE` JSON lines for repository copies (and separate file inventory), per-ID check_docs/pre-build/marker render, PNG remove/restore, full-build parent subprocess, and child cache purge/MkDocs/site-validation phases. Parent subprocess wall time **includes** child phases and must not be added to them. Normal CI/test behavior is unchanged when the env var is absent. The historical 138.72 s uninstrumented run, three instrumented before-runs, and four post-A/B owner wall-time observations are recorded above. A/B reuse one full copy rather than five and add two contract regressions (**20 tests** total).

Owner Windows sampling command (PowerShell from repository root, in the same configured docs/pytest venv; `-s` ensures phase markers are retained in the log):

```powershell
$env:PIXELSCOPE_E8_PROFILE = '1'
New-Item -ItemType Directory -Force temp/e8 | Out-Null
try {
    1..3 | ForEach-Object {
        & .\.venv\Scripts\python.exe -m pytest -q -s tests/unit/test_user_guide_screenshot_rendering.py --durations=0 2>&1 |
            Tee-Object -FilePath "temp/e8/phase-$_.log"
        if ($LASTEXITCODE -ne 0) { throw "E8 screenshot rendering run $_ failed ($LASTEXITCODE)" }
    }
} finally {
    Remove-Item Env:PIXELSCOPE_E8_PROFILE
}
```

Run the same command in three fresh Python processes; preferably alternate cold/warm order with unrelated work to reduce first-run cache bias. Record Python, pytest, MkDocs, SSD/NTFS context if known, exact E8 HEAD SHA, wall time/phase medians and spread; compare Windows owner-local with Windows CI and Ubuntu CI **separately**. Keep the new logs untracked (e.g. write under `temp/`) and do not include local absolute paths/private environment data in PR screenshots or logs. A/B post-change owner measurements are recorded above and complete the requested timing checkpoint. The suite contains 20 tests: original 18 plus two negative/cleanup regressions. No change to CI events or E4 selector is included in A/B. Any later CI-event change still requires separate cost and impact/trigger proof, not just a lower `--durations` value.
