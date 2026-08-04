from __future__ import annotations

from pixelscope.ui.plot_text import coordinate_header, middle_elide, plot_number


def test_current_raw_fixture_title_remains_unabridged() -> None:
    title = "1 · bit_depth_variations / synthetic_fhd_16bit_gray.raw"

    assert middle_elide(title) == title


def test_long_plot_title_uses_wider_middle_elision() -> None:
    title = (
        "1 · an_extremely_long_parent_folder_for_plot_validation / "
        "synthetic_fhd_16bit_gray_with_an_extended_variation_name.raw"
    )

    elided = middle_elide(title)

    assert len(elided) == 72
    assert elided.startswith("1 · an_extremely_long_parent")
    assert elided.endswith("extended_variation_name.raw")
    assert "…" in elided


def test_coordinate_headers_avoid_redundant_axis_assignments() -> None:
    assert coordinate_header("Code", 1023.5) == "Code 1023.5"
    assert coordinate_header("Distance", 315.0, "px") == "Distance 315 px"
    assert coordinate_header("Normalized distance", 0.425) == "Normalized distance 0.425"


def test_plot_number_uses_compact_shared_precision() -> None:
    assert plot_number(384.0) == "384"
    assert plot_number(0.123456789) == "0.123457"
