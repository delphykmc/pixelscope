from __future__ import annotations

import ast
from pathlib import Path
from weakref import ref

import pytest

from pixelscope.ui.lifecycle_hooks import (
    OwnerCallback,
    OwnerCallbackAttribute,
    WeakOwnerAttribute,
    WeakOwnerHook,
    WeakOwnerTupleAttribute,
)
from pixelscope.ui.residual_owner_hardening import (
    _OWNER_CALLBACK_FIELDS,
    _WEAK_OWNER_FIELDS,
    _WEAK_OWNER_TUPLE_FIELDS,
    install_residual_owner_hardening,
)

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
    "src/pixelscope/ui/residual_owner_hardening.py",
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


def test_non_owning_descriptors_return_real_objects_without_retaining_them() -> None:
    class Owner:
        def original(self) -> str:
            return "original"

    class Holder:
        owner = WeakOwnerAttribute("owner")
        owners = WeakOwnerTupleAttribute("owners")
        original = OwnerCallbackAttribute("original")

    owner = Owner()
    owner_ref = ref(owner)
    holder = Holder()
    holder.owner = owner
    holder.owners = (owner, None)
    holder.original = owner.original

    assert holder.owner is owner
    assert holder.owners == (owner, None)
    assert holder.original() == "original"

    del owner

    assert owner_ref() is None
    with pytest.raises(RuntimeError, match="owner was destroyed"):
        _ = holder.owner
    with pytest.raises(RuntimeError, match="dependency was destroyed"):
        _ = holder.owners
    with pytest.raises(RuntimeError, match="owner was destroyed"):
        holder.original()


def test_rank4_measured_owner_edges_install_non_owning_descriptors() -> None:
    install_residual_owner_hardening()
    install_residual_owner_hardening()

    for owner_type, attribute_name in _WEAK_OWNER_FIELDS:
        assert isinstance(owner_type.__dict__[attribute_name], WeakOwnerAttribute)
    for owner_type, attribute_name in _WEAK_OWNER_TUPLE_FIELDS:
        assert isinstance(owner_type.__dict__[attribute_name], WeakOwnerTupleAttribute)
    for owner_type, attribute_name in _OWNER_CALLBACK_FIELDS:
        assert isinstance(owner_type.__dict__[attribute_name], OwnerCallbackAttribute)
