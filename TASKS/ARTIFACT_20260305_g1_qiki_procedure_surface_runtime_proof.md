# ARTIFACT: G1-QIKI-002 procedure surface runtime proof

Статус: pass
Дата: 2026-03-06
Этап: `G1-QIKI-002`

## Цель

Доказать, что procedural path в ORION V читается не только внутри блока `QIKI`, а как отдельное операторское состояние:
- `F1` показывает секцию `Процедура/Procedure`,
- в ней видны `Prepared`, `Plan`, `Execution`, `Time`,
- из `F1` есть прямой переход `Процедуры/Procedures -> F6`,
- `F6` действительно открывается с procedural audit trail.

## Что проверялось

1. Живой стек `Phase1 + operator-console` поднят и healthy.
2. В `OrionVApp.run_test(...)` приходит реальная telemetry `sim_state`.
3. Инжектируется валидный QIKI response с procedural action:
   - `ORION_PROCEDURE`
   - `safe_pause_resume`
4. До исполнения в `F1` видны:
   - `Процедура/Procedure`
   - `Prepared`
   - `Plan`
   - `Time`
5. После подтверждения процедуры:
   - `Execution` появляется в `F1`,
   - процедура доходит до `confirmed`,
   - `sim_state` возвращается в `RUNNING`,
   - `Процедуры/Procedures` переводит в `F6`,
   - audit filter становится `procedures`.

## Команды проверки

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  tools/orion_v_qiki_procedure_surface_smoke.py

bash scripts/prove_orion_v_qiki_procedure_surface.sh
```

## Результат

```text
OK: orion_v_qiki_procedure_surface_smoke
PROCEDURE_BUTTON=Процедуры/Procedures OK -> F6
CONFIRM_BUTTON=QIKI: нет действия/No action
FINAL_LEVEL=f6
AUDIT_FILTER=procedures
AUDIT_SUMMARY=[F6] Журнал действий

Фильтр: тип=procedures страница 1/1 всего 4

procedures | procedure_start | status=- | qiki.events.v1.operator.procedures
procedures | procedure_start | status=True | qiki.events.v1.operator.procedures
procedures | procedure_done | status=True | qiki.events.v1.operator.procedures
procedures | procedure_finish | status=ok | qiki.events.v1.operator.procedures
```

## Что этим доказано

1. Procedural surface в `F1` существует как отдельный операторский слой.
2. `Prepared -> Execution -> audit trail` теперь читается как единый цикл.
3. Переход `Процедуры/Procedures -> F6` реально работает, а не только покрыт unit-тестом.
4. `G1-QIKI-002` усилился не новым transport, а лучшей видимостью существующего procedural path.

## Остаточный риск

- Пока procedural surface доказан для одного сценария `safe_pause_resume`.
- Следующий выбор остаётся между:
  - вторым procedural scenario,
  - или дальнейшим усилением procedural visibility/history на других уровнях ORION V.
