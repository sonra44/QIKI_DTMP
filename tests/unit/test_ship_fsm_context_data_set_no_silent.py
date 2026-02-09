import logging

from qiki.services.q_core_agent.core.ship_fsm_handler import _safe_set_context_data


def test_ship_fsm_context_data_set_logs_exception(caplog) -> None:
    class BadContext:
        def __setitem__(self, key: str, value: str) -> None:
            raise RuntimeError("boom")

    caplog.set_level(logging.DEBUG, logger="q_core_agent")
    _safe_set_context_data(BadContext(), "ship_state_name", "SHIP_IDLE")
    assert any(r.message == "ship_fsm_context_data_set_failed" for r in caplog.records)

