# Radar Phase 2 Roadmap

## 1. Контекст и актуальное состояние
- **Phase 1 завершён:** end-to-end поток (protobuf → gRPC → JetStream → FastStream) работает, интеграционные тесты `test_radar_*` зелёные. Базовые Pydantic-модели и минимальный `frame_to_track` закрывают MVP.
- **Архитектурная опора:** см. `RADAR.md` (состояние на 2025-09-17). Все изменения Phase 2 должны сохранять обратную совместимость с текущими protobuf/AsyncAPI контрактами.

## 2. Цели Phase 2
1. Перевести радар из режима «сырые кадры + заглушка» в полноценный тактический орган: устойчивый stateful-трекинг, качественные IFF-режимы, понятные оператору представления.
2. Ввести формализованные guard-правила для FSM/WorldModel, чтобы решения агента опирались на радар.
3. Усилить наблюдаемость и отказоустойчивость потока (JetStream, FastStream, UI, логирование, аудит).

## 3. Блоки реализации

### 3.1 Stateful-трекинг (`services/faststream_bridge/radar_handlers.py`, `shared/models/radar.py`)
- **Задачи:**
  - Заменить `frame_to_track` на `TrackStore` с фильтрацией и ассоциацией (KF/EKF на полярных координатах, окно по дальности/азимуту/доплеру, счётчики жизни).
  - Расширить `RadarTrackModel` полями `position`, `velocity`, ковариациями и `quality`/`status` по аналогии с `radar_msgs/RadarTrack.msg` (ROS).
  - Обновить симулятор, чтобы генерировать plausible шум/доплер и режимы потери кадров.
- **Deliverables:** модуль `track_store.py`, unit-тесты на ассоциацию/сброс треков, обновлённые integration test сценарии (потеря, всплеск детекций).
- **Риски/зависимости:** требуется мат-обоснование фильтра (выделить отдельный design-note). Совместимость со старыми схемами обеспечиваем через optional-поля (protobuf остаётся прежним).
- **Ресурсы:** [ROS radar_msgs](https://wiki.ros.org/radar_msgs/), `radar_msgs/RadarTrack.msg` (struct для расширенных полей).

### 3.2 IFF и транспондер (`shared/models/radar.py`, `services/q_sim_service`, `services/q_core_agent`)
- **Задачи:**
  - Формализовать режимы: `ON | OFF | SILENT | SPOOF`, добавить enum в модели и симулятор.
  - Ввести логику слияния: IFF-метка связывается с треком в окне по дальности/азимуту/скорости, иначе класс `UNKNOWN`.
  - Логирование всех команд транспондера, отдельный subject для событий `spoof`.
- **Deliverables:** обновлённые Pydantic-модели, сценарии симулятора, регрессионные тесты на режимы.
- **Ресурсы:** [radartutorial.eu — Primary vs Secondary radar](https://www.radartutorial.eu/07.waves/wa02.en.html) (подтверждает видимость цели при отключённом транспондере), FAA IFF материалы.

### 3.3 FSM и guard-правила (`services/q_core_agent/core`, `state/`, `tests`)
- **Задачи:**
  - Зафиксировать таблицу guard-условий (danger sectors, range thresholds, spoof alerts) и интегрировать в FSM.
  - Публиковать переходы в тему `qiki.fsm.transitions`, чтобы оператор видел логику.
  - Обновить WorldModel: хранить активные треки, их IFF/quality.
- **Deliverables:** YAML/JSON спецификация guard-правил, unit-тесты на переходы, integration tests с симуляцией событий.
- **Ресурсы:** практики ROS Navigation (behavior trees на guard-условиях), internal FSM guidelines.

### 3.4 JetStream/FastStream и наблюдаемость (`tools/js_init.py`, `services/faststream_bridge`, `observability/`)
- **Задачи:**
  - Пересмотреть настройки JetStream: `MaxAckPending`, `AckWait`, выбор push/pull-консюмеров для тяжёлых обработчиков (рекомендации [docs.nats.io](https://docs.nats.io/nats-concepts/jetstream)).
  - Добавить метрики (Prometheus/OpenTelemetry): задержки публикации/потребления, redeliveries, lag, dropped frames.
  - Алерты при выходе за SLA (target p50 <= 500ms, p95 <= 1500ms).
- **Deliverables:** конфиги JetStream v2, метрики, dashboards, integration test на redelivery.

### 3.5 Операторский UI (`services/q_core_agent/ui`, `docs/`) 
- **Задачи:**
  - Определить DTO `RadarTableRow` (знаки по вертикали, дальность, азимут, IFF, quality) и терминальный рендер.
  - Добавить легенду и частоту обновления (4–8 Гц), предусмотреть scroll/filters.
  - Обновить документацию (README, ARCHITECTURE раздел UI).
- **Deliverables:** UI-модуль, e2e-тест (snapshot), обновлённые doc.

### 3.6 Доступ и аудит (`services/q_core_agent`, `auth/`, `docs/SECURITY`) 
- **Задачи:**
  - Ввести OAuth scopes для операций радара (read tracks, toggle transponder).
  - Журналирование команд (who/when/why), экспорт в SIEM.
  - Security review (spoof сценарии, rate limiting на команды).
- **Deliverables:** policy-док, тесты RBAC, обновлённая security doc.

### 3.7 Документация и QA
- Обновить `docs/asyncapi/radar_v1.yaml`, добавить Phase 2 расширения.
- Дополнить `RADAR.md` разделом «Phase 2 status», синхронизировать с roadmap.
- CI-гейты: ruff/mypy/pytest уже обязательны; добавить нагрузочные сценарии (`pytest -m radar_load`).

## 4. Приоритизация и спринты
1. **Sprint A (завершён):** TrackStore + расширенные модели + базовые метрики (без UI/guard).
2. **Sprint B (в работе):** IFF режимы, guard-таблица, WorldModel интеграция (метрики `qiki_agent_*`, SAFE_MODE/diagnostic предложения, e2e тест Spoof → FSM).
3. **Sprint C:** Observability 2.0 (JetStream tuning, Prometheus), UI таблица.
4. **Sprint D:** Security scopes/audit, остаточные backlog (docs, нагрузочные тесты).

## 5. Outstanding risks
- Недостаточное покрытие stateful-трекинга тестами → требуется synthetic dataset.
- Потенциальные изменения protobuf (если добавим поля) → контролировать через optional + `buf breaking`.
- Производительность FastStream при высокой плотности детекций → план нагрузочного тестирования с 5× rate.

## 6. Источники и альтернативы
- ROS radar_msgs (detections vs tracks): подтверждает разделение сырых точек и фильтрованных объектов.
- NATS JetStream docs: рекомендации по AckWait/MaxAckPending и мониторингу redeliveries.
- Радартуториал и FAA/IFF briefs: модель Primary vs Secondary radar (цель видна даже при OFF транспондере).
- Open-source решения (Autoware, Apollo) используют фильтры KF/EKF + data association, что подтверждает выбранный трек.
