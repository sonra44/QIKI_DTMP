# TASK: Блок 0 «оператор→тело» — abort-гонка, голые таски, TOCTOU пломбы

**ID:** TASK_20260709_BLOCK0_OPERATOR_BODY
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 1 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Легализовать (досье + коммит + верификация) уже сделанные и test-proven фиксы
дефектов 0.3 / 0.4 / 0.5 из `02_BLOCK0_DEFECT_BASELINE.md` (= блок 1
`AUDIT_2026-07-09_GLOBAL.md`): исход подтверждённого оператором действия не
может молча потеряться или перезаписать «прервано».

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что стало честнее: `q abort` во время установки модуля **гарантированно**
  оставляет процедуру прерванной (модуль не ставится «после смерти» команды);
  исполнение подтверждённого действия не теряется молча (исключения фоновых
  задач попадают в лог); подменить параметры команды между одобрением и
  эффектом нельзя (deepcopy пломбы + пересверка digest в мосте).
- Ограничение: один цикл = один сценарий (этот — Consequence Confirmation P3).

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_block1_operator_to_body.py -q
```

## Before / After

- Before: abort на await S4-аудита перетирался стыковкой S5 (ABORTED→DONE,
  модуль ставился после «прервано»); 27 голых `asyncio.create_task` в
  `orion_v/app.py` (GC мог убить, исключения терялись); пломба хранила
  shallow-копию parameters — мутация вложенных структур после authorize
  доезжала до тела.
- After: guard `if not proc.active: return` после каждого await продвижения
  стадий + входной guard S5; все fire-and-forget корутины через
  `self._spawn_task` (`_bg_tasks` + reaper с `logger.error`);
  `seal_decision`/`sealed_command` делают deepcopy, мост пересчитывает digest
  перед эффектом (`BRIDGE_SEAL_DIGEST_DRIFT`, тело не трогается при дрейфе).

## Impact Metric

- Метрика: RED-тесты контракта «оператор→тело» (`test_block1_operator_to_body.py`).
- Baseline: 4 failed (гонка воспроизводится, deepcopy нет, digest не сверяется,
  `_spawn_task` отсутствует).
- Target: 4 passed; пин-тесты и m5-спуф не краснеют.
- Actual: 4 passed; пин/смежные 144 passed (см. Evidence).

## Scope / Non-goals

- In scope: дефекты 0.3, 0.4, 0.5 (`orion_v/app.py`,
  `qiki/shared/command_decision.py`, `qiki/shared/decision_body_bridge.py`,
  тесты + адаптация тестовых стабов `create_task`→`_spawn_task`).
- Out of scope: дефекты 0.1/0.2/0.6-0.17 (этапы 2-4), радар, UI-переработки,
  декомпозиция `app.py`; pre-existing падения
  `test_orion_v_f5_syntax_w7::test_code_fence_is_highlighted`,
  `tools/orion_v_qiki_release_dock_smoke.py`,
  `tools/orion_v_qiki_dialog_f5_smoke.py` (доказаны на чистом 64dbe0c).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/02_BLOCK0_DEFECT_BASELINE.md` (0.3-0.5)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/09_WORK_SEQUENCE.md` (этап 1)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/_support/CLARIFICATION_REPLY_001.md` (A1)
  - `docs/dev/AUDIT_2026-07-09_GLOBAL.md` (блок «оператор→тело»)

## Plan (steps)

1) RED-тесты контракта (усилить abort-тест до реального окна гонки — await
   S4-аудита) → подтвердить 4 failed. [сделано]
2) Фиксы: guard'ы abort; `_spawn_task`/`_bg_tasks`/reaper + замена 27 вызовов;
   deepcopy пломбы + `BRIDGE_SEAL_DIGEST_DRIFT` в мосте. [сделано]
3) Верификация по `08_VERIFICATION_PLAN.md`: тесты этапа 1, пин-тесты,
   смоки, полный `tests/unit`. [сделано]
4) Досье + коммит + гейты PR. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (поведение зафиксировано этим досье; канон не менялся)
- [x] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean (`git status --porcelain` is expected) — после коммита этапа

## Evidence (commands → output)

Все прогоны — Docker, контейнер `qiki-dev-phase1`, 2026-07-09.

1. RED (до фиксов, abort-тест усилен до окна S4):

```
$ docker exec qiki-dev-phase1 python -m pytest tests/unit/test_block1_operator_to_body.py -q
FAILED ...::test_abort_during_stage_audit_await_keeps_aborted_and_body_untouched
FAILED ...::test_seal_freezes_nested_parameters_deep
FAILED ...::test_bridge_recomputes_digest_before_effect
FAILED ...::test_spawn_task_keeps_reference_and_logs_exception
```

2. GREEN (после фиксов): `4 passed`.

3. Тесты этапа 1 + пин-тесты + смежные (11 файлов: block1, f1_first_playable_loop,
   qiki_approve_m6, command_decision_m5, qiki_loop, qiki_dialog_f5,
   bridge_p0/m7, body_attach_live/p3, app_incidents):
   `139 passed`; hand_confirm + hand_confirm_pilot: `5 passed`.

4. Смоки: `orion_v_qiki_decision_spoof_deny_smoke.py` → `M5 PASS`;
   `qiki_decision_body_bridge_smoke.py` → `M7-M9 PASS` + `JSONL-трасса OK`.
   `orion_v_qiki_release_dock_smoke.py` и `orion_v_qiki_dialog_f5_smoke.py`
   падают **идентично на чистом 64dbe0c** (проверено `git stash` → прогон →
   `stash pop`) — pre-existing, вне scope (кандидаты этапа 4: ACK-каналы 0.15).

5. Полный `tests/unit`: единственный failed —
   `test_orion_v_f5_syntax_w7::test_code_fence_is_highlighted`, pre-existing
   (падает на чистом 64dbe0c, тот же метод проверки).

6. Правка пин-теста `test_orion_f1_first_playable_loop.py` — НЕ поведение
   цикла F1, а тестовый стаб `create_task` (возвращал `None`/объект без
   `add_done_callback`, `_spawn_task` вешает reaper). Аналогично в
   `test_orion_v_app_incidents.py` (`_TaskStub.add_done_callback`).

7. Гейты PR (Docker-first):

```
$ bash scripts/branch_policy_check.sh            → PASS
$ bash scripts/ops/anti_loop_gate.sh             → [anti-loop] OK (это досье)
$ bash scripts/qiki_drift_audit.sh --strict      → EXIT=0
$ bash scripts/quality_gate_docker.sh            → EXIT=0 ([quality-gate] OK)
```

Попутно (разблокировка гейтов, отдельные коммиты):
- восстановлен reference-слой `.codex/imp/RE_QIKI_{Runtime_Evidence_Notes,
  Maturity_Matrix,Risks_and_Unresolved_Zones}.md` из `cbaf6c7` (потерян при
  снапшот-пересборке дерева; drift-гейт требует его наличия);
- `test_orion_v_f5_syntax_w7._render_ansi`: пинован
  `color_system="truecolor"` — без TERM (docker exec) Rich деградировал до
  8 цветов и фоновые эскейпы подсветки исчезали (pre-existing red, чинит
  тест-среду, не поведение).
