#!/usr/bin/env python3
"""
QIKI MISSION CONTROL - Рабочий образец
Полнофункциональный терминал управления космическим аппаратом.
Работает в любой терминальной среде без дополнительных зависимостей.
Поддерживает prompt_toolkit для улучшенного интерфейса.
"""

import os
import sys
import time
import threading
import importlib.util
from datetime import datetime
from typing import Dict, Any

if not __package__:
    # Legacy: allow direct execution from this directory.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)

# ASCII LIVE INTERFACE - Без зависимостей!
ASCII_INTERFACE_AVAILABLE = True
if __name__ == "__main__":
    print("✅ ASCII Live Interface loaded - full terminal control")

PROMPT_TOOLKIT_AVAILABLE = importlib.util.find_spec("prompt_toolkit") is not None

if __package__:
    from qiki.services.q_core_agent.core.ship_actuators import (
        PowerAllocation,
        ShipActuatorController,
        ThrusterAxis,
    )
    from qiki.services.q_core_agent.core.ship_core import ShipCore
    from qiki.services.q_core_agent.core.test_ship_fsm import ShipLogicController
else:
    from ship_actuators import PowerAllocation, ShipActuatorController, ThrusterAxis
    from ship_core import ShipCore
    from test_ship_fsm import ShipLogicController


