
Цель: зафиксировать **регламентное** ТЗ для внедрения виртуализации Sensor Plane (бортовые сенсоры) в проекте **QIKI_DTMP** так, чтобы:
- соблюсти **no‑mocks policy** (в UI только реальные данные симуляции или честное `N/A/—`);
- не создавать **дубли** и “вторые источники правды”;
- не добавлять `*_v2.*` и параллельные контракты/subject’ы.

ТЗ написано так, чтобы его можно было показать стороннему инженеру/модели без доступа к репозиторию.

---

## 0) Контекст (не обсуждается)

1) Проект — **симуляция / Digital Twin**. “Железо” бота виртуальное.  
2) “Реальные данные” в рамках проекта — это **simulation‑truth** (детерминированные вычисления), а **не** метрики VPS/контейнера.  
3) **Запрещено**:
   - добавлять `*_v2.*` (например, `sensor_v2`, `telemetry_v2`, `imu_v2` и т.п.);
   - заводить второй `bot_config`/`bot_spec`/`sensor_spec` с дублирующим содержимым.
4) Разрешено:
   - расширять **существующий** `src/qiki/services/q_core_agent/config/bot_config.json` новыми параметрами;
   - расширять **существующую** телеметрию `qiki.telemetry` (в `TelemetrySnapshotModel` разрешены `extra`);
   - использовать текущие сервисы/каналы (без новых `.proto`).

---

## 1) Каноничные документы/артефакты (источник правды)

**Текстовый SoT (человекочитаемый):**
- `docs/design/hardware_and_physics/bot_source_of_truth.md` (раздел 5.2 Sensor Plane)
- `docs/operator_console/REAL_DATA_MATRIX.md`

**Машиночитаемые (приоритет выше текста):**
- `src/qiki/services/q_core_agent/config/bot_config.json` — runtime профиль “железа” (Sensor Plane параметры/включение)

---

## 2) Проблема, которую решаем

Сейчас UI/телеметрия покрывает часть “сенсорной картины” (attitude/thermal/radiation), но Sensor Plane как слой:
- не выделен как набор подсистемных измерений/статусов;
- не даёт оператору честной диагностики (что измеряется, что недоступно, почему);
- не имеет расширения по навигационным/вспомогательным сенсорам (proximity/solar/star tracker/magnetometer).

Нужно:
- добавить минимально‑достаточную, детерминированную виртуализацию Sensor Plane, пригодную для ORION, без “красивых нулей”.

---

## 3) Scope

### 3.1 Must‑have (обязательно в MVP)

1) **Sensor Plane в симуляции (`q_sim_service`)**
   - симуляция должна публиковать слой `sensor_plane.*` в `qiki.telemetry`:
     - статусы “есть данные / нет данных” (без моков),
     - минимальный набор измерений.

2) **Единый источник параметров**
   - `hardware_profile.sensor_plane` в `bot_config.json` содержит включение и состав сенсоров (какие блоки активны).
   - параметры, которые уже канонично живут в других plane‑блоках (например `thermal_plane`, `power_plane`, `docking_plane`) **не дублируются** в sensor_plane.

3) **Телеметрия (формат)**
   - добавляется top‑level ключ `sensor_plane` (разрешён как `extra` в TelemetrySnapshot v1).
   - минимум:
     - `sensor_plane.imu`:
       - `enabled: bool`
       - `ok: bool | null`
       - `roll_rad/pitch_rad/yaw_rad` **не переносим** (они уже каноничны как top‑level `attitude.*`), но допускаем `yaw_rate_rps`/`roll_rate_rps`/`pitch_rate_rps` как производные.
     - `sensor_plane.radiation`:
       - `enabled: bool`
       - `background_usvh: float | null` (канон остаётся `radiation_usvh`, здесь — алиас/объяснение не обязателен)
       - `dose_total_usv: float | null` (интеграл по времени симуляции)
     - `sensor_plane.proximity`:
       - `enabled: bool`
       - `min_range_m: float | null`
       - `contacts: int | null`
     - `sensor_plane.solar`:
       - `enabled: bool`
       - `illumination_pct: float | null`
     - `sensor_plane.star_tracker`:
       - `enabled: bool`
       - `locked: bool | null`
       - `attitude_err_deg: float | null`
     - `sensor_plane.magnetometer`:
       - `enabled: bool`
       - `field_ut: {x: float, y: float, z: float} | null`

   Принцип no‑mocks:
   - если сенсор выключен → `enabled=false`, остальные поля `null`;
   - если включен, но модель/данные не готовы → поля `null` (и в UI это `N/A`), без “0.0”.

4) **ORION UI (no‑mocks)**
   - добавить экран/таблицу “Sensors / Сенсоры” (или расширить Diagnostics) и показывать:
     - включено/доступно (enabled/ok/locked),
     - ключевые значения (dose_total, min_range, illumination, field vector),
     - `N/A` если данных нет.
   - никаких имитаций прогресс‑баров, если значения `null`.

5) **Тесты**
   - unit‑тест в `q_sim_service`:
     - `sensor_plane` присутствует в payload телеметрии;
     - при `enabled=false` значения `null`;
     - `dose_total_usv` монотонно не убывает при шаге симуляции (если radiation включён).
   - unit‑тест в `operator_console` (если есть парсер/рендер для сенсоров):
     - при отсутствии `sensor_plane` UI не падает и показывает `N/A`.

---

### 3.2 Out of scope (явно НЕ делаем в MVP)

- Реальный доступ к аппаратным датчикам (I2C/SPI/GPIO).
- Сложная физика (световые модели/звёздные каталоги/магнитные карты Земли).
- Статистический шум, если он не детерминирован (random без seed запрещён).
- Полный R.L.S.M (радар/лидар/спектрометр/магнитометр как единый perception) — это отдельный следующий блок.

---

## 4) Параметры в `bot_config.json` (без дублей)

Добавить/поддержать в `hardware_profile` секцию (пример):

```json
{
  "hardware_profile": {
    "sensor_plane": {
      "enabled": true,
      "imu": {"enabled": true},
      "radiation": {"enabled": true},
      "proximity": {"enabled": false},
      "solar": {"enabled": false},
      "star_tracker": {"enabled": false},
      "magnetometer": {"enabled": false}
    }
  }
}
```

Важно:
- `thermal_plane` и его узлы остаются отдельным каноном (Sensor Plane не копирует температуры узлов).
- Docking измерения тока/напряжения/температуры остаются в Power Plane (`power.dock_*`) и Thermal Plane (`dock_bridge` node); Sensor Plane не дублирует эти числа.

---

## 5) Критерии приёмки (DoD)

Считаем задачу выполненной, если:
1) В Docker‑стеке `phase1` симуляция публикует `sensor_plane.*` в `qiki.telemetry` (реальные значения или `null`, без моков).
2) ORION отображает сенсоры корректно (без падений, `N/A` если данных нет).
3) `pytest` для `q_sim_service` зелёный, есть тесты на `sensor_plane` и `dose_total_usv`.
4) Не добавлены `*_v2.*`, не создано дублирующих источников правды.

