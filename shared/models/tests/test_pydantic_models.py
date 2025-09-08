import pytest
from pydantic import ValidationError
from shared.models.core import (
    BiosStatus,
    DeviceStatus,
    DeviceStatusEnum,
    FsmStateSnapshot,
    FsmStateEnum,
    SensorData,
    SensorTypeEnum,
)


def test_bios_status_healthy():
    """
    Тестирует, что all_systems_go=True, когда все устройства OK.
    """
    status = BiosStatus(
        bios_version="1.0",
        firmware_version="2.0",
        post_results=[
            DeviceStatus(
                device_id="cpu", device_name="CPU", status=DeviceStatusEnum.OK
            ),
            DeviceStatus(
                device_id="mem", device_name="Memory", status=DeviceStatusEnum.OK
            ),
        ],
    )
    assert status.all_systems_go is True


def test_bios_status_unhealthy():
    """
    Тестирует, что all_systems_go=False, если хотя бы одно устройство не OK.
    """
    status = BiosStatus(
        bios_version="1.0",
        firmware_version="2.0",
        post_results=[
            DeviceStatus(
                device_id="cpu", device_name="CPU", status=DeviceStatusEnum.OK
            ),
            DeviceStatus(
                device_id="gpu", device_name="GPU", status=DeviceStatusEnum.ERROR
            ),
        ],
    )
    assert status.all_systems_go is False


def test_sensor_data_validation():
    """
    Тестирует, что модель SensorData требует хотя бы одно поле с данными.
    """
    # Должно работать
    SensorData(sensor_id="lidar1", sensor_type=SensorTypeEnum.LIDAR, scalar_data=10.5)

    # Должно вызвать ошибку
    with pytest.raises(ValidationError) as excinfo:
        SensorData(sensor_id="lidar1", sensor_type=SensorTypeEnum.LIDAR)

    assert "Sensor data must have at least one data field" in str(excinfo.value)


def test_fsm_snapshot_defaults():
    """
    Тестирует, что временные метки создаются по умолчанию.
    """
    snapshot = FsmStateSnapshot(
        current_state=FsmStateEnum.IDLE,
        previous_state=FsmStateEnum.BOOTING,
    )
    assert snapshot.ts_mono > 0
    assert snapshot.ts_wall > 0
    assert isinstance(snapshot.history, list)
    assert len(snapshot.history) == 0


def test_pydantic_to_camel_alias():
    """
    Тестирует, что сериализация в JSON использует camelCase псевдонимы.
    """
    status = DeviceStatus(
        device_id="cpu", device_name="CPU", status=DeviceStatusEnum.OK
    )
    json_dict = status.model_dump(by_alias=True)

    assert "deviceId" in json_dict
    assert "deviceName" in json_dict
    assert "statusMessage" in json_dict
    assert (
        "device_id" not in json_dict
    )  # Проверяем, что оригинальные имена не используются