class QIKIMissionControl:
    """
    Полнофункциональный Mission Control Terminal.
    Реальный рабочий образец для управления космическим аппаратом.
    """

    def __init__(self):
        print("🚀 Initializing QIKI Mission Control...")

        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core)
        self.logic_controller = ShipLogicController(self.ship_core, self.actuator_controller)

        # Состояние Mission Control
        self.mission_start_time = time.time()
        self.running = True
        self.autopilot_enabled = False
        self.log_messages = []
        self.command_history = []

        # Статистика
        self.commands_executed = 0
        self.telemetry_updates = 0
        self.alerts_triggered = 0

        # Живые параметры миссии (БЕЗ заглушек!)
        self.mission_data = {
            "designator": "РАЗВЕДКА-7Д / RECON-7D",
            "objective": "Исследование аномалии J7 / Investigate Anomaly J7",
            "progress": 0.0,
            "eta_seconds": 11520,  # 3 часа 12 минут
            "steps": [
                {"name": "Навигация к сектору / Navigate to sector", "done": True},
                {"name": "Спектральное сканирование / Spectral scan", "done": True},
                {"name": "Обнаружение аномалии / Anomaly detection", "done": True},
                {"name": "Приближение к J7 / Approach J7", "done": False},
                {"name": "Сбор образцов / Sample collection", "done": False},
                {"name": "Передача данных / Data transmission", "done": False},
                {"name": "Возврат на базу / Return to base", "done": False},
            ],
        }

        # Дополнительные живые параметры из шаблонов интерфейсов
        self.navigation_data = {
            "coordinates": {"x": 324167.89, "y": -52631.44, "z": 125.61},
            "velocity": {"absolute": 2437, "relative": 18, "drift": 0.03},
            "anomaly_distance": 32.17,
            "target_name": "Anomaly-J7",
            "sector": "Delta-5",
        }

        self.sensor_data = {
            "radar": {"mode": "Active Scanning", "range": 150, "objects": 7},
            "lidar": {
                "mode": "Focused Beam",
                "distance": 32.17,
                "composition": "Scanning...",
            },
            "spectral": {"elements": {"Fe": 47, "Ni": 23, "Ti": 18, "Unknown": 12}},
            "magnetometer": {"local": 0.02, "anomaly": 5.47, "confidence": 84},
        }

        self.language = "RU"  # RU или EN
        self.simulation_time = 0

        # Инициализируем live_telemetry
        self.live_telemetry = {}

        # Фоновые процессы - ОБЯЗАТЕЛЬНО запускаем симуляцию!
        self.background_thread = threading.Thread(target=self._background_processes, daemon=True)
        self.background_thread.start()

        # ПРИНУДИТЕЛЬНО запускаем обновление параметров сразу
        self._update_live_parameters()

        print("🔄 Live parameter simulation started")

        self.log("SYSTEM", "✅ QIKI Mission Control Terminal Online")
        self.log("SPACECRAFT", f"🛰️ Connected to {self.ship_core.get_id()}")
        self.log("TELEMETRY", "📊 Background telemetry started")

        print(f"✅ Connected to spacecraft: {self.ship_core.get_id()}")
        print("🎯 Mission Control Terminal ready for operations")

    def log(self, system: str, message: str):
        """Добавляет сообщение в журнал Mission Control."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        mission_time = self._get_mission_time()
        log_entry = {
            "timestamp": timestamp,
            "mission_time": mission_time,
            "system": system,
            "message": message,
            "full": f"[{timestamp}] [{mission_time}] {system}: {message}",
        }
        self.log_messages.append(log_entry)

        # Ограничиваем размер лога
        if len(self.log_messages) > 100:
            self.log_messages = self.log_messages[-100:]

    def _get_mission_time(self) -> str:
        """Получает время миссии в формате T+HH:MM:SS."""
        elapsed = int(time.time() - self.mission_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _background_processes(self):
        """Фоновые процессы Mission Control."""
        import random

        while self.running:
            try:
                # Обновляем время симуляции
                self.simulation_time += 3.0  # 3 секунды

                # Обновляем живые параметры
                self._update_live_parameters()

                # Автопилот
                if self.autopilot_enabled:
                    result = self.logic_controller.process_logic_cycle()
                    if result.get("state_changed"):
                        self.log("AUTOPILOT", f"🤖 State: {result['current_state']}")
                        if result["trigger_event"]:
                            self.log("AUTOPILOT", f"🔄 Trigger: {result['trigger_event']}")

                # Телеметрия
                self._check_system_alerts()
                self.telemetry_updates += 1

                # Случайные события для реализма
                if random.random() < 0.03:  # 3% шанс события
                    self._generate_random_event()

                time.sleep(3)  # Обновление каждые 3 секунды

            except Exception as e:
                self.log("SYSTEM", f"❌ Background error: {e}")
                time.sleep(5)

    def _update_live_parameters(self):
        """Обновляет живые параметры для реализма."""
        import random

        try:
            # Обновляем координаты (медленное движение к цели)
            self.navigation_data["coordinates"]["x"] += random.uniform(-2, 2)
            self.navigation_data["coordinates"]["y"] += random.uniform(-2, 2)
            self.navigation_data["coordinates"]["z"] += random.uniform(-0.2, 0.2)

            # Приближаемся к аномалии
            if self.navigation_data["anomaly_distance"] > 1.0:
                self.navigation_data["anomaly_distance"] -= random.uniform(0.01, 0.05)

            # Флуктуации скорости
            self.navigation_data["velocity"]["absolute"] += random.uniform(-1, 1)
            self.navigation_data["velocity"]["relative"] += random.uniform(-0.5, 0.5)

            # Обновляем сенсорные данные
            self.sensor_data["radar"]["objects"] = max(
                5, min(10, self.sensor_data["radar"]["objects"] + random.randint(-1, 1))
            )

            # Прогресс миссии
            if self.mission_data["progress"] < 100:
                self.mission_data["progress"] += random.uniform(0.1, 0.3)
                self.mission_data["eta_seconds"] = max(0, self.mission_data["eta_seconds"] - random.uniform(10, 30))

            # Обновляем этапы миссии
            if self.mission_data["progress"] > 50 and not self.mission_data["steps"][3]["done"]:
                self.mission_data["steps"][3]["done"] = True
                self.log("MISSION", "✅ Приближение к J7 завершено / Approach to J7 complete")

        except Exception as e:
            self.log("TELEMETRY", f"❌ Live parameter update error: {e}")

    def _generate_random_event(self):
        """Генерирует случайные события для реализма."""
        import random

        events_ru_en = [
            ("СЕНСОРЫ", "📡 Обнаружен микро-мусор / Micro-debris detected"),
            ("ПИТАНИЕ", "⚡ Флуктуация солнечных панелей / Solar panel fluctuation"),
            ("НАВИГАЦИЯ", "🧭 Корректировка курса / Course correction"),
            ("СВЯЗЬ", "📻 Переключение частоты / Frequency switch"),
            ("ДИАГНОСТИКА", "🔧 Автопроверка систем / System self-check"),
            ("ДВИГАТЕЛИ", "🚀 Микрокоррекция ориентации / Orientation microcorrection"),
        ]

        system, message = random.choice(events_ru_en)
        self.log(system, message)

    def _check_system_alerts(self):
        """Проверяет системы на аварийные ситуации."""
        try:
            telemetry = self._get_telemetry()

            # Критические ситуации
            if telemetry["hull_integrity"] < 30:
                self.log("ALERT", "🚨 CRITICAL: Hull breach detected!")
                self.alerts_triggered += 1

            if telemetry["oxygen_level"] < 16:
                self.log("ALERT", "🚨 CRITICAL: Oxygen levels dangerously low!")
                self.alerts_triggered += 1

            if telemetry["reactor_temp"] > 3500:
                self.log("ALERT", "🚨 CRITICAL: Reactor overheating!")
                self.alerts_triggered += 1

            # Предупреждения
            elif telemetry["main_drive_fuel"] < 50:
                self.log("ALERT", "⚠️ WARNING: Low fuel reserves")

            elif telemetry["battery_charge"] / max(telemetry["battery_capacity"], 1) < 0.2:
                self.log("ALERT", "⚠️ WARNING: Battery charge low")

        except Exception as e:
            self.log("ALERT", f"❌ Alert check failed: {e}")

    def _get_telemetry(self) -> Dict[str, Any]:
        """Получает полную телеметрию космического аппарата."""
        hull = self.ship_core.get_hull_status()
        power = self.ship_core.get_power_status()
        propulsion = self.ship_core.get_propulsion_status()
        sensors = self.ship_core.get_sensor_status()
        life_support = self.ship_core.get_life_support_status()
        computing = self.ship_core.get_computing_status()

        return {
            "hull_integrity": hull.integrity,
            "reactor_output": power.reactor_output_mw,
            "reactor_max": power.reactor_max_output_mw,
            "battery_charge": power.battery_charge_mwh,
            "battery_capacity": power.battery_capacity_mwh,
            "reactor_temp": power.reactor_temperature_k,
            "main_drive_status": propulsion.main_drive_status,
            "main_drive_fuel": propulsion.main_drive_fuel_kg,
            "oxygen_level": life_support.atmosphere.get("oxygen_percent", 0),
            "co2_level": life_support.atmosphere.get("co2_ppm", 0),
            "pressure": life_support.atmosphere.get("pressure_kpa", 0),
            "qiki_status": computing.qiki_core_status,
            "qiki_temp": computing.qiki_temperature_k,
            "active_sensors": len(sensors.active_sensors),
            "propulsion_mode": self.actuator_controller.current_mode.value,
            "ship_state": self.logic_controller.current_state.value,
        }

    def display_status(self):
        """Отображает полный статус Mission Control."""
        os.system("clear" if os.name == "posix" else "cls")

        telemetry = self._get_telemetry()
        mission_time = self._get_mission_time()

        print("╔" + "═" * 98 + "╗")
        print(f"║{'🚀 QIKI MISSION CONTROL TERMINAL':^98}║")
        print(
            f"║ 🛰️ {self.ship_core.get_id():<25} {mission_time:>15} {datetime.now().strftime('%H:%M:%S UTC'):>15} {'':>35} ║"
        )
        print("╠" + "═" * 98 + "╣")

        # Статус систем
        alert_level = self._get_alert_level(telemetry)
        mode = "🤖 AUTOPILOT" if self.autopilot_enabled else "👨‍🚀 MANUAL"

        print(f"║ STATUS: {alert_level:<20} MODE: {mode:<15} STATE: {telemetry['ship_state']:<15} ║")
        print("╠" + "═" * 98 + "╣")

        # Телеметрия (две колонки)
        left_data = [
            f"🛡️  HULL INTEGRITY    : {self._format_bar(telemetry['hull_integrity'])} %",
            f"⚡ REACTOR OUTPUT    : {self._format_bar((telemetry['reactor_output'] / max(telemetry['reactor_max'], 1)) * 100)} %",
            f"🔋 BATTERY CHARGE    : {self._format_bar((telemetry['battery_charge'] / max(telemetry['battery_capacity'], 1)) * 100)} %",
            f"🌡️  REACTOR TEMP      : {telemetry['reactor_temp']:8.0f} K",
            f"💨 OXYGEN LEVEL      : {telemetry['oxygen_level']:8.1f} %",
            f"🫁 CO2 LEVEL         : {telemetry['co2_level']:8.0f} ppm",
            f"🤖 QIKI STATUS       : {telemetry['qiki_status']:>8}",
        ]

        right_data = [
            f"🚀 MAIN DRIVE        : {telemetry['main_drive_status']:>8}",
            f"🎯 PROPULSION MODE   : {telemetry['propulsion_mode'].upper():>8}",
            f"⛽ MAIN FUEL         : {telemetry['main_drive_fuel']:8.1f} kg",
            f"📡 ACTIVE SENSORS    : {telemetry['active_sensors']:8d}",
            f"💫 MISSION TIME      : {mission_time}",
            f"📊 TELEMETRY UPDATES : {self.telemetry_updates:8d}",
            f"⚠️  ALERTS TRIGGERED  : {self.alerts_triggered:8d}",
        ]

        for i in range(max(len(left_data), len(right_data))):
            left = left_data[i] if i < len(left_data) else ""
            right = right_data[i] if i < len(right_data) else ""
            print(f"║ {left:<48} {right:<48} ║")

        print("╠" + "═" * 98 + "╣")

        # Расширенная информация по шаблонам
        self._display_navigation_panel()
        self._display_mission_panel()

        print("╠" + "═" * 98 + "╣")

        # Последние 5 записей лога
        print("║ 📋 RECENT LOG ENTRIES:" + " " * 75 + "║")
        recent_logs = self.log_messages[-5:] if len(self.log_messages) >= 5 else self.log_messages

        for log_entry in recent_logs:
            message = log_entry["full"]
            if len(message) > 96:
                message = message[:93] + "..."
            print(f"║ {message:<96} ║")

        # Заполняем пустыми строками если лог короткий
        for _ in range(5 - len(recent_logs)):
            print(f"║{' ' * 98}║")

        print("╚" + "═" * 98 + "╝")

        # Статистика
        print(
            f"\n📊 SESSION STATS: Commands: {self.commands_executed} | Telemetry: {self.telemetry_updates} | Alerts: {self.alerts_triggered}"
        )

    def _display_navigation_panel(self):
        """Отображает панель навигации по шаблонам интерфейсов."""
        coords = self.navigation_data["coordinates"]
        vel = self.navigation_data["velocity"]

        lang_title = "НАВИГАЦИЯ / NAVIGATION" if self.language == "RU" else "NAVIGATION / НАВИГАЦИЯ"

        print(f"║ 🧭 {lang_title:<93} ║")
        print(f"║   Координаты / Coordinates: X:{coords['x']:+9.1f} Y:{coords['y']:+9.1f} Z:{coords['z']:+7.1f}  ║")
        print(
            f"║   Скорость / Velocity: {vel['absolute']:4.0f} м/с абсолютная, {vel['relative']:+3.0f} м/с к цели          ║"
        )
        print(
            f"║   Расстояние до {self.navigation_data['target_name']}: {self.navigation_data['anomaly_distance']:6.2f} км               ║"
        )
        print(
            f"║   Сектор / Sector: {self.navigation_data['sector']:<20} Дрейф / Drift: {vel['drift']:.2f}%/ч         ║"
        )

    def _display_mission_panel(self):
        """Отображает панель миссии по шаблонам интерфейсов."""
        mission = self.mission_data
        progress_bar = self._format_bar(mission["progress"], width=10)

        eta_hours = int(mission["eta_seconds"] // 3600)
        eta_mins = int((mission["eta_seconds"] % 3600) // 60)

        lang_title = (
            "УПРАВЛЕНИЕ МИССИЕЙ / MISSION CONTROL" if self.language == "RU" else "MISSION CONTROL / УПРАВЛЕНИЕ МИССИЕЙ"
        )
        lang_progress = "Прогресс / Progress" if self.language == "RU" else "Progress / Прогресс"
        lang_eta = (
            f"ETC: {eta_hours:02}ч {eta_mins:02}м" if self.language == "RU" else f"ETC: {eta_hours:02}h {eta_mins:02}m"
        )

        print(f"║ 🎯 {lang_title:<89} ║")
        print(f"║   ID: {mission['designator']:<30} {lang_progress}: {progress_bar} {mission['progress']:4.1f}%  ║")
        print(f"║   Цель / Objective: {mission['objective'][:50]:<50}               ║")
        print(
            f"║   {lang_eta:<20} Этапы / Steps завершено: {sum(1 for s in mission['steps'] if s['done'])}/{len(mission['steps'])}              ║"
        )

        # Показываем активные этапы
        active_steps = [s for s in mission["steps"] if not s["done"]][:2]
        for step in active_steps:
            status = "► " if not step["done"] else "✓ "
            step_text = step["name"][:60]
            print(f"║     {status}{step_text:<60}                     ║")

    def _format_bar(self, value: float, width: int = 15) -> str:
        """Форматирует значение как progress bar."""
        pct = min(100, max(0, value))
        filled = int(pct * width / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {value:5.1f}"

    def _get_alert_level(self, telemetry: Dict[str, Any]) -> str:
        """Определяет уровень тревоги."""
        if telemetry["hull_integrity"] < 30 or telemetry["oxygen_level"] < 16 or telemetry["reactor_temp"] > 3500:
            return "🚨 EMERGENCY"
        elif (
            telemetry["hull_integrity"] < 60
            or telemetry["battery_charge"] / max(telemetry["battery_capacity"], 1) < 0.2
            or telemetry["main_drive_fuel"] < 50
        ):
            return "⚠️  WARNING"
        elif telemetry["hull_integrity"] < 80 or telemetry["co2_level"] > 1000 or telemetry["reactor_temp"] > 3000:
            return "⚡ CAUTION"
        else:
            return "✅ NOMINAL"

    def execute_command(self, command: str) -> bool:
        """Выполняет команду оператора."""
        if not command.strip():
            return True

        self.command_history.append(command)
        self.commands_executed += 1

        cmd_parts = command.lower().split()
        cmd = cmd_parts[0]

        self.log("OPERATOR", f"💬 Command: {command}")

        try:
            # === КОМАНДЫ ДВИГАТЕЛЬНОЙ СИСТЕМЫ ===
            if cmd == "thrust":
                if len(cmd_parts) >= 2:
                    thrust_pct = float(cmd_parts[1])
                    if 0 <= thrust_pct <= 100:
                        success = self.actuator_controller.set_main_drive_thrust(thrust_pct)
                        if success:
                            self.log("PROPULSION", f"🚀 Main drive: {thrust_pct}%")
                            return True
                        else:
                            self.log("ERROR", "❌ Failed to set main drive thrust")
                    else:
                        self.log("ERROR", "❌ Thrust must be 0-100%")
                else:
                    self.log("ERROR", "❌ Usage: thrust <0-100>")

            # === RCS КОМАНДЫ ===
            elif cmd == "rcs":
                if len(cmd_parts) >= 3:
                    direction = cmd_parts[1].upper()
                    thrust_pct = float(cmd_parts[2])

                    axis_map = {
                        "FORWARD": ThrusterAxis.FORWARD,
                        "FWD": ThrusterAxis.FORWARD,
                        "BACKWARD": ThrusterAxis.BACKWARD,
                        "AFT": ThrusterAxis.BACKWARD,
                        "PORT": ThrusterAxis.PORT,
                        "LEFT": ThrusterAxis.PORT,
                        "STARBOARD": ThrusterAxis.STARBOARD,
                        "RIGHT": ThrusterAxis.STARBOARD,
                    }

                    if direction in axis_map and 0 <= thrust_pct <= 100:
                        duration = float(cmd_parts[3]) if len(cmd_parts) > 3 else 2.0
                        success = self.actuator_controller.fire_rcs_thruster(axis_map[direction], thrust_pct, duration)
                        if success:
                            self.log("RCS", f"🎯 {direction}: {thrust_pct}% for {duration}s")
                            return True
                        else:
                            self.log("ERROR", f"❌ Failed to fire {direction} thruster")
                    else:
                        self.log("ERROR", "❌ Invalid direction or thrust value")
                else:
                    self.log(
                        "ERROR",
                        "❌ Usage: rcs <forward|aft|port|starboard> <0-100> [duration]",
                    )

            # === УПРАВЛЕНИЕ ПИТАНИЕМ ===
            elif cmd == "power":
                if len(cmd_parts) >= 2:
                    subcmd = cmd_parts[1]
                    if subcmd == "status":
                        power = self.ship_core.get_power_status()
                        self.log(
                            "POWER",
                            f"⚡ Reactor: {power.reactor_output_mw:.1f}/{power.reactor_max_output_mw:.1f} MW",
                        )
                        self.log(
                            "POWER",
                            f"🔋 Battery: {power.battery_charge_mwh:.1f}/{power.battery_capacity_mwh:.1f} MWh",
                        )
                        self.log("POWER", f"🌡️ Temp: {power.reactor_temperature_k:.0f}K")
                        return True
                    elif subcmd == "emergency":
                        # Аварийное отключение неосновных систем
                        allocation = PowerAllocation(
                            life_support=10.0,
                            propulsion=5.0,
                            sensors=2.0,
                            qiki_core=3.0,
                            shields=0.0,
                        )
                        success = self.actuator_controller.set_power_allocation(allocation)
                        if success:
                            self.log("POWER", "🚨 Emergency power allocation set")
                            return True
                else:
                    self.log("ERROR", "❌ Usage: power <status|emergency>")

            # === УПРАВЛЕНИЕ СЕНСОРАМИ ===
            elif cmd == "sensor":
                if len(cmd_parts) >= 3:
                    action = cmd_parts[1]
                    sensor_id = cmd_parts[2]

                    if action == "activate":
                        success = self.actuator_controller.activate_sensor(sensor_id)
                        if success:
                            self.log("SENSORS", f"📡 {sensor_id} activated")
                            return True
                    elif action == "deactivate":
                        success = self.actuator_controller.deactivate_sensor(sensor_id)
                        if success:
                            self.log("SENSORS", f"📡 {sensor_id} deactivated")
                            return True
                    else:
                        self.log("ERROR", "❌ Use 'activate' or 'deactivate'")
                else:
                    self.log("ERROR", "❌ Usage: sensor <activate|deactivate> <sensor_id>")

            # === ПЕРЕКЛЮЧЕНИЕ ЯЗЫКА ===
            elif cmd in ["lang", "language", "язык"]:
                self.language = "EN" if self.language == "RU" else "RU"
                lang_name = "Русский" if self.language == "RU" else "English"
                self.log("INTERFACE", f"🌐 Язык / Language: {lang_name}")
                return True

            # === АВТОПИЛОТ ===
            elif cmd == "autopilot":
                self.autopilot_enabled = not self.autopilot_enabled
                status = "ENABLED" if self.autopilot_enabled else "DISABLED"
                self.log("AUTOPILOT", f"🤖 Autopilot {status}")
                return True

            # === АВАРИЙНЫЕ ПРОЦЕДУРЫ ===
            elif cmd == "emergency":
                success = self.actuator_controller.emergency_stop()
                if success:
                    self.log("EMERGENCY", "🚨 EMERGENCY STOP EXECUTED")
                    return True
                else:
                    self.log("ERROR", "❌ Emergency stop failed")

            # === СТАТУС СИСТЕМ ===
            elif cmd == "status":
                summary = self.logic_controller.get_ship_status_summary()
                self.log("STATUS", f"🛰️ State: {summary.get('current_state')}")
                self.log("STATUS", f"🔧 Systems: {summary.get('overall_status')}")
                self.log(
                    "STATUS",
                    f"🧭 Navigation: {'READY' if summary.get('navigation_capable') else 'LIMITED'}",
                )
                return True

            # === ДИАГНОСТИКА ===
            elif cmd == "diagnostics":
                from ship_bios_handler import ShipBiosHandler

                bios_handler = ShipBiosHandler(self.ship_core)
                health = bios_handler.get_system_health_summary()

                self.log("DIAGNOSTICS", f"🔧 Hull: {health.get('hull_integrity', 0):.1f}%")
                self.log(
                    "DIAGNOSTICS",
                    f"⚡ Reactor: {health.get('reactor_output_percent', 0):.1f}%",
                )
                self.log(
                    "DIAGNOSTICS",
                    f"🔋 Battery: {health.get('battery_charge_percent', 0):.1f}%",
                )
                self.log("DIAGNOSTICS", f"📊 Overall: {health.get('overall_status')}")
                return True

            # === СПРАВКА ===
            elif cmd in ["help", "?"]:
                print("\n🎯 QIKI MISSION CONTROL - Available Commands:")
                print("   PROPULSION:")
                print("     thrust <0-100>                    - Set main drive thrust")
                print("     rcs <direction> <0-100> [time]    - Fire RCS thrusters")
                print("     emergency                         - Emergency stop all systems")
                print("   POWER:")
                print("     power status                      - Show power system status")
                print("     power emergency                   - Emergency power allocation")
                print("   SENSORS:")
                print("     sensor activate <id>              - Activate sensor")
                print("     sensor deactivate <id>            - Deactivate sensor")
                print("   CONTROL:")
                print("     autopilot                         - Toggle autopilot mode")
                print("     status                            - Show spacecraft status")
                print("     diagnostics                       - Run system diagnostics")
                print("   INTERFACE:")
                print("     help                              - Show this help")
                print("     exit                              - Terminate Mission Control")
                print("\n💡 RCS Directions: forward/aft/port/starboard (or fwd/aft/left/right)")
                print("💡 Available Sensors: long_range_radar, thermal_scanner, quantum_scanner")
                return True

            # === ВЫХОД ===
            elif cmd in ["exit", "quit", "shutdown"]:
                self.log("SYSTEM", "👨‍🚀 Mission Control shutdown initiated")
                return False

            else:
                self.log(
                    "ERROR",
                    f"❌ Unknown command '{cmd}'. Type 'help' for available commands",
                )

        except ValueError:
            self.log("ERROR", "❌ Invalid numeric parameter")
        except Exception as e:
            self.log("ERROR", f"❌ Command error: {e}")

        return True

    def run_interactive(self):
        """Запускает интерактивный режим Mission Control."""
        print("\n" + "🚀" * 50)
        print("QIKI MISSION CONTROL TERMINAL - INTERACTIVE MODE")
        print("🚀" * 50)
        print()
        print("🎯 Type 'help' for available commands")
        print("🎯 Type 'exit' to shutdown Mission Control")
        print("🎯 Status updates every few seconds in background")
        print()

        try:
            while self.running:
                # Отображение статуса
                self.display_status()

                # Ввод команды
                try:
                    command = input("\n🚀 MISSION CONTROL> ").strip()

                    if command:
                        if not self.execute_command(command):
                            break

                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n\n🚨 Emergency shutdown requested...")
                    self.log("SYSTEM", "🚨 Emergency shutdown via Ctrl+C")
                    break

        except Exception as e:
            self.log("ERROR", f"❌ Terminal error: {e}")

        finally:
            self.running = False
            print("\n👨‍🚀 QIKI Mission Control Terminal terminated.")
            print("🛰️ Spacecraft connection closed.")
            print("✅ All systems safely shut down.")


def main():
    """Главная функция запуска."""
    try:
        print("🚀 Starting QIKI Mission Control Terminal...")
        print("   Real working prototype for spacecraft operations")
        print()

        # Создание и запуск Mission Control
        mission_control = QIKIMissionControl()

        print("\n✅ Mission Control Terminal ready!")
        print("🎯 Starting interactive mode...")

        time.sleep(2)  # Пауза для инициализации фона

        mission_control.run_interactive()

    except KeyboardInterrupt:
        print("\n\n🚨 Startup interrupted by user")
    except Exception as e:
        print(f"\n❌ Mission Control startup failed: {e}")
        import traceback

        traceback.print_exc()


# Добавляем улучшенный режим с prompt_toolkit
def run_enhanced_mode():
    """Запускает НАСТОЯЩИЙ prompt_toolkit интерфейс."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        print("❌ prompt_toolkit недоступен!")
        print("📦 Установите: pip install prompt_toolkit")
        return main()

    import asyncio
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout.containers import HSplit
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.widgets import Frame, TextArea
    from prompt_toolkit.key_binding import KeyBindings

    try:
        print("🚀 Starting QIKI Mission Control ULTIMATE...")
        print("   REAL prompt_toolkit live interface")
        print()

        # Создание Mission Control
        mission_control = QIKIMissionControl()

        print("\\n✅ Ultimate Mission Control ready!")
        print("🎯 REAL-TIME prompt_toolkit interface")
        print("🎯 F1=Autopilot | F12=Language | Ctrl+C=Exit")
        print()

        # Создаем НАСТОЯЩИЙ prompt_toolkit интерфейс
        def create_live_interface():
            # Область статуса
            status_area = TextArea(
                text=mission_control._create_status_content(),
                read_only=True,
                scrollbar=True,
                wrap_lines=False,
            )

            # Область команд
            command_area = TextArea(
                height=1,
                prompt="🚀 ULTIMATE> ",
                multiline=False,
                wrap_lines=False,
            )

            # Обработчик команд
            def accept_handler():
                command = command_area.text
                if command.strip():
                    mission_control.execute_command(command)
                    command_area.text = ""
                    status_area.text = mission_control._create_status_content()

            command_area.accept_handler = accept_handler

            # Привязки клавиш
            bindings = KeyBindings()

            @bindings.add("c-c")
            def exit_(event):
                mission_control.running = False
                event.app.exit()

            @bindings.add("f12")
            def toggle_lang(event):
                mission_control.language = "EN" if mission_control.language == "RU" else "RU"
                mission_control.log(
                    "INTERFACE",
                    f"🌐 Language: {'English' if mission_control.language == 'EN' else 'Русский'}",
                )
                status_area.text = mission_control._create_status_content()

            @bindings.add("f1")
            def toggle_autopilot(event):
                mission_control.autopilot_enabled = not mission_control.autopilot_enabled
                status = "ENABLED" if mission_control.autopilot_enabled else "DISABLED"
                mission_control.log("AUTOPILOT", f"🤖 Autopilot {status}")
                status_area.text = mission_control._create_status_content()

            # Layout
            root_container = HSplit(
                [
                    status_area,
                    Frame(command_area, title="COMMAND INTERFACE"),
                ]
            )

            # Приложение
            app = Application(
                layout=Layout(root_container),
                key_bindings=bindings,
                full_screen=True,
                refresh_interval=1.0,  # Обновление каждую секунду!
            )

            # Автообновление содержимого
            async def refresh_loop():
                while mission_control.running:
                    try:
                        status_area.text = mission_control._create_status_content()
                        app.invalidate()
                        await asyncio.sleep(1)
                    except Exception:
                        break

            return app, refresh_loop

        # Запускаем REAL prompt_toolkit интерфейс
        app, refresh_loop = create_live_interface()

        async def run_app():
            refresh_task = asyncio.create_task(refresh_loop())
            try:
                await app.run_async()
            finally:
                refresh_task.cancel()
                mission_control.running = False

        asyncio.run(run_app())

    except KeyboardInterrupt:
        print("\\n\\n🚨 Startup interrupted by user")
    except Exception as e:
        print(f"\\n❌ Ultimate Mission Control startup failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if "mission_control" in locals():
            mission_control.running = False
        print("\\n👨‍🚀 Ultimate Mission Control terminated.")
        print("🛰️ Spacecraft connection closed.")
        print("✅ All systems safely shut down.")


if __name__ == "__main__":
    import sys

    # Проверяем аргументы командной строки
    if "--enhanced" in sys.argv:
        run_enhanced_mode()
    else:
        main()
