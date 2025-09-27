import pytest
from qiki.shared.models.radar import (
    RadarTrackModel,
    RadarDetectionModel,
    RangeBand,
    FriendFoeEnum,
    RadarTrackStatusEnum,
)

def test_lr_rejects_id_fields():
    """Проверяет, что Pydantic-валидатор запрещает ID-поля в LR-диапазоне."""
    trk_data = {
        "track_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "range_m": 42000,
        "bearing_deg": 180.0,
        "elev_deg": 5.0,
        "vr_mps": -100.0,
        "snr_db": 20.0,
        "rcs_dbsm": 1.0,
        "range_band": RangeBand.RR_LR,  # Ключевое условие
        "transponder_id": "ABC-123",  # Запрещенное поле
        "iff": FriendFoeEnum.FRIEND,
        "status": RadarTrackStatusEnum.TRACKED
    }
    with pytest.raises(ValueError, match="LR band must not carry transponder_id"):
        RadarTrackModel(**trk_data)

def test_sr_allows_id_fields():
    """Проверяет, что Pydantic-валидатор РАЗРЕШАЕТ ID-поля в SR-диапазоне."""
    trk_data = {
        "track_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12",
        "range_m": 2000,
        "bearing_deg": 180.0,
        "elev_deg": 5.0,
        "vr_mps": -100.0,
        "snr_db": 20.0,
        "rcs_dbsm": 1.0,
        "range_band": RangeBand.RR_SR, # Ключевое условие
        "transponder_id": "ABC-123", # Разрешенное поле
        "id_present": True,
        "iff": FriendFoeEnum.FRIEND,
        "status": RadarTrackStatusEnum.TRACKED
    }
    # Эта строка не должна вызывать исключение
    RadarTrackModel(**trk_data)


def test_detection_lr_blocks_id():
    det_data = {
        "range_m": 12000,
        "bearing_deg": 45.0,
        "elev_deg": 3.0,
        "vr_mps": -50.0,
        "snr_db": 18.0,
        "rcs_dbsm": 0.5,
        "range_band": RangeBand.RR_LR,
        "transponder_id": "ALLY-01",
        "id_present": True,
    }
    with pytest.raises(ValueError, match="LR band must not carry transponder_id"):
        RadarDetectionModel(**det_data)


def test_track_lr_blocks_id_present_flag():
    trk_data = {
        "track_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13",
        "range_m": 40000,
        "bearing_deg": 90.0,
        "elev_deg": 1.0,
        "vr_mps": 10.0,
        "snr_db": 15.0,
        "rcs_dbsm": 0.2,
        "range_band": RangeBand.RR_LR,
        "id_present": True,
        "iff": FriendFoeEnum.UNKNOWN,
        "status": RadarTrackStatusEnum.NEW,
    }
    with pytest.raises(ValueError, match="LR band must not carry id_present"):
        RadarTrackModel(**trk_data)
