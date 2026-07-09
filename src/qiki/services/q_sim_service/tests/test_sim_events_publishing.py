from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.nats_subjects import SIM_POWER_BUS, SIM_POWER_PDU, SIM_SENSOR_THERMAL


class _FakeEventsPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, str, str]] = []

    def publish_event(self, subject: str, payload: dict, *, event_type: str, source: str) -> None:
        self.calls.append((subject, payload, event_type, source))


def test_qsim_publishes_minimal_sim_events() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    fake = _FakeEventsPublisher()
    qsim.events_nats_enabled = True
    qsim._events_publisher = fake  # type: ignore[assignment]
    qsim._events_interval_sec = 0.0
    qsim._events_last_sent_mono = 0.0

    qsim._maybe_publish_events()

    # Санация 0050: минимальный набор сим-событий = 3 (thermal, power.bus,
    # power.pdu — PDU-статус добавлен producer'ом осознанно; подписчика на
    # SIM_POWER_PDU пока нет — forward-looking эмит, зафиксировано в досье).
    assert len(fake.calls) == 3

    by_subject = {subj: payload for (subj, payload, _etype, _source) in fake.calls}
    by_type = {subj: etype for (subj, _payload, etype, _source) in fake.calls}
    assert set(by_subject.keys()) == {SIM_SENSOR_THERMAL, SIM_POWER_BUS, SIM_POWER_PDU}

    thermal = by_subject[SIM_SENSOR_THERMAL]
    assert thermal["schema_version"] == 1
    assert thermal["category"] == "sensor"
    assert thermal["source"] == "thermal"
    assert thermal["subject"] == "core"
    assert isinstance(thermal["temp"], float)
    assert isinstance(thermal["ts_epoch"], float)

    bus = by_subject[SIM_POWER_BUS]
    assert bus["schema_version"] == 1
    assert bus["category"] == "power"
    assert bus["source"] == "bus"
    assert bus["subject"] == "main"
    assert isinstance(bus["current"], float)
    assert isinstance(bus["bus_v"], float)
    assert isinstance(bus["ts_epoch"], float)

    pdu = by_subject[SIM_POWER_PDU]
    assert by_type[SIM_POWER_PDU] == "qiki.events.v1.PowerPduStatus"
    assert pdu["schema_version"] == 1
    assert pdu["category"] == "power"
    assert pdu["source"] == "pdu"
    assert pdu["overcurrent"] in (0, 1)
    assert isinstance(pdu["pdu_limit_w"], float)
    assert isinstance(pdu["bus_v"], float)
    assert isinstance(pdu["ts_epoch"], float)
