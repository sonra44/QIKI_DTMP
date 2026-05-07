from __future__ import annotations

from collections.abc import Callable

from .artifact_freshness import evaluate_artifact_freshness
from .models import LLMModuleAnalysis, ModuleFact
from .operator_next import operator_next_step
from .operator_state import OperatorModuleRow, OperatorState
from .tui_table_model import build_operator_module_table_rows, filter_operator_modules, format_signal_counts
from .tui_action_history import OperatorActionHistoryEntry
from .tui_models import (
    AnalyzerStatus,
    ArtifactReference,
    LivePassSummary,
    ModuleAnalysisArtifact,
    ModuleOverviewRow,
    ProjectScanSummary,
)
from .tui_text import localize_semantic_list, localize_semantic_text


def _compact_path(path: str, max_len: int = 72) -> str:
    if len(path) <= max_len:
        return path
    parts = path.split("/")
    if len(parts) < 3:
        return _truncate(path, max_len)
    tail = "/".join(parts[-2:])
    prefix = ".../"
    if len(prefix) + len(tail) <= max_len:
        return prefix + tail
    return _truncate(path, max_len)


def _compact_module_path(module_path: str, max_len: int = 44) -> str:
    if len(module_path) <= max_len:
        return module_path
    parts = module_path.split(".")
    if len(parts) < 3:
        return _truncate(module_path, max_len)
    tail = ".".join(parts[-3:])
    prefix = "..."
    if len(prefix) + len(tail) <= max_len:
        return prefix + tail
    return _truncate(module_path, max_len)




def _format_signal_counts(module: OperatorModuleRow) -> str:
    return format_signal_counts(module)


def _layer_detail(layer_details: dict[str, object], *keys: str) -> str:
    parts = []
    for key in keys:
        value = layer_details.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key}={value}")
    return " | ".join(parts) if parts else "-"


def _operator_status_label(text: Callable[..., str], layer_name: str, status: object, details: dict[str, object]) -> str:
    status_value = str(status or "unknown").lower()
    if layer_name == "factual":
        scan_errors = int(details.get("scan_errors") or 0)
        if scan_errors:
            return text("operator_layer_factual_error")
        if status_value in {"ready", "present", "completed", "done"} or details.get("schema_ready"):
            return text("operator_layer_factual_ready")
    if layer_name == "runtime":
        event_count = int(details.get("runtime_event_count") or 0)
        if event_count > 0 or status_value in {"ready", "present", "completed", "done"}:
            return text("operator_layer_runtime_ready")
        return text("operator_layer_runtime_absent")
    if layer_name == "enrichment":
        modules_done = int(details.get("modules_done") or 0)
        if status_value in {"ready", "present", "completed", "done"} and modules_done > 0:
            return text("operator_layer_enrichment_ready")
        if status_value in {"degraded", "failed"}:
            return text(f"operator_layer_enrichment_{status_value}")
        return text("operator_layer_enrichment_absent")
    if layer_name == "report":
        if status_value in {"ready", "present", "completed", "done"}:
            return text("operator_layer_report_ready")
        return text("operator_layer_report_absent")
    return text(f"operator_layer_status_{status_value}") if status_value in {"ready", "absent", "degraded", "failed"} else text("unknown")


def _operator_layer_label(text: Callable[..., str], layer_name: str) -> str:
    key_by_layer = {
        "factual": "operator_layer_name_factual",
        "runtime": "operator_layer_name_runtime",
        "enrichment": "operator_layer_name_enrichment",
        "report": "operator_layer_name_report",
    }
    return text(key_by_layer[layer_name]) if layer_name in key_by_layer else layer_name


def _operator_limit_label(text: Callable[..., str], code: object) -> str:
    normalized = str(code or "").strip().lower()
    mapping = {
        "runtime_absent": "operator_limit_runtime_absent",
        "enrichment_absent": "operator_limit_enrichment_absent",
        "enrichment_degraded": "operator_limit_enrichment_degraded",
        "provider_unconfigured": "operator_limit_provider_unconfigured",
    }
    key = mapping.get(normalized)
    return text(key) if key else str(code)


def _operator_limit_labels(text: Callable[..., str], codes: list[str]) -> str:
    return ", ".join(_operator_limit_label(text, code) for code in codes) if codes else text("none")


def _operator_next_step_label(text: Callable[..., str], step: object) -> str:
    value = str(step or "").strip()
    lower = value.lower()
    if lower.startswith("run a real runtime") or "runtime instrumentation" in lower:
        return text("operator_next_collect_runtime")
    if lower.startswith("run enrichment") or lower.startswith("run extra analysis"):
        return text("operator_next_run_enrichment")
    return value or text("unknown")


def _operator_provider_label(text: Callable[..., str], configured: bool) -> str:
    return text("operator_provider_configured") if configured else text("operator_provider_not_configured")


