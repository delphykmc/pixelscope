from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.app import registration_controller as registration_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.registration_controller import install_large_folder_registration
from pixelscope.io.path_discovery import discover_registration_inputs
from pixelscope.ui.folder_display_tags import install_folder_display_tags

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _wait_idle(qtbot: object, controller: object) -> None:
    qtbot.waitUntil(lambda: controller.is_idle, timeout=5000)  # type: ignore[attr-defined]


def _make_folder(tmp_path: Path, count: int) -> Path:
    folder = tmp_path / "perf"
    folder.mkdir()
    for index in range(1, count + 1):
        (folder / f"image{index}.png").write_bytes(b"x")
    return folder


def test_async_controller_reuses_worker_sort_keys_without_quadratic_rebuild(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    folder = _make_folder(tmp_path, 80)
    discovery = discover_registration_inputs((folder,))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window)
    original = registration_module.natural_sort_key
    calls = 0

    def counting_key(path: Path) -> tuple[object, ...]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(registration_module, "natural_sort_key", counting_key)
    for record in discovery.items:
        controller._register_record(record)

    assert len(window.documents) == 80
    assert calls == 0
    window.close()


def test_async_controller_does_not_linearly_scan_folder_membership_for_fresh_item(
    qtbot: object, tmp_path: Path
) -> None:
    folder = _make_folder(tmp_path, 2)
    discovery = discover_registration_inputs((folder,))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window)
    controller._register_record(discovery.items[0])
    folder_key = discovery.items[0].canonical_folder_key
    assert folder_key is not None

    class NoContainsList(list[str]):
        def __contains__(self, _item: object) -> bool:
            raise AssertionError("fresh registration must not linearly scan folder document list")

    window._folder_documents[folder_key] = NoContainsList(window._folder_documents[folder_key])
    controller._register_record(discovery.items[1])

    assert len(window._folder_documents[folder_key]) == 2
    window.close()


def test_async_discovered_registration_does_not_resolve_paths_on_gui_thread(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    folder = _make_folder(tmp_path, 20)
    discovery = discover_registration_inputs((folder,))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window)
    original_resolve = Path.resolve
    calls = 0

    def counting_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        return original_resolve(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", counting_resolve)
    for record in discovery.items:
        controller._register_record(record)

    assert len(window.documents) == 20
    assert calls == 0
    window.close()


def test_folder_display_tag_row_refresh_is_coalesced_per_registration_slice(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    folder = _make_folder(tmp_path, 40)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    tags = install_folder_display_tags(window)
    controller = install_large_folder_registration(
        window,
        chunk_size=8,
        slice_budget_ms=100_000,
    )
    original_refresh = tags._refresh_folder_row
    calls = 0

    def counting_refresh(folder_path: Path | None, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        original_refresh(folder_path, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(tags, "_refresh_folder_row", counting_refresh)
    controller.enqueue((folder,))
    _wait_idle(qtbot, controller)

    assert calls == 5
    assert len(window.documents) == 40
    window.close()


def test_registration_progress_is_owned_by_files_panel_and_hides_when_idle(
    qtbot: object, tmp_path: Path
) -> None:
    folder = _make_folder(tmp_path, 3)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=1)

    assert controller._progress.parentWidget() is window.document_list.parentWidget()
    assert controller._progress.isHidden()

    controller.enqueue((folder,))
    assert controller.progress.phase == "scanning"
    assert not controller._progress.isHidden()
    _wait_idle(qtbot, controller)

    assert controller.progress.phase == "idle"
    assert controller._progress.isHidden()
    window.close()