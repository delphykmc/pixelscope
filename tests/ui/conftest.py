from __future__ import annotations

import pytest

from pixelscope.ui.display_gain import display_gain_state


@pytest.fixture(autouse=True)
def reset_display_gain_state() -> None:
    state = display_gain_state()
    state.set_gain(1.0)
    yield
    state.set_gain(1.0)