def _operator_artifacts_label(text: Callable[..., str], status: object) -> str:
    status_value = str(status or "").lower()
    if status_value in {"present", "ready", "done"}:
        return text("operator_artifacts_present")
    if status_value in {"absent", "missing", "skipped", ""}:
        return text("operator_artifacts_absent")
    return text("operator_artifacts_limited") if status_value == "degraded" else str(status)


def _operator_probe_label(text: Callable[..., str], status: object) -> str:
    status_value = str(status or "").lower()
    if status_value in {"ok", "ready", "success"}:
        return text("operator_probe_ok")
    if status_value in {"failed", "error"}:
        return text("operator_probe_failed")
    if status_value in {"not_checked", "unknown", ""}:
        return text("operator_probe_not_checked")
    return str(status)


def render_operator_health_cards(text: Callable[..., str], state: OperatorState | None) -> str:
    if state is None:
        return text("operator_health_unavailable")
    cards: list[str] = [text("operator_health_title")]
    for layer in state.layers:
        status_label = _operator_status_label(text, layer.name, layer.status, layer.details)
        if layer.name == "factual":
            detail = text(
                "operator_health_detail_factual",
                modules_scanned=layer.details.get("modules_scanned", 0),
                scan_errors=layer.details.get("scan_errors", 0),
            )
        elif layer.name == "runtime":
            detail = text("operator_health_detail_runtime", runtime_event_count=layer.details.get("runtime_event_count", 0))
        elif layer.name == "enrichment":
            detail = text(
                "operator_health_detail_enrichment",
                provider=_operator_provider_label(text, bool(layer.details.get("provider_configured"))),
                modules_done=layer.details.get("modules_done", 0),
                degraded_count=layer.details.get("degraded_count", 0),
            )
        elif layer.name == "report":
            detail = text("operator_health_detail_report", report_ref=layer.details.get("report_version") or layer.details.get("report_path") or text("unknown"))
        else:
            detail = _layer_detail(layer.details, *sorted(layer.details))
        cards.append(text("operator_health_card", layer=_operator_layer_label(text, layer.name), status=status_label, detail=detail))
    if state.warnings:
        warnings = ", ".join(_operator_limit_label(text, warning) for warning in state.warnings[:4])
        cards.append(text("operator_health_warnings", count=len(state.warnings), warnings=warnings))
    else:
        cards.append(text("operator_health_no_warnings"))
    return "\n".join(cards)


def render_operator_module_table(
    text: Callable[..., str],
    state: OperatorState | None,
    *,
    selected_module_path: str | None = None,
    limit: int = 30,
    search: str = "",
    status_filter: str = "all",
    degraded_only: bool = False,
) -> str:
    if state is None:
        return text("operator_module_table_unavailable")
    header = text("operator_module_table_header")
    lines = [header]
    table_rows = build_operator_module_table_rows(
        state,
        selected_module_path=selected_module_path,
        limit=limit,
        search=search,
        status_filter=status_filter,
        degraded_only=degraded_only,
    )
    for module in table_rows:
        lines.append(
            text(
                "operator_module_table_row",
                marker=module.marker,
                module_path=module.module_path,
                state=text(f"operator_module_state_{module.state_kind}"),
                limits=_truncate(text(f"operator_module_limits_{module.limits_kind}"), 25),
                findings=module.findings_count,
                action=_truncate(text(f"operator_module_action_{module.next_action_kind}"), 28),
            )
        )
    filtered_total = len(filter_operator_modules(state, search=search, status_filter=status_filter, degraded_only=degraded_only))
    hidden = max(0, filtered_total - limit)
    if hidden:
        lines.append(text("operator_module_table_more", hidden_count=hidden))
    if not table_rows:
        lines.append(text("operator_module_table_empty"))
    return "\n".join(lines)


def render_operator_inspector(
    text: Callable[..., str],
    state: OperatorState | None,
    selected_module_path: str | None,
) -> str:
    if state is None:
        return text("operator_inspector_unavailable")
    if not selected_module_path:
        next_step = state.next_safe_steps[0] if state.next_safe_steps else text("none")
        return "\n".join([
            text("operator_inspector_title"),
            text("operator_inspector_no_selection"),
            text("operator_dashboard_next_step", next_step=next_step),
        ])
    module = next((item for item in state.modules if item.module_path == selected_module_path), None)
    if module is None:
        return "\n".join([
            text("operator_inspector_title"),
            text("operator_inspector_missing_module", module_path=selected_module_path),
        ])
    return "\n".join([
        text("operator_inspector_title"),
        text("operator_inspector_module", module_path=module.module_path),
        text("operator_inspector_source", file_path=_compact_path(module.file_path)),
        text("operator_inspector_signals", signals=_format_signal_counts(module)),
        text(
            "operator_inspector_enrichment",
            analysis_state=text("operator_layer_enrichment_ready") if module.enriched else text("operator_layer_enrichment_absent"),
            limit_state=text("operator_module_state_warning") if module.degraded else text("operator_module_limits_none"),
            findings=module.findings_count,
        ),
    ])


