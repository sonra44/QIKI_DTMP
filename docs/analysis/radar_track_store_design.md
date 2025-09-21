# Design Note — Radar TrackStore & Metrics (Phase 2 Sprint A)

**Дата:** 2025-09-17  
**Авторы:** Codex (GPT-5)  
**Связанные документы:** `RADAR.md`, `docs/radar_phase2_roadmap.md`, `journal/2025-09-17_Radar-Integration-Finalize/log.md`

---

## 1. Цель и объём
- Перейти от примитивной функции `frame_to_track` к устойчивому stateful-трекингу в `services/faststream_bridge`.
- Обновить Pydantic-модели радара (detections/tracks) без ломки существующих protobuf/AsyncAPI контрактов.
- Закрыть базовые метрики наблюдаемости (latency, redeliveries) для радара в Phase 2.

## 2. Текущее состояние
- `RadarFrameModel` и `RadarTrackModel` реализованы в `shared/models/radar.py`; поля соответствуют MVP (range/bearing/elev и т.п.).
- FastStream-хендлер `frame_to_track` публикует трек по первой детекции (без фильтрации/ассоциации).  
- JetStream настроен с дедупликацией; метрик и SLA по задержкам нет.  
- Интеграционные тесты: `tests/integration/test_radar_flow.py`, `test_radar_tracks_flow.py` — проверяют только happy-path.

## 3. Требования Sprint A
1. **TrackStore:**
   - Поддержка нескольких одновременных треков, ассоциация детекций на основе окна по дальности/азимуту/доплеру.
   - Фильтр: базовый α-β или EKF в полярных координатах (см. ROS `radar_msgs` рекомендации).
   - Управление жизненным циклом: `age`, `missed_updates`, `quality ∈ [0,1]`.
2. **Модели:**
   - Расширить `RadarTrackModel` optional-полями `position`, `velocity`, `covariance`, `status` (Enum).
   - Добавить `RadarTrackStatusEnum` (`NEW`, `TRACKED`, `LOST`).
   - Все новые поля должны иметь значения по умолчанию / `None`, чтобы protobuf v1 остался валидным.
3. **Метрики & Telemetry:**
   - Prometheus collector в FastStream-бридже (`radar_frame_latency_ms`, `radar_track_count`, `radar_redeliveries_total`).
   - Логирование SLA: p50 ≤ 500 мс, p95 ≤ 1500 мс (сверяется при тестах).
4. **Тесты:**
   - Unit: TrackStore (association, drop, quality), Prometheus exporter (лейблы/значения).
   - Integration: всплеск детекций, пропуск кадров, redelivery.
5. **Документация:**
   - Обновить `RADAR.md` (раздел Phase 2), `docs/asyncapi/radar_v1.yaml` (описание quality/status).
   - Журнал Sprint A в `journal/2025-09-17_Radar-Integration-Finalize/log.md` (новый раздел «Phase 2»).

## 4. Архитектура и взаимодействия
```
NATS JetStream (qiki.radar.v1.frames)
        ↓ FastStream handler (RadarFrameModel)
 TrackStore.update()
        ↓ emits RadarTrackModel[]
  - publishes to qiki.radar.v1.tracks
  - updates metrics exporter
        ↓ FSM / WorldModel (Phase B)
```

### 4.1 TrackStore дизайн
- **Структура:**
  - `tracks: Dict[UUID, TrackState]`
  - `TrackState` содержит фильтр (α-β/EKF), кумулятивную статистику, timestamp, quality.
- **Ассоциация:**
  1. Перевод детекции в декартову систему (`polar_to_cartesian`).
  2. Расчёт расстояния и доплер-расхождения; если < threshold → assign.
  3. Неассоциированные детекции → новые треки.
  4. Треки без обновлений > `miss_limit` → статус `LOST`, удаление.
- **Quality:**
  - Формула: `quality = clamp(1 - miss_count / miss_limit, 0, 1)` * вес по SNR.
  - Для новых треков — 0.5, растёт по мере подтверждений.
- **Фильтр:**
  - MVP: α-β (позиция, скорость).  
  - Расширение: EKF по примеру `radar_msgs` (`position_covariance`, `velocity_covariance`).

