from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QSizePolicy, QWidget


def install_iqa_preferred_growth_policy(window: Any) -> None:
    """Let IQA compress under pressure without advertising eager expansion.

    PR #68 deliberately changed the IQA workspace to Ignored so its preferred
    width could not become an application-wide minimum.  For the Windows
    recovery experiment, retain a zero minimum but restore Preferred as the
    outer workspace's horizontal policy.  This gives QMainWindow a useful
    sizeHint again without adding resize-event thresholds or resizeDocks rules.
    """

    workspace = getattr(window, "iqa_workspace", None)
    if not isinstance(workspace, QWidget):
        return

    workspace.setMinimumWidth(0)
    policy = workspace.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
    workspace.setSizePolicy(policy)
    workspace.updateGeometry()
