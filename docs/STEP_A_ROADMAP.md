# Step-A Roadmap (Корпус / Пропульсивный контур / Стыковка)

## Фазы внедрения

1. **Инфраструктура (текущий инкремент)**
   - Расширенный `BotSpec` с компонентами `docking`, `antenna_xpdr`, `sensor_mounts`.
   - Структурированные конфиги: `config/propulsion/thrusters.json`, `config/power/hess.json`,
     `config/docking/ports.json`, `config/comms/antenna.json`, `config/sensors/mounts.json`.
   - Геометрия: `assets/geometry/hull_collision.json`, placeholder для `dodecahedron.glb`.

2. **Аллокатор и энергетика**
   - Реализация QP/NNLS + PWPF в `src/qiki/services/q_core_agent/control/allocation.py`.
   - Ограничения HESS, публикация `EnergyStatus`, обработка отказов thruster кластеров.
   - Юнит-тесты: ранк матрицы аллокации, устойчивость при отказе 1 RCS.

3. **Стыковка, XPDR, интеграции**
   - Состояния docking (align → soft → hard → bridge) + bridge профили.
   - Антенна/XPDR: статусы, режимы ON/OFF/SILENT/SPOOF, обновление WorldModel.
   - Интеграционные тесты: Mode=IDS + Motion → импульсы под P_peak, стыковка без нарушений.

## Definition of Done для Step-A

- Наполненные конфиги и валидируемый `BotSpec`.
- Thruster аллокатор выдаёт решения без нарушения энергетических лимитов.
- Стейты стыковки и XPDR интегрированы в события/метрики.
- `ruff`, `mypy`, `pytest` зелёные; документация и журналы обновлены.
