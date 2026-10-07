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
    root = SOURCE_ROOT / "pixelscope"
    for path in root.rglob("*.py"):
        for module in _imports(path):
            if _is_reserved_implementation(module):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative} -> {module}")
    assert violations == []


def test_default_core_modules_contain_no_iqa_implementation_imports() -> None:
    paths = (
        SOURCE_ROOT / "pixelscope" / "app" / "application.py",
        SOURCE_ROOT / "pixelscope" / "app" / "core_application.py",
        SOURCE_ROOT / "pixelscope" / "app" / "bootstrap.py",
        SOURCE_ROOT / "pixelscope" / "app" / "main_window.py",
        SOURCE_ROOT / "pixelscope" / "app" / "settings.py",
    )
    violations = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _imports(path) if _contains_iqa_implementation({module})
        )
        for path in paths
    }
    assert {path: modules for path, modules in violations.items() if modules} == {}


def test_main_window_has_no_legacy_iqa_constructor_or_auto_composition_seam() -> None:
    source = (SOURCE_ROOT / "pixelscope" / "app" / "main_window.py").read_text(encoding="utf-8")
    assert "iqa_result_pool" not in source
    assert "_legacy_window_contributions" not in source


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


def test_generic_composition_lifetime_contains_no_iqa_compatibility_shim() -> None:
    path = SOURCE_ROOT / "pixelscope" / "ui" / "composition_lifetime.py"
    source = path.read_text(encoding="utf-8")
    assert not _contains_iqa_implementation(_imports(path))
    assert "install_remote_iqa" not in source


def test_base_settings_has_no_concrete_iqa_type_or_runtime_dependency() -> None:
    path = SOURCE_ROOT / "pixelscope" / "app" / "settings.py"
    source = path.read_text(encoding="utf-8")
    assert not _contains_iqa_implementation(_imports(path))
    assert "RemoteIqaSettings" not in source
    assert "remote_iqa:" not in source


def test_core_diagnostics_exposes_only_generic_extension_sections() -> None:
    path = SOURCE_ROOT / "pixelscope" / "core" / "diagnostics.py"
    source = path.read_text(encoding="utf-8")
    assert "RemoteIqaDiagnostics" not in source
    assert "remote_iqa" not in source
    assert "ExtensionDiagnosticsSection" in source
