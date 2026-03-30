import pytest


@pytest.mark.asyncio
async def test_orion_bios_first_load_message_uses_post_results_count() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    calm_logs: list[str] = []
    console_logs: list[str] = []

    def _calm_log(msg: str, *, level: str = "info") -> None:
        calm_logs.append(f"{level}:{msg}")

    def _log_msg(msg: str, style: str | None = None) -> None:
        if style is None:
            console_logs.append(msg)
        else:
            console_logs.append(f"{style}:{msg}")

    app._calm_log = _calm_log  # type: ignore[method-assign]
    app._log_msg = _log_msg  # type: ignore[method-assign]

    await app.handle_event_data(
        {
            "subject": "qiki.events.v1.bios_status",
            "data": {
                "all_systems_go": True,
                "post_results": [
                    {"device_id": "imu_main", "status": 1},
                    {"device_id": "radar_360", "status": 1},
                    {"device_id": "mainboard", "status": 1},
                ],
                "event_schema_version": 1,
                "source": "q-bios-service",
                "subject": "qiki.events.v1.bios_status",
            },
        }
    )

    assert app._bios_loaded_announced is True
    assert any("BIOS loaded" in line for line in calm_logs)
    assert any("devices: 3" in line or "устройств: 3" in line for line in calm_logs)
    assert not any("components" in line or "компоненты" in line for line in calm_logs)
    assert any("devices: 3" in line or "устройств: 3" in line for line in console_logs)
