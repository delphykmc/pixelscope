from __future__ import annotations

import numpy as np
import pytest
from pyqtgraph import functions

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.image_viewer import ImageViewer


@pytest.mark.parametrize("channels", [1, 3, 4])
def test_final_uint8_preview_renders_exact_pixels_without_rescale(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, channels: int
) -> None:
    gray = np.array([[0, 17, 255], [128, 254, 1]], dtype=np.uint8)
    source = gray if channels == 1 else np.stack([gray] * channels, axis=-1)
    if channels >= 3:
        source[..., 1] = 47
        source[..., 2] = 193
    if channels == 4:
        source[..., 3] = np.array([[0, 73, 255], [128, 254, 1]], dtype=np.uint8)
    document = ImageDocument.from_array(source, "preview")
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]

    def reject_rescale(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Final uint8 display codes must not be rescaled during paint")

    monkeypatch.setattr(functions, "rescaleData", reject_rescale)
    viewer.set_document(document)
    viewer.image_item.render()
    image = viewer.image_item.qimage
    assert image is not None
    assert (image.width(), image.height()) == (3, 2)
    for y in range(2):
        for x in range(3):
            pixel = image.pixelColor(x, y)
            expected = (
                (int(source[y, x]),) * 3 + (255,)
                if channels == 1
                else tuple(int(value) for value in source[y, x]) + ((255,) if channels == 3 else ())
            )
            assert pixel.getRgb() == expected
    assert np.array_equal(viewer.image_item.image, document.preview)
    viewer.close()
