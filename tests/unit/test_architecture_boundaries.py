from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NUMERICAL_ROOTS = (ROOT / "src/pixelscope/core", ROOT / "src/pixelscope/io")
FORBIDDEN_UI_IMPORTS = {"PySide6", "pyqtgraph"}


def _forbidden_imports(path: Path) -> list[str]:
    findings: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        imported_roots: list[str] = []
        if isinstance(node, ast.Import):
            imported_roots = [alias.name.partition(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots = [node.module.partition(".")[0]]
        for imported_root in imported_roots:
            if imported_root in FORBIDDEN_UI_IMPORTS:
                relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
                findings.append(f"{relative}:{node.lineno}: imports {imported_root}")
    return findings


def test_numerical_core_and_io_do_not_import_ui_frameworks() -> None:
    findings = [
        finding
        for root in NUMERICAL_ROOTS
        for path in sorted(root.rglob("*.py"))
        for finding in _forbidden_imports(path)
    ]

    assert findings == [], (
        "Numerical core/io must remain independent of Qt and pyqtgraph; "
        "move presentation work to pixelscope.ui.\n" + "\n".join(findings)
    )


def test_boundary_diagnostic_identifies_forbidden_import(tmp_path: Path) -> None:
    module = tmp_path / "coupled.py"
    module.write_text("from PySide6.QtCore import QObject\n", encoding="utf-8")

    assert _forbidden_imports(module) == [f"{module}:1: imports PySide6"]
