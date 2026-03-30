import grpc
import pytest

from qiki.services.q_core_agent.core import grpc_data_provider as gdp
from qiki.shared.models.core import SensorData, SensorTypeEnum


class _DummyRpcError(grpc.RpcError):
    def __init__(self, status_code: grpc.StatusCode, details: str):
        super().__init__()
        self._status_code = status_code
        self._details = details

    def code(self):
        return self._status_code

    def details(self):
        return self._details

    def __str__(self) -> str:
        return self._details


def _provider_with_stub(monkeypatch: pytest.MonkeyPatch, stub) -> gdp.GrpcDataProvider:
    class _DummyChannel:
        def close(self) -> None:
            return None

    def _fake_connect(self):
        self.channel = _DummyChannel()
        self.stub = stub

    monkeypatch.setattr(gdp.GrpcDataProvider, "_connect", _fake_connect)
    return gdp.GrpcDataProvider("dummy:50051")


def test_get_sensor_data_timeout_raises_when_fallback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Stub:
        def GetSensorData(self, *_args, **_kwargs):
            raise _DummyRpcError(grpc.StatusCode.DEADLINE_EXCEEDED, "deadline exceeded")

    monkeypatch.setenv("QIKI_ALLOW_GRPC_FALLBACK", "false")
    provider = _provider_with_stub(monkeypatch, _Stub())

    with pytest.raises(gdp.GrpcTimeout):
        provider.get_sensor_data()


def test_get_sensor_data_invalid_payload_raises_when_fallback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Reading:
        class sensor_id:
            value = "sensor-1"

    class _Response:
        reading = _Reading()

    class _Stub:
        def GetSensorData(self, *_args, **_kwargs):
            return _Response()

    def _raise_invalid(_reading):
        raise ValueError("missing oneof payload")

    monkeypatch.setenv("QIKI_ALLOW_GRPC_FALLBACK", "false")
    monkeypatch.setattr(gdp, "proto_sensor_reading_to_pydantic_sensor_data", _raise_invalid)
    provider = _provider_with_stub(monkeypatch, _Stub())

    with pytest.raises(gdp.GrpcInvalidPayload):
        provider.get_sensor_data()


def test_get_sensor_data_happy_path_returns_valid_sensor_data(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Reading:
        class sensor_id:
            value = "sensor-ok"

    class _Response:
        reading = _Reading()

    class _Stub:
        def GetSensorData(self, *_args, **_kwargs):
            return _Response()

    expected = SensorData(
        sensor_id="sensor-ok",
        sensor_type=SensorTypeEnum.OTHER,
        scalar_data=42.0,
        metadata={"source": "test"},
        quality_score=1.0,
    )

    monkeypatch.setenv("QIKI_ALLOW_GRPC_FALLBACK", "false")
    monkeypatch.setattr(gdp, "proto_sensor_reading_to_pydantic_sensor_data", lambda _reading: expected)
    provider = _provider_with_stub(monkeypatch, _Stub())

    result = provider.get_sensor_data()
    assert result == expected


def test_get_sensor_data_timeout_returns_explicit_fallback_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Stub:
        def GetSensorData(self, *_args, **_kwargs):
            raise _DummyRpcError(grpc.StatusCode.DEADLINE_EXCEEDED, "deadline exceeded")

    monkeypatch.setenv("QIKI_ALLOW_GRPC_FALLBACK", "true")
    provider = _provider_with_stub(monkeypatch, _Stub())

    result = provider.get_sensor_data()
    assert result.string_data == "NO_DATA"
    assert result.metadata.get("is_fallback") is True
    assert result.metadata.get("reason") == "timeout"
