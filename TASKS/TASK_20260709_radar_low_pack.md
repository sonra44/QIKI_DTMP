# TASK: LOW-пакет радарной зоны — LRU-кэп консоли, guard смока, решения по хвостам

**ID:** TASK_20260709_RADAR_LOW_PACK
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез task-0045 (LOW-строки карты `AUDIT_2026-07-09_POSTFIX.md` + пост-ревью 0043)
**Date created:** 2026-07-09

## Goal

Закрыть радарно-консольные LOW кодом там, где дефект реален, и
задокументированным решением там, где «фикс» был бы вслепую.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: при полном кэпе треков (128) непрерывно сопровождаемый
  контакт больше не выселяется из памяти консоли раньше редких новых —
  сопровождение не мерцает под нагрузкой.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_radar_low_pack.py -q
```

## Before / After

- Before: кэп `_latest_radar_tracks` — FIFO по первой вставке (dict держит
  позицию ключа при обновлении): обновляемый трек сидел в голове словаря и
  выселялся кэпом раньше редких новых — тот же класс дефекта, что M6 в
  мозговой WorldModel; смок track_visible читал `frame.sensor_id` без
  guard'а — гейт, закрывшийся между чтениями, ронял его AttributeError
  на None вместо честного сообщения.
- After: `_on_track` перевставляет ключ (pop → insert) — LRU, живой трек
  не выселяется; смок падает с честным «гейт закрылся между кадрами
  (STOPPED/обесточка?)».

## Impact Metric

- Метрика: RED-тест `test_latest_radar_tracks_cap_is_lru_not_fifo`.
- Baseline: 1 failed (живой обновляемый трек выселен FIFO-кэпом).
- Target/Actual: **1 passed**; смежные (f1_radar_page + staleness) зелёные;
  полный `tests/unit` 0 FAILED; live-смок track_visible EXIT=0.

## Scope / Non-goals — решения по каждому LOW радарной зоны

- [x] **Консольный FIFO-кэп** → LRU-перевставка (код, RED→GREEN).
- [x] **Смок: sensor_id без guard / FAILED_PRECONDITION=STOPPED** → guard +
  честная формулировка «гейт закрыт (STOPPED ИЛИ обесточка)» (код).
- [зафиксировано, без кода] **`_on_track` без `_request_refresh_ui`** —
  осознанное решение этапа 6 подтверждается: при живом стеке телеметрия
  тикает постоянно и страница обновляется её refresh'ем; refresh-на-трек =
  шторм при 128 треках. Чинить только по live-evidence залипания
  (троттлированный refresh отдельным срезом).
- [зафиксировано, без кода] **«охват 360°» на target/sensors-путях** —
  канон-грунт (RAG, bot_gdd.md «Роли сенсоров»): «Радар (360°): непрерывный
  круговой обзор» — охват есть свойство радара, строка честна на любом
  пути, где рендерятся радарные треки. Не дефект.
- [отложено, отдельный срез] **intents `previous_radar_ts` / 8с-столл на
  паузе** (карта, LOW): свежесть радара в warmup — строковое неравенство
  timestamp'ов; на паузе timestamp заморожен → observation-команды честно
  ждут весь warmup-timeout. Это поведенческая логика observation-контура
  (не точечный фикс): нужен RED-контур «наблюдение на паузе» и решение
  семантики («на паузе свежий радар невозможен» → ранний precondition-ответ
  или принятие замороженного кадра). В LOW-пакет не влезает по риску.
- Вне радарной зоны (не взяты сознательно): app.py-гигиена (on_unmount
  `_bg_tasks`, дубль incident_open, `Q:`-капс, help_visible-дефолты,
  палитра/Help, cockpit `vm is None`), пороги `<`/`<=` SoC, legacy-копия
  порога в main_orion.py, grpc_data_provider ValueError→SAFE — кандидаты
  ближайших срезов по своим файлам (рекомендация карты: «соединить с
  ближайшими этапами по файлам»).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/dev/AUDIT_2026-07-09_POSTFIX.md` (LOW-секция)
  - `TASKS/TASK_20260709_radar_staleness.md` (срез-предшественник)

## Plan (steps)

1) RED LRU-теста (1 failed зафиксирован) → фикс → GREEN. [сделано]
2) Guard смока + живой прогон (3/3 цикла, мир возвращён в STOPPED). [сделано]
3) Досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. RED: «кэп выселил непрерывно обновляемый трек (FIFO по первой вставке
   вместо LRU)»; GREEN после pop→insert: 1 passed + смежные 25 passed.
2. Live-смок с guard'ом (PROBE_CYCLES=3):

```
[smoke] sensor_id стабилен между кадрами: e46bc6f6-… ✓
[smoke] циклов с радаром: 3/3 (100%); чтений до радара: [3, 3, 3]; «0 треков при живом контакте»: 0
[smoke] возвращаю сим в исходное состояние: sim.stop
[smoke] Этап 2 PASS: радарный ingest честен на живом стеке
```
