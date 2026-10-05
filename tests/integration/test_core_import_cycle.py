from __future__ import annotations

import subprocess
import sys


def test_line_profile_import_does_not_cycle_through_yuv() -> None:
    """A clean interpreter must be able to import the core line-profile path."""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pixelscope.core.line_profile import LineSelection; "
                "from pixelscope.core.image_document import ImageDocument; "
                "from pixelscope.core.yuv import NativeYuvFrame"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
