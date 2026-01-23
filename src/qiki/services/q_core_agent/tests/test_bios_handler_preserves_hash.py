
from __future__ import annotations

from datetime import UTC, datetime

from qiki.services.q_core_agent.core.bios_handler import BiosHandler
from qiki.shared.models.core import BiosStatus


class _DummyBotCore:
    def get_property(self, property_name: str):  # noqa: ANN001
        return None


def test_bios_handler_preserves_hardware_profile_hash() -> None:
    handler = BiosHandler(_DummyBotCore())

    status = BiosStatus(
        bios_version="v1",
        firmware_version="fw1",
        hardware_profile_hash="hash-123",
        post_results=[],
        timestamp=datetime.now(UTC),
    )

    updated = handler.process_bios_status(status)
    assert updated.hardware_profile_hash == "hash-123"
