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
