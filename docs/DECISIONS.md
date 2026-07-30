# Decisions

- CPython 3.10 x64 is fixed for production compatibility and deployment policy.
- PySide6 provides supported Qt6 bindings; pyqtgraph provides a responsive
  `ImageItem`/`ViewBox` without introducing a custom renderer.
- Python/NumPy/OpenCV come first; native code is deferred until profiling proves
  a bottleneck and stays behind numerical/RAW interfaces.
- Large RAW is exposed through NumPy memmap views with explicit row strides.
- UI widgets never own decoding/difference algorithms; QThreadPool workers keep
  expensive work off the event loop.
- Remote evaluation uses a versioned REST job API, allowing the local UI and
  future GPU implementation to evolve independently.
- Deployment is fixed to PyInstaller 5.7 `onedir` due to internal policy.
  PyInstaller 6.x is prohibited. Inno Setup is the planned installer.
