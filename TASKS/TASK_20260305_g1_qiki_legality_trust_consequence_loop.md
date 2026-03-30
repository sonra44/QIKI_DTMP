# TASK: G1 цикл QIKI — legality, trust, consequence

Статус: complete
Дата: 2026-03-05
Ответственные: user + codex

## Контекст

Эта задача реализует канонический следующий этап, зафиксированный в:
- `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`

Эта задача нужна потому, что проект уже сильно продвинут в направлениях:
- ORION,
- telemetry/radar/runtime,
- hardening и доказательств,

но при этом всё ещё недореализован главный игровой цикл, сформулированный в `LOG.MD`:

`Наблюдение -> Запрос/Команда QIKI -> Legality/Trust -> Consequence`

## Цель

Реализовать один законченный, операторски понятный цикл взаимодействия с QIKI внутри ORION V.

## Операторский сценарий

Оператор пытается выполнить действие через текущий командный контур.
До исполнения ORION обязан ясно показать:
- можно ли выполнить действие,
- почему оно допустимо или заблокировано,
- насколько надёжны данные, на которых основано решение,
- что произошло после выполнения или отказа.

## Scope

### В scope

1. Выбрать первый канонический сценарий команды.
2. Добавить показ legality в ORION V.
3. Добавить показ trust для релевантных данных в ORION V.
4. Добавить подтверждение последствия.
5. Добавить таргетные тесты и Docker-proof.

### Вне scope

1. Реализация боя.
2. Реализация миссионных ветвей.
3. Улучшение radar renderer.
4. Полировка UI, не связанная с этим циклом.

## Разделы и движение работ

### Раздел 1: Контракт

Цель:
- выбрать первый канонический сценарий команды и формализовать allowed/blocked/deferred semantics.

Проверки:
- reason codes явные,
- нет скрытого “магического” успеха или провала,
- нет фейковых значений.

Тесты:
- unit tests на исходы команды и маршрутизацию причин.

### Раздел 2: Legality UI

Цель:
- ORION V показывает legality действия и причину блокировки.

Проверки:
- оператор понимает, почему команда заблокирована,
- оператор видит условие будущей допустимости, если оно применимо,
- blocked state не выглядит двусмысленно.

Тесты:
- Textual/unit tests на рендер legality и переходы состояний.

### Раздел 3: Trust UI

Цель:
- ORION V показывает trust/quality данных, на которых основано решение.

Проверки:
- `healthy/degraded/failed/off` различимы,
- `source/confidence/reason` показываются там, где это нужно,
- `N/A` не используется как нормальное игровое состояние.

Тесты:
- unit tests на отображение trust-состояний,
- regression checks на честные fallback-состояния.

### Раздел 4: Подтверждение последствия

Цель:
- после команды или запроса ORION показывает, что произошло.

Проверки:
- позитивное подтверждение видно,
- blocked/deferred/failure исходы видимы,
- телеметрия или состояние подтверждают результат.

Тесты:
- runtime-path tests в ORION V,
- при необходимости integration proof в Docker.

### Раздел 5: Продуктовая валидация

Цель:
- подтвердить, что этап усиливает именно игру, а не только внутренности системы.

Проверки:
- сценарий читается по интерфейсу,
- игроку больше не нужно угадывать legality/trust/consequence,
- результат совпадает с продуктовой истиной из `LOG.MD`.

Тесты:
- acceptance checklist item с before/after заметками.

## Два контура контроля

### Инженерный контроль

- [x] контракты/доки обновлены
- [x] таргетные Docker-тесты зелёные
- [x] lint зелёный по изменённым файлам
- [x] runtime-proof записан
- [x] checkpoint сохранён в память

### Продуктовый контроль

- [x] операторский сценарий записан
- [x] legality понятна
- [x] trust понятен
- [x] consequence понятен
- [x] изменение явно приближает проект к продуктовой модели из `LOG.MD`

## Журнал доказательств

### Петля 0: фиксация канона

Изменённые файлы:
- `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_legality_trust_consequence_loop.md`

Результат:
- канонический следующий этап зафиксирован,
- restart-контекст зафиксирован,
- двухконтурная схема исполнения зафиксирована.

Тесты:
- пока нет; это петля настройки планирования и фиксации контекста.

Риски:
- первый канонический сценарий команды ещё не выбран,
- legality/trust surfaces в ORION пока не реализованы.

## Следующее действие

