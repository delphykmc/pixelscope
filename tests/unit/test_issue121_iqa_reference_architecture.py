from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_base_core_does_not_import_reference_or_enterprise_namespaces() -> None:
    violations: list[str] = []
    for relative_root in ("app", "core", "io", "workers"):
        root = SOURCE_ROOT / "pixelscope" / relative_root
        for path in root.rglob("*.py"):
            for module in _imports(path):
                if module == "pixelscope_iqa_reference" or module.startswith(
                    "pixelscope_iqa_reference."
                ):
                    violations.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {module}")
                if module == "pixelscope_enterprise" or module.startswith(
                    "pixelscope_enterprise."
                ):
                    violations.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {module}")
    assert violations == []


def test_generic_bootstrap_contains_no_iqa_implementation_imports() -> None:
    modules = _imports(SOURCE_ROOT / "pixelscope" / "app" / "bootstrap.py")
    assert all(".iqa_" not in module and "remote_iqa" not in module for module in modules)


def test_reference_extension_uses_only_allowed_main_surfaces() -> None:
    root = SOURCE_ROOT / "pixelscope_iqa_reference"
    allowed = (
        "pixelscope.app.bootstrap",
        "pixelscope.app.main_window",
        "pixelscope.app.window_contribution",
        "pixelscope.remote.iqa_public_contract",
        "pixelscope.remote.iqa_public_fixture",
        "pixelscope.workers.thread_pools",
    )
    violations: list[str] = []
    for path in root.rglob("*.py"):
        for module in _imports(path):
            if not module.startswith("pixelscope."):
                continue
            if not any(module == prefix or module.startswith(f"{prefix}.") for prefix in allowed):
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {module}")
    assert violations == []


def test_enterprise_reserved_paths_are_not_owned_by_main() -> None:
    reserved = (
        "src/pixelscope_enterprise",
        "tests/enterprise",
        "docs/enterprise",
        "enterprise",
    )
    assert [path for path in reserved if (REPOSITORY_ROOT / path).exists()] == []
