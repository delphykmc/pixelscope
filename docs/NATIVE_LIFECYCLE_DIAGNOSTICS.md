# Native lifecycle crash diagnostic playbook

This runbook is for nondeterministic native crashes in the Windows Qt/PySide6/pyqtgraph
stack, especially access violations, heap corruption, stale-wrapper failures, or crashes
whose apparent failing test moves between full-suite runs.

It captures the diagnostic approach established while investigating Issue #81 and the
Issue #121 Slice 4 regression. The goal is to distinguish a functional regression from
an accumulated lifetime/destruction-order defect without changing the very GC timing
being investigated.

## Core principle

Start with the least intrusive observation possible. Native lifecycle failures are timing
sensitive: object enumeration, explicit collection, Qt object inspection, `repr()` on
stale wrappers, or repeated deep probes can move the crash and create misleading
causality.

Do not assume that the last test on the stack is the root cause. Treat it first as the
place where accumulated lifetime damage became observable.

## Initial triage sequence

Use the following order unless evidence strongly requires a different path.

### 1. Reproduce under normal GC

Run the ordinary owner/local Windows suite first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For localization, add only lightweight test-boundary logging or `-vv`. Record:

- exact exit code / Windows exception (`0xC0000374`, access violation, and similar);
- native/Python stack at detection;
- last started and last completed test;
- whether the failing test/index changes between runs; and
- whether the crash occurs during the suite or only at interpreter/process teardown.

A moving crash location with a similar Qt/pyqtgraph stack is evidence for accumulated
state or lifetime ordering, not proof that every reported test is independently broken.

### 2. Run a GC-disable A/B test

As a diagnostic only, rerun the same workload with Python automatic cyclic GC disabled.
Do not make this a production fix.

Interpretation:

- normal GC crashes, but GC-disabled completes the test workload: cyclic-GC destruction
  timing is a strong trigger candidate;
- the crash moves from mid-suite to final process teardown: retained Qt/Python wrapper
  graphs are likely surviving until shutdown, strengthening the lifetime hypothesis;
- GC-disabled still crashes at the same point: prioritize object-hierarchy corruption,
  use-after-free, worker/thread ownership, or another non-GC trigger.

`gc.disable()` proves neither a memory leak nor a specific bad cycle. It changes when
cyclic objects are reclaimed and is therefore an A/B discriminator only.

### 3. Run the passive natural-GC timeline

When GC timing is implicated, prefer the committed low-intrusion observer before any
deep heap inspection:

```powershell
.\.venv\Scripts\python.exe -m scripts.diagnose_gc_passive -q
```

Default outputs:

```text
temp/gc_passive.tsv
temp/gc_passive_summary.txt
temp/gc_passive_fatal.log
```

The passive probe intentionally does **not** call:

- `gc.collect()`;
- `gc.get_objects()`;
- `gc.get_referrers()`;
- `gc.DEBUG_SAVEALL`; or
- Qt object/tree APIs.

It observes existing `gc.callbacks` stop events and associates natural collection bursts
with the current pytest test index/nodeid.

Read the result as a timeline, not as a leak detector. Useful questions are:

- Does generation-2 collection pressure grow monotonically as the suite progresses?
- Are large generation-2 bursts concentrated after a particular test family?
- Does pressure fall again after cleanup, or does each later window retain more?
- Does the suite still complete under normal GC?

A large single `collected` value is not automatically a defect. A bounded burst that is
successfully reclaimed can be normal. Progressive growth or repeated native-sensitive
bursts are more important than the absolute number.

Also check whether a test intentionally calls `gc.collect()`: the passive observer does
not force collection itself, but it will still report explicit collections initiated by
test code.

### 4. Deep-inspect one fresh-process checkpoint

Only after the passive timeline identifies a useful boundary, run a new process from
suite start to a checkpoint immediately before the suspect region.

At that checkpoint, and only once per process:

1. enable `gc.DEBUG_SAVEALL`;
2. call one full `gc.collect()`;
3. inspect only the newly appended `gc.garbage` objects;
4. build a referent graph with `gc.get_referents()`;
5. compute strongly connected components (SCCs);
6. aggregate repeated SCC signatures by type; and
7. print representative edges, including dictionary attribute names where possible.

Exit after the checkpoint analysis. Do not continue the UI suite after a deep probe,
because the probe deliberately changes lifetime state.

Important interpretation:

