# QIKI Body v0.2.2 — Repo Patch Checklist

Generated: 2026-06-21T04:25:01+00:00

## 0. Назначение

Короткий практический чеклист для вставки QIKI Body v0.2.2 в репозиторий.

Это не новый канон.

Это не runtime patch.

Это быстрый контроль перед commit.

## 1. Архив

Использовать один из архивов:

- `qiki_body_v0_2_2_REPO_OVERLAY.zip` — Markdown only.
- `qiki_body_v0_2_2_JSON_REPO_OVERLAY.zip` — JSON companion only.
- `qiki_body_v0_2_2_FULL_REPO_OVERLAY_WITH_JSON.zip` — Markdown + JSON.

## 2. Распаковка

Из корня репозитория:

```bash
unzip qiki_body_v0_2_2_FULL_REPO_OVERLAY_WITH_JSON.zip
```

Или Markdown only:

```bash
unzip qiki_body_v0_2_2_REPO_OVERLAY.zip
```

## 3. Проверить файлы

```bash
find docs/design/hardware_and_physics/qiki_body_v0_2_2 -type f | sort
```

Ожидается минимум:

```text
docs/design/hardware_and_physics/qiki_body_v0_2_2/00_INDEX.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/01_BODY_CANON.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/02_REQUIREMENTS.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/03_ARCHITECTURE_VIEWPOINTS.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/04_CALCULATION_FRAME.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/05_ENGINEERING_RATIONALE.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/06_INTERFACE_CONTROL.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/07_ADR/
docs/design/hardware_and_physics/qiki_body_v0_2_2/08_IMPLEMENTATION_BRIDGE.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/09_ACCEPTANCE_CHECKS.md
docs/design/hardware_and_physics/qiki_body_v0_2_2/10_READER_MANUAL.md
```

## 4. Проверить git status

```bash
git status --short
```

Допустимо:

```text
A  docs/design/hardware_and_physics/qiki_body_v0_2_2/...
```

Допустимо при ручном обновлении индекса:

```text
M  docs/INDEX.md
```

Допустимо при alignment note:

```text
M  docs/design/game/bot_gdd.md
```

Недопустимо:

```text
M  q_sim_service/...
M  orion/...
M  proto/...
M  generated/...
M  docker-compose.yml
M  telemetry/...
```

## 5. Проверка no-runtime-diff

Не должно быть изменений в:

- Python runtime files;
- simulation files;
- ORION UI;
- MFD;
- proto;
- NATS;
- gRPC;
- telemetry paths;
- generated files;
- Docker/runtime config;
- runtime tests.

Если такие изменения появились — остановиться.

## 6. Alignment note

Если есть старый bot GDD, добавить в начало или рядом:

```md
> Alignment note — QIKI Body v0.2.2
>
> QIKI Body v0.2.2 is the current target documentation canon for body hardware / physics / machine-body constraints.
>
> This older GDD file remains available as game-design and historical context.
>
> Hardware, body, power, thermal, RCS, bayonet, NBL, protection, modularity, command gating and evidence claims should be checked against:
>
> `docs/design/hardware_and_physics/qiki_body_v0_2_2/`
>
> Older conflicting statements should be treated as superseded by QIKI Body v0.2.2 unless explicitly re-accepted by a later ADR.
```

## 7. Add files

Markdown only:

```bash
git add docs/design/hardware_and_physics/qiki_body_v0_2_2
```

Если обновлены индексы или старый GDD:

```bash
git add docs/INDEX.md docs/design/game/bot_gdd.md
```

## 8. Финальная проверка

```bash
git status --short
```

Проверить глазами, что нет runtime-diff.

## 9. Commit

Markdown only:

```bash
git commit -m "docs: add QIKI Body v0.2.2 documentation package"
```

Markdown + JSON:

```bash
git commit -m "docs: add QIKI Body v0.2.2 documentation and JSON companion"
```

## 10. После commit

Не продолжать сразу runtime.

Следующий runtime шаг — отдельная задача:

`RUNTIME_SLICE_0001_PLAN.md`

## 11. Красная линия

Если появляется соблазн написать:

- implemented;
- verified;
- runtime supports;
- ORION now shows;
- telemetry supports;
- conforms;

нужно остановиться и потребовать evidence.
