Цели Этап--1

Ввести политику диапазонов: LR (дальний, без ID/IFF) и SR (ближний, с ID/IFF) — как в Evochron-логике.

Сохранить обратную совместимость: старые подписчики на qiki.radar.v1.frames/…tracks продолжают жить.

Добавить события EnteredSR/LeftSR, включить Guard-правила, метрики с лейблом band.

Никакого JPDA/IMM/фьюжна/GUI на этом шаге — только разделение и события.

Изменения по файлам (минимально-ломающие)
1) protos/radar/v1/radar.proto — добавить enum/поле (без ломки)
// +++ ADD +++
enum RadarRangeBand {
  RR_UNSPECIFIED = 0;
  RR_LR = 1; // Long Range, no ID/IFF allowed
  RR_SR = 2; // Short Range, ID/IFF permitted
}

message RadarDetection {
  // ... существующие поля ...
  // +++ ADD +++
  optional RadarRangeBand range_band = 90;
}

message RadarTrack {
  // ... существующие поля ...
  // +++ ADD +++
  optional RadarRangeBand range_band = 90;
}


Совместимость: новые поля опциональны → старые сообщения валидны.

Сгенерировать артефакты (как у тебя принято):

make proto  # или ваш скрипт генерации

2) src/qiki/shared/models/radar.py — расширение моделей + валидация

Добавь Enum и валидаторы (PEP 8, типы, ruff-friendly):

# +++ ADD near imports +++
from enum import Enum
from typing import Optional
from pydantic import field_validator, BaseModel

class RangeBand(str, Enum):
    RR_UNSPECIFIED = "RR_UNSPECIFIED"
    RR_LR = "RR_LR"
    RR_SR = "RR_SR"

class RadarDetectionModel(BaseModel):
    # ... существующие поля ...
    range_band: Optional[RangeBand] = None

    @field_validator("transponder_id", mode="after")
    @classmethod
    def _no_id_in_lr(cls, v, info):
        band = info.data.get("range_band")
        if band == RangeBand.RR_LR and v:
            raise ValueError("LR band must not carry transponder_id")
        return v

class RadarTrackModel(BaseModel):
    # ... существующие поля ...
    range_band: Optional[RangeBand] = None
    transponder_id: Optional[str] = None
    transponder_mode: Optional[str] = None
    id_present: Optional[bool] = None

    @field_validator("transponder_id", "transponder_mode", "id_present", mode="after")
    @classmethod
    def _lr_no_id_fields(cls, v, info):
        band = info.data.get("range_band")
        field = info.field_name
        if band == RangeBand.RR_LR and v not in (None, False, "", 0):
            raise ValueError(f"LR band must not carry {field}")
        return v


Мини-юнит на валидаторы добавим в разделе тестов.

3) Новые NATS-сабжекты (добавить, старые не трогаем)

Новые:

qiki.radar.v1.frames.lr — LR-детекции (без ID),

qiki.radar.v1.tracks.sr — SR-треки (с ID/IFF).

Старые:

qiki.radar.v1.frames — временный union (LR+SR) для обратной совместимости,

qiki.radar.v1.tracks — как было (до миграции клиентов).

4) src/qiki/services/q_sim_service/radar_publisher.py — присвоение band + публикации

Идея: при формировании кадра/трека определи band и репаблиш в новые сабжекты; старый frames оставь как union.

# +++ near top +++
from qiki.shared.models.radar import RangeBand
from nats.aio.client import Client as NATS

LR_SUBJECT = "qiki.radar.v1.frames.lr"
SR_SUBJECT = "qiki.radar.v1.tracks.sr"
UNION_FRAME_SUBJECT = "qiki.radar.v1.frames"   # для совместимости

def compute_band(distance_m: float, sr_threshold_m: float) -> RangeBand:
    return RangeBand.RR_SR if distance_m <= sr_threshold_m else RangeBand.RR_LR

