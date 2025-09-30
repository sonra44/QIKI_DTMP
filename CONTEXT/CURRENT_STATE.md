# CURRENT STATE — Состояние проекта (обновлено 2025-09-27)

## Обзор
- **Техническая готовность:** ~88%
- **Основной стек:** Phase 1 docker-compose (NATS + JetStream, q-sim-service, q-sim-radar, faststream-bridge, qiki-dev, nats-js-init).
- **Radar v1:** реализован end-to-end (protobuf → Pydantic → JetStream → FastStream → интеграционные тесты), базовая LR/SR сегрегация подтверждена docker-тестом.
- **Документация:** обновляется (README, ARCHITECTURE, RESTART_CHECKLIST — актуализированы; остальная документация в процессе).

## Компоненты и статусы

| Компонент | Готовность | Статус / комментарий |
|-----------|------------|-----------------------|
| Protocol Buffers | 100% | Контракты обновлены (`SensorType.RADAR`, `RadarFrame/Track`, `GetRadarFrame`). |
| Generated Stubs + shim | 100% | `generated/`, `radar/`, `*_pb2.py` shim — импорты работают в Docker-образах. |
| Q-Sim Service | 95% | gRPC (`HealthCheck`, `GetSensorData`, `GetRadarFrame`), генерация радара; поддерживает режимы транспондера через `RADAR_TRANSPONDER_MODE`. |
| Q-Sim Radar | 95% | Публикует LR/SR кадры в JetStream, автоматический `RadarRangeBand`, базовая бизнес-логика генерации без физики деталей. |
| FastStream Bridge | 90% | Внедрён TrackStore (α-β фильтр, stateful трекинг), публикует треки/метрики и поля транспондера; guard-правила/визуализация впереди. |
| Q-Core Agent | 80% | Tick-цикл стабилен; потребляет команды/трековые события; визуализация/алерты не реализованы. |
| Testing | 88% | `ruff`, `mypy`, `pytest` зелёные; интеграции радара (`test_radar_flow`, `test_radar_tracks_flow`, `test_radar_lr_sr_topics`) выполняются в `qiki-dev`. Нагрузочные тесты отсутствуют. |
| Documentation | 75% | README/ARCHITECTURE/RESTART_CHECKLIST обновлены; CLAUDE_MEMORY, ROADMAP и др. требуют пересмотра; Stage 0 документирован в `journal/2025-09-21_Stage0-Implementation/task.md`. |
| Observability | 70% | Дополнены метрики WorldModel (`qiki_agent_radar_active_tracks`, `qiki_agent_guard_critical_active`, `qiki_agent_guard_warning_total`) и JetStream лаги; остаётся http-экспорт, алерты и дополнительные JetStream показатели. |
| Configuration Management | 90% | Реализован BotSpec с валидатором и генератором конфигов; интеграция с docker-compose. |
| Event Standardization | 85% | Внедрены CloudEvents-хедеры для всех сообщений; стандартизированы контракты. |
| Audit & Logging | 80% | Создан сервис регистратора с кодами событий 1xx-9xx; структурированное логирование. |
| CI/CD Validation | 75% | Добавлен smoke-тест скрипт; интеграция в CI планируется. |
| UI / Visualization | 10% | Требования из PDF «Разработка визуализации радара» пока не реализованы. |

