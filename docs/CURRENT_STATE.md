# PixelScope current state

Snapshot date: 2026-08-09
Current merged baseline / P3-C PR #25 merge commit:
`7f6bef73e6712f6a14a4d401820a915196e25da2`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 through P2-F completed as PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3-0 roadmap transition merged as PR #21 at
  `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.
- P3-A Difference Gray/mixed-bit support merged as PR #22 at
  `769588bf869847da844cfc0b77c008023d8b048b`.
- P3 roadmap replanning merged as PR #23 at
  `4c7d1bbbb4476134f76a204578098d35a03feca2`.
- P3-B RAW Native & Display Semantics merged as PR #24 at
  `1817490a08c61da9087efe9c3c6afd8bd85838f0`.
- P3-C Display Gain generalization merged as PR #25 at
  `7f6bef73e6712f6a14a4d401820a915196e25da2`.

P2 — Runtime Foundation, Settings & Performance is complete. Its historical plan
is retained at
[`exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

The active plan is
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md) for
**P3 — Image Semantics & RAW Processing**. P3-A/P3-B/P3-C are merged; P3-D is
**Unified Image Opening & RAW Profile Resolution**. The earlier speculative global
Profile Library/suggestion scope is no longer authoritative.

## Current product baseline

### Workspace and navigation

- Folder-grouped Files tree with pending/loading/resident/error state.
- Ordered selection is the comparison model; Difference owns its selected pair.
- Fixed one-to-six-image Multi View geometry with primary-image behavior.
- PageUp/PageDown atomically moves one-to-six registered distinct folders by one
  Folder Position using the same pure planner that predicts preload targets.
- Left/Right moves through the selected-image set; Up/Down remains native Files
  tree navigation.
- Files-tree `+` / `-` retains Qt-native expand/collapse behavior. Display Gain
  `+` / `-` is scoped to the image-presentation subtree.
- ROI uses Ctrl+drag and Esc; Line Profile uses Shift+drag and Shift+Esc.
- Plots floating geometry, selected tab, and workspace state persist separately
  from application settings.

### Unified image opening

P3-D establishes one top-level file-open entry point:

```text
Open Images...  -> .png .bmp .jpg .jpeg .raw
Open Folder...  -> folder discovery of the same supported family
```

There is no separate **Open RAW with Profile...** command and no Empty Workspace
RAW-open button/signal. `Ctrl+O` remains Open Images; `Ctrl+Shift+O` remains Open
Folder. The picker filter is exactly:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

The supported extension contract is owned by `io.path_discovery`. Unsupported
extensions and `.json` files do not become image entries and are not treated as
RAW.

`ImageInput` remains the common registration input for Open Images, Open Folder,
drag/drop, folder discovery/registration, Folder Position workflows, preload,
reload, and sidecar-reload identity. Ordinary PNG/BMP/JPEG bypass RAW profile UI.
RAW remains conditionally profile-resolved before registration:

- exact same-basename `.json` sidecar → parse/validate and preserve current
  confirmation plus exact/minimum-size policy;
- no sidecar → editable RAW Profile dialog;
- invalid sidecar → warning followed by editable fallback;
- cancel → no erroneous RAW document registration;
- multiple RAW files → each file resolves its own sidecar/profile independently.

The RAW dialog uses **Load Profile...** / **Save Profile...** user terminology;
JSON remains the compatible storage format. P3-D adds no last-profile reuse,
apply-to-all profile UI, size-only/fuzzy matching, global profile library, profile
CRUD manager, sensor/Bayer inference, or Black/White estimation.

### Analysis

- Full-image and Active ROI Statistics.
- Histogram Auto/256/1024/4096 bins and Count/Normalized/Log count modes.
- Statistics/Histogram identical numerical requests are idempotent across
  scheduled, running, and completed states when source identity/generation,
  layout/Bayer semantics, ROI, and histogram specification are unchanged.
- Line Profile supports absolute, normalized, and Difference-from-reference
  modes with primary→active→first-displayed reference priority.
- Difference supports Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA
  Bayer ↔ Bayer, with explicit native/normalized domains, byte-budgeted cache,
  threshold/gain display controls, mask, metrics, and reversed-pair reuse.
- Split Channels keeps native RGB/Bayer component semantics.

### Difference semantics

P3-A establishes the production Difference contract:

- Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA Bayer ↔ Bayer are supported;
- cross-family, size-mismatch, CFA-mismatch, and unsupported layouts are rejected;
- equal effective bit depths retain compact native code-domain Difference with
  full scale `(1 << bit_depth) - 1`;
