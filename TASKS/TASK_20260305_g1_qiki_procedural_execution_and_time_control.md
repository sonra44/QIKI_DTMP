# TASK: G1 цикл QIKI — процедурное исполнение и управление временем

Статус: complete
Дата: 2026-03-05
Ответственные: user + codex

## Контекст

Эта задача является следующим этапом после честного закрытия:
- `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_legality_trust_consequence_loop.md`

Базовый цикл QIKI уже доказан.
Теперь нужно доказать следующий уровень:
- QIKI не просто отвечает,
- QIKI готовит и проводит исполняемую процедуру,
- ORION V показывает её ход,
- время становится частью игры, а не скрытым runtime-флагом.

## Цель

Реализовать первый законченный процедурный цикл QIKI в ORION V с использованием уже существующих:
- `ProcedureEngine`,
- `qiki.commands.control`,
- `qiki.responses.control`,
- `sim.pause/start`.

## Операторский сценарий

Оператор даёт QIKI намерение не на один атомарный шаг, а на короткий исполняемый сценарий.
ORION обязан показать:
- что именно QIKI собирается сделать,
- какие шаги входят в процедуру,
- какой шаг выполняется сейчас,
- как pause/start влияют на цикл,
- чем процедура закончилась.

## Scope

### В scope

1. Один канонический procedural scenario.
2. Plan preview в ORION V.
3. Execution-state в ORION V.
4. Подтверждение шагов через ACK/telemetry.
5. Использование time-control как части сценария.
6. Docker-proof + runtime-proof.

### Вне scope

1. Новый бой.
2. Новый mission generator.
3. Новый radar renderer.
4. Полировка unrelated UI.

## Разделы работ

### Раздел 1: Процедурный контракт

Цель:
- связать намерение QIKI с существующим `ProcedureEngine` без нового обходного контура.

Проверки:
- нет нового subject,
- нет `v2`,
- процедура строится на существующих командах.

Тесты:
- unit tests на routing от QIKI-response к procedure start.

### Раздел 2: Plan Preview

Цель:
- ORION V показывает план до запуска исполнения.

Проверки:
- имя процедуры видно,
- шаги видны,
- оператор понимает, что произойдёт дальше.

Тесты:
- Textual/unit tests на рендер plan preview.

### Раздел 3: Execution-State

Цель:
- ORION V показывает текущий шаг и итог исполнения.

Проверки:
- статусы не молчат,
- timeout/abort/ok различимы,
- оператор видит последнюю проблему.

Тесты:
- unit tests на прогресс/статусы процедуры,
- runtime-path tests на ACK-driven transition.

### Раздел 4: Time Control

Цель:
- pause/start становятся частью явного операционного цикла.

Проверки:
- мир реально встаёт на паузу,
- процедура не маскирует hidden progress,
- возврат в RUNNING виден по sim-state.

Тесты:
- integration proof на `sim.pause/start`,
- ORION V smoke на отображение процедуры и sim-state.

### Раздел 5: Продуктовая валидация

Цель:
- подтвердить, что новый этап действительно приближает игру к `LOG.MD`.

Проверки:
- QIKI стала не только “ответчиком”, но и исполнителем сценария,
- время стало игровой переменной,
- оператор видит логику исполнения, а не угадывает её.

## Первый канонический сценарий

Первым сценарием этого этапа фиксируется:
- `QIKI, подготовь безопасную стабилизацию наблюдения`.

Инженерный MVP-перевод:
- QIKI предлагает процедуру на базе уже существующего `safe_pause_resume` или эквивалентной процедуры,
- ORION показывает её шаги,
- процедура выполняет `sim.pause` и `sim.start`,
- оператор видит подтверждённые переходы состояний.

## Два контура контроля

### Инженерный контроль

- [ ] контракт/доки обновлены
- [ ] таргетные Docker-тесты зелёные
- [ ] runtime-proof зелёный
- [ ] no-v2/no-duplicates соблюдены
- [ ] checkpoint сохранён в память

### Продуктовый контроль

