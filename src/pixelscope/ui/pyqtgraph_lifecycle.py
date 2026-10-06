from __future__ import annotations

from contextlib import suppress
from typing import Any, Callable, cast

import pyqtgraph as pg
from PySide6.QtWidgets import QGraphicsWidget

_PATCH_ATTRIBUTE = "_pixelscope_qt_lifecycle_hardened"
_PLOT_WIDGET_FORWARDERS = (
    "addItem",
    "removeItem",
    "autoRange",
    "clear",
    "setAxisItems",
    "setXRange",
    "setYRange",
    "setRange",
    "setAspectLocked",
    "setMouseEnabled",
    "setXLink",
    "setYLink",
    "enableAutoRange",
    "disableAutoRange",
    "setLimits",
    "register",
    "unregister",
    "viewRect",
)


def _disconnect_graphics_widget_anchor(item: object) -> None:
    """Break pyqtgraph GraphicsWidgetAnchor's strong parent reference before Qt teardown."""

    parent = getattr(item, "_GraphicsWidgetAnchor__parent", None)
    geometry_changed = getattr(item, "_GraphicsWidgetAnchor__geometryChanged", None)
    if parent is not None and geometry_changed is not None:
        with suppress(RuntimeError, TypeError):
            parent.geometryChanged.disconnect(geometry_changed)
    for attribute in (
        "_GraphicsWidgetAnchor__parent",
        "_GraphicsWidgetAnchor__parentAnchor",
        "_GraphicsWidgetAnchor__itemAnchor",
    ):
        if hasattr(item, attribute):
            setattr(item, attribute, None)


def _detach_legend(plot_widget: object) -> None:
    """Detach PlotItem.legend while the native graphics graph is still valid."""

    plot_item = getattr(plot_widget, "plotItem", None)
    if plot_item is None:
        return
    legend = getattr(plot_item, "legend", None)
    if legend is None:
        return

    with suppress(RuntimeError, TypeError, AttributeError):
        legend.clear()
    _disconnect_graphics_widget_anchor(legend)

    # PlotItem.close() removes the ViewBox but does not clear its legend reference.
    # Break both the Python reference and native QGraphicsItem parentage first so
    # cyclic GC cannot later re-enter a partially destroyed ViewBox hierarchy.
    plot_item.legend = None
    with suppress(RuntimeError, TypeError):
        QGraphicsWidget.setParentItem(legend, None)
    with suppress(RuntimeError, TypeError):
        scene = legend.scene()
        if scene is not None:
            scene.removeItem(legend)
    with suppress(RuntimeError, TypeError):
        legend.close()
    with suppress(RuntimeError, TypeError):
        legend.deleteLater()


def _release_plot_widget_forwarders(plot_widget: object) -> None:
    """Drop pyqtgraph's instance-bound PlotItem method wrappers after final close."""

    namespace = getattr(plot_widget, "__dict__", None)
    if not isinstance(namespace, dict):
        return
    for name in _PLOT_WIDGET_FORWARDERS:
        namespace.pop(name, None)


def install_pyqtgraph_lifecycle_hardening() -> None:
    """Install one process-wide PlotWidget.close guard for PixelScope UI teardown."""

    current_close = cast(Callable[..., Any], pg.PlotWidget.close)
    if getattr(current_close, _PATCH_ATTRIBUTE, False):
        return

    original_close = current_close

    def hardened_close(plot_widget: object) -> Any:
        _detach_legend(plot_widget)
        try:
            return original_close(plot_widget)
        finally:
            _release_plot_widget_forwarders(plot_widget)

    setattr(hardened_close, _PATCH_ATTRIBUTE, True)
    pg.PlotWidget.close = hardened_close  # type: ignore[method-assign]
