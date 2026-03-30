"""Trace CLI for EventStore JSONL export."""

from __future__ import annotations

import argparse
import sys
import time

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.trace_export import (
    TraceExportFilter,
    export_event_store_jsonl_async,
    parse_csv_set,
    parse_sample_map,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qiki-trace", description="Trace tooling for QIKI EventStore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export", help="Export EventStore snapshot to JSONL")
    export.add_argument("--out", required=True, help="Output JSONL path")
    export.add_argument("--from", dest="from_ts", type=float, default=None, help="Window start (unix seconds)")
    export.add_argument("--to", dest="to_ts", type=float, default=None, help="Window end (unix seconds)")
    export.add_argument("--types", default="", help="Comma-separated event types")
    export.add_argument("--subsystems", default="", help="Comma-separated subsystem list")
    export.add_argument("--truth", default="", help="Comma-separated truth state filter")
    export.add_argument("--max-lines", type=int, default=10000, help="Hard line cap for export")
    export.add_argument(
        "--sample",
        default="",
        help="Per-event-type sampling map, e.g. RADAR_RENDER_TICK=10,SITUATION_UPDATED=2",
    )
    return parser


def _run_export(args: argparse.Namespace) -> int:
    now = time.time()
    from_ts = args.from_ts if args.from_ts is not None else (now - 60.0)
    to_ts = args.to_ts if args.to_ts is not None else now
    event_store = EventStore.from_env()
    export_filter = TraceExportFilter(
        from_ts=float(from_ts),
        to_ts=float(to_ts),
        types=parse_csv_set(args.types),
        subsystems=parse_csv_set(args.subsystems),
        truth_states=parse_csv_set(args.truth),
        max_lines=max(1, int(args.max_lines)),
        sample_every_by_type=parse_sample_map(args.sample),
    )
    result = export_event_store_jsonl_async(event_store, args.out, export_filter=export_filter, now_ts=now)
    print(
        "TRACE_EXPORT_OK "
        f"out={result.out_path} lines={result.lines_written} "
        f"from={result.from_ts:.3f} to={result.to_ts:.3f} duration_ms={result.duration_ms:.2f}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        return _run_export(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
