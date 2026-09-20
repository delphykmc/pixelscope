from pathlib import Path

from scripts.check_user_guide_site import find_site_problems


def test_user_guide_site_contract_accepts_local_resources(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "main.css").write_text("body { background: url(local.png); }", encoding="utf-8")
    (assets / "local.png").write_bytes(b"png")
    (assets / "iframe-worker.js").write_text("// local shim", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="assets/main.css"></head>'
        '<body><img src="assets/local.png"></body>'
        '<script src="assets/iframe-worker.js"></script></html>',
        encoding="utf-8",
    )
    (tmp_path / "llms.txt").write_text("Start:\n- index.html\n", encoding="utf-8")

    assert find_site_problems(tmp_path) == []


def test_user_guide_site_contract_rejects_remote_assets_and_stale_routes(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="https://example.com/main.css"></head>'
        '<body><script src="https://example.com/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "llms.txt").write_text(
        "Start:\n- index.md\n- missing.html\n",
        encoding="utf-8",
    )

    problems = find_site_problems(tmp_path)

    assert any("Markdown source routes" in problem for problem in problems)
    assert any("missing site route: missing.html" in problem for problem in problems)
    assert any("remote resource dependency" in problem for problem in problems)


def test_user_guide_site_contract_requires_actual_local_offline_shim(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        '<html><script src="assets/iframe-worker.js"></script></html>',
        encoding="utf-8",
    )
    (tmp_path / "llms.txt").write_text("- index.html\\n", encoding="utf-8")

    problems = find_site_problems(tmp_path)

    assert any("missing local offline-search shim asset" in problem for problem in problems)


def test_user_guide_site_contract_rejects_omitted_offline_shim(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "llms.txt").write_text("- index.html\\n", encoding="utf-8")

    assert any(
        "missing the offline-search iframe-worker shim" in problem
        for problem in find_site_problems(tmp_path)
    )
