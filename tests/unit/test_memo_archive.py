"""Memo archive: multi-ROI crops, privacy, integrity, CAS and offline HTML."""
from __future__ import annotations

import hashlib
import json
import zipfile
from uuid import uuid4

import cv2
import numpy as np
import pytest

from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1
from pixelscope.core.review_record import (
    ReviewAnalysisCaptureV1,
    ReviewFindingV1,
    ReviewFingerprintV1,
    ReviewLocatorV1,
    ReviewNativeSignatureV1,
    ReviewSourceV1,
    ReviewValidationError,
    utc_now,
)
from pixelscope.core.review_view_state import ReviewViewStateV1
from pixelscope.core.review_workflow import ReviewLibrary
from pixelscope.io.memo_archive import (
    MemoArchive,
    export_memo_html,
    load_memo_archive,
    save_memo_archive,
)


def _sources(tmp_path):
    signature = ReviewNativeSignatureV1(
        "1" * 64,
        (4, 5),
        (4, 5),
        "uint8",
        "GRAY",
        8,
        json.dumps(
            AnalysisNativeInterpretationV1().to_portable(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    return tuple(
        ReviewSourceV1(
            str(uuid4()),
            ReviewLocatorV1(f"source{n}.raw"),
            signature,
            ReviewFingerprintV1("sha256", hashlib.sha256(bytes([n])).hexdigest(), 1, 0, "verified"),
        )
        for n in range(2)
    )


def _finding(sources, roi, title):
    keys = tuple(x.source_key for x in sources)
    state = ReviewViewStateV1(
        reference_source_key=keys[0],
        page_source_keys=keys,
        active_source_key=keys[1],
        primary_source_key=keys[0],
        layout_kind="Grid 2x2",
        presentation_mode="originals",
        sync_enabled=True,
        center_ref_xy=(2.0, 1.5),
        physical_scale=1.0,
        reference_shape=(4, 5),
        source_shapes_ref={key: (4, 5) for key in keys},
        per_source={},
    )
    return ReviewFindingV1(
        id=str(uuid4()),
        title=title,
        note="비교 <script>alert(1)</script> 메모",
        tags=(),
        captured_utc=utc_now(),
        source_keys=keys,
        reference_key=keys[0],
        pair_target_key=keys[1],
        view_state=state,
        roi_ref=roi,
        line_ref=None,
        channel="All",
        display_gain=1.0,
        difference_intent=None,
        analysis=(ReviewAnalysisCaptureV1("unavailable", reason="not calculated"),),
        availability="unavailable",
    )


def _png(roi, value):
    x, y, w, h = roi
    del x, y
    image = np.full((h, w, 3), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _notebook(tmp_path):
    library = ReviewLibrary()
    sources = _sources(tmp_path)
    rois = [(0, 0, 2, 2), (1, 1, 3, 2), (2, 0, 2, 3)]
    crops = {}
    findings = []
    for index, roi in enumerate(rois):
        finding = library.add(_finding(sources, roi, f"ROI-{index+1}"), sources)
        findings.append(finding)
        for n, source in enumerate(sources):
            crops[finding.id, source.source_key] = _png(roi, 50 + index * 10 + n)
    return library, sources, findings, crops


def test_multi_roi_archive_survives_missing_originals_and_exports_safe_html(tmp_path):
    library, sources, findings, crops = _notebook(tmp_path)
    path = tmp_path / "inspection.pxmemo"
    revision = save_memo_archive(path, MemoArchive(library.document, crops))
    assert len(revision) == 64
    loaded, same_revision = load_memo_archive(path)
    assert same_revision == revision
    assert [f.roi_ref for f in loaded.review.findings] == [
        (0, 0, 2, 2), (1, 1, 3, 2), (2, 0, 2, 3)
    ]
    assert dict(loaded.crops) == crops
    # No source file was created: the HTML remains completely offline.
    assert not (tmp_path / "source0.raw").exists()
    page = export_memo_html(tmp_path / "shareable", loaded)
    markup = page.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in markup
    assert "<script>" not in markup
    assert len(tuple((page.parent / "images").rglob("*.png"))) == 6
    assert str(tmp_path) not in markup
    for finding in findings:
        assert finding.id in str(tuple((page.parent / "images").rglob("*.png")))


def test_delete_one_roi_then_resave_keeps_independent_crops(tmp_path):
    library, _, findings, crops = _notebook(tmp_path)
    path = tmp_path / "memo.pxmemo"
    first = save_memo_archive(path, MemoArchive(library.document, crops))
    library.delete(findings[1].id)
    removed = {key: value for key, value in crops.items() if key[0] != findings[1].id}
    with pytest.raises(FileExistsError):
        save_memo_archive(path, MemoArchive(library.document, removed))
    second = save_memo_archive(
        path, MemoArchive(library.document, removed), expected_revision=first
    )
    assert second != first
    reloaded, _ = load_memo_archive(path)
    assert len(reloaded.review.findings) == 2
    assert len(reloaded.crops) == 4


def test_corrupt_digest_or_extra_zip_member_fails_closed(tmp_path):
    library, _, _, crops = _notebook(tmp_path)
    path = tmp_path / "original.pxmemo"
    save_memo_archive(path, MemoArchive(library.document, crops))
    tampered = tmp_path / "tampered.pxmemo"
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(tampered, "w") as changed:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename.endswith(".png"):
                data = data + b"tampered"
            changed.writestr(info.filename, data)
        changed.writestr("../escape.txt", "no")
    with pytest.raises(ReviewValidationError):
        load_memo_archive(tampered)


def test_dimensions_or_orphan_crop_rejected_before_publishing(tmp_path):
    library, sources, findings, crops = _notebook(tmp_path)
    wrong = dict(crops)
    wrong[findings[0].id, sources[0].source_key] = _png((0, 0, 3, 3), 12)
    with pytest.raises(ReviewValidationError, match="dimensions"):
        save_memo_archive(tmp_path / "wrong.pxmemo", MemoArchive(library.document, wrong))
    assert not (tmp_path / "wrong.pxmemo").exists()
    orphan = dict(crops)
    orphan[str(uuid4()), str(uuid4())] = _png((0, 0, 2, 2), 0)
    with pytest.raises(ReviewValidationError, match="missing|extra"):
        save_memo_archive(tmp_path / "orphan.pxmemo", MemoArchive(library.document, orphan))
