"""Explicit module alias for the canonical Core-only PixelScope launcher."""

from pixelscope.app.application import main

if __name__ == "__main__":
    raise SystemExit(main())
