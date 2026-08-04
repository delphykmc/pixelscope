from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    original = MAIN_WINDOW.read_text(encoding="utf-8")
    updated = original
    updated = replace_once(
        updated,
        "            document.error_state or str(document.source_path or \"\"),\n"
        "        )\n"
        "        if select:\n",
        "            document.error_state or str(document.source_path or \"\"),\n"
        "            loading_state=document.loading_state,\n"
        "            resident=document.source is not None,\n"
        "        )\n"
        "        if select:\n",
        "programmatic document residency arguments",
    )
    updated = replace_once(
        updated,
        "            image_input.path,\n"
        "            str(image_input.path),\n"
        "        )\n"
        "        return document.document_id\n",
        "            image_input.path,\n"
        "            str(image_input.path),\n"
        "            loading_state=document.loading_state,\n"
        "            resident=False,\n"
        "        )\n"
        "        return document.document_id\n",
        "registered input residency arguments",
    )
    updated = replace_once(
        updated,
        "                loading_state=document.loading_state,\n"
        "            )\n\n"
        "    def show_selected_image",
        "                loading_state=document.loading_state,\n"
        "                resident=document.source is not None,\n"
        "            )\n\n"
        "    def show_selected_image",
        "Files residency state propagation",
    )
    if updated == original:
        print("P1-A Files residency patch was already applied")
        return 0
    MAIN_WINDOW.write_text(updated, encoding="utf-8")
    print(f"Applied P1-A Files residency patch to {MAIN_WINDOW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
