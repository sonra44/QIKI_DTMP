import pytest

from qiki.services.q_core_agent.core import interfaces
from qiki.shared.models.core import FsmStateEnum, FsmStateSnapshot


class _HappyProvider(interfaces.IDataProvider):
    def get_bios_status(self):
        return None

    def get_fsm_state(self) -> FsmStateSnapshot:
        return FsmStateSnapshot(
            current_state=FsmStateEnum.IDLE,
            previous_state=FsmStateEnum.BOOTING,
        )

    def get_proposals(self):
        return []

    def get_sensor_data(self):
        return None

    def send_actuator_command(self, command):
        return None


def test_interface_happy_path_returns_ok_with_value() -> None:
    provider = _HappyProvider()

    result = provider.get_fsm_state_result()

    assert result.ok is True
    assert result.value is not None
    assert result.reason == interfaces.InterfaceReason.OK.value
    assert result.is_fallback is False


def test_qsim_interface_unavailable_returns_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_INTERFACE_FALLBACK", "false")
    monkeypatch.setenv("QIKI_USE_STATESTORE", "false")

    provider = interfaces.QSimDataProvider(qsim_service_instance=object())
    result = provider.get_fsm_state_result()

    assert result.ok is False
    assert result.value is None
    assert result.reason == interfaces.InterfaceReason.UNAVAILABLE.value
    with pytest.raises(RuntimeError):
        provider.get_fsm_state()


def test_qsim_interface_fallback_is_explicit_not_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_INTERFACE_FALLBACK", "true")
    monkeypatch.setenv("QIKI_USE_STATESTORE", "false")

    provider = interfaces.QSimDataProvider(qsim_service_instance=object())
    result = provider.get_fsm_state_result()

    assert result.ok is False
    assert result.is_fallback is True
    assert result.reason == interfaces.InterfaceReason.FALLBACK.value
    assert result.value is not None
