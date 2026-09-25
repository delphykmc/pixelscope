from __future__ import annotations

from types import MethodType

import pytest

from pixelscope.app.instance_patch import InstanceAttributePatch, InstancePatchSet


class _Target:
    def method(self) -> str:
        return "class"


def _bound(target: _Target, value: str) -> object:
    def replacement(_self: _Target) -> str:
        return value

    return MethodType(replacement, target)


def test_restore_removes_instance_override_for_class_method() -> None:
    target = _Target()
    replacement = _bound(target, "patched")
    assert "method" not in vars(target)

    patch = InstanceAttributePatch(target, "method", replacement)

    assert target.method() == "patched"
    assert vars(target)["method"] is replacement

    patch.restore()

    assert "method" not in vars(target)
    assert target.method() == "class"
    assert not patch.active


def test_restore_recovers_exact_previous_instance_override() -> None:
    target = _Target()
    previous = _bound(target, "previous")
    replacement = _bound(target, "replacement")
    target.method = previous  # type: ignore[method-assign]

    patch = InstanceAttributePatch(target, "method", replacement)
    assert target.method() == "replacement"

    patch.restore()

    assert vars(target)["method"] is previous
    assert target.method() == "previous"


def test_stacked_patches_restore_outer_then_inner() -> None:
    target = _Target()
    inner = _bound(target, "inner")
    outer = _bound(target, "outer")

    inner_patch = InstanceAttributePatch(target, "method", inner)
    outer_patch = InstanceAttributePatch(target, "method", outer)

    assert target.method() == "outer"
    outer_patch.restore()
    assert vars(target)["method"] is inner
    assert target.method() == "inner"

    inner_patch.restore()
    assert "method" not in vars(target)
    assert target.method() == "class"


def test_restore_rejects_out_of_order_stacked_patch() -> None:
    target = _Target()
    inner_patch = InstanceAttributePatch(target, "method", _bound(target, "inner"))
    outer_patch = InstanceAttributePatch(target, "method", _bound(target, "outer"))

    with pytest.raises(RuntimeError, match="restore order violation"):
        inner_patch.restore()

    assert inner_patch.active
    assert outer_patch.active
    assert target.method() == "outer"

    outer_patch.restore()
    inner_patch.restore()
    assert target.method() == "class"


def test_restore_is_idempotent() -> None:
    target = _Target()
    patch = InstanceAttributePatch(target, "method", _bound(target, "patched"))

    patch.restore()
    patch.restore()

    assert "method" not in vars(target)
    assert target.method() == "class"


def test_patch_set_restores_in_reverse_install_order() -> None:
    target = _Target()
    patches = InstancePatchSet()
    inner = _bound(target, "inner")
    outer = _bound(target, "outer")

    assert patches.install(target, "method", inner) is inner
    assert patches.install(target, "method", outer) is outer
    assert patches.active_count == 2
    assert target.method() == "outer"

    patches.restore_all()

    assert patches.active_count == 0
    assert "method" not in vars(target)
    assert target.method() == "class"
