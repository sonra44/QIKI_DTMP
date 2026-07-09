# TASK: ORION V — план приведения консоли в играбельный вид (F1–F5)

**ID:** TASK_20260709_ORION_V_F1_F5_PLAYABLE_PLAN
**Status:** proposed
**Owner:** Claude (анализ по заказу оператора)
**Date created:** 2026-07-09

## Goal

Превратить ORION V из «кликабельного дашборда» в играбельную консоль: действия оператора на F1–F5 публикуют реальные команды, возвращают ACK и дают наблюдаемый эффект в симуляции; тактическая картина (радар) питается настоящими объектами мира, а не консервированной сценой.

## Анализ текущего состояния (сводка)

Командный путь **уже работает end-to-end** и покрыт тестами:
`_publish_sim_command` → `qiki.commands.control` → `apply_control_command`
(sim.start/pause/stop/reset, power.dock/nbl, sim.dock.engage/release, sim.rcs.stop/fire, sim.xpdr.mode)
→ ACK на `qiki.responses.control` → `_wait_for_ack`
(контракт: `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`).
Играбельность = переиспользовать этот путь из F1/F5, а не строить новый.

Разрывы по экранам:

| Экран | Сейчас | Главный разрыв |
|---|---|---|
| **F1 Кокпит** | телеметрия живая; «первый играбельный цикл» (`cockpit_playable_view_model.py`) | цикл **локальный**: не публикует runtime-команды (`app.py:858`, `runtime_claim_status="local_ui_loop_no_runtime_command"`), нет ACK/эффекта |
| **F2 Системы** | 8 карточек от `HardwareViewModel` | локальные копии порогов питания (`modules/power.py:70-76`, `cockpit.py:1866-1896`: 30%/24В против shared-канона 20%/22В) → F1/F2/чипы противоречат |
| **F3 Глубокий анализ** | инциденты + SAFE-MODE + лента (84 строки) | квитирование не является реальным действием; фильтров нет |
| **F4 Консоль** | пассивное зеркало `_console_history` (24 записи) | нет пар команда→ACK, нет фильтра |
| **F5 QIKI/Диалог** | реальный чат `qiki.intents` → `qiki.responses.qiki` | превью решения — прочерки-заглушки (`app.py:2369`); сортировка ленты по `HH:MM:SS` ломается через полночь (`qiki_dialog.py:94`); голая `q` **роняет консоль** (`app.py:1478-1481`) |
| **Мир (q-sim)** | телеметрия реальная | радар — консервированная сцена из 2 фиксированных детекций (`q_sim_service/service.py:392-452`), в `WorldModel` нет объектов-целей |

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что должно стать понятнее/играбельнее в ORION: действие в кокпите (Burn/Brake/Расстыковка) видимо проходит цикл «отправлено → ACK → эффект в телеметрии»; радар показывает реальные треки с риском сближения или честное «эфир чист»; кандидат QIKI проходит validation→publish→ack→effect с реальными значениями стадий.
- Ограничение: один цикл = один новый операционный сценарий → **каждая фаза ниже оформляется отдельной TASK** при взятии в работу.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console
# F1: действие сцены → тикер: отправлено → ACK applied → эффект (скорость/док-статус)
# F5: q: <вопрос> → кандидат → q confirm → стадии превью заполняются реальными значениями
```

## Before / After

- Before: F1-цикл локальный (без команд/ACK/эффекта); радар — 2 захардкоженные детекции; превью решения F5 — прочерки; `q` на F5 завершает приложение; пороги питания расходятся между F1/F2/чипами.
- After: критерии «играбельно» по экранам (см. таблицу ниже) выполнены.

## Критерии «играбельно» по экранам

| Экран | Играбельно = |
|---|---|
| **F1** | softkeys публикуют реальные команды `qiki.commands.control`, ACK и эффект видны; чип PWR несёт cap-гейт `БУСТ/ДЕРЖ/СТАБ`; страница РАДАР показывает реальные треки (пеленг/дальность/скорость/IFF/качество/риск) или честное «эфир чист» |
| **F2** | пороги едины с shared-каноном; карточки не противоречат чипам F1; честные «Нет данных» остаются |
| **F3** | квитирование инцидента — реальное действие с аудитом; фильтры ленты по категории/подсистеме |
| **F4** | история команд+ACK с фильтрацией, глубина > 24 записей |
| **F5** | превью решения показывает реальные стадии validation/publish/ack/effect; цикл предложение→подтверждение→исполнение→эффект замкнут; ввод не роняет приложение |

## Plan (steps) — фазы

### Фаза 0 — Геймбрейкеры (S)

Файлы: `orion_v/app.py`, `orion_v/screens/qiki_dialog.py`, `orion_v/modules/power.py`, `orion_v/screens/cockpit.py`, `orion_v/hardware_view_model/collector.py`, `orion_v/operator_state.py`

1. Голая `q` на F5 = обычный текст в диалог, а не `action_quit` (`app.py:1478-1481`); выход — только Ctrl+Q/явная команда.
2. F5/F8 добавить в командный переключатель уровней (`app.py:1475`).
3. Сортировка ленты F5 по полному timestamp/монотонному счётчику, не по строке `HH:MM:SS` (`qiki_dialog.py:94`).
4. ACK-канал: сброс `_pending_ack_command_id` после завершения ожидания; изоляция каналов, чтобы `clear()` не перетирал чужой pending (`app.py:1974-2018, 4492`).
5. Унификация порогов питания: единственный источник в `qiki.shared`, удалить локальные копии (6 мест: `modules/power.py:70-76`, `cockpit.py:1866-1896`, `collector.py:2355`, `operator_state.py:1416` и др.). Синхронизировать со «SelfModel Срез 0» (единый владелец порогов уже начат в `qiki/shared`).
6. Косметика честности: обновить устаревшие докстринги «M1 read-only» (`qiki_dialog.py:1-11`), удалить мёртвый `_build_text` (`qiki_dialog.py:241`).

### Фаза 1 — F1: реальные действия с ACK и эффектом (M)

Файлы: `orion_v/app.py` (`action_cockpit_playable_apply` ~858), `orion_v/cockpit_playable_view_model.py`, `orion_v/screens/cockpit.py`

1. Ряд softkeys №3 → **контекстные действия сцены** (G-D из `F1_GAME_FIELD_REWORK.md`): docked → «Расстыковка/Зарядка/Диагностика» (`sim.dock.release`, `power.dock.on/off`); free_flight → «Burn/Brake/Удержание» (`sim.rcs.fire`, `sim.rcs.stop`); XPDR-режим (`sim.xpdr.mode`).
2. Каждое действие — через существующий путь `_publish_sim_command` + `_wait_for_ack`; убрать дисклеймер `local_ui_loop_no_runtime_command` там, где команда стала настоящей; статус в тикере: `отправлено → ACK applied/rejected → эффект в телеметрии`.
3. Чип PWR: cap-гейт из `supercap_soc_pct` с порогами `T_boost=0.6 / T_hold=0.3` (данные уже в телеметрии, гэп G3): `PWR | OK | bat 93% · cap 70% ▸БУСТ`.
4. Декомпрессия обучалки (G-A): убрать чек-листы разработчика («ПАНЕЛИ 6/6», дубли), «Краткие факты» — только непустые строки, скрывать мёртвые кнопки инцидентов при пустоте.

### Фаза 2 — Настоящий мир и радар (L)

Файлы: `q_sim_service/world_model.py` (или соседний модуль мира), `q_sim_service/service.py` (`generate_radar_frame`), `faststream_bridge` (гвард-события), `orion_v/screens/cockpit.py` (страница РАДАР)

1. **WorldModel: объекты-цели** — сим-truth сущности с позицией/скоростью/RCS/транспондером; стартовая сцена из конфига (`config/`), интеграция в тик мира. Никаких UI-моков: всё, что рисуется, живёт в симуляции.
2. `generate_radar_frame`: детекции из реальных объектов (дальность/пеленг/элевация/vr от относительной кинематики; snr от дальности и RCS), убрать захардкоженную сцену `service.py:392-452`.
3. Страница РАДАР на F1 (G-B): треки со всеми реальными полями `RadarTrackModel` (сейчас ~5 из ~20), производный риск сближения из range/vr (G5/TCAS), пусто → `эфир чист | охват 360° | режим: НАВИГАЦИЯ`.
4. Включить `RADAR_GUARD_EVENTS_ENABLED=1` в `docker-compose.phase1.yml` → гвард-алерты питают инциденты F3.

### Фаза 3 — F5: честный жизненный цикл решения QIKI (M)

Файлы: `orion_v/app.py` (`_build_qiki_decision_preview_lines` ~2369, `_confirm_qiki_pending_action`, `_authorize_pending_against_seal` ~3898), `orion_v/screens/qiki_dialog.py`

1. Превью решения — реальные стадии: `validation` — из валидации кандидата; `publish` — факт публикации в `qiki.commands.control`; `ack` — из `_wait_for_ack`; `effect` — из `_wait_for_qiki_effect`. Прочерк — только для честно не наступившей стадии.
2. Голос QIKI (G-C): диалоговая лента `QIKI ▸` как основной вид, сырые коды LEGALITY/TRUST — в tooltip/F6.
3. Закрыть аудит-баги пути подтверждения: гонка `q abort` при attach (`app.py:3530-3744`); TOCTOU на seal — глубокая копия `parameters` (`command_decision.py:92` + `app.py:3176-3200`). **Примечание:** частично уже исправлено в рабочей ветке `runtime/attach-seed-critical-remediation` (deepcopy пломбы, `_spawn_task`) — сверить перед взятием в работу.

### Фаза 4 — F2/F3/F4: опорные экраны (M)

Файлы: `orion_v/screens/systems.py`, `orion_v/screens/deep_dive.py`, `orion_v/screens/raw.py`, `orion_v/app.py`

1. **F2**: перейти на shared-пороги (из Фазы 0); карточка body_structure — честная пометка «локальная самопроверка» остаётся до появления NATS-источника (no-mocks).
2. **F3**: квитирование инцидента публикует событие в `OPERATOR_INCIDENTS` и меняет статус в `BoundedEventsStore.active_incidents()`; фильтры ленты по категории/подсистеме (store уже умеет `query(...)`).
3. **F4**: расширить `_console_history` (deque до ~200), показать пары команда→ACK со статусом, простой фильтр (команды/ответы/события). Тренды/replay **не делаем** — источника нет (no-mocks, `REAL_DATA_MATRIX.md`).

### Фаза 5 — Стабильность и производительность (M)

Файлы: `orion_v/app.py`, `orion_v/clients/nats_client.py`, `orion_v/command_decision.py`

1. ~25 голых `asyncio.create_task` → существующий `_spawn_task`/`_bg_tasks` (критично: путь исполнения подтверждённого действия `app.py:3160`). **Примечание:** частично уже сделано в ветке `runtime/attach-seed-critical-remediation`.
2. Ограничить рост памяти: `_incident_first_seen` (`app.py:561`), `_latest_radar_tracks`, `DecisionStore` (`command_decision.py:179`) — bounded/TTL.
3. NATS-колбэки: не глотать исключения (`nats_client.py:159-291`), обёртка для control/qiki-путей.
4. `_refresh_ui`: не перерисовывать скрытые экраны каждый тик (сейчас ~24 `query_one`/тик + полный ре-парс Markdown-ленты F5).

Рекомендуемый порядок: **0 → 1 → 2 → 3 → 4 → 5** (ядро игры F1+F5 — раньше опорных экранов; Фаза 5 может идти параллельно любой начиная с Фазы 1).

## Переиспользуемое (не писать заново)

- `_publish_sim_command` / `_wait_for_ack` / `_wait_for_qiki_effect` (`orion_v/app.py:1971+`) — весь командный контур.
- `HardwareCollector`/`HardwareViewModel` — источник карточек F2 и блоков F1.
- `BoundedEventsStore` (`query`, `active_incidents`) — F3/F6/фильтры.
- `apply_control_command` + `_build_control_response_payload` (q-sim) — расширять список команд здесь же, по контракту `SIMULATION_CONTROL_CONTRACT.md`.

## Impact Metric

- Метрика: число экранов F1–F5, удовлетворяющих критериям «играбельно» (таблица выше); число действий F1, дающих реальный цикл команда→ACK→эффект.
- Baseline: 0 экранов; 0 действий (цикл F1 локальный).
- Target: 5 экранов; ≥3 контекстных действия сцены с реальным циклом.
- Actual (после внедрения): —

## Scope / Non-goals

- In scope: фазы 0–5 выше; объекты-цели в WorldModel как sim-truth.
- Out of scope: тренды/графики, лимит-монитор, replay/история (нет источника — no-mocks, `REAL_DATA_MATRIX.md`); хардкор-мета SYNC (G-E — отдельный ADR); F6–F8; переработка legacy-консолей (`main_orion.py` и пр. — ARCHIVE по `00_CONSOLE_MAP.md`).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/F1_GAME_FIELD_REWORK.md` (фазы G-A…G-F — этот план реализует G-A/G-B/G-C/G-D частично)
  - `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
  - `docs/operator_console/REAL_DATA_MATRIX.md` (no-mocks policy)
  - `docs/dev/AUDIT_2026-07-09_GLOBAL.md` (источник дефектов Фаз 0/3/5)
  - `docs/design/operator_console/F5_QIKI_DIALOG_SYSTEM_DESIGN.md`, `F5V2_CONSOLE_UX_DESIGN.md`
  - `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
  - `src/qiki/services/operator_console/00_CONSOLE_MAP.md`

