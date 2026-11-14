# Memo compact ROI labels

Status: active. ChatGPT-assisted. Issue #235, parent #230.

Observed production captures under temp/ui03-memo-audit show long titles overlap
and clip at tile edges. First bounded slice: Viewer outlines display ROI ordinal
only; complete editable title stays in the Memo list/editor and saved evidence.
No mode/settings, source matching, numerical work or ROI-coordinate changes.
This removes unbounded title width; nearby ordinal collisions and edge placement
still require separate visual verification rather than claiming total resolution.
Keep native clipboard/merge hold separate. Existing owner files remain untouched.

Observed: tests/ui/test_memo_roi_workflow.py plus test_memo_chrome.py:
7 passed10.16s, XML temp/memo-compact-labels-20261115.xml. Ruff check/format2files,
mypy134, docs contract and diff checks passed. No full validation or merge claimed.

## Collision placement follow-up

Owner requested compact typography and labels moved below or beside their ROI
when they collide. ImageViewer places labels in logical scene pixels, tries the
original corner then bottom/right/left/top, clamps to the visible view, and lazily
searches remaining visible space only if those candidates collide. Font is8pt,
normal weight with1px document margin. Rectangles, ROI records and analysis stay
unchanged. Range changes and existing geometry settling reposition labels; the
class-native signal connection is explicitly disconnected at disposal.

When the viewport cannot physically fit all labels, the bounded search retains
labels at the least-overlapping candidate instead of hiding records or looping.
This is a physical space limitation, not a universal non-overlap guarantee.
Total rectangle-intersection work is capped at8192 per relayout; if packing
exhausts that budget, retain the best tested/clamped candidate. Offscreen ROI
labels are hidden until their rectangles re-enter the viewport, avoiding orphan
badges over unrelated image pixels. Dense80-label regression injects a32-check
budget and verifies its operation count, rather than a wall-clock threshold.
No new worker, timer, global cache or QObject backreference is introduced.
The new placement regression covers adjacent/edge ROIs, zoom, resize and cleanup
at two sizes, preserving rectangle/source identity. Owner requested12hour sleep
after completion; no merge or unlocked clipboard acceptance is implied.

Observed final command: `.venv/Scripts/python -m pytest -q --tb=short
tests/ui/test_memo_label_placement.py tests/ui/test_memo_roi_workflow.py
tests/ui/test_memo_chrome.py tests/ui/test_w01_physical_zoom.py
tests/ui/test_issue81_qt_lifecycle.py tests/ui/test_issue121_qt_gc_lifecycle.py
tests/unit/test_qt_lifecycle_architecture.py
--junitxml=temp/memo-placement-final-20261115.xml`: **54 passed25.53s**.
Source/tests Ruff check passed, changed-files format passed, mypy134 passed,
docs contract/strict MkDocs and diff check passed. New full pytest is not claimed.
Production Qt dock/float snapshots follow; owner untracked files remain intact.

Final review fixes: bounded dense search and offscreen hide/return. The same
focused command now reports **55 passed22.49s**, including the new dense budget
regression. Independent working-diff re-review accepted both fixes. A viewport
smaller than one label cannot fully contain its text; that physical limit and
budget-exhaustion overlap are retained as explicit constraints. Ruff source/tests,
mypy134 and docs/diff checks passed again. Exact-commit capture/review follows.
