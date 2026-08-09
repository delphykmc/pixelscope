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

Register files or folders by drag-and-drop or through **File > Open Images /
Open Folder**. Files are grouped by parent folder. Standard Ctrl/Shift
selection forms the ordered comparison set, and Page Up/Page Down moves
multi-folder selections atomically in natural filename order.

Auto, Single View, and Multi View provide synchronized cursor, zoom, offset,
ROI, and line coordinates. Multi View uses fixed layouts for one to six source
images, with focus promotion in the three- and five-image layouts. Difference
is derived from any two selected sources and is promoted consistently without
changing the logical source IDs.

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

RAW always opens a profile workflow unless a same-name JSON profile is accepted
through the stored preference. The profile separates storage format, sample
container, effective bit depth, byte order, bit alignment, dimensions, stride,
offset, and channel layout.

Supported storage formats are:

- Unpacked `uint8` and `uint16`, including little/big endian and LSB/MSB
  alignment where applicable.
- MIPI RAW10, RAW12, and RAW14.
- Grayscale and Bayer mosaic channel layouts.

Bayer analysis uses native R/Gr/Gb/B mosaic planes. Demosaic preview,
black/white-level processing, and profile suggestion are not implemented.

Example profile:
[`examples/raw_profiles/example_unpacked_raw16.json`](examples/raw_profiles/example_unpacked_raw16.json).

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

## Current scope and documentation

The authoritative current baseline and verified backlog are in
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md). Use
[`docs/index.md`](docs/index.md) to locate product, architecture, decision,
quality, roadmap, packaging, UI, and execution-plan documents.

Standalone distribution, installer signing, live GPU IQA, heatmap overlays,
persistent comparison sessions, saved ROI management, alpha overlay, and RAW
demosaic remain future work.
