from __future__ import annotations

from dataclasses import dataclass

from .operator_state import OperatorModuleRow, OperatorState

MODULE_TABLE_COLUMNS = ("marker", "module", "state", "limits", "findings", "action")


def compact_module_path(module_path: str, max_len: int = 42) -> str:
    if len(module_path) <= max_len:
        return module_path
    parts = module_path.split(".")
    if len(parts) < 3:
        return module_path[: max(0, max_len - 1)] + "…"
    tail = ".".join(parts[-3:])
    prefix = "..."
    if len(prefix) + len(tail) <= max_len:
        return prefix + tail
    return module_path[: max(0, max_len - 1)] + "…"


def format_signal_counts(module: OperatorModuleRow) -> str:
    signals = [
        ("routes", module.route_count),
        ("env", module.env_var_count),
        ("cli", module.cli_option_count),
        ("models", module.pydantic_model_count),
        ("attrs", module.class_attribute_count),
    ]
    active = [f"{name}:{count}" for name, count in signals if count]
    return " ".join(active) if active else "-"


@dataclass(frozen=True, slots=True)
class OperatorModuleTableRow:
    marker: str
    module_path: str
    signals: str
    state_kind: str
    limits_kind: str
    runtime_kind: str
    next_action_kind: str
    findings_count: int
    enriched: bool
    degraded: bool
    has_runtime: bool
    has_enrichment: bool
    sort_attention_rank: int
    raw_module_path: str
    technical: dict[str, object]

    @property
    def findings(self) -> int:
        return self.findings_count


def _layer_status(state: OperatorState, name: str) -> str:
    layer = next((item for item in state.layers if item.name == name), None)
    return str(layer.status).lower() if layer is not None else "absent"


