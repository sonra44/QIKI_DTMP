from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import types
from typing import Any

import httpx

from project_introspector import EventEmitter, instrument_function, scan_project


def parse_args() -> argparse.Namespace:
    introspector_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run one QIKI_DTMP live runtime flow around q-bios-service."
    )
    parser.add_argument(
        "--analyzer-url",
        default="http://127.0.0.1:8011",
        help="Analyzer base URL.",
    )
    parser.add_argument(
        "--project-name",
        default="QIKI_DTMP",
        help="Project name stored in analyzer.",
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("QIKI_REPO_ROOT") or str(introspector_root.parent),
        help="QIKI_DTMP repo root that contains src/ and generated/.",
    )
    return parser.parse_args()


def write_bot_config(path: Path, *, schema_version: str) -> None:
    payload = {
        "schema_version": schema_version,
        "hardware_profile": {
            "sensors": [{"id": "imu_main", "type": "imu"}],
            "actuators": [{"id": "motor_left", "type": "wheel_motor"}],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


async def run_flow(*, analyzer_url: str, project_name: str, repo_root: Path) -> dict[str, Any]:
    source_root = repo_root / "src"
    generated_root = repo_root / "generated"
    if str(generated_root) not in sys.path:
        sys.path.insert(0, str(generated_root))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    health_checker_module = types.ModuleType("qiki.services.q_bios_service.health_checker")

    @dataclass(frozen=True, slots=True)
    class StubSimHealthResult:
        ok: bool
        message: str

    def stub_check_qsim_health(*, host: str, port: int, timeout_s: float) -> StubSimHealthResult:
        return StubSimHealthResult(ok=True, message="ok")

    health_checker_module.SimHealthResult = StubSimHealthResult
    health_checker_module.check_qsim_health = stub_check_qsim_health
    sys.modules["qiki.services.q_bios_service.health_checker"] = health_checker_module

    from qiki.services.q_bios_service.config import BiosConfig
    from qiki.services.q_bios_service.main import BiosService

    static_snapshot = scan_project(source_root, project_name=project_name)
    static_response = httpx.post(
        f"{analyzer_url}/events/static",
        json=static_snapshot.model_dump(mode="json"),
        timeout=60.0,
    )
    static_response.raise_for_status()

    emitter = EventEmitter(
        endpoint=f"{analyzer_url}/events/runtime",
        project_name=project_name,
        batch_size=1,
        timeout_seconds=5.0,
    )

    from qiki.services.q_bios_service import main as bios_main_module

    published: list[tuple[str, dict[str, Any]]] = []
    closed = {"value": False}
    cfg_path = repo_root / "introspector" / "tmp" / "bios_runtime_flow_bot_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    write_bot_config(cfg_path, schema_version="1.0")

    service = BiosService(
        BiosConfig(
            bot_config_path=str(cfg_path),
            nats_url="nats://example:4222",
            nats_subject="qiki.events.v1.bios_status",
            publish_enabled=True,
            publish_interval_s=0.2,
        )
    )

    class FakePublisher:
        def __init__(self, *, nats_url: str) -> None:
            self.nats_url = nats_url

        async def publish_json(self, *, subject: str, payload: dict[str, Any]) -> None:
            published.append((subject, payload))
            service.stop()

        async def close(self) -> None:
            closed["value"] = True

    bios_main_module.NatsJsonPublisher = FakePublisher

    instrumented_publisher_loop = instrument_function(
        emitter=emitter,
        capture_args=False,
        capture_result=False,
        extra_tags={"flow": "q_bios_service_publish_once"},
    )(service._publisher_loop)

    await instrumented_publisher_loop()
    emitter.flush()

    schema_response = httpx.get(f"{analyzer_url}/schema/{project_name}", timeout=60.0)
    schema_response.raise_for_status()
    schema = schema_response.json()

    target_symbol = "qiki.services.q_bios_service.main.BiosService._publisher_loop"
    matching_symbol = next(
        (
            symbol
            for symbol in schema.get("symbols", [])
            if symbol.get("qualified_name") == target_symbol
        ),
        None,
    )

    runtime_path = repo_root / "introspector" / "analyzer" / "data" / f"{project_name}.runtime.json"
    runtime_events = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.exists() else []

    last_runtime_event = None
    for event in reversed(runtime_events):
        if event.get("qualified_name") == target_symbol:
            last_runtime_event = event
            break

    published_subject, published_payload = published[0]
    return {
        "flow": "qiki.events.v1.bios_status via BiosService._publisher_loop",
        "static_modules_uploaded": len(static_snapshot.modules),
        "published_subject": published_subject,
        "published_payload_subject": published_payload.get("subject"),
        "published_payload_source": published_payload.get("source"),
        "runtime_event_count_in_schema": schema.get("runtime_event_count"),
        "instrumented_symbol": target_symbol,
        "instrumented_symbol_runtime_call_count": (
            matching_symbol.get("runtime_call_count") if matching_symbol else None
        ),
        "runtime_store_path": str(runtime_path),
        "runtime_store_event_found": last_runtime_event is not None,
        "runtime_store_last_event": last_runtime_event,
        "publisher_closed": closed["value"],
        "static_response": static_response.json(),
    }


def main() -> None:
    args = parse_args()
    result = asyncio.run(
        run_flow(
            analyzer_url=args.analyzer_url.rstrip("/"),
            project_name=args.project_name,
            repo_root=Path(args.repo_root).resolve(),
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