## Definition of Done (DoD)

- [ ] Docker-first checks passed (commands + outputs recorded)
- [ ] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (if behavior changed)
- [ ] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [ ] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean (`git status --porcelain` is expected)

## Верификация (по фазам)

1. **Юнит/интеграция**: `bash scripts/quality_gate_docker.sh`; целевые — `tests/integration/test_control_ack_envelope.py`, `q_sim_service/tests/test_control_responses.py`; новые тесты: контекстные действия F1 (publish+ACK), радарные детекции из объектов мира, стадии превью F5, сортировка ленты через полночь, `q` на F5 не завершает приложение.
2. **Живой прогон**: команды из `Reproduction Command`.
3. **Ручной чек**: F1 — действие → ACK → эффект, cap-гейт в PWR, треки мира на РАДАР; F2 — пороги совпадают с чипами F1; F3 — гвард-алерт порождает инцидент, квитирование пишет аудит; F4 — пары команда→ACK и фильтр; F5 — `q: <текст>` → кандидат → `q confirm` → стадии реальными значениями, голая `q` не роняет консоль.

## Notes / Risks

- В рабочем дереве есть незакоммиченные правки ветки `runtime/attach-seed-critical-remediation` (deepcopy пломбы TOCTOU, `_spawn_task` вместо голых `create_task`, AGENTS.md) — пересекаются с Фазами 3/5; перед началом работ сверить/закоммитить, чтобы не потерять и не задублировать.
- Фаза 2 меняет контракт радарного продьюсера — согласовать с `RADAR_VISUALIZATION_RFC.md` и ADR радар-стратегии; поведение при пустом мире должно остаться честным («эфир чист», не пустой экран-ошибка).
- Пороговая унификация (Фаза 0.5) может изменить severity карточек F2 — это ожидаемое исправление правды, зафиксировать в evidence.

## Next

1) Взять Фазу 0 отдельной TASK (`TASK_YYYYMMDD_orion_v_f1f5_phase0_gamebreakers.md`) и выполнить цикл дизайн→правка→тест→живой кадр→коммит.
2) Далее фазы 1–5 по порядку, каждая — отдельная TASK со своим Reproduction Command и Evidence.
