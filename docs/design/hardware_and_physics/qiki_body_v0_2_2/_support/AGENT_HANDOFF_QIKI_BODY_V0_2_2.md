# QIKI Body v0.2.2 — Agent Handoff

Generated: 2026-06-21T04:25:01+00:00

## 0. Назначение

Этот документ предназначен для Codex, Claude Code, локального агента или человека, который будет вставлять QIKI Body v0.2.2 Documentation Package в репозиторий.

Это handoff-инструкция.

Она не является новым каноном.

Она не является runtime-задачей.

Она не разрешает менять код.

## 1. Главная задача агента

Внести documentation-only package в репозиторий по пути:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

Пакет должен быть внесён без runtime-изменений.

## 2. Используемый архив

Рекомендуемый архив:

`qiki_body_v0_2_2_FULL_REPO_OVERLAY_WITH_JSON.zip`

Если нужен только Markdown:

`qiki_body_v0_2_2_REPO_OVERLAY.zip`

Если JSON добавляется отдельно:

`qiki_body_v0_2_2_JSON_REPO_OVERLAY.zip`

## 3. Что разрешено

Агенту разрешено:

- распаковать overlay в корень репозитория;
- создать директорию `docs/design/hardware_and_physics/qiki_body_v0_2_2/`;
- добавить Markdown-файлы пакета;
- добавить `07_ADR/`;
- добавить `_json/`, если используется JSON companion;
- добавить alignment note в старый GDD;
- обновить документационные индексы;
- проверить `git status --short`;
- подготовить documentation-only commit.

## 4. Что запрещено

Агенту запрещено:

- менять runtime code;
- менять simulation code;
- менять ORION UI;
- менять MFD;
- менять proto;
- менять NATS subjects;
- менять gRPC contracts;
- менять telemetry paths;
- менять generated files;
- добавлять runtime tests;
- менять Docker/runtime config;
- заявлять implemented без evidence;
- заявлять verified без verification;
- подставлять выдуманные массы, нормали, thermal thresholds, Thrust Map или Torque Map;
- добавлять новые модули;
- добавлять новые Terta-exotic технологии;
- превращать JSON companion в runtime schema.

## 5. Stop conditions

Агент должен остановиться, если:

- в `git status --short` появились файлы за пределами `docs/`;
- появились изменения `.py`, `.proto`, `.json` runtime-config, `.yaml`, `.toml`, generated files;
- требуется изменить telemetry path;
- требуется изменить ORION UI;
- требуется добавить тесты поведения;
- старый GDD предлагается удалить;
- в тексте появляется `implemented`, но evidence отсутствует;
- в тексте появляется `verified`, но verification отсутствует;
- нужно ввести новые численные значения без расчёта;
- задача начала превращаться в runtime implementation.

## 6. Expected package path

После распаковки должен существовать путь:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

Внутри должны быть:

- `00_INDEX.md`
- `01_BODY_CANON.md`
- `02_REQUIREMENTS.md`
- `03_ARCHITECTURE_VIEWPOINTS.md`
- `04_CALCULATION_FRAME.md`
- `05_ENGINEERING_RATIONALE.md`
- `06_INTERFACE_CONTROL.md`
- `07_ADR/`
- `08_IMPLEMENTATION_BRIDGE.md`
- `09_ACCEPTANCE_CHECKS.md`
- `10_READER_MANUAL.md`

Если используется JSON:

- `_json/`

## 7. Expected git status

Нормальный результат:

```text
A  docs/design/hardware_and_physics/qiki_body_v0_2_2/...
M  docs/INDEX.md
M  docs/design/game/bot_gdd.md
```

`M docs/INDEX.md` допустимо только если обновляется документационный индекс.

`M docs/design/game/bot_gdd.md` допустимо только если добавляется alignment note.

Плохой результат:

```text
M  q_sim_service/...
M  orion/...
M  proto/...
M  generated/...
M  docker-compose.yml
M  telemetry/...
```

Если такое появилось — остановиться.

## 8. Команды проверки

Из корня репозитория:

```bash
find docs/design/hardware_and_physics/qiki_body_v0_2_2 -type f | sort
git status --short
```

Если используется archive overlay:

```bash
unzip qiki_body_v0_2_2_FULL_REPO_OVERLAY_WITH_JSON.zip
find docs/design/hardware_and_physics/qiki_body_v0_2_2 -type f | sort
git status --short
```

## 9. Commit message

Рекомендуемый commit message:

```text
docs: add QIKI Body v0.2.2 documentation package
```

Если добавлен JSON companion:

```text
docs: add QIKI Body v0.2.2 documentation and JSON companion
```

## 10. После commit

После documentation-only commit можно ставить отдельную задачу:

`RUNTIME_SLICE_0001_PLAN.md`

Но не раньше.

Первый runtime-slice должен быть отдельным patch с отдельным scope, tests и evidence.

## 11. Главная память для агента

Canon is not implemented.

Target-only is not runtime-ready.

Template-only is not runtime schema.

Calculation-required is not calculated.

ACK is not effect confirmation.

ORION is evidence station.

Module requires passport.

Runtime changes are forbidden in this step.
