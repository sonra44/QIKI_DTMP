# TASK-0006 — Faststream bridge truth contract (app.py ~418)

## Как было (UNSAFE)
- Точка: `src/qiki/services/faststream_bridge/app.py:418` в `handle_radar_frame`.
- На любой ошибке обработки кадра (`except Exception`) код создавал synthetic track из пустого кадра:
  - `frame_to_track(RadarFrameModel(..., detections=[]))`
  - и публиковал его через `_track_publisher.publish_track(...)`.
- В результате событие выглядело как обычный publish path, хотя исходный факт был "ошибка/нет данных".

## Почему это подмена truth
- Ошибка обработки входа превращалась в "успешно опубликованный" track.
- Отсутствие/потеря факта не различалось от валидного факта.
- Publish-слой не возвращал честный результат (успех/ошибка), что скрывало проблемы доставки.

## Как стало
- Введён явный контракт `PublishResult(ok, reason, event_id, is_fallback)`.
- Убрана молчаливая подмена в `except`: по умолчанию bridge **дропает** невалид/NoData (`ok=False`, reason=`DROP:*`).
- Fallback-публикация разрешена только при `QIKI_ALLOW_BRIDGE_FALLBACK=true`:
  - результат помечается `is_fallback=true`, reason=`SIMULATED_EVENT`;
  - в headers проставляются truth-маркеры: `x-qiki-truth-state=NO_DATA`, `x-qiki-fallback=true`.
- Добавлена валидация входа и publishable track; invalid payload не публикуется.
- Публикация теперь возвращает bool (успех доставки до брокера/flush), ошибки не маскируются под успех.

## Контракт после изменений
- `OK`: `PublishResult(ok=True, reason="PUBLISHED", event_id=...)`.
- `NO_DATA/UNAVAILABLE/INVALID`: `PublishResult(ok=False, reason=..., event_id=None)` + no publish.
- `FALLBACK` (только явно): `PublishResult(ok=True, reason="SIMULATED_EVENT", is_fallback=True, event_id=...)`.

## Тестовое покрытие
- `test_faststream_bridge_truth_contract.py`:
  - happy path,
  - NoData drop (no publish),
  - invalid payload drop (no publish),
  - fallback allowed (publish + `is_fallback=true` + NO_DATA headers).
