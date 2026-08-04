from __future__ import annotations

import math

PLOT_TITLE_MAX_CHARS = 72


def middle_elide(text: str, max_chars: int = PLOT_TITLE_MAX_CHARS) -> str:
    """Return a compact middle-elided label while preserving both path ends."""

    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    remaining = max_chars - 1
    left = (remaining + 1) // 2
    right = remaining - left
    return f"{text[:left]}…{text[-right:]}" if right else f"{text[:left]}…"


def plot_number(value: float) -> str:
    """Format finite plot coordinates and values compactly and consistently."""

    if not math.isfinite(value):
        return str(value)
    return f"{value:.6g}"


def coordinate_header(label: str, value: float, unit: str | None = None) -> str:
    """Format the shared hover coordinate without redundant x=/y= prefixes."""

    suffix = f" {unit}" if unit else ""
    return f"{label} {plot_number(value)}{suffix}"