async def publish_radar(nc: NATS, frame):
    # frame.det: список детекций/треки; псевдокод – адаптируй к твоей модели
    sr_threshold = cfg.radar.sr_threshold_m  # возьми из твоего конфига
    lr_dets = []
    sr_tracks = []
    for det in frame.det:
        band = compute_band(det.range_m, sr_threshold)
        det.range_band = band
        if band == RangeBand.RR_LR:
            # гарантируем отсутствие ID/IFF
            det.transponder_id = None
            det.transponder_mode = None
            det.id_present = False
            lr_dets.append(det)
        else:
            # для SR готовим треки (или детекции, если у тебя так устроено)
            sr_tracks.append(det_to_track(det))  # твоя вспомогательная функция

    # Паблиш LR-детекции и SR-треки в отдельные сабжекты
    if lr_dets:
        await nc.publish(LR_SUBJECT, encode_cloud_event(lr_dets, band="LR"))
    if sr_tracks:
        await nc.publish(SR_SUBJECT, encode_cloud_event(sr_tracks, band="SR"))

    # Параллельно — старый union-кадр для совместимости (можно пометить header’ом)
    await nc.publish(UNION_FRAME_SUBJECT, encode_cloud_event(frame, band="UNION"))


CloudEvents-хедеры: добавь ce-extension: x-range-band=LR|SR|UNION, чтобы наблюдателям/метрикам было видно.

5) src/qiki/services/faststream_bridge/radar_handlers.py — маршрутизация и лейблы метрик

Подписаться на новые сабжекты;

Метрики (qiki_frame_latency_ms, qiki_radar_msgs_total) — добавить лейбл band="LR|SR|UNION";

В track_publisher.py оставляем текущий поток, добавив поддержку qiki.radar.v1.tracks.sr.

6) src/qiki/services/q_core_agent/core/world_model.py — события EnteredSR/LeftSR

Локальное состояние + генерация событий в Registrar. Порог возьми из конфига (sr_threshold_m):

from typing import Dict, Set
from qiki.shared.events import emit_event  # твой emitter в Registrar

class WorldModel:
    def __init__(self, sr_threshold_m: float) -> None:
        self._sr_threshold = sr_threshold_m
        self._in_sr: Set[str] = set()  # track_id в SR

    def on_track(self, trk: RadarTrackModel) -> None:
        tid = trk.track_id
        is_sr = (trk.range_band == RangeBand.RR_SR) or (trk.range_m <= self._sr_threshold)
        if is_sr and tid not in self._in_sr:
            self._in_sr.add(tid)
            emit_event(src="world_model", code=210, severity="EVT_INFO",
                       msg=f"EnteredSR {tid}", payload=None)
        elif (not is_sr) and tid in self._in_sr:
            self._in_sr.remove(tid)
            emit_event(src="world_model", code=211, severity="EVT_INFO",
                       msg=f"LeftSR {tid}", payload=None)


Если у тебя Track уже несёт range_band, используй его; иначе — fallback по range_m.

7) src/qiki/resources/radar/guard_rules.yaml — расширить правила

Добавь секцию, чтобы Guard умел реагировать на band и на переходы SR:

# +++ ADD +++
range_bands:
  sr_threshold_m: 5000      # пример, вынеси в конфиг
  enforce_no_id_on_lr: true

events:
  - name: entered_sr
    code: 210
    severity: info
    match: { range_band: RR_SR, first_entry: true }
    actions: [ "enable_close_range_behaviors" ]

  - name: left_sr
    code: 211
    severity: info
    match: { range_band: RR_LR, was_in_sr: true }
    actions: [ "disable_close_range_behaviors" ]

rules:
  - name: lr_no_idiff
    when: { range_band: RR_LR }
    assert:
      - "id_present == false"
      - "transponder_id is None"

8) Метрики и back-pressure

Экспортируй qiki_radar_msgs_total{band="LR|SR|UNION"}, qiki_frame_latency_ms{band=...}.

На UI-ветке — «latest-wins» очередь (если есть), в остальном — полная доставка.

Тесты (юнит + интеграция «ИДТ»)
1) Юниты валидаторов (PEP 8, pytest)

