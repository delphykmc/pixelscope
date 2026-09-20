from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_LINK_RELS = {
    "apple-touch-icon",
    "icon",
    "manifest",
    "modulepreload",
    "preload",
    "stylesheet",
}
SITE_ROUTE = re.compile(r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.html\b")
CSS_REMOTE_RESOURCE = re.compile(
    r"(?:url\(\s*|@import\s+)[\"']?(?P<url>(?:https?:)?//[^\"')\s;]+)",
    re.IGNORECASE,
)


def is_remote_url(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith("//"):
        return True
    return urlsplit(candidate).scheme.lower() in {"http", "https"}


class ResourceReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}

        for attribute in ("src", "poster"):
            value = attributes.get(attribute)
            if value:
                self.references.append(value)

        srcset = attributes.get("srcset")
        if srcset:
            for candidate in srcset.split(","):
                url = candidate.strip().split(maxsplit=1)[0]
                if url:
                    self.references.append(url)

        if tag == "link":
            rels = set(attributes.get("rel", "").lower().split())
            href = attributes.get("href")
            if href and rels.intersection(RESOURCE_LINK_RELS):
                self.references.append(href)


def find_site_problems(site_root: Path) -> list[str]:
    site_root = site_root.resolve()
    problems: list[str] = []

    if not site_root.is_dir():
        return [f"missing generated site directory: {site_root}"]

    llms_path = site_root / "llms.txt"
    if not llms_path.is_file():
        problems.append("generated site is missing llms.txt")
    else:
        llms_text = llms_path.read_text(encoding="utf-8")
        if ".md" in llms_text:
            problems.append(
                "site/llms.txt contains Markdown source routes; use generated .html routes"
            )

        routes = SITE_ROUTE.findall(llms_text)
        if not routes:
            problems.append("site/llms.txt does not contain any generated .html routes")
        for route in sorted(set(routes)):
            if not (site_root / route).is_file():
                problems.append(f"site/llms.txt points to missing site route: {route}")

    for html_path in sorted(site_root.rglob("*.html")):
        parser = ResourceReferenceParser()
        parser.feed(html_path.read_text(encoding="utf-8"))
        if html_path == site_root / "index.html" and not any(
            "iframe-worker" in reference for reference in parser.references
        ):
            problems.append("site/index.html is missing the offline-search iframe-worker shim")

        for reference in parser.references:
            if is_remote_url(reference):
                relative = html_path.relative_to(site_root)
                problems.append(
                    f"{relative}: remote resource dependency is not offline-safe: " f"{reference}"
                )
            elif "iframe-worker" in urlsplit(reference).path:
                local_path = (html_path.parent / unquote(urlsplit(reference).path)).resolve()
                if not local_path.is_file():
                    relative = html_path.relative_to(site_root)
                    problems.append(
                        f"{relative}: missing local offline-search shim asset: {reference}"
                    )

    for css_path in sorted(site_root.rglob("*.css")):
        css_text = css_path.read_text(encoding="utf-8")
        for match in CSS_REMOTE_RESOURCE.finditer(css_text):
            relative = css_path.relative_to(site_root)
            problems.append(
                f"{relative}: remote CSS resource dependency is not offline-safe: "
                f"{match.group('url')}"
            )

    return problems


def main() -> int:
    site_root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    problems = find_site_problems(site_root)
    if problems:
        print("Generated User Guide artifact contract failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Generated User Guide artifact contract passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
