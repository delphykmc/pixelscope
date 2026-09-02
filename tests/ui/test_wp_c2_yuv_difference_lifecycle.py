from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.ui.difference_panel import DifferencePanel


class _CancelProbe:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def _document(name: str) -> ImageDocument:
    return ImageDocument.from_yuv(
        NativeYuvFrame(
            y=np.zeros((4, 4), dtype=np.uint8),
            u=np.zeros((2, 2), dtype=np.uint8),
            v=np.zeros((2, 2), dtype=np.uint8),
            layout="YUV420",
        ),
        name,
    )


def test_yuv_channel_switch_cancels_inflight_map_and_preview_work(qtbot: object) -> None:
    first = _document("a.yuv")
    second = _document("b.yuv")
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))

    map_probe = _CancelProbe()
    preview_probe = _CancelProbe()
    panel._worker = map_probe  # type: ignore[assignment]
    panel._worker_key = ("Y",)
    panel._preview_worker = preview_probe  # type: ignore[assignment]

    panel.channel.setCurrentText("U")

    assert map_probe.cancelled is True
    assert preview_probe.cancelled is True
    assert panel._worker is None
    assert panel._worker_key is None
    assert panel._preview_worker is None
    assert panel.channel.currentText() == "U"
