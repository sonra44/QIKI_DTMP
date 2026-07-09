# 09. Последовательность работ для CLI-агента

Статус: target spec. Правила: 1 этап = 1 ветка `task-<id>-<slug>`
(4+ цифры, CONTRIBUTING.md) = 1 PR = 1 досье `TASKS/TASK_*.md`.
Номера `<id>` — по ответу на Q6 (`_support/CLARIFICATION_REQUEST_001.md`).
Этапы 1–3 (Блок 0) — строго до любых UI-переработок. Этапы 5–9 можно
параллелить с 10 при непересекающихся файлах.

| Этап | Slug ветки | Содержание | Зависит от |
|------|-----------|------------|------------|
| 0 | `orion-playable-docs` | Внесение этого пакета (docs-only, если он ещё не в main-ветке), указатель в `docs/INDEX.md`, note «конкретизирован пакетом» в `F1_GAME_FIELD_REWORK.md`; ответ `CLARIFICATION_REPLY_001.md` | — |
| 1 | `block0-operator-body` | Дефекты 0.3, 0.4, 0.5: abort-гонка, голые create_task, TOCTOU пломбы. **Сначала легализовать/доделать незакоммиченный «блок 1» из рабочего дерева** (Q1 [BLOCKING]) | 0, ответ Q1 |
| 2 | `block0-radar-ingest` | Дефекты 0.1, 0.2, 0.9 + smoke `radar_track_visible` | 0 |
| 3 | `block0-state-honesty` | Дефекты 0.6, 0.7, 0.8, 0.11 | 0 |
| 4 | `console-med-hygiene` | Дефекты 0.12–0.17: голая `q`, f5/f8, полночь, pending/ACK, кэпы памяти, пороги→shared (закрывает часть приёмок C/D/E) | 1 |
| 5 | `f1-decompress` | Фаза G-A: уборка Z7, «Краткие факты» Z8, скрытие мёртвых кнопок Z9, подпись Z6. **Правка пин-теста №1** (синхронно с `03`) | 1 |
| 6 | `f1-radar-page` | Фаза G-B: страница РАДАР Z4 + derived-риск (G5) | 2 |
| 7 | `f1-qiki-voice` | Фаза G-C: лента `QIKI ▸` на F1 (Z7) + identity-строка Z3 (G-F) | 5 |
| 8 | `command-surface` | F4-аффорданс: полный `help`, палитра, quit-confirm (сверх этапа 4) + cap-гейт в чип PWR (Z2/G3) | 4 |
| 9 | `f1-context-actions` | Фаза G-D (часть): контекстные действия Z6 → intent → F5-контур. **Правка пин-теста №2** (синхронно с `06`) | 5, 7, стабильный F5 |
| 10 | `rcs-motion` | Дефект 0.10: интеграция RCS + фаза полёта Burn/Coast/Brake в «Наведение» (G2-гэп) | 3 |
| 11 | `runtime-30min-gate` | 30-мин smoke, приёмочный прогон всех карточек `07`, обновление `CURRENT_STATE.md`, закрытие DoD G1 | все |

## Обязанности на каждом этапе (DOCUMENTATION_UPDATE_PROTOCOL.md)

1. Досье `TASKS/TASK_<дата>_<slug>.md` по `TASKS/TEMPLATE_TASK.md`
   с анти-луп-секциями и Evidence.
2. Обновление `CURRENT_STATE.md (snapshot)` при изменении поведения.
3. Обновление борда `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md` (доступен только
   CLI-агенту).
4. PR: гейты из `08_VERIFICATION_PLAN.md`, ревью `load` / `Sourcery` /
   `CodeRabbit` / `@codex review`.

## Правило остановки последовательности

Если этап вскрывает, что дефект уже исправлен иначе (живая работа вне
пакета), — не чинить второй раз: зафиксировать в
`CLARIFICATION_REPLY_<NNN>.md` и скорректировать план следующего этапа.
