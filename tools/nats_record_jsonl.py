from __future__ import annotations

import asyncio
import os
from argparse import ArgumentParser
from pathlib import Path

from qiki.shared.record_replay import record_jsonl


async def main() -> int:
    parser = ArgumentParser(description="Record NATS subjects to JSONL (Phase1 tooling, no-mocks)")
    parser.add_argument(
        "--subjects",
        default="qiki.telemetry,qiki.events.v1.>",
        help="Comma-separated NATS subjects to subscribe to (default: qiki.telemetry,qiki.events.v1.>)",
    )
    parser.add_argument("--duration-s", type=float, default=3.0, help="Record duration in seconds (default: 3.0)")
    parser.add_argument("--out", default="recording.jsonl", help="Output path (default: recording.jsonl)")
    args = parser.parse_args()

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    subjects = [s.strip() for s in str(args.subjects).split(",") if s.strip()]
    out_path = Path(str(args.out))

    result = await record_jsonl(
        nats_url=nats_url,
        subjects=subjects,
        duration_s=float(args.duration_s),
        output_path=out_path,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))

