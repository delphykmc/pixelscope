import ast

from scripts.check_docs import ROOT, find_problems, guide_nav_index_problems


def test_repository_documentation_contract() -> None:
    assert find_problems(ROOT) == []


def test_added_mkdocs_nav_page_must_be_in_agent_index() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    llms = (ROOT / "docs/user-guide/llms.txt").read_text(encoding="utf-8")
    assert guide_nav_index_problems(mkdocs, llms) == []

    added_nav = mkdocs.replace(
        "  - Troubleshooting: troubleshooting/index.md",
        "  - Future feature: features/future-feature.md\n"
        "  - Troubleshooting: troubleshooting/index.md",
    )
    assert added_nav != mkdocs
    # The old hard-coded critical list does not include this new page.
    missing = guide_nav_index_problems(added_nav, llms)
    assert missing == [
        "docs/user-guide/llms.txt: expected exactly one route for "
        "features/future-feature.html, found 0"
    ]

    updated = llms + "\n- features/future-feature.html\n"
    assert guide_nav_index_problems(added_nav, updated) == []
    assert any(
        "features/future-feature.html, found 2" in problem
        for problem in guide_nav_index_problems(
            added_nav, updated + "- features/future-feature.html\n"
        )
    )


def test_display_gain_guide_matches_runtime_source() -> None:
    # Documentation CI intentionally has no Qt/runtime dependency.
    source = ROOT / "src/pixelscope/ui"
    shortcuts = ast.parse(
        (source / "display_gain_shortcuts.py").read_text(encoding="utf-8")
    )
    keys = {
        node.args[0].value
        for node in ast.walk(shortcuts)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "QKeySequence"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    gain = ast.parse((source / "display_gain.py").read_text(encoding="utf-8"))
    options = next(
        ast.literal_eval(node.value)
        for node in gain.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DISPLAY_GAIN_OPTIONS"
            for target in node.targets
        )
    )
    guide = ROOT / "docs/user-guide"
    reference = (guide / "reference/keyboard-shortcuts.md").read_text(encoding="utf-8")
    image_view = (guide / "features/image-view.md").read_text(encoding="utf-8")
    gain_row = next(line for line in reference.splitlines() if "shared Display Gain" in line)
    documented_keys = set(gain_row.split("|")[1].replace("`", "").strip().split(" / "))
    assert keys == documented_keys
    for key in keys:
        assert f"`{key}`" in image_view
    assert ", ".join(f"{value:g}×" for value in options) in reference
    assert all(f"`{value:g}×`" in image_view for value in options)
    for page in (reference, image_view):
        assert "0.5 EV" not in page
        assert "`[`" not in page
        assert "`]`" not in page
