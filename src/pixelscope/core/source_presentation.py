"""Deterministic, Qt-free source labels. Labels are never source identities."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePath
from unicodedata import normalize


@dataclass(frozen=True)
class SourceLabelInput:
    """A presentation-only snapshot; ``source_key`` is an opaque stable lookup key."""

    source_key: str
    source_path: PurePath | None
    fallback_name: str = ""
    display_tag: str = ""


@dataclass(frozen=True)
class DisplayLabel:
    text: str
    source_key: str
    qualified: bool


def normalized_label_key(value: str) -> str:
    """Detect visually confusable Unicode normalization and case collisions."""

    return normalize("NFC", value).casefold()


def _parts(source: SourceLabelInput) -> tuple[str, tuple[str, ...], str]:
    path = source.source_path
    basename = path.name if path is not None else source.fallback_name
    basename = basename or source.source_key
    if path is None:
        parents: tuple[str, ...] = ()
    else:
        # Include the drive/root only as a last resort when both paths have
        # identical directory suffixes. The displayed path stays presentation-only.
        parents = tuple(part for part in path.parts[:-1] if part not in ("/", "\\"))
    tag = " ".join(source.display_tag.split())
    return basename, parents, tag


def resolve_display_aliases(sources: Iterable[SourceLabelInput]) -> dict[str, DisplayLabel]:
    """Resolve unique labels without reading files or mutating sources.

    A non-conflicting explicit folder tag wins. Otherwise, colliding labels
    receive the shortest *distinguishing* parent suffix, then a stable opaque
    key digest if their normalized paths still collide. Results do not depend
    on input order, including when Unicode differs only by NFC or casefold.
    """

    items = tuple(sources)
    entries = {source.source_key: source for source in items}
    if any(not key for key in entries):
        raise ValueError("source_key must not be empty")
    if len(entries) != len(items):
        raise ValueError("duplicate source_key")
    details = {key: _parts(source) for key, source in entries.items()}
    depths = {key: 0 for key in entries}
    # Path spelling provides a restart-stable tie-break for casefold collisions.
    # Truly identical locators (e.g. derived views) use their opaque source key.
    path_values = {
        key: str(source.source_path) if source.source_path is not None else ""
        for key, source in entries.items()
    }
    path_counts: dict[str, int] = defaultdict(int)
    for value in path_values.values():
        if value:
            path_counts[value] += 1

    def digest_material(key: str) -> str:
        path = path_values[key]
        return path if path and path_counts[path] == 1 else key

    digests = {key: sha256(digest_material(key).encode("utf-8")).hexdigest() for key in entries}
    suffix_lengths = {key: 0 for key in entries}

    def candidate(key: str) -> str:
        basename, parents, tag = details[key]
        depth = depths[key]
        path_label = " / ".join((*parents[-depth:], basename)) if depth else basename
        label = f"[{tag}] {path_label}" if tag else path_label
        if suffix_lengths[key]:
            label += f" [{digests[key][:suffix_lengths[key]]}]"
        return label

    # Each conflicted candidate makes monotonic progress to a longer directory
    # suffix or SHA-256 suffix; the upper bound is independent of input order.
    limit = sum(len(parts[1]) + 65 for parts in details.values()) + 1
    for _ in range(limit):
        conflicts: dict[str, list[str]] = defaultdict(list)
        for key in entries:
            conflicts[normalized_label_key(candidate(key))].append(key)
        duplicated = [keys for keys in conflicts.values() if len(keys) > 1]
        if not duplicated:
            return {
                key: DisplayLabel(
                    text=candidate(key),
                    source_key=key,
                    qualified=bool(depths[key] or suffix_lengths[key]),
                )
                for key in entries
            }
        for group in duplicated:
            for key in group:
                parent_count = len(details[key][1])
                if depths[key] < parent_count:
                    depths[key] += 1
                elif suffix_lengths[key] < len(digests[key]):
                    suffix_lengths[key] = (
                        8
                        if not suffix_lengths[key]
                        else min(len(digests[key]), suffix_lengths[key] + 4)
                    )
                else:
                    raise ValueError("source keys do not yield distinguishable labels")
    raise ValueError("unable to resolve unique source aliases")


def resolve_display_alias(sources: Iterable[SourceLabelInput], source_key: str) -> DisplayLabel:
    """Convenience lookup for downstream W06/W07/W09 presentation adapters."""

    return resolve_display_aliases(sources)[source_key]
