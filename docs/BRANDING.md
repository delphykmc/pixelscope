# PixelScope branding and application identity

PixelScope's application identity is independent from P3 input/catalog behavior.

## Canonical application identity

- Product name: **PixelScope**.
- Source-run Windows AppUserModelID: `PixelScope.PixelScope`.
- Canonical package icon assets remain the SVG/PNG/ICO triplet under
  `src/pixelscope/assets/icons/`.
- Source-run title-bar, Alt+Tab, running-taskbar, scaling, and resource-loading
  behavior remain governed by the P2 identity implementation and tests.

## Scope boundary

P3-D Unified Image Opening & RAW Profile Resolution changes Files registration,
selection intent, viewer presentation ownership, and lazy RAW profile resolution.
It does **not** change application branding, executable icon binding, shortcuts,
installer identity, digital signing, updater behavior, or distribution packaging.

Those release-shell concerns remain P7 and must continue to respect the fixed
packaging constraints in `docs/PACKAGING_CONSTRAINTS.md`.
