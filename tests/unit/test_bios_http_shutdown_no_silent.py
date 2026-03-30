import logging

from qiki.services.q_bios_service import main as bios_main


def test_safe_http_server_shutdown_logs_exception(caplog) -> None:
    class DummyServer:
        def shutdown(self) -> None:
            raise RuntimeError("boom")

    caplog.set_level(logging.DEBUG)
    bios_main._safe_http_server_shutdown(DummyServer())  # type: ignore[arg-type]
    assert any(r.message == "bios_http_server_shutdown_failed" for r in caplog.records)
