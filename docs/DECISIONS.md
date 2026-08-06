# Engineering decisions

- CPython 3.10 x64 is fixed for compatibility and deployment policy.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image, view,
  ROI, histogram, and line-plot primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup
  is the planned installer layer.
- NumPy/OpenCV implementations come first. Native code is deferred until
  profiling proves a bottleneck and remains behind numerical/RAW interfaces.
- UI widgets do not own decode or Difference algorithms. Expensive I/O and
  analysis run in bounded workers with stale-result rejection.
- Source pixels keep native dtype/channel meaning. RGBA alpha is ignored.
  Difference caches a native absolute map and derives views/metrics without
  recalculating subtraction.
- Difference cache capacity is byte-budgeted with a 512 MiB default and exposed
  diagnostics. Runtime Preferences remain future work.
- Decoded image residency currently uses a fixed seven-document reloadable
  working set. This is an interim constraint pending byte-budgeted residency.
- Ordered selection is the comparison model. Legacy A/B roles are not primary
  UI; Difference may select any two current images.
- Multi View has one fixed layout policy. `MultiCompareView._fixed_geometry()`
  is the sole geometry authority; P1-F removed the runtime arrangement registry,
  fields, actions, restore dependency, and persisted setting. Legacy setting
  values are ignored at startup and removed by Reset Workspace Layout.
- Layout fit and ordinary view preservation are distinct. Refit survives
  pending lazy loads; navigation, display-only Difference changes, and dock
  resize preserve zoom/offset.
- Plot title-bar icons are rendered in code with design-token colors instead of
  platform glyphs.
- Line Profile Difference mode resolves its initial reference by primary image,
  active image, then first displayed document and preserves explicit selection
  while available.
- RAW storage format, sample container, effective bit depth, endian, and
  alignment are separate profile concepts. MIPI RAW10/12/14 have fixed layouts
  and omit non-applicable container controls.
- Remote evaluation uses a versioned REST job API so the desktop UI and future
  GPU implementation can evolve independently.
