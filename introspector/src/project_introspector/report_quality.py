from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import LLMModuleAnalysis, ProjectSchema


MAX_LIST_ITEMS = 20


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _limited(items: Sequence[str], *, limit: int = MAX_LIST_ITEMS) -> dict[str, object]:
    values = list(items)
    return {
        "items": values[:limit],
        "total": len(values),
        "truncated": len(values) > limit,
    }


def _payload_from_derived(item: object) -> Mapping[str, Any]:
    mapping = _as_mapping(item)
    return _as_mapping(mapping.get("payload"))


def _derived_doc_key(item: object) -> str | None:
    value = _as_mapping(item).get("doc_key")
    return str(value) if value else None


def _derived_updated_at(item: object) -> str | None:
    value = _as_mapping(item).get("updated_at")
    return str(value) if value else None


def _module_analysis_from_payload(payload: Mapping[str, Any]) -> LLMModuleAnalysis | None:
    if not payload.get("module_path"):
        return None
    try:
        return LLMModuleAnalysis.model_validate(dict(payload))
    except Exception:
        return None


def _build_module_findings(derived_items: Sequence[object]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    seen: set[tuple[str, str | None]] = set()

    for item in derived_items:
        doc_key = _derived_doc_key(item)
        if not doc_key:
            continue
        if not (doc_key.startswith("llm_module_") or doc_key.startswith("ops_live_module_")):
            continue
        analysis = _module_analysis_from_payload(_payload_from_derived(item))
        if analysis is None:
            continue

        key = (analysis.module_path, doc_key)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "module_path": analysis.module_path,
                "purpose": analysis.purpose,
                "status": analysis.status,
                "activity_status": analysis.activity_status,
                "attention_status": analysis.attention_status,
                "runtime_signal_status": analysis.runtime_signal_status,
                "semantic_confidence_status": analysis.semantic_confidence_status,
                "degraded": analysis.degraded,
                "warnings": analysis.warnings,
                "actionable_hints": analysis.actionable_hints,
                "responsibilities": analysis.responsibilities,
                "public_symbols": analysis.public_symbols,
                "provider": {
                    "provider_name": analysis.llm_provider,
                    "requested_model": analysis.requested_model or analysis.llm_model,
                    "provider_model_used": analysis.provider_model_used,
                    "provider_error_kind": analysis.provider_error_kind,
                    "provider_status_code": analysis.provider_status_code,
                    "provider_retryable": analysis.provider_retryable,
                    "structured_output_used": analysis.provider_structured_output_used,
                    "structured_output_fallback": analysis.provider_structured_output_fallback,
                    "payload_truncated": bool(analysis.payload_limits.get("payload_truncated")),
                },
                "provenance": {
                    "source": "derived_doc",
                    "doc_key": doc_key,
                    "updated_at": _derived_updated_at(item),
                    "trust_layer": "llm_enrichment",
                },
            }
        )

    findings.sort(key=lambda item: (str(item["module_path"]), str(item["provenance"])))
    return findings


