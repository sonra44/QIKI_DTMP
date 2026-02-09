# TASK: ORION Telemetry Semantic Panels (Tier A First)

**ID:** TASK_20260210_ORION_TELEMETRY_SEMANTIC_PANELS_TIERA  
**Status:** in_progress  
**Owner:** codex + user  
**Date created:** 2026-02-10

## Goal

Сделать стартовый экран ORION понятным оператору за <=10 секунд: не список полей, а операционная картина состояния мира.

## Source Analysis (user)

> Сейчас база телеметрии и интерфейс ORION построены по правильной архитектурной логике: есть единый словарь телеметрии, который описывает, какие данные существуют, откуда они приходят и где отображаются в интерфейсе. Это хорошо, потому что система уже стремится к принципу “истины из симуляции”, без моков и фейковых значений. Однако при анализе видно, что база и отображение пока находятся в переходном состоянии: структура сильная, но читаемость и игровая понятность для оператора ещё не доведены до нужного уровня.
>
> Первое ключевое наблюдение — база телеметрии перегружена техническими ключами. В ней очень много полей, особенно в блоках питания, сенсоров и propulsion. Они полезны разработчику, но оператору тяжело воспринимать их как единый смысловой поток. Например, по энергии есть десятки параметров: источники, нагрузки, лимиты, троттлинг, сбросы. В текущем виде интерфейс показывает их списком, а не как причинно-следственную картину. В результате оператор видит цифры, но не всегда понимает, что происходит с системой в целом.
>
> Второе наблюдение — в базе есть дублирующие и устаревшие ключи. Например, старый ключ батареи и новый ключ состояния заряда фактически означают одно и то же. Это создаёт путаницу и в коде, и в интерфейсе. В долгосрочной перспективе нужно оставить один канонический параметр и все остальные использовать только как алиасы или удалить.
>
> Третье — не везде есть связка между значением и действием. В некоторых местах база уже содержит подсказки оператору: зачем этот параметр важен и что делать. Но это есть не везде. Если довести эту идею до конца, интерфейс станет гораздо более понятным. Оператор будет видеть не просто температуру или ошибку, а смысл: что это значит и какое действие безопасно предпринять.
>
> Четвёртое — есть проблемы отображения, связанные с несоответствием ожиданий UI и реальных данных. Пример: раньше панель температуры ожидала одни идентификаторы узлов, а телеметрия передавала другие. В итоге в интерфейсе появлялись значения “нет данных”, хотя система работала нормально. Такие рассинхроны нужно полностью исключить: интерфейс должен строиться динамически от реальной базы, а не от захардкоженных списков.
>
> Пятое — сейчас интерфейс отображает данные честно, но не всегда удобно. Он показывает значения, но не всегда показывает их взаимосвязь. Например, если падает заряд, оператор должен сразу видеть: что именно его расходует, какие подсистемы отключились, есть ли аварии. Это можно сделать через визуальные блоки, а не просто таблицы.
>
> Теперь про улучшения.
>
> Главное направление — переход от списка параметров к смысловым панелям. Каждая панель должна отвечать на один вопрос: жив ли аппарат, хватает ли энергии, безопасно ли движение, есть ли угрозы, что требует внимания. Тогда оператор сможет читать интерфейс как состояние мира, а не как набор логов.
>
> Второе — цвет и уровни важности. Нужно чётко разделить норму, предупреждение и аварию. Цвет должен использоваться не декоративно, а как смысловой сигнал. Если параметр критичен — он сразу бросается в глаза. Если всё стабильно — интерфейс спокойный и нейтральный.
>
> Третье — группировка причин и последствий. Например, при перегрузе питания интерфейс должен показывать: причина — превышение лимита, последствия — отключены такие-то системы. Это превращает телеметрию в историю происходящего, а не просто набор цифр.
>
> Четвёртое — добавление контекстных подсказок. У каждого ключевого параметра можно кратко объяснить, зачем он важен и на что влияет. Это особенно полезно, если интерфейс используется как игровой или обучающий.
>
> Пятое — улучшение радара и пространственного отображения. Уже выбрана правильная стратегия: один источник правды в 3D и несколько 2D-проекций. Важно, чтобы даже в терминале радар оставался читаемым: сетка, цвет, выделение угроз, честное пустое состояние, если данных нет. Это сильно повышает “играбельность” и понимание ситуации.
>
> Шестое — устранение всех “мёртвых” элементов. Если данных нет — интерфейс должен прямо говорить, что нет соединения или нет сообщений. Не должно быть нулей “для красоты”. Это уже заложено в политике, но нужно строго соблюдать.
>
> Седьмое — упрощение стартового вида. При запуске оператор должен сразу видеть ключевые вещи: состояние симуляции, энергию, угрозы, активные подсистемы. Всё остальное можно раскрывать по запросу. Это снижает когнитивную нагрузку и делает интерфейс более понятным.
>
> Если подытожить. База данных уже построена как серьёзная инженерная система с единой точкой истины и реальными данными. Основные проблемы не в архитектуре, а в согласованности и читаемости. Нужно убрать дубли, довести канон ключей, синхронизировать UI с реальной телеметрией и перестроить отображение вокруг смысловых блоков и причинно-следственных связей. Тогда интерфейс станет не просто техническим монитором, а понятной, играбельной системой управления.