tests/unit/test_radar_range_band_validation.py

import pytest
from qiki.shared.models.radar import RadarTrackModel, RangeBand

def test_lr_rejects_id_fields():
    trk = {
        "track_id": "T1",
        "range_m": 42000,
        "range_band": "RR_LR",
        "transponder_id": "ABC",
        "id_present": True,
    }
    with pytest.raises(ValueError):
        RadarTrackModel(**trk)

def test_sr_allows_id_fields():
    trk = {
        "track_id": "T2",
        "range_m": 2000,
        "range_band": "RR_SR",
        "transponder_id": "ABC",
        "id_present": True,
    }
    RadarTrackModel(**trk)  # не должно падать

2) Интеграционные дымовые (ИДТ)

tests/integration/test_radar_lr_sr_topics.py

Поднять окружение (как в существующих интеграционных), подписаться на:

qiki.radar.v1.frames.lr

qiki.radar.v1.tracks.sr

qiki.radar.v1.frames (union)

Сгенерировать сцену из симулятора: цель с дальности >SR → затем <SR.

Ассерты:

На старте в течение ≤2 с пришёл frames.lr без ID;

После сближения пришёл tracks.sr с ID;

В frames (union) оба типа тоже наблюдаются;

CloudEvents-хедер x-range-band проставлен.

tests/integration/test_radar_sr_entry_events.py

Подписаться на qiki.events.v1.audit и на qiki.radar.v1.tracks.sr.

Проверить генерацию EnteredSR (код 210) при первом входе и LeftSR (211) при удалении.

tests/integration/test_guard_lr_no_idiff.py

Включить правило lr_no_idiff.

Подбросить LR-сообщение с «грязным» ID → ожидать Guard-событие нарушения (5xx/warn).

В тестах используй таймауты ≤2–3 с, аккуратный teardown подписок, и не ломай существующие test_radar_flow.py.

Качество кода: PEP 8, ruff, mypy, isort, docstrings
pyproject.toml (или ruff.toml) — добавить/уточнить
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E","F","I","UP","B","N","S","W"]
ignore = ["E203","W503"]
fix = true

[tool.ruff.isort]
combine-as-imports = true
force-sort-within-sections = true

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
strict_optional = true


Соблюдай PEP 8 (имена, длина строк, импорт-блоки).

Докстринги минимум у публичных функций/классов.

Типы везде, особенно в валидаторах и публичных API.

Запуск перед коммитом:

ruff check --fix .
mypy src/ tests/
pytest -q

CI/Compose

Протоген:

make proto


Интеграции:

docker compose -f docker-compose.phase1.yml up -d
pytest tests/integration/test_radar_lr_sr_topics.py -q
pytest tests/integration/test_radar_sr_entry_events.py -q
pytest tests/integration/test_guard_lr_no_idiff.py -q


Если есть pre-commit — добавь ruff, mypy, pytest -q -k unit.

DoD (Definition of Done) Этап--1

Новые поля range_band в protobuf/моделях, валидаторы применяются.

Сим пуляет LR в qiki.radar.v1.frames.lr без ID/IFF; SR → qiki.radar.v1.tracks.sr с ID/IFF; frames остаётся union.

Агент генерит события EnteredSR/LeftSR (210/211) и логирует их в Registrar.

Guard-правило lr_no_idiff срабатывает на грязные LR-сообщения.

Метрики содержат лейбл band.

Все новые тесты зелёные; старые test_radar_* не сломаны.

Ruff/mypy/PEP 8 чисто.

Где могут быть подводные камни (и что делать)

Старые подписчики: не выключай qiki.radar.v1.frames до миграции; просто живи с union.

Отсутствие band у старых сообщений: трактуй как RR_UNSPECIFIED → применяй fallback по дальности.

Дубликаты (union + LR/SR): в тестах фильтруй по сабжекту/хедеру x-range-band.

Конфиг порога SR: вынеси в cfg.radar.sr_threshold_m, добавь sanity-чек (не 0/не отрицательный).