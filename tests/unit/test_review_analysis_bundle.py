from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import numpy as np
import pytest

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis import (
    AnalysisMeasurementV1,
    AnalysisSeriesV1,
    AnalysisSnapshotV1,
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
    capture_presented_analysis,
    freeze_series_values,
    measurement,
    parse_analysis_context,
    serialize_analysis_context,
)
from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1
from pixelscope.core.review_analysis_sources import native_interpretation, native_profile_signature
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.analysis_bundle import (
    AnalysisFeatureAvailabilityV1,
    verify_analysis_bundle,
    write_analysis_bundle,
)
from pixelscope.io.raw_profile import RawProfile


def _snapshot(roi: tuple[int, int, int, int] | None = None) -> AnalysisSnapshotV1:
    document_id = str(uuid4())
    source_key = str(uuid4())
    digest = "a" * 64
    token = PresentedAnalysisTokenV1(
        feature="statistics",
        request_id=str(uuid4()),
        request_epoch=2,
        source_documents=((document_id, 7),),
        source_keys=(source_key,),
        roi_ref=roi,
        channel="All",
        domain="native",
        profile_signatures=(digest,),
        difference_cache_key=None,
    )
    return AnalysisSnapshotV1(
        snapshot_id=str(uuid4()),
        captured_utc="2026-11-04T00:00:00+00:00",
        token=token,
        sources=(
            AnalysisSourceV1(
                source_key=source_key,
                document_id=document_id,
                generation=7,
                native_shape=(12, 16, 3),
                reference_shape=(12, 16),
                native_dtype="uint16",
                channel_layout="RGB",
                effective_bits=10,
                profile_signature=digest,
            ),
        ),
        measurements=(measurement(source_key, "R", "Mean", 23.0, 20),),
        presentation=(("scope", "roi" if roi else "full"),),
    )


class _FakeAdapter:
    def __init__(self, snapshot: AnalysisSnapshotV1) -> None:
        self.snapshot = snapshot
        self.current = snapshot.token
        self.presented = snapshot.token
        self.mutate_during_read = False

    def get_presented_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        return self.presented

    def get_current_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        return self.current

    def read_presented_analysis(self) -> tuple:
        if self.mutate_during_read:
            self.current = replace(self.current, request_epoch=99)
        s = self.snapshot
        return s.sources, s.measurements, s.presentation


def test_capture_blocks_pending_stale_source_and_changed_during_read() -> None:
    snapshot = _snapshot((0, 0, 4, 5))
    adapter = _FakeAdapter(snapshot)
    captured = capture_presented_analysis(adapter, snapshot.token)
    assert captured.available
    assert captured.snapshot is not None
    assert captured.snapshot.measurements == snapshot.measurements
    adapter.presented = None
    assert capture_presented_analysis(adapter, snapshot.token).reason == "pending_or_uncomputed"
    adapter.presented = snapshot.token
    adapter.current = replace(
        snapshot.token, source_documents=((snapshot.token.source_documents[0][0], 8),)
    )
    assert capture_presented_analysis(adapter, snapshot.token).reason == "stale_or_mismatched"
    adapter.current = snapshot.token
    adapter.mutate_during_read = True
    assert capture_presented_analysis(adapter, snapshot.token).reason == "changed_during_capture"


def test_identical_roi_area_different_origin_are_distinct() -> None:
    first = _snapshot((0, 0, 4, 5))
    second = replace(first, token=replace(first.token, roi_ref=(3, 4, 4, 5)))
    assert serialize_analysis_context(first) != serialize_analysis_context(second)
    assert parse_analysis_context(serialize_analysis_context(second))["roi_ref"] == [3, 4, 4, 5]


@pytest.mark.parametrize("dtype", ["uint8", "uint16", "int32", "float32", ">u2", ">f4", "<u2"])
def test_native_dtype_roundtrip_preserves_endianness(dtype: str) -> None:
    snapshot = _snapshot()
    source = replace(snapshot.sources[0], native_dtype=dtype)
    parsed = parse_analysis_context(
        serialize_analysis_context(replace(snapshot, sources=(source,)))
    )
    assert parsed["sources"][0]["native_dtype"] == dtype


