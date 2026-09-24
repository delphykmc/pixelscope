"""WP-Help-E4: pinned Windows base/head real-QWidget capture and review artifacts.

No push, no secrets, no silent fallback to offscreen, no fake UI captures.
Every leg executes a separate Python process with its own PYTHONPATH rooted at
the pinned checkout. A reviewed PNG is never replaced automatically.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.compare_ui_screenshots import (  # noqa: E402
    compare_pair,
    documentation_relation,
    scene_contract,
)
from scripts.run_ui_capture_poc import assess_capture_process, sanitized_stderr  # noqa: E402
from scripts.select_ui_screenshots import (  # noqa: E402
    _git_text,
    git_changed_files,
    resolve_sha,
    select_changes,
)

SHA = re.compile(r"[0-9a-f]{40}")
TIMEOUT = 100


def _read_manifest(root: Path) -> dict[str, Any]:
    data = json.loads((root / "docs/user-guide/assets/screenshots/manifest.json").read_text(
        encoding="utf-8"
    ))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported screenshot manifest")
    return data


def _pinned(root: Path, sha: str) -> None:
    if SHA.fullmatch(sha) is None or resolve_sha(root, sha) != sha:
        raise ValueError("revision must be a complete immutable Git commit SHA")
    actual = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    if actual != sha:
        raise ValueError("checkout HEAD is not the requested pinned revision")


def _env(root: Path) -> dict[str, str]:
    result = os.environ.copy()
    result["PYTHONHASHSEED"] = "0"
    result["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))
    if result.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        raise ValueError("offscreen Qt cannot qualify as native Windows screenshot CI")
    return result


def _execute(root: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=TIMEOUT,
    )


def renderer_environment(
    root: Path, output: Path, probe: Path
) -> dict[str, Any]:
    process = _execute(root, [str(probe), "--output", str(output)], _env(root))
    if process.returncode or not output.is_file():
        raise ValueError(
            "renderer probe failed: " + sanitized_stderr(process.stderr)
        )
    result = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("primary_screen") is None:
        raise ValueError("renderer probe lacks an active Windows screen")
    return result


def capture_scene(
    root: Path, sha: str, scene: str, folder: Path
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    folder.mkdir(parents=True, exist_ok=True)
    png, meta = folder / "capture.png", folder / "capture.json"
    process_info: dict[str, Any] = {"source_sha": sha, "scenario": scene}
    try:
        command = [
            str(root / "scripts/capture_ui_scene.py"),
            "--scene", scene, "--output", str(png),
            "--metadata", str(meta), "--source-sha", sha,
        ]
        process = _execute(root, command, _env(root))
        process_info["exit_code"] = process.returncode
        process_info["stderr"] = sanitized_stderr(process.stderr)
        observed = assess_capture_process(process, png, meta, scene, sha)
        return observed, process_info
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        process_info["failure"] = type(exc).__name__
        process_info["error"] = (
            str(exc)[:150] if isinstance(exc, ValueError) else type(exc).__name__
        )
        return None, process_info


def _write_report(output: Path, report: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    cases = report.get("screenshots", [])
    counts = Counter(row["status"] for row in cases)
    lines = [
        "# WP-Help-E4 pinned Windows real-QWidget screenshot diff",
        "",
        f"- Base SHA: `{report['base_sha']}`",
        f"- Head SHA: `{report['head_sha']}`",
        f"- Overall: **{report['status']}**",
        "- All captured screenshots are PR artifacts, not approved guide PNGs.",
        "- Exact decoded pixels decide CHANGED; diagnostic tolerances cannot hide labels.",
        "- Legacy screenshot mismatch is review debt, not proof of historical provenance.",
        "",
        "## Screenshot statuses",
        "",
    ]
    lines += [f"- {status}: {count}" for status, count in sorted(counts.items())]
    for row in cases:
        lines.append(
            f"- `{row['id']}`: **{row['status']}**"
            + (f" — {row['reason']}" if "reason" in row else "")
        )
    if report.get("warnings"):
        lines += ["", "## Coverage warnings", ""]
        lines += [f"- {w}" for w in report["warnings"]]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    base_root: Path, head_root: Path, base_sha: str, head_sha: str, output: Path
) -> int:
    if os.name != "nt":
        raise ValueError("E4 real-QWidget captures require Windows, not offscreen")
    if base_root.resolve() == head_root.resolve():
        raise ValueError("base/head must be separate checkout directories")
    _pinned(base_root, base_sha)
    _pinned(head_root, head_sha)
    base_manifest, head_manifest = _read_manifest(base_root), _read_manifest(head_root)
    # Read real pinned Markdown on both sides: prose-only changes select none.
    selection = select_changes(
        git_changed_files(head_root, base_sha, head_sha),
        base_manifest,
        head_manifest,
        base_sha=base_sha,
        head_sha=head_sha,
        read_at_revision=lambda sha, path: _git_text(head_root, sha, path),
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "runner_os": platform.platform(),
        "selection": selection,
        "warnings": selection["warnings"],
        "screenshots": [],
        "status": "failed",
    }
    output.mkdir(parents=True, exist_ok=True)
    failed = False
    try:
        if not selection["selected_ids"]:
            report["status"] = "no affected screenshots"
            return 0
        old = {row["id"]: row for row in base_manifest["screenshots"]}
        new = {row["id"]: row for row in head_manifest["screenshots"]}
        compatible_runtime = (
            (base_root / "requirements/runtime.txt").read_bytes()
            == (head_root / "requirements/runtime.txt").read_bytes()
            and (base_root / "pyproject.toml").read_bytes()
            == (head_root / "pyproject.toml").read_bytes()
        )
        base_env = head_env = None
        if compatible_runtime:
            probe = ROOT / "scripts/probe_ui_screenshot_environment.py"
            base_env = renderer_environment(base_root, output / "base-environment.json", probe)
            head_env = renderer_environment(head_root, output / "head-environment.json", probe)
        else:
            report["warnings"].append("different pinned runtime packaging/dependencies")
        for key in selection["selected_ids"]:
            selected = next(item for item in selection["selected_screenshots"] if item["id"] == key)
            row: dict[str, Any] = {
                "id": key,
                "capture_mode": selected["capture_mode"],
                "selected_reasons": selected["reasons"],
            }
            report["screenshots"].append(row)
            if key not in new:
                row["status"] = "REMOVED_REVIEW"
                continue
            if new[key]["capture_mode"] != "isolated":
                row["status"] = "DEFERRED_REVIEW"
                row["reason"] = "scene has no verified isolated real-UI builder"
                continue
            if not compatible_runtime:
                row["status"] = "BASELINE_INCOMPATIBLE"
                row["reason"] = "pinned runtime packaging/dependencies differ"
                continue
            head_dir = output / key / "head"
            head_meta, head_process = capture_scene(
                head_root, head_sha, new[key]["scenario"], head_dir
            )
            row["head_process"] = head_process
            if head_meta is None:
                row["status"] = "CAPTURE_FAILED_HEAD"
                failed = True
                continue
            if key not in old or old[key]["capture_mode"] != "isolated":
                row["status"] = "NEW_REVIEW"
                row["reason"] = "no comparable isolated builder in pinned base"
                row["documentation"] = documentation_relation(
                    head_root, new[key], head_dir / "capture.png"
                )
                continue
            # Do not run unrelated base scenario just to fabricate a comparison.
            if old[key]["scenario"] != new[key]["scenario"]:
                row["status"] = "BASELINE_INCOMPATIBLE"
                row["reason"] = "different scene implementations"
                continue
            base_dir = output / key / "base"
            base_meta, base_process = capture_scene(
                base_root, base_sha, old[key]["scenario"], base_dir
            )
            row["base_process"] = base_process
            if base_meta is None:
                row["status"] = "CAPTURE_FAILED_BASE"
                failed = True
                continue
            try:
                result = compare_pair(
                    base_dir / "capture.png", head_dir / "capture.png",
                    base_meta, head_meta, base_env, head_env,
                    scene_contract(base_root, old[key]["scenario"]),
                    scene_contract(head_root, new[key]["scenario"]),
                    old[key], new[key], output / key / "comparison",
                )
            except (OSError, ValueError, SyntaxError) as exc:
                result = {"status": "COMPARISON_FAILED", "reason": type(exc).__name__}
            row.update(result)
            row["documentation"] = documentation_relation(
                head_root, new[key], head_dir / "capture.png"
            )
            if result["status"] == "COMPARISON_FAILED":
                failed = True
        report["status"] = "failed" if failed else "passed"
        return 1 if failed else 0
    finally:
        _write_report(output, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(
            args.base_root.resolve(), args.head_root.resolve(),
            args.base_sha, args.head_sha, args.output_dir.resolve(),
        )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        _write_report(
            args.output_dir.resolve(),
            {
                "base_sha": args.base_sha,
                "head_sha": args.head_sha,
                "status": "failed",
                "warnings": ["E4 infrastructure/selection failure: " + type(exc).__name__],
                "screenshots": [],
            },
        )
        print(f"E4 failed: {type(exc).__name__}: {str(exc)[:150]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
