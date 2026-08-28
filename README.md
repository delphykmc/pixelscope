# PixelScope

PixelScope is a CPU-only Windows desktop application for visual and numeric
comparison of PNG, BMP, JPEG, and profile-described RAW images. It preserves
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

## RAW support

Direct RAW file input resolves a profile before loading unless a valid same-name
JSON sidecar is accepted through the stored preference. RAW discovered through
folder registration remains pending. A selected-but-off-page unresolved RAW does
not prompt or decode merely because it is selected; foreground Current Comparison
Page entry resolves its profile when source is required. Cancel leaves that RAW
pending with no worker and suppresses immediate passive re-prompt within the same
foreground attempt. Unresolved RAW is excluded from speculative preload.

The profile separates storage format, sample container, effective bit depth, byte
order, bit alignment, dimensions, stride, offset, and channel layout.

Supported storage formats are:

- Unpacked `uint8` and `uint16`, including little/big endian and LSB/MSB
  alignment where applicable.
- MIPI RAW10, RAW12, and RAW14.
- Grayscale and Bayer mosaic channel layouts.

Bayer analysis uses native R/Gr/Gb/B mosaic planes. Demosaic preview,
black/white-level processing, and profile suggestion are not implemented.

Example profile:
[`examples/raw_profiles/example_unpacked_raw16.json`](examples/raw_profiles/example_unpacked_raw16.json).

## Runtime memory policy

Decoded-source residency keeps P2 exact native `source.nbytes` accounting and
protected soft-budget LRU semantics. For large logical selections, selection alone
does not protect every visited source: the Current Comparison Page plus correctness
dependencies are protected, while off-page selected sources may be evicted and
normally reloaded when revisited. Preload remains exactly the next Folder Position;
PixelScope does not add a Comparison Page preload system.

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
notification/self-update integration, saved ROI management, alpha overlay, or RAW
demosaic.