@pytest.mark.parametrize("dtype", ["object", "float8", "../uint16", r"C:\private\uint16"])
def test_native_dtype_rejects_non_numeric_or_path_values(dtype: str) -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="native format"):
        replace(snapshot.sources[0], native_dtype=dtype)
    data = parse_analysis_context(serialize_analysis_context(snapshot))
    data["sources"][0]["native_dtype"] = dtype
    with pytest.raises(ValueError, match="native signature"):
        parse_analysis_context(json.dumps(data).encode())


def test_analysis_labels_accept_producer_values_and_reject_path_separators() -> None:
    snapshot = _snapshot()
    assert snapshot.token.channel == "All"
    assert snapshot.token.domain == "native"
    assert snapshot.measurements[0].metric == "Mean"
    for channel in (r"w\w", "folder/R"):
        with pytest.raises(ValueError, match="channel/domain"):
            replace(snapshot.token, channel=channel)


def test_snapshot_rejects_generation_and_profile_mismatch() -> None:
    snap = _snapshot()
    with pytest.raises(ValueError, match="generations"):
        replace(snap, sources=(replace(snap.sources[0], generation=8),))
    with pytest.raises(ValueError, match="profiles"):
        replace(snap, sources=(replace(snap.sources[0], profile_signature="b" * 64),))
    with pytest.raises(ValueError, match="half-open"):
        replace(snap.token, roi_ref=(1, 2, 0, 4))


def test_nonfinite_values_have_explicit_state_and_no_json_nan() -> None:
    snap = _snapshot()
    nan = measurement(snap.sources[0].source_key, "R", "PSNR", float("inf"), 20)
    assert nan.state == "pos_inf" and nan.value is None
    snap = replace(snap, measurements=(nan,))
    raw = serialize_analysis_context(snap)
    assert b"Infinity" not in raw
    assert parse_analysis_context(raw)["measurements"][0]["state"] == "pos_inf"
    with pytest.raises(ValueError):
        AnalysisMeasurementV1(snap.sources[0].source_key, "R", "Mean", float("nan"), 10)


def test_context_roundtrip_excludes_private_source_data() -> None:
    snap = _snapshot()
    raw = serialize_analysis_context(snap)
    parsed = parse_analysis_context(raw)
    assert parsed["kind"] == "pixelscope-analysis-context"
    assert parsed["sources"][0]["verification"] == "unverified"
    assert snap.sources[0].document_id.encode() not in raw
    assert b"source_path" not in raw
    assert b"alias" not in raw


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version=2),
        lambda d: d.update(kind="pixelscope-session"),
        lambda d: d.update(roi_ref=[-1, 0, 4, 5], scope="roi"),
        lambda d: d.update(roi_ref=[0, 0, 4, 5], scope="full"),
        lambda d: d["sources"][0].update(source_path="/home/user/private.raw"),
        lambda d: d["measurements"][0].update(value=float("nan")),
        lambda d: d["sources"][0].update(verification="verified"),
        lambda d: d.update(schema_version=True),
    ],
)
def test_invalid_context_schema_is_rejected(mutation: object) -> None:
    data = parse_analysis_context(serialize_analysis_context(_snapshot()))
    data = copy.deepcopy(data)
    mutation(data)  # type: ignore[operator]
    with pytest.raises((ValueError, TypeError)):
        parse_analysis_context(json.dumps(data).encode("utf-8"))


def test_duplicate_json_keys_rejected() -> None:
    raw = serialize_analysis_context(_snapshot())
    hostile = raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')
    with pytest.raises(ValueError, match="duplicate"):
        parse_analysis_context(hostile)


def test_zip_roundtrip_and_private_path_sentinel(tmp_path: Path) -> None:
    snap = _snapshot((1, 2, 4, 5))
    target = tmp_path / "bundle.zip"
    write_analysis_bundle(target, (snap,))
    manifest = verify_analysis_bundle(target)
    assert manifest["snapshot_count"] == 1
    with ZipFile(target) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert {
            "manifest.json",
            "data/context.json",
            "data/measurements.csv",
            "data/measurements.json",
        } == set(names)
        for name in names:
            payload = archive.read(name)
            assert b"C:\\\\Users\\\\secret" not in payload
            assert b"/home/private" not in payload
            assert b"private.raw" not in payload