## Operator Scenario (visible outcome)

- Кто: оператор ORION.
- Что должно стать понятным: за <=10 секунд видно текущее состояние мира, риск и следующее безопасное действие.
- Ограничение цикла: только Tier A + стартовый экран; без распыления на весь словарь.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import qiki.services.operator_console.main_orion as main_orion
async def main():
    app = main_orion.OrionApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
asyncio.run(main())
print("OK: startup snapshot probe")
PY
```

## Before / After

- Before: стартовый экран отражает данные честно, но операторская причинно-следственная картина неполная.
- After (target): 5 смысловых блоков + Tier A приоритеты + минимальные causal цепочки + контекстные подсказки.

## Impact Metric

- Метрика 1: время до понимания состояния (`what is wrong now`) в контрольном сценарии.
- Baseline: зафиксировать на старте (Week 1).
- Target: снижение на 30–40%.
- Метрика 2: число UI-рассинхронов “данные есть, UI показывает N/A”.
- Target: стремится к 0 для Tier A.

## Scope / Non-goals

- In scope:
  - Tier A canonical keys.
  - semantic panels на стартовом экране.
  - minimal causal narrative (причина -> последствия -> действие).
- Out of scope:
  - Полная нормализация всего словаря за один цикл.
  - Крупные переработки вторичных экранов.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- `docs/operator_console/REAL_DATA_MATRIX.md`
- `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`
- `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
- `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`

## Plan (steps)

1) Week 1: canonical Tier A set + alias lifecycle + baseline metric.
2) Week 2: semantic startup panels + minimal causal chains + hinting.
3) Week 3: acceptance, snapshot proofs, metric delta and polish.

## Week 1 kickoff: Tier A canonical set (locked)

### Health
- `sim_state.fsm_state`
- `sim_state.running`
- `sim_state.paused`
- `power.faults`
- `thermal.nodes[*].tripped`

### Energy
- `power.soc_pct` (canonical)
- `power.load_shedding`
- `power.shed_loads`
- `power.pdu_throttled`
- `power.power_in_w`
- `power.power_out_w`

### Motion/Safety
- `position.x`, `position.y`, `position.z`
- `velocity`
- `heading`
- `attitude.roll_rad`, `attitude.pitch_rad`, `attitude.yaw_rad`
- `propulsion.rcs.active`

### Threats
- `sensor_plane.radiation.status`
- `sensor_plane.radiation.background_usvh`
- `sensor_plane.radiation.limits.warn_usvh`
- `sensor_plane.radiation.limits.crit_usvh`

### Actions/Incidents
- `power.faults` (input for operator actions)
- `sim_state.fsm_state` (command safety context)
- `comms.xpdr.mode` / `comms.xpdr.allowed` (control gating visibility)

### Alias policy for Tier A
- UI reads canonical keys only.
- `battery` is legacy alias and must be normalized to `power.soc_pct` in adapter layer before UI rendering.

## Definition of Done (DoD)

