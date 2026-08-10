from __future__ import annotations

from collections.abc import Iterator

import pytest

from pixelscope.ui.display_gain import display_gain_state


@pytest.fixture(autouse=True)
def reset_display_gain_for_p3d_input_policy(request: pytest.FixtureRequest) -> Iterator[None]:
    """Isolate P3-D input-policy gain mutation without touching unrelated UI tests."""

    if request.path.name != "test_p3d_input_policy.py":
        yield
        return
    state = display_gain_state()
    state.set_gain(1.0)
    try:
        yield
    finally:
        state.set_gain(1.0)