## Ключевые достижения (сентябрь 2025)
- Radar v1 интегрирован во все уровни: контракты, симулятор, FastStream, тесты.
- 2025-09-27: Реализована база Stage 1 — LR/SR разделение радара, обновлённые протобафы, docker-интеграционный тест `test_radar_lr_sr_topics` зелёный.
- Транспондерные режимы (ON/OFF/SILENT/SPOOF) добавлены в симулятор и треки, поддерживаются тестами.
- Phase 1 docker-compose успешно поднимает весь стек; `nats-js-init` исправлен (2025-09-18) и инициализирует JetStream без ошибок преобразования таймингов.
- Контейнерный прогон `ruff`/`mypy`/`pytest` (2025-09-18) подтверждён — 100 % зелёный результат.
- 2025-09-19: выполнено восстановление Phase 1 после реструктуризации — полный docker-цикл (`up → health → QA → down`) задокументирован, все проверки зелёные.
- 2025-09-19: стек поднят в фоне, контрольные `ruff`/`mypy`/`pytest (radar)` выполнены, логи подтверждают устойчивую работу.
- Исправлены ошибки импортов в контейнерах (добавлены shim-пакеты и обновлён `sys.path`).
- Интеграционные тесты радара выполняются из `qiki-dev-phase1`; базовые проверки качества (`ruff`, `mypy`, `pytest`, `buf lint`) проходят.
- 2025-09-20: WorldModel дедуплицирует guard-ивенты, экспортирует метрики, RuleEngine создаёт SAFE_MODE/diagnostic предложения; проведён боевой запуск Phase 1 с зелёными ruff/mypy/pytest.
- 2025-09-20: Добавлен е2e-тест Spoof → FSM (IDLE→ACTIVE) + диагностический proposal, подтверждён контейнерный прогон `ruff/mypy/pytest` в Phase 1.
- 2025-09-20: Старт Stage 0 — утверждён `docs/stage0_actual_plan.md`, добавлен BotSpec (YAML + валидатор) с покрытием `ruff/mypy/pytest`.
- 2025-09-20: CloudEvents-хедеры внедрены для кадров и треков (`qiki.shared.events`, NATS publishers), добавлен монитор JetStream lag (Prometheus gauge, `JetStreamLagMonitor` с `set_consumer_lag`); тесты/линтеры прогоняются через `docker compose exec qiki-dev`.
- 2025-09-21: ЗАВЕРШЕН Stage 0 — реализован полный набор компонентов: BotSpec с генерацией конфигов, CloudEvents стандартизация, мониторинг JetStream лагов, сервис регистратора событий, smoke-тесты; все компоненты проходят `ruff`/`mypy`/`pytest` в docker-контейнерах.
- 2025-09-28: Стартовал Step-A — подготовлены расширенный BotSpec, конфиги propulsion/power/docking/comms/sensors и геометрия корпуса, roadmap зафиксирован в `docs/STEP_A_ROADMAP.md`.

## Открытые задачи / риски
- **Продвинутая агрегация:** TrackStore реализован (α-β фильтр), далее — IFF слияние, guard-правила и оценка качества.
- **Визуализация / UX:** нет UI, табличного отображения и алертов, описанных в PDF по визуализации радара.
- **Наблюдаемость:** JetStream latency/drop rate и http-экспорт метрик ещё не внедрены; требуется интеграция с Prometheus/OTel.
- **AsyncAPI автоматизация:** спецификация имеется, но публикация/валидация в CI не настроены.
- **Нагрузочные тесты:** нет сценариев с высокой частотой кадров и backpressure.
- **Документация:** необходимо синхронизировать CLAUDE_MEMORY, IMPLEMENTATION_ROADMAP, PROJECT_MAP и смежные отчёты.
- **CI/CD интеграция:** smoke-тесты созданы, но требуется интеграция в автоматический CI pipeline.
- **Step-A реализация:** инфраструктура готова; впереди аллокатор тяги, ограничения HESS и сценарии стыковки/XPDR.

## Следующие шаги
1. Реализовать Step-A фазу 2: аллокатор тяги (QP/NNLS + PWPF) и ограничения HESS с публикацией `EnergyStatus`.
2. Реализовать Step-A фазу 3: стыковка (align→bridge), статусы XPDR и интеграционные тесты.
3. Завершить обновление ключевой документации (CLAUDE_MEMORY, CURRENT_STATE, ROADMAP).
4. Интегрировать smoke-тесты в CI/CD pipeline для автоматической валидации.
5. Запланировать работу над трекингом и визуализацией радара (отдельный backlog).
6. Настроить метрики и нагрузочные проверки для JetStream pipeline.
7. Включить интеграционные тесты радара в CI и автоматизировать AsyncAPI артефакты.
8. Формализовать протокол PRIMARY ACTUAL LONG TERM CONTEXT RECALL (PALTCR) для фиксации критичных шагов восстановления.