def render_action_log(
    text: Callable[..., str],
    action_feedback: dict[str, str],
    *,
    running_actions: set[str] | None = None,
    action_history: list[OperatorActionHistoryEntry] | tuple[OperatorActionHistoryEntry, ...] | None = None,
    history_limit: int = 8,
) -> str:
    running_actions = running_actions or set()
    lines = [text("operator_action_log_title")]
    if action_history:
        lines.append(text("operator_action_log_recent_title"))
        for entry in list(action_history)[-history_limit:][::-1]:
            state = text("action_running") if entry.action_key in running_actions else entry.state
            lines.append(
                text(
                    "operator_action_log_history_line",
                    timestamp=entry.timestamp,
                    action=entry.label or entry.action_key,
                    state=state,
                    message=entry.message,
                )
            )
    else:
        if not action_feedback:
            lines.append(text("operator_action_log_empty"))
        for action_key in sorted(action_feedback):
            state = action_feedback[action_key]
            if action_key in running_actions:
                state = text("action_running")
            lines.append(text("operator_action_log_line", action=action_key, state=state))
    lines.append(text("operator_action_log_hotkeys"))
    return "\n".join(lines)

def render_operator_dashboard(text: Callable[..., str], state: OperatorState | None) -> str:
    if state is None:
        return text("operator_dashboard_unavailable")
    layer_by_name = {layer.name: layer for layer in state.layers}
    artifacts_total = len(state.artifacts)
    artifacts_missing = sum(1 for artifact in state.artifacts if not artifact.exists)
    artifacts_stale = sum(1 for artifact in state.artifacts if artifact.freshness and artifact.freshness.status == "stale")
    module_count = len(state.modules)
    enriched_count = sum(1 for module in state.modules if module.enriched)
    degraded_count = sum(1 for module in state.modules if module.degraded)
    route_count = sum(module.route_count for module in state.modules)
    env_count = sum(module.env_var_count for module in state.modules)
    next_step = state.next_safe_steps[0] if state.next_safe_steps else text("none")
    warnings = ", ".join(_operator_limit_label(text, warning) for warning in state.warnings[:5]) if state.warnings else text("none")
    lines = [
        text(
            "operator_dashboard_header",
            project_name=state.run.project_name,
            run_status=text("operator_project_status_limited") if state.warnings else text("operator_project_status_ready"),
            run_mode=state.run.mode,
            run_id=state.run.run_id,
        ),
        text(
            "operator_dashboard_layers",
            factual=_operator_status_label(text, "factual", layer_by_name.get("factual").status, layer_by_name.get("factual").details)
            if layer_by_name.get("factual")
            else text("unknown"),
            runtime=_operator_status_label(text, "runtime", layer_by_name.get("runtime").status, layer_by_name.get("runtime").details)
            if layer_by_name.get("runtime")
            else text("unknown"),
            enrichment=_operator_status_label(text, "enrichment", layer_by_name.get("enrichment").status, layer_by_name.get("enrichment").details)
            if layer_by_name.get("enrichment")
            else text("unknown"),
            report=_operator_status_label(text, "report", layer_by_name.get("report").status, layer_by_name.get("report").details)
            if layer_by_name.get("report")
            else text("unknown"),
        ),
        text(
            "operator_dashboard_modules",
            module_count=module_count,
            enriched_count=enriched_count,
            degraded_count=degraded_count,
            route_count=route_count,
            env_count=env_count,
        ),
        text(
            "operator_dashboard_artifacts",
            artifacts_total=artifacts_total,
            artifacts_missing=artifacts_missing,
            artifacts_stale=artifacts_stale,
        ),
        text("operator_dashboard_warnings", warnings=warnings),
        text("operator_dashboard_next_step", next_step=_operator_next_step_label(text, next_step)),
    ]
    return "\n".join(lines)


