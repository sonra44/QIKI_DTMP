# TASK: Этап 8 «command-surface» — реестр команд, полный help, quit-confirm, палитра, cap-гейт PWR

**ID:** TASK_20260709_STAGE8_COMMAND_SURFACE
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 8 пакета `orion_playable_f1_f5_v1` (task-0051)
**Date created:** 2026-07-09

## Goal

Закрыть этап 8 (§F4 + Z2/G3): полный сгруппированный help, quit-confirm,
typed-команды в палитре Ctrl+P (single path через роутер), cap-гейт
суперконденсатора в чип PWR. Критерий §F4: новый оператор находит любую
команду через help или палитру, не читая исходников.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно: `help` выводит в консоль F4 полный список команд 7 группами
  (УРОВНИ/МИР/ПРОЦЕДУРЫ/QIKI/РЕШЕНИЯ/ФИЛЬТРЫ-СТРАНИЦЫ/СЕССИЯ), сверенный с
  фактическим роутером пином полноты; Ctrl+P содержит typed-команды
  (sim.start/pause/stop, q confirm/…, proc …, уровни) — безаргументные
  исполняются тем же роутером, аргументные префиллят ввод; `quit`/`exit`
  спрашивают подтверждение (повторный quit не наслаивает модалы); чип PWR
  несёт готовность к пиковому действию: `PWR OK 80% ~102м · cap 78% ▸БУСТ`.

## Reproduction Command

```bash
bash scripts/prove_orion_v_stage8.sh
```

## Before / After

- Before: `_show_help` — одна строка 160 симв., расходившаяся с роутером;
  quit — мгновенный `action_quit()`; палитра несла только 5 «Ф1»-записей —
  и ДАЖЕ ОНИ БЫЛИ МЕРТВЫ в проде: `from textual.command import SystemCommand`
  на textual 8.2.7 тихо падал в `except: return` (SystemCommand переехал в
  textual.app) — кастомный блок палитры не отдавал ни одной записи
  (бонус-находка этапа); порогов cap-гейта в shared не было, чип PWR не
  знал о суперконденсаторе.
- After: `command_registry.py` — ЕДИНЫЙ владелец командной поверхности
  (CommandSpec: name/aliases/group/summary/palette/arg_hint); help, палитра
  и пин полноты читают один реестр; роутер извлечён в
  `_route_typed_command(raw)` (Input и палитра — один путь со всеми
  гейтами); quit → `_request_quit_confirm` (ConfirmDialog + guard
  `_quit_confirm_open`; системная Textual-запись «Quit» тоже подменена);
  импорт SystemCommand — textual.app с фоллбэком (палитра ожила);
  `qiki/shared/supercap_gate.py` — владелец T_boost=0.6/T_hold=0.3
  (канон §13: SoC_cap = готовность к пику; числа — спека Z2), чип PWR несёт
  `· cap NN% ▸БУСТ|ДЕРЖ|СТАБ` (RU-коды — слой отображения), нет данных →
  сегмента нет.

## Impact Metric

- Метрика: RED-пакеты A-D + живой prove.
- Baseline: 7 RED failed + ImportError supercap (владелец отсутствовал);
  палитра в проде отдавала 0 кастомных записей.
- Target/Actual: **26 passed** (реестр двунаправленно: поведенчески
  реестр→роутер + AST роутер→реестр; help 7 групп ≤160; quit-confirm +
  guard; палитра single-path + only-registry-names; cap-границы
  60/30 включительно + чип 3 кода + честное отсутствие); полный tests/unit
  И src-деревья 0 FAILED; live prove **EXIT=0** (help/ACK-путь
  sim.start-stop/cap 78% ▸БУСТ из живой телеметрии/quit-модал+guard);
  мир возвращён в STOPPED (FAILED_PRECONDITION подтверждён).

## Scope / Non-goals

- In scope: command_registry.py (новый), shared/supercap_gate.py (новый),
  app.py (роутер/help/quit/палитра/префилл), operator_state.py (cap-сегмент),
  смок + prove, синхронная адаптация пина quit (R1).
- Out of scope (хвосты): унификация `_peak_state` (20/70,
  blocked/limited/ready — контур блокировок, запинован тестами) на
  shared-владельца — отдельный срез с собственными RED; перевод роутера
  на данные реестра (AST-пин тогда упростится до тождества); подписчик
  SIM_POWER_PDU.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs:
  - `04_F2_F3_F4_ZONES_SPEC.md` §F4, `06_COMMAND_SURFACE_CONTROL_PATH.md`
  - `03_F1_COCKPIT_SPEC.md` Z2/G3; RAG-грунт: BODY_CANON §13 (SoC_cap),
    bot_gdd Power Plane («Пороговая логика: T_boost/T_hold»)
  - Интернет-сверка Textual: command palette guide (Provider/COMMANDS),
    ModalScreen[bool] + guard от наслоения модалок

## Plan (steps)

1) RED A-D (7 failed + ImportError зафиксированы). [сделано]
2) Фиксы по зависимостям: реестр → экстракция роутера → help → quit →
   палитра (+починка мёртвого импорта SystemCommand) → shared-гейт → чип. [сделано]
3) Live prove + досье + гейты + коммит + main + рестарт консоли. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

```
[smoke] help: все 7 групп в консоли F4 ✓
[smoke] палитра→роутер: sim.start ушла живым ACK-путём ✓
[smoke] sim.stop отправлена — мир возвращается в STOPPED ✓
[smoke] чип PWR живьём: ▸ PWR OK 80% ~102м · cap 78% ▸БУСТ ✓
[smoke] quit → модал → n: консоль жива, guard снят ✓
[smoke] повторный quit снова спрашивает (после ответа) ✓
[smoke] Этап 8 PASS: командная поверхность честна на живом стеке
```

Мир после prove: STOPPED (FAILED_PRECONDITION подтверждён отдельной пробой).
Ruff: новые файлы чисты; 3 остатка в test_block0_console_hygiene (F401
uuid4 + 2×E501) — pre-existing (проверено stash-пробой).
