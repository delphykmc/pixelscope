from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ORDINARY_IMAGE_SUFFIXES = frozenset({".png", ".bmp", ".jpg", ".jpeg"})
RAW_IMAGE_SUFFIX = ".raw"
RAW_LIKE_IMAGE_SUFFIXES = frozenset({RAW_IMAGE_SUFFIX, ".data", ".yuv"})
SUPPORTED_IMAGE_SUFFIXES = ORDINARY_IMAGE_SUFFIXES | RAW_LIKE_IMAGE_SUFFIXES
SUPPORTED_IMAGE_FILTER = "Supported Images (*.png *.bmp *.jpg *.jpeg *.raw *.data *.yuv)"


@dataclass(frozen=True)
class ImageInput:
    """One discoverable image and its optional sidecar RAW profile."""

    path: Path
    raw_profile_path: Path | None = None


@dataclass(frozen=True)
class RegistrationInput:
    """One registration operation with worker-computed canonical metadata."""

    image_input: ImageInput
    from_folder: bool
    resolve_raw_profile: bool
    select_on_complete: bool
    canonical_path_key: str | None = None
    canonical_folder_path: Path | None = None
    canonical_folder_key: str | None = None
    sort_key: tuple[object, ...] | None = None


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


def is_raw_like_path(path: Path) -> bool:
    return path.suffix.casefold() in RAW_LIKE_IMAGE_SUFFIXES


def raw_profile_sidecar_for_path(path: Path) -> Path | None:
    """Resolve the WP-B RAW sidecar ladder without weakening JSON authority."""

    json_sidecar = path.with_suffix(".json")
    if json_sidecar.is_file():
        return json_sidecar
    imgprops_sidecar = path.with_suffix(".imgprops")
    if imgprops_sidecar.is_file():
        return imgprops_sidecar
    return None


def image_input_for_path(path: Path) -> ImageInput | None:
    candidate = path.resolve()
    if not candidate.is_file():
        return None
    suffix = candidate.suffix.casefold()
    if suffix in ORDINARY_IMAGE_SUFFIXES:
        return ImageInput(candidate)
    if suffix in RAW_LIKE_IMAGE_SUFFIXES:
        return ImageInput(candidate, raw_profile_sidecar_for_path(candidate))
    return None


def _checkpoint(callback: Callable[[], None] | None) -> None:
    if callback is not None:
        callback()


def _registration_input(
    image_input: ImageInput,
    *,
    sort_key: tuple[object, ...],
    from_folder: bool,
    resolve_raw_profile: bool,
    select_on_complete: bool,
) -> RegistrationInput:
    folder = image_input.path.parent
    return RegistrationInput(
        image_input=image_input,
        from_folder=from_folder,
        resolve_raw_profile=resolve_raw_profile,
        select_on_complete=select_on_complete,
        canonical_path_key=str(image_input.path).casefold(),
        canonical_folder_path=folder,
        canonical_folder_key=str(folder).casefold(),
        sort_key=sort_key,
    )


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
    """Discover registration work and canonical metadata without touching Qt state.

    Folders preserve the existing registration-only intent and are ordered by their
    resolved path. Explicit files preserve the existing selection-oriented intent and
    are processed after folders. Canonical path/folder identities and natural-sort
    keys are computed here so the production GUI registration path does not repeat
    filesystem canonicalization or sort-key work per item.
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
        folder_inputs: list[tuple[tuple[object, ...], ImageInput]] = []
        for entry in candidates:
            _checkpoint(checkpoint)
            image_input = image_input_for_path(entry)
            if image_input is not None:
                folder_inputs.append((natural_sort_key(image_input.path), image_input))
        folder_inputs.sort(key=lambda item: item[0])
        if not folder_inputs:
            empty_folder_count += 1
            continue
        registered_folders.append(folder)
        items.extend(
            _registration_input(
                image_input,
                sort_key=sort_key,
                from_folder=True,
                resolve_raw_profile=False,
                select_on_complete=False,
            )
            for sort_key, image_input in folder_inputs
        )

    direct_inputs: list[tuple[tuple[object, ...], ImageInput]] = []
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
        direct_inputs.append((natural_sort_key(image_input.path), image_input))
    direct_inputs.sort(key=lambda item: item[0])
    items.extend(
        _registration_input(
            image_input,
            sort_key=sort_key,
            from_folder=False,
            resolve_raw_profile=True,
            select_on_complete=True,
        )
        for sort_key, image_input in direct_inputs
    )

    return RegistrationDiscovery(
        items=tuple(items),
        folder_count=len(unique_folders),
        empty_folder_count=empty_folder_count,
        registered_folders=tuple(registered_folders),
    )