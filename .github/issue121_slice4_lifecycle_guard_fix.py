from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new)


def main() -> None:
    path = Path("tests/unit/test_qt_lifecycle_architecture.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '    "src/pixelscope/ui/iqa_client_install.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n'
        '    "src/pixelscope/ui/iqa_submission.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n',
        '    "src/pixelscope/ui/iqa_client_install.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n',
        "remove over-broad submission owner guard",
    )

    marker = "\ndef test_production_composition_uses_final_rank4_non_owning_adapters() -> None:\n"
    dedicated_test = '''\ndef test_public_iqa_execution_controller_does_not_retain_main_window() -> None:\n    relative_path = "src/pixelscope/ui/iqa_submission.py"\n    tree = ast.parse(\n        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"),\n        filename=relative_path,\n    )\n    controller = next(\n        node\n        for node in tree.body\n        if isinstance(node, ast.ClassDef)\n        and node.name == "PublicIqaExecutionController"\n    )\n    violations: list[str] = []\n    for node in ast.walk(controller):\n        if not isinstance(node, ast.Assign) or _root_name(node.value) != "window":\n            continue\n        for target in node.targets:\n            if (\n                isinstance(target, ast.Attribute)\n                and isinstance(target.value, ast.Name)\n                and target.value.id == "self"\n            ):\n                violations.append(\n                    f"{relative_path}:{node.lineno}: self.{target.attr} retains window"\n                )\n    assert violations == []\n\n'''
    text = replace_once(
        text,
        marker,
        dedicated_test + marker,
        "dedicated public controller owner guard",
    )
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
