# Design: bot_core

## 1. Overview
This document defines the `bot_core` component, which represents the fundamental, low-level definition of the bot entity within the Q-Core Agent microservice. It serves as the foundation upon which all higher-level logic, including the FSM (Finite State Machine), is built.

The purpose of `bot_core` is to:
- Uniquely identify the bot instance.
- Manage its static configuration and properties (e.g., hardware profile, physical limitations).
- Define the raw, uninterpreted interaction points for sensors (`SensorRawIn`) and actuators (`ActuatorRawOut`).

This component is intentionally kept separate from the FSM to ensure a clear distinction between the bot's intrinsic properties and its behavioral state.

### 1.1. Bot Identification
The bot's unique ID is critical for multi-agent scenarios and logging. 
- **Generation:** The ID is generated once upon the very first launch of the agent.
- **Persistence:** The ID is stored in a separate, persistent file (e.g., `.qiki_bot.id`) outside of the main configuration, to ensure the bot retains its identity even if its configuration is changed.
- **Format:** `QIKI-{YYYYMMDD}-{8_char_hash}` (e.g., `QIKI-20250721-a1b2c3d4`).

## 2. Functional Requirements
<!-- What must this component do? -->

## 3. Architecture & Design
The `bot_core` is a simple data container and interface layer. It does not contain complex logic. Its primary role is to hold the bot's static configuration and provide a clear boundary between the high-level `Q-Core Agent` logic (like the FSM) and the low-level `Q-Sim Service`.

It also maintains a **Runtime Info Buffer**, a read-only snapshot of the last known values from sensors and commands sent to actuators. This is crucial for debugging and state analysis without querying the FSM.

```mermaid
graph TD
    subgraph Q-Core Agent
        FSM(Finite State Machine)
        RuleEngine(Rule Engine)
        Monitor(Monitoring Tools)
    end

    subgraph Q-Sim Service
        SensorSim(Sensor Simulation)
        ActuatorSim(Actuator Simulation)
    end

    Config[bot_config.json] --> CoreBot(bot_core)
    RuntimeBuffer["Runtime Info Buffer (Internal)"] --.-> CoreBot

    CoreBot -- reads --> Config
    FSM -- uses --> CoreBot
    RuleEngine -- uses --> CoreBot
    Monitor -- reads --> RuntimeBuffer

    SensorSim -- "SensorRawIn" --> CoreBot
    CoreBot -- "ActuatorRawOut" --> ActuatorSim
```

## 4. API Specification
The `bot_core` component does not expose an external network API. It provides a programmatic API (a Python class) for other components within the `Q-Core Agent` microservice.

### Configuration & Properties
- `get_id() -> str`: Returns the unique bot ID.
- `get_property(property_name: str) -> Any`: Retrieves a static property from the loaded configuration.

### Sensor Data (Asynchronous Push/Pull Model)
- `register_sensor_callback(callback: Callable[[SensorRawIn], None])`: Registers a callback function that will be invoked with new sensor data as it arrives (push model).
- `get_latest_sensor_value(sensor_id: str) -> Optional[SensorRawIn]`: Retrieves the most recent value for a specific sensor (pull model).
- `get_sensor_history(sensor_id: str, n: int = 10) -> List[SensorRawIn]`: Retrieves the last `n` values for a specific sensor.

### Actuator Commands
- `send_actuator_command(command: ActuatorRawOut)`: Sends a raw command to an actuator.

### Runtime Info Buffer (Read-Only)
- `@property current_sensor_snapshot() -> Dict[str, Any]`: Returns a dictionary of the last known values for all sensors.
- `@property last_actuator_commands() -> Dict[str, Any]`: Returns a dictionary of the last commands sent to all actuators.

## 5. Data Models
The `bot_core` component operates on three primary data models. Formal JSON schemas will be created in the `/schemas` directory.

**1. Bot Configuration (`bot_config.json`):**
```json
{
  "schema_version": "1.0",
  "bot_id": "QIKI-20250721-a1b2c3",
  "bot_type": "explorer_v1",
  "mode": "full", // or "minimal"
  "hardware_profile": {
    "max_speed_mps": 2.5,
    "power_capacity_wh": 1000,
    "actuators": [
      {"id": "motor_left", "type": "wheel_motor"},
      {"id": "motor_right", "type": "wheel_motor"}
    ],
    "sensors": [
      {"id": "lidar_front", "type": "lidar"},
      {"id": "imu_main", "type": "imu"}
    ]
  }
}
```
*In `minimal` mode, the `hardware_profile` can be omitted. In this mode, sensor/actuator methods are non-operational but do not raise errors, facilitating unit testing of higher-level logic.*

**2. Sensor Raw Input (`SensorRawIn`):**
```json
{
  "timestamp_utc": "2025-07-21T18:30:00Z",
  "sensor_id": "lidar_front",
  "value": 10.5,
  "unit": "meters"
}
```

**3. Actuator Raw Output (`ActuatorRawOut`):**
```json
{
  "actuator_id": "motor_left",
  "command": "set_velocity_percent",
  "value": 50
}
```

## 6. Anti-patterns (Past Failures)
Based on the analysis of projects in `_ARCHIVE`, the following anti-patterns must be strictly avoided:

- **Mixing State and Configuration:** In `qiki_bot`, telemetry, state (like FSM state), and static configuration were often mixed in single files (`telemetry.json`). `bot_core` must only deal with static, intrinsic properties.
- **Implicit Data Contracts:** Raw sensor and actuator data formats were not formally defined, leading to inconsistencies across CLI tools and monitors. `bot_core` must rely on formal schemas for its I/O points.
- **Lack of Persistent ID:** No clear mechanism for generating and persisting a unique bot identifier was present, complicating multi-agent scenarios.
- **Direct Hardware/Sim Access:** Modules often directly read files or accessed hardware, bypassing any abstraction. `bot_core` must be the single, clear interface for raw I/O.
- **Monolithic Getters:** The `get_bot_status()` function in `qiki_hardware` returned hundreds of fields, creating a tight coupling. `bot_core` API must be atomic and granular.
- **Embedded Unit Conversions:** In `qiki_termux`, sensors transmitted data in non-standard units (cm, PWM). All data in `SensorRawIn` and `ActuatorRawOut` must use standard SI units, with conversions handled by adapters.
- **Unsafe Fallbacks:** `bot_core` must fail loudly and immediately if `bot_config.json` is missing or invalid. It should not fall back to a "default" or "safe" configuration, as this hides critical deployment errors.

## 7. Open Questions
<!-- What is not yet decided? -->

1.  **Configuration Hot-Reload:** Should the `bot_core` support reloading its configuration from `bot_config.json` at runtime, or is a restart required? For MVP, a restart is assumed.
2.  **Schema Validation Enforcement:** Where should the validation of `SensorRawIn` and `ActuatorRawOut` schemas be enforced? In the `bot_core` itself, or at the boundary of the `Q-Sim Service` / real hardware driver?