- [ ] оператор видит plan preview
- [ ] оператор видит execution-state
- [ ] время участвует в игровом цикле явно
- [ ] процедура читается как часть QIKI-centric игры
- [ ] изменение приближает проект к `LOG.MD`

## Журнал доказательств

### Петля 0: фиксация нового этапа

Изменённые файлы:
- `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_procedural_execution_and_time_control.md`

Результат:
- новый этап зафиксирован,
- определён первый сценарий,
- восстановление контекста после рестарта задано.

Риски:
- procedural QIKI path ещё не подключён к ORION V,
- plan preview ещё не реализован,
- execution-state пока живёт только в общем procedure status.

## Следующее действие

1. Найти фактический путь `proc list/run/status` в `orion_v/app.py` и точку интеграции с QIKI-response.
2. Реализовать минимальный `plan preview` без создания второго источника истины.
3. Провести первую процедуру через Docker и live runtime-proof.

## Петля 1: safe observation -> procedure preview -> confirmed

Сценарий:
- оператор вводит `q: safe observation` или `q: подготовь безопасную стабилизацию наблюдения`;
- QIKI возвращает `allowed/resource` и procedural action типа `ORION_PROCEDURE` с именем `safe_pause_resume`;
- ORION V извлекает procedural pending-action, показывает `План/Plan` по существующему `ProcedureEngine` и отражает `Execution-State`;
- после `q confirm` ORION V запускает существующую процедуру;
- процедура проходит шаги `sim.pause -> sim.start`;
- итог подтверждается:
  - `procedure status = ok`
  - `sim_state = RUNNING, paused = false`
  - `consequence = confirmed`

Изменённые файлы:
- `src/qiki/shared/models/qiki_chat.py`
- `schemas/asyncapi/qiki.responses.qiki/v1/payload.schema.json`
- `schemas/asyncapi/qiki.responses.qiki/v1/README.md`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_safe_observation_smoke.py`
- `scripts/prove_orion_v_qiki_safe_observation.sh`
- `TASKS/ARTIFACT_20260305_g1_qiki_procedural_execution_runtime_proof.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check ...`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`
- `bash scripts/prove_orion_v_qiki_safe_observation.sh`

Результат:
- procedural action type `ORION_PROCEDURE` работает;
- ORION V показывает plan preview и execution-state;
- первая петля `G1-QIKI-002` подтверждена Docker/unit/live proof.

Следующий шаг:
1. Улучшить operator-facing surface процедуры в ORION V вне одного только QIKI-блока.
2. Выбрать, что важнее на следующей петле:
   - richer plan/execution UX,
   - или второй procedural scenario.

## Петля 2: явная operator-facing поверхность процедуры в F1/F6

Сценарий:
- procedural path уже работал, но его смысл был слишком сосредоточен внутри текстового блока `QIKI`;
- `F1` получил отдельную секцию `Процедура/Procedure`, где видны:
  - подготовленная процедура,
  - следующий операторский шаг,
  - `Plan/Preview`,
  - `Execution`,
  - текущее `sim_state/paused/speed`;
- в quick actions добавлен прямой переход `Процедуры/Procedures -> F6`, который переводит оператора сразу в procedural audit journal.