def render_module_rows(text: Callable[..., str], rows: list[ModuleOverviewRow], *, runtime_mode: bool = False) -> str:
    if runtime_mode:
        header = f"{'module_path':<44} {'status':<12} {'enrich':<10} {'runtime':<8} {'warn':<5} {'degr':<5}"
        lines = [header]
        for row in rows:
            lines.append(
                f"{_compact_module_path(row.module_path, 44):<44} "
                f"{_truncate(row.status, 12):<12} "
                f"{_truncate(_localized_enrichment_state(text, row.enrichment_state), 10):<10} "
                f"{str(row.runtime_count):<8} "
                f"{str(row.warnings_count):<5} "
                f"{_truncate(text('bool_true') if row.degraded else text('bool_false'), 5):<5}"
            )
        return "\n".join(lines)

    header = f"{'module_path':<44} {'status':<12} {'enrich':<10} {'degr':<5} {'warn':<5} {'runtime':<7} purpose"
    lines = [header]
    for row in rows:
        purpose = _truncate(row.purpose or "-", 36)
        lines.append(
            f"{_compact_module_path(row.module_path, 44):<44} "
            f"{_truncate(row.status, 12):<12} "
            f"{_truncate(_localized_enrichment_state(text, row.enrichment_state), 10):<10} "
            f"{_truncate(text('bool_true') if row.degraded else text('bool_false'), 5):<5} "
            f"{str(row.warnings_count):<5} "
            f"{_truncate(text('bool_true') if row.runtime_signal else text('bool_false'), 7):<7} "
            f"{purpose}"
        )
    return "\n".join(lines)


def render_module_summary(
    text: Callable[..., str],
    module: ModuleFact | None,
    analysis: LLMModuleAnalysis | None,
    enrichment_state: str,
) -> str:
    if module is None:
        return text("no_module_selected")
    lines = [
        text("module_path", module_path=module.module_path),
        text("source_path", file_path=_compact_path(module.file_path)),
    ]
    if analysis is None:
        lines.append(text("enrichment_state", state=_localized_enrichment_state(text, enrichment_state)))
        lines.append(text("semantic_unavailable"))
        return "\n".join(lines)
    language = _infer_language(text)
    lines.extend(
        [
            text(
                "purpose",
                purpose=localize_semantic_text(
                    language,
                    analysis.purpose or "-",
                    code=analysis.purpose_code,
                    kind="purpose",
                ),
            ),
            text("status", status=_localized_status(text, analysis.status)),
            text("enrichment_state", state=_localized_enrichment_state(text, enrichment_state)),
            text("degraded", degraded=text("bool_true") if analysis.degraded else text("bool_false")),
        ]
    )
    return "\n".join(lines)


def render_list_block(
    text: Callable[..., str],
    title: str,
    items: list[str],
    *,
    codes: list[str] | None = None,
    kind: str | None = None,
) -> str:
    localized_title = text(title)
    if not items:
        return text("none_list", title=localized_title)
    language = _infer_language(text)
    localized_items = localize_semantic_list(language, items, codes=codes, kind=kind)
    return f"{localized_title}:\n" + "\n".join(f"- {item}" for item in localized_items)

def render_compact_detail_block(
    text: Callable[..., str],
    analysis: LLMModuleAnalysis | None,
) -> str:
    section_specs = [
        ("warnings", None, "warning"),
        ("actionable_hints", None, "actionable_hint"),
        ("processing_notes", None, "processing_note"),
        ("responsibilities", None, "responsibility"),
        ("public_symbols", None, None),
    ]
    if analysis is None:
        return "\n".join(
            [
                text("detail_unavailable"),
                text("empty_sections", sections=", ".join(text(title) for title, _, _ in section_specs)),
            ]
        )
    sections = [
        ("warnings", analysis.warnings, analysis.warning_codes, "warning"),
        ("actionable_hints", analysis.actionable_hints, analysis.actionable_hint_codes, "actionable_hint"),
        ("processing_notes", analysis.processing_notes, analysis.processing_note_codes, "processing_note"),
        ("responsibilities", analysis.responsibilities, analysis.responsibility_codes, "responsibility"),
        ("public_symbols", analysis.public_symbols, None, None),
    ]
    lines: list[str] = []
    empty_titles: list[str] = []
    for title, items, codes, kind in sections:
        if items:
            lines.append(render_list_block(text, title, items, codes=codes, kind=kind))
        else:
            empty_titles.append(text(title))
    if empty_titles:
        lines.append(text("empty_sections", sections=", ".join(empty_titles)))
    return "\n\n".join(lines)


def render_artifact_block(
    text: Callable[..., str],
    module: ModuleFact | None,
    artifact: ModuleAnalysisArtifact | None,
    project_scan: ProjectScanSummary | None = None,
) -> str:
    lines: list[str] = []
    if module is not None:
        lines.append(text("source", file_path=_compact_path(module.file_path)))
    if artifact and artifact.detail_ref:
        scan_updated_at = project_scan.scanned_at if project_scan else None
        lines.extend(_render_ref_block(text, artifact.detail_ref, detail=True, scan_updated_at=scan_updated_at))
        if artifact.related_refs:
            lines.append(text("related_artifacts"))
            for related_ref in artifact.related_refs:
                lines.append(
                    text(
                        "artifact_meta",
                        source_kind=_localized_source_kind(text, related_ref.source_kind),
                        variant=_localized_variant(text, related_ref.variant),
                        updated_at=_localized_updated_at(text, related_ref.updated_at or "unknown"),
                    )
                )
                lines.append(_artifact_freshness_line(text, related_ref.updated_at, scan_updated_at, related_ref.exists))
                lines.extend(
                    _artifact_evidence_reason_lines(
                        text,
                        related_ref.updated_at,
                        scan_updated_at,
                        related_ref.exists,
                    )
                )
                lines.append(text("artifact", artifact_path=related_ref.path.name))
    else:
        lines.append(text("artifact_unavailable"))
    return "\n".join(lines)


