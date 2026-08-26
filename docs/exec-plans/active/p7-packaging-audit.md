# P7-0 Packaging Audit

Status: Complete for repository-owned assumptions
Audited base: `main@8648b88ed7fd3a0af75013dd31633c48ccbce3e5`

This audit covers the repository facts required before P7-A. It does not validate a
Windows packaged executable and does not close P5-G, P6, or final P7.

## Entry point and lifecycle

Both supported source entry paths converge on the same composition root:

```text
python -m pixelscope
    -> pixelscope.__main__
    -> pixelscope.app.application.main

installed `pixelscope` script
    -> pixelscope.app.application:main
```

`application.main()` owns QApplication creation/configuration, settings loading,
worker-pool composition, MainWindow construction, feature composition, window show,
and `app.exec()`. P7-A must not add another application bootstrap. The PyInstaller
executable will use `src/pixelscope/__main__.py` and therefore preserve the canonical
composition root.

`MainWindow.closeEvent()` is the controlled shutdown path. It saves UI state, shuts
down analysis/IQA controllers, cancels owned workers, waits bounded worker grace
periods, clears worker bookkeeping, and accepts the close event.

## Resources and generated paths

Canonical application assets remain:

```text
src/pixelscope/assets/icons/pixelscope.svg
src/pixelscope/assets/icons/pixelscope.png
src/pixelscope/assets/icons/pixelscope.ico
```

Runtime icon loading already uses `importlib.resources.files("pixelscope")` and reads
packaged PNG bytes. The audited application resource path does not depend on the
current working directory or a developer absolute path. P7-A must explicitly include
the canonical icon data in the `onedir` artifact.

Tests, examples, docs, scripts, and generated test data are not runtime resources and
must not be copied wholesale into the artifact.

Generated release output is fixed to:

```text
build/pyinstaller/        # work/intermediate files
dist/PixelScope/          # canonical validated onedir tree
```

The existing `.gitignore` already excludes `build/` and `dist/`.

## Dependency and hook strategy

Release builds use the owner-selected Windows x64 CPython baseline
`>=3.10.8,<3.11`. Runtime remains the pinned dependency set in
`requirements/runtime.txt`, including PySide6 6.4.2, pyqtgraph 0.13.3,
OpenCV 4.8.1.78, NumPy 1.24.4, httpx 0.24.1, and Pydantic 1.10.13.

PyInstaller is release tooling rather than an application runtime dependency. P7-A
will add a separate `requirements/release.txt` with exactly `PyInstaller==5.7` and a
pinned compatible community-hook layer.

P7-A will rely on PyInstaller package hooks for ordinary PySide6, NumPy, and OpenCV
binary discovery while explicitly adding only the three canonical PixelScope icon
assets. Broad `collect_all()` calls are prohibited. Artifact validation must prove
that the canonical artifact contains at minimum the Windows Qt platform plugin
(`qwindows.dll`), PySide6 runtime modules, NumPy native extension, OpenCV native
extension/binaries, and PixelScope icon resources.

No repository evidence requires speculative hidden imports before a real Windows build.
Concrete missing imports/plugins should be handled by the smallest explicit spec/hook
change after observing build evidence.

## GUI process semantics

PixelScope is a Windows GUI application. P7-A therefore uses a windowed/no-console
executable. Standard output/error are not a product correctness contract; existing
application diagnostics remain unchanged.

PyInstaller windowed mode can expose console streams as unavailable. The current
unconditional logging setup assumes a stream exists, so P7-A may add a minimal safe
configuration that preserves source-console behavior while avoiding dependence on a
console stream in the frozen GUI process.

## Version authority

The audit found duplicate manual version values:

```text
pyproject.toml                  version = "0.1.0"
src/pixelscope/__init__.py      __version__ = "0.1.0"
```

P7-A will replace this with one authority:

```text
src/pixelscope/version.py::__version__
```

Setuptools package metadata will derive its version through a dynamic attribute, and
`pixelscope.__version__` will re-export the same value for compatibility. Build/spec
and later ZIP/installer/release metadata must derive from the same authority.

This changes no Session, Settings, Remote IQA, image-source, Difference, or Statistics
semantics.

## Packaged executable smoke boundary

Source pytest is not packaged-executable evidence. P7-A will provide a Windows-specific
release smoke harness that starts `dist/PixelScope/PixelScope.exe`, waits for the real
process-owned visible PixelScope top-level window, fails on early process exit, sends a
standard Windows close message, and requires bounded clean process termination.

This validates packaged startup/MainWindow construction and the existing shutdown path
without adding test-only production behavior.

## Redistribution notices

P7-A establishes the internal validated `onedir` build foundation. P7-B, before
producing distributable ZIP/installer artifacts, must review and assemble the required
third-party license/notice payload from authoritative dependency license texts.

## Conclusion

No major repository contract blocks P7-A. The canonical composition root is reusable,
resource handling is suitable for packaged data, the version-authority fix is local,
generated artifact boundaries are compatible with `.gitignore`, release tooling can
remain separate from runtime dependencies, and P5/P6 authorities require no change.

Windows build/executable evidence remains a separate gate and must be reported as NOT
RUN until actually observed on Windows.
