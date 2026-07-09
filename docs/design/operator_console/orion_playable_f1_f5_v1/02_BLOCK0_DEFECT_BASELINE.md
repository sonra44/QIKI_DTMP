# 02. Блок 0 — обязательный дефектный базис

Статус: target spec. Источник: `docs/dev/AUDIT_2026-07-09_GLOBAL.md`
(сводка 4 аудиторов, срез 64dbe0c). Без Блока 0 критерии P2–P5 из
`01_PLAYABLE_CANON.md` недостижимы: UI-переработки поверх лгущего
контура — запрещённый путь.

## In-scope: HIGH (ломают игровой цикл)

| # | Дефект | Где | Почему блокирует игру | Подход к фиксу |
|---|--------|-----|----------------------|----------------|
| 0.1 | Refresh мозга берёт одно чтение из ротации [LIDAR→RADAR→IMU], очередь=1 → ~2/3 обновлений без радара; после рестарта «0 целей» при живом контакте | `src/qiki/services/q_sim_service/service.py:326-329,478-484`; `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:4330-4336` | убивает «Наблюдение» (P2) | refresh читает до 3 чтений подряд или фоновый ingest |
| 0.2 | WorldModel: кадр любого сенсора сносит ВСЕ треки (глобальный `_frame_derived_track_ids`); sensor_id радара = uuid4 на кадр | `src/qiki/services/q_sim_service/world_model.py:21,67-71`; `service.py:448` | там же (P2) | ключевать множество по `sensor_id`; фиксированный sensor_id радара в симе |
| 0.3 | Гонка `q abort`: `_advance_attach_procedure`/`_attach_procedure_dock` не перепроверяют `proc.status` после await → модуль ставится ПОСЛЕ «прервано», ABORTED перезаписывается | `src/qiki/services/operator_console/orion_v/app.py:3530-3744` | ломает Consequence Confirmation (P3) | guard `proc.status` после каждого await |
| 0.4 | ~25 голых `asyncio.create_task` (вкл. execute подтверждённого действия, `app.py:3160`) — GC может убить таск, исключения теряются | `app.py`, по всему файлу | молчаливая потеря исполнения (P3, P5) | `_bg_tasks` set + done_callback с логом. **Частично уже в рабочем дереве** (`_spawn_task`) — см. Q1 |
| 0.5 | TOCTOU пломбы: shallow-копия parameters при seal; мутация вложенных структур между authorize и effect не ловится | `src/qiki/shared/command_decision.py:92`; `app.py:3176-3200`; `src/qiki/shared/decision_body_bridge.py` | подрывает «одобрено = исполнено» (P3) | deepcopy при seal + повторная сверка digest перед эффектом в bridge. **Частично в рабочем дереве** — см. Q1 |
| 0.6 | FSM enum-коллизия: `FsmState.ERROR_STATE(4)` коэрцится в `FsmStateEnum.PAUSED(4)` — авария читается как пауза | `src/qiki/services/q_core_agent/state/types.py:13-21` vs `src/qiki/shared/models/core.py:33-40`; `fsm_handler.py:91-114` | ложь состояния борта (P1, P3) | выровнять значения или явный маппинг + тест |
| 0.7 | Провал актуаторной команды = «accepted»: `send_actuator_command` глотает RpcError; SAFE-режим не срабатывает | `src/qiki/services/q_core_agent/.../grpc_data_provider.py:199-217` | silent failure — прямой запрет канона (P3) | RpcError → accepted=False → SAFE-путь |
| 0.8 | Блокирующий sync gRPC+HTTP в event loop NATS: `_refresh_agent_snapshot` (timeout 10 c) и warmup (до 8 c) без `to_thread` | `qiki_orion_intents_service.py:4696, 4383-4498` | встаёт весь loop, разрыв NATS — рвёт P5 | `asyncio.to_thread` |
| 0.9 | GetRadarFrame игнорирует состояние сима: контакты от выключенного радара и при паузе | `src/qiki/services/q_sim_service/grpc_server.py:109-119` | пауза/обесточка нечестны (P2) | гейт по sim state |
| 0.10 | RCS не двигает бота: тяга/топливо считаются, position/speed/attitude не интегрируются | `world_model.py:2356-2484` vs `1878-1894` | «движение без последствий» (P4) | интеграция в тике + тест на смещение |
| 0.11 | Константы, неотличимые от измерений: `hull=100.0`, `radiation_usvh=0.0` при «работающем» дозиметре, `temp_external_c=-60` | `world_model.py:1055-1057` | нарушает Truth/Quality contract (P1) | пометка `source=fixture/derived` в контракте поля |

## In-scope: MED (стабильность консоли и честность ленты)

| # | Дефект | Где | Фикс |
|---|--------|-----|------|
| 0.12 | Голая `q` в командном вводе = мгновенный `action_quit`, консоль закрывается | `app.py:1478-1481` (роутер), биндинг `("q","quit")` `app.py:~270` | подсказка + подтверждение выхода; `q` без аргументов в командном режиме ≠ quit |
| 0.13 | `f5`/`f8` отсутствуют в текстовом переключателе уровней | `app.py:1475` (`{"f1","f2","f3","f4","f6","f7"}`) | добавить в множество |
| 0.14 | Сортировка ленты диалога по строке `HH:MM:SSZ` ломается через полночь | `src/.../orion_v/screens/qiki_dialog.py:94` | сортировать по полному timestamp, не по строке времени |
| 0.15 | `_pending_ack_command_id` не сбрасывается → счётчик P завышен навсегда; общие ACK-каналы, `clear()` перетирает чужой pending | `app.py:1975,4492`; `app.py:1974-2018` | сброс после resolve/timeout; изоляция ожиданий по command_id |
| 0.16 | Утечки памяти: `_incident_first_seen` (`app.py:561`), `_latest_radar_tracks`, `DecisionStore` без кэпа (`command_decision.py:179`) | там же | TTL/кэпы |
| 0.17 | Локальные пороги против shared: `modules/power.py:70-76` (30%/24В против 20%/22В — F2 и чипы F1 расходятся); `cockpit.py:1866-1896`; `collector.py:2355`; `operator_state.py:1416` | там же | единый владелец `qiki/shared` (продолжение Среза 0) |

## Явно OUT-OF-SCOPE Блока 0

Перечислено, чтобы исполнитель не расползался (stop condition в handoff §5):

- range_band в gRPC-кадрах (`radar_publisher.py:104-113`) — мина под будущий
  band-сплит, не текущий блокер играбельности.
- Инфра JetStream: `RADAR_SUBJECTS qiki.radar.v1.*` vs `.frames.lr`, Msg-Id
  коллизии — треки консоли идут по `qiki.radar.v1.tracks`, играбельность v1
  не блокируется.
- v2-поля `auth_context`/`command_intent_class`, gateway-security — трек Д1/Д2.
- Наружный NATS-порт (ops/ufw) — трек Д2+.
- Весь LOW-список аудита (мёртвый код, перф `_refresh_ui`, легаси `main.py`).
- Декомпозиция монолита `app.py` (принятый долг, см. `10_RISKS...md` R3).
- MED «станционные ветки мертвы» (`world_model.py:168-191`) — понадобится
  для контекстного действия «станция», но в v1 сцены docked/free_flight/track
  покрываются без него.

## Правило приоритета

Этапы Блока 0 (1–3 в `09_WORK_SEQUENCE.md`) выполняются ДО любых
UI-переработок F1–F5. Порядок внутри Блока 0 повторяет рекомендованный
порядок аудита: «оператор→тело» → «радар» → «честность состояния».
