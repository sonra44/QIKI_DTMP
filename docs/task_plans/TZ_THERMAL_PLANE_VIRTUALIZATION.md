# ТЗ (MVP): Thermal Plane виртуализации “железа” QIKI (без дублей, без v2)

Цель: зафиксировать **регламентное** ТЗ для реализации Thermal Plane (виртуализации тепла) в проекте **QIKI_DTMP** так, чтобы:
- соблюсти **no-mocks policy** (в UI только реальные данные симуляции или честное `N/A/—`);
- не создавать **дубли** и “вторые источники правды”;
- не добавлять `*_v2.*` и параллельные контракты.

ТЗ написано так, чтобы его можно было показать стороннему инженеру/модели без доступа к репозиторию.

---

## 0) Контекст (не обсуждается)

1) Проект — **симуляция / Digital Twin**. “Железо” бота виртуальное.  
2) Температуры/узлы — это **simulation-truth**, а не метрики VPS/контейнера.
3) **Нельзя**:
   - добавлять `*_v2.*` ради удобства;
   - заводить “второй” bot_spec/bot_config/thermal_spec.
4) Разрешено:
   - расширять **существующий** `src/qiki/services/q_core_agent/config/bot_config.json` новыми полями (как единственный runtime SoT);
   - расширять **существующую** телеметрию `qiki.telemetry` (под `thermal.*`), соблюдая строгую валидацию.

---

## 1) Каноничные документы/артефакты (источник правды)

**Текстовый SoT (человекочитаемый):**
- `docs/design/hardware_and_physics/bot_source_of_truth.md`
- `docs/operator_console/REAL_DATA_MATRIX.md`

**Машиночитаемые (приоритет выше текста):**
- `src/qiki/services/q_core_agent/config/bot_config.json` — runtime профиль “железа”

**Смежные (контекст):**
- `docs/design/hardware_and_physics/mcqpu_cpu_ram_telemetry.md` — принцип “виртуального железа”
- `docs/task_plans/high_priority_tasks.md` / `docs/STEP_A_ROADMAP.md` — STEP‑A (RCS/Docking/XPDR) и зависимости

---

## 2) Проблема, которую решаем

Сейчас:
- в телеметрии есть `thermal` и `thermal.nodes[]`, но это часто пусто/не выражает модель;
- ORION не может показывать “реальную термо‑картину” (без демо‑нулей), а Power Plane уже зависит от термо‑ограничений (NBL, будущие RCS пики).

Нужно:
- внедрить **простую, детерминированную** термо‑модель (MVP) по принципу “thermal network / lumped nodes”:
  - узлы (nodes) с температурой и тепловой ёмкостью;
  - нагрев от нагрузок (MCQPU/PDU/supercap/dock/NBL/…);
  - теплообмен с внешней средой и (опционально) между узлами;
  - пороги перегрева, которые влияют на разрешения нагрузок (power shedding) **без моков**.

Примечание по методологии: это классический подход “lumped parameter thermal network”, где элементы агрегируются в узлы (C) и связи (R), и температура интегрируется по уравнениям теплового баланса.

---

## 3) Scope

### 3.1 Must‑have (обязательно в MVP)

1) **Thermal Plane в симуляции**:
   - модель узлов `thermal.nodes[]` обновляется на каждом `sim_tick`;
   - значения детерминированны (одинаковые входы → одинаковые выходы).
2) **Единый источник параметров**:
   - параметры термо‑модели живут в `bot_config.json` (одна истина).
3) **Телеметрия**:
   - `qiki.telemetry` содержит `thermal.nodes[]` (реальные значения или пусто/`N/A`, но без подстановок).
   - `temp_core_c`/`temp_external_c` должны быть консистентны с узлами (см. раздел 6).
4) **Интеграция с Power Plane** (минимум):
   - если температура core/pdu превышает пороги — Power Plane должен ограничивать нагрузку (например, запрещать NBL и/или сбрасывать не‑критичные нагрузки) **реально**.
