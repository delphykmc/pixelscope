from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import ApplicationSettings
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.performance_settings import PerformanceSettings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


def _window(qtbot: object, source_budget: int) -> MainWindow:
    application_settings = ApplicationSettings()
    performance_settings = PerformanceSettings(
        difference_cache_bytes=1024,
        source_residency_bytes=source_budget,
    )
    window = MainWindow(application_settings, performance_settings)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    return window


def _document(path: Path, nbytes: int, value: int = 0) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((1, nbytes), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_byte_budget_evicts_oldest_unprotected_source_and_updates_files(
    qtbot: object, tmp_path: Path
) -> None:
    window = _window(qtbot, source_budget=8)
    oldest = _document(tmp_path / "oldest.png", 4, 1)
    middle = _document(tmp_path / "middle.png", 4, 2)
    newest = _document(tmp_path / "newest.png", 4, 3)
    oldest.statistics_cache[("stats",)] = object()
    oldest.histogram_cache[("hist",)] = object()

    window.add_document(oldest, select=False)
    window.add_document(middle, select=False)
    window.add_document(newest, select=False)

    assert oldest.source is None
    assert oldest.preview is None
    assert oldest.loading_state == "pending"
    assert oldest.statistics_cache == {}
    assert oldest.histogram_cache == {}
    assert middle.source is not None
    assert newest.source is not None
    assert window.residency_manager.used_bytes == 8
    assert window.residency_manager.resident_document_ids == (
        middle.document_id,
        newest.document_id,
    )
    item = window.document_list.document_item(oldest.document_id)
    assert item is not None
    assert "Not cached" in item.toolTip(0)


def test_more_than_seven_sources_remain_resident_when_bytes_fit(
    qtbot: object, tmp_path: Path
) -> None:
    window = _window(qtbot, source_budget=16)
    documents = [_document(tmp_path / f"source-{index}.png", 1) for index in range(8)]

    for document in documents:
        window.add_document(document, select=False)

    assert all(document.source is not None for document in documents)
    assert window.residency_manager.resident_count == 8
    assert window.residency_manager.used_bytes == 8
    assert not hasattr(window, "_resident_document_limit")


@pytest.mark.parametrize(
    "protection",
    ("visible", "selected", "active", "difference", "load_target"),
)
def test_each_runtime_protection_input_skips_oldest_source(
    qtbot: object,
    tmp_path: Path,
    protection: str,
) -> None:
    window = _window(qtbot, source_budget=4)
    protected = _document(tmp_path / f"protected-{protection}.png", 4)
    newcomer = _document(tmp_path / f"new-{protection}.png", 4)
    window.add_document(protected, select=False)

    if protection == "visible":
        window._visible_document_ids = {protected.document_id}
    elif protection == "selected":
        item = window.document_list.document_item(protected.document_id)
        assert item is not None
        window.document_list.blockSignals(True)
        item.setSelected(True)
        window.document_list.blockSignals(False)
        window._selection_order = [protected.document_id]
        assert window._visible_document_ids == set()
        assert window._active_document_id is None
    elif protection == "active":
        window._active_document_id = protected.document_id
    elif protection == "difference":
        window._difference_source_ids = (protected.document_id, "unregistered")
    else:
        window._load_worker_targets["test-task"] = protected.document_id

    assert protected.document_id in window._residency_protected_document_ids()
    window.add_document(newcomer, select=False)

    assert protected.source is not None
    assert newcomer.source is None
    assert window.residency_manager.used_bytes == 4


def test_all_protected_and_oversized_sources_may_exceed_soft_budget(
    qtbot: object, tmp_path: Path
) -> None:
    window = _window(qtbot, source_budget=4)
    first = _document(tmp_path / "first.png", 4)
    second = _document(tmp_path / "second.png", 4)
    window._visible_document_ids = {first.document_id, second.document_id}
    window.add_document(first, select=False)
    window.add_document(second, select=False)

    assert first.source is not None
    assert second.source is not None
    assert window.residency_manager.used_bytes == 8
    assert window.residency_manager.over_budget_bytes == 4

    oversized_window = _window(qtbot, source_budget=4)
    oversized = _document(tmp_path / "oversized.png", 12)
    oversized_window._active_document_id = oversized.document_id
    oversized_window.add_document(oversized, select=False)
    assert oversized.source is not None
    assert oversized_window.residency_manager.used_bytes == 12
    assert oversized_window.residency_manager.over_budget_bytes == 8

    programmatic_window = _window(qtbot, source_budget=4)
    programmatic = ImageDocument.from_array(
        np.zeros((1, 8), dtype=np.uint8),
        "programmatic",
    )
    programmatic_window.add_document(programmatic, select=False)
    assert programmatic.source is not None
    assert programmatic_window.residency_manager.used_bytes == 8
    assert programmatic_window.residency_manager.over_budget_bytes == 4


def test_evicted_document_reloads_through_normal_worker_path(qtbot: object, tmp_path: Path) -> None:
    paths = [tmp_path / "first.png", tmp_path / "second.png"]
    arrays = [np.full((2, 3), index, dtype=np.uint8) for index in (10, 20)]
    for path, array in zip(paths, arrays, strict=True):
        assert cv2.imwrite(str(path), array)

    window = _window(qtbot, source_budget=6)
    documents = [
        ImageDocument.from_array(array, path.name, source_path=path)
        for path, array in zip(paths, arrays, strict=True)
    ]
    for document in documents:
        window.add_document(document, select=False)
    assert documents[0].source is None

    window._select_document_ids([documents[0].document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers
        and window.documents[documents[0].document_id].source is not None,
        timeout=3000,
    )

    reloaded = window.documents[documents[0].document_id]
    assert reloaded.loading_state == "ready"
    assert documents[1].source is None
    assert reloaded.source is not None
    assert window.residency_manager.used_bytes == int(reloaded.source.nbytes)
    assert window.residency_manager.resident_count == 1


def test_stale_load_result_does_not_change_document_or_accounting(
    qtbot: object, tmp_path: Path
) -> None:
    window = _window(qtbot, source_budget=16)
    pending = ImageDocument.pending_document(tmp_path / "pending.png")
    window.add_document(pending, select=False)
    stale_result = _document(tmp_path / "pending.png", 4)
    window._load_tokens[pending.document_id] = 2

    window._load_succeeded(pending.document_id, 1, stale_result)

    assert window.documents[pending.document_id] is pending
    assert pending.source is None
    assert window.residency_manager.used_bytes == 0
    assert window.residency_manager.resident_count == 0


def test_source_eviction_invalidates_local_state_but_keeps_difference_map(
    qtbot: object, tmp_path: Path
) -> None:
    window = _window(qtbot, source_budget=4)
    first = _document(tmp_path / "first.png", 2)
    second = _document(tmp_path / "second.png", 2)
    third = _document(tmp_path / "third.png", 2)
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    first.statistics_cache[("stats",)] = object()
    first.histogram_cache[("hist",)] = object()
    window._channel_view_cache[(first.document_id, first.generation)] = [first]

    first_generation = (first.document_id, first.generation)
    second_generation = (second.document_id, second.generation)
    difference_key = (
        (first_generation, second_generation)
        if first_generation <= second_generation
        else (second_generation, first_generation)
    )
    difference = CachedDifferenceMap(
        np.ones((1, 1), dtype=np.uint8),
        255.0,
        "GRAY",
        None,
    )
    assert window.difference_panel.difference_cache.put(difference_key, difference).stored

    window._visible_document_ids = {third.document_id}
    window.add_document(third, select=False)

    assert first.source is None
    assert first.statistics_cache == {}
    assert first.histogram_cache == {}
    assert not any(key[0] == first.document_id for key in window._channel_view_cache)
    assert window.difference_panel.difference_cache.peek(difference_key) is difference


def test_document_removal_drops_residency_accounting(qtbot: object, tmp_path: Path) -> None:
    window = _window(qtbot, source_budget=8)
    document = _document(tmp_path / "remove.png", 4)
    window.add_document(document, select=False)

    window._remove_document_ids([document.document_id])

    assert document.document_id not in window.documents
    assert window.residency_manager.used_bytes == 0
    assert window.residency_manager.resident_count == 0
