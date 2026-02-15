"""Deterministic load/stability harness for radar pipeline."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from statistics import quantiles

from qiki.core.load_scenarios import ScenarioConfig, available_scenarios, build_scenario
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline


@dataclass(frozen=True)
class LoadSummary:
    scenario: str
    duration_s: float
    target_count: int
    frames: int
    avg_frame_ms: float
    p95_frame_ms: float
    max_frame_ms: float
    fusion_clusters: int
    situation_events: int
    sqlite_queue_peak: int
    dropped_events: int
    total_events_written: int


class _HarnessRuntimeError(RuntimeError):
    pass


def _is_on(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 2:
        return float(values[0])
    return float(quantiles(values, n=100, method="inclusive")[94])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qiki-load-harness", description="QIKI load/stability harness")
    parser.add_argument("--scenario", required=True, choices=available_scenarios())
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--targets", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--fusion", choices=("on", "off"), default="on")
    parser.add_argument("--sqlite", choices=("on", "off"), default="off")
    parser.add_argument("--db-path", default="artifacts/load_harness_eventstore.sqlite")
    parser.add_argument("--avg-threshold", type=float, default=80.0)
    parser.add_argument("--max-threshold", type=float, default=250.0)
    return parser


def run_harness(args: argparse.Namespace) -> LoadSummary:
    os.environ["RADAR_FUSION_ENABLED"] = "1" if args.fusion == "on" else "0"
    os.environ["RADAR_EMIT_OBSERVATION_RX"] = "0"

    strict_load = _is_on(os.getenv("QIKI_LOAD_STRICT", "0"))
    backend = "sqlite" if args.sqlite == "on" else "memory"

    batch_size = 400 if backend == "memory" else 1000
    queue_max = 50_000 if backend == "memory" else 250_000
    flush_ms = 20 if backend == "memory" else 5
    store = EventStore(
        maxlen=200_000,
        enabled=True,
        backend=backend,
        db_path=str(args.db_path),
        batch_size=batch_size,
        queue_max=queue_max,
        flush_ms=flush_ms,
        strict=strict_load,
    )
    pipeline = RadarPipeline(event_store=store)
    queue_peak = 0

    try:
        frames = build_scenario(
            args.scenario,
            ScenarioConfig(
                seed=int(args.seed),
                duration_s=float(args.duration),
                target_count=int(args.targets),
            ),
        )
        for frame in frames:
            pipeline.render_observations(
                list(frame.observations),
                truth_state=frame.truth_state,
                reason=frame.reason,
                is_fallback=frame.is_fallback,
            )
            queue_peak = max(queue_peak, store.sqlite_queue_depth)
            if strict_load:
                health = pipeline.health_snapshot()
                if health.overall == "CRIT":
                    issues = ", ".join(health.top_issues) if health.top_issues else "HEALTH_CRIT"
                    raise _HarnessRuntimeError(f"health_crit: {issues}")

        perf = pipeline.snapshot_metrics()
        stats = store.stats()
        frame_times = list(perf.frame_times_ms)
        summary = LoadSummary(
            scenario=args.scenario,
            duration_s=float(args.duration),
            target_count=int(args.targets),
            frames=len(frame_times),
            avg_frame_ms=float(perf.avg_frame_ms),
            p95_frame_ms=_p95(frame_times),
            max_frame_ms=float(perf.max_frame_ms),
            fusion_clusters=len(store.filter(subsystem="FUSION", event_type="FUSION_CLUSTER_BUILT")),
            situation_events=len(store.filter(subsystem="SITUATION")),
            sqlite_queue_peak=max(queue_peak, store.sqlite_queue_depth),
            dropped_events=int(perf.dropped_events),
            total_events_written=int(stats.rows),
        )

        if strict_load:
            health = pipeline.health_snapshot()
            if health.overall == "CRIT":
                issues = ", ".join(health.top_issues) if health.top_issues else "HEALTH_CRIT"
                raise _HarnessRuntimeError(f"health_crit: {issues}")
            if summary.avg_frame_ms > float(args.avg_threshold):
                raise _HarnessRuntimeError(
                    f"avg_frame_ms exceeded threshold: {summary.avg_frame_ms:.2f} > {float(args.avg_threshold):.2f}"
                )
            if summary.max_frame_ms > float(args.max_threshold):
                raise _HarnessRuntimeError(
                    f"max_frame_ms exceeded threshold: {summary.max_frame_ms:.2f} > {float(args.max_threshold):.2f}"
                )
            if summary.dropped_events > 0:
                raise _HarnessRuntimeError(f"dropped_events={summary.dropped_events}")

        return summary
    finally:
        pipeline.close()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_harness(args)
    except _HarnessRuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps({"ok": True, **summary.__dict__}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
