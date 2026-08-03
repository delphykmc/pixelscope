# PixelScope UI/performance iteration status

## Baseline

- Original iteration baseline: `ea64b1d8fda331e3f85dbfa0181d772974358e74`
- P0-A correction merge: `1606503a08b24b73e77f9fb4784d22c2339d6f59`
- P0-B merge: `b0ee42a9757337947de12eaf7052cae99ee7e527`
- Current work branch: `chatgpt/p0c-toolbar-icons-states`
- Current phase: **P0-C — toolbar icons and states**
- Phase state: **implementation prepared; awaiting local MainWindow patch and Windows review**
- Runtime constraints retained: CPython 3.10, PySide6 6.4.2, and future
  PyInstaller 5.7 `onedir` compatibility.

## Completed in P0-C

### Platform-independent icon factory

- Added a QPainter-based internal icon factory for:
  - Fit
  - 1:1 / actual size
  - Zoom in
  - Zoom out
  - Sync
  - Difference
  - Plots
  - Export
  - Focus pin
- Each icon has explicit normal, checked/active, and disabled pixmaps.
- Icons use PixelScope design-token colors instead of platform
  `QStyle.StandardPixmap` glyphs.
- High-DPI pixmaps are generated at 2x device pixel ratio.
- Generated `QIcon` objects are cached by icon kind.

### Toolbar interaction states

The reviewed MainWindow patch adds:

- Compact toolbar labels while preserving full menu/action text:
  - Fit
  - 1:1
  - Zoom +
  - Zoom −
  - Sync
  - Diff
  - Plots
  - Export
- Fit, 1:1, Zoom In, and Zoom Out disable when no image view is active.
- Sync disables outside a Multi View containing at least two occupied viewers.
- Sync tooltip distinguishes enabled, disabled, and checked states.
- Difference tooltip policy:
  - no current cached map: `Calculate Difference in Analysis first`
  - current pair differs from the calculated result: `Difference is not calculated for the selected pair`
  - cached and hidden: `Show the cached Difference for the selected image pair`
  - visible: `Hide Difference`
- A visible Difference remains enabled so it can always be hidden.
- Plots tooltip changes between Show and Hide according to dock visibility.
- Export disables when the Statistics table has no exportable result.
- Menu and toolbar Export actions share the same availability message.
- Toolbar actions have status tips matching their tooltips.

### Focus pin

- Replaced the tile-header Arrow/Apply platform icons with the internal pin icon.
- The focus pin is checkable and uses the icon's checked-state accent color.
- Focused and non-focused tooltips are explicit.
- Hover, pressed, checked, and disabled toolbar/pin styling is centralized in
  design tokens.

## Files changed or prepared

- `src/pixelscope/ui/toolbar_icons.py`
- `src/pixelscope/ui/design_tokens.py`
- `src/pixelscope/ui/tile_header.py`
- `tests/ui/test_toolbar_icons.py`
- `scripts/apply_p0c_toolbar_patch.py` — temporary reviewed patch helper
- `docs/ui/implementation_status.md`
- `src/pixelscope/app/main_window.py` — modified locally by the patch helper,
  then committed and pushed before review

## Test coverage added

- Every icon kind produces non-null and distinct normal/checked/disabled pixmaps.
- Icon objects are cached.
- Unknown icon kinds fail explicitly.
- Focus pin check state and tooltip changes.
- Main toolbar uses distinct internal icons and compact icon labels.
- Empty, single-image, and multi-image enablement.
- Sync checked/unchecked tooltip state.
- Difference no-cache, visible, cached-hidden, and pair-mismatch tooltips.
- Plots Show/Hide tooltip transition.

## Required local integration

Fetch the branch and apply the deterministic MainWindow patch:

```powershell
git fetch origin
git switch --track origin/chatgpt/p0c-toolbar-icons-states
.\.venv\Scripts\python.exe scripts\apply_p0c_toolbar_patch.py
.\.venv\Scripts\python.exe scripts\apply_p0c_toolbar_patch.py --check
```

Format the affected Python files:

```powershell
.\.venv\Scripts\python.exe -m ruff format `
    src\pixelscope\app\main_window.py `
    src\pixelscope\ui\toolbar_icons.py `
    src\pixelscope\ui\design_tokens.py `
    src\pixelscope\ui\tile_header.py `
    tests\ui\test_toolbar_icons.py `
    scripts\apply_p0c_toolbar_patch.py
```

Run targeted and full validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ui\test_toolbar_icons.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

After the patch succeeds, remove the temporary helper before the final PR:

```powershell
git rm scripts\apply_p0c_toolbar_patch.py
git add src\pixelscope\app\main_window.py src\pixelscope\ui tests\ui docs\ui

git commit -m "Integrate P0-C toolbar icons and states"
git push
```

Manual UI checks:

1. Verify all toolbar glyphs are distinct and aligned at normal Windows scaling.
2. Verify checked Sync, Diff, and Plots icons use the accent state.
3. Verify disabled actions are visibly muted.
4. Verify Fit, 1:1, and Zoom enable only with an active image view.
5. Verify Sync disables in Single View and enables in Multi View.
6. Verify all four Difference tooltip states.
7. Verify focus-pin state in 3-view and 5-view layouts.
8. Verify existing toolbar shortcuts and menu actions remain unchanged.
9. Regenerate and inspect UI captures because the toolbar appears in every main
   window capture.

## Incomplete / intentionally deferred

- P1-A through P1-C: not started.
- Preferences UI and QSettings-backed performance settings remain a separate
  future phase.
- Image resident cache and one-group-ahead preload remain a separate future
  phase.
- GitHub Release update checking and installer workflow remain separate.
- P0-A's internal fixed-arrangement compatibility field/QSettings key remains for
  a later cleanup.

## Exact next starting point

1. Apply and commit the deterministic MainWindow patch locally.
2. Report targeted/full test, Ruff, format, mypy, and visual results.
3. Apply follow-up corrections on `chatgpt/p0c-toolbar-icons-states`.
4. Regenerate toolbar-bearing captures and update capture documentation if needed.
5. Create a ChatGPT-labeled P0-C pull request after validation passes.
6. Merge P0-C, then start **P1-A — Files, Statistics, and responsive tile header**.
