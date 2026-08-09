# PixelScope current state

Snapshot date: 2026-08-09
Current merged baseline / P3-C PR #25 merge commit:
`7f6bef73e6712f6a14a4d401820a915196e25da2`

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 through P2-F completed as PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3-0 merged as PR #21.
- P3-A Difference Gray/mixed-bit support merged as PR #22.
- P3 roadmap replanning merged as PR #23.
- P3-B RAW Native & Display Semantics merged as PR #24.
- P3-C Display Gain generalization merged as PR #25 at the baseline SHA above.

The active plan is [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).
P3-D is **Unified Image Opening & RAW Profile Resolution**. The earlier speculative
Profile Library/suggestion scope is deferred.

## Workspace ownership model

P3-D distinguishes four states:

```text
Registered
    ↓ user selection
Selected
    ↓ viewer capacity / layout
Presented
    ↓ source lifecycle
Resident when required
```

- **Registered**: known to the Files workspace/catalog. No artificial six-item limit.
- **Selected**: chosen as the current comparison/analysis set.
- **Presented**: occupying viewer tiles. Multi View remains bounded by the existing
  one-to-six-tile presentation contract.
- **Resident**: decoded native source held under the separate P2 source-residency
  budget.

Registration count, selection count, presentation capacity, and resident-source
ownership are independent concerns.

## Unified input policy

Supported image inputs are exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The image picker filter is:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

### Open Images...

Selection-oriented input:

- multi-file selection is supported;
- all supported selected files are registered;
- registered direct files become the current selection;
- viewer presentation remains bounded by existing layout capacity rather than by
  registration count;
- ordinary and RAW files share this command;
- RAW follows the existing profile-resolution contract before direct-open
  registration.

There is no separate **Open RAW with Profile...** action.

### Open Folders...

Registration-oriented input:

- multiple existing directories may be selected in one Qt-only dialog;
- resolved directory paths are deduplicated and ordered deterministically;
- practical folder count is not limited to six;
- supported immediate contents are registered in Files;
- current selection and presentation do not change;
- no first image is automatically selected;
- no two-folder comparison group is created implicitly;
- empty/no-supported-image folders are skipped and reported compactly.

Folder-only registration preserves layout, active/focus document, ROI, Line
Profile selection, Difference presentation/cache, Display Gain, existing view
state, and source-residency ownership because it does not invoke the selection or
render lifecycle.

### Drag and drop

- dropped image files are registration + selection oriented, like Open Images;
- dropped folders are registration-only, like Open Folders;
- any folder count uses the same policy; there is no exactly-two-folder special case;
- mixed file + folder drop preserves both intents: explicit files become the
  selection while folder contents remain registered-only.

Unsupported files and standalone `.json` sidecars never become image documents.

## Registered but unselected state

`registered documents > 0` with `selected documents == 0` is a supported state.
The central workspace displays **Select an image from Files to view**. A truly
empty workspace instead displays **Drop images or folders here** with Open Images
and Open Folders actions.

## RAW registration boundary

Direct RAW open/drop preserves the P3-D contract:

- exact same-basename sidecar → parse/validate under confirmation and exact/minimum
  size policy;
- no sidecar → editable RAW Profile dialog;
- invalid sidecar → warning then editable fallback;
- cancel → no erroneous direct-open RAW registration;
- multiple RAW files resolve independently.

Folder registration is lazy for RAW. The RAW path and deterministic same-basename
sidecar path can be registered as a pending document without showing a dialog or
decoding source. Profile resolution occurs when foreground selection/loading
actually requires the RAW. Unresolved RAW is excluded from speculative preload
until a profile is resolved. No profile is inferred from file size or other weak
evidence.

The RAW dialog uses **Load Profile...** / **Save Profile...** terminology. P3-D
adds no global Profile Library, profile CRUD manager, last-profile reuse,
apply-to-all behavior, size-only/fuzzy matching, sensor/Bayer inference, or
Black/White estimation.

## Navigation and analysis baseline

- PageUp/PageDown Folder Position operates only on one-to-six currently selected
  documents from distinct folders. Other registered folders do not participate.
- Left/Right navigates the selected set; Up/Down remains Files-tree navigation.
- ROI uses Ctrl+drag / Esc; Line Profile uses Shift+drag / Shift+Esc.
- Statistics, Histogram, Line Profile, Difference, Split Channels, and pixel
  inspection consume native source semantics rather than gained preview pixels.
- Difference supports Gray, RGB/RGBA, and same-CFA Bayer with native/normalized
  domain rules established by P3-A.

## RAW and Display Gain baseline

Current RAW support includes unpacked uint8/uint16, MIPI RAW10/12/14, stride,
offset, endian/alignment, Gray/Bayer layout, JSON migration, same-path reload,
exact/minimum-size policy, and Black/White metadata.

Display Gain remains presentation-only:

```text
display = anchor + gain * (source - anchor)
```

- choices: 1×/2×/4×/8×/16×;
- ordinary Gray/RGB uses anchor 0;
- RGBA gains RGB only and preserves alpha;
- RAW 1× uses native effective full scale;
- RAW gain >1 uses `B + G * (X - B)` with existing Gray/Bayer Black rules;
- 1× reuses canonical preview;
- gain changes do not mutate source, analysis results, residency, or Difference.

## Runtime/settings baseline

Settings schema remains version 5. P3-D adds no settings/schema migration and no
Settings-owned RAW profile collection. Source residency remains exact native
`source.nbytes` under protected soft-budget LRU semantics. Difference cache remains
independent. Preload remains +1 Folder Position, max-one dedicated worker, with
running-preload promotion as established by P2. Diagnostics remain deterministic,
bounded, sanitized, and observation-only.

## Active P3 sequence

1. P3-A — Difference Gray / Mixed Bit-Depth Support — Complete — PR #22
2. P3-B — RAW Native & Display Semantics — Complete — PR #24
3. P3-C — Display Gain Extension — Complete — PR #25
4. P3-D — Unified Image Opening & RAW Profile Resolution — In progress
5. P3-E — Integration & Hardening

## P3-D validation state

P3-D tests cover unified menu/filter behavior, Open Images multi-selection and
>6 registration, Open Folders multi-directory registration/deduplication, folder
and image D&D intent, mixed drop, registered-but-unselected state, lazy RAW
profile resolution, Folder Position isolation to selected folders, and
registration-only preservation of selection/view/layout/ROI/Line Profile/
Difference/Display Gain/residency/cache state.

The Chat implementation agent does not run the Windows `.venv` validation suite.
Owner/local Windows validation is required before merge; no P3-D PASS claim is
recorded here.
