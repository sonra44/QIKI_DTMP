
Цель: добавить трассируемость `hardware_profile_hash` во **всех критических местах** (BIOS → телеметрия → ORION) без моков, без `v2`, без дублей источников правды.

---

## 0) Контекст и запреты (не обсуждается)

1) Проект — **симуляция / Digital Twin**. “Реальные данные” = **simulation‑truth**, а не метрики VPS/OS.  
2) Запрещено:
   - добавлять `*_v2.*` (ни файлов, ни subject’ов);
   - заводить параллельный “канон” профиля железа (`bot_physical_specs.json` и т.п.) ради хэша.
3) Разрешено:
   - расширять существующие модели/JSON (backward compatible);
   - добавлять новые ключи в `qiki.telemetry` как `extra` (TelemetrySnapshot v1 допускает).

---

## 1) Source of Truth

- Runtime профиль железа (канон): `src/qiki/services/q_core_agent/config/bot_config.json`
- Интенция (текст): `docs/design/hardware_and_physics/bot_source_of_truth.md` (раздел 11.2)
- BIOS дизайн: `docs/design/q-core-agent/bios_design.md` (пример `hardware_profile_hash: sha256:...`)

---

## 2) Определение `hardware_profile_hash`

### 2.1 Что хэшируем

Хэш должен отражать именно “железный профиль”, а не случайные runtime‑поля.

Хэшируем только подмножество `bot_config.json`:
- `hardware_profile`
- `hardware_manifest`

### 2.2 Как хэшируем (детерминированно)

- алгоритм: SHA‑256
- вход: JSON сериализация **с сортировкой ключей** и компактными разделителями
- кодировка: UTF‑8
- формат строки: `sha256:<64 hex>`

Пример: `sha256:bd1c10a...e4c1` (в UI может быть обрезан визуально, но в raw/inspector должен быть полный).

---

## 3) Где должно появиться (минимум)

### 3.1 BIOS (q-bios-service)

- В `BiosStatus` добавить поле (backward compatible): `hardware_profile_hash: str | None`.
- `/bios/status` должен возвращать `hardware_profile_hash` если `bot_config.json` читается.
- Если `bot_config.json` не читается → `hardware_profile_hash` отсутствует/`null` (no-mocks).

### 3.2 Телеметрия (qiki.telemetry)

- В `q_sim_service` добавить top-level ключ в telemetry snapshot (как extra): `hardware_profile_hash`.
- Значение должно совпадать с BIOS (если оба читают один и тот же `bot_config.json`).

### 3.3 ORION UI

- В `Diagnostics` показывать строку:
  - `Hardware profile hash/Хэш профиля`
  - `N/A/—` если ключ отсутствует
- Цель: оператор всегда видит, “какой профиль железа сейчас крутится”.

---

## 4) Тесты

1) Unit-тест для shared util:
   - одинаковый input → одинаковый hash
   - изменение любой детали в `hardware_profile` → другой hash
2) `q_sim_service`:
   - `_build_telemetry_payload()` содержит `hardware_profile_hash` и он выглядит как `sha256:<64hex>`.
3) `q_bios_service`:
   - `build_bios_status()` возвращает `hardware_profile_hash` если config читается.

---

## 5) Критерии приёмки (DoD)

Считаем задачу выполненной, если:
1) BIOS и Telemetry содержат `hardware_profile_hash` в продакшен‑пути (Docker).
2) ORION отображает его в `Diagnostics` без моков.
3) `pytest` зелёный по добавленным тестам.
4) Нет `v2`, нет параллельных SoT.