5) **ORION UI**:
   - отдельная таблица/экран Thermal (или расширение Diagnostics) показывает узлы и температуры;
   - при отсутствии данных — честные `N/A/—` (no-mocks).
6) **Тесты**:
   - unit‑тесты на нагрев/охлаждение + влияние порога (без Docker e2e, но пригодно к запуску в `qiki-dev`).

### 3.2 Out of scope (явно НЕ делаем в MVP)

- CFD/FEA, сложная геометрия, лучистый теплообмен и т.п.
- “Красивые” теплокарты, если нет реальных данных.
- Исторический replay/TSDB (Grafana можно подключать позже, когда стабилизирован контракт).

---

## 4) Термины и сущности

**Thermal Node** — изотермический узел (агрегат), например:
- `core` (MCQPU core)
- `battery`
- `pdu`
- `supercap`
- `dock_bridge`
- `hull` (корпус/радиаторы)
- `rcs_cluster_A/B/C/D` (для будущего RCS этапа; в MVP можно подготовить структуру, но можно не включать)

**External environment** — `temp_external_c` (уже есть в телеметрии, используется как “ambient”).

---

## 5) Единственный источник параметров (bot_config.json)

Добавить в `hardware_profile` новый раздел (примерная форма; имена полей финализируются при реализации):

```json
{
  "hardware_profile": {
    "thermal_plane": {
      "enabled": true,
      "ambient_exchange_w_per_c": 0.5,
      "nodes": [
        { "id": "core", "heat_capacity_j_per_c": 800.0, "cooling_w_per_c": 0.8, "t_init_c": 25.0, "t_max_c": 90.0 },
        { "id": "pdu",  "heat_capacity_j_per_c": 600.0, "cooling_w_per_c": 0.6, "t_init_c": 25.0, "t_max_c": 95.0 },
        { "id": "battery", "heat_capacity_j_per_c": 1200.0, "cooling_w_per_c": 0.3, "t_init_c": 20.0, "t_max_c": 70.0 }
      ],
      "couplings": [
        { "a": "core", "b": "pdu", "k_w_per_c": 0.2 }
      ]
    }
  }
}
```

Правила:
- **Никаких** вторых файлов‑контрактов (`thermal_spec.json` запрещён).
- Можно добавлять поля/узлы, но только внутри `bot_config.json`.

---

## 6) Контракт телеметрии (qiki.telemetry)

Текущий контракт (см. `REAL_DATA_MATRIX`) уже предполагает `thermal.nodes[].{id,temp_c}`.

Требования:
1) `thermal.nodes[]` содержит **реальные** температуры узлов (float, °C).
2) Если thermal plane отключён/не настроен:
   - `thermal.nodes` может быть пустым,
   - ORION показывает `N/A/—` (никаких “0.0°C”).
3) `temp_core_c`:
   - должен соответствовать `thermal.nodes[id=core].temp_c`, если узел `core` существует;
   - иначе может оставаться как есть (но **без** искусственных значений).

---

## 7) Алгоритм термо‑модели (MVP, детерминированный)

Рекомендуемая модель: **lumped nodes** (узлы) + простая интеграция:

Для узла `i`:

`dT_i/dt = (Q_i - cooling_i*(T_i - T_amb) - Σ_k k_ik*(T_i - T_k)) / C_i`

где:
- `C_i` — тепловая ёмкость узла (J/°C)
- `cooling_i` — линейное охлаждение в ambient (W/°C)
- `k_ik` — теплопроводность связи между узлами (W/°C)
- `Q_i` — тепловыделение (W) от нагрузок
- `T_amb` — `temp_external_c`

Интеграция: явный Euler на шаге `dt = sim_tick_interval` (достаточно для MVP).

Почему так: это стандартный reduced‑order подход “thermal network”, применяемый в инженерной практике для быстрых моделей.

---

## 8) Источники тепла (Q_i)

