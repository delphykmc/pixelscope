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


def _is_reserved_implementation(module: str) -> bool:
    return module.startswith(("pixelscope_iqa_reference", "pixelscope_enterprise"))


def _contains_iqa_implementation(modules: set[str]) -> bool:
    return any(".iqa_" in module or "remote_iqa" in module for module in modules)


def _is_allowed_main_import(module: str, allowed: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in allowed)


def test_base_core_does_not_import_reference_or_enterprise_namespaces() -> None:
    violations: list[str] = []
    for relative_root in ("app", "core", "io", "workers"):
        root = SOURCE_ROOT / "pixelscope" / relative_root
        for path in root.rglob("*.py"):
            for module in _imports(path):
                if _is_reserved_implementation(module):
                    relative = path.relative_to(REPOSITORY_ROOT)
                    violations.append(f"{relative} -> {module}")
    assert violations == []


def test_generic_bootstrap_contains_no_iqa_implementation_imports() -> None:
    modules = _imports(SOURCE_ROOT / "pixelscope" / "app" / "bootstrap.py")
    assert not _contains_iqa_implementation(modules)


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
            if module.startswith("pixelscope.") and not _is_allowed_main_import(module, allowed):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative} -> {module}")
    assert violations == []


def test_enterprise_reserved_paths_are_not_owned_by_main() -> None:
    reserved = (
        "src/pixelscope_enterprise",
        "tests/enterprise",
        "docs/enterprise",
        "enterprise",
    )
    existing = [path for path in reserved if (REPOSITORY_ROOT / path).exists()]
    assert existing == []


def test_generic_composition_lifetime_does_not_eager_load_iqa_implementation() -> None:
    path = SOURCE_ROOT / "pixelscope" / "ui" / "composition_lifetime.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    eager_modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            eager_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            eager_modules.add(node.module)
    assert not _contains_iqa_implementation(eager_modules)

    install = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "install_remote_iqa"
    )
    lazy_modules = {
        node.module
        for node in ast.walk(install)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "pixelscope.ui.iqa_composition_lifetime" in lazy_modules
