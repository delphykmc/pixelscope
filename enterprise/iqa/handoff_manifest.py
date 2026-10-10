"""Generate and inspect immutable, file-scoped public-safe IQA handoff manifests.

This stdlib-only tool is a downstream transfer aid, NOT an approval authority.
The approved JSON must be published externally after the frozen Git commit/tag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

OWNED_LEAVES = (
    "src/pixelscope_enterprise/iqa/",
    "tests/enterprise/iqa/",
    "docs/enterprise/iqa/",
    "enterprise/iqa/",
)
SHARED_INIT = "src/pixelscope_enterprise/__init__.py"
RESERVED_ROOTS = (
    "src/pixelscope_enterprise/",
    "tests/enterprise/",
    "docs/enterprise/",
    "enterprise/",
)
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
TAG_RE = re.compile(r"handoff/iqa/v[1-9][0-9]*\Z")


class HandoffError(ValueError):
    """A transfer precondition failed without altering downstream files."""


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, check=False
        )
    except OSError as exc:
        raise HandoffError(f"Git is required: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "no detail"
        raise HandoffError(f"git {args[0]} failed: {detail}")
    return result.stdout


def _resolve_commit(root: Path, sha: str) -> str:
    if SHA_RE.fullmatch(sha) is None:
        raise HandoffError("expected an exact lowercase 40-character commit SHA")
    actual = _git(root, "rev-parse", "--verify", f"{sha}^{{commit}}").decode().strip()
    if actual != sha:
        raise HandoffError(f"commit does not resolve exactly: {sha}")
    return actual


def _ancestor(root: Path, earlier: str, later: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", earlier, later],
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise HandoffError("could not verify Git ancestry")
    return result.returncode == 0


def _owned_path(path: str) -> bool:
    if not isinstance(path, str) or "\\" in path or "\x00" in path:
        return False
    parts = PurePosixPath(path).parts
    if not parts or any(part in ("", ".", "..") for part in path.split("/")):
        return False
    return path == SHARED_INIT or any(path.startswith(prefix) for prefix in OWNED_LEAVES)


def _require_owned(path: str) -> str:
    if not _owned_path(path):
        raise HandoffError(f"path outside IQA-owned leaves: {path!r}")
    return path


def _tree(root: Path, sha: str) -> dict[str, tuple[str, str]]:
    raw = _git(root, "ls-tree", "-r", "-z", "--full-tree", sha)
    tree: dict[str, tuple[str, str]] = {}
    for row in raw.split(b"\x00"):
        if not row:
            continue
        try:
            head, path_bytes = row.split(b"\t", 1)
            mode, kind, blob = head.decode("ascii").split(" ")
            path = path_bytes.decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise HandoffError("invalid Git tree entry") from exc
        if not path.startswith(RESERVED_ROOTS):
            continue
        if not _owned_path(path):
            raise HandoffError(f"non-IQA file in reserved handoff roots: {path}")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise HandoffError(f"unsupported Git entry mode/kind at {path}")
        tree[path] = mode, blob
    if not tree:
        raise HandoffError("no IQA-owned files found in approved commit")
    return tree


def _blob(root: Path, sha: str) -> bytes:
    if SHA_RE.fullmatch(sha) is None:
        raise HandoffError("invalid Git blob SHA")
    return _git(root, "cat-file", "blob", sha)


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version", "main_base_sha", "handoff_sha", "contract_revision",
        "approved_tag", "reviewed_by", "approved_at", "transfer_mode",
        "imported_paths", "removed_paths", "validated_tests",
    }
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise HandoffError("manifest lacks required approval/provenance fields")
    if manifest["schema_version"] != 1:
        raise HandoffError("unsupported manifest version")
    for key in ("main_base_sha", "handoff_sha"):
        if not isinstance(manifest[key], str) or SHA_RE.fullmatch(manifest[key]) is None:
            raise HandoffError(f"invalid {key}")
    previous = manifest.get("previous_approved_handoff_sha")
    if previous is not None and (
        not isinstance(previous, str) or SHA_RE.fullmatch(previous) is None
    ):
        raise HandoffError("invalid previous approved SHA")
    if not isinstance(manifest["approved_tag"], str) or TAG_RE.fullmatch(
        manifest["approved_tag"]
    ) is None:
        raise HandoffError("invalid approval tag")
    if manifest["transfer_mode"] not in ("manifest-delta", "history-merge"):
        raise HandoffError("invalid transfer mode")
    if not isinstance(manifest["contract_revision"], int) or (
        isinstance(manifest["contract_revision"], bool) or manifest["contract_revision"] < 1
    ):
        raise HandoffError("invalid public contract revision")
    if not manifest["reviewed_by"] or not manifest["approved_at"]:
        raise HandoffError("missing approval identity/time")
    if not isinstance(manifest["validated_tests"], list) or not manifest["validated_tests"]:
        raise HandoffError("missing owner validation evidence")
    for test in manifest["validated_tests"]:
        if not isinstance(test, dict) or not all(
            test.get(k) for k in ("command", "platform", "python", "outcome")
        ):
            raise HandoffError("invalid owner validation evidence")
    if not isinstance(manifest["imported_paths"], list) or not isinstance(
        manifest["removed_paths"], list
    ):
        raise HandoffError("manifest path lists must be arrays")
    seen: set[str] = set()
    for entry in manifest["imported_paths"]:
        path = _require_owned(entry["path"])
        if path in seen or entry["mode"] not in ("100644", "100755"):
            raise HandoffError(f"duplicate path or invalid mode: {path}")
        if entry["operation"] not in ("add", "update"):
            raise HandoffError(f"invalid import operation: {path}")
        if any(
            not isinstance(entry[key], str) or regex.fullmatch(entry[key]) is None
            for key, regex in (("sha256", HASH_RE), ("git_blob_sha", SHA_RE))
        ):
            raise HandoffError(f"invalid hash at {path}")
        old = entry.get("previous_sha256")
        if entry["operation"] == "update" and (
            not isinstance(old, str) or HASH_RE.fullmatch(old) is None
        ):
            raise HandoffError(f"missing old hash for update: {path}")
        seen.add(path)
    for entry in manifest["removed_paths"]:
        path = _require_owned(entry["path"])
        if path in seen or not isinstance(entry["previous_sha256"], str) or (
            HASH_RE.fullmatch(entry["previous_sha256"]) is None
        ):
            raise HandoffError(f"invalid deletion or duplicate path: {path}")
        seen.add(path)


def _validate_commits(root: Path, manifest: dict[str, Any]) -> None:
    main = _resolve_commit(root, manifest["main_base_sha"])
    handoff = _resolve_commit(root, manifest["handoff_sha"])
    if not _ancestor(root, main, handoff):
        raise HandoffError("approved handoff is not descended from pinned PUBLIC MAIN")
    tag_ref = f"refs/tags/{manifest['approved_tag']}^{{commit}}"
    tagged = _git(root, "rev-parse", "--verify", tag_ref).decode().strip()
    if tagged != handoff:
        raise HandoffError("approved tag does not resolve to manifest handoff SHA")
    previous = manifest.get("previous_approved_handoff_sha")
    if previous is not None:
        _resolve_commit(root, previous)
        if manifest["transfer_mode"] == "history-merge" and not _ancestor(
            root, previous, handoff
        ):
            raise HandoffError("history-merge requires approved SHA ancestry")
    elif manifest["transfer_mode"] == "history-merge":
        raise HandoffError("history-merge requires previous approved SHA")


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_manifest(data)
    return data


def generate(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repo.resolve()
    base = _resolve_commit(root, args.main_base_sha)
    approved = _resolve_commit(root, args.handoff_sha)
    if not _ancestor(root, base, approved):
        raise HandoffError("MAIN base is not an ancestor of handoff")
    tagged = _git(
        root, "rev-parse", "--verify", f"refs/tags/{args.tag}^{{commit}}"
    ).decode().strip()
    if TAG_RE.fullmatch(args.tag) is None or tagged != approved:
        raise HandoffError("approval tag missing or does not point to frozen handoff SHA")
    public_contract = _git(
        root, "show", f"{base}:src/pixelscope/remote/iqa_public_contract.py"
    ).decode("utf-8")
    match = re.search(r"(?m)^IQA_PUBLIC_CONTRACT_REVISION = ([1-9][0-9]*)$", public_contract)
    if match is None:
        raise HandoffError("MAIN does not expose public IQA contract revision")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    previous = _read(args.previous_manifest) if args.previous_manifest else None
    if previous and previous["handoff_sha"] == approved:
        raise HandoffError("new version must differ from previous approved handoff")
    prior = {e["path"]: e for e in previous["imported_paths"]} if previous else {}
    current = _tree(root, approved)
    entries: list[dict[str, str]] = []
    for path, (mode, blob) in sorted(current.items()):
        digest = _hash(_blob(root, blob))
        old = prior.get(path)
        entry = {
            "path": path, "mode": mode, "git_blob_sha": blob,
            "sha256": digest, "operation": "update" if old else "add",
        }
        if old:
            entry["previous_sha256"] = old["sha256"]
        entries.append(entry)
    removals = [
        {"path": path, "previous_sha256": entry["sha256"]}
        for path, entry in sorted(prior.items())
        if path not in current
    ]
    manifest = {
        "schema_version": 1, "main_base_sha": base, "handoff_sha": approved,
        "previous_approved_handoff_sha": previous["handoff_sha"] if previous else None,
        "contract_revision": int(match.group(1)), "approved_tag": args.tag,
        "reviewed_by": args.reviewed_by, "approved_at": args.approved_at,
        "transfer_mode": args.transfer_mode,
        "imported_paths": entries, "removed_paths": removals,
        "validated_tests": evidence,
    }
    _validate_manifest(manifest)
    _validate_commits(root, manifest)
    return manifest


def _target(destination: Path, path: str) -> Path:
    _require_owned(path)
    current = destination
    if current.is_symlink():
        raise HandoffError("destination root must not be a symlink")
    for part in path.split("/"):
        current = current / part
        if current.is_symlink():
            raise HandoffError(f"symlink at imported path: {current}")
    if current.exists() and not current.is_file():
        raise HandoffError(f"non-file import collision: {current}")
    return current


def plan_import(
    repo: Path,
    destination: Path,
    manifest: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> list[tuple[str, Path, bytes | None, str]]:
    """Fail closed before writing; unrelated SUB sibling paths are never inspected."""
    _validate_manifest(manifest)
    _validate_commits(repo, manifest)
    approved_tree = _tree(repo, manifest["handoff_sha"])
    manifest_paths = {item["path"] for item in manifest["imported_paths"]}
    if set(approved_tree) != manifest_paths:
        raise HandoffError("manifest does not exactly cover approved IQA file tree")
    prior_sha = manifest.get("previous_approved_handoff_sha")
    if prior_sha is None and previous is not None:
        raise HandoffError("first handoff cannot have a prior manifest")
    if prior_sha is not None:
        if previous is None:
            raise HandoffError("incremental handoff requires previous approved manifest")
        _validate_manifest(previous)
        _validate_commits(repo, previous)
        if previous["handoff_sha"] != prior_sha:
            raise HandoffError("previous manifest does not match pinned previous SHA")
        prior_paths = {entry["path"]: entry for entry in previous["imported_paths"]}
        expected_removals = set(prior_paths) - manifest_paths
        actual_removals = {entry["path"] for entry in manifest["removed_paths"]}
        if actual_removals != expected_removals:
            raise HandoffError("removed paths do not match prior approved snapshot")
        for entry in manifest["imported_paths"]:
            old = prior_paths.get(entry["path"])
            if old is None and entry["operation"] != "add":
                raise HandoffError("new file must use add operation")
            if old is not None and (
                entry["operation"] != "update"
                or entry["previous_sha256"] != old["sha256"]
            ):
                raise HandoffError("update does not match previous approved hash")
        for entry in manifest["removed_paths"]:
            if entry["previous_sha256"] != prior_paths[entry["path"]]["sha256"]:
                raise HandoffError("deletion does not match prior approved hash")
    actions: list[tuple[str, Path, bytes | None, str]] = []
    for entry in manifest["imported_paths"]:
        path = entry["path"]
        mode, blob_sha = approved_tree[path]
        if (mode, blob_sha) != (entry["mode"], entry["git_blob_sha"]):
            raise HandoffError(f"Git tree mode/blob mismatch: {path}")
        payload = _blob(repo, blob_sha)
        if _hash(payload) != entry["sha256"]:
            raise HandoffError(f"source SHA-256 mismatch: {path}")
        target = _target(destination, path)
        current = _hash(target.read_bytes()) if target.exists() else None
        if current == entry["sha256"]:
            continue
        if entry["operation"] == "add":
            if current is not None:
                raise HandoffError(f"unowned existing path collision: {path}")
        elif current != entry["previous_sha256"]:
            raise HandoffError(f"downstream update collision: {path}")
        actions.append(("write", target, payload, entry["mode"]))
    for entry in manifest["removed_paths"]:
        target = _target(destination, entry["path"])
        if not target.exists():
            continue
        if _hash(target.read_bytes()) != entry["previous_sha256"]:
            raise HandoffError(f"downstream deletion collision: {entry['path']}")
        actions.append(("delete", target, None, ""))
    return actions


def apply_import(actions: list[tuple[str, Path, bytes | None, str]]) -> None:
    """Apply only after approval of preview; preflight must have succeeded."""
    for operation, target, payload, mode in actions:
        if operation == "delete":
            target.unlink()
            continue
        assert payload is not None
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                tmp_path = Path(handle.name)
                handle.write(payload)
            os.chmod(tmp_path, 0o755 if mode == "100755" else 0o644)
            os.replace(tmp_path, target)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate_cmd = sub.add_parser("generate", help="generate *external* approved JSON")
    for flag in ("repo", "handoff-sha", "main-base-sha", "tag", "reviewed-by", "approved-at", "evidence", "output"):
        generate_cmd.add_argument(f"--{flag}", required=True)
    generate_cmd.add_argument("--previous-manifest")
    generate_cmd.add_argument(
        "--transfer-mode", choices=("manifest-delta", "history-merge"),
        default="manifest-delta",
    )
    import_cmd = sub.add_parser("import", help="preflight/dry-run or explicit apply")
    for flag in ("repo", "destination", "manifest"):
        import_cmd.add_argument(f"--{flag}", required=True)
    import_cmd.add_argument("--apply", action="store_true")
    import_cmd.add_argument("--previous-manifest")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            args.repo = Path(args.repo)
            args.evidence = Path(args.evidence)
            args.output = Path(args.output)
            args.previous_manifest = (
                Path(args.previous_manifest) if args.previous_manifest else None
            )
            manifest = generate(args)
            if args.output.exists():
                raise HandoffError("refuse to overwrite existing approval manifest")
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"Generated externally retained approval manifest: {args.output}")
        else:
            manifest = _read(Path(args.manifest))
            previous = (
                _read(Path(args.previous_manifest)) if args.previous_manifest else None
            )
            actions = plan_import(
                Path(args.repo), Path(args.destination), manifest, previous
            )
            for action, target, _, _ in actions:
                print(f"{action}: {target}")
            if args.apply:
                apply_import(actions)
                print(f"Applied {len(actions)} approved file-scoped operations")
            else:
                print("DRY RUN ONLY; repeat with --apply after owner diff approval")
    except (HandoffError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
