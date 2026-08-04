# PixelScope UI/performance iteration status

## Baseline

- Original iteration baseline: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- P0-A correction merge: `1606503a08b24b73e77f9fb4784d22c2339d6f59`
- P0-B merge: `b0ee42a9757337947de12eaf7052cae99ee7e527`
- P0-C merge: `494cab1a49da1efeaa970fc605029e1eda80e3b8`
- Current work branch: `chatgpt/p0d-split-toolbar-diff-order`
- Current phase: **P0-D — split-channel continuity, disabled menu states, and Difference ordering**
- Phase state: **implementation prepared; awaiting local MainWindow patch and Windows review**
- Runtime constraints retained: CPython 3.10, PySide6 6.4.2, and future
  PyInstaller 5.7 `onedir` compatibility.

## P0-D goals

1. Avoid briefly displaying the unsplit source image when a newly selected image
   is loading while Split Channels remains enabled.
2. Make unavailable View-menu commands visibly muted without losing their
   check/icon state.
3. Add Split Channels to the main toolbar.
4. Place a newly calculated Difference first in Multi View, while retaining
   source order followed by Diff in Single View and opening Diff immediately.

## Prepared P0-D implementation

### Split-channel loading continuity

- Split mode now enters its channel layout whenever one image is selected, even
  while the selected image is still loading.
- While pixels are unavailable, the channel grid uses stable loading placeholders
  instead of first showing the unsplit pending document.
- Standard image placeholders use R/G/B labels.
- Bayer placeholders use R/Gr/Gb/B when a RAW profile identifies Bayer layout.
- When loading completes, placeholders are replaced directly by cached real
  channel documents.
- If a loaded document cannot be split, the original document is shown instead
  of leaving an empty workspace.
- Split checked state remains preserved when the command is temporarily
  unavailable, such as during loading or multi-selection.

### View-menu and toolbar states

- Added internal `split_channels` and `dock` icons with normal, checked, and
  disabled states.
- Split Channels uses one shared checkable `QAction` in both the View menu and the
  main toolbar, so menu and toolbar state cannot diverge.
- Dock Plots receives its own internal icon.
- Disabled menu text uses an explicit design-token color.
- The disabled palette now sets WindowText in addition to Text and ButtonText,
  covering menu implementations that read different palette roles.
- Split Channels tooltips distinguish:
  - available and off
  - available and checked
  - loading
  - wrong selection count
  - unsupported image layout

### Difference display ordering

- A newly calculated Difference is promoted to the first Multi View position for
  all supported source counts below the six-source forced-single case.
- Difference becomes the focus document after calculation in Multi View.
- Cached Difference toggled on in Multi View is also promoted first.
- Visible-focus cycling uses the same Difference-first order.
- Calculating Difference while already in Single View keeps Single View active,
  opens Diff immediately, and preserves navigation order:
  `1, 2, 3, ..., Diff`.
- Toggling a cached Difference on while in Single View also opens Diff without
  forcing Multi View.
- Six sources plus Difference continues to use the existing forced Single View
  and workspace restore behavior.

## Files changed or prepared

- `src/pixelscope/ui/toolbar_icons.py`
- `src/pixelscope/ui/design_tokens.py`
- `tests/ui/test_toolbar_icons.py`
- `tests/ui/test_p0d_workspace_behavior.py`
- `scripts/apply_p0d_workspace_patch.py` — temporary reviewed patch helper
- `docs/ui/implementation_status.md`
- `src/pixelscope/app/main_window.py` — modified locally by the patch helper,
  then committed and pushed before review

## Test coverage prepared

- Split Channels and Dock icon interaction states.
- Split toolbar action compact label and shared menu action.
- Disabled menu text palette and retained icons.
- Split checked-state persistence while temporarily unavailable.
- Loading placeholders prevent an intermediate unsplit render.
- Placeholders transition directly to R/G/B channel documents after loading.
- Newly calculated Difference is first for 3-source and 5-source Multi View.
- Single View calculation stays single, opens Diff, and exposes navigation order
  `1, 2, 3, Diff`.
- Cached Diff hide/show in Single View does not switch layout mode.

## Required local integration

Fetch the branch and apply the deterministic MainWindow patch:

```powershell
git fetch origin
git switch --track origin/chatgpt/p0d-split-toolbar-diff-order
.\.venv\Scripts\python.exe scripts\apply_p0d_workspace_patch.py
.\.venv\Scripts\python.exe scripts\apply_p0d_workspace_patch.py --check
```

Format the affected files:

```powershell
.\.venv\Scripts\python.exe -m ruff format `
    src\pixelscope\app\main_window.py `
    src\pixelscope\ui\toolbar_icons.py `
    src\pixelscope\ui\design_tokens.py `
    tests\ui\test_toolbar_icons.py `
    tests\ui\test_p0d_workspace_behavior.py `
    scripts\apply_p0d_workspace_patch.py
```

Run targeted validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ui\test_toolbar_icons.py -q
.\.venv\Scripts\python.exe -m pytest tests\ui\test_p0d_workspace_behavior.py -q
```

Run full validation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

After validation, remove the temporary patch helper before the final PR:

```powershell
git rm scripts\apply_p0d_workspace_patch.py
git add src\pixelscope\app\main_window.py src\pixelscope\ui tests\ui docs\ui

git commit -m "Integrate P0-D split and Difference workspace behavior"
git push
```

## Manual UI checks

1. Enable Split Channels on one RGB image, then select another unloaded image.
   Confirm the workspace immediately remains in a channel-grid loading state and
   never flashes the unsplit source tile.
2. Confirm R/G/B or R/Gr/Gb/B channel views replace the loading placeholders once.
3. Select two images while Split remains checked. Confirm Split becomes visibly
   gray in both menu and toolbar but retains its checked icon state.
4. Return to one supported image. Confirm Split re-enables in the prior checked
   state.
5. Confirm Dock Plots is visibly gray while the plot dock is not floating and
   enables when the dock floats.
6. Calculate Difference in 3-source and 5-source Multi View. Confirm Diff is the
   first tile.
7. Calculate Difference in Single View. Confirm the displayed image is Diff and
   navigation remains sources first, Diff last.
8. Hide and show cached Diff in Single View. Confirm the layout remains Single.
9. Recheck six-source Difference hide/restore behavior.

## Incomplete / intentionally deferred

- P1-A through P1-C: not started.
- Preferences UI and QSettings-backed performance settings remain separate.
- Image resident cache and one-group-ahead preload remain separate.
- GitHub Release update checking and installer workflow remain separate.
- P0-A's internal fixed-arrangement compatibility field/QSettings key remains for
  later cleanup.

## Exact next starting point

1. Apply and commit the deterministic P0-D MainWindow patch locally.
2. Report targeted/full test, Ruff, format, mypy, and visual results.
3. Apply follow-up corrections on `chatgpt/p0d-split-toolbar-diff-order`.
4. Remove the temporary patch helper.
5. Create a `[ChatGPT-assisted]` P0-D pull request after validation passes.
6. Merge P0-D, then start **P1-A — Files, Statistics, and responsive tile header**.
