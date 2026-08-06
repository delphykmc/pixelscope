# Execution plan: P2 — Runtime Foundation, Settings & Performance

Status: Active  
Owner: repository owner + P2 orchestration agents  
Branch/PR: P2-0 `docs/p2-0-program-setup`; P2-A `feature/p2-a-settings-identity`; one scoped PR per later subphase  
Last updated: 2026-08-07

## Goal

Establish explicit startup settings, byte-budgeted decoded-source residency,
bounded preload, deterministic diagnostics, and performance hardening while
preserving current PixelScope behavior and keeping each subphase independently
reviewable.

## Scope

### In scope

- P2-0 durable P1 completion and roadmap transition.
- P2-A application identity, resources, typed settings, persistence, and
  Difference-cache startup injection.
- P2-B byte-budgeted native decoded-source residency.
- P2-C bounded one-group-ahead folder preload.
- P2-D deterministic runtime diagnostics and sanitized failure visibility.
- P2-E integration, characterization, mechanical checks, and phase hardening.

### Out of scope

- Persistent comparison sessions, Recent Files/Folders, saved ROI management,
  arbitrary-angle line sampling, alpha overlay, and broader export workflows.
- RAW demosaic, black/white-level processing, profile suggestion, and profile
  management.
- Remote GPU/server work, remote IQA submission/result UI, heatmaps, login, SSO,
  token/credential management, and access administration.
- Installer, signing, update checking, and release distribution.
- Mixed-dimension Statistics redesign, broad shortcut redesign, broad
  MainWindow rewrite, or native C/C++ optimization without profiling evidence.

## Current state

- PR #12 merged at
  `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`; that commit is also the P2-0
  branch base.
- P2-0 merged as PR #13 at
  `52daa63425a286e370aa5ef36f59ba51a8acd565`; P2-A starts from that latest
  `main` commit.
- The canonical blue-gray PixelScope SVG/PNG/ICO triplet, package-data declaration,
  package-resource loader, and `QApplication` icon assignment are present in the
  draft P2-A identity slice. Owner Windows visual validation remains pending.
- `DifferenceMapCache` is already a byte-budgeted LRU. The default is 512 MiB;
  `used_bytes`, `budget_bytes`, and `entry_count` diagnostics exist.
- `DifferencePanel` accepts `difference_cache_budget_bytes` in its constructor,
  but `MainWindow` currently relies on the default rather than startup settings.
- Frozen `PerformanceSettings` exists and currently contains only the Difference
  cache budget. Application bootstrap does not load or inject it.
- Decoded-source residency is not absent: `MainWindow` owns a reloadable,
  count-based seven-document policy coupled to UI/application lifecycle.
- The current residency protected set uses visible documents and active load
  targets. Selected and analysis documents are not yet explicit policy inputs.
- Native source loading uses a dedicated pool with at most two workers; shared
  numerical work uses a pool with at most four workers.
- Normal-load stale-result handling primarily uses target document ID,
  `MainWindow._load_tokens`, the load-worker registry, and rejection of results
  from cancelled workers. `ImageLoadWorker` is not assumed to own a complete,
  meaningful document-generation identity contract.
- Settings dialog, settings persistence/migration, decoded-source budget,
  preload, and diagnostics UI are not implemented.

## Corrected assumptions

- Difference-cache budgeting is implemented; startup persistence/injection is
  the missing part.
- Source residency exists, but it is fixed-count rather than byte-budgeted.
- Current residency protection is limited to visible documents and active load
  targets; selected and analysis protection are P2-B targets.
- `ImageDocument.from_array()` retains native source and preview; a native source
  budget is not total process memory.
- Cancellation does not guarantee an already-running decoder stops immediately.
  Obsolete-result rejection is a separate contract.
- Current request identity must not be described as stronger than the actual
  `_load_tokens` and worker-registry implementation.

## Invariants and constraints

- Target CPython 3.10 x64, PySide6 6.4.2, and pyqtgraph 0.13.3.
- Keep exactly PyInstaller 5.7 `onedir` compatibility; resource lookup must not
  depend on source-tree paths or the current working directory.
- Keep expensive I/O and numerics off the UI thread.
- Preserve source dtype, channel meaning, strides, endianness, alignment, and
  overflow-safe arithmetic.
- P2 settings applied to resource budgets are immutable startup snapshots;
  runtime editing indicates restart required.
- Difference cache and decoded-source residency remain separate budgets.
- Decoded-source accounting covers `ImageDocument.source` only. It excludes
  previews, Qt textures, Difference/derived caches, and transient worker arrays.
  Diagnostics must label it `Decoded native source arrays only`.
- Source budget is a soft limit because protected documents may temporarily
  exceed it.
- Normal load has priority over preload.
- No credential or token storage is introduced before P6.

## Proposed architecture

The current `MainWindow` remains the integration point during P2, but policy
sources of truth move behind explicit boundaries:

