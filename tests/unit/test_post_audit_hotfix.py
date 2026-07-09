"""Hotfix-срез пост-фикс аудита (AUDIT_2026-07-09_POSTFIX.md): M1, M2, M3, M7.

M1 — fire-and-forget команда не должна залипать pending (P).
M2 — параллельный publisher не подменяет command_id ждущему.
M3 — «Краткие факты»: группа без данных реально схлопывается на боевых строках.
M7 — exception-ветка warmup мутирует контекст только под lock.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen


def _app() -> OrionVApp:
    app = OrionVApp()
    app._set_help_text = lambda *a, **k: None  # type: ignore[method-assign]
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore[method-assign]
    app._request_refresh_ui = lambda: None  # type: ignore[method-assign]

    class _StubNats:
        async def publish_command(self, _subject: str, _payload: dict) -> None:
            return None

    app._nats_client = _StubNats()  # type: ignore[assignment]
    return app


def _ack(command_id: str, name: str) -> dict:
    return {
        "_received_mono": time.monotonic(),
        "data": {
            "ok": True,
            "kind": name,
            "request_id": command_id,
            "payload": {"command_name": name, "status": "applied"},
        },
    }


# ── M2: ждущий держит СВОЙ command_id, чужой publish его не сбивает ──────────

def test_wait_for_ack_survives_concurrent_publisher() -> None:
    app = _app()

    async def run() -> bool:
        rid_a = await app._publish_sim_command("sim.pause")
        assert isinstance(rid_a, str) and rid_a  # publish возвращает id
        # конкурент перезаписывает общий слот ДО начала ожидания A
        rid_b = await app._publish_sim_command("sim.start")
        assert rid_b != rid_a
        app._control_acks.append(_ack(rid_a, "sim.pause"))
        return await app._wait_for_ack("sim.pause", 0.3, command_id=rid_a)

    assert asyncio.run(run()) is True  # свой ACK найден несмотря на чужой pending


# ── M1: fire-and-forget мировой команды доводит цикл и снимает pending ───────

def test_fire_and_forget_world_command_resolves_pending() -> None:
    app = _app()

    async def run() -> None:
        task = asyncio.get_running_loop().create_task(
            app._publish_sim_command_tracked("sim.start", {})
        )
        await asyncio.sleep(0.05)
        # ACK приходит на текущий pending (это же id вернул publish внутри)
        pending = app._pending_ack_command_id
        assert pending, "pending должен быть выставлен на время ожидания"
        app._control_acks.append(_ack(pending, "sim.start"))
        await task

    asyncio.run(run())
    assert app._pending_ack_command_id is None  # P не залип


def test_fire_and_forget_world_command_clears_pending_on_timeout() -> None:
    app = _app()

    async def run() -> None:
        await app._publish_sim_command_tracked("sim.start", {}, ack_timeout_s=0.05)

    asyncio.run(run())
    assert app._pending_ack_command_id is None


# ── M3: схлопывание Z8 на БОЕВЫХ строках (не синтетике) ──────────────────────

def test_quick_facts_honest_on_real_energy_lines() -> None:
    """На боевых строках: хвост-подпись («… | crit < N%») не считается данными;
    warn-группа без источника НЕ прячется (§19.6), но и не тащит хвост."""
    screen = OrionVCockpitScreen()
    energy_sev, energy_lines = screen._energy_block({})  # телеметрии нет вообще
    details = (
        screen._fact_value_detail(energy_lines[0], "Заряд/SOC: "),
        screen._fact_value_detail(energy_lines[1], "Шина/Bus: "),
    )
    assert details == ("", "")  # значений нет — детали честно пусты
    rows = screen.build_quick_fact_rows([("ENERGY", energy_sev, details)])
    joined = "\n".join(rows)
    assert "crit <" not in joined  # статический хвост не выдан за данные
    if energy_sev in {"warn", "crit"}:
        assert any("ENERGY" in row and "Нет данных" in row for row in rows)
    else:
        assert "нет данных: ENERGY" in joined

    # ok-группа без данных схлопывается в одну строку
    rows = screen.build_quick_fact_rows([("COMMS", "ok", ("", ""))])
    assert rows == ["нет данных: COMMS"]

    # при живом значении группа остаётся рядом с данными
    energy_sev, energy_lines = screen._energy_block({"power": {"soc_pct": 42.0}})
    details = (screen._fact_value_detail(energy_lines[0], "Заряд/SOC: "),)
    rows = screen.build_quick_fact_rows([("ENERGY", energy_sev, details)])
    assert any("42" in row for row in rows)


# ── M7: fallback-ingest в warmup идёт под lock ───────────────────────────────

def test_warmup_fallback_ingest_holds_lock(monkeypatch) -> None:
    import qiki.services.q_core_agent.qiki_orion_intents_service as svc

    lock = asyncio.Lock()
    locked_during_ingest: list[bool] = []

    def _boom_refresh(*, agent, data_provider) -> None:  # noqa: ARG001
        raise RuntimeError("refresh down")

    class _Agent:
        context = SimpleNamespace(world_snapshot={}, latest_sensor_data=None)

        def _ingest_sensor_data(self, _provider) -> None:
            locked_during_ingest.append(lock.locked())

    monkeypatch.setattr(svc, "_refresh_agent_snapshot", _boom_refresh)

    async def run() -> None:
        await svc._refresh_agent_snapshot_until_target_track(
            agent=_Agent(),
            data_provider=SimpleNamespace(),
            target_designator="X-9999",
            timeout_s=0.15,
            step_s=0.05,
            lock=lock,
        )

    asyncio.run(run())
    assert locked_during_ingest, "fallback-ingest не вызвался"
    assert all(locked_during_ingest)  # мутация контекста только под lock
