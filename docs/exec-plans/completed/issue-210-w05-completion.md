# W05 completion and merge-readiness plan

Status: Complete — implementation, independent review and merge preparation; no merge.
Owner: ChatGPT-assisted orchestration. PR: https://github.com/delphykmc/pixelscope/pull/218
Baseline: `7f77f4b2f4a79a46e6ec054babcb86948b55e6c9`, main
`f7145f9ac7302816587c272b600e0861c32789cf`. Updated: 2026-11-05.

## Observable goal and scope

Complete Workspace, Original 2, Original 4, A/B/Diff and Diff Focus with exact
runtime A/B identities, canonical Presented/Active/Files/action state and source
Primary/Pick/page behavior. Preserve per-source physical zoom/center with Sync
off, including hidden sources, without inventing durable Review UUIDs or adding
source/residency authority. Difference remains explicit Calculate or valid cache
reuse; preset/role changes cannot authorize a frozen metrics export.

No Wipe/Blend, Review persistence, Session schema change, packaging, or merge.
After implementation, focused/full native Windows validation and independent
exact-head review, publish results and prepare PR for merge. Only then fulfill
the user's explicit system-sleep request.

## Initial independent audit and implementation slices

1. Replace the controller's post-render viewer overlay with a typed MainWindow
   comparison-plan seam. Canonical rendering owns actual display documents,
   capacity, Active, Files state, native loading and six-source page protection.
2. Extend existing live view-state capture/restore with source object/generation/
   reference-shape verified physical viewports. Retain hidden-source geometry
   only within the unchanged current page; revoke on source/context changes.
3. Exercise real Difference workers and permission revocation; add navigation,
   Sync off/toggle, page2, Primary/Pick, resize and shutdown regressions.
4. Narrow cumulative Product/Architecture/guide updates, static gates, focused
   tests, clean-HEAD full Windows pytest with normal GC and outside-Git temp root.
5. Independent read-only exact-head review, remediation/re-review, evidence and
   ready-for-review PR state. No automatic approval or merge.

## Risks / evidence boundary

Live viewport records are not durable source bindings or numerical snapshots.
Never restore after generation/object/shape mismatch, schedule an unguarded late
restore, retain QWidget ownership cycles, or revive an obsolete Difference map.
Report physical multi-DPI/manual hardware limitations separately. Keep temporary
probes/logs in ignored `temp/w05-completion-20261105/`.

## Implementation and observed evidence

- Canonical typed plan rendering replaces the provisional overlay. Presented IDs,
  capacity, Active/Files state, six-source protection and existing source-only T,
  navigation/Primary/Pick now share the MainWindow render path.
- `PresetViewState` uses weak live source bindings and W01 physical measurement,
  existing W04 epochs/checkpoint rollback, explicit input/zoom/Sync/close revocation
  and no durable UUID. Shared Sync anchors include newly visible tiles; Sync-Off
  retained records include hidden page sources and the Single viewer.
- Independent audit findings addressed: Single-to-preset bookkeeping, independent
  view continuity, all-tile Sync anchor, >6 Selected navigation, explicit Single
  zoom authority and actionable derived Primary. Independent final review passed
  on code commit `b45a28f41fb2e27fdcea34dbf35e13aa910cf147`.
- Inherited unit/UI test basenames collided under default pytest collection;
  unit module renamed to `test_comparison_presets_contract.py` without test removal.
- Expanded native focused slice: **112 passed in 42.79s**, including W05/W04/W01,
  workspace/Difference and Session restore. Log emitted Windows COM diagnostic
  `0x8001010d` while pytest-qt processed events; process completed, exit 0. This
  diagnostic is retained, not suppressed or claimed fixed.
- Actual Windows UI, DPR 1.0, synthetic six-source images: Sync Off → Original 2,
  1:1 and independent pan → Workspace. Returned source centers were (895,500)
  and (960,540), both 100%; four hidden sources retained ~19.5869% and (960,540).
  Selected/Page remained six and Presented changed 6→2→6. Program closed normally.
  This manual session predates the final additional Single zoom/derived Primary
  fixes, which are covered by subsequent automated tests; final whole-suite and
  static evidence will be recorded separately. Other physical DPI/hardware not run.

## Terminal acceptance and handoff

Clean code HEAD `b45a28f41fb2e27fdcea34dbf35e13aa910cf147`, Windows CPython
3.10.11 / PySide6 6.4.2, normal automatic GC:

```powershell
python -u -m pytest -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/pixelscope-w05-full-20261105 --junitxml=../full.xml
```

**1846 passed, 1 warning in 494.26s**, exit 0; XML reports no failures/errors/skips.
The warning is the intentional duplicate ZIP member in a tampering test. The COM
diagnostic noted above recurred; no exception suppression, test exclusion or
timeout increase was used, and its cause is not claimed fixed.

Ruff lint/diff checks exit 0; formatter checks 380 files; mypy checks 122 source
files; documentation and dependency checks pass. Exact-code-head hosted runs
41874974842 (change-scoped), 41874974918 (guide) and 41874974788 (pinned screenshot)
all succeeded. Hosted checks do not replace the full native result.

Independent read-only review rechecked source/call sites/contracts/tests and read
the primary full/focused/XML/static/native records: **PASS, no actionable finding**
on the code SHA above. No self-approval or merge is implied. This completion-record
follow-up changes documentation only; preserve the tested code SHA when reporting
validation rather than claiming an unexecuted full rerun on the document commit.

W06 may adopt `install_comparison_preset_controls` after W05 is actually merged;
its signal/role semantics and stable object names remain owned by W05 until then.
W09 remains responsible for durable source verification and restore transactions;
these weak runtime viewport records must not be serialized as verified source IDs.
Session v1, Wipe/Blend, packaging and other physical DPI/monitor tests are excluded.
All follow-up commits carry the ChatGPT co-author trailer; PR evidence is explicitly
ChatGPT-assisted. The user's requested outcome is ready-for-review, **not merge**.
