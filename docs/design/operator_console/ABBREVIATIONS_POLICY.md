# ORION Operator Console — Abbreviations Policy (EN/RU)

## Goal

Make the TUI readable at a glance (even in narrow tmux splits) **without losing meaning**. We allow abbreviations only when there is an immediate expansion path for both languages.

## Global rules

- Every user-facing label/value is **bilingual**: `EN/RU` (no spaces around `/`).
- Default: **no abbreviations** in user-facing text.
- If an abbreviation is necessary, it must be:
  - short and stable (not a one-off random shortening),
  - explained in **Help (F9)** under a **Glossary/Глоссарий** section,
  - and (when the widget supports it) expanded via **tooltip**.

## Allowed zones for abbreviations

1) **Table column headers** (DataTable)
   - Reason: columns must fit; headers are repeated constantly.
   - Requirement: every abbreviated column **must** be listed in Help glossary.

2) **Header compact blocks** (top “chrome”)
   - Reason: always-visible system overview must remain stable under resize.
   - Requirement: full expansion must exist in tooltip + in Help glossary.

3) **Dense status panels** (System dashboard widgets)
   - Reason: these panels are “glanceable” and width-limited in tmux splits.
   - Requirement: abbreviated units/labels must be listed in Help glossary (F9).

4) **Bottom keybar navigation** (F1…F10 strip)
   - Reason: the keybar must remain readable and stable at small widths.
   - Requirement: abbreviated screen names must be listed in Help glossary (F9).

## Forbidden zones for abbreviations

- **Inspector** (details panel) — show full words, full units.
- **Output/Console logs** — do not shorten text; keep it explicit.
- **Commands and error messages** — prefer clarity over compactness.

## Examples (canonical)

- `Sys/Систем` → `System/Система`
- `Events/Событ` → `Events/События`
- `Power/Пит` → `Power systems/Система питания`
- `Diag/Диагн` → `Diagnostics/Диагностика`
- `Mission/Миссия` → `Mission control/Управление миссией`
- `Bat/Бат` → `Battery/Батарея`
- `Rad/Рад` → `Radiation/Радиация`
- `Ext temp/Нар темп` → `External temperature/Наружная температура`
- `Core temp/Темп ядра` → `Core temperature/Температура ядра`
- `Fresh/Свеж` → `Freshness/Свежесть`
- `Ack/Подтв` → `Acknowledged/Подтверждено`
- `Vr/Скорость` → `Radial velocity/Радиальная скорость`
- `sec/с`, `min/мин`, `h/ч` → compact time units
- `SoC/Заряд` → `State of charge/Уровень заряда`
- `P in/Вх мощн` → `Power input/Входная мощность`
- `P out/Вых мощн` → `Power output/Выходная мощность` / `Power consumption/Потребляемая мощность`
- `Bus V/Шина В` → `Bus voltage/Напряжение шины`
- `Bus A/Шина А` → `Bus current/Ток шины`
- `CPU/ЦП` → `Central processing unit usage/Загрузка центрального процессора`
- `Mem/Пам` → `Memory usage/Загрузка памяти`
- `Age/Возраст` is not an abbreviation and is always allowed.

## Implementation checklist

- When adding/changing a label: confirm it’s `EN/RU` and not shortened.
- When introducing a new abbreviation: update Help glossary **in the same PR**.
- Run the TUI in a narrow split and confirm truncation uses `…` (not wrapping chaos).
