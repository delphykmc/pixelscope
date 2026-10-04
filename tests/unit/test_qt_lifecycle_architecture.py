from __future__ import annotations

import ast
from pathlib import Path
from weakref import ref

import pytest

from pixelscope.ui.lifecycle_hooks import OwnerCallback, WeakOwnerHook

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_MODULES = (
    "src/pixelscope/app/yuv_input_semantics.py",
    "src/pixelscope/app/yuv_runtime_contracts.py",
    "src/pixelscope/app/raw_input_compatibility.py",
    "src/pixelscope/ui/workflow_polish.py",
    "src/pixelscope/ui/recent_entries.py",
    "src/pixelscope/ui/display_gain.py",
    "src/pixelscope/ui/composition_lifetime.py",
    "src/pixelscope/ui/iqa_submission_lifecycle.py",
    "src/pixelscope/ui/iqa_result_mapping.py",
    "src/pixelscope/ui/iqa_historical_results.py",
    "src/pixelscope/ui/iqa_historical_results_lifecycle.py",
    "src/pixelscope/ui/iqa_scene_inspection.py",
    "src/pixelscope/ui/iqa_scene_inspection_lifecycle.py",
    "src/pixelscope/ui/iqa_result_retry.py",
    "src/pixelscope/ui/iqa_preview_lifecycle.py",
    "src/pixelscope/ui/iqa_replay_debug.py",
    "src/pixelscope/ui/iqa_request_debug.py",
    "src/pixelscope/ui/quick_compare.py",
    "src/pixelscope/ui/issue77_ui_design_followup.py",
    "src/pixelscope/ui/multiview_reorder_stability.py",
    "src/pixelscope/ui/beta_workspace_hardening.py",
    "src/pixelscope/ui/iqa_p5f_diagnostics.py",
    "src/pixelscope/ui/iqa_remote_settings.py",
)

RANK4_OWNER_ASSIGNMENTS = {
    "src/pixelscope/app/yuv_runtime_contracts.py": {("window", "window")},
    "src/pixelscope/app/raw_input_compatibility.py": {("window", "window")},
    "src/pixelscope/ui/iqa_result_retry.py": {("remote_controller", "remote_controller")},
    "src/pixelscope/ui/iqa_preview_lifecycle.py": {
        ("controller", "controller"),
        ("workspace", "controller"),
    },
    "src/pixelscope/ui/iqa_replay_debug.py": {("window", "window")},
    "src/pixelscope/ui/iqa_request_debug.py": {
        ("window", "window"),
        ("workspace", "window"),
        ("controller", "controller"),
    },
    "src/pixelscope/ui/workflow_polish.py": {
        ("window", "window"),
        ("tree", "window"),
    },
    "src/pixelscope/ui/recent_entries.py": {
        ("window", "window"),
        ("session_controller", "session"),
        ("comparison_set_controller", "session"),
        ("file_menu", "file_menu"),
    },
    "src/pixelscope/ui/display_gain.py": {
        ("window", "window"),
        ("combo", "combo"),
    },
    "src/pixelscope/ui/composition_lifetime.py": {
        ("window", "window"),
        ("controller", "controller"),
    },
}


def _root_name(node: ast.expr) -> str | None:
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def test_cycle_hardened_modules_do_not_install_bound_methodtype_or_weak_proxy() -> None:
    violations: list[str] = []
    for relative_path in LIFECYCLE_MODULES:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "MethodType"
            ):
                violations.append(f"{relative_path}:{node.lineno}: MethodType")
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and any(
                    isinstance(target, ast.Attribute) and "_original" in target.attr
                    for target in node.targets
                )
            ):
                violations.append(
                    f"{relative_path}:{node.lineno}: strong original bound method"
                )
    assert violations == []


def test_rank4_helpers_do_not_store_direct_owner_backreferences() -> None:
    violations: list[str] = []
    for relative_path, forbidden in RANK4_OWNER_ASSIGNMENTS.items():
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            root = _root_name(node.value)
            if root is None:
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and (target.attr, root) in forbidden
                ):
                    violations.append(
                        f"{relative_path}:{node.lineno}: self.{target.attr} retains {root}"
                    )
    assert violations == []


def test_production_composition_uses_final_rank4_non_owning_adapters() -> None:
    relative_path = "src/pixelscope/app/application.py"
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative_path)

    hardened_imports: set[str] = set()
    legacy_imports: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        imported = {alias.name for alias in node.names}
        if node.module == "pixelscope.ui.composition_lifetime":
            hardened_imports.update(imported)
        if node.module in {
            "pixelscope.ui.analysis_export",
            "pixelscope.ui.iqa_submission",
            "pixelscope.ui.session",
        }:
            legacy_imports.extend(
                name
                for name in imported
                if name in {"install_analysis_export", "install_remote_iqa", "install_session"}
            )

    assert {
        "install_analysis_export",
        "install_remote_iqa",
        "install_session",
        "release_command_row_metric_window",
    } <= hardened_imports
    assert legacy_imports == []

    release_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "release_command_row_metric_window"
    ]
    assert len(release_calls) == 1


def test_non_owning_hooks_do_not_retain_their_owner() -> None:
    class Owner:
        def original(self) -> str:
            return "original"

    owner = Owner()
    owner_ref = ref(owner)
    original = OwnerCallback(owner.original)
    hook = WeakOwnerHook(owner, lambda current: current.original())

    assert original() == "original"
    assert hook() == "original"

    del owner

    assert owner_ref() is None
    with pytest.raises(RuntimeError, match="owner was destroyed"):
        original()
    with pytest.raises(RuntimeError, match="owner was destroyed"):
        hook()
