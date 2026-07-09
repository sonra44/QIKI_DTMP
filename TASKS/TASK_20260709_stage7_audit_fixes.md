# TASK: Аудит этапа 7 — канон-12, guard серийника, гейт-покрытие проводки

**ID:** TASK_20260709_STAGE7_AUDIT_FIXES
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез task-0049 (запрос оператора: «проверка этапа 7, поиск ошибок и исправление»)
**Date created:** 2026-07-09

## Goal

Адверсариальный аудит этапа 7 (`fa2a77f..3741f17`) двумя субагентами
(код + мутационный тест-аудит), верификация глазами, фиксы подтверждённого.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: «додекаэдр · 12 граней» и знаменатель «N/12» — канон-константа
  идентичности: сломанный посев больше не может родить «додекаэдр · 0 граней |
  модулей 0/0»; битая телеметрия (dict/list вместо hash-строки) даёт честное
  «QIKI-—», а не мусорный серийник «QIKI- 1}».

## Reproduction Command

```bash
bash scripts/prove_orion_v_f1_identity.sh
```

## Before / After

- Before: строка идентичности брала «граней» и знаменатель из `vm.faces_total`
  (латентная ложь при битом посеве); `str()`-коэрция hash пропускала dict/list
  в серийник (runtime-прогон аудитора: «QIKI- 1}»); мёртвая display-ветка
  схлопывания блока вводила читателя в заблуждение; докстринг смока заявлял
  проверку ленты G-C, которой в смоке нет (overclaim улики); тесты не
  доказывали: счётчик модулей при N>0 (сид всегда 0 — хардкод выживал),
  проводку tooltip в живом cockpit (мутация «tooltip=""» выживала),
  identity-only при systems (протечка body-сводки прошла бы).
- After: `DODECAHEDRON_FACES = 12` — канон-константа в строке (из vm — только
  фактический счётчик модулей); `isinstance(str)`-guard в двух местах (формат
  + `_hardware_profile_hash`); display-ветка убрана с осознанным комментарием;
  докстринг смока честен + дешёвый ассерт honesty-строки панели QIKI;
  4 новых теста: N=1 через РЕАЛЬНЫЙ attach-пайплайн
  (`build_body_structure_self_check_view_model`), канон-12 при faces_total=0,
  reject не-строковых hash, Pilot-проводка tooltip; строгий `len(lines)==1`
  при systems; prove-обёртка `scripts/prove_orion_v_f1_identity.sh` (смок
  теперь в prove-пути проекта).

## Impact Metric

- Baseline: 3 мутации выживали (хардкод модулей, пустой tooltip, протечка
  сводки), 2 latent-дефекта кода, 1 overclaim улики.
- Target/Actual: **11 passed** (identity-пакет), все три мутационные дыры
  закрыты; prove EXIT=0 живьём (QIKI-207B23 + tooltip + honesty-строка);
  полный tests/unit 0 FAILED; q_sim_service-дерево — только 2 известных
  pre-existing; ruff-дифф чист.

## Scope / Non-goals — карта находок

- [x] F1 (LOW, латентный): канон-12 константой — починено.
- [x] F4 (LOW): non-str hash guard — починено (оба места).
- [x] F5 (LOW): мёртвая display-ветка — убрана, задокументировано.
- [x] F2 (MED): смок-overclaim G-C — докстринг честен, honesty-строка
  ассертится; лента QIKI ▸ покрыта юнитами test_orion_qiki_voice и
  F5-контуром (требует LLM-реплики — вне смока осознанно).
- [x] Тест-дыры (2 HIGH + MED) — закрыты новыми тестами.
- Чисто по аудиту (подтверждено): перф VM-вызовов пренебрежим (0.06мс,
  кэшированный снапшот, без I/O; 4×/тик); Z7/G-C реализован в проде
  (limit=3, коды только в tooltip, honesty-строка на панели); конфликтов
  tooltip нет; серийник детерминирован, раздвоения нет.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code: `TASKS/TASK_20260709_f1_qiki_identity.md` (этап 7),
  `03_F1_COCKPIT_SPEC.md` (Z3/Z7).

## Plan (steps)

1) 2 адверсариальных субагента + верификация глазами. [сделано]
2) Фиксы кода/смока/тестов + prove-обёртка. [сделано]
3) Досье + гейты + коммит + main + рестарт консоли + чекпоинт. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

```
[prove] Этап 7 «идентичность QIKI» — юнит: 11 passed
[smoke] identity живьём: QIKI-207B23 | додекаэдр · 12 граней | модулей 0/12
[smoke] evidence-мета в tooltip рамки (источник серийника назван) ✓
[smoke] панель QIKI: honesty-строка (граница | источник | доверие) на месте ✓
[smoke] Этап 7 PASS: идентичность QIKI честна на живом стеке
```
