# TASK (2026-02-02): Comms Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для связи/XPDR, чтобы было понятно:
- какие параметры существуют и где они заданы (SoT),
- где они реально применяются в расчёте/управлении,
- какие telemetry keys публикуются,
- где и как это отображается в ORION,
- и какие gaps остаются (без моков).

Статус: DRAFT (живой документ).

---

## 0) Target task + DoD (MVP)

**Target:** `Comms Plane (XPDR): SoT → sim truth → telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT для comms/xpdr: `src/qiki/services/q_core_agent/config/bot_config.json` (`hardware_profile.comms_plane.*`).
2) Если `hardware_profile.comms_plane.enabled=false`, XPDR **жёстко OFF** (и нельзя включить через команду).
3) `q_sim_service` публикует `comms.*` и они объяснимы оператору: `enabled/mode/active/allowed/id`.
4) ORION показывает минимум на экране Diagnostics (без “красивых нулей”): `Comms enabled`, `XPDR mode`, `XPDR active`, `XPDR allowed`, `XPDR id`.
5) Есть доказательство: unit test на `sim.xpdr.mode` и dictionary guard зелёный.

---

## 1) Single Source of Truth (SoT)

SoT конфиг: `src/qiki/services/q_core_agent/config/bot_config.json`

### 1.1 Comms Plane

- `hardware_profile.comms_plane.enabled` (bool)
- `hardware_profile.comms_plane.xpdr_mode_init` (enum: `ON|OFF|SILENT|SPOOF`)

### 1.2 Связанные параметры (Power Plane)

XPDR — это электрическая нагрузка, поэтому мощность задана в Power Plane:
- `hardware_profile.power_plane.transponder_power_w` (W)

### 1.3 Debug-only overrides (не канон)

- `RADAR_TRANSPONDER_ID` — задаёт “реальный” XPDR id (по умолчанию генерится `ALLY-XXXXXX`).
- `RADAR_TRANSPONDER_MODE` — override режима **только если** `comms_plane.enabled=true`.

---

## 2) Compute (q_sim_service)

### 2.1 Где читается SoT

- `src/qiki/services/q_sim_service/service.py`:
  - `QSimService.__init__()` читает `hardware_profile.comms_plane.enabled` и `xpdr_mode_init` (через `bot_config.json`).
  - Если `enabled=false` → XPDR принудительно `OFF`.

### 2.2 Runtime truth: что считается “active”

- `QSimService._is_transponder_active()`:
  - `false`, если `comms_plane.enabled=false`;
  - `false`, если `world_model.transponder_allowed=false` (power/thermal shedding);
  - иначе active при `mode in (ON,SPOOF)`.

### 2.3 Power/thermal gating (allowed)

Gating считается в симуляции (source of truth = `WorldModel`):
- `src/qiki/services/q_sim_service/core/world_model.py`:
  - `transponder_allowed` сбрасывается при:
    - low SoC load shedding,
    - thermal trip (например `pdu`),
    - PDU overcurrent при расчёте нагрузки.
  - XPDR power load учитывается как `power.loads.transponder` только если `transponder_active && transponder_allowed`.

---

## 3) Telemetry keys (payload)

### 3.1 Comms (operator-facing)

- `comms.enabled`
- `comms.xpdr.mode`
- `comms.xpdr.active`
- `comms.xpdr.allowed`
- `comms.xpdr.id`

### 3.2 Связанные power-ключи (explainability)

- `power.loads.transponder` (W) — реальная нагрузка XPDR на шине (0 при `OFF`/`SILENT`/`not allowed`).
- `power.shed_loads`, `power.shed_reasons` — почему `allowed=false` (если применимо).

---

## 4) ORION mapping (UI)

- ORION показывает comms/xpdr в Diagnostics таблице:
  - Код: `src/qiki/services/operator_console/main_orion.py` (`_render_diagnostics_table()`).
- Канонический словарь ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` (`subsystems.comms`).

---

## 5) Evidence

- Unit tests:
  - `src/qiki/services/q_sim_service/tests/test_comms_plane.py`
- Dictionary guard:
  - `tests/unit/test_telemetry_dictionary.py`

---

## 6) Gaps / open questions (fill next)

1) Нужен ли отдельный ORION экран `Comms/Связь` (а не только Diagnostics), если появятся процедуры/операции/лимиты?
2) Нужен ли операторский “контракт управления” для XPDR в каноне (аналог `SIMULATION_CONTROL_CONTRACT.md`) — команды, подтверждения, ожидаемые эффекты в телеметрии.
3) Будущие параметры link budget / bitrate / antenna state сейчас не моделируются (и должны оставаться `N/A`, не “0”).

