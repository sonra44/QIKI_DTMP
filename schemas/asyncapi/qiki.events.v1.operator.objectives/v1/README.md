# Контракт события: `qiki.events.v1.operator.objectives` (v1)

`qiki.events.v1.operator.objectives` фиксирует observation objective contour для ORION V:
сначала как seed, затем как closure на том же truth-backed path.

Текущий MVP-смысл:

- producer публикует observation objective seed со статусом `prepared` и
  `kind=observation_objective_seed`;
- тот же canonical path затем может закрыть objective через
  `kind=observation_objective_update` и один из closure-статусов:
  - `confirmed` — цель выполнена и наблюдаемый consequence подтверждён;
  - `failed` — execution path сорвался или consequence не подтвердился;
  - `cancelled` — prepared objective был снят оператором до честного завершения;
- ORION V показывает objective как отдельный F1 contour;
- procedure/audit/telemetry остаются существующим execution backbone;
- никаких demo/random mission values.
- для post-`resume_observation` continuation на том же payload допускаются ровно
  два минимальных truth-backed result:
  - `observation_result_status=reconfirmed`
  - `observation_result_reason_code=OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED`
  - `observation_result_status=signature_changed`
  - `observation_result_reason_code=OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED`
  - `observation_result_summary_en/ru`

Важно:

- в `v1` нет отдельного статуса `active`;
- running/step-by-step execution остаётся на existing procedure backbone;
- objective event path нужен для seed + closure, а не для дублирования всей procedural state machine.

Минимальный payload включает:

- `objective_id`
- `objective_type=observation`
- `status` in:
  - `prepared`
  - `confirmed`
  - `failed`
  - `cancelled`
- `observation_style` (`safe` или `slow`)
- `procedure_name`
- `route_role` (`official` или `deviation`)
- `request_id`
- `proposal_id`
- `target_designator` (если оператор указал цель явно)
- `track_visible` + `track_id/track_label/range/quality`, если цель уже реально видна в radar truth
- bilingual title/summary
- optional continuation-result fields for the same contour:
  - `observation_result_status`
  - `observation_result_reason_code`
  - `observation_result_summary_en`
  - `observation_result_summary_ru`

Минимальный route-choice контракт для `G3-QIKI-004`:

- для одной observation target route identity остаётся на том же payload:
  - `observation_style`
  - `procedure_name`
  - `proposal_id`
  - `route_role`
- для текущего честного среза этого достаточно, потому что в runtime уже существуют
  две реальные valid procedures для одного observation contour:
  - `safe_pause_resume`
  - `safe_pause_slow_resume`
- `route_role=official` закрепляет существующий `safe_pause_resume` contour как официальный путь;
- `route_role=deviation` закрепляет `safe_pause_slow_resume` как текущий deviation path, не создавая
  второго truth source и не вынося route semantics в UI-эвристику;
- это не новый mission engine и не отдельный route-subject; это два route-contour
  на том же objective truth path.

Lifecycle vocabulary `v1`:

- `prepared` — observation contour prepared and visible to the operator
- `confirmed` — objective closed successfully on a confirmed consequence
- `failed` — objective closed unsuccessfully
- `cancelled` — objective was explicitly cancelled before successful closure

Kind vocabulary `v1`:

- `observation_objective_seed` — initial prepared contour
- `observation_objective_update` — closure/update on the same objective path

Субъект остаётся внутри канонического namespace `qiki.events.v1.>` и не создаёт `v2`.
