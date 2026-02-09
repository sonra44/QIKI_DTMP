# ARTIFACT: Canon Evidence Reliability Audit (QIKI_DTMP)

**Date:** 2026-02-09  
**Scope:** `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md` + `QIKI_DTMP/TASKS/` + git history (`main`)  
**Purpose:** синхронизировать базу фактов и подтвердить, что статусы в каноне подкреплены проверяемыми доказательствами.

## Executive Summary

- Канон задач в целом управляемый: открытых задач в board нет, второго канона не обнаружено.
- Обнаружен системный разрыв достоверности: часть завершённых задач ссылается на отсутствующие task-досье.
- Это не доказывает, что работа не была выполнена, но доказывает, что текущая доказательная цепочка неполная.

## Methodology

1. Проверка anti-drift guard:
- `bash scripts/check_no_second_task_board.sh`
- результат: `OK`.

2. Проверка канонических entrypoints:
- `docs/design/canon/INDEX.md` существует.
- `docs/Архив/**` явно помечен как reference-only в canon docs.

3. Проверка достоверности board:
- извлечены все `- [x]/- [ ]` пункты из `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
- для каждого пункта проверены ссылки на `TASKS/TASK_*.md` (наличие файла).
- для `latest proof HEAD` проверено существование commit (`git cat-file -e`).

## Findings (Data)

- Total entries: **52**
- Open entries: **0**
- Entries with `latest proof HEAD`: **12**
- HEAD proof valid: **12/12**
- Entries with `TASKS/TASK_*.md` references: **35**
- Entries where all referenced task files exist: **23**
- **Anomalies (missing referenced task files): 18**

## Mismatch List (Canon -> Evidence)

Ниже пункты канона, где ссылка на evidence-файл отсутствует в текущем `main`:

1. `Fix Docker build reproducibility (requirements*.txt)`
2. `Operator-safe exception logging (ORION)`
3. `Operator console: NATS client no longer swallows handler/ack errors`
4. `Shell OS panels: no silent exceptions + ORION operator log`
5. `ORION: operator log write failures are no longer silent`
6. `ORION: oplog throttle failure is no longer silent`
7. `ORION UI: no silent focus/trim/boot-cancel errors`
8. `Q-Core Agent: Ship FSM context set is no longer silent`
9. `BIOS: NATS publisher close is no longer silent`
10. `BIOS: HTTP server shutdown is no longer silent`
11. `Q-Sim: control loop no longer swallows exceptions`
12. `P1: Smoke tools are fail-loud (no silent exceptions)`

Примечание: 18 аномалий формируются из 12 пунктов, потому что у одного пункта ORION UI несколько missing ссылок.

## Deep Analysis: Why this happens

### Primary causes

1. **Evidence link rot after history/structure churn**
- task-досье удалялись/переносились/не переносились при веточных циклах, а board остался с прежними путями.

2. **Asymmetric completion discipline**
- код и коммиты доходят до `main`, но часть досье не проходит финальную сверку “file exists”.

3. **Mixed proof channels**
- часть задач доказывается commit hash/doc updates, часть — task-файлами. При отсутствии единой нормализации появляются битые ссылки.

### Probabilities (pragmatic estimate)

- 0.65: evidence link rot (переименование/удаление task-файлов)
- 0.25: неполное закрытие task-cabinet в старых циклах
- 0.10: ошибки ручного копирования ссылок в board

## Risks

- Governance risk: статус `done` без доступного evidence снижает доверие к канону.
- Product risk: команда тратит время на повторную верификацию старых решений.
- Process risk: усиливается ощущение “ходим по кругу”.

## Sync Actions Applied Now

1. В каноничный board добавлен открытый пункт:
- `Evidence integrity reconciliation (legacy TASK links, 2026-01-27/28)`.

2. Зафиксирован этот audit-artifact как единый reference на текущий момент.

## Corrective Plan (no second canon)

1. Для каждого mismatch пункта выбрать одну из двух стратегий:
- A) восстановить `TASKS/TASK_*.md` из git history;
- B) заменить ссылку в board на валидный commit/doc evidence.

2. После каждой правки прогонять проверку достоверности board.

3. Закрыть reconciliation-пункт только при `ANOMALIES=0`.

## Reproduction Commands

```bash
bash scripts/check_no_second_task_board.sh
```

```bash
python3 - <<'PY'
import re
from pathlib import Path
board=Path('/home/sonra44/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md').read_text(encoding='utf-8').splitlines()
entries=[]; cur=None
for i,l in enumerate(board,1):
    m=re.match(r'- \[(x| )\] \*\*(.+?)\*\*',l)
    if m:
        cur={'done':m.group(1)=='x','txt':''}; entries.append(cur)
    elif cur is not None:
        cur['txt'] += l+'\n'
an=0
for e in entries:
    for ref in set(re.findall(r'`([^`]*TASKS/[^`]*\.md)`', e['txt'])):
        p=(Path('/home/sonra44')/ref) if ref.startswith('QIKI_DTMP/') else (Path('/home/sonra44/QIKI_DTMP')/ref)
        if not p.exists(): an += 1
print(f'ANOMALIES={an}')
PY
```

## Update (2026-02-09): Placeholder Verification Progress

After restoring missing evidence link targets (commit `62694bd`), all placeholder dossiers were upgraded to verified evidence (code-backed checks + unit tests where applicable).

- Verified dossiers (18):
  - BIOS shutdown, BIOS publisher close
  - operator-console NATS client
  - ship FSM context set
  - q-sim no-silent
  - shell_os panels
  - smoke tools fail-loud
  - requirements files present
  - ORION no-silent exception logging slices (show_screen, UI input, responsive chrome, etc.)
- Remaining placeholders: none.
