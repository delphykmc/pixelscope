from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from pixelscope.core.source_presentation import (
    SourceLabelInput,
    normalized_label_key,
    resolve_display_alias,
    resolve_display_aliases,
)


def _source(key: str, path: str, tag: str = "") -> SourceLabelInput:
    return SourceLabelInput(key, PurePosixPath(path), display_tag=tag)


def test_four_identical_names_use_shortest_parent_suffix() -> None:
    inputs = [
        _source("a", "/test/base/chart.png"),
        _source("b", "/test/noise/chart.png"),
        _source("c", "/test/tone/chart.png"),
        _source("d", "/test/sharp/chart.png"),
    ]
    labels = resolve_display_aliases(inputs)
    assert [labels[key].text for key in "abcd"] == [
        "base / chart.png",
        "noise / chart.png",
        "tone / chart.png",
        "sharp / chart.png",
    ]
    assert labels == resolve_display_aliases(reversed(inputs))


def test_repeated_parent_names_grow_to_unique_suffix() -> None:
    inputs = [_source("a", "/run1/capture/chart.png"), _source("b", "/run2/capture/chart.png")]
    assert resolve_display_aliases(inputs)["a"].text == "run1 / capture / chart.png"
    assert resolve_display_aliases(inputs)["b"].text == "run2 / capture / chart.png"


def test_unicode_nfc_and_casefold_collisions_are_distinguished() -> None:
    inputs = [
        _source("a", "/한국/기준/카페\u0301.PNG"),
        _source("b", "/한국/노이즈/카페\u0301.png"),
        _source("c", "/한국/색감/카페\u0301.PNG"),
    ]
    labels = resolve_display_aliases(inputs)
    assert len({normalized_label_key(label.text) for label in labels.values()}) == 3
    assert "기준" in labels["a"].text
    assert "노이즈" in labels["b"].text


def test_explicit_tag_has_precedence_and_can_be_removed() -> None:
    inputs = [_source("a", "/base/chart.png", "Reference"), _source("b", "/noise/chart.png")]
    labels = resolve_display_aliases(inputs)
    assert labels["a"].text == "[Reference] chart.png"
    assert labels["b"].text == "chart.png"
    cleared = resolve_display_aliases([_source("a", "/base/chart.png"), inputs[1]])
    assert cleared["a"].text == "base / chart.png"
    assert cleared["b"].text == "noise / chart.png"


def test_same_tag_collision_qualifies_each_source() -> None:
    inputs = [_source("a", "/r1/chart.png", "Ref"), _source("b", "/r2/chart.png", "Ref")]
    labels = resolve_display_aliases(inputs)
    assert labels["a"].text == "[Ref] r1 / chart.png"
    assert labels["b"].text == "[Ref] r2 / chart.png"


def test_same_normalized_absolute_path_falls_back_to_stable_suffix() -> None:
    inputs = [
        SourceLabelInput("id-A", PureWindowsPath("C:/Data/IMAGE.PNG")),
        SourceLabelInput("id-B", PureWindowsPath("c:/data/image.png")),
    ]
    labels = resolve_display_aliases(inputs)
    assert labels["id-A"].text != labels["id-B"].text
    assert len({normalized_label_key(label.text) for label in labels.values()}) == 2
    assert labels == resolve_display_aliases(reversed(inputs))
    assert resolve_display_alias(inputs, "id-A") == labels["id-A"]


def test_distinct_regular_names_are_unqualified() -> None:
    labels = resolve_display_aliases([_source("a", "/x/one.png"), _source("b", "/y/two.png")])
    assert labels["a"].text == "one.png"
    assert labels["b"].text == "two.png"
    assert not labels["a"].qualified


def test_duplicate_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate source_key"):
        resolve_display_aliases([_source("same", "/a/test.png"), _source("same", "/b/test.png")])


def test_nfc_composed_and_decomposed_basename_collide() -> None:
    inputs = [
        _source("a", "/a/caf\u00e9.png"),
        _source("b", "/b/cafe\u0301.png"),
    ]
    labels = resolve_display_aliases(inputs)
    assert len({normalized_label_key(label.text) for label in labels.values()}) == 2
    assert labels["a"].text.startswith("a /")
    assert labels["b"].text.startswith("b /")