def _render_ref_block(
    text: Callable[..., str],
    ref: ArtifactReference,
    *,
    detail: bool,
    scan_updated_at: str | None = None,
) -> list[str]:
    updated_at = ref.updated_at or "unknown"
    lines = []
    if detail:
        lines.append(
            " | ".join(
                [
                    text("detail_source", source_kind=_localized_source_kind(text, ref.source_kind)),
                    text("detail_variant", variant=_localized_variant(text, ref.variant)),
                    text("detail_updated_at", updated_at=_localized_updated_at(text, updated_at)),
                ]
            )
        )
    else:
        lines.append(
            text(
                "artifact_meta",
                source_kind=_localized_source_kind(text, ref.source_kind),
                variant=_localized_variant(text, ref.variant),
                updated_at=_localized_updated_at(text, updated_at),
            )
        )
    lines.append(text("artifact", artifact_path=ref.path.name))
    lines.append(_artifact_freshness_line(text, ref.updated_at, scan_updated_at, ref.exists))
    lines.extend(_artifact_evidence_reason_lines(text, ref.updated_at, scan_updated_at, ref.exists))
    if not ref.exists:
        lines.append(text("artifact_exists", artifact_exists=ref.exists))
    return lines


def _artifact_freshness_line(
    text: Callable[..., str],
    artifact_updated_at: str | None,
    scan_updated_at: str | None,
    artifact_exists: bool,
) -> str:
    freshness = evaluate_artifact_freshness(
        artifact_updated_at,
        scan_updated_at,
        artifact_exists=artifact_exists,
    )
    return text(
        "artifact_freshness",
        state=_localized_artifact_freshness(text, freshness.freshness_state),
        scan_updated_at=_localized_updated_at(text, scan_updated_at or "unknown"),
    )


def _artifact_evidence_reason_lines(
    text: Callable[..., str],
    artifact_updated_at: str | None,
    scan_updated_at: str | None,
    artifact_exists: bool,
) -> list[str]:
    freshness = evaluate_artifact_freshness(
        artifact_updated_at,
        scan_updated_at,
        artifact_exists=artifact_exists,
    )
    return [
        text("evidence_reason", reason=_localized_evidence_reason(text, freshness.reason_code)),
        text("operator_hint", hint=_localized_operator_hint(text, freshness.reason_code)),
    ]


def _artifact_freshness_state(
    artifact_updated_at: str | None,
    scan_updated_at: str | None,
    artifact_exists: bool,
) -> str:
    return evaluate_artifact_freshness(
        artifact_updated_at,
        scan_updated_at,
        artifact_exists=artifact_exists,
    ).freshness_state


def _localized_status(text: Callable[..., str], status: str | None) -> str:
    key = f"status_value_{status or 'no-analysis'}"
    try:
        return text(key)
    except KeyError:
        return status or text("status_value_no-analysis")


def _localized_source_kind(text: Callable[..., str], source_kind: str) -> str:
    key = f"source_kind_{source_kind}"
    try:
        return text(key)
    except KeyError:
        return source_kind


def _localized_variant(text: Callable[..., str], variant: str) -> str:
    key = f"variant_{variant}"
    try:
        return text(key)
    except KeyError:
        return variant


def _localized_updated_at(text: Callable[..., str], updated_at: str) -> str:
    if updated_at == "unknown":
        return text("unknown")
    return updated_at


def _localized_artifact_freshness(text: Callable[..., str], state: str) -> str:
    key = f"artifact_freshness_value_{state}"
    try:
        return text(key)
    except KeyError:
        return state


def _localized_evidence_reason(text: Callable[..., str], reason_code: str) -> str:
    key = f"evidence_reason_value_{reason_code}"
    try:
        return text(key)
    except KeyError:
        return reason_code


def _localized_operator_hint(text: Callable[..., str], reason_code: str) -> str:
    key = f"operator_hint_value_{reason_code}"
    try:
        return text(key)
    except KeyError:
        return reason_code


def _localized_enrichment_state(text: Callable[..., str], state: str) -> str:
    key = f"enrichment_state_value_{state}"
    try:
        return text(key)
    except KeyError:
        return state


def _localized_scan_status(text: Callable[..., str], status: str | None) -> str:
    key = f"scan_status_value_{status or 'pending'}"
    try:
        return text(key)
    except KeyError:
        return status or text("scan_status_value_pending")


