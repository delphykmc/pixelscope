"""Repository tests must prefer this checkout over another installed source tree."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_pytest_prefers_checkout_over_external_package(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    external = tmp_path / "external"
    package = external / "pixelscope"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# A stale external installation.\n", encoding="utf-8")
    probe = tmp_path / "test_import_probe.py"
    expected = str(root / "src" / "pixelscope" / "__init__.py")
    probe.write_text(
        "from pathlib import Path\n"
        "import pixelscope\n"
        "def test_import_origin():\n"
        f"    assert Path(pixelscope.__file__).resolve() == Path({expected!r}).resolve()\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(external)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(root / "pyproject.toml"), "-q", str(probe)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
