from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .tui_models import LivePassSummary, ProjectScanSummary

OperatorNextStepCode = Literal[
    "scan_first",
    "configure_provider",
    "run_enrichment_queue",
    "review_enrichment",
    "review_scan",
]


@dataclass(frozen=True, slots=True)
class OperatorNextStep:
    code: OperatorNextStepCode
    text_key: str


def operator_next_step(
    *,
    project_scan: ProjectScanSummary | None,
    provider_configured: bool,
    enrichment_pending: int,
    enrichment_done: int,
    enrichment_degraded: int,
    last_live_pass: LivePassSummary | None,
) -> OperatorNextStep:
    """Return the next operator action as domain state, not rendered UI text.

    This logic is intentionally independent from Textual/rendering so the same
    decision can be reused by TUI, reports, CLI exports, and future run results.
    """
    if project_scan is None:
        return OperatorNextStep("scan_first", "operator_next_scan_first")
    if not provider_configured and enrichment_done == 0:
        return OperatorNextStep("configure_provider", "operator_next_configure_provider")
    if provider_configured and enrichment_pending > 0:
        return OperatorNextStep("run_enrichment_queue", "operator_next_run_enrichment_queue")
    if enrichment_done > 0 or enrichment_degraded > 0 or last_live_pass is not None:
        return OperatorNextStep("review_enrichment", "operator_next_review_enrichment")
    return OperatorNextStep("review_scan", "operator_next_review_scan")
