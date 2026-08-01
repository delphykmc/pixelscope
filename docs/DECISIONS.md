# Engineering decisions

- CPython 3.10 x64 is fixed for compatibility and deployment policy.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides ImageItem,
  ViewBox, ROI, histogram, and line-plot primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup
  is the planned installer layer.
- NumPy/OpenCV implementations come first. Native code is deferred until
  profiling proves a bottleneck and remains behind numerical/RAW interfaces.
- UI widgets do not own decode or difference algorithms. Expensive I/O and
  analysis run in bounded `QThreadPool` workers with stale-result rejection.
- Source pixels keep native dtype/channel meaning. RGBA alpha is ignored for
  current analysis. Difference caches a native absolute map and derives channel
  and mask previews without recalculating subtraction.
- Ordered selection is the comparison model. Legacy fixed A/B controls are not
  primary UI; Difference may select any two current images.
- Layout-fit and ordinary view preservation are distinct state. Refit survives
  pending lazy loads; toggles, navigation, Diff display changes, and dock resize
  preserve zoom and offset.
- Plot title-bar icons are rendered in code with design-token colors instead of
  platform `StandardPixmap` glyphs, keeping Float/Dock, Maximize/Restore, and
  Hide legible across Windows themes and DPI settings.
- Remote evaluation uses a versioned REST job API, allowing the desktop UI and
  future GPU implementation to evolve independently.
