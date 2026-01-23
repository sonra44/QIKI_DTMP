from __future__ import annotations

import pytest

from qiki.services.q_bios_service import health_checker


class _DummyResponse:
    def __init__(self, message: str = "ok") -> None:
        self.message = message


class _DummyStub:
    def __init__(self, channel) -> None:  # noqa: ANN001
        self._channel = channel

    def HealthCheck(self, req, timeout: float):  # noqa: N802, ANN001
        return _DummyResponse("ok")


def test_check_qsim_health_closes_channel_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"value": False}

    class _Channel:
        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(health_checker.grpc, "insecure_channel", lambda address: _Channel())
    monkeypatch.setattr(health_checker, "QSimAPIServiceStub", lambda channel: _DummyStub(channel))

    res = health_checker.check_qsim_health(host="localhost", port=50051, timeout_s=0.1)
    assert res.ok is True
    assert closed["value"] is True


def test_check_qsim_health_closes_channel_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"value": False}

    class _Channel:
        def close(self) -> None:
            closed["value"] = True

    class _FailingStub:
        def __init__(self, channel) -> None:  # noqa: ANN001
            self._channel = channel

        def HealthCheck(self, req, timeout: float):  # noqa: N802, ANN001
            raise RuntimeError("boom")

    monkeypatch.setattr(health_checker.grpc, "insecure_channel", lambda address: _Channel())
    monkeypatch.setattr(health_checker, "QSimAPIServiceStub", lambda channel: _FailingStub(channel))

    res = health_checker.check_qsim_health(host="localhost", port=50051, timeout_s=0.1)
    assert res.ok is False
    assert closed["value"] is True

