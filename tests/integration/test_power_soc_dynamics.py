import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel


@pytest.mark.integration
@pytest.mark.asyncio
async def test_power_soc_decreases_while_running_and_freezes_when_paused_and_stopped() -> None:
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    telemetry_latest: dict | None = None

    async def on_telemetry(msg) -> None:
        nonlocal telemetry_latest
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            telemetry_latest = TelemetrySnapshotModel.normalize_payload(payload)
        except Exception:
            return

    await nc.subscribe("qiki.telemetry", cb=on_telemetry)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    async def publish(cmd: CommandMessage) -> None:
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush(timeout=1)

    async def wait_for(predicate, *, timeout_s: float = 6.0) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if telemetry_latest is not None and predicate(telemetry_latest):
                return telemetry_latest
            await asyncio.sleep(0.05)
        raise AssertionError("Timeout waiting for telemetry condition")

    def get_soc(t: dict) -> float:
        power = t.get("power") or {}
        return float((power if isinstance(power, dict) else {}).get("soc_pct", 0.0))

    async def sample_soc_over(duration_s: float) -> list[float]:
        out: list[float] = []
        deadline = asyncio.get_running_loop().time() + duration_s
        while asyncio.get_running_loop().time() < deadline:
            if telemetry_latest is not None:
                out.append(get_soc(telemetry_latest))
            await asyncio.sleep(0.1)
        return out

    try:
        await publish(CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta))
        t_run = await wait_for(lambda t: (t.get("sim_state") or {}).get("fsm_state") == "RUNNING", timeout_s=8.0)

        # Proof test: intended to run with BOT_CONFIG_PATH pointing to:
        # - /workspace/tests/fixtures/bot_config_power_soc_drain.json
        # If the stack is running in normal mode, skip to avoid false failures.
        power0 = t_run.get("power") if isinstance(t_run.get("power"), dict) else {}
        thermal0 = t_run.get("thermal") if isinstance(t_run.get("thermal"), dict) else {}
        thermal_nodes0 = thermal0.get("nodes") if isinstance(thermal0.get("nodes"), list) else []

        power_in0 = float(power0.get("power_in_w", 0.0))
        power_out0 = float(power0.get("power_out_w", 0.0))
        dock_connected0 = bool(power0.get("dock_connected", True))

        if dock_connected0 or power_in0 > 0.5 or not (60.0 <= power_out0 <= 90.0) or thermal_nodes0:
            pytest.skip("Not running power SoC drain fixture")

        soc_samples_run = await sample_soc_over(3.0)
        assert soc_samples_run, "No telemetry samples observed"
        assert min(soc_samples_run) < (soc_samples_run[0] - 0.3), "SoC did not decrease while RUNNING"

        paused_at = asyncio.get_running_loop().time()
        await publish(CommandMessage(command_name="sim.pause", parameters={}, metadata=meta))
        await wait_for(lambda t: (t.get("sim_state") or {}).get("fsm_state") == "PAUSED", timeout_s=8.0)
        await asyncio.sleep(max(0.0, 0.35 - (asyncio.get_running_loop().time() - paused_at)))

        soc_pause_samples = await sample_soc_over(2.0)
        assert soc_pause_samples, "No telemetry samples observed while PAUSED"
        assert (max(soc_pause_samples) - min(soc_pause_samples)) <= 0.05, "SoC changed during PAUSED"

        stopped_at = asyncio.get_running_loop().time()
        await publish(CommandMessage(command_name="sim.stop", parameters={}, metadata=meta))
        await wait_for(lambda t: (t.get("sim_state") or {}).get("fsm_state") == "STOPPED", timeout_s=8.0)
        await asyncio.sleep(max(0.0, 0.35 - (asyncio.get_running_loop().time() - stopped_at)))

        soc_stop_samples = await sample_soc_over(2.0)
        assert soc_stop_samples, "No telemetry samples observed while STOPPED"
        assert (max(soc_stop_samples) - min(soc_stop_samples)) <= 0.05, "SoC changed during STOPPED"
    finally:
        # Keep stack usable for other integration tests / operator workflows.
        try:
            await publish(CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta))
        finally:
            await nc.close()

