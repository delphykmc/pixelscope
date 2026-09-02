from __future__ import annotations

from typing import Any


def install_native_yuv_difference(window: Any) -> None:
    """Retire WP-C1's temporary Difference block for the WP-C2-aware panel.

    WP-C1 wrapped DifferencePanel only to keep native YUV outside legacy
    RGB/Gray/Bayer Difference. WP-C2 makes DifferencePanel YUV-aware, so production
    must restore the panel's original set/calculate entry points while leaving every
    other NativeYuvSemanticsController lifecycle hook in place.
    """

    controller = window.__dict__.get("native_yuv_semantics_controller")
    if controller is None:
        raise RuntimeError("native YUV semantics must be installed before YUV Difference")

    difference = window.difference_panel
    difference.set_documents = controller._difference_set_documents_original
    difference.calculate_difference = controller._difference_calculate_original
    controller._difference_yuv_blocked = False
    window.__dict__["native_yuv_difference_installed"] = True