def test_cancel_and_write_failure_never_publish_partial_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snap = _snapshot()
    target = tmp_path / "bundle.zip"
    with pytest.raises(RuntimeError, match="cancel"):
        write_analysis_bundle(target, (snap,), cancelled=lambda: True)
    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))

    def deny(_source: Path, _target: Path) -> None:
        raise PermissionError("simulated replace failure")

    monkeypatch.setattr("pixelscope.io.analysis_bundle.os.replace", deny)
    with pytest.raises(PermissionError):
        write_analysis_bundle(target, (snap,))
    assert not target.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_target_collision_requires_overwrite_token(tmp_path: Path) -> None:
    snap = _snapshot()
    target = tmp_path / "bundle.zip"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        write_analysis_bundle(target, (snap,))
    assert target.read_bytes() == b"existing"
    previous = target.stat()
    write_analysis_bundle(
        target,
        (snap,),
        expected_existing=(previous.st_dev, previous.st_ino, previous.st_mtime_ns),
    )
    assert verify_analysis_bundle(target)["kind"] == "pixelscope-analysis-bundle"


def test_reject_manifest_tamper(tmp_path: Path) -> None:
    path = tmp_path / "bundle.zip"
    write_analysis_bundle(path, (_snapshot(),))
    with ZipFile(path, "a") as archive:
        archive.writestr("data/measurements.csv", b"forged")
    with pytest.raises(ValueError, match="duplicate"):
        verify_analysis_bundle(path)


def test_histogram_series_freezes_large_integer_counts_without_precision_loss(
    tmp_path: Path,
) -> None:
    base = _snapshot((1, 2, 4, 5))
    values, states = freeze_series_values(np.asarray([2**53 + 1, 4], dtype=np.int64))
    assert values[0] == 2**53 + 1
    frozen = AnalysisSeriesV1(
        source_key=base.sources[0].source_key,
        channel="R",
        kind="histogram",
        coordinates=(0.0, 1.0, 2.0),
        values=values,
        value_states=states,
        sample_count=2**53 + 5,
        definition_revision="native-bin-counts-v1",
    )
    snap = replace(
        base,
        token=replace(base.token, feature="histogram"),
        measurements=(),
        series=(frozen,),
    )
    parsed = parse_analysis_context(serialize_analysis_context(snap))
    assert parsed["series"][0]["values"] == [2**53 + 1, 4]
    path = tmp_path / "hist.zip"
    write_analysis_bundle(path, (snap,))
    assert verify_analysis_bundle(path)["snapshot_count"] == 1
    with ZipFile(path) as archive:
        raw = json.loads(archive.read("data/measurements.json"))
        assert raw["snapshots"][0]["series"][0]["values"][0] == 2**53 + 1


def test_line_series_preserves_explicit_nan_inf_states() -> None:
    base = _snapshot()
    values, states = freeze_series_values(np.asarray([0.0, np.nan, np.inf, -np.inf, -3.25]))
    assert states == ("finite", "nan", "pos_inf", "neg_inf", "finite")
    series = AnalysisSeriesV1(
        source_key=base.sources[0].source_key,
        channel="Gray",
        kind="line",
        coordinates=(0.0, 1.0, 2.0, 3.0, 4.0),
        values=values,
        value_states=states,
        sample_count=5,
        definition_revision="native-line-profile-v1",
    )
    snapshot = replace(
        base,
        token=replace(base.token, feature="line"),
        measurements=(),
        series=(series,),
    )
    raw = serialize_analysis_context(snapshot)
    assert b"NaN" not in raw and b"Infinity" not in raw
    assert parse_analysis_context(raw)["series"][0]["value_states"] == list(states)


