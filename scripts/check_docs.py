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
    "mkdocs.yml",
    "requirements/docs.txt",
    "docs/index.md",
    "docs/CURRENT_STATE.md",
    "docs/PRODUCT_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/ROADMAP.md",
    "docs/PACKAGING_CONSTRAINTS.md",
    "docs/USER_GUIDE.md",
    "docs/USER_GUIDE_PRE_MKDOCS.md",
    "docs/USER_GUIDE_FOLLOW_UP.md",
    "docs/QUALITY.md",
    "docs/AGENT_HARNESS_NOTES.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/active/next-phase.md",
    "docs/user-guide/index.md",
    "docs/user-guide/getting-started/quick-start.md",
    "docs/user-guide/formats/raw.md",
    "docs/user-guide/formats/yuv.md",
    "docs/user-guide/reference/keyboard-shortcuts.md",
    "docs/user-guide/reference/terminology.md",
    "docs/user-guide/troubleshooting/index.md",
    "docs/user-guide/assets/screenshots/README.md",
    "docs/user-guide/llms.txt",
)

CRITICAL_GUIDE_NAV = (
    "index.md",
    "getting-started/installation.md",
    "getting-started/quick-start.md",
    "getting-started/concepts.md",
    "workflows/open-images.md",
    "workflows/open-folders.md",
    "workflows/compare-images.md",
    "workflows/compare-many-images.md",
    "workflows/compare-folder-positions.md",
    "workflows/inspect-roi.md",
    "workflows/inspect-histogram.md",
    "workflows/inspect-line-profile.md",
    "workflows/use-difference.md",
    "workflows/save-and-restore-work.md",
    "features/files-workspace.md",
    "features/image-view.md",
    "features/statistics.md",
    "features/histogram.md",
    "features/line-profile.md",
    "features/difference.md",
    "features/plots-workspace.md",
    "features/iqa-workspace.md",
    "features/settings.md",
    "formats/standard-images.md",
    "formats/raw.md",
    "formats/yuv.md",
    "reference/keyboard-shortcuts.md",
    "reference/supported-formats.md",
    "reference/settings.md",
    "reference/terminology.md",
    "troubleshooting/index.md",
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

    mkdocs_path = repository_root / "mkdocs.yml"
    if mkdocs_path.is_file():
        mkdocs_text = mkdocs_path.read_text(encoding="utf-8")
        for page in CRITICAL_GUIDE_NAV:
            marker = f": {page}"
            count = mkdocs_text.count(marker)
            if count != 1:
                problems.append(
                    f"mkdocs.yml: expected exactly one nav entry for {page}, found {count}"
                )

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
