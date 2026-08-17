from __future__ import annotations

import argparse
from pathlib import Path

from pixelscope.remote.iqa_fixture import write_golden_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the deterministic P5-A IQA v1 fixture")
    parser.add_argument("output", type=Path)
    parser.add_argument("--scene-count", type=int, default=11)
    arguments = parser.parse_args()
    write_golden_result(arguments.output, arguments.scene_count)


if __name__ == "__main__":
    main()