def test_series_rejects_wrong_feature_count_and_pathlike_labels() -> None:
    base = _snapshot()
    kwargs = dict(
        source_key=base.sources[0].source_key,
        channel="Gray",
        kind="line",
        coordinates=(0.0, 1.0),
        values=(1.0, 2.0),
        value_states=("finite", "finite"),
        sample_count=2,
        definition_revision="native-line-profile-v1",
    )
    series = AnalysisSeriesV1(**kwargs)
    with pytest.raises(ValueError, match="cannot include native series"):
        replace(base, series=(series,))
    with pytest.raises(ValueError, match="cardinality"):
        AnalysisSeriesV1(**(kwargs | {"coordinates": (0.0,)}))
    with pytest.raises(ValueError, match="classification"):
        AnalysisSeriesV1(**(kwargs | {"channel": "C:/private/file"}))


def test_series_parse_fails_closed_on_wrong_status_and_future_fields() -> None:
    base = _snapshot()
    series = AnalysisSeriesV1(
        source_key=base.sources[0].source_key,
        channel="Gray",
        kind="line",
        coordinates=(0.0, 1.0),
        values=(1.0, 2.0),
        value_states=("finite", "finite"),
        sample_count=2,
        definition_revision="native-line-profile-v1",
    )
    snap = replace(
        base,
        token=replace(base.token, feature="line"),
        series=(series,),
    )
    data = parse_analysis_context(serialize_analysis_context(snap))
    data["series"][0]["value_states"][0] = "verified"
    with pytest.raises(ValueError, match="state"):
        parse_analysis_context(json.dumps(data).encode())
    data["series"][0]["value_states"][0] = "finite"
    data["series"][0]["absolute_source_path"] = "C:/secret.raw"
    with pytest.raises(ValueError, match="series"):
        parse_analysis_context(json.dumps(data).encode())


def test_capture_freezes_series_only_when_both_tokens_stay_current() -> None:
    snap = _snapshot()
    series = AnalysisSeriesV1(
        source_key=snap.sources[0].source_key,
        channel="R",
        kind="line",
        coordinates=(0.0, 1.0),
        values=(2.0, 4.0),
        value_states=("finite", "finite"),
        sample_count=2,
        definition_revision="native-line-profile-v1",
    )
    target = replace(snap, token=replace(snap.token, feature="line"), series=(series,))

    class SeriesAdapter(_FakeAdapter):
        def read_presented_series(self) -> tuple[AnalysisSeriesV1, ...]:
            if self.mutate_during_read:
                self.current = replace(self.current, request_epoch=100)
            return (series,)

    adapter = SeriesAdapter(target)
    capture = capture_presented_analysis(adapter, target.token)
    assert capture.snapshot is not None
    assert capture.snapshot.series == (series,)
    adapter.mutate_during_read = True
    assert capture_presented_analysis(adapter, target.token).reason == "changed_during_capture"


@pytest.mark.parametrize("feature", ["statistics", "difference"])
def test_wire_series_kind_cannot_bypass_dto_classification(feature: str) -> None:
    """A malicious wire document must not represent impossible native series."""
    data = parse_analysis_context(serialize_analysis_context(_snapshot()))
    data["feature"] = feature
    data["series"] = [
        {
            "source_key": data["sources"][0]["source_key"],
            "channel": "R",
            "kind": feature,
            "coordinates": [0.0],
            "values": [1.0],
            "value_states": ["finite"],
            "sample_count": 1,
            "definition_revision": "native-v1",
        }
    ]
    with pytest.raises(ValueError, match="cannot include native series"):
        parse_analysis_context(json.dumps(data).encode("utf-8"))