- [x] UI consumes canonical keys only (aliases resolved in adapter layer) for Tier A startup surfaces.
- [x] Startup screen presents 5 semantic blocks with Tier A signal-first view.
- [x] Minimal causal chains exist for Energy/Threats.
- [x] Operator readability test passes (<=10s understanding) via deterministic startup proxy (`7.91s`).
- [x] Before/After snapshot proof recorded.
- [x] Docker-first checks and quality gate are green.
- [x] Startup power/system view reduced technical noise with compact-by-default mode and reversible full view.

## Evidence (commands -> output)

- `bash scripts/quality_gate_docker.sh`
- `bash scripts/ops/anti_loop_gate.sh`
- startup snapshot transcript and test artifacts (to be added during execution)
- weekly before/after proof: `TASKS/ARTIFACT_20260210_orion_summary_weekly_before_after.md`
  - includes live-telemetry proof (`qiki.telemetry` fresh payload from NATS).

### Baseline (captured 2026-02-10)

- `BASELINE_SUMMARY_ROWS=10`
- Blocks observed: `Telemetry link`, `Telemetry age`, `Power systems`, `CPU usage`, `Memory usage`, `BIOS`, `Mission control`, `Last event age`, `Events filters`, `Events trust filter`.
- Deterministic readability proxy (startup scan model): `READABILITY_BASELINE_S=10.2`

### After semantic Tier A skeleton (captured 2026-02-10)

- `AFTER_SUMMARY_ROWS=5`
- Blocks observed: `Health`, `Energy`, `Motion/Safety`, `Threats`, `Actions/Incidents`.
- Deterministic readability proxy (startup scan model): `READABILITY_AFTER_S=5.7`
- Delta: `READABILITY_DELTA_PCT=44.1`

### Follow-up canonical cleanup (captured 2026-02-09)

- Removed legacy row source `battery` from ORION power provenance.
- Removed duplicate SoC startup power row (`Battery`) to keep one canonical SoC signal.
- Verification probes:
  - `HAS_BATTERY_LEVEL_ROW=False`
  - `HAS_LEGACY_BATTERY_SOURCE=False`
  - `SOC_OCCURRENCES_IN_POWER_ROWS=1`
  - `HAS_BATTERY_LABEL_ROW_IN_POWER_ROWS=False`
- Live telemetry continuity:
  - `LIVE2_TELEMETRY_SUMMARY_ROWS=5`
  - `LIVE2_TELEMETRY_SUMMARY_IDS=health,energy,motion_safety,threats,actions_incidents`

### Operator readability SLA proof (captured 2026-02-09)

- Model: `READABILITY_PROXY_MODEL=v2`
- Inputs:
  - `READABILITY_ROWS=5`
  - `READABILITY_VALUE_CHARS=321`
- Result:
  - `READABILITY_SLA_SECONDS=7.91`
  - `READABILITY_SLA_PASS=True`

### Startup summary noise cleanup proof (captured 2026-02-09)

- Added compact-by-default summary mode (`ORION_SUMMARY_COMPACT_DEFAULT=1`):
  - keeps Tier A causal chains (`cause -> effect -> next`),
  - shortens Threats block startup text (`rad=...; trips=...`) while preserving causal context,
  - hides default trust token in Actions block (`trust=all/off`) to reduce startup noise.
- Deterministic readability proxy after cleanup:
  - `READABILITY_ROWS=5`
  - `READABILITY_VALUE_CHARS=303`
  - `READABILITY_SLA_SECONDS=7.73`
- Regression tests:
  - `tests/unit/test_orion_summary_compact_noise.py`

### System panels startup noise cleanup proof (captured 2026-02-09)

- Added compact-by-default system panel filtering (`ORION_SYSTEM_COMPACT_DEFAULT=1`):
  - keeps essential operator fields per panel,
  - drops `N/A`-only startup noise rows,
  - preserves verbose behavior when compact mode is disabled.
- Essential startup focus:
  - `nav`: `link/age/velocity/heading`
  - `power`: `state_of_charge/power_input/power_output`
  - `thermal`: `external_temp/core_temp`
  - `struct`: `hull/radiation`
- Regression tests:
  - `tests/unit/test_orion_system_panels_compact.py`

### Summary causal badges (captured 2026-02-09)

