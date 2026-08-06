from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "AGENTS.md",
    "README.md",
    ".github/pull_request_template.md",
    "docs/index.md",
    "docs/CURRENT_STATE.md",
    "docs/PRODUCT_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/PACKAGING_CONSTRAINTS.md",
    "docs/USER_GUIDE.md",
    "docs/QUALITY.md",
    "docs/AGENT_HARNESS_NOTES.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/active/next-phase.md",
)

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def markdown_files(root: Path) -> list[Path]:
    files = [root / "AGENTS.md", root / "README.md"]
    files.extend(sorted((root / "docs").rglob("*.md")))
    return [path for path in files if path.is_file()]


def local_link_target(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if not target or target.startswith("#"):
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split(maxsplit=1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    relative_path = unquote(parsed.path)
    if not relative_path:
        return None
    return (document.parent / relative_path).resolve()


def find_problems(root: Path = ROOT) -> list[str]:
    repository_root = root.resolve()
    problems: list[str] = []

    for relative in REQUIRED_PATHS:
        path = repository_root / relative
        if not path.exists():
            problems.append(f"missing required path: {relative}")

    for document in markdown_files(repository_root):
        text = document.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = local_link_target(document, match.group(1))
            if target is None:
                continue
            try:
                target.relative_to(repository_root)
            except ValueError:
                problems.append(
                    f"{document.relative_to(repository_root)}: link escapes repository: "
                    f"{match.group(1)}"
                )
                continue
            if not target.exists():
                problems.append(
                    f"{document.relative_to(repository_root)}: broken local link: "
                    f"{match.group(1)}"
                )

    return problems


def main() -> int:
    problems = find_problems()
    if problems:
        print("Documentation contract failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Documentation contract passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
