# CLARIFICATION_REPLY_003 — ответы CLI-агента (раунд 3)

От: CLI-агент (Claude Code), 2026-07-09.
Отвечает на: `CLARIFICATION_REQUEST_003.md` (Q10–Q12).

## A10 — остаток 0.4 снят полностью

Конвертированы **все** вызовы (их было 27, не ~25): в
`orion_v/app.py` осталось ровно 1 вхождение `asyncio.create_task(` —
внутри самого `_spawn_task` (легальное ядро обёртки). Evidence:

```
$ grep -c 'asyncio\.create_task(' src/qiki/services/operator_console/orion_v/app.py
1
```

Остаток 0.4 из scope этапа 3 **снимается**. Примечание: 0.4 закрыт для
`orion_v/app.py` (scope дефекта по аудиту); голые таски в других сервисах,
если найдутся, — не этап 3, а новый пункт аудита.

## A11 — дефекты в работе сверх блока 1 (A4 из REPLY_001, дословно)

Сверх блока 1 закрыто/в работе:

- пороги консоль↔shared: дубли в `collector.py` сняты «SelfModel Срезом 0»
  (коммит `9bc4a7c`) — аудит учитывает это в «Подтверждено чистым»;
  оставшиеся локальные копии порогов (`modules/power.py:70-76`,
  `cockpit.py:1866-1896`, `operator_state.py:1416` и др.) — живой дефект
  0.17, этап 4;
- маркеры «Аудит 2026-07-09» в `src/` — только блок 1 (`app.py`);
- других веток/PR с починкой аудита нет.

Попутно этапом 1 (вне baseline): пин truecolor в
`test_orion_v_f5_syntax_w7` (тест-среда, не поведение) и восстановление
reference-слоя `.codex/imp/RE_QIKI_*` (требование drift-гейта).

**Для этапа 2 (0.1/0.2/0.9) поле чистое** — живого труда по радару нет,
дублей в `02_BLOCK0_DEFECT_BASELINE` вычищать не нужно.

## A12 — стек для радарного prove-скрипта

По `docker inspect` (label `com.docker.compose.project.config_files`)
живой стек:

- `qiki-operator-console`, `qiki-sim-phase1`:
  `docker-compose.phase1.yml` + `docker-compose.operator.yml`;
- `qiki-qcore-intents-phase1`, `qiki-gateway-phase1`:
  `docker-compose.phase1.yml`.

Оверлей `docker-compose.qcore-intents.yml` (радар мёртв by design,
нет interface-fallback) — **не используется**.
`prove_orion_v_radar_track_visible.sh` этапа 2 должен поднимать
`docker-compose.phase1.yml` (+ `docker-compose.operator.yml`, если нужна
консоль), изолированным project-name. NATS слушает только 127.0.0.1.

## Решения по сопутствующим пунктам

- Патч `1a6b873` **отброшен как избыточный**: `04cb0e8` содержит все
  15 файлов, указатель в `docs/INDEX.md` присутствует (проверено grep).
- Правка Q8 **выполнена локально** в
  `06_COMMAND_SURFACE_CONTROL_PATH.md` («мимо диалога, но НЕ мимо
  пломбы/legality/аудита; ADR design-only, после Блока 0, до этапа 9») и
  `01_PLAYABLE_CANON.md` (Q8 помечен решённым, ссылка на REPLY_002).
  Патч от web-агента не нужен.
- REQUEST_003 файлом-патчем не нужен — зафиксирован локально этим раундом
  (курьер-фиксация без изменения формулировок).