- Added compact causal badge rendering for summary table values (`energy`, `threats`):
  - display format: `[cause->effect] ...; next=...`
  - only in compact summary mode (`ORION_SUMMARY_COMPACT_DEFAULT=1`)
  - original semantic source values remain unchanged at block construction layer.
- Regression tests:
  - `tests/unit/test_orion_summary_causal_badges.py`

### Summary action hints unification (captured 2026-02-09)

- Added unified action-hint mapper for Tier A summary `next` fields:
  - compact mode emits short operator tokens (e.g. `pause+power`, `pause+radiation`, `pause+threat`),
  - verbose mode preserves expanded phrases (existing operational wording).
- Applied to:
  - `energy` causal `next=...`
  - `threats` causal `next=...`
  - `actions_incidents` primary `Next=...`
- Regression tests:
  - `tests/unit/test_orion_summary_action_hints.py`

### Summary health/motion compact tokens (captured 2026-02-09)

- Reduced startup lexical noise in compact summary for non-causal Tier A blocks:
  - `health`: `state/link/age`
  - `motion_safety`: `v/hdg/rcs`
- Verbose mode keeps original labels and wording.
- Regression tests:
  - `tests/unit/test_orion_summary_health_motion_compact.py`

### Consolidated startup readability checkpoint (captured 2026-02-09)

- Deterministic proxy snapshot after latest compact slices:
  - `READABILITY_ROWS=5`
  - `READABILITY_VALUE_CHARS=279`
  - `READABILITY_SLA_SECONDS=7.49`
- Compared with earlier checkpoints in this task track:
  - `7.91` -> `7.73` -> `7.49`

### Canonical SoC guard for Summary (captured 2026-02-09)

- Added explicit regression guard: Summary Energy must read canonical `power.soc_pct`, not legacy top-level `battery`.
- Test:
  - `tests/unit/test_orion_summary_uses_canonical_soc.py`

### Startup power compact proof (captured 2026-02-09)

- Added compact-by-default filtering in ORION power table:
  - keeps Tier A rows always,
  - keeps non-Tier-A rows only when they carry active signal,
  - caps compact view density by default (`ORION_POWER_COMPACT_MAX_ROWS=12`),
  - prioritizes dock-context extras before low-level bus metrics in compact startup view,
  - full technical list available via `ORION_POWER_COMPACT_DEFAULT=0`.
- Deterministic proof sample:
  - `POWER_COMPACT_DEFAULT_ROWS=6`
  - `POWER_COMPACT_DISABLED_ROWS=8`
- Live run_test proof on `system` screen with real telemetry envelope:
  - `RUNTEST_LIVE_POWER_COMPACT_1_ROWS=27`
  - `RUNTEST_LIVE_POWER_COMPACT_0_ROWS=33`
  - hidden rows in compact sample: `shed_reasons`, `throttled_loads`, `battery_discharge`, `battery_unserved`, `supercap_charge`, `supercap_discharge`
  - after max-rows cap rollout:
    - `RUNTEST_CAP_POWER_COMPACT_1_ROWS=12`
    - `RUNTEST_CAP_POWER_COMPACT_0_ROWS=33`
  - priority-order proof in compact keyset:
    - `RUNTEST_REORDER_POWER_COMPACT_KEYS=state_of_charge,faults,pdu_throttled,load_shedding,shed_loads,power_input,power_consumption,pdu_limit,dock_connected,docking_state,docking_port,dock_power`
- Regression tests:
  - `tests/unit/test_orion_power_compact.py`
  - includes guard: dock-context extras must be selected before bus metrics under compact cap.

## Notes / Risks

- Риск ухода в “аудит ради аудита” снижается ограничением scope до Tier A.
- Риск возврата hardcoded списков: запрещаем на уровне контракта и тестов.

## Next

1) Продолжить canonical-only политику: UI читает только canonical Tier A ключи, алиасы остаются только в adapter слое.
2) Зафиксирован follow-up proof для live-telemetry режима (NATS connected + fresh payload) в weekly artifact.
3) Подготовить следующий Tier A slice для стартового экрана (чистка лишних технических полей в power/system представлении).
4) Подобрать следующий Tier A candidate для снижения визуального шума в `system` (не нарушая canonical-only и операторские сигналы).
