# Memo HTML readability — actual browser audit

Status: active. ChatGPT-assisted. Parent #230. Baseline main e6e2265a.

The preceding document-only PR239 is merged. Continue #230 with actual generated
HTML rather than guessing new functionality. Production save_folder_memo generates
synthetic2/4/6-source reports with two ROIs, long titles/notes/basenames. Existing
owner Memo data is untouched. Source generator stays ignored under temp/.

Chrome browser-use at loopbackHTTP confirmed the2-source report viewport1689px,
documentWidth4760px, note client1100/scroll4465 and figurewidth1192.375. Screenshot
shows offscreen title/note/caption text and horizontal scrollbar. Small fixture
crops are only content/link evidence; they are not large-image visual acceptance.

Bounded fix: wrap long report text without truncating it, constrain figure width.
Preserve note line breaks, CSP/escaping, exact crop PNG bytes/coordinates, CSV paths,
pxmemo map/schema and one Save workflow. No new Export/layout setting/navigation.
Unit contract checks and browser before/after geometry plus actual screenshots are
required. Original file URL was policy-blocked and abandoned; allowed HTTP initially
timed out under sandbox networking, then responded200 from a permitted loopback
server serving ONLY generated synthetic report artifacts. No external publication.

Focused command: `.venv/Scripts/python -m pytest -q --tb=short
tests/unit/test_memo_report.py tests/unit/test_memo_archive.py
tests/unit/test_memo_folder.py --junitxml=temp/memo-html-readability-20261117.xml`:
**45 passed10.60s**. New unit contract retains complete long text/linebreaks,
escaped markup and all crop files. Browser measurements supply the layout proof,
rather than equating CSS string checks with rendered correctness.

After actualChrome default1689px: document1674px (verticalscrollbar), no note
overflow;2/4/6-source large fixtures load4/8/12 PNGs respectively. Two CSV links
are present per report from synthetic frozen Statistics contexts. Crop pixels,
CSV values and colour data are synthetic fixtures, not algorithm/IQA acceptance.
At960px viewport document945px, no note overflow and640px crops retain width.
Viewport override reset. Paired tiny-crop screenshots compare the same long-text
conditions; after additionally includes CSV links. Large-crop views are extra
after evidence, not falsely paired to tiny baseline images.

Initial temporary fixture with inconsistent source metadata was correctly rejected;
fixed fixture now agrees with the source signatures/ROI shape. This was not a
product save failure. No permanent capture framework, extra report settings or
dependencies added. Original source/template CSS unchanged except two layout rules.
