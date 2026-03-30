import pytest

from qiki.services.q_core_agent.core import ship_actuators as sa


class _ShipCoreOK:
    def __init__(self) -> None:
        self._config = {"mode": "normal"}

    def send_actuator_command(self, _command) -> None:
        return None


class _ShipCoreTimeout:
    def __init__(self) -> None:
        self._config = {"mode": "normal"}

    def send_actuator_command(self, _command) -> None:
        raise TimeoutError("ack timeout")


class _ShipCoreUnavailable:
    def __init__(self) -> None:
        self._config = {"mode": "normal"}

    def send_actuator_command(self, _command) -> None:
        raise ConnectionError("actuator bus unavailable")


class _ShipCoreShouldNotSend:
    def __init__(self) -> None:
        self._config = {"mode": "normal"}

    def send_actuator_command(self, _command) -> None:
        raise AssertionError("send must not be called in fallback mode")


def test_main_drive_happy_path_returns_accepted_with_command_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_ACTUATOR_FALLBACK", "false")
    monkeypatch.setattr(sa, "ACTUATOR_PROTO_FALLBACK_ACTIVE", False)

    controller = sa.ShipActuatorController(_ShipCoreOK())
    result = controller.set_main_drive_thrust_result(30.0)

    assert result.status == sa.ActuationStatus.ACCEPTED
    assert result.command_id
    assert result.correlation_id == result.command_id
    assert result.is_fallback is False


def test_main_drive_timeout_returns_timeout_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_ACTUATOR_FALLBACK", "false")
    monkeypatch.setattr(sa, "ACTUATOR_PROTO_FALLBACK_ACTIVE", False)

    controller = sa.ShipActuatorController(_ShipCoreTimeout())
    result = controller.set_main_drive_thrust_result(20.0)

    assert result.status == sa.ActuationStatus.TIMEOUT
    assert controller.set_main_drive_thrust(20.0) is False


def test_main_drive_unavailable_returns_unavailable_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_ACTUATOR_FALLBACK", "false")
    monkeypatch.setattr(sa, "ACTUATOR_PROTO_FALLBACK_ACTIVE", False)

    controller = sa.ShipActuatorController(_ShipCoreUnavailable())
    result = controller.set_main_drive_thrust_result(20.0)

    assert result.status == sa.ActuationStatus.UNAVAILABLE
    assert controller.set_main_drive_thrust(20.0) is False


def test_fallback_allowed_returns_explicit_simulated_actuation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_ACTUATOR_FALLBACK", "true")
    monkeypatch.setattr(sa, "ACTUATOR_PROTO_FALLBACK_ACTIVE", True)

    controller = sa.ShipActuatorController(_ShipCoreShouldNotSend())
    result = controller.set_main_drive_thrust_result(10.0)

    assert result.status == sa.ActuationStatus.ACCEPTED
    assert result.is_fallback is True
    assert result.reason == "SIMULATED_ACTUATION"
