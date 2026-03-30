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


def _arm_thermal_sensitive_pdu(qsim: QSimService) -> None:
    wm = qsim.world_model
    start = 84.94
    wm._rcs_propellant_kg = 20.0
    wm.temp_external_c = start
    wm._thermal_nodes["pdu"]["temp_c"] = start
    wm._thermal_nodes["pdu"]["cool_w_per_c"] = 0.0
    wm._thermal_couplings["pdu"] = []
    for node_id in ("core", "supercap", "battery"):
        wm._thermal_couplings[node_id] = [pair for pair in wm._thermal_couplings[node_id] if pair[0] != "pdu"]


async def _main() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    _arm_thermal_sensitive_pdu(qsim)

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

        async def ack_ok(command_name: str, timeout_s: float) -> bool:
            return bool(command_name) and timeout_s > 0

        app._publish_sim_command = publish_local_sim_command  # type: ignore[method-assign]
        app._wait_for_ack = ack_ok  # type: ignore[method-assign]

        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            await app._on_telemetry({"data": qsim._build_telemetry_payload(qsim.world_model.get_state())})
            await pilot.pause()

            await app._on_qiki_response(_response_payload(qsim, 901))
            await pilot.pause()
            assert app._qiki_pending_action is not None

            await app._execute_qiki_pending_action()
            await pilot.pause()

            qsim.step(delta_time=2.0)
            await app._on_telemetry({"data": qsim._build_telemetry_payload(qsim.world_model.get_state())})
            await pilot.pause()

            app.action_show_level("f2")
            app.action_select_subsystem("thermal")
            await pilot.pause()

            await app._on_qiki_response(_response_payload(qsim, 902))
            await pilot.pause()

            response = app._qiki_last_response
            assert response is not None
            assert response.legality is not None
            assert response.legality.status == "deferred"
            assert response.legality.domain == "resource"
            assert response.legality.reason_code == "COMBAT_ENTRY_THERMAL_WARN"

            systems_text = _widget_text(app.query_one("#orionv-systems", Static))
            thermal = app._snapshot.get("thermal") or {}
            nodes = thermal.get("nodes") or []
            pdu = next(node for node in nodes if isinstance(node, dict) and node.get("id") == "pdu")

            assert bool(pdu.get("warned")) is True
            assert "pdu" in systems_text.lower()
            assert "warn" in systems_text.lower()

            print("OK: orion_v_qiki_thermal_followup_constraint_smoke")
            print(f"THERMAL_CODE={response.legality.reason_code}")
            print(f"THERMAL_STATUS={response.legality.status}")
            print(f"PDU_WARNED={pdu.get('warned')}")
            print(f"PDU_TEMP={float(pdu.get('temp_c')):.5f}")
    finally:
        OrionVApp._connect_and_subscribe = original_connect


if __name__ == "__main__":
    asyncio.run(_main())
