"""№8в (сопутствующий runtime-фикс): изоляция подписок ORION V.

Живой инцидент 2026-07-04: вторая консоль в контейнере (канон-путь
run_orion_v_live.sh → docker exec) падала на tracks-подписке («consumer is
already bound to a subscription»), и ВЕСЬ остальной батч (events, control,
qiki responses) молча не подписывался — голос QIKI не доходил до пульта.

RED-негатив: провал одной подписки не должен хоронить остальные.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp


class _FakeNC:
    is_connected = True


class _FakeNatsClient:
    connection_state = "connected"

    def __init__(self) -> None:
        self.nc = _FakeNC()
        self.calls: list[str] = []

    async def connect(self) -> None:
        self.calls.append("connect")

    async def subscribe_system_telemetry(self, cb) -> None:
        self.calls.append("telemetry")

    async def subscribe_tracks(self, cb) -> None:
        self.calls.append("tracks")
        raise RuntimeError("nats: JetStream.Error consumer is already bound to a subscription")

    async def subscribe_events(self, cb) -> None:
        self.calls.append("events")

    async def subscribe_control_responses(self, cb) -> None:
        self.calls.append("control_responses")

    async def subscribe_qiki_responses(self, cb) -> None:
        self.calls.append("qiki_responses")


def test_failed_tracks_subscription_does_not_kill_qiki_responses() -> None:
    app = OrionVApp.__new__(OrionVApp)  # без TUI: тестируем только подписочный контур
    fake = _FakeNatsClient()
    app._nats_client = fake  # noqa: SLF001 - целевой контур теста
    app._subscriptions_started = False  # noqa: SLF001
    app._subscribed_keys = set()  # noqa: SLF001

    asyncio.run(app._connect_and_subscribe())  # noqa: SLF001

    assert "qiki_responses" in fake.calls, "провал tracks не должен хоронить qiki-подписку"
    assert "events" in fake.calls
    assert "control_responses" in fake.calls
    # батч не завершён (tracks так и не подписан) — флаг честно False, ретрай продолжится
    assert app._subscriptions_started is False  # noqa: SLF001


def test_retry_resubscribes_only_missing_subscriptions() -> None:
    app = OrionVApp.__new__(OrionVApp)
    fake = _FakeNatsClient()
    app._nats_client = fake  # noqa: SLF001
    app._subscriptions_started = False  # noqa: SLF001
    app._subscribed_keys = set()  # noqa: SLF001

    asyncio.run(app._connect_and_subscribe())  # noqa: SLF001
    first_round = list(fake.calls)
    asyncio.run(app._connect_and_subscribe())  # noqa: SLF001
    second_round = fake.calls[len(first_round):]

    # повторный проход трогает только несостоявшуюся подписку, без дублей остальных
    assert "tracks" in second_round
    assert "qiki_responses" not in second_round
    assert "telemetry" not in second_round