def _layer_detail_int(state: OperatorState, name: str, key: str) -> int:
    layer = next((item for item in state.layers if item.name == name), None)
    if layer is None:
        return 0
    try:
        return int(layer.details.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def state_has_runtime(state: OperatorState) -> bool:
    status = _layer_status(state, "runtime")
    return status in {"ready", "present", "completed"} or _layer_detail_int(state, "runtime", "runtime_event_count") > 0


def resolve_module_state_kind(module: OperatorModuleRow, *, has_runtime: bool) -> str:
    if module.degraded or module.findings_count > 0:
        return "warning"
    if not has_runtime or not module.enriched:
        return "limited"
    return "ready"


def resolve_limits_kind(module: OperatorModuleRow, *, has_runtime: bool) -> str:
    if not has_runtime and not module.enriched:
        return "runtime_and_enrichment"
    if not has_runtime:
        return "runtime"
    if not module.enriched:
        return "enrichment"
    return "none"


def resolve_next_action_kind(module: OperatorModuleRow, *, has_runtime: bool) -> str:
    if not has_runtime:
        return "collect_runtime"
    if not module.enriched:
        return "run_enrichment"
    if module.degraded or module.findings_count > 0:
        return "review_findings"
    return "none"


def attention_rank(row: OperatorModuleTableRow) -> int:
    rank_by_state = {
        "error": 0,
        "warning": 1,
        "limited": 2,
        "absent": 3,
        "ready": 4,
        "unknown": 5,
    }
    return rank_by_state.get(row.state_kind, 5)


def filter_operator_modules(
    state: OperatorState,
    *,
    search: str = "",
    status_filter: str = "all",
    degraded_only: bool = False,
) -> list[OperatorModuleRow]:
    """Return module rows matching operator-facing table filters.

    This is intentionally pure and Textual-free so table behavior can be
    acceptance-tested in environments without the optional TUI dependency.
    """
    query = search.strip().lower()
    has_runtime = state_has_runtime(state)
    rows: list[OperatorModuleTableRow] = []
    for module in state.modules:
        if query and query not in module.module_path.lower() and query not in module.file_path.lower():
            continue
        row = build_operator_module_table_row(module, has_runtime=has_runtime)
        if degraded_only and not module.degraded:
            continue
        if not match_operator_module_filter(row, module, status_filter):
            continue
        rows.append(row)
    rows.sort(key=lambda row: (row.sort_attention_rank, -row.findings_count, row.raw_module_path))
    return [state_module for row in rows for state_module in state.modules if state_module.module_path == row.raw_module_path]


def match_operator_module_filter(row: OperatorModuleTableRow, module: OperatorModuleRow, status_filter: str) -> bool:
    filter_id = status_filter.strip().lower().replace("_", "-")
    if filter_id in {"all", ""}:
        return True
    if filter_id in {"attention", "needs-attention", "degraded"}:
        return row.state_kind in {"limited", "warning", "error", "absent"} or row.findings_count > 0 or row.limits_kind != "none"
    if filter_id in {"missing-enrichment", "no-analysis", "no-enrichment"}:
        return not row.has_enrichment
    if filter_id in {"no-runtime", "missing-runtime"}:
        return not row.has_runtime
    if filter_id in {"has-findings", "has-risks"}:
        return row.findings_count > 0
    if filter_id in {"warnings", "warning"}:
        return row.state_kind == "warning" or module.degraded
    if filter_id in {"ready", "ready-only"}:
        return row.state_kind == "ready"
    if filter_id in {"routes", "entrypoints"}:
        return module.route_count > 0
    if filter_id in {"env-config"}:
        return bool(module.env_var_count or module.cli_option_count or module.pydantic_model_count)
    return True


def build_operator_module_table_row(
    module: OperatorModuleRow,
    *,
    has_runtime: bool,
    selected_module_path: str | None = None,
) -> OperatorModuleTableRow:
    state_kind = resolve_module_state_kind(module, has_runtime=has_runtime)
    limits_kind = resolve_limits_kind(module, has_runtime=has_runtime)
    runtime_kind = "confirmed" if has_runtime else "absent"
    next_action_kind = resolve_next_action_kind(module, has_runtime=has_runtime)
    row = OperatorModuleTableRow(
        marker=">" if module.module_path == selected_module_path else " ",
        module_path=compact_module_path(module.module_path),
        signals=format_signal_counts(module),
        state_kind=state_kind,
        limits_kind=limits_kind,
        runtime_kind=runtime_kind,
        next_action_kind=next_action_kind,
        findings_count=module.findings_count,
        enriched=module.enriched,
        degraded=module.degraded,
        has_runtime=has_runtime,
        has_enrichment=module.enriched,
        sort_attention_rank=0,
        raw_module_path=module.module_path,
        technical={
            "source_path": module.file_path,
            "signals": format_signal_counts(module),
            "runtime_status": runtime_kind,
            "enrichment_status": "ready" if module.enriched else "absent",
            "degraded": module.degraded,
            "findings_count": module.findings_count,
        },
    )
    return OperatorModuleTableRow(
        marker=row.marker,
        module_path=row.module_path,
        signals=row.signals,
        state_kind=row.state_kind,
        limits_kind=row.limits_kind,
        runtime_kind=row.runtime_kind,
        next_action_kind=row.next_action_kind,
        findings_count=row.findings_count,
        enriched=row.enriched,
        degraded=row.degraded,
        has_runtime=row.has_runtime,
        has_enrichment=row.has_enrichment,
        sort_attention_rank=attention_rank(row),
        raw_module_path=row.raw_module_path,
        technical=row.technical,
    )


def build_operator_module_table_rows(
    state: OperatorState,
    *,
    selected_module_path: str | None = None,
    limit: int = 30,
    search: str = "",
    status_filter: str = "all",
    degraded_only: bool = False,
) -> list[OperatorModuleTableRow]:
    if limit <= 0:
        return []
    rows: list[OperatorModuleTableRow] = []
    has_runtime = state_has_runtime(state)
    for module in filter_operator_modules(
        state,
        search=search,
        status_filter=status_filter,
        degraded_only=degraded_only,
    )[:limit]:
        rows.append(
            build_operator_module_table_row(module, has_runtime=has_runtime, selected_module_path=selected_module_path)
        )
    return rows


def operator_module_table_headers(text) -> tuple[str, str, str, str, str, str]:
    """Return localized headers for the Textual DataTable-backed module table.

    The static renderer and the future Textual DataTable share this helper so
    the column contract remains testable without importing Textual.
    """
    return (
        text("operator_module_table_col_selected"),
        text("operator_module_table_col_module"),
        text("operator_module_table_col_state"),
        text("operator_module_table_col_limits"),
        text("operator_module_table_col_findings"),
        text("operator_module_table_col_action"),
    )


def operator_module_table_row_values(text, row: OperatorModuleTableRow) -> tuple[str, str, str, str, str, str]:
    """Return DataTable-ready string values for a module row."""
    return (
        row.marker,
        row.module_path,
        text(f"operator_module_state_{row.state_kind}"),
        text(f"operator_module_limits_{row.limits_kind}"),
        str(row.findings_count),
        text(f"operator_module_action_{row.next_action_kind}"),
    )
