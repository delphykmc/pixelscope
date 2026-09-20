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
