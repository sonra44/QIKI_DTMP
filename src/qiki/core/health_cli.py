"""CLI for runtime health snapshot dump."""

from __future__ import annotations

import argparse
import json

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qiki-health", description="QIKI health snapshot CLI")
    parser.add_argument("--json", action="store_true", help="Print JSON snapshot (default).")
    parser.add_argument("--renderer", default="unicode")
    parser.add_argument("--fps", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = EventStore.from_env()
    pipeline = RadarPipeline(
        RadarRenderConfig(
            renderer=str(args.renderer or "unicode"),
            view="top",
            fps_max=max(1, int(args.fps)),
            color=True,
        ),
        event_store=store,
    )
    try:
        # Prime runtime metrics once so snapshot is meaningful even from cold start.
        pipeline.render_observations([], truth_state="NO_DATA", reason="NO_DATA")
        snapshot = pipeline.health_snapshot()
        payload = {"snapshot": snapshot.to_dict(), "top_issues": list(snapshot.top_issues)}
        print(json.dumps(payload, ensure_ascii=True))
    finally:
        pipeline.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