Изменённые файлы:
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tests/unit/test_orion_v_app_incidents.py`
- `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_procedural_execution_and_time_control.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/screens/cockpit.py src/qiki/services/operator_console/orion_v/app.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_qiki_loop.py`

Результат:
- operator-facing слой процедуры больше не прячется только в `QIKI`;
- `F1` показывает procedural state как состояние системы;
- `F6` стал прямой точкой входа в журнал процедур с одного клика;
- цикл `G1-QIKI-002` стал ближе к модели `plan -> execution -> time -> consequence`.

Следующий шаг:
1. Либо собрать отдельный runtime-proof именно для нового procedural surface `F1/F6`.
2. Либо брать второй procedural scenario на уже укреплённом operator-facing контуре.

## Петля 3: live runtime-proof procedural surface `F1/F6`

Сценарий:
- procedural surface из петли 2 должен быть доказан не только unit/headless-тестами;
- нужен отдельный live proof, который показывает:
  - секцию `Процедура/Procedure` в `F1`,
  - появление `Execution` после запуска процедуры,
  - переход `Процедуры/Procedures -> F6`,
  - procedural audit trail с фильтром `procedures`.

Изменённые файлы:
- `tools/orion_v_qiki_procedure_surface_smoke.py`
- `scripts/prove_orion_v_qiki_procedure_surface.sh`
- `TASKS/ARTIFACT_20260305_g1_qiki_procedure_surface_runtime_proof.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check tools/orion_v_qiki_procedure_surface_smoke.py`
- `bash scripts/prove_orion_v_qiki_procedure_surface.sh`

Результат:
- live proof зелёный;
- `F1` показывает `Процедура/Procedure` как отдельную системную секцию;
- `Execution` виден после реального procedural run;
- кнопка `Процедуры/Procedures` переводит в `F6`;
- `F6` открывается с `audit filter=procedures` и реальным журналом procedural событий.

Следующий шаг:
1. Выбрать второй procedural scenario.
2. Не возвращаться к уже доказанному `F1/F6` unless появится конкретный дефект.

## Петля 4: slow observation -> reduced-speed running

Сценарий:
- оператор запрашивает `slow observation` / `подготовь медленное наблюдение`;
- QIKI готовит новую процедуру `safe_pause_slow_resume`;
- процедура:
  - ставит симуляцию на паузу,
  - затем возвращает её в `RUNNING` на скорости `x0.25`;
- ORION V показывает параметризованный шаг:
  - `sim.start speed=0.25 -> ack sim.start`;
- consequence подтверждается живой телеметрией `sim_state.speed=0.25`.

Изменённые файлы:
- `config/orion_v/procedures/safe_pause_slow_resume.json`
- `src/qiki/services/operator_console/orion_v/procedure_engine.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_procedure_engine.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_slow_observation_smoke.py`
- `scripts/prove_orion_v_qiki_slow_observation.sh`
- `TASKS/ARTIFACT_20260306_g1_qiki_slow_observation_runtime_proof.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check ...`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_procedure_engine.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`
- `bash scripts/prove_orion_v_qiki_slow_observation.sh`

Результат:
- второй procedural scenario зелёный;
- `ProcedureEngine` поддерживает параметры шагов без нового transport;
- ORION V честно показывает time-control scenario с пониженной скоростью;
- `sim_state.speed=0.25` подтверждён live proof.

Следующий шаг:
1. Сделать короткий аудит покрытия этапа `G1-QIKI-002`: что уже закрыто, а что ещё реально нужно.
2. Не плодить третий scenario автоматически, пока не станет ясно, что именно осталось незакрытым по канону.

## Петля 5: acceptance audit и закрытие этапа

Сценарий:
- после четырёх зелёных петель этап нельзя было закрывать автоматически;
- выполнен отдельный аудит покрытия `G1-QIKI-002` против канона и DoD;
- повторно прогнаны таргетные unit/runtime proofs;
- найден реальный дефект: procedural consequence мог становиться `confirmed` раньше, чем телеметрия подтверждала reduced-speed effect `speed=0.25`;
- дефект исправлен в `orion_v/app.py`, добавлен unit-тест на ожидание телеметрического эффекта;
- после повторного прогона acceptance переведён в `PASS/PASS`.

Изменённые файлы:
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `TASKS/ARTIFACT_20260306_g1_qiki_procedural_execution_acceptance.md`
- `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_procedural_execution_and_time_control.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_procedure_engine.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/app.py tests/unit/test_orion_v_qiki_loop.py`
- `bash scripts/prove_orion_v_qiki_safe_observation.sh`
- `bash scripts/prove_orion_v_qiki_procedure_surface.sh`
- `bash scripts/prove_orion_v_qiki_slow_observation.sh`

Результат:
- stage coverage закрыт честно;
- `confirmed` теперь зависит от наблюдаемого procedural telemetry effect;
- этап `G1-QIKI-002` переведён в `complete`;
- следующий правильный шаг: replan нового продуктового этапа, а не третий procedural scenario.
