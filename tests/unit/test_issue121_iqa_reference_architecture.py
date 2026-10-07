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


def _module_name(path: Path) -> str:
    relative = path.relative_to(SOURCE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _source_import_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in SOURCE_ROOT.rglob("*.py"):
        graph[_module_name(path)] = {
            module for module in _imports(path) if module.startswith("pixelscope")
        }
    return graph


def _reachable_modules(entrypoint: str) -> set[str]:
    graph = _source_import_graph()
    pending = [entrypoint]
    reachable: set[str] = set()
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        pending.extend(
            dependency
            for dependency in graph.get(module, ())
            if dependency in graph and dependency not in reachable
        )
    return reachable


def _is_reserved_implementation(module: str) -> bool:
    return module.startswith(("pixelscope_iqa_reference", "pixelscope_enterprise"))


def _contains_iqa_implementation(modules: set[str]) -> bool:
    return any(".iqa_" in module or "remote_iqa" in module for module in modules)


def _is_iqa_runtime_module(module: str) -> bool:
    return module.startswith(("pixelscope.ui.iqa_", "pixelscope.remote.iqa_"))


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


def test_core_entrypoint_transitive_imports_reach_no_iqa_implementation() -> None:
    reachable = _reachable_modules("pixelscope.__main__")
    allowed_iqa_modules = {
        "pixelscope.remote.iqa_domain",
        "pixelscope.remote.iqa_public_contract",
        "pixelscope.remote.iqa_public_fixture",
    }
    violations = sorted(
        module
        for module in reachable
        if _is_iqa_runtime_module(module) and module not in allowed_iqa_modules
    )
    assert violations == []


def test_reference_entrypoint_transitive_iqa_imports_are_public_only() -> None:
    reachable = _reachable_modules("pixelscope_iqa_reference.__main__")
    allowed_iqa_modules = {
        "pixelscope.remote.iqa_domain",
        "pixelscope.remote.iqa_public_contract",
        "pixelscope.remote.iqa_public_fixture",
    }
    violations = sorted(
        module
        for module in reachable
        if _is_iqa_runtime_module(module) and module not in allowed_iqa_modules
    )
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


def test_generic_base_ui_contains_no_legacy_p5_attribute_contract() -> None:
    legacy_names = {
        "iqa_dock",
        "iqa_workspace",
        "iqa_workspace_action",
        "remote_iqa_workspace",
    }
    paths = (
        SOURCE_ROOT / "pixelscope" / "ui" / "beta_workspace_hardening.py",
        SOURCE_ROOT / "pixelscope" / "ui" / "workflow_polish.py",
        SOURCE_ROOT / "pixelscope" / "ui" / "user_guide_help.py",
    )
    violations = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(
            name for name in legacy_names if name in path.read_text(encoding="utf-8")
        )
        for path in paths
    }
    assert {path: names for path, names in violations.items() if names} == {}


def test_core_diagnostics_exposes_only_generic_extension_sections() -> None:
    path = SOURCE_ROOT / "pixelscope" / "core" / "diagnostics.py"
    source = path.read_text(encoding="utf-8")
    assert "RemoteIqaDiagnostics" not in source
    assert "remote_iqa" not in source
    assert "ExtensionDiagnosticsSection" in source