def _localized_enrichment_queue_status(text: Callable[..., str], status: str | None) -> str:
    key = f"enrichment_queue_status_value_{status or 'pending'}"
    try:
        return text(key)
    except KeyError:
        return status or text("enrichment_queue_status_value_pending")


def _infer_language(text: Callable[..., str]) -> str:
    return "ru" if text("bool_false") == "нет" else "en"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1] + "…"


def render_replay_status(
    text: Callable[..., str],
    analyzer_status: AnalyzerStatus | None,
    project_scan: ProjectScanSummary | None,
    last_live_pass: LivePassSummary | None,
    schema_ready: bool,
    runtime_merged: bool,
    module_rows: list[ModuleOverviewRow],
    *,
    action_hint: str,
) -> str:
    if analyzer_status is None:
        return text("storage_unavailable")
    enrichment_pending = sum(1 for row in module_rows if row.enrichment_state == "pending")
    enrichment_done = sum(1 for row in module_rows if row.enrichment_state == "done")
    enrichment_degraded = sum(1 for row in module_rows if row.enrichment_state == "degraded")
    provider_configured = analyzer_status.configured
    operator_next = text(
        operator_next_step(
            project_scan=project_scan,
            provider_configured=provider_configured,
            enrichment_pending=enrichment_pending,
            enrichment_done=enrichment_done,
            enrichment_degraded=enrichment_degraded,
            last_live_pass=last_live_pass,
        ).text_key
    )
    lines = [
        text("operator_next", step=operator_next),
        text(
            "replay_status",
            app_name=analyzer_status.app_name,
            build_marker=analyzer_status.build_marker,
            default_model=analyzer_status.default_model,
            fallback_model=analyzer_status.fallback_model,
            schema_ready=text("bool_true") if schema_ready else text("bool_false"),
            runtime_merged=text("bool_true") if runtime_merged else text("bool_false"),
            module_count=len(module_rows),
            runtime_count=sum(1 for row in module_rows if row.runtime_signal),
            scan_status=_localized_scan_status(text, project_scan.factual_status if project_scan else None),
            provider_actions=(
                text("provider_actions_enabled")
                if provider_configured
                else text("provider_actions_disabled")
            ),
            enrichment_status=_localized_enrichment_queue_status(
                text,
                last_live_pass.enrichment_status if last_live_pass else None,
            ),
            enrichment_pending=enrichment_pending,
            enrichment_done=enrichment_done,
            enrichment_degraded=enrichment_degraded,
            enrichment_failed=last_live_pass.modules_failed if last_live_pass else 0,
        ),
        text(
            "scan_status",
            status=_localized_scan_status(text, project_scan.factual_status if project_scan else None),
            modules_scanned=project_scan.modules_scanned if project_scan else 0,
            scan_errors=project_scan.scan_errors if project_scan else 0,
            runtime_event_count=project_scan.runtime_event_count if project_scan else 0,
            scanned_at=_localized_updated_at(text, project_scan.scanned_at or "unknown") if project_scan else text("unknown"),
        ),
        text(
            "provider_actions_status",
            state=text("provider_actions_enabled") if provider_configured else text("provider_actions_disabled"),
        ),
        text(
            "provider_action_reason",
            reason=text("provider_action_reason_configured")
            if provider_configured
            else text("provider_action_reason_not_configured"),
        ),
        text(
            "provider_action_hint",
            hint=text("provider_action_hint_configured")
            if provider_configured
            else text("provider_action_hint_not_configured"),
        ),
        action_hint,
    ]
    return "\n".join(lines)


def _operator_next_step(
    text: Callable[..., str],
    *,
    project_scan: ProjectScanSummary | None,
    provider_configured: bool,
    enrichment_pending: int,
    enrichment_done: int,
    enrichment_degraded: int,
    last_live_pass: LivePassSummary | None,
) -> str:
    if project_scan is None:
        return text("operator_next_scan_first")
    if not provider_configured and enrichment_done == 0:
        return text("operator_next_configure_provider")
    if provider_configured and enrichment_pending > 0:
        return text("operator_next_run_enrichment_queue")
    if enrichment_done > 0 or enrichment_degraded > 0 or last_live_pass is not None:
        return text("operator_next_review_enrichment")
    return text("operator_next_review_scan")


def render_storage_block(
    text: Callable[..., str],
    analyzer_status: AnalyzerStatus | None,
) -> str:
    if analyzer_status is None:
        return text("storage_unavailable")
    storage_lines = [text("storage_line", name=name, path=path) for name, path in analyzer_status.storage_layout.items()]
    if not storage_lines:
        return text("storage_unavailable")
    return "\n".join(storage_lines)


def _report_mapping(report: dict[str, object] | None, key: str) -> dict[str, object]:
    value = report.get(key) if report else None
    return value if isinstance(value, dict) else {}