def test_bayer_native_interpretation_and_private_profile_name_are_portable() -> None:
    profile = RawProfile(
        name="C:\\internal\\private-profile.raw",
        width=8,
        height=4,
        stride_bytes=16,
        offset_bytes=8,
        bit_depth=10,
        channel_layout="BAYER",
        bayer_pattern="GRBG",
        endianness="big",
        bit_alignment="msb",
        black_level=64,
        white_level=1023,
    )
    doc = ImageDocument.from_array(
        np.full((4, 8), 333, dtype=np.uint16),
        "private-name.raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
    )
    interpretation = native_interpretation(doc)
    assert interpretation.cfa_pattern == "GRBG"
    assert interpretation.cfa_phase_xy == (0, 0)
    assert interpretation.raw_row_stride_bytes == 16
    assert interpretation.raw_byte_offset == 8
    assert interpretation.raw_endianness == "big"
    assert interpretation.raw_bit_alignment == "msb"
    assert interpretation.raw_black_levels == (64,)
    assert (
        AnalysisNativeInterpretationV1.from_portable(interpretation.to_portable()) == interpretation
    )
    base = _snapshot()
    signature = native_profile_signature(doc)
    source = replace(
        base.sources[0],
        native_shape=doc.shape,
        reference_shape=doc.reference_shape,
        native_dtype=str(doc.original_dtype),
        channel_layout=doc.channel_layout,
        effective_bits=doc.bit_depth,
        profile_signature=signature,
        native_interpretation=interpretation,
    )
    snap = replace(
        base,
        token=replace(base.token, profile_signatures=(signature,)),
        sources=(source,),
    )
    raw = serialize_analysis_context(snap)
    assert b"private-profile.raw" not in raw
    assert b"private-name.raw" not in raw
    decoded = parse_analysis_context(raw)
    assert decoded["sources"][0]["native_interpretation"] == interpretation.to_portable()


def test_yuv_native_plane_shapes_and_chroma_footprint_roundtrip() -> None:
    frame = NativeYuvFrame(
        y=np.zeros((8, 10), dtype=np.uint8),
        u=np.zeros((4, 5), dtype=np.uint8),
        v=np.zeros((4, 5), dtype=np.uint8),
        layout="YUV420",
    )
    document = ImageDocument.from_yuv(frame, "private-yuv-name.yuv")
    interpretation = native_interpretation(document)
    assert interpretation.yuv_layout == "YUV420"
    assert interpretation.yuv_chroma_step_xy == (2, 2)
    assert interpretation.yuv_plane_shapes == ((8, 10), (4, 5), (4, 5))
    assert (
        AnalysisNativeInterpretationV1.from_portable(interpretation.to_portable()) == interpretation
    )
    base = _snapshot()
    digest = native_profile_signature(document)
    source = replace(
        base.sources[0],
        native_shape=document.shape,
        reference_shape=document.reference_shape,
        native_dtype=str(document.original_dtype),
        channel_layout=document.channel_layout,
        effective_bits=document.bit_depth,
        profile_signature=digest,
        native_interpretation=interpretation,
    )
    snap = replace(
        base,
        token=replace(base.token, profile_signatures=(digest,)),
        sources=(source,),
    )
    payload = serialize_analysis_context(snap)
    assert b"private-yuv-name" not in payload
    restored = parse_analysis_context(payload)
    assert restored["sources"][0]["native_interpretation"] == interpretation.to_portable()


def test_native_interpretation_wire_rejects_extra_paths_and_bad_planes() -> None:
    base = AnalysisNativeInterpretationV1().to_portable()
    with pytest.raises(ValueError, match="unknown native interpretation fields"):
        AnalysisNativeInterpretationV1.from_portable(base | {"source_path": "C:/secret.raw"})
    wrong_step = base | {
        "sampling_semantics": "cell_footprint",
        "sample_step_xy": [2, 2],
        "sample_phase_xy": [1, 0],
    }
    with pytest.raises(ValueError, match="zero phase"):
        AnalysisNativeInterpretationV1.from_portable(wrong_step)
    missing_planes = base | {
        "yuv_layout": "YUV420",
        "yuv_chroma_step_xy": [2, 2],
    }
    with pytest.raises(ValueError, match="three native plane"):
        AnalysisNativeInterpretationV1.from_portable(missing_planes)
    invalid_bool = base | {"raw_byte_offset": True}
    with pytest.raises(ValueError, match="RAW numeric"):
        AnalysisNativeInterpretationV1.from_portable(invalid_bool)


def test_analysis_bundle_records_omissions_and_rejects_inconsistent_availability(
    tmp_path: Path,
) -> None:
    target = tmp_path / "partial.zip"
    snap = _snapshot()
    entries = (
        AnalysisFeatureAvailabilityV1("statistics", "captured"),
        AnalysisFeatureAvailabilityV1("histogram", "stale"),
        AnalysisFeatureAvailabilityV1("line", "pending"),
        AnalysisFeatureAvailabilityV1("difference", "uncomputed"),
    )
    write_analysis_bundle(target, (snap,), availability=entries)
    verified = verify_analysis_bundle(target)
    expected = [{"feature": row.feature, "state": row.state} for row in entries]
    assert verified["availability"] == expected
    with ZipFile(target) as archive:
        context = json.loads(archive.read("data/context.json"))
    assert context["availability"] == expected
    with pytest.raises(ValueError, match="availability"):
        write_analysis_bundle(
            tmp_path / "wrong.zip",
            (snap,),
            availability=(
                AnalysisFeatureAvailabilityV1("statistics", "stale"),
                *entries[1:],
            ),
        )