1. Зафиксирован первый канонический сценарий: `q: dock` получает не тихий `OK`, а явный `blocked` по домену `protocol` с reason code `MVP_NO_AUTO_ACTIONS`.
2. Целевой code path: `src/qiki/services/q_core_agent/qiki_orion_intents_service.py` + `src/qiki/services/operator_console/orion_v/app.py` + `src/qiki/services/operator_console/orion_v/screens/cockpit.py`.
3. Реализовать Раздел 1 и Раздел 2 прежде, чем расширять scope.

## Петля 1: выбран первый сценарий

Сценарий:
- оператор вводит `q: dock`;
- QIKI возвращает `legality=blocked`, `domain=protocol`, `reason_code=MVP_NO_AUTO_ACTIONS`;
- ORION V обязан показать legality, trust и consequence без отправки control-команды.

Зачем этот сценарий выбран первым:
- он опирается на уже существующий MVP-инвариант `no auto-actions`;
- не требует фальшивого эффекта в телеметрии;
- даёт законченный и честный операторский цикл уже в первом срезе.

## Петля 2: data-trust для station approach

Сценарий:
- оператор вводит `q: approach station` или `q: сближение со станцией`;
- QIKI использует `agent.context.world_snapshot["radar_tracks"]` как источник истины по station track;
- при `NO_DATA/STALE/LOW_QUALITY` возвращается не общий `OK`, а явный `deferred` по домену `trust`;
- trust сигнал показывает `off/degraded` с `source=sensor`, `confidence` и точным `reason_code`;
- при хорошем track возвращается `allowed` как оценка допустимости, но automatic execution не запускается.
- при хорошем track consequence возвращается как `confirmed`: подтверждение опирается на текущую радарную телеметрию, а не на отправку control-команды.

Проверки:
- station track выбирается только из `object_type=STATION`;
- no-mocks сохранён: trust строится из реального snapshot, а не из UI;
- consequence явно фиксирует, что control bus не трогался.

Тесты:
- unit tests на `qiki_orion_intents_service` для `NO_DATA`, `LOW_QUALITY`, `TRUSTED`;
- ORION V loop test на help/status строку для `deferred data`;
- cockpit render test на legality/trust/consequence для station approach.

## Петля 3: подтверждаемое исполнение release dock

Сценарий:
- оператор вводит `q: release dock` / `q: undock` / `q: отстыковаться`;
- QIKI использует `agent.context.world_snapshot["docking"]` как источник истины по пристыкованному состоянию;
- при валидном пристыкованном состоянии QIKI возвращает `allowed`, даёт явное действие `sim.dock.release` и помечает consequence как `pending`;
- ORION V показывает оператору следующий шаг `q confirm`, требует отдельное подтверждение, затем отправляет реальную команду на `qiki.commands.control`;
- после `control ack` ORION V ждёт изменения `docking.state` и только после телеметрического подтверждения переводит consequence в `confirmed`.

Проверки:
- действие не отправляется автоматически после одного лишь ответа QIKI;
- подтверждение в ORION V обязательно и отделено от самого запроса;
- путь исполнения использует существующий `COMMANDS_CONTROL`, без нового subject и без моков;
- телеметрический эффект подтверждается по `docking.state` и `docking.connected`.

Тесты:
- unit tests на `qiki_orion_intents_service` для `release dock` в состояниях `allowed` и `already undocked`;
- ORION V loop test на появление `q confirm` и обновление consequence после ack+telemetry;
- cockpit render test на явное отображение confirmable action.
- live Docker-proof внутри `qiki-operator-console`: инжектируется готовый QIKI response, затем ORION V проходит реальный путь `qiki.commands.control -> q_sim_service -> qiki.responses.control -> telemetry transition`, и `docking.state` подтверждает `undocked`.

Постоянный proof-артефакт:
- `tools/orion_v_qiki_release_dock_smoke.py`
- `scripts/prove_orion_v_qiki_release_dock.sh`

Команда доказательства:
- `bash scripts/prove_orion_v_qiki_release_dock.sh`

Ожидаемый результат:
- `OK: orion_v_qiki_release_dock_smoke`
- `FINAL_DOCKING={'enabled': True, 'state': 'undocked', 'connected': False, 'port': 'A', 'ports': ['A', 'B']}`
- `CONSEQUENCE=confirmed`

## Петля 4: station hail через comms + radar truth

