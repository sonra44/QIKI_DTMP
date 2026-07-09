# Глобальный код-аудит QIKI_DTMP — 2026-07-09

4 параллельных аудитора (мозг / консоль / симулятор / shared+инфра). Полные
отчёты — в сессии Claude 2026-07-09; здесь сводка с файл:строками для починки.

## КРИТИЧНЫЕ [HIGH]

### R. Радарный контур мозга — след дня, раскрыт полностью
1. **Refresh берёт одно чтение из ротации [LIDAR→RADAR→IMU] с очередью=1**
   (`q_sim_service/service.py:326-329,478-484` + `qiki_orion_intents_service.py:4330-4336`)
   → ~2/3 обновлений мозга приносят не-радар; после рестарта мир пуст → «0 целей»
   при живом контакте на шине. Фикс: refresh читает до 3 чтений подряд / фоновой ingest.
2. **WorldModel: кадр любого сенсора сносит ВСЕ треки** (глобальное множество
   `_frame_derived_track_ids`, `world_model.py:21,67-71`; доказано живым прогоном:
   after empty SR → 0 tracks). Фикс: ключевать по sensor_id + фиксированный
   sensor_id радара в симе (`service.py:448` — сейчас uuid4 на каждый кадр).
3. gRPC-кадры без range_band (UNSPECIFIED; разметка только в NATS-пути,
   `radar_publisher.py:104-113`) — мина под любой будущий band-сплит в мозге.

### Прочие HIGH
- **Гонка `q abort` установки**: `_advance_attach_procedure`/`_attach_procedure_dock`
  не перепроверяют proc.status после await → модуль ставится ПОСЛЕ «прервано»,
  ABORTED перезаписывается (app.py:3530-3744). Фикс: guard после каждого await.
- **~25 голых asyncio.create_task** (вкл. execute подтверждённого действия,
  app.py:3160) — GC может убить, исключения теряются. Фикс: `_bg_tasks` set +
  done_callback с логом.
- **TOCTOU пломбы**: shallow-копия parameters при seal; мутация вложенных структур
  между authorize и effect не ловится (command_decision.py:92 + app.py:3176-3200).
  Фикс: deepcopy при seal + повторная сверка digest перед эффектом в bridge.
- **FSM enum-коллизия**: `FsmState.ERROR_STATE(4)` коэрцится в `FsmStateEnum.PAUSED(4)`
  (state/types.py:13-21 vs shared/models/core.py:33-40, fsm_handler.py:91-114) —
  авария читается как пауза. Фикс: выровнять значения/явный маппинг.
- **Провал актуаторной команды = "accepted"**: send_actuator_command глотает RpcError
  и accepted=False (grpc_data_provider.py:199-217), SAFE-режим не срабатывает.
- **Блокирующий sync gRPC+HTTP в event loop NATS**: _refresh_agent_snapshot
  (timeout 10с) и warmup (до 8с) без to_thread (intents:4696, 4383-4498) —
  встаёт весь loop, риск разрыва NATS.
- **GetRadarFrame игнорирует состояние сима** (grpc_server.py:109-119): контакты
  от выключенного/обесточенного радара и при паузе.
- **RCS не двигает бота**: тяга/топливо считаются, position/speed/attitude
  не интегрируются (world_model.py:2356-2484 vs 1878-1894).
- **Константы, неотличимые от измерений**: temp_external_c=-60 (world_model.py:1057,
  дефолт совпадает), radiation_usvh=0.0 (:1056) при «работающем» дозиметре,
  hull=100.0 (:1055).

## СРЕДНИЕ [MED] — по темам

**Надёжность каналов:** NATS-колбэки консоли глотают исключения в debug
(nats_client.py:159-291; control/qiki вообще без обёртки) · молчаливые
«без ответа» пути в хендлере мозга (intents:4677-4682) · qiki_chat_llm глотает
всё без единого лога (:112-113) · gateway-аудит пишется ДО форварда — исход
недоказуем (handler.py:137) · gateway не отклоняет stream:true.

**Гонки/лайфсайкл:** ACK-каналы общие, clear() перетирает чужой pending
(app.py:1974-2018) · `_pending_ack_command_id` не сбрасывается → счётчик P
завышен навсегда (:1975,4492) · потолок 6с на процедуру → ложный FAILED (:4000-4029)
· snapshot_lock не покрывает warmup (intents:4707+) · предусловия S4/S5 по
вечно-свежему merge-снапшоту (app.py:3236+).

**Утечки памяти:** `_incident_first_seen` (app.py:561), `_latest_radar_tracks`,
DecisionStore без кэпа (command_decision.py:179), `latest_observation_objectives`
без кэпа + подписан на своё эхо (intents:4612+).

**Правда/пороги:** локальные копии порогов в 6 местах против shared
(modules/power.py:70-76 — 30%/24В против 20%/22В — F2 и чипы расходятся;
cockpit.py:1866-1896; collector.py:2355; operator_state.py:1416 — чужая
константа) · NaN проходит в термо (power_thermal_view_model) · 0.0°C
трактуется как «нет данных» (falsy-or) · self_model радар freshness="fresh"
без основания (self_model.py:258) · safe_unknown вместо safe_nominal у
здоровой системы (world_model.py:754).

**Инфра:** RADAR_SUBJECTS `qiki.radar.v1.*` не матчит `.frames.lr` (3 compose +
js_init) — LR/SR мимо JetStream · Msg-Id коллизия LR/SR/union (radar_publisher)
· v2-поля auth_context/command_intent_class — сироты, сервер не проверяет ·
mounts несуществующих путей в operator.yml:44-45 · docker-compose.qcore-intents.yml
без interface-fallback (радар мёртв при запуске этим оверлеем).

**Диалог/лента:** сортировка по строке HH:MM:SSZ ломается через полночь
(qiki_dialog.py:94) · голая `q` в вводе на F5 убивает консоль (app.py:1478) ·
f5/f8 нет в командном переключателе (:1472) · станционные ветки мертвы
(object_type не ставится, world_model.py:168-191 → _best_station_track=None).

## НИЗКИЕ [LOW] — крупными мазками
Мёртвый код: ~2000 строк в симе (мапперы, core-модули), _build_text, недостижимые
ветки · дубли констант/карт page↔subsystem (3 копии) · устаревшие докстринги
(«M1 read-only», «validation: —» не заполняется) · always-green тесты без assert
(patch_chain_import_smoke, radar mouse) · перф: _refresh_ui пересобирает скрытые
экраны, re-parse Markdown всей ленты, 24 query_one на refresh · legacy main.py
сима = вечная заморозка · тик без компенсации дрейфа · speed 0.0 → подмена x1.0.

## Подтверждено чистым
Утечки реального ключа провайдера в логи gateway НЕТ (redact+fingerprint) ·
прямые подмены пломбы ловятся (m5-тесты) · пороги консоль↔shared после Среза 0
без дублей в collector · prove-скрипты не битые · гонок в gRPC-пути сима нет.

## Рекомендуемый порядок починки
1. Блок «оператор→тело»: abort-гонка + голые таски (execute-путь) + TOCTOU пломбы.
2. Блок «радар»: refresh×3 чтения + per-sensor треки + фиксированный sensor_id.
3. Блок «честность состояния»: FSM enum, актуатор accepted, to_thread refresh.
4. Блок «каналы»: обёртки NATS-колбэков, логи LLM, ответ-на-любой-вход хендлера.
5. Блок «пороги/правда»: снести 6 локальных копий порогов, NaN/0.0°C, полночь.
6. Утечки памяти (TTL/кэпы), инфра (RADAR_SUBJECTS, Msg-Id), потом LOW.