- `SettingsRepository`: typed settings load/save/reset and schema migration.
- `ApplicationSettings`: validated persisted user choices.
- immutable `PerformanceSettings`: startup-only budget/preload snapshot.
- `ResidencyManager`: native-source byte accounting, protection, LRU eviction,
  reload policy, and diagnostics.
- `PreloadController`: one-group-ahead request planning, bounded worker ownership,
  stale cancellation/drop, and budget-aware retention.
- `DiagnosticsSnapshot` or equivalent immutable model: deterministic counters and
  sanitized failure information.

These are planned P2 boundaries, not current components. UI widgets must not
become policy owners.

## Subphase dependency graph

`P2-0 → P2-A → P2-B → P2-C → P2-D → P2-E`

Each phase starts from the latest merged `main`; no phase is developed against
an unmerged predecessor.

## P2-0 through P2-E

### P2-0 — Program setup and roadmap transition

Status: Complete; merged as PR #13  
Branch: `docs/p2-0-program-setup`

- Preserve P1-D/P1-E/P1-F as completed durable history.
- Transition ROADMAP to P2–P7.
- Establish this active P2 plan and reconcile current-state documentation.
- Documentation-only changes; no source, test, script, or packaging changes.

### P2-A — Application identity and Settings foundation

Status: In progress; draft identity/resource slice opened  
Branch: `feature/p2-a-settings-identity`

- PixelScope application/window/taskbar icon and canonical resource asset.
- Packaged-resource-safe lookup.
- Typed `ApplicationSettings`, immutable startup `PerformanceSettings`,
  `SettingsRepository`, and QSettings persistence adapter.
- Schema version, migration, validation, defaults, reset, and invalid-state
  handling.
- Settings dialog with restart-required indication and Reset Settings.
- Difference-cache budget setting and startup injection with a confirmed 512 MiB
  default.

The current draft implements the first two bullets only. It remains draft until
the settings/persistence scope and required validation are complete.

Explicit exclusions: decoded-source budget control, preload control, diagnostics
dialog, credentials/tokens, installer, and signing.

### P2-B — Byte-budgeted decoded-source residency

Branch: `feature/p2-b-source-residency-budget`

- Remove the fixed seven-document limit as policy source of truth.
- Account native decoded `ImageDocument.source.nbytes`.
- Introduce LRU `ResidencyManager` with visible, selected, analysis, and active
  load-target protection.
- Implement soft-budget behavior, oversized protected-source policy,
  eviction/reload, dependent cache invalidation, decoded-source budget setting,
  and diagnostics API.

Accounting is intentionally narrower than process memory.

### P2-C — Bounded next-group preload

Branch: `feature/p2-c-folder-preload`

- Compute the next group from the current folder-pair context.
- Preload one group ahead only.
- Use bounded worker ownership that cannot starve normal loads.
- Cancel or drop stale work; validate request token/generation before apply.
- Retain only when compatible with the source budget.
- Add preload setting and diagnostics.

Cancellation contract: a running decoder may finish; obsolete results must not
apply. Cancellation requests and stale-result rejection are distinct signals.

### P2-D — Runtime diagnostics and failure visibility

Branch: `feature/p2-d-runtime-diagnostics`

- Produce a deterministic snapshot containing source residency used/budget/count,
  Difference cache used/budget/entries, normal-load workers, analysis workers,
  preload counters, stale-result drops, and sanitized failure summaries.
- Add Copy Diagnostics and optional text export.
- Redact full paths by default; use basename or relative representation.
- Exclude bearer tokens, credentials, pixel content, and unbounded raw traceback.
- Diagnostics reads must not start expensive work.

### P2-E — Performance characterization and phase hardening

Branch: `feature/p2-e-performance-hardening`

- Integrate P2 behavior and complete settings default/migration/invalid tests.
- Characterize FHD/UHD navigation; uint8/uint16/RGB/grayscale/Bayer/RAW;
  low-memory budgets; oversized sources; rapid navigation; cancellation and
  stale rejection; diagnostics consistency.
- Add architecture mechanical checks and deterministic performance smoke tests.
- Evaluate Windows CI quality-gate feasibility and complete durable P2 docs.
- Do not add a new large feature.

## Branch and PR sequence

| Order | Branch | Merge prerequisite |
|---|---|---|
| 0 | `docs/p2-0-program-setup` | PR #12 merged |
| 1 | `feature/p2-a-settings-identity` | P2-0 merged; required owner decisions resolved |
| 2 | `feature/p2-b-source-residency-budget` | P2-A merged |
| 3 | `feature/p2-c-folder-preload` | P2-B merged |
| 4 | `feature/p2-d-runtime-diagnostics` | P2-C merged |
| 5 | `feature/p2-e-performance-hardening` | P2-D merged |

## Merge gates

- **P2-0:** docs-only diff, coherent P1 archive, P2 active plan, ROADMAP P2–P7,
  documentation checker and docs contract.
- **P2-A:** typed settings/persistence tests, resource lookup from source and
  packaged-layout simulation, invalid/legacy/reset behavior, restart indication,
  and Difference budget injection.
