from __future__ import annotations

from .operator_state import OperatorState

STATUS_THEME_CLASSES = (
    "status-ok",
    "status-warning",
    "status-error",
    "status-muted",
    "status-running",
)

_OK_STATUSES = {"ready", "present", "current", "done", "completed", "ok", "available"}
_WARNING_STATUSES = {
    "completed_with_limits",
    "ready_with_limits",
    "degraded",
    "partial",
    "stale",
    "future_timestamp",
    "invalid_timestamp",
    "warning",
}
_ERROR_STATUSES = {"failed", "error", "missing", "unavailable"}
_MUTED_STATUSES = {"absent", "skipped", "unknown", "not_configured", "none"}
_RUNNING_STATUSES = {"running", "pending", "in_progress", "queued"}


def normalize_status_token(status: object) -> str:
    return str(status or "unknown").strip().lower().replace("-", "_").replace(" ", "_")


def status_theme_class(status: object) -> str:
    token = normalize_status_token(status)
    if token in _OK_STATUSES:
        return "status-ok"
    if token in _WARNING_STATUSES:
        return "status-warning"
    if token in _ERROR_STATUSES:
        return "status-error"
    if token in _RUNNING_STATUSES:
        return "status-running"
    if token in _MUTED_STATUSES:
        return "status-muted"
    return "status-muted"


def operator_state_theme_class(state: OperatorState | None) -> str:
    if state is None:
        return "status-muted"
    return status_theme_class(state.run.status)


def layer_theme_class(state: OperatorState | None, layer_name: str) -> str:
    if state is None:
        return "status-muted"
    layer = next((item for item in state.layers if item.name == layer_name), None)
    if layer is None:
        return "status-muted"
    return status_theme_class(layer.status)
