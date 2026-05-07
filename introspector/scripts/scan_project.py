from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


# Allow loose script execution from a source checkout without requiring pip install -e .
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import httpx

from project_introspector.scanner import scan_project
from project_introspector.schema_builder import build_schema


def _default_source_root(introspector_root: Path) -> Path:
    candidates = [introspector_root / "src", introspector_root.parent / "src"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return introspector_root / "src"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_args() -> argparse.Namespace:
    introspector_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run a factual project scan and optionally upload it to analyzer.")
    parser.add_argument("--analyzer-url", default=os.getenv("INTROSPECTOR_ANALYZER_URL", "http://127.0.0.1:8015"))
    parser.add_argument("--project-name", default="INTROSPECTOR_DEMO")
    parser.add_argument(
        "--source-root",
        default=os.getenv("INTROSPECTOR_SOURCE_ROOT") or str(_default_source_root(introspector_root)),
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("INTROSPECTOR_SCAN_OUTPUT_DIR") or str(introspector_root / "tmp" / "project_scan"),
    )
    parser.add_argument("--offline", action="store_true", help="Write local scan artifacts without contacting analyzer.")
    parser.add_argument("--no-upload", action="store_true", help="Alias for --offline in this version.")
    parser.add_argument("--snapshot-out", default=None, help="Path to write static snapshot JSON.")
    parser.add_argument("--summary-out", default=None, help="Path to write scan summary JSON.")
    parser.add_argument("--schema-out", default=None, help="Path to write schema JSON.")
    return parser.parse_args()


def _summary_payload(
    *,
    args: argparse.Namespace,
    source_root: Path,
    output_dir: Path,
    snapshot_path: Path,
    schema_path: Path | None,
    mode: str,
    uploaded: bool,
    analyzer_url: str | None,
    modules_scanned: int,
    scan_errors: int,
    scanned_at: str,
    runtime_event_count: int,
    schema_ready: bool,
    derived_summary_published: bool = False,
) -> dict[str, Any]:
    return {
        "operation": "scan_project",
        "phase": "factual_scan",
        "mode": mode,
        "project_name": args.project_name,
        "analyzer_url": analyzer_url,
        "source_root": str(source_root),
        "modules_scanned": modules_scanned,
        "scan_errors": scan_errors,
        "scanned_at": scanned_at,
        "output_dir": str(output_dir),
        "snapshot_path": str(snapshot_path),
        "schema_path": str(schema_path) if schema_path else None,
        "uploaded": uploaded,
        "schema_ready": schema_ready,
        "schema_fetched": uploaded and schema_ready,
        "derived_summary_published": derived_summary_published,
        "factual_layer": {
            "status": "ready" if scan_errors == 0 else "degraded",
            "schema_ready": schema_ready,
            "runtime_merged": runtime_event_count > 0,
            "runtime_event_count": runtime_event_count,
            "modules_discovered": modules_scanned,
            "scan_errors": scan_errors,
        },
    }


def main() -> None:
    args = parse_args()
    analyzer_url = args.analyzer_url.rstrip("/")
    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    offline = bool(args.offline or args.no_upload)

    snapshot_out = Path(args.snapshot_out).resolve() if args.snapshot_out else output_dir / "static_snapshot.json"
    summary_out = Path(args.summary_out).resolve() if args.summary_out else output_dir / "summary.json"
    schema_out = Path(args.schema_out).resolve() if args.schema_out else output_dir / "schema.json"

    print("factual scan: static scan started")
    snapshot = scan_project(source_root, project_name=args.project_name)
    print(f"factual scan: modules discovered={len(snapshot.modules)} scan_errors={len(snapshot.scan_errors)}")
    _write_json(snapshot_out, snapshot.model_dump(mode="json"))
    print(f"factual scan: static snapshot written={snapshot_out}")

    if offline:
        schema = build_schema(snapshot, [])
        _write_json(schema_out, schema.model_dump(mode="json"))
        summary = _summary_payload(
            args=args,
            source_root=source_root,
            output_dir=output_dir,
            snapshot_path=snapshot_out,
            schema_path=schema_out,
            mode="offline",
            uploaded=False,
            analyzer_url=None,
            modules_scanned=len(snapshot.modules),
            scan_errors=len(snapshot.scan_errors),
            scanned_at=snapshot.scanned_at.isoformat(),
            runtime_event_count=0,
            schema_ready=True,
        )
        _write_json(summary_out, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    try:
        with httpx.Client(timeout=120.0) as client:
            print("factual scan: static snapshot upload started")
            response = client.post(
                f"{analyzer_url}/events/static",
                json=snapshot.model_dump(mode="json"),
            )
            response.raise_for_status()
            print("factual scan: static snapshot upload done")

            print("schema build started")
            schema_response = client.get(f"{analyzer_url}/schema/{args.project_name}")
            schema_response.raise_for_status()
            schema_payload = schema_response.json()
            print("schema build done")
    except Exception:
        print(f"Analyzer is unavailable or rejected the scan. Static snapshot was written to {snapshot_out}.")
        print("Run with --offline to avoid analyzer upload.")
        raise

    _write_json(schema_out, schema_payload)
    runtime_event_count = int(schema_payload.get("runtime_event_count", 0) or 0)
    print("runtime merge started")
    print(f"runtime merge done: runtime_events={runtime_event_count}")

    summary = _summary_payload(
        args=args,
        source_root=source_root,
        output_dir=output_dir,
        snapshot_path=snapshot_out,
        schema_path=schema_out,
        mode="analyzer_upload",
        uploaded=True,
        analyzer_url=analyzer_url,
        modules_scanned=len(snapshot.modules),
        scan_errors=len(snapshot.scan_errors),
        scanned_at=snapshot.scanned_at.isoformat(),
        runtime_event_count=runtime_event_count,
        schema_ready=True,
        derived_summary_published=True,
    )
    _write_json(summary_out, summary)
    with httpx.Client(timeout=30.0) as client:
        client.post(
            f"{analyzer_url}/derived/{args.project_name}/ops_project_scan_summary",
            json=summary,
        ).raise_for_status()
    _write_json(summary_out, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
