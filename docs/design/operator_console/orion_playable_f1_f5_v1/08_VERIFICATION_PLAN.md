# 08. План верификации

Статус: target spec.

## Пин существующего поведения (не должны краснеть)

Ни на одном этапе, кроме явно объявленных правок (этапы 5 и 9), не краснеют:

- `tests/unit/test_orion_f1_first_playable_loop.py` — учебный цикл F1
  (меняется ТОЛЬКО на этапах 5/9 синхронно с `03`/`06`, см. риск R1);
- m5-спуф: `tests/unit/test_orion_v_qiki_approve_m6.py`,
  `test_command_decision_m5.py`, smoke
  `tools/orion_v_qiki_decision_spoof_deny_smoke.py` — неприкосновенны;
- QIKI-контур: `tests/unit/test_orion_v_qiki_loop.py` (~40 тестов),
  `test_orion_v_f5_hand_confirm*.py`, `test_orion_v_qiki_dialog_f5.py`;
- смоки: `tools/orion_v_f1_quick_actions_smoke.py` (до этапа 5),
  `tools/orion_v_qiki_release_dock_smoke.py`,
  `tools/orion_v_qiki_dialog_f5_smoke.py`,
  `tools/qiki_decision_body_bridge_smoke.py`.

## Новые unit-тесты (по этапам)

| Этап | Тест |
|------|------|
| 1 | guard `proc.status` после await (abort-гонка); `_spawn_task` не теряет исключения; digest-drift в bridge (`BRIDGE_SEAL_DIGEST_DRIFT` — начат в рабочем дереве, Q1) |
| 2 | per-sensor `_frame_derived_track_ids` (кадр IMU не сносит радарные треки); фиксированный sensor_id; GetRadarFrame при паузе/обесточке |
| 3 | FSM: ERROR_STATE не читается как PAUSED; actuator RpcError → accepted=False → SAFE; refresh через to_thread не блокирует loop (таймингом) |
| 4 | голая `q` → подсказка; quit → подтверждение; f5/f8 в переключателе; полуночная сортировка (23:59/00:01); сброс `_pending_ack_command_id`; кэпы `_latest_radar_tracks`/`DecisionStore`; эквивалентность порогов shared↔консоль |
| 5 | обновлённый пин-тест F1 (декомпрессия Z7; инвариант «ничего в qiki.commands.control с F1» — новым тестом) |
| 6 | радарная страница: рендер трека, «эфир чист», derived-риск с пометкой |
| 7 | лента `QIKI ▸` (2–3 реплики), identity-строка Z3 |
| 9 | контекстные действия: сцена → набор действий; выбор публикует intent (и НЕ публикует control); интеграция с F5-кандидатом |
| 10 | RCS: смещение позиции после fire за N тиков |

## Новые смоки/prove-скрипты

- `tools/orion_v_radar_track_visible_smoke.py` +
  `scripts/prove_orion_v_radar_track_visible.sh` (этап 2).
- `tools/orion_v_f1_context_actions_smoke.py` +
  `scripts/prove_orion_v_f1_context_action_release.sh` (этап 9).
- `scripts/prove_orion_v_rcs_motion.sh` (этап 10).
- `tools/orion_v_runtime_30min_smoke.py` +
  `scripts/prove_orion_v_runtime_30min.sh` (этап 11): headless Textual pilot
  при живом стеке; длительность `ORIONV_SMOKE_DURATION_S` (1800 дефолт,
  120 CI); ассерты каждые N секунд:
  - NATS connected;
  - посеянный контакт не исчезает из треков;
  - RSS процесса консоли не растёт монотонно (кэпы работают);
  - лента диалога монотонна по ts;
  - 0 unhandled exceptions.

Образец исполнения смоков — существующие `tools/orion_v_*_smoke.py`
(`app.run_test(...)`, standalone `asyncio.run(main())`).

## Гейты на каждый PR (Docker-first)

```bash
bash scripts/branch_policy_check.sh
bash scripts/quality_gate_docker.sh          # финальный этап: QUALITY_GATE_PROFILE=full
bash scripts/qiki_drift_audit.sh --strict
bash scripts/ops/anti_loop_gate.sh           # требует досье TASKS с точными секциями
```

Для docs-этапов дополнительно:

```bash
bash scripts/check_no_second_task_board.sh
bash scripts/check_reference_truth_boundaries.sh
```

## Порядок доказательства этапа

1. Unit/смоки этапа зелёные локально (в Docker).
2. Prove-скрипт этапа зелёный, вывод записан в досье
   (`## Evidence (commands → output)`).
3. Гейты PR зелёные; PR по шаблону с секциями
   `## Visible Delta for Operator`, `## Before / After Command Transcript`,
   `## Impact Metric`.
4. Только после этого в досье/доках допускается слово `implemented`.
