"""Observe default renderer-relevant Qt state in a fresh, unprivileged process.

Execute for BOTH pinned source roots with matching Python/Qt env. This probe is
a comparability guard; it does not claim to see every active application setting.
"""
from __future__ import annotations

import argparse
import json
import locale
import sys
from pathlib import Path

from PySide6.QtCore import QLocale, qVersion
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


def probe() -> dict[str, object]:
    app = QApplication([])
    font = app.font()
    palette = app.palette()
    screen = app.primaryScreen()
    result: dict[str, object] = {
        "qt": qVersion(),
        "font": {
            "family": font.family(),
            "style": font.styleName(),
            "point_size": font.pointSizeF(),
            "pixel_size": font.pixelSize(),
            "weight": font.weight(),
        },
        "qt_locale": QLocale.system().name(),
        "python_locale": list(locale.getlocale()),
        "style": app.style().objectName(),
        "palette": {
            name: palette.color(getattr(QPalette.ColorRole, name)).name()
            for name in ("Window", "WindowText", "Base", "Text", "Button", "ButtonText")
        },
        "primary_screen": (
            {
                "logical_dpi": screen.logicalDotsPerInch(),
                "device_pixel_ratio": screen.devicePixelRatio(),
            }
            if screen is not None
            else None
        ),
    }
    app.quit()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = probe()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"Renderer environment probe failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
