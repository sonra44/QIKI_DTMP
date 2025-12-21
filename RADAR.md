# Radar (v1) — индекс и точки входа

Этот файл — **индекс** по радарному контуру QIKI_DTMP. Источник правды по контрактам: `protos/radar/v1/radar.proto` и правила из `docs/CONTRACT_POLICY.md`.

## Что есть в Phase1

- Поток данных и контейнеры: `docs/ARCHITECTURE.md`.
- Рестарт/проверки: `docs/RESTART_CHECKLIST.md`.
- Дорожная карта Phase 2: `docs/radar_phase2_roadmap.md`.
- Guard rules (YAML): `src/qiki/resources/radar/guard_rules.yaml`.

## NATS subject'ы (Radar v1)

- Кадры (compat union): `qiki.radar.v1.frames`
- Кадры LR: `qiki.radar.v1.frames.lr`
- SR-объекты/кадры: `qiki.radar.v1.tracks.sr`
- Треки (агрегация): `qiki.radar.v1.tracks`

## Где смотреть код

- Protobuf контракт: `protos/radar/v1/radar.proto`
- Pydantic модели: `src/qiki/shared/models/radar.py`
- Конвертеры: `src/qiki/shared/converters/radar_proto_pydantic.py`
- Паблишер симулятора: `src/qiki/services/q_sim_service/radar_publisher.py`
- FastStream обработка/агрегация: `src/qiki/services/faststream_bridge/radar_handlers.py`, `src/qiki/services/faststream_bridge/radar_track_store.py`

## Быстрая проверка (интеграция)

```bash
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/integration/test_radar_flow.py \
  tests/integration/test_radar_tracks_flow.py \
  tests/integration/test_radar_lr_sr_topics.py
docker compose -f docker-compose.phase1.yml down
```

