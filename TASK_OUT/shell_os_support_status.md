# shell_os support status

## 1. Runtime role

`shell_os` сегодня не является canonical operator surface и не выглядит как самостоятельный product UI path.

Фактическая роль по коду и compose:

- отдельный optional overlay поверх уже поднятого Phase1 runtime;
- support/diagnostic Textual TUI для локальной host/runtime inspection;
- secondary surface без права конкурировать с ORION V.

Основания:

- canonical operator path зафиксирован за ORION V: `docker-compose.operator.yml` запускает `python main_orion_v.py`, а `README.md`, `docs/INDEX.md`, `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md` описывают ORION как operator console;
- `docker-compose.shell_os.yml` поднимает только сервис `shell-os` отдельным overlay и сам комментарием подаётся как `Shell OS overlay for Phase1 stack`;
- `src/qiki/services/shell_os/main.py` поднимает маленький Textual app с табами `System / Resources / Services / About`, а не operator workflow;
- в `src/qiki/services/shell_os/__init__.py` сервис прямо описан как `host/container observability`.

Итоговая классификация:

- не supported secondary operator UI;
- да, supported diagnostic/support shell;
- не dead legacy surface, потому что entrypoint, overlay и тесты живы;
- но это support-tier surface, а не product/operator-tier surface.

## 2. Inputs / outputs

### Inputs

Реальные входы `shell_os` ограничены local/best-effort probe источниками:

- `NATS_URL` из окружения overlay;
- TCP reachability check до NATS host:port через `socket.create_connection(...)`;
- `docker ps --format ...` через локальный subprocess вызов Docker CLI;
- host/container OS данные через `platform`, `/etc/os-release`, `psutil`;
- CPU/RAM/Swap/Disk/Net counters через `psutil`;
- process-local context: `PID`, `CWD`, текущее UTC время.

`shell_os` не использует:

- QIKI intents/replies subjects;
- ORION procedure/control loop;
- gRPC к `q-sim-service`;
- AsyncAPI/NATS subscriptions;
- publish path в runtime contour.

### Outputs

Единственный реальный output:

- локальный интерактивный Textual TUI в контейнере `qiki-shell-os`.

Отсутствуют:

- публикации в `qiki.*` subjects;
- HTTP endpoints;
- gRPC endpoints;
- ownership над runtime truth;
- operator command ingress.

## 3. Covered scenarios

`shell_os` реально покрывает только support/inspection сценарии:

1. Быстро посмотреть, жив ли контейнерный/host runtime сам по себе:
   OS, kernel, hostname, Python, uptime, PID.
2. Быстро увидеть текущую ресурсную картину контейнера/хоста:
   CPU, load average, RAM, swap, disk, network counters.
3. Проверить, достижим ли NATS по TCP из этого контейнера.
4. Проверить, виден ли Docker CLI и какие контейнеры сейчас running по `docker ps`.
5. Получить truthy status при отсутствии источника:
   bad URL, CLI missing, timeout, exception, unavailable.

Это не operator scenarios, а support scenarios. Конкретно `shell_os` не покрывает:

- наблюдение за world truth как продуктовым cockpit;
- radar/tracks/sensor trust;
- QIKI intent/reply loop;
- legality/trust/consequence cycle;
- control command confirm/execute/effect;
- operator objectives/incidents/procedures/audit overlays.

## 4. Relation to ORION V

Связь с ORION V асимметрична:

- ORION V уже закреплён как canonical operator surface;
- `shell_os` живёт рядом с тем же runtime contour, но не входит в operator canon.

Что уже закрыто ORION V и не должно дублироваться `shell_os`:

- операторский cockpit и navigation chrome;
- telemetry/radar/event rendering для человека;
- QIKI interaction loop;
- legality/trust/consequence presentation;
- operator confirm/command/procedure path;
- operator-facing live runbook path под `tmux`.

Что остаётся допустимым для `shell_os`:

- диагностика среды;
- быстрый host/runtime inspection;
- вспомогательная проверка reachability/containers/resources;
- внутренний support экран, когда нужен лёгкий no-mocks обзор среды, а не работа оператора.

Практическая граница:

- ORION V отвечает за operator interaction with world;
- `shell_os` отвечает только за support visibility into environment/runtime.

## 5. Recommended status label

Рекомендуемый status label:

`Supported diagnostic/support shell overlay (secondary support surface, non-operator, non-canonical)`

Короткая формулировка для future tasking:

- `shell_os` = supported support-tier diagnostic shell;
- не primary UI;
- не competing secondary operator UI;
- не legacy/archive;
- не owner никакой product truth.

Если нужна бинарная развилка из задания, правильнее всего:

- **не** `supported secondary UI` в смысле operator surface;
- **да** `diagnostic/support shell`.

## 6. Drift / ambiguity

### A. Semantic drift: термин “Shell OS” уже занят ORION-доками

Это главный источник двусмысленности.

В репозитории выражение `Shell OS` в active docs в основном означает именно ORION:

- `docs/design/operator_console/ORION_OS_SYSTEM.md`: ORION is the Operator Console TUI (“Shell OS”);
- `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`: ORION = Textual TUI “Shell OS” for the operator;
- validation/checklist/worklog документы тоже используют `ORION Shell OS`.

При этом есть отдельный сервис `src/qiki/services/shell_os/`, который не ORION и не operator console.

Вывод:

- технически сервис `shell_os` существует;
- терминологически имя конфликтует с ORION documentation language;
- без явной подписи его легко принять за primary operator path или за “облегчённый ORION”.

### B. Compose/runtime drift: overlay сидит на external network naming

`docker-compose.shell_os.yml` использует external network:

- `name: qiki_dtmp_qiki-network-phase1`

При этом baseline compose оперирует сервисной сетью `qiki-network-phase1`.

Это не ломает классификацию, но показывает, что `shell_os` подключается как внешняя support-пристройка к уже существующему contour, а не как встроенная часть канонического запуска.

### C. Docs presence drift: почти нет user-facing runbook для shell_os

`README.md`, `docs/INDEX.md`, ORION runbook/quickstart не продвигают `shell_os` как launch path.

Это хорошо для канона, но оставляет ambiguity другого типа:

- сервис присутствует в runtime/compose;
- tasking и audit-документы уже считают его support overlay;
- отдельного короткого статуса до сих пор не было.

### D. Risk of mistaken primary-path reading

Прямых признаков, что `shell_os` сегодня подаётся как canonical primary path, не найдено.

Но риск неправильного чтения остаётся из-за комбинации:

- имя `shell_os`;
- термин `Shell OS` в ORION docs;
- наличие живого compose overlay и test coverage.

Итог по drift:

- drift не в runtime ownership;
- drift в naming/labeling ambiguity.

## 7. Minimal next task candidates

1. Добавить один короткий status note в runtime registry / canon docs:
   `shell_os` = support diagnostic shell, not operator path.
2. Добавить явную формулировку в `docker-compose.shell_os.yml` comment header:
   support diagnostics only, not ORION/operator surface.
3. Пройтись по docs, где встречается термин `Shell OS`, и отделить:
   `ORION Shell OS` от standalone service `shell_os`.
4. Сделать маленький launch/use-case note для support engineers:
   когда поднимать `shell_os`, а когда сразу идти в ORION V.
5. Проверить, нужен ли rename/alias-level cleanup только на naming layer, без изменения runtime.

## Bottom line

`shell_os` больше не должен висеть в неопределённом состоянии.

По фактическому коду и compose это:

- живой;
- поддерживаемый;
- support-tier;
- diagnostic shell overlay;
- не operator canon;
- не competing UI path against ORION V.
