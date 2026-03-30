# signature_changed remaining gap fix

## 1. Где именно был remaining gap

Remaining gap был двухступенчатым внутри live continuity chain между `faststream_bridge` и `ORION/q-core resumed comparison`.

Первая точка:
- `src/qiki/services/faststream_bridge/track_publisher.py`
- bridge публиковал `ce_id` и `Nats-Msg-Id` как bare `track_id`
- для одного и того же live contact это давало JetStream dedupe
- из-за этого ORION cache мог оставаться на старом visible label и не видеть реальную `ON -> SPOOF` mutation того же объекта

Вторая точка:
- `src/qiki/services/operator_console/orion_v/app.py`
- после bridge-fix resumed contour всё ещё жил на q-core `track_id`, а live public cache в ORION индексировался по bridge/public `track_id`
- ORION comparison path пытался читать live cache по q-core identity, не находил entry и падал обратно на старый q-core label
- результатом был `reconfirmed` вместо `signature_changed`

## 2. Почему предыдущих q-core fixes оказалось недостаточно

Предыдущие q-core fixes уже разделили identity и signature внутри q-core, но они не закрывали live stitching между двумя identity spaces:
- q-core contour identity
- bridge/public live track identity

Пока bridge mutation могла быть подавлена dedupe, ORION вообще не видел новый visible signature.
После снятия dedupe ORION всё ещё должен был знать, какой именно public live contact соответствует уже выбранному q-core contour.

## 3. Какие файлы изменены

- `src/qiki/services/faststream_bridge/track_publisher.py`
- `src/qiki/services/faststream_bridge/tests/test_track_publisher_headers.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_qiki_loop.py`

## 4. Что именно исправлено в continuity chain

### Bridge publish continuity

В `track_publisher.py` добавлен `build_event_id(track)`.

Теперь:
- payload continuity по-прежнему держится на стабильном `track.track_id`
- но publish event identity строится как `track_id + event timestamp`
- `ce_id` и `Nats-Msg-Id` больше не гасят последующие same-contact updates

Это сохранило same object continuity и одновременно позволило доставлять visible mutations `ON` и `SPOOF`.

### ORION resumed live binding

В `app.py` добавлена локальная public binding логика:
- `public_track_id`
- `public_track_label`
- поиск live public track отдельным путём от q-core contour id
- сохранение этой binding в active objective и pending action
- resumed comparison теперь использует live public label, но оставляет q-core `track_id` как identity результата

Также сохранён backward-compatible путь:
- если bridge и q-core уже используют один и тот же `track_id`, ORION сначала берёт live track по прямому совпадению q-core id

## 5. Как теперь сохраняется same object identity через `ON -> SPOOF`

Теперь цепочка работает так:

1. `q_sim_service` меняет truth для того же объекта.
2. `faststream_bridge` публикует новые события того же contact без dedupe suppression.
3. ORION видит тот же public live track и обновлённый visible label.
4. resumed contour остаётся на том же q-core `track_id`.
5. comparison path интерпретирует изменение label как visible signature mutation того же объекта.
6. финальная semantics становится `signature_changed`, а не `new target`.

## 6. Какие тесты добавлены/обновлены

Добавлены/обновлены регрессии:

- `src/qiki/services/faststream_bridge/tests/test_track_publisher_headers.py`
  - проверка, что event id теперь не равен bare `track_id`
  - проверка, что для одного и того же `track_id` разные updates дают разные event ids

- `tests/unit/test_orion_v_qiki_loop.py`
  - сохранён сценарий, где same live track id даёт `signature_changed`
  - добавлен сценарий `qcore-track-id != bridge-track-id`, где public binding сохраняет same object continuity и даёт `signature_changed`

Точечный запуск:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  src/qiki/services/faststream_bridge/tests/test_track_publisher_headers.py \
  tests/unit/test_orion_v_qiki_loop.py \
  -k 'signature_changed or public_track_binding'
```

Результат:

```text
..                                                                       [100%]
```

## 7. Результат повторного proof/run

Целевой live precomparison proof:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  env QIKI_OBSERVATION_STYLE=slow QIKI_INITIAL_XPDR_MODE=ON QIKI_RESUME_XPDR_MODE=SPOOF \
  python tools/orion_v_resume_precomparison_probe.py
```

Evidence из `TASK_OUT/signature_changed_remaining_gap_precomparison.log`:

- initial target выбран корректно:
  - public/bridge track: `da490d07-f35b-45a4-ac40-aa04ee98ab8d`
  - initial visible label: `ALLY-0F4107`
- pending action уже несёт обе identity:
  - q-core `observation_track_id`: `ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `public_track_id`: `da490d07-f35b-45a4-ac40-aa04ee98ab8d`
- resumed comparison фиксирует:
  - `previous_track_id = ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `comparison_track_id = ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `previous_label = ALLY-0F4107`
  - `comparison_label = SPOOF-05C30E`
  - `result_candidate = signature_changed`
- final objective:
  - `observation_result_status = signature_changed`
  - `track_id = ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `track_label = SPOOF-05C30E`

## 8. Сработал ли теперь `signature_changed`

Да.

По целевому live precomparison proof `signature_changed` теперь срабатывает корректно на том же resumed contour после `ON -> SPOOF`.

Это означает, что исходный blocker в bridge/q-core continuity chain добит:
- same object identity не теряется
- changed visible signature не создаёт новый target
- финальная semantics соответствует ожидаемой

## 9. Если всё ещё нет — точная новая локализация остаточного gap

Для самого blocker ответ: нет, этот gap больше не воспроизводится в целевом proof.

Но отдельный `tools/orion_v_qiki_observation_objective_seed_smoke.py` всё ещё падает раньше по другому узкому месту:

- `_pick_live_target_designator`
- timeout while waiting for live radar track with public designator in q_core world snapshot

Это не тот же continuity gap между bridge publish и resumed comparison path.
На момент фикса это выглядит как отдельный smoke-harness / world-snapshot target-pick path, который не даёт дойти до уже исправленного финального comparison шага.