MVP‑источники (реальные из текущей симуляции):
- MCQPU / CPU load → `Q_core_w` (пропорционально cpu_usage_pct)
- Power Plane:
  - PDU нагрузка (или “power_out_w”/“bus_a”) → нагрев `pdu`
  - supercap charge/discharge → нагрев `supercap`
  - dock current → нагрев `dock_bridge` (уже есть детерминированная формула)
  - NBL power → нагрев `core` и/или `pdu` (минимум: `core`)
- (Будущее) RCS импульсы → нагрев `rcs_cluster_*`

Важно: если данных нет, тепловыделение = 0 (и это честно).

---

## 9) Тепловые пороги и влияние на систему (MVP)

Цель: реальная связь “перегрев → ограничения”.

MVP‑правила:
- Если `core.temp_c > core.t_max_c` → запретить NBL (и/или снизить доступные бюджеты) до остывания ниже `t_max_c - hysteresis`.
- Если `pdu.temp_c > pdu.t_max_c` → включить load shedding/ограничение non‑critical нагрузок (аналогично).

Гистерезис обязателен (чтобы не “пилить” on/off каждый тик):
- `t_trip` и `t_clear = t_trip - Δ`.

---

## 10) ORION UI (no‑mocks)

Требования к UI:
- Экран `Thermal` (или Diagnostics‑секция), который показывает:
  - список узлов (id/label),
  - temp_c,
  - статус (`Normal/Abnormal/N/A`) и возраст телеметрии.
- Никаких фейковых “процентов прогресса” и “OK” без источника. Если данных нет — `N/A`.

Опционально (если удобно):
- кликабельность: выбор узла → показ деталей в Inspector (без действий).

---

## 11) Тесты (минимальные, быстрые)

1) Нагрев:
- при ненулевом `Q_i` температура узла растёт.
2) Охлаждение:
- при `Q_i=0` температура стремится к `T_amb`.
3) Порог:
- при перегреве `core` запрещается NBL (и это отражается в телеметрии power plane).
4) Детерминизм:
- одинаковые входы и `dt` → одинаковые температуры.

---

## 12) Критерии приёмки (DoD)

Считаем задачу выполненной, если:
1) В Docker‑стеке `phase1` ORION показывает `Thermal` с реальными узлами и температурами.
2) Нет моков: при отсутствии источника — `N/A/—`, а не “0.0”.
3) Пороги реально влияют на доступность нагрузок (как минимум NBL) и это видно по телеметрии.
4) `pytest` для `q_sim_service` зелёный.

---

## 13) Нота про Grafana (когда имеет смысл)

Grafana/Loki полезны для **истории** и **трендов**, но их имеет смысл подключать “в полную силу” после стабилизации контрактов телеметрии и узлов (иначе будет дрейф дашбордов).
Для Loki есть отдельные best practices: избегать высокой кардинальности label’ов и иметь план по агенту (Promtail постепенно заменяется на Alloy).

---

## 14) References (для обсуждения подхода, не SoT проекта)

- NASA NTRS — *Creation of lumped parameter thermal model by the use of finite elements* (NASA‑CR‑158944), 1978: https://ntrs.nasa.gov/citations/19780025536
- MDPI Sensors — *Lumped Parameter Thermal Network Modeling…* (пример LPTN‑подхода), 2024: https://www.mdpi.com/1424-8220/24/12/3982
- DSPE — Lumped capacitance modeling (узлы/связи → система ODE): https://www.dspe.nl/knowledge/thermomechanics/chapter-4-thermo-mechanical-modeling/4-2-lumped-capacitance-modeling/
- Grafana Loki docs — Label/cardinality best practices: https://grafana.com/docs/loki/latest/get-started/labels/cardinality/
- Grafana blog — Promtail merging into Alloy (таймлайн): https://grafana.com/blog/grafana-loki-3-4-standardized-storage-config-sizing-guidance-and-promtail-merging-into-alloy/
