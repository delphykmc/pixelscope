from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".bmp"})


@dataclass(frozen=True)
class ImageInput:
    """One discoverable image and its optional sidecar RAW profile."""

    path: Path
    raw_profile_path: Path | None = None


def natural_sort_key(path: Path) -> tuple[object, ...]:
    """Sort filenames so image2 precedes image10, case-insensitively."""

    parts = re.split(r"(\d+)", path.name.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def image_input_for_path(path: Path) -> ImageInput | None:
    candidate = path.resolve()
    if not candidate.is_file():
        return None
    if candidate.suffix.casefold() in SUPPORTED_IMAGE_SUFFIXES:
        return ImageInput(candidate)
    if candidate.suffix.casefold() == ".raw":
        sidecar = candidate.with_suffix(".json")
        return ImageInput(candidate, sidecar if sidecar.is_file() else None)
    return None


def discover_image_inputs(paths: Iterable[Path], recursive: bool = False) -> tuple[ImageInput, ...]:
    """Expand files/folders into unique, naturally sorted supported inputs."""

    discovered: list[ImageInput] = []
    seen: set[str] = set()
    for supplied in paths:
        candidate = supplied.resolve()
        candidates = (
            candidate.rglob("*")
            if candidate.is_dir() and recursive
            else candidate.iterdir()
            if candidate.is_dir()
            else (candidate,)
        )
        folder_inputs = [
            image_input
            for entry in candidates
            if (image_input := image_input_for_path(entry)) is not None
        ]
        for image_input in sorted(folder_inputs, key=lambda item: natural_sort_key(item.path)):
            identity = str(image_input.path).casefold()
            if identity not in seen:
                seen.add(identity)
                discovered.append(image_input)
    return tuple(sorted(discovered, key=lambda item: natural_sort_key(item.path)))


def pair_folders(folder_a: Path, folder_b: Path) -> tuple[tuple[ImageInput, ImageInput], ...]:
    """Pair immediate child images by natural sort position."""

    inputs_a = discover_image_inputs((folder_a,))
    inputs_b = discover_image_inputs((folder_b,))
    return tuple(zip(inputs_a, inputs_b, strict=False))
