from __future__ import annotations

import asyncio
from uuid import UUID

from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.q_core_agent.qiki_orion_intents_service import _build_hostile_attack_block_response
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode


def _widget_text(widget: object) -> str:
    renderable = getattr(widget, "renderable", None)
    if hasattr(renderable, "plain"):
        return str(getattr(renderable, "plain"))
    if renderable is not None:
        return str(renderable)
    content = getattr(widget, "content", None)
    if hasattr(content, "plain"):
        return str(getattr(content, "plain"))
    if content is not None:
        return str(content)
    return str(widget)


def _world_snapshot(qsim: QSimService) -> dict:
    state = qsim.world_model.get_state()
    state["radar_tracks"] = [
        {
            "object_type": 2,
            "range_m": 1800.0,
            "quality": 0.95,
            "age_s": 0.1,
            "transponder_id": "UNBT9999",
            "iff": 2,
        }
    ]
    return state


def _response_payload(qsim: QSimService, request_id: int) -> dict:
    req = QikiChatRequestV1(
        request_id=UUID(int=request_id),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot=_world_snapshot(qsim),
        agent=None,
    )
    return {"data": response.model_dump(mode="json")}


async def _no_nats(self: OrionVApp) -> None:
    self._nats_state = "lost"


async def _main() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    qsim.world_model._rcs_propellant_kg = 8.0
    qsim.world_model._max_bus_a = 3.0

    original_connect = OrionVApp._connect_and_subscribe
    OrionVApp._connect_and_subscribe = _no_nats
    try:
        app = OrionVApp()

        async def publish_local_sim_command(command_name: str, parameters: dict | None = None) -> None:
            cmd = CommandMessage(
                command_name=command_name,
                parameters=parameters or {},
                metadata=MessageMetadata(
                    message_type="control_command",
                    source="orion_v_smoke",
                    destination="q_sim_service",
                ),
            )
            assert qsim.apply_control_command(cmd) is True
            qsim.step(delta_time=0.1)
            telemetry = qsim._build_telemetry_payload(qsim.world_model.get_state())
            await app._on_telemetry({"data": telemetry})

        async def ack_ok(command_name: str, timeout_s: float, command_id=None) -> bool:
            return bool(command_name) and timeout_s > 0

        app._publish_sim_command = publish_local_sim_command  # type: ignore[method-assign]
        app._wait_for_ack = ack_ok  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            await app._on_telemetry({"data": qsim._build_telemetry_payload(qsim.world_model.get_state())})
            await pilot.pause()

            await app._on_qiki_response(_response_payload(qsim, 801))
            await pilot.pause()
            assert app._qiki_pending_action is not None

            await app._execute_qiki_pending_action()
            await pilot.pause()

            qsim.step(delta_time=2.0)
            await app._on_telemetry({"data": qsim._build_telemetry_payload(qsim.world_model.get_state())})
            await pilot.pause()

            app.action_show_level("f2")
            app.action_select_subsystem("power")
            await pilot.pause()

            await app._on_qiki_response(_response_payload(qsim, 802))
            await pilot.pause()

            response = app._qiki_last_response
            assert response is not None
            assert response.legality is not None
            assert response.legality.status == "blocked"
            assert response.legality.domain == "resource"
            assert response.legality.reason_code == "COMBAT_ENTRY_POWER_OVERCURRENT"

            systems_text = _widget_text(app.query_one("#orionv-systems", Static))
            power = (app._snapshot.get("power") or {})

            assert "pdu_overcurrent" in systems_text
            assert bool(power.get("load_shedding")) is True
            assert "pdu_overcurrent" in list(power.get("shed_reasons") or [])

            print("OK: orion_v_qiki_hostile_power_gate_smoke")
            print(f"POWER_CODE={response.legality.reason_code}")
            print(f"POWER_STATUS={response.legality.status}")
            print(f"POWER_SHED_REASONS={power.get('shed_reasons')}")
    finally:
        OrionVApp._connect_and_subscribe = original_connect


if __name__ == "__main__":
    asyncio.run(_main())
