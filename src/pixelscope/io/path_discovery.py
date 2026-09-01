from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ORDINARY_IMAGE_SUFFIXES = frozenset({".png", ".bmp", ".jpg", ".jpeg"})
RAW_IMAGE_SUFFIX = ".raw"
SUPPORTED_IMAGE_SUFFIXES = ORDINARY_IMAGE_SUFFIXES | {RAW_IMAGE_SUFFIX}
SUPPORTED_IMAGE_FILTER = "Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)"


@dataclass(frozen=True)
class ImageInput:
    """One discoverable image and its optional sidecar RAW profile."""

    path: Path
    raw_profile_path: Path | None = None


@dataclass(frozen=True)
class RegistrationInput:
    """One registration operation with its existing file/folder intent preserved."""

    image_input: ImageInput
    from_folder: bool
    resolve_raw_profile: bool
    select_on_complete: bool


@dataclass(frozen=True)
class RegistrationDiscovery:
    """Filesystem-only discovery result consumed later by the GUI registration phase."""

    items: tuple[RegistrationInput, ...]
    folder_count: int
    empty_folder_count: int
    registered_folders: tuple[Path, ...]


def natural_sort_key(path: Path) -> tuple[object, ...]:
    """Sort filenames so image2 precedes image10, case-insensitively."""

    parts = re.split(r"(\d+)", path.name.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def image_input_for_path(path: Path) -> ImageInput | None:
    candidate = path.resolve()
    if not candidate.is_file():
        return None
    suffix = candidate.suffix.casefold()
    if suffix in ORDINARY_IMAGE_SUFFIXES:
        return ImageInput(candidate)
    if suffix == RAW_IMAGE_SUFFIX:
        sidecar = candidate.with_suffix(".json")
        return ImageInput(candidate, sidecar if sidecar.is_file() else None)
    return None


def _checkpoint(callback: Callable[[], None] | None) -> None:
    if callback is not None:
        callback()


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
        for entry in candidates:
            image_input = image_input_for_path(entry)
            if image_input is None:
                continue
            identity = str(image_input.path).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            discovered.append(image_input)
    return tuple(sorted(discovered, key=lambda item: natural_sort_key(item.path)))


def discover_registration_inputs(
    paths: Iterable[Path],
    recursive: bool = False,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> RegistrationDiscovery:
    """Discover folder and direct-file registration work without touching Qt state.

    Folders preserve the existing registration-only intent and are ordered by their
    resolved path. Explicit files preserve the existing selection-oriented intent and
    are processed after folders. A file supplied both through a folder and explicitly
    therefore remains two registration operations; catalog duplicate suppression is
    intentionally left to the canonical registration owner.
    """

    unique_folders: dict[str, Path] = {}
    direct_candidates: list[Path] = []
    for supplied in paths:
        _checkpoint(checkpoint)
        candidate = supplied.resolve()
        if candidate.is_dir():
            unique_folders.setdefault(str(candidate).casefold(), candidate)
        elif candidate.is_file():
            direct_candidates.append(candidate)

    items: list[RegistrationInput] = []
    registered_folders: list[Path] = []
    empty_folder_count = 0
    for folder_key in sorted(unique_folders):
        _checkpoint(checkpoint)
        folder = unique_folders[folder_key]
        candidates = folder.rglob("*") if recursive else folder.iterdir()
        folder_inputs: list[ImageInput] = []
        for entry in candidates:
            _checkpoint(checkpoint)
            image_input = image_input_for_path(entry)
            if image_input is not None:
                folder_inputs.append(image_input)
        folder_inputs.sort(key=lambda item: natural_sort_key(item.path))
        if not folder_inputs:
            empty_folder_count += 1
            continue
        registered_folders.append(folder)
        items.extend(
            RegistrationInput(
                image_input=image_input,
                from_folder=True,
                resolve_raw_profile=False,
                select_on_complete=False,
            )
            for image_input in folder_inputs
        )

    direct_inputs: list[ImageInput] = []
    direct_seen: set[str] = set()
    for candidate in direct_candidates:
        _checkpoint(checkpoint)
        image_input = image_input_for_path(candidate)
        if image_input is None:
            continue
        identity = str(image_input.path).casefold()
        if identity in direct_seen:
            continue
        direct_seen.add(identity)
        direct_inputs.append(image_input)
    direct_inputs.sort(key=lambda item: natural_sort_key(item.path))
    items.extend(
        RegistrationInput(
            image_input=image_input,
            from_folder=False,
            resolve_raw_profile=True,
            select_on_complete=True,
        )
        for image_input in direct_inputs
    )

    return RegistrationDiscovery(
        items=tuple(items),
        folder_count=len(unique_folders),
        empty_folder_count=empty_folder_count,
        registered_folders=tuple(registered_folders),
    )
