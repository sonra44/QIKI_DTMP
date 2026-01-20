from __future__ import annotations

import pytest

from qiki.services.q_bios_service.config import BiosConfig


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_publish_enabled_parsing(monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
    monkeypatch.setenv("BIOS_PUBLISH_ENABLED", raw)
    cfg = BiosConfig()
    assert cfg.publish_enabled is expected