def _report_list(report: dict[str, object] | None, key: str) -> list[object]:
    value = report.get(key) if report else None
    return value if isinstance(value, list) else []


def render_project_report_block(
    text: Callable[..., str],
    report: dict[str, object] | None,
) -> str:
    if not report:
        return text("project_report_unavailable")
    scope = _report_mapping(report, "scope")
    factual = _report_mapping(report, "factual_layer")
    runtime = _report_mapping(report, "runtime_layer")
    enrichment = _report_mapping(report, "enrichment_layer")
    limits = _report_list(report, "limits")
    next_steps = _report_list(report, "next_safe_steps")
    findings = _report_list(report, "module_findings")

    limit_codes = [
        str(item.get("code"))
        for item in limits
        if isinstance(item, dict) and item.get("code")
    ]
    step_lines = [f"- {item}" for item in next_steps[:3] if item]
    if not step_lines:
        step_lines = [f"- {text('unknown')}"]
    finding_lines: list[str] = []
    for item in findings[:3]:
        if not isinstance(item, dict):
            continue
        provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
        finding_lines.append(
            text(
                "project_report_finding_line",
                module_path=_truncate(str(item.get("module_path") or text("unknown")), 54),
                status=item.get("status") or text("unknown"),
                degraded=text("bool_true") if item.get("degraded") else text("bool_false"),
                warnings_count=len(item.get("warnings") or []),
                source=provenance.get("doc_key") or text("unknown"),
            )
        )
    if not finding_lines:
        finding_lines = [f"- {text('none')}"]

    provider_credentials = bool(enrichment.get("provider_credentials_configured", enrichment.get("provider_configured")))
    artifacts_status = str(enrichment.get("artifacts_status") or enrichment.get("status") or text("unknown"))
    return text(
        "project_report_block",
        project_name=scope.get("project_name") or text("unknown"),
        source_root=_compact_path(str(scope.get("source_root") or text("unknown"))),
        modules_scanned=factual.get("modules_scanned", 0),
        scan_errors=factual.get("scan_errors", 0),
        function_count=factual.get("function_count", 0),
        class_count=factual.get("class_count", 0),
        symbol_count=factual.get("symbol_count", 0),
        import_edge_count=factual.get("import_edge_count", 0),
        runtime_status=_operator_status_label(text, "runtime", runtime.get("status"), {"runtime_event_count": runtime.get("runtime_event_count", 0)}),
        runtime_event_count=runtime.get("runtime_event_count", 0),
        enrichment_status=_operator_status_label(text, "enrichment", enrichment.get("status"), {"modules_done": enrichment.get("modules_done", 0)}),
        enrichment_artifacts=_operator_artifacts_label(text, artifacts_status),
        provider_configured=_operator_provider_label(text, provider_credentials),
        provider_probe=_operator_probe_label(text, enrichment.get("provider_probe_status")),
        modules_done=enrichment.get("modules_done", 0),
        modules_degraded=enrichment.get("modules_degraded", 0),
        modules_failed=enrichment.get("modules_failed", 0),
        module_findings_total=report.get("module_findings_total", 0),
        module_findings_preview="\n".join(finding_lines),
        limits=_operator_limit_labels(text, limit_codes),
        next_safe_steps="\n".join(_operator_next_step_label(text, step) for step in next_steps[:3]) if next_steps else "\n".join(step_lines),
        llm_truth=text("bool_true")
        if _report_mapping(report, "provenance").get("llm_is_truth_source")
        else text("bool_false"),
    )


def render_project_report_summary_block(
    text: Callable[..., str],
    report: dict[str, object] | None,
) -> str:
    if not report:
        return text("project_report_unavailable")
    scope = _report_mapping(report, "scope")
    factual = _report_mapping(report, "factual_layer")
    runtime = _report_mapping(report, "runtime_layer")
    enrichment = _report_mapping(report, "enrichment_layer")
    limits = _report_list(report, "limits")
    next_steps = _report_list(report, "next_safe_steps")
    limit_codes = [
        str(item.get("code"))
        for item in limits
        if isinstance(item, dict) and item.get("code")
    ]
    provider_credentials = bool(enrichment.get("provider_credentials_configured", enrichment.get("provider_configured")))
    artifacts_status = str(enrichment.get("artifacts_status") or enrichment.get("status") or text("unknown"))
    return text(
        "project_report_summary_block",
        project_name=scope.get("project_name") or text("unknown"),
        source_root=_compact_path(str(scope.get("source_root") or text("unknown")), max_len=64),
        modules_scanned=factual.get("modules_scanned", 0),
        scan_errors=factual.get("scan_errors", 0),
        symbol_count=factual.get("symbol_count", 0),
        import_edge_count=factual.get("import_edge_count", 0),
        runtime_status=_operator_status_label(text, "runtime", runtime.get("status"), {"runtime_event_count": runtime.get("runtime_event_count", 0)}),
        runtime_event_count=runtime.get("runtime_event_count", 0),
        enrichment_status=_operator_status_label(text, "enrichment", enrichment.get("status"), {"modules_done": enrichment.get("modules_done", 0)}),
        enrichment_artifacts=_operator_artifacts_label(text, artifacts_status),
        provider_configured=_operator_provider_label(text, provider_credentials),
        provider_probe=_operator_probe_label(text, enrichment.get("provider_probe_status")),
        limits=_operator_limit_labels(text, limit_codes),
        next_safe_step=_operator_next_step_label(text, next_steps[0]) if next_steps else text("unknown"),
    )


