from __future__ import annotations

import argparse
from pathlib import Path

from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic P5-A2 IQA schema-v2 fixture"
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--scene-count", type=int, default=4)
    arguments = parser.parse_args()
    write_golden_result_v2(arguments.output, arguments.scene_count)


if __name__ == "__main__":
    main()
