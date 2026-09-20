from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.search_user_guide import GUIDE_ROOT, main, search_guide


def _write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_source_search_returns_real_markdown_line_and_site_route(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "workflows/compare-folders.md",
        "# Compare folder positions\n\n"
        "## Atomic movement\n"
        "Use PageUp to compare folder positions without partial movement.\n"
        "Read Primary in the comparison view.\n",
    )
    matches = search_guide("How do I compare folder positions?", docs_root=tmp_path)
    assert len(matches) == 1
    result = matches[0]
    assert result.title == "Compare folder positions"
    assert result.heading == "Atomic movement"
    assert result.source == "docs/user-guide/workflows/compare-folders.md"
    assert result.route == "workflows/compare-folders.html"
    assert result.line == 4
    assert "PageUp" in result.snippet


def test_heading_only_hit_cites_matching_heading_not_unrelated_body(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "features/needle.md",
        "# Needle\n\nUnrelated introductory text.\n\n" "## Another topic\nStill unrelated prose.\n",
    )
    matches = search_guide("Needle", docs_root=tmp_path)
    assert len(matches) == 2
    # The H1 section matches both the heading and title; later section only
    # inherits the document title. Both must cite the real matching H1 line.
    assert [(match.line, match.snippet) for match in matches] == [
        (1, "Needle"),
        (1, "Needle"),
    ]


def test_subheading_only_hit_cites_subheading_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "features/tools.md",
        "# Tools\n\nIntroduction.\n\n" "## Rareword\nBody unrelated to the query.\n",
    )
    matches = search_guide("Rareword", docs_root=tmp_path)
    assert len(matches) == 1
    assert matches[0].line == 5
    assert matches[0].snippet == "Rareword"


def test_source_search_never_indexes_fenced_code_or_screenshot_assets(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "index.md",
        "# Guide\n\nIntro text.\n\n"
        "~~~python\n"
        "# phantom-only-heading\n"
        "password_needle\n"
        "~~~\n",
    )
    _write(tmp_path, "assets/screenshots/README.md", "# password_needle\nScreenshot notes.\n")
    assert search_guide("password_needle", docs_root=tmp_path) == []
    assert search_guide("phantom-only-heading", docs_root=tmp_path) == []


def test_search_ranking_and_order_are_stable(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "features/difference.md",
        "# Difference\n\n## Difference unavailable\nDifference unavailable for mismatched types.\n",
    )
    _write(
        tmp_path,
        "troubleshooting/index.md",
        "# Troubleshooting\n\n## Other symptoms\nDifference may be unavailable.\n",
    )
    first = search_guide("Difference unavailable", docs_root=tmp_path, limit=1)
    assert first[0].source == "docs/user-guide/features/difference.md"
    assert first == search_guide("Difference unavailable", docs_root=tmp_path, limit=1)


def test_search_unicode_json_and_empty_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "index.md", "# Korean guide\n\n## 진단\n한글 검사 도구.\n")
    found = search_guide("한글 검사", docs_root=tmp_path)
    assert found and "한글" in found[0].snippet
    assert search_guide("nonexistenttoken", docs_root=tmp_path) == []
    # CLI deliberately uses only its checked-in source by default, not test injection.
    assert main(["RAW14", "--json", "--limit", "2"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response and all("source" in item and "line" in item for item in response)
    assert all(item["source"].startswith("docs/user-guide/") for item in response)


@pytest.mark.parametrize("query", ["", "How do I?", " " * 3, "x" * 2001])
def test_search_rejects_empty_or_unbounded_query(query: str) -> None:
    with pytest.raises(ValueError):
        search_guide(query)


@pytest.mark.parametrize("limit", [0, -1, 21])
def test_search_rejects_unbounded_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        search_guide("RAW14", limit=limit)


def test_real_source_routes_exist_in_guide() -> None:
    matches = search_guide("RAW14", docs_root=GUIDE_ROOT)
    assert matches
    for match in matches:
        assert (GUIDE_ROOT / Path(match.route).with_suffix(".md")).is_file()
        assert match.line > 0