def compose_project_report(
    schema: ProjectSchema,
    *,
    ops_status: Mapping[str, Any] | None = None,
    scan_summary: Mapping[str, Any] | None = None,
    live_pass_summary: Mapping[str, Any] | None = None,
    derived_items: Sequence[object] | None = None,
    analyzer_url: str | None = None,
) -> dict[str, object]:
    """Compose an operator report from existing facts and derived artifacts only."""
    ops_status = ops_status or {}
    scan_summary = scan_summary or {}
    live_pass_summary = live_pass_summary or {}
    derived_items = list(derived_items or [])

    module_paths = {module.module_path for module in schema.modules}
    runtime_modules = {
        edge.target
        for edge in schema.edges
        if edge.kind == "runtime_call" and edge.target in module_paths
    }
    static_only_modules = sorted(module_paths - runtime_modules)
    import_edge_count = sum(1 for edge in schema.edges if edge.kind == "import")
    runtime_hot_symbols = [
        symbol.qualified_name
        for symbol in schema.symbols
        if symbol.runtime_call_count > 0
    ]

    live_enrichment = _as_mapping(live_pass_summary.get("enrichment"))
    live_status = _as_mapping(live_pass_summary.get("llm_status"))
    scan_factual = _as_mapping(scan_summary.get("factual_layer"))
    module_findings = _build_module_findings(derived_items)

    provider_credentials_configured = bool(live_status.get("configured")) if live_status else False
    enrichment_run_provider_configured = live_enrichment.get("provider_configured")
    provider_configured = (
        bool(enrichment_run_provider_configured)
        if enrichment_run_provider_configured is not None
        else provider_credentials_configured
    )
    enrichment_status = str(live_enrichment.get("status") or "absent")
    enrichment_artifacts_status = "absent"
    if module_findings:
        enrichment_artifacts_status = "present" if live_enrichment else "partial_no_live_pass"
    if enrichment_status == "absent" and module_findings:
        enrichment_status = enrichment_artifacts_status

    limits: list[dict[str, str]] = []
    if schema.runtime_event_count == 0:
        limits.append(
            {
                "code": "runtime_absent",
                "message": "No runtime events were present; runtime behavior is not proven by this report.",
            }
        )
    if not module_findings:
        limits.append(
            {
                "code": "enrichment_absent",
                "message": "No module enrichment artifacts were found; module interpretation is factual-only.",
            }
        )
    if enrichment_status in {"degraded", "failed"}:
        limits.append(
            {
                "code": "enrichment_degraded",
                "message": "Provider-backed enrichment is degraded or unavailable; factual scan remains usable.",
            }
        )
    if any(item.get("provider", {}).get("provider_error_kind") for item in module_findings):
        limits.append(
            {
                "code": "provider_errors_present",
                "message": "One or more enrichment artifacts contain provider error metadata.",
            }
        )
    if any(item.get("provider", {}).get("payload_truncated") for item in module_findings):
        limits.append(
            {
                "code": "payload_truncated",
                "message": "One or more LLM payloads were truncated before enrichment.",
            }
        )
    project_payloads = [
        _payload_from_derived(item)
        for item in derived_items
        if _derived_doc_key(item) == "llm_project"
    ]
    if any(payload.get("degraded") for payload in project_payloads):
        limits.append(
            {
                "code": "project_analysis_degraded",
                "message": "Project-level LLM analysis was degraded or policy-sanitized.",
            }
        )

    next_safe_steps: list[str] = []
    if schema.runtime_event_count == 0:
        next_safe_steps.append("Run a real runtime instrumentation pass before making runtime-behavior claims.")
    if enrichment_status in {"absent", "degraded", "failed", "partial_no_live_pass"}:
        next_safe_steps.append("Run or repair provider-backed module enrichment only after factual scan is green.")
    if not next_safe_steps:
        next_safe_steps.append("Review module findings against source evidence before acting on enrichment.")

    return {
        "report_version": "project-introspector.report.v1",
        "scope": {
            "project_name": schema.project_name,
            "source_root": scan_summary.get("source_root"),
            "analyzer_url": analyzer_url or scan_summary.get("analyzer_url"),
            "schema_built_at": schema.built_at.isoformat(),
            "scan_updated_at": scan_summary.get("scanned_at"),
            "latest_derived_updated_at": ops_status.get("latest_derived_updated_at"),
        },
        "factual_layer": {
            "status": "ready",
            "factual_scan_status": "ready",
            "modules_scanned": _safe_int(scan_summary.get("modules_scanned")) or schema.module_count,
            "scan_errors": _safe_int(scan_summary.get("scan_errors")),
            "schema_ready": True,
            "module_count": schema.module_count,
            "function_count": schema.function_count,
            "class_count": schema.class_count,
            "symbol_count": len(schema.symbols),
            "import_edge_count": import_edge_count,
            "runtime_event_count": schema.runtime_event_count,
            "scan_factual_layer": dict(scan_factual),
        },
        "runtime_layer": {
            "status": "absent" if schema.runtime_event_count == 0 else "present",
            "runtime_event_count": schema.runtime_event_count,
            "runtime_present_modules": _limited(sorted(runtime_modules)),
            "static_only_modules": _limited(static_only_modules),
            "runtime_hot_symbols": _limited(sorted(runtime_hot_symbols)),
        },
        "enrichment_layer": {
            "status": enrichment_status,
            "artifacts_status": enrichment_artifacts_status,
            "provider_configured": provider_configured,
            "provider_credentials_configured": provider_credentials_configured,
            "provider_probe_status": str(live_status.get("probe_status") or "not_checked") if live_status else "not_checked",
            "enrichment_run_provider_configured": (
                bool(enrichment_run_provider_configured)
                if enrichment_run_provider_configured is not None
                else None
            ),
            "provider_name": live_status.get("provider_name"),
            "default_model": live_status.get("default_model"),
            "fallback_model": live_status.get("fallback_model"),
            "modules_requested": _safe_int(live_enrichment.get("modules_requested")),
            "modules_done": _safe_int(live_enrichment.get("modules_done")),
            "modules_degraded": _safe_int(live_enrichment.get("modules_degraded")),
            "modules_failed": _safe_int(live_enrichment.get("modules_failed")),
        },
        "module_findings": module_findings[:MAX_LIST_ITEMS],
        "module_findings_total": len(module_findings),
        "limits": limits,
        "next_safe_steps": next_safe_steps,
        "provenance": {
            "truth_layers": {
                "factual": "static scan + runtime events + schema + analyzer storage metadata",
                "enrichment": "provider-backed derived documents",
            },
            "llm_is_truth_source": False,
        },
    }
