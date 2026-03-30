# Runtime Contour Canon Report

## 1. Supported contours

### Единственный supported contour для дальнейшего tasking

`docker-compose.phase1.yml` + `docker-compose.operator.yml`

Почему это считается каноническим contour:

- `README.md` даёт именно этот launch path: сначала `docker compose -f docker-compose.phase1.yml up -d --build`, затем `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console`.
- `docs/RESTART_CHECKLIST.md` называет `docker-compose.phase1.yml` базовым runtime и отдельно фиксирует live ORION V path через `./scripts/run_orion_v_live.sh`.
- `docs/ORION_V_RUNBOOK.md` и `docs/ORION_V_QUICKSTART.md` используют тот же contour как default/pilot path.
- `docker-compose.phase1.yml` содержит фактический baseline runtime: `nats`, `q-sim-service`, `q-bios-service`, `faststream-bridge`, `q-core-intents`, `registrar`, `qiki-dev`, `nats-js-init`.
- `docker-compose.operator.yml` накладывает поверх baseline канонический operator surface `operator-console` с командой `python main_orion_v.py`.

Практически canonical launch path:

1. `docker compose -f docker-compose.phase1.yml up -d --build`
2. `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
3. Для живой интерактивной сессии ORION V под `tmux`: `./scripts/run_orion_v_live.sh`

Основание:

- compose: `docker-compose.phase1.yml`, `docker-compose.operator.yml`
- scripts: `scripts/run_orion_v_live.sh`
- docs/runbook: `README.md`, `docs/RESTART_CHECKLIST.md`, `docs/ORION_V_RUNBOOK.md`, `docs/ORION_V_QUICKSTART.md`, `docs/INDEX.md`

## 2. Support contours

### Support contour A: `docker-compose.phase1.yml` без operator overlay

Роль:

- headless baseline contour для backend/runtime smoke, integration tests, NATS/JetStream, q-sim, q-bios, registrar, q-core-intents, faststream-bridge
- используется как базовый слой почти всеми smoke/test scripts

Почему это support, а не canonical operator contour:

- сам по себе не поднимает operator surface
- все operator runbook'и требуют overlay `docker-compose.operator.yml`

Основание:

- compose: `docker-compose.phase1.yml`
- scripts: `scripts/run_integration_tests_docker.sh`, `scripts/quality_gate_docker.sh`, `scripts/prove_orion_v_*.sh`

### Support contour B: `docker-compose.phase1.yml` + `docker-compose.shell_os.yml`

Роль:

- вторичный TUI/shell surface, подключаемый к уже существующей phase1 network

Почему это только support:

- существует отдельный overlay `docker-compose.shell_os.yml`
- не фигурирует как default launch path в README/runbook
- не конкурирует с ORION V как canonical operator surface

Ограничение:

- для дальнейшего tasking по operator surface этот contour не должен считаться каноном

Основание:

- compose: `docker-compose.shell_os.yml`
- код: `src/qiki/services/shell_os/main.py`

## 3. Transitional / redundant contours

### `docker-compose.qcore-intents.yml`

Классификация: transitional / redundant

Почему:

- в текущем `docker-compose.phase1.yml` сервис `q-core-intents` уже включён по умолчанию
- в том же `docker-compose.phase1.yml` для `faststream-bridge` уже задан `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`
- отдельный overlay повторяет ту же конфигурацию ownership intents

Вывод:

- исторически это был explicit override для перевода ownership `qiki.intents` на `q-core-intents`
- по текущему compose-коду overlay больше не нужен для default contour

### `docker-compose.operator_orionv.yml`

Классификация: transitional / redundant

Почему:

- `docker-compose.operator.yml` уже запускает ORION V через `command: python main_orion_v.py`
- `docker-compose.operator_orionv.yml` делает только override команды на `python -m qiki.services.operator_console.main_orion_v`
- это не новый contour, а дублирующий способ указать тот же entrypoint

Вывод:

- хранит переходный override-слой
- не нужен как отдельный supported contour

### `docker-compose.yml`

Классификация: transitional / redundant

Почему:

- по составу это старый mixed contour: включает `operator-console`, но не включает `q-bios-service` и `q-core-intents`
- использует старую baseline-логику, где основной stack ещё не разложен на canonical phase1 + overlays
- README/runbook/restart checklist не используют этот файл как primary launch path

Риск drift:

- можно случайно поднять ORION V на неканоническом backend contour без `q-bios-service` и без `q-core-intents`

### `docker-compose.minimal.yml`

Классификация: transitional / redundant

Почему:

- это урезанный baseline без operator surface, без `q-bios-service`, без `q-core-intents`
- в текущих runbook и quickstart он не фигурирует как supported runtime contour
- служит скорее как исторически упрощённый launch slice

## 4. Legacy / archive contours

### `docker-compose.operator_legacy.yml`

Классификация: legacy / archive

Почему:

- файл сам переводит `operator-console` на `python -m qiki.services.operator_console.legacy.main_orion`
- включает `profiles: ["legacy"]`
- `docs/ORION_V_RUNBOOK.md` и `docs/CUTOVER_PLAN.md` прямо называют этот path rollback-only / diagnostics-only
- `src/qiki/services/operator_console/legacy/main_orion.py` печатает `LEGACY MODE — NOT FOR PRODUCTION`

Вывод:

- допустим только как rollback/diagnostics contour
- не должен использоваться как supported contour для новых задач

## 5. Canonical owners

### intents

Owner в default contour: `q-core-intents`

Доказательство:

- `docker-compose.phase1.yml` поднимает сервис `q-core-intents` с:
  - `QIKI_INTENTS_SUBJECT=qiki.intents`
  - `QIKI_RESPONSES_SUBJECT=qiki.responses.qiki`
  - command `python -m qiki.services.q_core_agent.qiki_orion_intents_service`
- тот же `docker-compose.phase1.yml` принудительно уводит `faststream-bridge` с live subject через:
  - `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`
- код `src/qiki/services/q_core_agent/qiki_orion_intents_service.py` реально подписывается на `intents_subject` и публикует в `responses_subject`

Важно:

- в коде `src/qiki/services/faststream_bridge/app.py` до сих пор есть live handler `@broker.subscriber(_QIKI_INTENTS_SUBJECT)` / `@broker.publisher(_QIKI_RESPONSES_SUBJECT)`
- поэтому ownership `qiki.intents` в проекте закреплён не только кодом, а именно compose-конфигурацией default contour

Формальная фиксация:

- default contour owner `qiki.intents` = `q-core-intents`
- `faststream-bridge` сохраняет latent alternate path, но в default contour он отключён

### control ACK

Owner `qiki.responses.control`: `q-sim-service`

Доказательство:

- `src/qiki/services/q_sim_service/grpc_server.py`:
  - подписывается на `COMMANDS_CONTROL`
  - применяет `sim_service.apply_control_command(cmd)`
  - затем публикует response в `RESPONSES_CONTROL`
- tests и runbook ждут ACK именно на `qiki.responses.control`

Формальная фиксация:

- default contour owner `qiki.responses.control` = `q-sim-service`

Важно:

- `faststream-bridge` в текущем коде не содержит фактического control ACK publisher для `qiki.responses.control`
- старые документы, где control ACK приписан bridge, противоречат текущему коду

### operator entrypoint

Canonical operator entrypoint: `src/qiki/services/operator_console/main_orion_v.py`

Доказательство:

- `docker-compose.operator.yml` запускает `command: python main_orion_v.py`
- `src/qiki/services/operator_console/main_orion_v.py` запускает `OrionVApp().run()`
- `src/qiki/services/operator_console/main.py` сам помечен как `LEGACY / ARCHIVE ENTRYPOINT` и явно говорит, что каноническая консоль проекта — `main_orion_v.py`

### supported launch path для ORION V

Supported launch path:

1. поднять `docker-compose.phase1.yml`
2. поднять `operator-console` через `docker-compose.operator.yml`
3. live interactive path под `tmux` выполнять через `./scripts/run_orion_v_live.sh`

Фактический live command:

- `scripts/run_orion_v_live.sh` делает `docker exec -it qiki-operator-console python main_orion_v.py`

Фиксация:

- canonical operator entrypoint = `main_orion_v.py`
- canonical live operator path = `./scripts/run_orion_v_live.sh`

## 6. Conflicts

### compose vs Dockerfile

#### Конфликт A: operator-console default CMD

- `src/qiki/services/operator_console/Dockerfile` по умолчанию имеет `CMD ["python", "main_orion.py"]`
- `docker-compose.operator.yml` поверх этого запускает `python main_orion_v.py`

Вывод:

- Dockerfile default указывает на legacy/non-canonical entrypoint
- compose исправляет это override'ом
- без compose-override контейнер уходит в неканонический запуск

#### Конфликт B: два способа запуска ORION V

- `docker-compose.operator.yml`: `python main_orion_v.py`
- `docker-compose.operator_orionv.yml`: `python -m qiki.services.operator_console.main_orion_v`

Вывод:

- оба пути ведут в ORION V
- но наличие двух override-файлов создаёт лишний альтернативный launch surface

### compose vs docs

#### Конфликт C: owner control ACK

- `docs/ARCHITECTURE.md` описывает `faststream-bridge` как subscriber `qiki.commands.control` и publisher `qiki.responses.control`
- фактический код показывает другой runtime path:
  - `q_sim_service/grpc_server.py` слушает `qiki.commands.control`
  - `q_sim_service/grpc_server.py` публикует `qiki.responses.control`

Фактической runtime-истиной считать код.

#### Конфликт D: root compose vs текущие runbook

- `docker-compose.yml` содержит свой mixed runtime contour с `operator-console`
- текущие docs (`README.md`, `docs/RESTART_CHECKLIST.md`, `docs/ORION_V_RUNBOOK.md`, `docs/ORION_V_QUICKSTART.md`) в качестве operational truth используют `docker-compose.phase1.yml` и overlay `docker-compose.operator.yml`

Вывод:

- `docker-compose.yml` расходится с актуальным runbook и не должен считаться primary contour

#### Конфликт E: legacy interactive command в quickstart

- `docs/ORION_V_QUICKSTART.md` в разделе legacy fallback для interactive checks показывает `docker exec -it qiki-operator-console python main_orion_v.py`
- это противоречит самому legacy override, который переводит контейнер на `qiki.services.operator_console.legacy.main_orion`

Вывод:

- это документный drift; для legacy contour этот interactive snippet нельзя считать надёжным

### docs/comments vs code

#### Конфликт F: ownership intents закреплён compose'ом, а не единой кодовой истиной

- `docs/ORION_V_QUICKSTART.md` говорит, что `q-core-intents` owns `qiki.intents -> qiki.responses.qiki`
- это верно только для default contour
- код `src/qiki/services/faststream_bridge/app.py` всё ещё содержит живой alternate path для тех же subjects

Вывод:

- ownership intents сейчас является runtime-contour decision, а не полностью устранённым code-level dual path

#### Конфликт G: `main.py` архивный, Dockerfile default не синхронизирован

- `src/qiki/services/operator_console/main.py` сам заявляет себя как `LEGACY / ARCHIVE ENTRYPOINT`
- Dockerfile по умолчанию всё ещё ведёт в `main_orion.py`, а не в `main_orion_v.py`

Вывод:

- комментарии и код консоли уже признают ORION V каноном
- базовый image entrypoint отстаёт от этого канона

## 7. Практический вывод

Для всех следующих runtime/tasking решений единственным supported contour нужно считать:

`docker-compose.phase1.yml` + `docker-compose.operator.yml` + live path `./scripts/run_orion_v_live.sh`

Формальная фиксация для дальнейших задач:

- supported contour: только этот
- support contours: `docker-compose.phase1.yml` headless baseline; `docker-compose.phase1.yml + docker-compose.shell_os.yml` как вторичный surface без права считаться operator canon
- transitional / redundant: `docker-compose.qcore-intents.yml`, `docker-compose.operator_orionv.yml`, `docker-compose.yml`, `docker-compose.minimal.yml`
- legacy / archive: `docker-compose.operator_legacy.yml`
- owner `qiki.intents` в default contour: `q-core-intents`
- owner `qiki.responses.control`: `q-sim-service`
- canonical operator entrypoint: `src/qiki/services/operator_console/main_orion_v.py`
- supported ORION V launch path: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console` + `./scripts/run_orion_v_live.sh`

Ограничение для постановки следующих задач:

- нельзя ставить задачи, которые предполагают иной default contour или иной owner `qiki.intents`, пока это не закреплено новым каноном и не подтверждено compose-кодом
