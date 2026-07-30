# Product specification

PixelScope targets local, CPU-only inspection of multiple RAW/BMP/PNG images:
pixel/channel values, unified full-image/ROI histograms and statistics, line
profiles, selection-driven multi-view comparison, folder-pair navigation, and
numerical signed/absolute differences. Statistics are presented with images as
columns and measurements as rows. Histogram and line-profile legends use short
comparison indices while full filenames remain available in tooltips.

The Files panel groups registered files under their parent folders. A
comparison selection containing one file per folder forms a multi-folder pair
session. Page Down/Up moves every participating folder atomically and stops
when the shortest folder reaches an endpoint.

The complete product adds packed Bayer RAW support, configurable line profiles,
and remote GPU IQA/image evaluation. Remote results include scalar and
attribute scores, heatmaps, pixel-level maps, model/preprocessing versions, and
inference metadata. Standalone Windows distribution remains a final release
goal.
