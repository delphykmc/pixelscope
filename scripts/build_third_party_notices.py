from __future__ import annotations

import platform
import re
import sys
from importlib import metadata
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.distribution_contract import notice_path  # noqa: E402
from scripts.release_contract import REPO_ROOT  # noqa: E402

RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements" / "runtime.txt"
_LICENSE_PREFIXES = ("license", "licence", "copying", "notice")


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def required_runtime_distributions() -> tuple[str, ...]:
    names: list[str] = []
    for raw_line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
        if not name:
            raise RuntimeError(f"Unable to parse runtime requirement: {raw_line!r}")
        names.append(name)
    return tuple(names)


def _python_license_path() -> Path:
    candidates = (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    raise RuntimeError(
        "CPython runtime license was not found under sys.base_prefix; "
        "the release notice payload cannot be generated"
    )


def _distribution_license_files(dist: metadata.Distribution) -> tuple[Path, ...]:
    found: dict[str, Path] = {}
    for package_file in dist.files or ():
        basename = Path(str(package_file)).name.casefold()
        if not basename.startswith(_LICENSE_PREFIXES):
            continue
        candidate = Path(dist.locate_file(package_file))
        if not candidate.is_file() or candidate.stat().st_size == 0:
            continue
        found[str(candidate.resolve()).casefold()] = candidate
    return tuple(sorted(found.values(), key=lambda path: str(path).casefold()))


def _project_urls(dist: metadata.Distribution) -> tuple[str, ...]:
    values = dist.metadata.get_all("Project-URL") or []
    return tuple(str(value).strip() for value in values if str(value).strip())


def _license_metadata(dist: metadata.Distribution) -> str:
    expression = dist.metadata.get("License-Expression")
    if expression and str(expression).strip():
        return str(expression).strip()
    value = dist.metadata.get("License")
    if value and str(value).strip():
        return str(value).strip()
    return ""


def _installed_distributions() -> tuple[metadata.Distribution, ...]:
    distributions = [
        dist
        for dist in metadata.distributions()
        if _normalize_distribution_name(str(dist.metadata.get("Name") or ""))
        != "pixelscope"
    ]
    return tuple(
        sorted(
            distributions,
            key=lambda dist: _normalize_distribution_name(
                str(dist.metadata.get("Name") or "")
            ),
        )
    )


def _validate_runtime_inventory(distributions: tuple[metadata.Distribution, ...]) -> None:
    by_name = {
        _normalize_distribution_name(str(dist.metadata.get("Name") or "")): dist
        for dist in distributions
    }
    missing: list[str] = []
    incomplete_license: list[str] = []
    for requirement in required_runtime_distributions():
        normalized = _normalize_distribution_name(requirement)
        dist = by_name.get(normalized)
        if dist is None:
            missing.append(requirement)
            continue
        if not _distribution_license_files(dist) and not _license_metadata(dist):
            incomplete_license.append(requirement)
    if missing:
        raise RuntimeError(f"Release environment is missing runtime distributions: {missing}")
    if incomplete_license:
        raise RuntimeError(
            "Runtime distributions have no discoverable license metadata/files: "
            f"{incomplete_license}"
        )


def render_third_party_notices() -> str:
    distributions = _installed_distributions()
    _validate_runtime_inventory(distributions)
    python_license_path = _python_license_path()
    python_license = python_license_path.read_text(encoding="utf-8", errors="replace")

    lines = [
        "PixelScope Third-Party Notices",
        "==============================",
        "",
        "Generated from the isolated PixelScope release environment.",
        "This inventory records release/runtime license material and does not replace",
        "final corporate legal or release-policy approval.",
        "",
        f"CPython runtime: Python {platform.python_version()}",
        f"Bundled license file: {python_license_path.name}",
        "",
        python_license.rstrip(),
        "",
    ]

    for dist in distributions:
        name = str(dist.metadata.get("Name") or "<unknown>")
        version = str(dist.version or "<unknown>")
        lines.extend(("", "-" * 80, "", f"{name} {version}"))
        license_value = _license_metadata(dist)
        if license_value:
            lines.append(f"License metadata: {license_value}")
        for project_url in _project_urls(dist):
            lines.append(f"Project-URL: {project_url}")

        license_files = _distribution_license_files(dist)
        if not license_files:
            lines.extend(("", "No bundled license/copying/notice file was discovered."))
            continue
        for license_file in license_files:
            lines.extend(
                (
                    "",
                    f"Bundled license file: {license_file.name}",
                    "",
                    license_file.read_text(encoding="utf-8", errors="replace").rstrip(),
                )
            )

    return "\n".join(lines).rstrip() + "\n"


def write_third_party_notices(destination: Path | None = None) -> Path:
    output = (destination or notice_path()).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_third_party_notices(), encoding="utf-8")
    return output


def main() -> int:
    output = write_third_party_notices()
    print(f"Third-party notices written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
