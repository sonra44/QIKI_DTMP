"""M5 live-proof (RED): подменённая после одобрения команда НЕ публикуется.

Бьёт по настоящему execute-пути консоли (_confirm пломбирует, затем подмена
_qiki_pending_action, затем _execute). Доказывает закрытие Д3:
1) честный путь: одобренная команда публикуется;
2) спуфинг: между одобрением и исполнением name подменён → публикации НЕТ,
   состояние blocked, реального sim-command не ушло.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp


def _pending(name: str) -> dict:
    return {
        "action_kind": "NATS_COMMAND",
        "proposal_id": "p-spoof",
        "title_ru": "Возобновить наблюдение безопасно",
        "title_en": "Resume safe observation",
        "subject": "qiki.commands.control",
        "name": name,
        "parameters": {"target": "ALLY-4D1ED5"},
        "dry_run": False,
    }


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 48)):
        published: list[str] = []

        async def _capture(command_name, parameters):
            published.append(command_name)

        async def _ack_ok(command_name, timeout_s, command_id=None):
            return True

        async def _effect(command_name, timeout_s):
            return None

        app._publish_sim_command = _capture  # type: ignore[assignment]
        app._wait_for_ack = _ack_ok  # type: ignore[assignment]
        app._wait_for_qiki_effect = _effect  # type: ignore[assignment]

        # 1) ЧЕСТНЫЙ путь: одобряем и исполняем ту же команду.
        app._qiki_pending_action = _pending("sim.dock.release")
        app._seal_pending_decision(app._qiki_pending_action)  # мирроринг confirm
        await app._execute_qiki_pending_action()
        assert published == ["sim.dock.release"], f"честная команда не опубликована: {published}"
        print("[smoke] честный путь OK: одобренная команда опубликована")

        # 2) СПУФИНГ: одобряем безобидное, затем подменяем name перед исполнением.
        published.clear()
        app._qiki_pending_action = _pending("sim.dock.release")
        app._seal_pending_decision(app._qiki_pending_action)  # оператор одобрил ЭТО
        # провайдер/гонка подменили действие после одобрения:
        app._qiki_pending_action = _pending("sim.rcs.fire")
        await app._execute_qiki_pending_action()
        assert published == [], f"СПУФИНГ ПРОШЁЛ: опубликовано {published}"
        print("[smoke] пост-seal подмена OK: команда, изменённая ПОСЛЕ одобрения, НЕ опубликована")

    print("[smoke] M5 PASS: публикуется только команда, совпадающая с пломбой одобрения")


if __name__ == "__main__":
    asyncio.run(_main())
