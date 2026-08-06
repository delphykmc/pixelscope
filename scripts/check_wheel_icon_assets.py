from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

EXPECTED_ASSETS = (
    "pixelscope/assets/icons/pixelscope.svg",
    "pixelscope/assets/icons/pixelscope.png",
    "pixelscope/assets/icons/pixelscope.ico",
)


def _resolve_wheel(path: Path) -> Path:
    if path.is_file():
        if path.suffix != ".whl":
            raise ValueError(f"not a wheel file: {path}")
        return path

    wheels = sorted(path.glob("pixelscope-*.whl"))
    if len(wheels) != 1:
        raise ValueError(
            f"expected exactly one pixelscope wheel under {path}, found {len(wheels)}"
        )
    return wheels[0]


def check_wheel(path: Path) -> None:
    wheel = _resolve_wheel(path)
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        missing = [name for name in EXPECTED_ASSETS if name not in names]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"{wheel.name} is missing packaged icon assets: {joined}")
        empty = [name for name in EXPECTED_ASSETS if not archive.read(name)]
        if empty:
            joined = ", ".join(empty)
            raise RuntimeError(f"{wheel.name} contains empty icon assets: {joined}")

    print(f"Wheel icon assets verified: {wheel}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the canonical PixelScope icons are present in a wheel."
    )
    parser.add_argument(
        "wheel_or_directory",
        type=Path,
        help="wheel path or directory containing exactly one pixelscope wheel",
    )
    args = parser.parse_args()
    check_wheel(args.wheel_or_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
