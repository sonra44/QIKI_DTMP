from __future__ import annotations

from project_introspector.operator_next import operator_next_step
from project_introspector.tui_models import LivePassSummary, ProjectScanSummary


def test_operator_next_step_scans_first_without_scan() -> None:
    step = operator_next_step(
        project_scan=None,
        provider_configured=False,
        enrichment_pending=0,
        enrichment_done=0,
        enrichment_degraded=0,
        last_live_pass=None,
    )

    assert step.code == "scan_first"
    assert step.text_key == "operator_next_scan_first"


def test_operator_next_step_configures_provider_before_first_enrichment() -> None:
    step = operator_next_step(
        project_scan=ProjectScanSummary(modules_scanned=3),
        provider_configured=False,
        enrichment_pending=3,
        enrichment_done=0,
        enrichment_degraded=0,
        last_live_pass=None,
    )

    assert step.code == "configure_provider"


def test_operator_next_step_runs_enrichment_queue_when_provider_ready() -> None:
    step = operator_next_step(
        project_scan=ProjectScanSummary(modules_scanned=3),
        provider_configured=True,
        enrichment_pending=2,
        enrichment_done=0,
        enrichment_degraded=0,
        last_live_pass=None,
    )

    assert step.code == "run_enrichment_queue"


def test_operator_next_step_reviews_existing_enrichment() -> None:
    step = operator_next_step(
        project_scan=ProjectScanSummary(modules_scanned=3),
        provider_configured=True,
        enrichment_pending=0,
        enrichment_done=1,
        enrichment_degraded=0,
        last_live_pass=LivePassSummary(modules_done=1),
    )

    assert step.code == "review_enrichment"


def test_operator_next_step_reviews_scan_when_no_enrichment_signal() -> None:
    step = operator_next_step(
        project_scan=ProjectScanSummary(modules_scanned=3),
        provider_configured=True,
        enrichment_pending=0,
        enrichment_done=0,
        enrichment_degraded=0,
        last_live_pass=None,
    )

    assert step.code == "review_scan"
