# Power Plane — Load Shedding & Throttling (P0 canon)

Цель: зафиксировать **реальную**, уже реализованную в симуляции (`q_sim_service`) детерминированную логику отключения/ограничения нагрузок, чтобы:
- оператор видел объяснимое поведение,
- UI не подставлял “моки”,
- будущие изменения не ломали порядок скрытно (тесты должны ловить регрессии).

Инварианты:
- **без `v2` / без новых subject’ов** — используем существующий `power.*` блок телеметрии;
- **deterministic**: порядок операций и списков стабилен;
- **simulation-truth**: источником правды является `q_sim_service`.

## Source of truth (код)

Реализация: `src/qiki/services/q_sim_service/core/world_model.py` (Power Plane section in `WorldModel.step()`).

Поля телеметрии (срез):
- `power.load_shedding` (bool)
- `power.shed_loads` (list[str]) — **dedup** с сохранением порядка (stable order)
- `power.shed_reasons` (list[str]) — причины активного shedding (dedup)
- `power.pdu_throttled` (bool)
- `power.throttled_loads` (list[str])
- `power.faults` (list[str])
- `power.loads_w.*`, `power.sources_w.*`

Важно: `power.shed_reasons` — это список **активных причин в тик**, а не “reason per load”.

## Термины

- **Shed**: нагрузка принудительно выключена (её потребление становится 0 в `power.loads_w.*`, а id появляется в `power.shed_loads`).
- **Throttle**: нагрузка ограничена (например, `motion` и/или `rcs`) для соблюдения лимита PDU.
- **Fault**: фиксируем нарушение лимитов после применения shed/throttle (например, `PDU_OVERCURRENT`).

## Причины (reasons)

Канонические строки причин (как в коде):
- `low_soc`
- `thermal_overheat`
- `pdu_overcurrent`
- `nbl_budget`

## 1) SoC-based shedding (Supervisor)

Триггер: гистерезис по SoC.

Параметры (из `bot_config.json` → `hardware_profile.power_plane.*`):
- `soc_shed_low_pct`
- `soc_shed_high_pct`

Правило:
- если `soc_pct <= low` ⇒ включаем внутреннее состояние “shed”;
- если “shed” и `soc_pct >= high` ⇒ выключаем “shed”.

Эффект в shed-состоянии:
- отключаем (и помечаем shed): **`radar`**, затем **`transponder`**
- `power.shed_reasons` включает `low_soc`

Recovery:
- при выходе из shed-состояния `radar_allowed` и `transponder_allowed` возвращаются `True` и `power.shed_loads` очищается (если нет других причин).

## 2) Thermal-based shedding (Supervisor, от Thermal Plane trip-state)

Триггер: `_thermal_trip_state` (с гистерезисом) по узлам, которые описаны в `hardware_profile.thermal_plane.nodes`.

Важно про порядок времени:
- trip-state вычисляется внутри `_thermal_step()` в конце тика,
- значит “эффект shedding по thermal trip” гарантированно проявляется **со следующего тика**.

Эффекты:
- если `THERMAL_TRIP:pdu` ⇒ отключаем (shed): **`radar`**, **`transponder`** (reason `thermal_overheat`)
- если `THERMAL_TRIP:core` ⇒ отключаем (shed): **`nbl`** (reason `thermal_overheat`)

## 3) NBL budget gating (non-critical)

NBL — отдельная некритичная нагрузка с ограничениями по SoC/термо.

Условия “allowed” (упрощённо):
- `nbl_active` true
- `soc_pct >= nbl_soc_min_pct`
- `temp_core_c <= nbl_core_temp_max_c`
- нет thermal trip по `core` или `pdu`

Если `nbl_active` true, но `nbl_allowed` false:
- `nbl` добавляется в `power.shed_loads`
- `power.shed_reasons` включает:
  - `thermal_overheat`, если причиной является thermal trip, иначе `nbl_budget`

## 4) PDU overcurrent enforcement (PDU)

Триггер: расчётный лимит PDU по току:

`pdu_limit_w = bus_v * max_bus_a`

Если `power_out_wo_supercap > pdu_limit_w`, то применяется **строгий порядок**:

1) Shed `nbl` (reason `pdu_overcurrent`)
2) Shed `radar` (reason `pdu_overcurrent`)
3) Shed `transponder` (reason `pdu_overcurrent`)
4) Throttle `motion` (если всё ещё выше лимита)
5) Throttle `rcs` (если всё ещё выше лимита)
6) Если всё ещё выше лимита ⇒ fault `PDU_OVERCURRENT`

Recovery:
- логика PDU не хранит “состояние” между тиками: на каждом тике всё пересчитывается заново;
- если нагрузка/лимит больше не нарушены — `power.pdu_throttled` и `PDU_OVERCURRENT` исчезают автоматически.

## Proof / Tests (must stay green)

Эта спецификация должна быть защищена тестами, которые выполняются в Docker quality gate.

Unit tests (canon):
- `tests/unit/test_power_load_shedding_order.py`

