from __future__ import annotations

import asyncio
import os
from argparse import ArgumentParser
from pathlib import Path

from qiki.shared.record_replay import replay_jsonl


async def main() -> int:
    parser = ArgumentParser(description="Replay JSONL to NATS subjects (Phase1 tooling, no-mocks)")
    parser.add_argument("--in", dest="input_path", required=True, help="Input JSONL path")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier (default: 1.0)")
    parser.add_argument(
        "--subject-prefix",
        default="",
        help="Optional prefix to publish into (prefix.<original-subject>) for isolation",
    )
    parser.add_argument(
        "--no-timing",
        action="store_true",
        help="Publish without timing delays (as fast as possible)",
    )
    args = parser.parse_args()

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    prefix = str(args.subject_prefix).strip()
    result = await replay_jsonl(
        nats_url=nats_url,
        input_path=Path(str(args.input_path)),
        speed=float(args.speed),
        subject_prefix=prefix if prefix else None,
        no_timing=bool(args.no_timing),
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))

