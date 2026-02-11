from __future__ import annotations

from qiki.services.q_core_agent.core.radar_situation_config import RadarSituationRuntimeConfig


def test_runtime_config_defaults_and_validation(monkeypatch) -> None:
    monkeypatch.delenv("SITUATION_CONFIRM_FRAMES", raising=False)
    monkeypatch.delenv("SITUATION_COOLDOWN_S", raising=False)
    monkeypatch.delenv("LOST_CONTACT_WINDOW_S", raising=False)
    monkeypatch.delenv("SITUATION_AUTO_RESOLVE_AFTER_LOST_S", raising=False)
    monkeypatch.delenv("SITUATION_ACK_S", raising=False)
    cfg = RadarSituationRuntimeConfig.from_env()
    assert cfg.confirm_frames >= 1
    assert cfg.cooldown_s >= 0.0
    assert cfg.lost_contact_window_s >= 0.0
    assert cfg.auto_resolve_after_lost_s >= 0.0
    assert cfg.ack_snooze_s >= 0.0


def test_runtime_config_invalid_env_does_not_crash(monkeypatch) -> None:
    monkeypatch.setenv("SITUATION_CONFIRM_FRAMES", "not-int")
    monkeypatch.setenv("SITUATION_COOLDOWN_S", "bad")
    monkeypatch.setenv("LOST_CONTACT_WINDOW_S", "-bad")
    monkeypatch.setenv("SITUATION_AUTO_RESOLVE_AFTER_LOST_S", "oops")
    monkeypatch.setenv("SITUATION_ACK_S", "none")
    cfg = RadarSituationRuntimeConfig.from_env()
    assert cfg.confirm_frames == 3
    assert cfg.cooldown_s == 5.0
    assert cfg.lost_contact_window_s == 2.0
    assert cfg.auto_resolve_after_lost_s == 2.0
    assert cfg.ack_snooze_s == 10.0