Сценарий:
- оператор вводит `q: hail station`, `q: contact station` или `q: связь со станцией`;
- QIKI использует `world_snapshot["radar_tracks"]` для цели и `world_snapshot["comms"]` для готовности канала;
- если канала связи нет или он offline, ответ должен быть не абстрактным, а явным `blocked/resource`;
- если канал degraded, ответ должен быть `deferred/resource`;
- если station track валиден и канал online, QIKI возвращает `allowed/resource` и `consequence=confirmed`, но без автоматической отправки сообщения.

Проверки:
- новый сценарий не создаёт новый control path;
- trust/legality строятся только из существующей телеметрии `radar + comms`;
- ORION V показывает `resource` как отдельный домен причины, а не смешивает его с `trust` или `protocol`.

Тесты:
- unit tests на `qiki_orion_intents_service` для `offline` и `online`;
- ORION V loop test на help/status строку для `blocked/resource`;
- cockpit render test на legality/trust/consequence для comms-сценария.

## Петля 5: docking corridor через zone truth

Сценарий:
- оператор вводит `q: docking corridor`, `q: enter docking corridor` или `q: коридор стыковки`;
- QIKI использует trusted station track и существующий порог `QIKI_DOCKING_TARGET_RANGE_M`;
- если trusted track отсутствует, ответ остаётся `deferred/trust`;
- если station track есть, но дальность выше порога, ответ идёт как `blocked/zone`;
- если дальность внутри порога, QIKI возвращает `allowed/zone` и `consequence=confirmed`, но без автоматического продолжения к стыковке.

Проверки:
- домен `zone` не подменяется ни `trust`, ни `protocol`;
- расчёт опирается только на существующий `range_m` и действующий env-порог;
- ORION V показывает понятное условие будущей допустимости: нужно сократить дальность ниже порога.

Тесты:
- unit tests на `qiki_orion_intents_service` для `too far` и `inside zone`;
- ORION V loop test на help/status строку для `blocked/zone`;
- cockpit render test на legality/trust/consequence для `zone`-сценария.

## Петля 6: attitude hold через IMU off/failed truth

Сценарий:
- оператор вводит `q: stabilize attitude`, `q: attitude hold` или `q: стабилизировать ориентацию`;
- QIKI использует `sensor_plane.imu` и `attitude` из текущего snapshot;
- если IMU выключен или чтение отсутствует, ответ идёт как `deferred/trust` с trust-state `off`;
- если IMU сообщает о сбойном состоянии, ответ идёт как `blocked/trust` с trust-state `failed`;
- если IMU исправен, QIKI возвращает `allowed/trust` и `consequence=confirmed`, но не запускает автоматическую стабилизацию.

Проверки:
- trust-state `off` и `failed` различаются явно;
- расчёт опирается только на существующие поля `sensor_plane.imu` и `attitude`;
- ORION V показывает, что отсутствие IMU и сбой IMU — это разные причины недопустимости.

Тесты:
- unit tests на `qiki_orion_intents_service` для `off`, `failed` и `healthy`;
- ORION V loop test на help/status строку для `blocked/trust` по `IMU_FAILED`;
- cockpit render test на legality/trust/consequence для IMU failure case.

## Сверка этапа на 2026-03-05

### Уже закрыто

- [x] `protocol`: `q: dock`
- [x] `trust` при отсутствии или плохом station track: `q: approach station`
- [x] подтверждаемое исполнение с обязательным подтверждением: `q: release dock`
- [x] `resource`: `q: hail station`
- [x] `zone`: `q: docking corridor`
- [x] `trust` для `off/failed`: `q: stabilize attitude`
- [x] ORION V отображает legality / trust / consequence в едином блоке
- [x] есть постоянный Docker-proof для исполняемого пути `release dock`

### Что подтверждено дополнительной проверкой

- [x] отдельный `degraded` trust-case уже существует и не требует новой петли
- [x] доказательство есть в коде и тестах:
  - `test_build_station_approach_response_marks_low_quality_track_as_degraded`
  - ветка `COMMS_LINK_DEGRADED` в `qiki_orion_intents_service.py`
- [x] итоговый proof/acceptance собран в `TASKS/ARTIFACT_20260305_g1_qiki_loop_acceptance.md`
- [x] финальная PASS/PASS запись по двум контурам контроля исполнения зафиксирована

### Следующее действие

1. Считать `G1-QIKI-001` закрытым.
2. Использовать `TASKS/ARTIFACT_20260305_g1_qiki_loop_acceptance.md` как итоговую точку входа по этому этапу.
3. Выбирать следующий этап уже поверх закрытого базового цикла.