def test_analysis_bundle_rejects_duplicate_feature_snapshots(tmp_path: Path) -> None:
    first = _snapshot()
    second = replace(first, snapshot_id=str(uuid4()))
    with pytest.raises(ValueError, match="one snapshot per feature"):
        write_analysis_bundle(tmp_path / "duplicate.zip", (first, second))


@pytest.mark.parametrize("layout", ["BAYER", "YUV420"])
def test_missing_native_interpretation_fails_closed_for_special_layouts(layout: str) -> None:
    base = _snapshot()
    with pytest.raises(ValueError, match="interpretation missing"):
        replace(
            base.sources[0],
            channel_layout=layout,
            native_interpretation=AnalysisNativeInterpretationV1(),
        )


@pytest.mark.parametrize("feature", ["histogram", "line"])
@pytest.mark.parametrize("series_field", ["missing", "empty"])
def test_histogram_and_line_wire_reject_missing_or_empty_series(
    feature: str,
    series_field: str,
) -> None:
    context = parse_analysis_context(serialize_analysis_context(_snapshot()))
    context["feature"] = feature
    if series_field == "missing":
        context.pop("series")
    else:
        context["series"] = []
    with pytest.raises(ValueError, match="require native series"):
        parse_analysis_context(json.dumps(context).encode("utf-8"))


@pytest.mark.parametrize("feature", ["statistics", "difference"])
def test_nonseries_wire_rejects_nonempty_native_series(feature: str) -> None:
    context = parse_analysis_context(serialize_analysis_context(_snapshot()))
    context["feature"] = feature
    context["series"] = [{
        "source_key": context["sources"][0]["source_key"],
        "channel": "R",
        "kind": "histogram",
        "coordinates": [0.0, 1.0],
        "values": [3],
        "value_states": ["finite"],
        "sample_count": 3,
        "definition_revision": "native-v1",
    }]
    with pytest.raises(ValueError, match="cannot include native series"):
        parse_analysis_context(json.dumps(context).encode("utf-8"))


def test_dto_rejects_missing_histogram_or_line_native_series() -> None:
    base = _snapshot()
    for feature in ("histogram", "line"):
        with pytest.raises(ValueError, match="require nonempty native series"):
            replace(base, token=replace(base.token, feature=feature))


def test_python_integer_histogram_counts_remain_lossless_in_bundle(tmp_path: Path) -> None:
    base = _snapshot()
    count = 2**53 + 1
    values, states = freeze_series_values((count, 4))
    assert values == (count, 4)
    assert tuple(type(value) for value in values) == (int, int)
    frozen = AnalysisSeriesV1(
        source_key=base.sources[0].source_key,
        channel="R",
        kind="histogram",
        coordinates=(0.0, 1.0, 2.0),
        values=values,
        value_states=states,
        sample_count=count + 4,
        definition_revision="native-bin-counts-v1",
    )
    snapshot = replace(
        base,
        token=replace(base.token, feature="histogram"),
        measurements=(),
        series=(frozen,),
    )
    path = tmp_path / "python-int-histogram.zip"
    write_analysis_bundle(path, (snapshot,))
    assert verify_analysis_bundle(path)["snapshot_count"] == 1
    with ZipFile(path) as archive:
        contexts = json.loads(archive.read("data/context.json"))
        measurements = json.loads(archive.read("data/measurements.json"))
    assert contexts["snapshots"][0]["series"][0]["values"] == [count, 4]
    assert measurements["snapshots"][0]["series"][0]["values"][0] == count


def test_series_rejects_bool_counts() -> None:
    with pytest.raises(ValueError, match="boolean"):
        freeze_series_values((True, False))
