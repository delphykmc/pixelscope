from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pixelscope.remote.iqa_localhost_server import (
    LOCALHOST_SCENARIOS,
    LocalhostIqaServer,
    LocalhostIqaServerConfig,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the debug-only P5-C Remote IQA localhost HTTP/fault server.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--scenario", choices=LOCALHOST_SCENARIOS, default="normal")
    parser.add_argument("--storage-root-id", default="debug_iqa")
    parser.add_argument(
        "--result-relative-path",
        default="results/job_debug_complete_manual1",
        help="Logical result directory returned by GET /result.",
    )
    parser.add_argument(
        "--last-request",
        type=Path,
        default=Path("temp/p5c-localhost/last_request.json"),
        help="Capture the most recent create-job request JSON here.",
    )
    parser.add_argument(
        "--slow-seconds",
        type=float,
        default=35.0,
        help="Delay used only by the slow-status scenario.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = LocalhostIqaServerConfig(
            scenario=args.scenario,
            storage_root_id=args.storage_root_id,
            result_relative_path=args.result_relative_path,
            last_request_path=args.last_request,
            slow_seconds=args.slow_seconds,
        )
        server = LocalhostIqaServer(config, host=args.host, port=args.port)
    except (OSError, ValueError) as exc:
        print(f"P5-C localhost server setup failed: {exc}", file=sys.stderr)
        return 2

    print(f"Remote IQA localhost server: {server.base_url}")
    print(f"Scenario: {config.scenario}")
    print(f"Published result reference: {config.storage_root_id}:{config.result_relative_path}")
    if config.last_request_path is not None:
        print(f"Last request capture: {config.last_request_path}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping P5-C localhost server.")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