- objects added to `gc.garbage` under `DEBUG_SAVEALL` are *collectible cyclic garbage
  preserved for inspection*; they are not automatically uncollectable leaks;
- a small SCC can retain a large downstream Qt subtree, so SCC topology is usually more
  useful than the raw garbage-object count;
- prioritize PixelScope-owned edges and bound callbacks over third-party cycles that may
  be normal when destroyed safely.

Examples of high-value signatures found during the Issue #81 / #121 investigation were:

```text
QDockWidget -> PlotsDockTitleBar -> QDockWidget
LineProfilePanel -> callback/partial -> bound method -> LineProfilePanel
ViewBox -> LegendItem -> GraphicsWidgetAnchor parent -> ViewBox
```

The first two identified explicit PixelScope strong-reference ownership cycles. The
third exposed a pyqtgraph wrapper graph whose destruction needed to be made
deterministic while the native graphics hierarchy was still valid.

### 5. Compare before/after fixes using the same checkpoint

After a lifecycle fix, repeat the **same** checkpoint and compare signatures rather than
chasing the smallest possible total garbage count.

Preferred evidence:

- the targeted production-owned SCC disappears;
- the targeted Qt/pyqtgraph SCC disappears or is deterministically detached before GC;
- downstream garbage falls materially when that cycle previously retained a subtree;
- focused lifecycle regression tests pass with automatic GC enabled; and
- the ordinary full suite passes with automatic GC enabled.

For Issue #121 Slice 4, the cp300 comparison was particularly useful: after removing the
identified ownership cycles, the deep-checkpoint garbage population fell from roughly
7.4k to 1.5k objects and the targeted lifecycle SCC families disappeared. The exact
counts are historical evidence, not future pass/fail thresholds.

## How to narrow a boundary

If a deep checkpoint is still required, use prefix search rather than isolated middle
chunks. Each diagnostic run should start from test #1 so accumulated lifetime behavior
is preserved.

A coarse sequence such as 50 / 100 / 150 / 200 / 250 / 300 can establish whether a
cycle exists early or appears after a transition. Binary-search only an actual
transition. Do not keep subdividing when the same cycle exists from the earliest
checkpoint and its counts are non-monotonic; that usually means natural automatic GC is
reclaiming it at varying times rather than one test introducing a simple monotonic
leak.

## What not to do first

Avoid these as initial probes:

- periodic `gc.get_objects()` censuses throughout the suite;
- repeated `gc.collect()` calls between tests;
- `gc.DEBUG_SAVEALL` for the entire full-suite run;
- periodic traversal of `QApplication.topLevelWidgets()` or Qt child trees;
- `repr()` / property access on wrappers that may already refer to deleted C++ objects;
- `gc.get_referrers()` without aggressively excluding diagnostic frames/locals;
- disabling GC as a permanent workaround;
- attributing a native crash to the test shown in the fatal stack without prefix/A-B
  evidence; or
- fixing third-party SCCs blindly just because they are cycles.

These probes either perturb destruction timing, retain objects themselves, risk touching
stale native wrappers, or conflate collectible cycles with leaks.

## Fix patterns to prefer

When evidence identifies a lifetime defect, prefer deterministic ownership changes over
GC policy changes:

- break Python strong back-references when Qt parent ownership already defines lifetime;
- use weak-owner callbacks where a signal callback would otherwise retain its owner;
- disconnect callbacks before owner/native graph destruction;
- explicitly detach third-party graphics anchors/back-references before native teardown;
- make shutdown idempotent;
- drain `QEvent.DeferredDelete` at test boundaries where the production close path has
  already requested affinity-safe deferred deletion; and
- preserve normal automatic GC for final validation.

The acceptance criterion is not "zero Python cycles". The criterion is that PixelScope
ownership is bounded and Qt-native destruction remains safe regardless of when normal
Python cyclic GC runs.

## Recommended evidence bundle

For a future Issue #81-style incident, attach or record:

1. normal-GC full-suite result and fatal stack;
2. GC-disable A/B result;
3. `gc_passive_summary.txt`;
4. one or two targeted SCC checkpoint reports around the identified boundary;
5. before/after SCC signatures for the fix;
6. focused lifecycle regression command/result; and
7. final ordinary GC-enabled full-suite result.

This bundle is usually more informative than repeated full heap dumps and is much less
likely to alter the native failure being diagnosed.
