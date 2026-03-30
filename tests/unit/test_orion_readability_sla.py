from qiki.services.operator_console.main_orion import OrionApp


def _startup_readability_proxy_seconds(app: OrionApp) -> float:
    """Deterministic proxy for startup scan time (operator readability SLA)."""
    blocks = app._build_summary_blocks()
    rows = len(blocks)
    value_chars = sum(min(len(str(b.value)), 80) for b in blocks)

    # Heuristic model (stable for CI): rows dominate scan cost, value text is secondary.
    # The target is operational acceptance <=10s for startup understanding.
    return 1.2 + 0.70 * rows + 0.01 * value_chars


def test_orion_startup_readability_proxy_is_within_10s_sla() -> None:
    app = OrionApp()
    readability_s = _startup_readability_proxy_seconds(app)
    assert readability_s <= 10.0, f"startup readability SLA failed: {readability_s:.2f}s > 10.0s"
