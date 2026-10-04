from __future__ import annotations

import ast
from pathlib import Path
from weakref import ref

import pytest

from pixelscope.ui.lifecycle_hooks import OwnerCallback, WeakOwnerHook

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_MODULES = (
    "src/pixelscope/app/yuv_input_semantics.py",
    "src/pixelscope/ui/workflow_polish.py",
    "src/pixelscope/ui/iqa_submission_lifecycle.py",
    "src/pixelscope/ui/iqa_result_mapping.py",
    "src/pixelscope/ui/iqa_historical_results.py",
    "src/pixelscope/ui/iqa_historical_results_lifecycle.py",
    "src/pixelscope/ui/iqa_scene_inspection.py",
    "src/pixelscope/ui/iqa_scene_inspection_lifecycle.py",
    "src/pixelscope/ui/quick_compare.py",
    "src/pixelscope/ui/issue77_ui_design_followup.py",
    "src/pixelscope/ui/multiview_reorder_stability.py",
    "src/pixelscope/ui/beta_workspace_hardening.py",
    "src/pixelscope/ui/iqa_p5f_diagnostics.py",
    "src/pixelscope/ui/iqa_remote_settings.py",
)


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
                    isinstance(target, ast.Attribute) and target.attr.startswith("_original")
                    for target in node.targets
                )
            ):
                violations.append(f"{relative_path}:{node.lineno}: strong original bound method")
    assert violations == []


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
