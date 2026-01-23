# OS PDF review (reference) — 2026-01-23

Контекст: в `Cabinet/Reports/OS/` лежат 4 PDF‑файла с архитектурными тезисами про QIKI OS/ORION.
Эти PDF являются **референсом/конспектом** (не каноном) и содержат смесь (а) пересказа существующих design‑доков и (б) предположений/«как должно быть».

Цель этого обзора: **вникнуть**, отделить *факты из текущего кода* от *проектных идей*, и зафиксировать,
что из PDF можно использовать как ориентиры, а что сейчас не реализовано.

## 1) Какие PDF

1. `QIKI OS_ Архитектура виртуальной операционной системы.pdf`
2. `Жизненный цикл архитектуры виртуальной системы (ORION_QIKI).pdf`
3. `Модульная архитектура хардкорного симулятора_ баланс реализма и гибкости.pdf`
4. `Ветка · Анализ проекта сборки.pdf`

## 2) Основная картина (что полезно и в целом верно концептуально)

В PDF последовательно продвигается одна и та же идея:
- QIKI как **digital twin** + оркестрация через микросервисы.
- Наличие **Boot/BIOS слоя** как “низкоуровневого” источника правды о “железе”.
- Ядро (Q‑Core) как “kernel/brain” с FSM + rule engine/arbiter.
- Симулятор отдельно (Q‑Sim), шина событий отдельно (NATS/JetStream), операторский UI отдельно (ORION).
- Модульность/plug‑and‑play через **контракты** и **версирование интерфейсов**.

Как направление это совпадает с проектной документацией и общей идеологией “docs-as-code”.

## 3) Что в PDF расходится с текущим кодом (важно для спокойствия)

### 3.1 BIOS: `bot_physical_specs.json` и «богатое API»

В PDF (особенно в `Ветка · Анализ проекта сборки.pdf`) утверждается, что BIOS:
- читает `bot_physical_specs.json`,
- имеет API: `get_bios_status`, `get_component_status`, `soft_reboot`, `hot_reload_config`.

Факт по коду (на 2026-01-23):
- Реальный HTTP API BIOS сейчас минимален: `GET /healthz`, `GET /bios/status`.
  См. `src/qiki/services/q_bios_service/handlers.py`.
- Реальный источник данных BIOS сейчас — `bot_config.json` (путь в `BiosConfig.bot_config_path`),
  а не `bot_physical_specs.json`. См. `src/qiki/services/q_bios_service/config.py` и `bios_engine.py`.
- Символов/эндпоинтов `get_component_status`, `soft_reboot`, `hot_reload_config` в коде нет.

Откуда “взялось” в PDF:
- эти пункты присутствуют как **design‑намерение** в `docs/design/q-core-agent/bios_design.md`,
  но текущая реализация BIOS — MVP‑уровня и не реализует этот дизайн целиком.

### 3.2 События `hardware_ready/hardware_error`

В PDF упоминаются события `hardware_ready/hardware_error`.
Факт по коду: BIOS публикует статус на subject `qiki.events.v1.bios_status` (NATS), payload — текущий `BiosStatus`.
Наличие отдельных событий `hardware_ready/hardware_error` как самостоятельных тем сейчас не доказано артефактами кода.

### 3.3 CloudEvents “везде”

PDF декларирует CloudEvents как единый стандарт событий.
Факт по коду:
- CloudEvents реально есть и используется как утилита/заголовки (см. `src/qiki/shared/events/cloudevents.py`,
  также логика в `src/qiki/services/faststream_bridge/app.py`).
- Но это не означает, что **все** сообщения в NATS сейчас реально оформлены как CloudEvents.

## 4) Что из PDF стоит взять в работу как “метод” (без скачка в другой проект)

1) **Контрактность и версионирование**: любые новые интерфейсы/subjects/DTO оформлять как контракт + версия.
2) **Изоляция ошибок**: модули/сервисы обязаны иметь timeout/retry/fallback, чтобы сбой одного не валил цепочку.
3) **Plug-and-play как pipeline документа→конфиг→код**: у нас уже есть design‑описание (см. `bot_physical_specs_design.md`),
   но текущая реализация BIOS фактически работает по `bot_config.json`. Это надо явно синхронизировать (дизайн vs реализация),
   не создавая “второй правды”.
4) **Lifecycle/Boot sequence**: полезен как narrative‑док, но как фактический “канон запуска” принимать только то,
   что подтверждается `docker-compose.*.yml` + кодом + smoke.

## 5) Связанные артефакты в репо (фактические)

- Truth Table: `Cabinet/Reports/TRUTH_TABLE_2026-01-23.md` (факты по текущему Phase1).
- План выравнивания: `TASKS/TASK_20260123_OS_ARCH_REFERENCE_AND_ALIGNMENT_PLAN.md`.
- BIOS (реально): `src/qiki/services/q_bios_service/*`.
- Hardware contracts (дизайн): `docs/design/hardware_and_physics/bot_physical_specs_design.md`.
- BIOS дизайн (намерение): `docs/design/q-core-agent/bios_design.md`.

