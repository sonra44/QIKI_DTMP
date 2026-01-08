from __future__ import annotations

import asyncio

import pytest

from qiki.services.operator_console.main_orion import OrionApp
from qiki.shared.models.orion_qiki_protocol import EnvironmentSetV1
from qiki.shared.nats_subjects import QIKI_ENVIRONMENT_SET_V1


class _FakeNats:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_command(self, subject: str, command: dict) -> None:
        self.published.append((subject, command))


@pytest.mark.asyncio
async def test_mode_command_publishes_environment_set() -> None:
    app = OrionApp()
    app.nats_client = _FakeNats()  # type: ignore[assignment]

    await app._run_command("mode mission")
    await asyncio.sleep(0)

    assert len(app.nats_client.published) == 1  # type: ignore[attr-defined]
    subject, payload = app.nats_client.published[0]  # type: ignore[attr-defined]
    assert subject == QIKI_ENVIRONMENT_SET_V1

    req = EnvironmentSetV1.model_validate(payload)
    assert req.environment_mode.value == "MISSION"

