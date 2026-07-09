"""Блок 0, этап 4 «гигиена консоли»: голая q, f5/f8, полночь, ACK, кэпы, пороги.

По `02_BLOCK0_DEFECT_BASELINE.md` (0.12-0.17) и `08_VERIFICATION_PLAN.md`
(этап 4).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.command_decision import CommandIntent, DecisionStore, seal_decision


def _app_for_commands() -> tuple[OrionVApp, list[str]]:
    app = OrionVApp()
    helps: list[str] = []
    app._set_help_text = lambda text: helps.append(text)  # type: ignore[method-assign]
    app._request_refresh_ui = lambda: None  # type: ignore[method-assign]
    app.action_close_command_mode = lambda: None  # type: ignore[method-assign]
    app.action_quit = Mock()  # type: ignore[method-assign]
    app.action_show_level = Mock()  # type: ignore[method-assign]
    return app, helps


def _submit(app: OrionVApp, text: str) -> None:
    app.on_input_submitted(SimpleNamespace(value=text, input=SimpleNamespace(value="")))


# ── 0.12: голая q не закрывает консоль ───────────────────────────────────────

def test_bare_q_does_not_quit() -> None:
    app, helps = _app_for_commands()
    _submit(app, "q")
    app.action_quit.assert_not_called()
    assert helps and "quit" in helps[-1].lower()  # подсказка вместо выхода


def test_explicit_quit_asks_confirmation() -> None:
    """Этап 8 (§F4-3, карточка D): выход — только с подтверждением.
    quit открывает ConfirmDialog; action_quit — только по callback(True)."""
    from qiki.services.operator_console.orion_v.dialogs import ConfirmDialog

    app, _ = _app_for_commands()
    pushed: list[tuple[object, object]] = []
    app.push_screen = lambda screen, callback=None: pushed.append((screen, callback))  # type: ignore[method-assign]

    _submit(app, "quit")
    app.action_quit.assert_not_called()  # без подтверждения выхода нет
    assert len(pushed) == 1 and isinstance(pushed[0][0], ConfirmDialog)

    pushed[0][1](True)  # оператор подтвердил
    app.action_quit.assert_called_once()


def test_quit_confirm_guard_prevents_stacked_modals() -> None:
    """Повторный quit до ответа не наслаивает второй модал (guard)."""
    app, _ = _app_for_commands()
    pushed: list[tuple[object, object]] = []
    app.push_screen = lambda screen, callback=None: pushed.append((screen, callback))  # type: ignore[method-assign]

    _submit(app, "quit")
    _submit(app, "exit")
    assert len(pushed) == 1, "второй quit наслоил модал"

    pushed[0][1](False)  # оператор остался
    app.action_quit.assert_not_called()
    _submit(app, "quit")  # после ответа guard снят
    assert len(pushed) == 2


def test_hotkey_q_shows_hint_not_quit() -> None:
    """Вторая половина 0.12: горячая клавиша q тоже не закрывает консоль."""
    app, helps = _app_for_commands()
    app.action_show_quit_hint()
    app.action_quit.assert_not_called()
    assert helps and "quit" in helps[-1].lower()
    assert ("q", "quit", "Выход") not in OrionVApp.BINDINGS


# ── 0.13: f5/f8 в текстовом переключателе уровней ────────────────────────────

def test_f5_and_f8_switch_levels() -> None:
    app, _ = _app_for_commands()
    _submit(app, "f5")
    _submit(app, "f8")
    assert [c.args[0] for c in app.action_show_level.call_args_list] == ["f5", "f8"]


# ── 0.14: сортировка ленты переживает полночь ────────────────────────────────

def test_dialog_sort_survives_midnight() -> None:
    from qiki.services.operator_console.orion_v.qiki_voice import QikiVoiceEntry
    from qiki.services.operator_console.orion_v.screens.qiki_dialog import merge_dialog_lines

    lines = merge_dialog_lines(
        operator_lines=[
            ("23:59:50Z", "статус перед полуночью"),
            ("00:00:05Z", "статус после полуночи"),
        ],
        voice_entries=[
            QikiVoiceEntry(received_at="23:59:55Z", kind="INFO", text="принято", legality_code=None, trust_code=None),
            QikiVoiceEntry(received_at="00:00:10Z", kind="INFO", text="работаю", legality_code=None, trust_code=None),
        ],
    )
    texts = [line.text for line in lines]
    assert texts == ["статус перед полуночью", "принято", "статус после полуночи", "работаю"]


# ── 0.15: pending ACK сбрасывается; чужие ACK не перетираются ────────────────

def test_pending_ack_resets_after_timeout() -> None:
    app, _ = _app_for_commands()
    app._pending_ack_command_id = "cmd-123"
    app._ack_wait_started_mono = 0.0
    ok = asyncio.run(app._wait_for_ack("sim.start", timeout_s=0.05))
    assert ok is False
    assert app._pending_ack_command_id is None  # P не завышен навсегда


def test_publish_does_not_wipe_foreign_acks() -> None:
    app, _ = _app_for_commands()
    app._nats_client = SimpleNamespace()

    async def _fake_publish(subject, payload) -> None:  # noqa: ARG001
        return None

    app._nats_client.publish_command = _fake_publish
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore[method-assign]
    foreign = {"data": {"command_id": "foreign-1", "kind": "ack"}, "_received_mono": 0.0}
    app._control_acks.append(foreign)
    asyncio.run(app._publish_sim_command("sim.start", {}))
    assert foreign in app._control_acks  # чужой pending не перетёрт


# ── 0.16: кэпы памяти ────────────────────────────────────────────────────────

def test_latest_radar_tracks_capped() -> None:
    app, _ = _app_for_commands()
    for i in range(300):
        asyncio.run(app._on_track({"data": {"track_id": f"trk-{i}", "status": "TRACKED"}}))
    assert len(app._latest_radar_tracks) <= 128
    assert "trk-299" in app._latest_radar_tracks  # свежие живут, старые выселены


def test_incident_first_seen_capped() -> None:
    app, _ = _app_for_commands()
    app._spawn_task = lambda coro: coro.close()  # аудит-паблиш не нужен
    for i in range(2000):
        asyncio.run(app._on_event({"subject": "qiki.events.v1.audit", "data": {"incident_id": f"inc-{i}", "severity": "C"}}))
    assert len(app._incident_first_seen) <= 1024
    assert "inc-1999" in app._incident_first_seen


def test_decision_store_capped() -> None:
    store = DecisionStore()
    for i in range(700):
        intent = CommandIntent(kind="NATS_COMMAND", subject="s", name=f"cmd-{i}", parameters={}, operator_facing_title="t")
        store.put(seal_decision(decision_id=f"d-{i}", intent=intent))
    assert len(store._by_id) <= 500
    assert store.get("d-699") is not None  # свежие решения не выселяются


# ── 0.17: пороги питания — только shared-канон ───────────────────────────────

def test_power_module_uses_shared_thresholds() -> None:
    from qiki.services.operator_console.orion_v.modules.common import tr
    from qiki.services.operator_console.orion_v.modules.power import PowerSubsystemModule

    module = PowerSubsystemModule()

    def _status(power: dict) -> str:
        return module.render_summary({"telemetry": {"power": power}}).split(" | ")[0]

    # SOC 25% — между локальной копией warn(30) и shared-каноном warn(20): OK
    assert _status({"soc_pct": 25.0, "bus_v": 28.0}) == tr("ok")
    # bus 23В — между локальной копией warn(24) и shared-каноном warn(22): OK
    assert _status({"soc_pct": 80.0, "bus_v": 23.0}) == tr("ok")
    # ниже shared-канона — честные WARN/CRIT
    assert _status({"soc_pct": 18.0, "bus_v": 28.0}) == tr("warn")
    assert _status({"soc_pct": 80.0, "bus_v": 19.0}) == tr("crit")
