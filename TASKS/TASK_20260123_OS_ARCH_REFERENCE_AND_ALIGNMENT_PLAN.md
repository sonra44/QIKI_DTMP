# TASK: OS reference PDFs → alignment plan (QIKI/ORION)

Дата: 2026-01-23  
Статус: DRAFT (план работ, без выполнения изменений)  

## Контекст / зачем

Есть локальные референс‑материалы (PDF), которые описывают “QIKI OS” как виртуальную ОС/платформу и предлагают слоистую модель (boot → kernel → services/drivers → modules → UI ORION), а также идеи про модульность/plug‑and‑play устройств и “не эмулировать железо побитно”.

Цель этой задачи — **взять полезные идеи**, но **не превратить их в новый «канон»**, а:

1) Положить материалы в “кабинет” как reference.
2) Сопоставить утверждения из PDF с **фактами** в коде/доках.
3) Сформировать **план обновлений**: что улучшаем, в каком порядке, и как принимаем (evidence).

## Входы (reference)

Эти файлы хранятся как справка (не канон):

- `Cabinet/Reports/OS/QIKI OS_ Архитектура виртуальной операционной системы.pdf`
- `Cabinet/Reports/OS/Ветка · Анализ проекта сборки.pdf`
- `Cabinet/Reports/OS/Жизненный цикл архитектуры виртуальной системы (ORION_QIKI).pdf`
- `Cabinet/Reports/OS/Модульная архитектура хардкорного симулятора_ баланс реализма и гибкости.pdf`

Примечание: во всех PDF в метаданных указан `Author/Creator: ChatGPT Deep Research / ChatGPT` → воспринимать как “design notes / hypothesis”, требующие проверки.

## Факты (быстрая проверка по коду на 2026-01-23)

### BIOS HTTP API (реальность)

Файл: `src/qiki/services/q_bios_service/handlers.py`

- Реально доступны маршруты:
  - `GET /healthz`
  - `GET /bios/status`
  - Остальное → 404

### BIOS fetch policy в ядре (реальность)

Файл: `src/qiki/services/q_core_agent/core/bios_http_client.py`

- `fetch_bios_status()` возвращает значение **без блокировки tick** по умолчанию (cache + background refresh), если `BIOS_CACHE_TTL_SEC > 0`.
- URL берётся из `BIOS_URL` (scheme http/https, host обязателен).

### Tick orchestrator (реальность)

Файл: `src/qiki/services/q_core_agent/core/tick_orchestrator.py`

- Есть фазы (legacy sync путь): update_context → handle_bios → handle_fsm → evaluate_proposals → make_decision.

### Конфиг “железа” для симуляции (реальность)

Файл: `src/qiki/services/q_sim_service/service.py`

- Симуляция читает `bot_config.json` из:
  - `QIKI_BOT_CONFIG_PATH` (если задан)
  - или `src/qiki/services/q_core_agent/config/bot_config.json` (внутри репо/в Docker)
  - иначе использует fallback defaults.

## Что в PDF выглядит как “идея”, но сейчас не подтверждено фактами

1) BIOS API в стиле `get_component_status`, `soft_reboot`, `hot_reload_config` — в текущем HTTP handler этого нет (есть только `/bios/status`).
2) “plug‑and‑play” устройств как динамическая загрузка модулей — сейчас виден конфиг‑driven подход (bot_config.json), но нет явного “module registry / discovery” слоя.
3) “boot layer” как отдельный компонент — в текущем Phase1 это скорее порядок запуска контейнеров/сервисов, чем отдельный загрузчик в коде.

## План обновлений (1 лучший план, последовательный)

### Шаг 1 — Truth table “что правда сейчас” (обязательный)

Сделать документ‑сверку (в репо, как dossier; канон приоритетов не трогаем):

- Сервисы Phase1: фактические compose‑сервисы, их health/ports, роли.
- Контракты данных: какие NATS subjects, какие gRPC методы, какие DTO/proto реально используются.
- BIOS: какие эндпоинты есть, какие нужны, где используется `BIOS_URL`, какая политика кэша.
- ORION: какие экраны показывают “состояние ОС” (boot/ready/safe), откуда берутся данные.

Acceptance / evidence:
- `bash scripts/quality_gate_docker.sh` (Docker-first)
- `docker compose ... ps` + `logs --tail=200` ключевых сервисов
- Serena: ссылки на исходные символы/файлы

Выход: один md‑файл “Truth Table” + список подтверждённых gaps.

### Шаг 2 — Контракт BIOS (минимальный и честный)

Цель: либо (A) реализовать недостающие эндпоинты, либо (B) убрать ложные обещания из docs.

Предлагаемый минимум (если решаем расширять BIOS):
- `GET /bios/status` (уже есть) — **контракт** (schema) + примеры.
- `GET /bios/components/<id>` — статус конкретного порта/устройства.
- `POST /bios/reload` (или `/bios/hot-reload`) — перечитать конфиг и опубликовать обновлённый статус.
- `POST /bios/reboot` — мягкий рестарт внутри контейнера (если это реально нужно/безопасно).

Acceptance / evidence:
- unit‑тесты на handler + smoke в Docker (curl + logs).
- ORION Summary показывает корректный статус BIOS после reload.

### Шаг 3 — Явная модель “модули/устройства” (plug‑and‑play без магии)

Цель: описать интерфейс устройства как “контракт”, чтобы расширение было предсказуемым.

Минимум:
- Единая спецификация устройства (JSON schema / pydantic модель) с обязательными полями: `id`, `type`, `capabilities`, `limits`, `protocol`.
- BIOS валидирует спецификацию и публикует ошибки как часть `bios_status`.
- Q‑Sim/Q‑Core используют один и тот же источник правды по структуре устройства (без дублей DTO).

Acceptance / evidence:
- тесты на валидацию спецификаций
- отсутствие “обхода BIOS” (Rule B: проверка по коду)

### Шаг 4 — ORION как “operator console ОС”

Цель: ORION должен показывать **состояние системы по слоям** и указывать “источник истины”.

Минимум:
- В Summary: `BOOT/READY/SAFE` + “почему” (ошибка BIOS? FSM state? деградация сенсоров?)
- В диагностике: ссылка на NATS subject / gRPC method (как источник данных), чтобы исключить “красивые числа без доказательств”.
- Телеметрия: убрать пустоты/раздувание (то, что ты отмечал про “много места и пустота”) — отдельный UX‑пасс.

Acceptance / evidence:
- прогон по `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md`
- отдельный `...RUN_YYYY-MM-DD.md` с результатами

### Шаг 5 — Качество/инструменты (не ломая базу)

Мы уже сделали quality gate “actionable”. Дальше — улучшение baseline отдельными PR, чтобы не раздувать дифф:
- отдельный PR на `ruff format` repository‑wide (или по подпапкам)
- отдельный PR на постепенное включение mypy (по changed‑files или по модулям)

## Связь с каноном задач

Канон приоритетов: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`  
Этот файл — только dossier/план, а не доска Now/Next.