- mixed effective bit depths independently normalize each native source by its
  own effective full scale, produce canonical float32 absolute maps in `[0,1]`,
  and use `%FS` threshold semantics;
- RAW Black/White levels, Display Gain, `DisplayTransform`, preview values,
  demosaic output, and implicit RGB→Gray conversion do not participate.

Settings schema remains v5. Persisted `difference_threshold` is the native code
threshold default; normalized threshold is session-local.

### RAW and Display Gain boundary

Current RAW support includes unpacked uint8/uint16, MIPI RAW10/12/14, stride/
offset/endian/alignment, Gray/Bayer layout, JSON profile migration, same-path
reload, exact/minimum-size policy, and Black/White metadata.

Decoded `ImageDocument.source` is authoritative. Pixel inspection, Statistics,
Histogram, Line Profile, Split Channels, Difference, and source residency consume
native source data rather than gained preview pixels.

P3-B/P3-C establish one generic presentation model:

```text
display = anchor + gain * (source - anchor)
```

- application-session Display Gain choices are 1×/2×/4×/8×/16×;
- ordinary Gray/RGB and ordinary RGB split channels use `anchor=0`;
- RGBA gains RGB only and preserves canonical 1× alpha;
- RAW 1× maps effective native full scale without subtracting Black or using White
  as display maximum;
- RAW gain >1 is `B + G * (X - B)` with existing Gray/Bayer Black-anchor rules;
- Bayer channel-specific Black processing uses parity-plane views rather than a
  full-frame Black map;
- gain/range math remains float32 and fused where possible;
- Difference is excluded from general Display Gain;
- 1× reuses canonical preview and schedules no gained-preview worker;
- gain>1 is viewer-local async presentation with stale-result rejection and
  hidden-view derived-buffer release;
- gain changes do not reload source, change generation/residency, or invalidate
  Difference.

P3-C is complete as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

## Runtime/settings baseline

Settings schema version 5 owns:

- RAW JSON confirmation;
- exact RAW file-size validation;
- optional default Open/Export folders;
- Difference Threshold/Gain defaults;
- Difference Map Cache MiB;
- Decoded Source Memory MiB;
- preload enablement.

P3-B/P3-C/P3-D add no setting or schema migration. Display Gain is session-local.
P3-D does not create Settings-owned profile storage or a new RawProfile version
field; existing RawProfile migration remains sufficient for the current workflow.

Source residency remains exact native `source.nbytes` under deterministic
protected soft-budget LRU semantics. Difference cache remains independent and
byte-budgeted. Preload remains `+1`, one Folder Position, max-one dedicated worker;
an exact matching RUNNING preload may transfer logical authority to foreground
without duplicate decode. Diagnostics remain deterministic, bounded, sanitized,
observation-only, with **Help > Copy Diagnostics** as the sole user surface.

## Active P3 sequence

1. **P3-A — Difference Gray / Mixed Bit-Depth Support — Complete — PR #22**
2. **P3-B — RAW Native & Display Semantics — Complete — PR #24**
3. **P3-C — Display Gain Extension — Complete — PR #25**
   - merge commit `7f6bef73e6712f6a14a4d401820a915196e25da2`.
4. **P3-D — Unified Image Opening & RAW Profile Resolution — In progress**
   - unify file-open UX without duplicating RAW decode/profile semantics;
   - preserve deterministic same-basename sidecars and current RawProfile
     compatibility;
   - explicitly defer Profile Library/suggestion until workflow evidence exists.
5. **P3-E — Integration & Hardening**.

Then P4 Workflow & Session Productivity, P5 Remote IQA Platform, P6 Identity /
Access & Remote Operations, and P7 Release Engineering & Distribution.

## P3-D validation state

P3-D test code covers the unified menu/filter, Empty Workspace cleanup, ordinary
image bypass, RAW sidecar/no-sidecar/invalid/cancel/multi-file resolution,
exact/minimum-size behavior, mixed folder/drop discovery, and profile terminology.
Existing suites remain responsible for PageUp/PageDown, RAW preload/reload/profile
identity, source residency, Difference, Display Gain, Statistics/Histogram/Line
Profile, and Split Channels regressions.

The Chat implementation agent does not run the Windows `.venv` validation suite.
Owner/local Windows validation is required before merge; no P3-D PASS claim is
recorded here.