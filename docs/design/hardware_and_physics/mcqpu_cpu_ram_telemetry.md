# MCQPU CPU/RAM Telemetry (simulation-truth, no-mocks)

Статус: **design spec / MVP**  
Проект: **QIKI_DTMP**  
Связанные “источники правды”:  
- `docs/design/hardware_and_physics/bot_source_of_truth.md` (структура бота, MCQPU/Q‑Core/S‑Core/R‑Core)  
- `docs/operator_console/REAL_DATA_MATRIX.md` (no‑mocks policy, источники данных для ORION)  

---

## 1) Цель

Сделать так, чтобы Operator Console (ORION) отображала:
- `CPU/ЦП` — **cpu_usage** (0..100%)
- `Mem/Пам` — **memory_usage** (0..100%)

…как **виртуальные метрики “железа бота” (MCQPU)**, вычисляемые внутри симуляции и публикуемые в телеметрию.

---

## 2) Принципы (жёстко)

1) **Игра/симуляция:** CPU/RAM — это *не* VPS/контейнер, а “виртуальное железо” MCQPU.  
2) **No‑mocks UI:** UI ничего не “рисует для красоты”; если данных нет — показывает `N/A`.  
3) **Single Source of Truth:** единственный источник значений — симуляционный `WorldModel` (simulation truth).  
4) **Без дублей:** не вводим `v2`, не создаём параллельные NATS subjects для того же смысла.  
5) **Детерминизм:** никакого `random`; значения должны быть воспроизводимы из состояния симуляции.  

---

## 3) Контракт данных

Источник в рантайме: NATS subject `qiki.telemetry` (TelemetrySnapshot v1).

Поля (уже существуют в модели телеметрии):
- `cpu_usage: float | None` (0..100)
- `memory_usage: float | None` (0..100)

Требование: публиковать **всегда** (не `None`) после запуска симуляции.

---

## 4) Что НЕ делаем (анти‑паттерны)

- Не используем метрики ОС/контейнера: `psutil`, `/proc`, `docker stats`, cloud‑метрики и т.п.  
  Это описывает нагрузку **хоста**, а не “MCQPU бота”.
- Не добавляем “демо‑нули” в UI (иначе нарушается `REAL_DATA_MATRIX`).
- Не считаем RAM по неограниченным структурам, которые копятся бесконечно (например, список всех кадров радара без лимита), иначе будет “вечно 100%”.

---

## 5) Рекомендуемая модель (MVP): “demand / capacity” + сглаживание

### 5.1 Почему так

Самый устойчивый и объяснимый подход для симуляции:  
**utilization = demand / capacity**, где:
- **demand** — детерминированная “потребность” подсистем (Q‑Core/S‑Core/R‑Core) по текущему состоянию,
- **capacity** — фиксированная “производительность” MCQPU (виртуальная), задаётся константами (MVP) и позже может быть вынесена в hardware profile.

Это стандартный принцип анализа производительности: система описывается через нагрузку/спрос и доступную мощность.  
См. например общие подходы “service demand / capacity” в аналитическом моделировании производительности. [^perf_book]

Для стабилизации UI применяем **экспоненциальное сглаживание (EMA)**. Рекомендуется использовать α, зависящий от `delta_time` через временную константу τ:  
`alpha = 1 - exp(-dt / tau)` — так поведение одинаково при разных dt. [^ema_wiki]

### 5.2 Параметры MCQPU (MVP)

Пока не вытаскиваем из hardware contracts (чтобы не множить источники правды), задаём константами в симуляции:
- `MCQPU_CPU_CAPACITY_CU_PER_SEC` — “compute units per second”
- `MCQPU_RAM_CAPACITY_MU` — “memory units”

Числа выбираются так, чтобы при типичной нагрузке “спокойный режим” был 10–30%, а интенсивный режим 60–95%.

### 5.3 Источники demand (MVP, только то, что реально есть сейчас)

Минимальный набор детерминированных входов:
- движение: `speed` (R‑Core нагрузка),
- радар включён/выключен: `radar_enabled` (S‑Core нагрузка),
- “pressure”: глубины очередей/буферов сим‑сервиса (Q‑Core/S‑Core индикатор),
  - `len(sensor_data_queue)`
  - `len(actuator_command_queue)`
