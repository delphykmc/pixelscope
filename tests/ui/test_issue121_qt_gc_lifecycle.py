from __future__ import annotations

import gc
from weakref import ReferenceType

import pyqtgraph as pg
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDockWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.line_profile_panel import LineProfilePanel
from pixelscope.ui.plots_dock_title import _CONTROLLER_ATTRIBUTE, PlotsDockTitleBar


def _drain_deferred_delete(app: QApplication) -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _legend_anchor_parent(legend: object) -> object | None:
    return getattr(legend, "_GraphicsWidgetAnchor__parent", None)


def test_line_profile_mouse_callbacks_hold_only_weak_owner_refs(qtbot: object) -> None:
    del qtbot
    panel = LineProfilePanel()

    assert len(panel._plot_mouse_callbacks) == 6
    for callback in panel._plot_mouse_callbacks:
        closure = callback.__closure__
        assert closure is not None
        contents = tuple(cell.cell_contents for cell in closure)
        assert panel not in contents
        owner_refs = [item for item in contents if isinstance(item, ReferenceType)]
        assert len(owner_refs) == 1
        assert owner_refs[0]() is panel

    panel.shutdown()
    panel.deleteLater()


def test_plot_widget_close_breaks_legend_viewbox_cycle_before_native_teardown(
    qtbot: object,
) -> None:
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    plot = pg.PlotWidget()
    plot_item = plot.getPlotItem()
    view_box = plot.getViewBox()
    legend = plot.addLegend(offset=(-8, 8))

    assert plot_item.legend is legend
    assert _legend_anchor_parent(legend) is view_box
    assert "addItem" in plot.__dict__

    plot.close()

    assert plot_item.legend is None
    assert _legend_anchor_parent(legend) is None
    assert plot.plotItem is None
    assert "addItem" not in plot.__dict__

    plot.deleteLater()
    _drain_deferred_delete(app)


def test_plots_dock_title_retention_is_weak_on_the_dock_side(qtbot: object) -> None:
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    dock = QDockWidget()
    title = PlotsDockTitleBar(dock)
    dock.setTitleBarWidget(title)

    retained = dock.__dict__[_CONTROLLER_ATTRIBUTE]
    assert isinstance(retained, ReferenceType)
    assert retained() is title
    assert PlotsDockTitleBar.controller_for_dock(dock) is title

    # The dock dictionary must not own the title wrapper strongly. The title already
    # belongs to the dock through Qt parentage; a Python back-edge made both wrappers
    # cyclic garbage and delayed their native destruction until arbitrary GC runs.
    assert title not in gc.get_referents(dock.__dict__)

    dock.close()
    dock.deleteLater()
    _drain_deferred_delete(app)


def test_repeated_main_window_close_is_safe_with_automatic_gc_enabled(
    qtbot: object,
    isolated_qsettings_subdirectory: None,
) -> None:
    del qtbot
    del isolated_qsettings_subdirectory
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert gc.isenabled()

    for _iteration in range(12):
        window = MainWindow()
        legends = (
            *tuple(window.comparison_analysis_panel.legends),
            *tuple(window.line_profile_panel.legends),
        )
        assert len(legends) == 12
        assert all(_legend_anchor_parent(legend) is not None for legend in legends)

        window.close()

        # MainWindow.closeEvent() owns final panel shutdown. Every pyqtgraph legend
        # must be detached while its ViewBox is still valid, before DeferredDelete
        # or cyclic GC can choose a later native destruction order.
        assert all(_legend_anchor_parent(legend) is None for legend in legends)

        window.deleteLater()
        _drain_deferred_delete(app)
        del legends
        del window

        # This is intentionally the failure trigger characterized in the Slice 4
        # investigation. It must be safe without disabling Python cyclic GC.
        gc.collect()
        _drain_deferred_delete(app)
