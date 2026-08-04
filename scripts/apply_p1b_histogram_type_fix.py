from __future__ import annotations

from pathlib import Path

PANEL = Path("src/pixelscope/ui/comparison_analysis_panel.py")


def main() -> int:
    original = PANEL.read_text(encoding="utf-8")
    old = "        return np.log10(values + 1.0)\n"
    new = (
        "        return np.asarray(\n"
        "            np.log10(values + 1.0),\n"
        "            dtype=np.float64,\n"
        "        )\n"
    )
    if new in original:
        print("P1-B histogram typing fix already applied")
        return 0
    count = original.count(old)
    if count != 1:
        raise RuntimeError(f"expected one log-count return, found {count}")
    PANEL.write_text(original.replace(old, new, 1), encoding="utf-8")
    print(f"Applied P1-B histogram typing fix to {PANEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
