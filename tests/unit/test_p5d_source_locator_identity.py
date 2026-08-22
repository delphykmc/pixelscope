from pixelscope.remote.iqa_domain import Source


def test_storage_root_location_is_excluded_from_source_identity_and_hash() -> None:
    source_a = Source(
        source_id="source-1",
        relative_path="dataset/scene/source.png",
        sha256="1" * 64,
        width=1920,
        height=1080,
        storage_root_id="root-a",
    )
    source_b = Source(
        source_id="source-1",
        relative_path="dataset/scene/source.png",
        sha256="1" * 64,
        width=1920,
        height=1080,
        storage_root_id="root-b",
    )

    assert source_a == source_b
    assert hash(source_a) == hash(source_b)