def render_project_findings_block(
    text: Callable[..., str],
    findings: list[dict[str, object]],
    *,
    total_count: int = 0,
    max_items: int = 12,
) -> str:
    visible_total = len(findings)
    if not findings:
        return text(
            "project_findings_block",
            visible_total=0,
            total_count=total_count,
            findings=f"- {text('none')}",
        )
    lines: list[str] = []
    for item in findings[:max_items]:
        provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
        warnings = item.get("warnings") if isinstance(item.get("warnings"), list) else []
        hints = item.get("actionable_hints") if isinstance(item.get("actionable_hints"), list) else []
        purpose = str(item.get("purpose") or text("unknown"))
        warning_preview = "; ".join(str(warning) for warning in warnings[:2]) or text("none")
        hint_preview = "; ".join(str(hint) for hint in hints[:2]) or text("none")
        lines.append(
            text(
                "project_findings_detail_line",
                module_path=_truncate(str(item.get("module_path") or text("unknown")), 72),
                status=item.get("status") or text("unknown"),
                degraded=text("bool_true") if item.get("degraded") else text("bool_false"),
                purpose=_truncate(purpose, 96),
                warnings_count=len(warnings),
                warning_preview=_truncate(warning_preview, 120),
                hint_preview=_truncate(hint_preview, 120),
                source=provenance.get("doc_key") or text("unknown"),
                trust_layer=provenance.get("trust_layer") or text("unknown"),
            )
        )
    if visible_total > max_items:
        lines.append(text("project_findings_more", remaining=visible_total - max_items))
    return text(
        "project_findings_block",
        visible_total=visible_total,
        total_count=total_count,
        findings="\n".join(lines),
    )


def render_live_pass_block(
    text: Callable[..., str],
    last_live_pass: LivePassSummary | None,
) -> str:
    if not last_live_pass:
        return text("live_pass_unavailable")
    last_pass_lines = [
        text(
            "replay_summary",
            summary_path=last_live_pass.summary_path,
            status_path=last_live_pass.status_path,
            queue_status=_localized_enrichment_queue_status(text, last_live_pass.enrichment_status),
            provider_configured=text("bool_true")
            if last_live_pass.provider_configured
            else text("bool_false"),
            modules_requested=last_live_pass.modules_requested,
            modules_done=last_live_pass.modules_done,
            modules_degraded=last_live_pass.modules_degraded,
            modules_failed=last_live_pass.modules_failed,
            output_dir=last_live_pass.output_dir,
        )
    ]
    last_pass_lines.extend(text("artifact_line", path=path) for path in last_live_pass.artifact_paths)
    return "\n".join(last_pass_lines)


def render_project_scan_block(
    text: Callable[..., str],
    project_scan: ProjectScanSummary | None,
) -> str:
    if not project_scan or project_scan.summary_path is None:
        return text("project_scan_unavailable")
    return text(
        "project_scan_summary",
        summary_path=project_scan.summary_path,
        status=_localized_scan_status(text, project_scan.factual_status),
        source_root=project_scan.source_root or text("unknown"),
        modules_scanned=project_scan.modules_scanned,
        scan_errors=project_scan.scan_errors,
        runtime_event_count=project_scan.runtime_event_count,
        scanned_at=_localized_updated_at(text, project_scan.scanned_at or "unknown"),
        output_dir=project_scan.output_dir or text("unknown"),
    )


def render_action_state_block(
    text: Callable[..., str],
    action_states: dict[str, str],
) -> str:
    order = (
        ("refresh-all", "btn_refresh_views"),
        ("reload-status", "btn_refresh_status"),
        ("scan-project", "btn_scan_project"),
        ("live-pass", "btn_live_pass"),
        ("reanalyze", "btn_reanalyze"),
    )
    lines = [text("action_states")]
    for action_key, label_key in order:
        lines.append(
            text(
                "action_state_line",
                label=text(label_key),
                state=action_states.get(action_key, text("action_idle")),
            )
        )
    return "\n".join(lines)


def render_analysis_guide(text: Callable[..., str]) -> str:
    return text("analysis_guide_body")
