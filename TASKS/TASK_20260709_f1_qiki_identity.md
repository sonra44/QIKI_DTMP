# TASK: Этап 7 «f1-qiki-voice» — идентичность QIKI на F1 (G-F, Z3)

**ID:** TASK_20260709_F1_QIKI_IDENTITY
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 7 пакета `orion_playable_f1_f5_v1` (task-0048)
**Date created:** 2026-07-09

## Goal

Закрыть этап 7 (`f1-qiki-voice`, фаза G-C + G-F). Ревизия показала: G-C
(лента `QIKI ▸`, tooltip LEGALITY/TRUST, строка честности панели) уже
сделан под-слайсом 8в (05.07, `qiki_voice.py` + cockpit:2512) и живёт в
проде — остаток этапа = G-F: строка идентичности Z3.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно: статус-блок F1 первой строкой всегда несёт «кто я»:
  `QIKI-<серийник> | додекаэдр · 12 граней | модулей N/12` — и при правом
  MFD «systems» блок больше не схлопывается в пустоту (identity не
  дублирует systems-страницу, решение №5 о дублях не нарушено). Серийник —
  живой (первые 6 hex digest'а `hardware_profile_hash` из телеметрии);
  без телеметрии — честное «QIKI-—». Evidence-мета (источник серийника,
  суррогатность, посев, source) — в tooltip рамки, не на строке.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_f1_qiki_identity.py -q
docker exec qiki-dev-phase1 python -u tools/orion_v_f1_identity_smoke.py
```

## Before / After

- Before: статус-блок при right-MFD «systems» (дефолт) был пуст — «кто я»
  не присутствовал на F1 вообще; при других страницах блок нёс только
  body/physics/power сводки. Спека Z3 (identity-строка) не реализована.
- After: `format_qiki_identity_line/format_qiki_identity_tooltip` — единый
  владелец в `body_structure_view_model.py` (канон-грунт: додекаэдр,
  12 граней — bot_source_of_truth §корпус, READER_MANUAL §6 «модульность
  не создаёт нового робота»; RAG-гейт пройден); cockpit ставит identity
  первой строкой блока всегда + tooltip рамки. Серийник парсит формат
  producer'а `sha256:<64hex>` — digest, не имя алгоритма.

## Impact Metric

- Метрика: RED-тесты `test_f1_qiki_identity.py` + живой смок.
- Baseline: ImportError (владельца не было); статус-блок при systems — "".
- Target/Actual: **7 passed** (формат, честное «—», sha256-префикс,
  tooltip-мета, оба режима блока) + пин №5 адаптирован (R1: блок при
  systems теперь identity-only, старый статус-ряд не возвращается);
  живой смок **EXIT=0**: `QIKI-207B23 | додекаэдр · 12 граней | модулей
  0/12` с настоящим серийником из живой телеметрии; полный tests/unit
  0 FAILED; src-деревья — только известные pre-existing (карта 0047).

## Scope / Non-goals

- In scope: body_structure_view_model.py (владелец строки/tooltip),
  screens/cockpit.py (`_compose_mfd_status_text` + `_hardware_profile_hash`
  + tooltip), тесты, смок.
- Out of scope: «реплика #N» — target-only до появления источника (спека
  Z3); отдельный id вместо суррогата hardware_profile_hash; G-C лента —
  уже в проде (под-слайс 8в), не трогалась; этапы 8+ пакета.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/03_F1_COCKPIT_SPEC.md` (Z3, Z7, порядок фаз)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/09_WORK_SEQUENCE.md` (этап 7)
  - RAG-грунт: bot_source_of_truth.md (додекаэдр, 12 граней),
    10_READER_MANUAL.md §6 (идентичность)

## Plan (steps)

1) Ревизия готовности G-C (лента в проде) + RAG-гейт канона идентичности. [сделано]
2) RED (ImportError + блок-режимы) → владелец + проводка → GREEN;
   живой смок поймал «QIKI-SHA256» (формат hash) → фикс парсера + пин. [сделано]
3) Досье + гейты + коммит + main + рестарт консоли + борд + чекпоинт. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. Юниты: 7 passed (identity) + смежные (test_orion_v_cockpit с
   адаптированным пином №5, test_orion_qiki_voice) зелёные; полный
   tests/unit 0 FAILED; ruff-дифф чист (3 E501 pre-existing).
2. Живой смок (стек phase1, настоящая телеметрия):

```
[smoke] identity живьём: QIKI-207B23 | додекаэдр · 12 граней | модулей 0/12
[smoke] evidence-мета в tooltip рамки (источник серийника назван) ✓
[smoke] Этап 7 PASS: идентичность QIKI честна на живом стеке
```

3. Первый прогон смока честно поймал дефект формата («QIKI-SHA256» —
   серийник брался из имени алгоритма, не digest) — исправлено, запинено
   `test_identity_serial_skips_algorithm_prefix`.