### 4.2 Расширение моделей
- `RadarTrackModel` получает поля:
  ```python
  position: Optional[Vector3Model]
  velocity: Optional[Vector3Model]
  position_covariance: Optional[List[float]]
  velocity_covariance: Optional[List[float]]
  status: RadarTrackStatusEnum = RadarTrackStatusEnum.NEW
  age_s: float = 0.0
  miss_count: int = 0
  ```
- Добавить `Vector3Model` (если нет) в `shared/models/core.py` или `radar.py` (ссылаться на существующие).
- Обеспечить `model_config = ConfigDict(extra="forbid", validate_assignment=True)`.

### 4.3 Метрики и наблюдаемость
- Использовать `prometheus_client` (уже в проекте? если нет — добавить зависимость в poetry).
- Метрики:
  - `Histogram`: `radar_frame_latency_ms` (observe в FastStream после обработки).
  - `Gauge`: `radar_track_active_total`.
  - `Counter`: `radar_redeliveries_total` (увеличиваем при FastStream `message.redelivered`).
- Экспозиция: существует ли endpoint? Если нет — добавить HTTP на `faststream_bridge` (aiohttp/fastapi) или pushgateway.

## 5. Пошаговый план реализации
1. **Подготовка моделей:** добавить новые Enum/поля, unit-тесты (`tests/shared/test_radar_models.py`).
2. **TrackStore Core:** создать модуль `services/faststream_bridge/radar_track_store.py` с классом `RadarTrackStore` и тестами (`tests/services/test_radar_track_store.py`).
3. **Интеграция FastStream:** заменить `frame_to_track` → `track_store.process(frame)`; конфигурируем thresholds из env/config.
4. **Prometheus:** реализовать `metrics.py`, подключить к FastStream app (`app.include_router` или встроенный HTTP сервер).
5. **Integration tests:** обновить `tests/integration/test_radar_flow.py` (новые сценарии).
6. **Документация:** правки `RADAR.md`, `docs/asyncapi/radar_v1.yaml`, `journal/...`.
7. **Прогоны:** `ruff --select=E,F src tests`, `mypy src`, `pytest -q tests` + таргетированные сценарии (load).

## 6. Риски и смягчение
- **Сложность фильтра:** α-β выбран как быстрый старт; EKF вынесен в отдельный optional этап.
- **Производительность:** TrackStore должен обрабатывать ≥ 200 детекций/тик. План нагрузочного теста в Sprint C.
- **Совместимость protobuf:** новый JSON может содержать дополнительные поля; клиенты на старых версиях должны игнорировать. Проверим `buf breaking`.
- **Наблюдаемость:** убедиться, что метрики не влияют на производительность (асинхронный экспорт).

## 7. Тестовая стратегия
- Unit: ассоциация (с/без соответствий), miss-count, quality. Используем фиктивные данные с фиксированным seed.
- Property-based (fast-check): генерация случайных детекций → проверка устойчивости TrackStore.
- Integration: расширить docker-compose Phase 1, прогнать `pytest -q tests/integration/test_radar_tracks_flow.py` с новыми кейсами.
- Нагрузочный сценарий (запланировать): скрипт `tools/radar_load_test.py` — имитирует 5× FPS.

## 8. Открытые вопросы / TODO
- Требуется ли отдельный topic для `RadarTrackStatus`? (сейчас остаёмся на `qiki.radar.v1.tracks`).
- Как хранить covariance: flat list (`float[6]` как в ROS) или матрица 3×3? Предлагается flat list для совместимости с ROS.
- Нужно ли синхронизировать TrackStore state в external storage (Redis)? Пока нет, хранение in-memory достаточное (обновим, если акселераторы будут нужны).

## 9. Ссылки
- ROS `radar_msgs` — раздел «Tracks» (дал ссылку в roadmap; подтверждает наличие position/velocity/covariance).
- JetStream consumer tuning — `docs.nats.io/nats-concepts/jetstream/consumers` (AckWait/MaxAckPending).
- Radartutorial — отличие Primary/Secondary radar для IFF (используется в Sprint B).

---

## 10. Definition of Done (Sprint A)
- TrackStore + обновлённые модели задокументированы и покрыты тестами.
- Метрики и SLA работают; Prometheus endpoint доступен.
- Документация/журналы синхронизированы, CI проверки зелёные.
