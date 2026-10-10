from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

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


def test_current_tests_do_not_import_retired_iqa_runtime_modules() -> None:
    allowed = {
        "pixelscope.remote.iqa_domain",
        "pixelscope.remote.iqa_public_contract",
        "pixelscope.remote.iqa_public_fixture",
    }
    retired_exact = {
        "pixelscope.app.iqa_history",
        "pixelscope.workers.iqa_thread_pool",
    }
    violations: list[str] = []
    for path in (REPOSITORY_ROOT / "tests").rglob("*.py"):
        for module in _imports(path):
            retired = (
                module.startswith("pixelscope.remote.iqa_")
                or module.startswith("pixelscope.ui.iqa_")
                or module in retired_exact
            )
            if retired and module not in allowed:
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative} -> {module}")
    assert violations == []


def test_historical_p5_runtime_files_are_retired_from_main_source() -> None:
    remote_root = SOURCE_ROOT / "pixelscope" / "remote"
    ui_root = SOURCE_ROOT / "pixelscope" / "ui"
    allowed_remote = {
        "iqa_domain.py",
        "iqa_public_contract.py",
        "iqa_public_fixture.py",
    }

    assert {path.name for path in remote_root.glob("iqa_*.py")} == allowed_remote
    assert list(ui_root.glob("iqa_*.py")) == []
    assert not (SOURCE_ROOT / "pixelscope" / "app" / "iqa_history.py").exists()
    assert not (SOURCE_ROOT / "pixelscope" / "workers" / "iqa_thread_pool.py").exists()


_PUBLIC_MAIN_SHA_ENV = "PIXELSCOPE_PUBLIC_MAIN_SHA"
_RESERVED_SUB_ROOTS = (
    "src/pixelscope_enterprise",
    "tests/enterprise",
    "docs/enterprise",
    "enterprise",
)
_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


def _git_output(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise AssertionError(f"Git is required for the MAIN ownership guard: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(f"MAIN ownership guard could not run git {args[0]}: {detail}")
    return result.stdout


def _assert_main_git_tree_has_no_reserved_paths(root: Path, ref: str) -> None:
    # A downstream checkout may track the reserved paths in its own HEAD.
    # Only the selected PUBLIC MAIN commit is authoritative for MAIN ownership.
    if ref != "HEAD" and _COMMIT_SHA.fullmatch(ref) is None:
        raise AssertionError(
            f"{_PUBLIC_MAIN_SHA_ENV} must be an exact 40-character PUBLIC MAIN commit SHA"
        )
    toplevel = Path(
        _git_output(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    ).resolve()
    assert toplevel == root.resolve(), "MAIN ownership guard requires the repository root"
    resolved = _git_output(root, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    if ref != "HEAD":
        assert resolved.lower() == ref.lower(), "PUBLIC MAIN SHA did not resolve exactly"
        # The consuming checkout must descend from the pinned merged MAIN commit.
        _git_output(root, "merge-base", "--is-ancestor", resolved, "HEAD")

    tree = _git_output(root, "ls-tree", "-r", "-z", "--name-only", "--full-tree", resolved)
    tracked = (os.fsdecode(path) for path in tree.split(b"\x00") if path)
    violations = sorted(
        path
        for path in tracked
        if any(
            path == reserved or path.startswith(f"{reserved}/") for reserved in _RESERVED_SUB_ROOTS
        )
    )
    assert not violations, (
        f"PUBLIC MAIN commit {resolved} tracks SUB-reserved paths: {violations}. "
        "If running in PRIVATE SUB, set PIXELSCOPE_PUBLIC_MAIN_SHA to the exact merged "
        "PUBLIC MAIN SHA; do not deselect the test."
    )


def test_enterprise_reserved_paths_are_not_owned_by_main() -> None:
    # PUBLIC MAIN checks HEAD; a PRIVATE SUB checkout pins the exact merged
    # PUBLIC MAIN SHA via this environment variable (no --deselect needed).
    pinned = os.environ.get(_PUBLIC_MAIN_SHA_ENV)
    if pinned is not None and _COMMIT_SHA.fullmatch(pinned) is None:
        raise AssertionError(
            f"{_PUBLIC_MAIN_SHA_ENV} must be the exact 40-character merged PUBLIC MAIN SHA"
        )
    _assert_main_git_tree_has_no_reserved_paths(REPOSITORY_ROOT, pinned or "HEAD")


def _issue156_commit_fixture(root: Path, relative_path: str) -> str:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n", encoding="utf-8")
    _git_output(root, "add", "--", relative_path)
    _git_output(
        root,
        "-c",
        "user.name=PixelScope Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "test MAIN ownership tree",
    )
    return _git_output(root, "rev-parse", "HEAD").decode("ascii").strip()


def test_issue156_guard_uses_pinned_main_tree_not_downstream_head(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    _git_output(root, "init", "-q")
    public_sha = _issue156_commit_fixture(root, "src/pixelscope/core.py")
    # A populated but untracked sibling also must not be treated as MAIN-owned.
    sibling = root / "enterprise" / "untracked_private.py"
    sibling.parent.mkdir()
    sibling.write_text("private = True\n", encoding="utf-8")
    _assert_main_git_tree_has_no_reserved_paths(root, "HEAD")

    _issue156_commit_fixture(root, "tests/enterprise/iqa/test_downstream.py")
    _issue156_commit_fixture(root, "enterprise/other_feature/config.toml")
    _assert_main_git_tree_has_no_reserved_paths(root, public_sha)
    with pytest.raises(AssertionError, match="tracks SUB-reserved paths"):
        _assert_main_git_tree_has_no_reserved_paths(root, "HEAD")


def test_issue156_guard_rejects_main_owned_reserved_paths(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    _git_output(root, "init", "-q")
    _issue156_commit_fixture(root, "src/pixelscope/core.py")
    _issue156_commit_fixture(root, "docs/enterprise/iqa/private.md")
    with pytest.raises(AssertionError, match="docs/enterprise/iqa/private.md"):
        _assert_main_git_tree_has_no_reserved_paths(root, "HEAD")


def test_issue156_guard_fails_closed_without_git_or_valid_pin(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="Git|git"):
        _assert_main_git_tree_has_no_reserved_paths(tmp_path, "HEAD")
    root = tmp_path / "checkout"
    root.mkdir()
    _git_output(root, "init", "-q")
    _issue156_commit_fixture(root, "src/pixelscope/core.py")
    with pytest.raises(AssertionError, match="40-character"):
        _assert_main_git_tree_has_no_reserved_paths(root, "main")


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
        "iqaWorkspaceDock",
        "ui/iqa_floating_geometry",
    }
    paths = (
        SOURCE_ROOT / "pixelscope" / "ui" / "beta_workspace_hardening.py",
        SOURCE_ROOT / "pixelscope" / "ui" / "workflow_polish.py",
        SOURCE_ROOT / "pixelscope" / "ui" / "user_guide_help.py",
        SOURCE_ROOT / "pixelscope" / "ui" / "plots_dock_title.py",
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
