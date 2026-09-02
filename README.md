# PixelScope

PixelScope is a CPU-only Windows desktop application for visual and numeric
comparison of PNG, BMP, JPEG, and profile-described raw-like binary images. It preserves
native source data while providing synchronized viewers, pixel inspection,
full-image/ROI statistics, histograms, line profiles, and overflow-safe
Difference analysis.

## Requirements and installation

- Windows 10 or 11, x64
- CPython 3.10.x x64; Python 3.11+ is intentionally unsupported

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\runtime.txt
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## Run

```powershell
.\.venv\Scripts\python.exe -m pixelscope
```

Use **File > Open Images...** for selection-oriented direct file input and
**File > Open Folder...** for native single-folder registration. Multiple folders
remain registration-only through folder drag/drop or the registration API. Direct
image files are registered and become the ordered logical selection; folder contents
are registered in Files without changing that selection or the current presentation.
Registration and logical selection are not limited by viewer capacity.

For more than six selected images, PixelScope derives a maximum-six **Current
Comparison Page** from selection order. Multi View presents that page; Single View
presents one page-local active image while Statistics, Histogram, Line Profile,
and other default comparison analysis remain scoped to the same page. Viewer slots
are local 1–6. The presentation-control row above the image workspace keeps
Page status visible even for one page; previous/next arrows remain present and are
disabled at unavailable endpoints. `Ctrl+Left` / `Ctrl+Right` moves one Comparison
Page only when that direction is available, while Left/Right remains fine
Previous/Next Selected Image navigation. PageUp/PageDown
remains Folder Position and is available only for one-to-six selected images from
distinct folders.

Auto, Single View, and Multi View provide synchronized cursor, zoom, offset,
ROI, and line coordinates. For six-or-fewer selections, the existing fixed layouts
remain in use, with focus promotion in the three- and five-image layouts. Large
selections keep six-slot Grid 3x2 geometry across Comparison Pages, including
cleared empty slots on a short final page. Difference is derived from applicable
current-page sources and retains explicit pair authority without changing logical
source IDs.

Histogram supports Auto/256/1024/4096 bins, Count/Normalized/Log count modes,
and native code-value ranges. Line Profile supports absolute values,
normalization, and Difference-from-reference with an explicit reference
selector. Compact legends identify image ID and channel without repeating full
filenames.

Difference keeps a byte-budgeted native absolute-map cache and derives channel
views, ROI metrics, gain, and threshold masks without recalculating subtraction.
Metrics include MAE, MSE, RMSE, PSNR, P95, P99, maximum difference, and non-zero
ratio.

## RAW-like binary and native YUV support

PixelScope treats `.raw`, `.data`, and `.yuv` as one **raw-like binary input family**.
The `.yuv` extension alone does not imply YUV420, YUV422, or any other byte layout.
A `.yuv` source can either use the existing generic RAW profile workflow or an explicit
WP-C1 native YUV interpretation.

Same-stem sidecars use this precedence:

1. PixelScope `.json`
2. `.imgprops`
3. editable interpretation dialog

A JSON whose `channel_layout` is `YUV444`, `YUV422`, or `YUV420` selects the native
YUV path. A non-YUV RAW JSON remains authoritative for the generic RAW path, and
`.imgprops` remains a generic RAW/Bayer contract. The native YUV dialog also retains a
**Generic RAW profile…** fallback, so extension is never used as semantic authority.

WP-C1 native YUV supports:

- 8-bit YUV444, YUV422, and YUV420;
- Y plane first followed by interleaved UV chroma;
- UV ordering only;
- tightly packed storage with exact file-size validation;
- unrestricted positive YUV444 dimensions;
- even width for YUV422;
- even width and even height for YUV420;
- fixed BT.601 Full-range RGB conversion for viewer preview only.

The native Y/U/V planes are numerical authority. YUV422 and YUV420 retain U/V at
their native chroma resolution; PixelScope does not create replicated full-resolution
U/V planes as analysis sources. Pixel Inspector reports native Y/U/V at the luma cursor
coordinate. Split Channels produces native-resolution Y, U, and V views. Statistics and
Histogram use each plane's native sample cardinality. ROI remains expressed in luma
coordinates and maps deterministically to the referenced chroma footprint. Line Profile
keeps chroma samples at their native luma-coordinate positions instead of duplicating
them at every luma sample.

