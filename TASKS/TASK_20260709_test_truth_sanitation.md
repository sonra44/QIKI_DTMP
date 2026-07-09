# TASK: Санитарный срез «тестовая правда» — ноль немотивированных красных в src-деревьях

**ID:** TASK_20260709_TEST_TRUTH_SANITATION
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез task-0050 (план оператора: санация → этап 8)
**Date created:** 2026-07-09

## Goal

`pytest src/qiki/services src/qiki/core` — 0 FAILED без skip-маскировки:
«любой FAILED = новый дефект». До среза шум pre-existing красных прятал
реальные поломки (pause-тест жил сломанным 3 среза).

## Operator Scenario (visible outcome)

- Кто выполняет: operator/агент
- Что честнее: прогон любого тест-дерева стал сигналом, а не шумом; заодно
  убран реальный дефект — env-утечка load_harness заражала fusion-конфигом
  все radar-тесты сессии.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest src/qiki/services src/qiki/core -q -p no:warnings
```

## Before / After

- Before: сбор src-дерева падал на скрипте-ложнотесте; 10+ красных
  (устаревшие ожидания, env-загрязнение, недоинициализированный хелпер);
  один тест сам полагался на утечку соседей.
- After: все src-деревья зелёные (0 FAILED); tests/unit зелёный; каждый
  вердикт задокументирован ниже.

## Impact Metric

- Baseline: сбор Interrupted + 10+ FAILED в src-деревьях.
- Target/Actual: **0 FAILED** (`src/qiki/services` + `src/qiki/core`),
  tests/unit 0 FAILED, ruff чист.

## Карта вердиктов (по разведке с воспроизведением)

| # | Тест | Вердикт | Причина/правка |
|---|------|---------|----------------|
| 1 | q_sim `test_radar_sr_threshold_env_override` | fix-test | env-override исправен (читается в `__init__`); ожидание 50.0 — от старой геометрии; формула даёт `max(50, min(86, 80)) = 80.0` |
| 2 | q_sim `test_sim_events_publishing` | fix-test | producer канонично эмитит 3 события; добавлена проверка PDU. **Флаг:** подписчика на `SIM_POWER_PDU` нет — forward-looking эмит |
| 3 | qiki_chat `test_handler` | fix-test | proposals=[] by design для неисполнимого текста; «proposal без действий» не имеет пути в коде |
| 4 | multisensor/replay (загрязнение) | **fix-code** | `load_harness.run_harness` писал сырой `os.environ["RADAR_FUSION_ENABLED"]` на всю сессию → save/restore в `finally` |
| 4б | `test_load_fusion_stress_no_fused_id_flapping` | fix-test | тест сам ПОЛАГАЛСЯ на утечку из соседей (после restore fusion выключился) → явный `monkeypatch.setenv` |
| 5 | mission_control live_real_input (6 шт.) | fix-test | хелпер `_make_terminal` строил объект мимо `__init__` без session-атрибутов → дописаны (standalone) |
| 6 | `operator_console/test_nats_connection.py` | rename | ручной скрипт с импортом несуществующего `clients` валил сбор ВСЕГО дерева → `check_nats_connection.py` + канонный импорт |
| 7а | `test_agent::run_tick_updates_context` | fix-test | агент читает FSM через `get_fsm_state_result` (result-обёртка), не `get_fsm_state` |
| 7б | `test_agent::neural_engine…when_disabled` | fix-test | `mock=False` = «не мокать», не «выключить»: без API-ключа движок ЧЕСТНО отдаёт DIAGNOSTICS «LLM unavailable» — тест переименован и ассертит честный путь |
| 8 | faststream `test_radar_handlers` (2 шт.) | fix-test | track store принимает транспондер только из SR-band (канон: LR транспондер не несёт); тесты слали RR_UNSPECIFIED → `range_band=RR_SR` в хелпере |
| 9 | `test_session_multiconsole` | — | порядковый эффект утечки №4; ушёл сам после fix-code |

## Scope / Non-goals

- In scope: только тестовая правда + один fix-code (env-утечка).
- Out of scope: подписчик SIM_POWER_PDU (forward-looking, потребитель —
  отдельное решение), поведение neural engine/track store (канонично).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related: память `full-test-scope-src-trees` (урок «полный прогон = оба скоупа»)

## Plan (steps)

1) Разведка с воспроизведением каждого красного (субагент). [сделано]
2) 9 правок по карте вердиктов. [сделано]
3) Досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence

`pytest src/qiki/services src/qiki/core -q -p no:warnings` → все точки, 100%,
0 FAILED; `tests/unit` 0 FAILED; ruff «All checks passed!».
