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

from project_introspector.models import LLMModuleAnalysis
from project_introspector.scanner import scan_project


DEFAULT_MODULE_LIMIT = 3


def _module_exists(source_root: Path, module_path: str) -> bool:
    module_fs_path = source_root.joinpath(*module_path.split("."))
    return module_fs_path.with_suffix(".py").exists() or (module_fs_path / "__init__.py").exists()


def _default_source_root(introspector_root: Path) -> Path:
    candidates = [introspector_root / "src", introspector_root.parent / "src"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return introspector_root / "src"


def _discover_default_modules(source_root: Path, *, limit: int = DEFAULT_MODULE_LIMIT) -> list[str]:
    candidates: list[tuple[tuple[int, int, str], str]] = []
    interesting_tokens = (
        "app",
        "api",
        "main",
        "server",
        "service",
        "handler",
        "bridge",
        "store",
        "client",
        "runtime",
        "console",
        "operator",
        "mission",
        "control",
    )
    for path in source_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        relative = path.relative_to(source_root)
        if any(part in {"test", "tests", "example", "examples", "mock", "mocks"} for part in relative.parts):
            continue
        module_path = ".".join(relative.with_suffix("").parts)
        token_score = sum(1 for token in interesting_tokens if token in module_path)
        depth_penalty = len(relative.parts)
        candidates.append(((-token_score, depth_penalty, module_path), module_path))
    candidates.sort()
    selected = [module_path for _key, module_path in candidates[:limit]]
    if selected:
        return selected
    fallback = sorted(
        ".".join(path.relative_to(source_root).with_suffix("").parts)
        for path in source_root.rglob("*.py")
        if path.name != "__init__.py"
    )
    return fallback[:limit]


def parse_args() -> argparse.Namespace:
    introspector_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run a reproducible live module-analysis pass.")
    parser.add_argument("--analyzer-url", default=os.getenv("INTROSPECTOR_ANALYZER_URL", "http://127.0.0.1:8015"))
    parser.add_argument("--project-name", default="INTROSPECTOR_DEMO")
    parser.add_argument(
        "--source-root",
        default=os.getenv("INTROSPECTOR_SOURCE_ROOT") or str(_default_source_root(introspector_root)),
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("INTROSPECTOR_OUTPUT_DIR") or str(introspector_root / "tmp" / "live_module_pass"),
    )
    parser.add_argument("--module", action="append", dest="modules", default=None)
    parser.add_argument(
        "--skip-factual-refresh",
        action="store_true",
        help="Use the existing schema/runtime layer as-is and run enrichment only.",
    )
    parser.add_argument(
        "--allow-unconfigured-provider",
        action="store_true",
        help="Allow the script to continue even if /llm/status reports configured=false.",
    )
    return parser.parse_args()


def _slug(module_path: str) -> str:
    return module_path.split(".")[-1]


def _ensure_modules_exist(source_root: Path, modules: list[str]) -> None:
    missing = [module_path for module_path in modules if not _module_exists(source_root, module_path)]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(f"source-root preflight failed; missing modules under {source_root}: {joined}")


def _validate_llm_status(
    status_payload: dict[str, Any],
    *,
    analyzer_url: str,
    allow_unconfigured_provider: bool,
) -> None:
    if status_payload.get("configured"):
        return
    if allow_unconfigured_provider:
        return
    provider_name = str(status_payload.get("provider_name") or "provider")
    raise RuntimeError(
        "provider-backed replay preflight failed: "
        f"{analyzer_url}/llm/status reported configured=false for {provider_name}. "
        "Export matching provider credentials before running scripts/run_fresh_analyzer.sh, "
        "or pass --allow-unconfigured-provider only when you intentionally want a degraded-path check."
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_module_name(module_path: str) -> str:
    return module_path.replace("/", "_").replace(".", "__")


def _artifact_doc_key(module_path: str, *, cheap_mode: bool) -> str:
    suffix = "_cheap" if cheap_mode else ""
    return f"ops_live_module_{_safe_module_name(module_path)}{suffix}"


def main() -> None:
    args = parse_args()
    analyzer_url = args.analyzer_url.rstrip("/")
    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    modules = args.modules or _discover_default_modules(source_root)
    _ensure_modules_exist(source_root, modules)

    progress_path = output_dir / "progress.log"

    def progress(message: str) -> None:
        print(message)
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    summary: dict[str, object] = {
        "operation": "enrichment_replay",
        "phase": "llm_enrichment",
        "project_name": args.project_name,
        "analyzer_url": analyzer_url,
        "source_root": str(source_root),
        "output_dir": str(output_dir),
        "modules": modules,
        "artifacts": [],
        "artifact_docs": [],
        "factual_refresh": {
            "status": "skipped" if args.skip_factual_refresh else "pending",
            "schema_ready": False,
            "runtime_merged": False,
            "runtime_event_count": 0,
        },
        "enrichment": {
            "status": "pending",
            "provider_configured": False,
            "modules_requested": len(modules),
            "modules_done": 0,
            "modules_degraded": 0,
            "modules_failed": 0,
        },
        "module_results": [],
    }

    snapshot = None

    with httpx.Client(timeout=120.0) as client:
        progress("enrichment queue started")
        status_response = client.get(f"{analyzer_url}/llm/status")
        status_response.raise_for_status()
        (output_dir / "llm_status.json").write_text(status_response.text, encoding="utf-8")
        status_payload = status_response.json()
        _validate_llm_status(
            status_payload,
            analyzer_url=analyzer_url,
            allow_unconfigured_provider=args.allow_unconfigured_provider,
        )
        summary["llm_status"] = status_payload
        summary["enrichment"]["provider_configured"] = bool(status_payload.get("configured"))

        if args.skip_factual_refresh:
            progress("factual refresh skipped: using existing schema/runtime layer")
            schema_response = client.get(f"{analyzer_url}/schema/{args.project_name}")
            schema_response.raise_for_status()
            schema_payload = schema_response.json()
            summary["factual_refresh"] = {
                "status": "skipped",
                "schema_ready": True,
                "runtime_merged": bool(schema_payload.get("runtime_event_count")),
                "runtime_event_count": int(schema_payload.get("runtime_event_count", 0) or 0),
            }
        else:
            progress("factual refresh started")
            progress("factual refresh: static scan started")
            snapshot = scan_project(source_root, project_name=args.project_name)
            progress(
                f"factual refresh: modules discovered={len(snapshot.modules)} scan_errors={len(snapshot.scan_errors)}"
            )
            static_response = client.post(
                f"{analyzer_url}/events/static",
                json=snapshot.model_dump(mode="json"),
            )
            static_response.raise_for_status()
            progress("schema build started")
            schema_response = client.get(f"{analyzer_url}/schema/{args.project_name}")
            schema_response.raise_for_status()
            schema_payload = schema_response.json()
            progress("schema build done")

            progress("runtime merge skipped: no synthetic runtime events injected")
            summary["factual_refresh"] = {
                "status": "done",
                "schema_ready": True,
                "runtime_merged": False,
                "runtime_event_count": int(schema_payload.get("runtime_event_count", 0) or 0),
                "modules_discovered": len(snapshot.modules),
                "scan_errors": len(snapshot.scan_errors),
            }

        module_results: list[dict[str, object]] = []
        for module_path in modules:
            slug = _slug(module_path)
            module_status = "done"
            module_degraded = False
            warnings: list[str] = []
            progress(f"module enrichment running: {module_path}")
            for cheap_mode in (False, True):
                suffix = "_cheap" if cheap_mode else ""
                path = output_dir / f"{slug}{suffix}.json"
                if not status_payload.get("configured"):
                    analysis = LLMModuleAnalysis(
                        module_path=module_path,
                        llm_model=status_payload.get("fallback_model" if cheap_mode else "default_model"),
                        llm_provider=str(status_payload.get("provider_name") or "provider"),
                        degraded=True,
                        warnings=["Provider is unconfigured; enrichment request was skipped intentionally."],
                        processing_notes=[
                            "Enrichment stayed in degraded mode because /llm/status reported configured=false."
                        ],
                    )
                    degraded_payload = analysis.model_dump(mode="json")
                    _write_json(path, degraded_payload)
                    summary["artifacts"].append(str(path))
                    doc_key = _artifact_doc_key(module_path, cheap_mode=cheap_mode)
                    client.post(
                        f"{analyzer_url}/derived/{args.project_name}/{doc_key}",
                        json=degraded_payload,
                    ).raise_for_status()
                    summary["artifact_docs"].append(
                        {
                            "doc_key": doc_key,
                            "module_path": module_path,
                            "variant": "cheap" if cheap_mode else "normal",
                        }
                    )
                    warnings.extend(analysis.warnings)
                    module_degraded = True
                    module_status = "degraded"
                    continue

                params = {"module_path": module_path}
                if cheap_mode:
                    params["cheap_mode"] = "true"
                response = client.post(
                    f"{analyzer_url}/llm/analyze/module/{args.project_name}",
                    params=params,
                )
                response.raise_for_status()
                path.write_text(response.text, encoding="utf-8")
                summary["artifacts"].append(str(path))
                payload = response.json()
                doc_key = _artifact_doc_key(module_path, cheap_mode=cheap_mode)
                client.post(
                    f"{analyzer_url}/derived/{args.project_name}/{doc_key}",
                    json=payload,
                ).raise_for_status()
                summary["artifact_docs"].append(
                    {
                        "doc_key": doc_key,
                        "module_path": module_path,
                        "variant": "cheap" if cheap_mode else "normal",
                    }
                )
                payload_warnings = payload.get("warnings") or []
                warnings.extend(str(item) for item in payload_warnings)
                if payload.get("degraded"):
                    module_degraded = True
                    module_status = "degraded"

            if module_status == "degraded":
                progress(f"module enrichment degraded: {module_path}")
            else:
                progress(f"module enrichment done: {module_path}")

            module_results.append(
                {
                    "module_path": module_path,
                    "status": module_status,
                    "degraded": module_degraded,
                    "warnings_count": len(warnings),
                }
            )

        modules_done = sum(1 for item in module_results if item["status"] == "done")
        modules_degraded = sum(1 for item in module_results if item["status"] == "degraded")
        modules_failed = sum(1 for item in module_results if item["status"] == "failed")
        summary["module_results"] = module_results
        summary["enrichment"] = {
            "status": "failed"
            if modules_failed
            else "degraded"
            if modules_degraded
            else "done",
            "provider_configured": bool(status_payload.get("configured")),
            "modules_requested": len(modules),
            "modules_done": modules_done,
            "modules_degraded": modules_degraded,
            "modules_failed": modules_failed,
        }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with httpx.Client(timeout=30.0) as client:
        for item in summary.get("artifact_docs", []):
            item["updated_at"] = item.get("updated_at") or None
        client.post(
            f"{analyzer_url}/derived/{args.project_name}/ops_live_pass_summary",
            json=summary,
        ).raise_for_status()
        if "llm_status" in summary:
            client.post(
                f"{analyzer_url}/derived/{args.project_name}/ops_live_pass_status",
                json=summary["llm_status"],
            ).raise_for_status()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
