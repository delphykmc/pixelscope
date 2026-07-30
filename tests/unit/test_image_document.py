from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument


def test_document_preserves_source_and_bounds() -> None:
    source = np.arange(12, dtype=np.uint16).reshape(3, 4)
    document = ImageDocument.from_array(source, "test")
    assert document.source is source
    assert document.original_dtype == np.dtype(np.uint16)
    assert document.preview is not None and document.preview.dtype == np.uint8
    assert document.pixel_at(2, 1) == 6
    assert document.pixel_at(-1, 0) is None
    assert document.pixel_at(4, 0) is None


def test_document_rgb_value_and_cache_invalidation() -> None:
    source = np.zeros((2, 2, 3), dtype=np.uint8)
    source[0, 1] = (1, 2, 3)
    document = ImageDocument.from_array(source, "rgb")
    assert document.pixel_at(1, 0) == (1, 2, 3)
    document.histogram_cache[("test",)] = object()
    document.replace_source(np.ones_like(source))
    assert document.generation == 1
    assert document.histogram_cache == {}
