"""Install non-owning descriptors for the measured residual MainWindow SCC."""

from __future__ import annotations

from typing import Any

from pixelscope.app.raw_input_compatibility import RawInputCompatibilityController
from pixelscope.app.yuv_runtime_contracts import NativeYuvRuntimeContracts
from pixelscope.ui.analysis_export import AnalysisExportController
from pixelscope.ui.iqa_preview_lifecycle import RemoteIqaPreviewLifecycle
from pixelscope.ui.iqa_result_retry import RemoteIqaResultRetryController
from pixelscope.ui.iqa_submission import RemoteIqaController, _RemoteIqaCloseFilter
from pixelscope.ui.lifecycle_hooks import (
    OwnerCallbackAttribute,
    WeakOwnerAttribute,
    WeakOwnerTupleAttribute,
)
from pixelscope.ui.presentation_controls import _CommandRowMetricRefresh
from pixelscope.ui.workflow_polish import FilesContextMenuController


_WEAK_OWNER_FIELDS: tuple[tuple[type[Any], str], ...] = (
    (NativeYuvRuntimeContracts, "window"),
    (RawInputCompatibilityController, "window"),
    (FilesContextMenuController, "window"),
    (FilesContextMenuController, "tree"),
    (_CommandRowMetricRefresh, "_window"),
    (_CommandRowMetricRefresh, "_command_layout"),
    (_CommandRowMetricRefresh, "_page_group"),
    (_CommandRowMetricRefresh, "_layout_combo"),
    (_CommandRowMetricRefresh, "_gain_combo"),
    (_CommandRowMetricRefresh, "_clear_button"),
    (_CommandRowMetricRefresh, "_keep_button"),
    (_CommandRowMetricRefresh, "_count_label"),
    (_CommandRowMetricRefresh, "_page_status_label"),
    (_CommandRowMetricRefresh, "_page_range_label"),
    (RemoteIqaController, "window"),
    (RemoteIqaController, "workspace"),
    (RemoteIqaController, "result_controller"),
    (RemoteIqaResultRetryController, "remote_controller"),
    (RemoteIqaPreviewLifecycle, "controller"),
    (RemoteIqaPreviewLifecycle, "workspace"),
    (_RemoteIqaCloseFilter, "controller"),
    (AnalysisExportController, "window"),
    (AnalysisExportController, "file_menu"),
)

_WEAK_OWNER_TUPLE_FIELDS: tuple[tuple[type[Any], str], ...] = (
    (_CommandRowMetricRefresh, "_secondary_labels"),
    (_CommandRowMetricRefresh, "_groups"),
)

_OWNER_CALLBACK_FIELDS: tuple[tuple[type[Any], str], ...] = (
    (RawInputCompatibilityController, "_register_input_original"),
    (RawInputCompatibilityController, "_confirm_raw_profile_original"),
    (RawInputCompatibilityController, "_ensure_loaded_original"),
)


def _install_descriptor(
    owner_type: type[Any],
    attribute_name: str,
    descriptor_type: type[WeakOwnerAttribute]
    | type[WeakOwnerTupleAttribute]
    | type[OwnerCallbackAttribute],
) -> None:
    current = owner_type.__dict__.get(attribute_name)
    if isinstance(current, descriptor_type):
        return
    if current is not None:
        raise RuntimeError(
            f"refusing to replace existing {owner_type.__name__}.{attribute_name} descriptor"
        )
    setattr(owner_type, attribute_name, descriptor_type(attribute_name))


def install_residual_owner_hardening() -> None:
    """Make measured helper-to-owner return edges non-owning before composition."""

    for owner_type, attribute_name in _WEAK_OWNER_FIELDS:
        _install_descriptor(owner_type, attribute_name, WeakOwnerAttribute)
    for owner_type, attribute_name in _WEAK_OWNER_TUPLE_FIELDS:
        _install_descriptor(owner_type, attribute_name, WeakOwnerTupleAttribute)
    for owner_type, attribute_name in _OWNER_CALLBACK_FIELDS:
        _install_descriptor(owner_type, attribute_name, OwnerCallbackAttribute)
