"""Deterministic, offline search of canonical PixelScope User Guide Markdown.

This is repository-side tooling for users/agents, not an application chatbot.
No network, embeddings, authentication, image files or generated-site state.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

GUIDE_ROOT = Path(__file__).resolve().parents[1] / "docs" / "user-guide"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "can",
        "do",
        "does",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "the",
        "to",
        "what",
        "when",
        "where",
        "why",
        "with",
    }
)


@dataclass(frozen=True)
class GuideMatch:
    title: str
    heading: str
    source: str
    route: str
    line: int
    snippet: str


@dataclass(frozen=True)
class _Section:
    title: str
    heading: str
    source: str
    route: str
    start: int
    lines: tuple[tuple[int, str], ...]


def _tokens(value: str) -> list[str]:
    return [match.group().casefold() for match in _TOKEN.finditer(value)]


def _plain(value: str) -> str:
    return _LINK.sub(r"\1", value).strip()


def _sections(path: Path, root: Path) -> list[_Section]:
    relative = path.relative_to(root)
    source = (Path("docs/user-guide") / relative).as_posix()
    route = relative.with_suffix(".html").as_posix()
    title = relative.stem.replace("-", " ").title()
    heading = title
    start = 1
    lines: list[tuple[int, str]] = []
    sections: list[_Section] = []
    fence: str | None = None

    def flush() -> None:
        if lines:
            sections.append(_Section(title, heading, source, route, start, tuple(lines)))

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            if fence is None:
                fence = marker.group()[0]
            elif marker.group()[0] == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = _HEADING.match(line)
        if match:
            flush()
            heading = _plain(match.group(2))
            if len(match.group(1)) == 1:
                title = heading
            start = line_number
            lines = []
        elif stripped:
            lines.append((line_number, _plain(stripped)))
    flush()
    return sections


def _rank(section: _Section, terms: list[str], phrase: str) -> int:
    title = _tokens(section.title)
    heading = _tokens(section.heading)
    body = [token for _, line in section.lines for token in _tokens(line)]
    available = set(title + heading + body)
    matched = [term for term in terms if term in available]
    if not matched:
        return 0
    score = sum(
        8 * title.count(term) + 5 * heading.count(term) + min(body.count(term), 4) for term in terms
    )
    if len(matched) == len(terms):
        score += 10
    if phrase and phrase in section.heading.casefold():
        score += 5
    return score


def _snippet(section: _Section, terms: list[str], *, max_chars: int = 260) -> tuple[int, str]:
    best_line, best_text = max(
        section.lines,
        key=lambda item: (
            sum(term in _tokens(item[1]) for term in terms),
            -item[0],
        ),
    )
    snippet = best_text
    if len(snippet) > max_chars:
        # Prefer context surrounding the first matched term rather than an
        # unrelated prefix of a long section paragraph.
        lowered = snippet.casefold()
        positions = [lowered.find(term) for term in terms if term in lowered]
        center = min(positions) if positions else 0
        start = max(0, center - 60)
        end = min(len(snippet), start + max_chars)
        snippet = ("…" if start else "") + snippet[start:end]
        if end < len(best_text):
            snippet += "…"
    return best_line, snippet


def search_guide(query: str, *, docs_root: Path = GUIDE_ROOT, limit: int = 5) -> list[GuideMatch]:
    """Return bounded, stable matches with Markdown source lines and site routes."""
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    if len(query) > 2000:
        raise ValueError("query exceeds 2000 characters")
    terms = list(dict.fromkeys(term for term in _tokens(query) if term not in _STOP))
    if not terms:
        raise ValueError("query must contain a meaningful search term")
    if not docs_root.is_dir():
        raise ValueError(f"User Guide source directory not found: {docs_root}")

    results: list[tuple[int, GuideMatch]] = []
    for path in sorted(docs_root.rglob("*.md")):
        if "assets" in path.relative_to(docs_root).parts or path.is_symlink():
            continue
        for section in _sections(path, docs_root):
            if not section.lines:
                continue
            score = _rank(section, terms, query.strip().casefold())
            if not score:
                continue
            line, snippet = _snippet(section, terms)
            results.append(
                (
                    score,
                    GuideMatch(
                        section.title,
                        section.heading,
                        section.source,
                        section.route,
                        line,
                        snippet,
                    ),
                )
            )
    results.sort(key=lambda item: (-item[0], item[1].source, item[1].line))
    return [match for _, match in results[:limit]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the local PixelScope User Guide")
    parser.add_argument("query", help="Words or question to search (never sent to a server)")
    parser.add_argument("--limit", type=int, default=5, help="Maximum results: 1–20")
    parser.add_argument("--json", action="store_true", help="Machine-readable results")
    args = parser.parse_args(argv)
    try:
        matches = search_guide(args.query, limit=args.limit)
    except ValueError as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps([asdict(match) for match in matches], ensure_ascii=False, indent=2))
    elif matches:
        for match in matches:
            print(f"{match.source}:{match.line} [{match.heading}] -> {match.route}")
            print(f"  {match.snippet}")
    else:
        print("No local User Guide matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
