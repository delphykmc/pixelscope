"""Small Base-owned composition seam for feature/client window contributions.

This is intentionally not a plugin framework. Production chooses concrete contributors
explicitly and passes them to :class:`MainWindow`; no discovery, version negotiation, or
hot loading is performed here. The phase order mirrors the existing window construction
and shutdown points so separation does not create a new lifecycle model.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow

MenuActionFactory = Callable[[str, str, Any, str | None], QAction]


class WindowHostAccess(Protocol):
    """Bounded Base surface available to external window contributions."""

    def current_comparison_source_paths(self) -> tuple[Path, ...]:
        """Return local source paths in the current comparison page."""

    def register_contributed_dock(self, dock: QDockWidget) -> None:
        """Register a contribution-owned dock for Base persistence/shutdown handling."""


class WindowContribution(Protocol):
    """Phased contribution used to preserve MainWindow construction/lifetime ordering."""

    def prepare(self, window: QMainWindow) -> None:
        """Create contribution-owned widgets/controllers before dock construction."""

    def install_dock(self, window: QMainWindow) -> None:
        """Attach contribution-owned workspace UI after Base layout exists."""

    def install_actions(
        self,
        window: QMainWindow,
        menu_name: str,
        add_action: MenuActionFactory,
    ) -> None:
        """Contribute actions at a Base-selected menu insertion point."""

    def shutdown(self) -> None:
        """Stop contribution-owned client work at the existing MainWindow shutdown point."""


class RuntimeWindowContribution(Protocol):
    """Optional post-window runtime phase owned by explicit composition roots."""

    def install_runtime(self, window: QMainWindow) -> None:
        """Install runtime/controller behavior after common presentation composition starts."""
