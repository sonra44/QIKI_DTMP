from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

import project_introspector.scanner as scanner_module
from project_introspector import EventEmitter, instrument_function


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one end-to-end live runtime flow against the analyzer."
    )
    parser.add_argument(
        "--analyzer-url",
        default="http://127.0.0.1:8011",
        help="Analyzer base URL.",
    )
    parser.add_argument(
        "--project-name",
        default="project-introspector",
        help="Logical project name stored by the analyzer.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    source_root = repo_root / "src"
    analyzer_url = args.analyzer_url.rstrip("/")

    static_snapshot = scanner_module.scan_project(source_root, project_name=args.project_name)
    static_response = httpx.post(
        f"{analyzer_url}/events/static",
        json=static_snapshot.model_dump(mode="json"),
        timeout=30.0,
    )
    static_response.raise_for_status()

    emitter = EventEmitter(
        endpoint=f"{analyzer_url}/events/runtime",
        project_name=args.project_name,
        batch_size=1,
        timeout_seconds=5.0,
    )
    instrumented_scan = instrument_function(
        emitter=emitter,
        capture_args=False,
        capture_result=False,
        extra_tags={"flow": "live_runtime_scan"},
    )(scanner_module.scan_project)

    runtime_snapshot = instrumented_scan(source_root, project_name=args.project_name)
    emitter.flush()

    schema_response = httpx.get(f"{analyzer_url}/schema/{args.project_name}", timeout=30.0)
    schema_response.raise_for_status()
    schema = schema_response.json()

    target_symbol = "project_introspector.scanner.scan_project"
    matching_symbol = next(
        (
            symbol
            for symbol in schema.get("symbols", [])
            if symbol.get("qualified_name") == target_symbol
        ),
        None,
    )

    result = {
        "flow": "project_introspector.scanner.scan_project",
        "source_root": str(source_root),
        "static_modules_uploaded": len(static_snapshot.modules),
        "runtime_modules_seen": len(runtime_snapshot.modules),
        "schema_runtime_event_count": schema.get("runtime_event_count"),
        "instrumented_symbol": target_symbol,
        "instrumented_symbol_runtime_call_count": (
            matching_symbol.get("runtime_call_count") if matching_symbol else None
        ),
        "schema_lookup_found": matching_symbol is not None,
        "static_response": static_response.json(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
