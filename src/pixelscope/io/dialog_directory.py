"""Directory validation for explicit file chooser preparation, never startup."""
from __future__ import annotations

from pathlib import Path

from pixelscope.core.cancellation import cancellation_checkpoint


def prepare_dialog_directory(configured: str, last_used: str) -> str:
    for value in (configured.strip(), last_used, str(Path.home())):
        cancellation_checkpoint()
        if not value:
            continue
        try:
            path = Path(value).expanduser()
            available = path.is_dir()
        except (OSError, ValueError):
            continue
        if available:
            cancellation_checkpoint()
            return str(path)
    cancellation_checkpoint()
    return ""