- **P2-B:** deterministic accounting/eviction/protection/oversize/reload tests;
  no fixed-count policy remains authoritative.
- **P2-C:** normal-load priority, bounded ownership, stale cancellation/drop,
  generation/token validation, budget-aware retention, and rapid-navigation tests.
- **P2-D:** deterministic/redacted snapshot, no expensive work on inspection,
  copy/export tests, and credential/path/pixel exclusions.
- **P2-E:** full standard validation, deterministic performance smoke coverage,
  Windows manual matrix, coherent durable docs, and no unresolved P2 regression.

## Validation plan

For documentation-only changes that do not modify `src/**`, `tests/**`, scripts,
dependencies, packaging, or runtime files, run only the documentation contract
and diff-scope checks:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_docs_contract.py
git diff --check
git diff --name-only
```

For any subphase that changes source, tests, scripts, dependencies, packaging, or
runtime behavior, run targeted tests first and then the full repository contract
from `docs/QUALITY.md`:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

P2-E adds deterministic performance smoke tests rather than unstable wall-clock
benchmarks as merge gates.

## Manual Windows validation

- P2-0: no new runtime manual check; P1-F manual evidence is not re-verified.
- P2-A: application/window/taskbar icon, Settings dialog, restart-required state,
  reset, persistence, invalid settings recovery, and packaged-resource lookup.
- P2-B: navigation under small budgets, visible/selected protection, oversized
  source behavior, eviction and reload.
- P2-C: folder-pair next-group prediction, normal-load responsiveness, rapid
  navigation, stale preload rejection, and disable/restart behavior.
- P2-D: readable/redacted diagnostics, copy/export, failure summaries, and no UI
  stall when opened.
- P2-E: FHD/UHD and RAW matrix on Windows 10/11 where available.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Settings migration corrupts startup | fresh/saved/legacy/invalid tests | typed validation, schema version, safe defaults, reset |
| Budget accounting is mistaken for total RAM | diagnostics/docs review | narrow scope label and separate cache counters |
| Protected set prevents convergence | low-budget/oversize tests | explicit soft-limit and oversized protected policy |
| Preload starves interactive loads | worker/counter tests | separate bounded ownership and normal-load priority |
| Cancelled work applies later | rapid-navigation tests | request identity plus stale-result rejection |
| Diagnostics leak sensitive data | snapshot redaction tests | basename/relative paths, sanitized errors, no credentials/pixels |
| P2 becomes a MainWindow rewrite | diff/review gate | introduce policy boundaries incrementally |

## Owner decisions

### Required before P2-A

- Canonical PixelScope icon design/asset — **Confirmed:** blue-gray image/scope/
  pixel mark with restrained amber accent; provisional until release naming and
  final P7 branding review.
- Difference-cache default — **Confirmed: 512 MiB**.

### Required before P2-B

- Decoded-source memory budget default — **Pending owner decision**;
  recommendation: 1024 MiB.

### Required before P2-C

- Preload default — **Pending owner decision**; recommendation: Enabled.

Recommendations are not accepted defaults until the owner records a decision.

## Progress log

- 2026-08-06: PR #12 merged at
  `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- 2026-08-07: P2-0 branch created from the same PR #12 merge commit.
- 2026-08-07: P1 workspace plan archived and P2–P7 roadmap transition drafted.
- 2026-08-07: Source contracts for Difference cache, performance settings,
  fixed-count source residency, load tokens, and worker pools reconciled.
- 2026-08-07: Repository owner confirmed the P2-0 documentation checker and docs
  contract test pass locally.
- 2026-08-07: Review feedback corrected current residency protection inputs,
  durable baseline wording, and the Difference-cache default decision.
- 2026-08-07: P2-0 merged as PR #13; P2-A branch created from merge commit
  `52daa63425a286e370aa5ef36f59ba51a8acd565`.
- 2026-08-07: Repository owner selected the provisional blue-gray canonical icon.
  The draft P2-A identity slice added SVG/PNG/ICO assets, package-resource loading,
  Qt bootstrap assignment, and focused asset/icon tests.

## Completion summary placeholder

Fill at P2 completion:

- Delivered behavior:
- Changed files/components:
- Validation results:
- Manual Windows results:
- Performance characterization:
- Remaining limitations:
- Follow-up phases:
- Durable docs updated:

## P2 exit criteria

- Typed settings and persistence are stable, validated, and restart semantics are
  explicit.
- Difference-cache budget is loaded at startup rather than silently defaulted.
- Native decoded-source residency is byte-accounted with protection, eviction,
  reload, and diagnostics.
- One-group-ahead preload is bounded, lower priority than normal load, and rejects
  stale results.
- Diagnostics are deterministic, redacted, cheap to inspect, and consistent with
  runtime state.
- P2 integration passes the full repository contract and the agreed Windows
  characterization matrix.
- No P2 document describes unimplemented P3–P7 work as delivered.