WP-C2 extends Difference to native YUV without changing that authority model. A native
YUV pair exposes exactly **Y / U / V**, defaulting to Y. YUV444 compares only with
YUV444, YUV422 only with YUV422, and YUV420 only with YUV420; mixed subsampling and
YUV/non-YUV pairs are rejected. The selected native plane is subtracted directly in the
8-bit code domain. In particular, YUV422/420 U/V Difference maps keep their native
chroma resolution and are never upsampled to luma resolution. Active ROI remains in
luma/image coordinates and reuses the WP-C1 native chroma-footprint mapping before
metrics are calculated. Difference cache identity includes document generation, YUV
layout/subsampling, and selected Y/U/V channel so unused chroma channels are not
precomputed.

Mixed YUV/non-YUV Statistics, Histogram, and Line Profile selections continue to fail
safe instead of presenting misleading channel labels.

For the generic RAW path, `.imgprops` maps Bayer metadata (`width`, `height`,
`sensorBitWidth`, `imageType=BAYER<n>`, `pattern`, and `pedestal`) and deliberately
does **not** infer packing from file size or producer-specific attributes. Missing
byte-layout metadata uses unpacked `uint16`, little-endian, LSB alignment where
applicable, offset 0, full-scale white level, and `minimum_row_bytes()` stride.

New/default RAW dialog profiles keep stride synchronized to the current minimum row
size while stride remains automatic. Width, storage-format, and container changes
recompute that minimum. Once the user edits stride explicitly, that value is a manual
override and later field changes do not silently replace it. Explicit JSON stride is
also preserved as manual input.

Raw-like inputs discovered through folder registration remain pending. A
selected-but-off-page unresolved raw-like input does not prompt or decode merely
because it is selected; foreground Current Comparison Page entry resolves its profile
when source is required. Cancel leaves that input pending with no worker and suppresses
immediate passive re-prompt within the same foreground attempt. Unresolved raw-like
inputs are excluded from speculative preload. Once a native YUV or generic RAW profile
is resolved, the source reuses the bounded preload/promotion, profile-identity,
residency, stale-result, and Session v1 persistence lifecycle.

The generic RAW profile separates storage format, sample container, effective bit depth,
byte order, bit alignment, dimensions, stride, offset, and channel layout.

Supported generic RAW storage formats are:

- Unpacked `uint8` and `uint16`, including little/big endian and LSB/MSB
  alignment where applicable.
- MIPI RAW10, RAW12, and RAW14.
- Grayscale and Bayer mosaic channel layouts.

Bayer analysis uses native R/Gr/Gb/B mosaic planes. Demosaic preview,
black/white-level processing, arbitrary YUV plane dumps, Y-only/UV-only semantic YUV
profiles, VU-order formats, planar I420/YV12, 10/12-bit YUV, configurable matrix/range
UI, cross-subsampling YUV Difference, chroma-resampled Difference, Combined/weighted
YUV Difference, and YUV↔RGB Difference are not implemented by WP-C2.

Example RAW profile:
[`examples/raw_profiles/example_unpacked_raw16.json`](examples/raw_profiles/example_unpacked_raw16.json).

## Runtime memory policy

Decoded-source residency keeps P2 protected soft-budget LRU semantics. RGB/Gray/Bayer
sources retain their established native-array accounting. Native YUV residency counts
the actual Y + U + V native sample storage; replicated chroma is not counted because it
is never retained as numerical authority. For large logical selections, selection alone
does not protect every visited source: the Current Comparison Page plus correctness
dependencies are protected, while off-page selected sources may be evicted and normally
reloaded when revisited. Preload remains exactly the next Folder Position; PixelScope
does not add a Comparison Page preload system.

## Development

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
```

Deterministic manual fixtures are documented in
[`test_data/README.md`](test_data/README.md). The RAW chart set covers unpacked
8/10/12/14/16-bit data and MIPI RAW10/12/14 equivalence.

## Build and release

Use [`docs/BUILD_AND_RELEASE.md`](docs/BUILD_AND_RELEASE.md) for the human-facing
owner-local Windows Beta build, installer/portable handoff, release-candidate, and
publication-staging procedure. Normative deployment and packaging constraints remain in
[`docs/PACKAGING_CONSTRAINTS.md`](docs/PACKAGING_CONSTRAINTS.md).

## Current scope and documentation

The authoritative current baseline and verified backlog are in
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md). Use
[`docs/index.md`](docs/index.md) to locate product, architecture, decision,
quality, roadmap, packaging, UI, and execution-plan documents.

Portable ZIP/Inno Setup distribution and owner-local candidate/publication staging are
implemented. Current Beta qualification does not include production Remote IQA
server/GPU/SSO integration, production signing or privileged corporate publication,
notification/self-update integration, saved ROI management, alpha overlay, RAW
demosaic, or post-WP-C2 YUV extensions such as cross-subsampling/converted Difference.