- активность транспондера (маленькая надбавка).

Важно: эти входы — часть симуляции, не OS.

---

## 6) Формулы (MVP, готово к реализации)

Нотация:
- `clamp(x, lo, hi)` — ограничение диапазона
- `demand_cpu_cu_per_sec` — суммарный “спрос” на вычисления
- `used_mem_mu` — суммарное “использование” памяти

### 6.1 CPU (cpu_usage)

1) Рассчитать “спрос” (compute demand):

```
base_cu = 8
motion_cu = 28 * clamp(abs(speed) / 1.0, 0, 1)
radar_cu = 18 if radar_enabled else 0
queue_cu = min(18, 0.9 * sensor_q + 0.6 * actuator_q)
xpdr_cu  = 3 if transponder_active else 0

demand_cpu_pct_target = clamp(base_cu + motion_cu + radar_cu + queue_cu + xpdr_cu, 0, 100)
```

2) Сгладить:

```
alpha = 1 - exp(-dt / tau_cpu)
cpu_usage = clamp(cpu_usage + alpha * (demand_cpu_pct_target - cpu_usage), 0, 100)
```

Рекомендуемое `tau_cpu`: 1.5–2.5 сек (чтобы не “дёргалось”, но реагировало).

### 6.2 RAM (memory_usage)

RAM моделируем как “виртуальную занятость буферов/структур” (не OS):

```
base_mem = 22
sensor_buf = min(35, 1.2 * sensor_q)
act_buf    = min(20, 1.0 * actuator_q)
radar_buf  = 10 if radar_enabled else 0

demand_mem_pct_target = clamp(base_mem + sensor_buf + act_buf + radar_buf, 0, 100)
```

Сглаживание:

```
alpha = 1 - exp(-dt / tau_mem)
memory_usage = clamp(memory_usage + alpha * (demand_mem_pct_target - memory_usage), 0, 100)
```

Рекомендуемое `tau_mem`: 3–5 сек (RAM обычно “инертнее” CPU).

---

## 7) Точки внедрения (чтобы не было дублей)

1) `WorldModel` хранит и обновляет:
- `self.cpu_usage`
- `self.memory_usage`

2) `QSimService.step()` передаёт в `WorldModel` текущие runtime‑сигналы (не OS):
- `radar_enabled`
- `sensor_queue_depth`
- `actuator_queue_depth`
- `transponder_active`

Вариант API (MVP): метод `world_model.set_runtime_load_inputs(...)`.

3) `WorldModel.get_state()` добавляет:
- `"cpu_usage": float`
- `"memory_usage": float`

4) `QSimService._build_telemetry_payload()` прокидывает их в `TelemetrySnapshotModel(...)`.

UI ORION уже читает `cpu_usage`/`memory_usage` из `qiki.telemetry` и перестанет показывать `Not available` автоматически.

---

## 8) Тест‑план (минимум)

Unit‑тест (в `q_sim_service`):
- в payload телеметрии есть `cpu_usage` и `memory_usage`,
- тип `float` (или `int`, но лучше `float`),
- диапазон [0..100].

Smoke:
- поднять compose‑стек, открыть ORION, убедиться что `CPU/ЦП` и `Mem/Пам` отображаются числами и меняются при изменении `speed`/включении радара.

---

## 9) Будущее расширение (без смены контракта)

Не меняя `TelemetrySnapshot v1`, можно улучшать “demand” за счёт симуляционных факторов:
- число треков/детекций (но только если есть **ограниченный** state‑счётчик, а не бесконечный список),
- интенсивность сообщений/событий,
- режимы Q‑Core (например, “planning burst”),
- термальные/энергетические ограничения (throttling), если появятся.

Параметры capacity (виртуальные характеристики MCQPU) можно позже переносить в `bot_config.json`/hardware profile как **единственный** машиночитаемый SoT, но без создания “вторых файлов‑истин”.

---

[^ema_wiki]: https://en.wikipedia.org/wiki/Exponential_smoothing (см. EMA; для dt‑инвариантности удобно брать α через `1-exp(-dt/τ)`).
[^perf_book]: https://en.wikipedia.org/wiki/Analytical_performance_modeling (общий подход demand/capacity и аналитические модели производительности).

