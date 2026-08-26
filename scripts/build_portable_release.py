from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_third_party_notices import write_third_party_notices  # noqa: E402
from scripts.distribution_contract import (  # noqa: E402
    MANIFEST_MEMBER_NAME,
    NOTICE_MEMBER_NAME,
    RELEASE_ROOT,
    portable_zip_path,
    release_stem,
    write_payload_manifest,
)
from scripts.release_contract import APP_DIR  # noqa: E402
from scripts.validate_release_artifact import validate_artifact  # noqa: E402

_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _payload_files(root: Path) -> list[Path]:
    root = root.resolve()
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def _write_zip_member(
    archive: zipfile.ZipFile,
    source: Path,
    member_name: PurePosixPath,
) -> None:
    info = zipfile.ZipInfo(member_name.as_posix(), date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with source.open("rb") as source_handle, archive.open(info, mode="w") as output_handle:
        shutil.copyfileobj(source_handle, output_handle, length=1024 * 1024)


def build_portable_release() -> Path:
    validate_artifact(APP_DIR)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = write_payload_manifest(APP_DIR)
    notices = write_third_party_notices()
    output = portable_zip_path()
    output.unlink(missing_ok=True)

    archive_root = PurePosixPath(release_stem())
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in _payload_files(APP_DIR):
            relative = PurePosixPath(source.relative_to(APP_DIR).as_posix())
            _write_zip_member(archive, source, archive_root / relative)
        _write_zip_member(archive, manifest, archive_root / MANIFEST_MEMBER_NAME)
        _write_zip_member(archive, notices, archive_root / NOTICE_MEMBER_NAME)

    return output


def main() -> int:
    output = build_portable_release()
    print(f"Portable PixelScope release written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
