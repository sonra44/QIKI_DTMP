# TASK: F1 decompress — dark cockpit, Краткие факты, подписи MFD

**ID:** TASK_20260709_F1_DECOMPRESS
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 5 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Фаза G-A (`03_F1_COCKPIT_SPEC.md` Z5-Z9): F1 перестаёт быть обучалкой
разработчика — экран тёмный и операторский по умолчанию, справка по H.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно глазами: при старте F1 панель QIKI/ОПЕРАТОР чистая — нет блока
  КЛАВИШИ/СПРАВКА/ПАЛИТРА/ПОДСКАЗКИ и строки учебного цикла; одна строка
  «H — справка | Ctrl+P — палитра»; H возвращает обучалку. Рамки MFD
  подсказывают «перекл. страниц: [ / ]». В «Кратких фактах» нет рядов-пустышек
  «—» — пустые группы схлопнуты строкой «нет данных: …». Заголовок корпуса —
  «КОРПУС (посев)», не «BODY STRUCTURE».
- Ограничение: один цикл = один сценарий (декомпрессия; радар-страница — этап 6,
  голос QIKI — этап 7, контекстные действия — этап 9).

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_f1_decompress.py -q
```

## Before / After

- Before: `help_visible` по умолчанию True — с первого кадра на экране
  КЛАВИШИ/СПРАВКА/ПАЛИТРА/ПОДСКАЗКА×2 + строка учебного цикла (подтверждено
  живым скрином panе w1:pW); «Краткие факты» рисовали ряды «—» при отсутствии
  данных; заголовок «BODY STRUCTURE | …» на русской консоли; рамки MFD без
  подсказки переключения.
- After: dark cockpit — дефолт Help·OFF (обучалка по H, DISPLAY_CANON T0);
  build_quick_fact_rows: только непустые ряды + «нет данных: SAFETY, THERMAL»;
  «КОРПУС (посев) | …» (поля-коды не тронуты); border_subtitle обеих MFD-рамок
  = «перекл. страниц: [ / ]».

## Impact Metric

- Метрика: строк обучалки на стартовом экране F1 (панель QIKI/ОПЕРАТОР).
- Baseline: 7+ строк (КЛАВИШИ, СПРАВКА, ПАЛИТРА, 2×ПОДСКАЗКА, цикл, ФОКУС-остатки).
- Actual: 1 строка («H — справка | Ctrl+P — палитра»); обучалка целиком
  доступна по H (пин-тест).

## Scope / Non-goals

- In scope: Z7-дефолт, Z8 (факты+заголовок), Z6-подпись, синхронная правка
  пин-теста №1 (риск R1 из 08_VERIFICATION_PLAN, предусмотрено).
- Out of scope: Z2 cap-гейт (этап 8), Z3 идентичность (этап 7), Z4 радар
  (этап 6), Z6 контекстные действия (этап 9); Z9 и снятие acceptance-чеклиста
  сделаны ранее (DISPLAY_CANON №8/№9) — покрыты существующими пинами.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/03_F1_COCKPIT_SPEC.md` (Z5-Z9)
  - `docs/design/operator_console/F1_GAME_FIELD_REWORK.md` (фаза G-A)

## Plan (steps)

1) RED-тесты (`tests/unit/test_f1_decompress.py`, 5 шт.). [сделано]
2) Фиксы: help-дефолт OFF; build_quick_fact_rows; КОРПУС (посев);
   MFD_PAGE_SWITCH_SUBTITLE. [сделано]
3) Синхронная адаптация пин-тестов (7 шт. в 4 файлах). [сделано]
4) Живой тест + рестарт консоли оператора. [сделано]
5) Досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита этапа

## Evidence (commands → output)

1. RED: ImportError/ассерты до фиксов; GREEN: `test_f1_decompress.py` 5 passed;
   адаптированные пины: f1_first_playable_loop + 3 body-structure файла —
   `37 passed` суммарно.
2. Полный `tests/unit`: 0 FAILED. Ruff: мой дифф не добавил ошибок
   (6 pre-existing E501, тот же счёт на чистом HEAD, stash-проверено).
3. Живой pilot-прогон (in-container, канонный live-формат):

```
[live] старт: обучалка скрыта, одна строка-подсказка ✓
[live] H: обучалка вернулась (КЛАВИШИ + учебный цикл) ✓
[live] рамки MFD: подпись «перекл. страниц: [ / ]» ✓
[live] правый MFD: BODY STRUCTURE не светится ✓
[live] Этап 5 PASS: pilot-прогон на живом коде
```

4. Консоль оператора (pane w1:pW) перезапущена на новый код (контейнер +
   вью канонным run_orion_v_live.sh): панель QIKI/ОПЕРАТОР чистая, обучалки
   нет — видимая дельта против скрина «до» (07:4x, блок КЛАВИШИ/ПОДСКАЗКИ).
