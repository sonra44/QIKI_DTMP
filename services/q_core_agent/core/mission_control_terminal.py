#!/usr/bin/env python3
"""
QIKI Mission Control Terminal
Терминальный интерфейс оператора для удаленного управления космическим аппаратом.
Дизайн в стиле NASA Mission Control / военного кокпита.
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
import threading

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea, Label, Button
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.application import get_app
    from prompt_toolkit.shortcuts import input_dialog, message_dialog
except ImportError:
    print("❌ prompt_toolkit не установлен. Устанавливаем...")
    os.system("pip install prompt_toolkit")
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea, Label, Button
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.application import get_app
    from prompt_toolkit.shortcuts import input_dialog, message_dialog

from ship_core import ShipCore
from ship_actuators import ShipActuatorController, ThrusterAxis, PropulsionMode, PowerAllocation
from test_ship_fsm import ShipLogicController, ShipState


class MissionControlTerminal:
    """
    Терминал управления полетом в стиле NASA Mission Control.
    Обеспечивает удаленное управление космическим аппаратом.
    """
    
    def __init__(self):
        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core)
        self.logic_controller = ShipLogicController(self.ship_core, self.actuator_controller)
        
        # Состояние интерфейса
        self.mission_time_start = time.time()
        self.current_command = ""
        self.log_messages = []
        self.telemetry_data = {}
        self.alert_level = "NOMINAL"  # NOMINAL, CAUTION, WARNING, EMERGENCY
        
        # Флаги режимов
        self.autopilot_enabled = False
        self.manual_control_enabled = True
        self.diagnostics_mode = False
        
        # Обновление данных в фоне
        self.running = True
        self.update_thread = threading.Thread(target=self._background_update, daemon=True)
        self.update_thread.start()
        
        self.log("MISSION CONTROL", "✅ QIKI Mission Control Terminal initialized")
        self.log("SPACECRAFT", f"🛰️ Connected to {self.ship_core.get_id()}")
    
    def log(self, system: str, message: str):
        """Добавляет сообщение в лог Mission Control."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        mission_time = self._get_mission_time()
        log_entry = f"[{timestamp}] [{mission_time}] {system}: {message}"
        self.log_messages.append(log_entry)
        if len(self.log_messages) > 50:  # Ограничиваем размер лога
            self.log_messages.pop(0)
    
    def _get_mission_time(self) -> str:
        """Получает время миссии в формате T+HH:MM:SS."""
        elapsed = int(time.time() - self.mission_time_start)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _background_update(self):
        """Фоновое обновление телеметрии и логики корабля."""
        while self.running:
            try:
                # Обновление логики корабля
                if self.autopilot_enabled:
                    logic_result = self.logic_controller.process_logic_cycle()
                    if logic_result.get('state_changed'):
                        self.log("AUTOPILOT", f"State: {logic_result['current_state']}")
                
                # Обновление телеметрии
                self._update_telemetry()
                
                # Проверка статуса системы
                self._check_system_alerts()
                
                time.sleep(2)  # Обновление каждые 2 секунды
                
            except Exception as e:
                self.log("SYSTEM", f"❌ Background update error: {e}")
                time.sleep(5)
    
    def _update_telemetry(self):
        """Обновляет телеметрические данные корабля."""
        try:
            hull = self.ship_core.get_hull_status()
            power = self.ship_core.get_power_status()
            propulsion = self.ship_core.get_propulsion_status()
            sensors = self.ship_core.get_sensor_status()
            life_support = self.ship_core.get_life_support_status()
            computing = self.ship_core.get_computing_status()
            
            self.telemetry_data = {
                'hull_integrity': hull.integrity,
                'reactor_output': power.reactor_output_mw,
                'reactor_max': power.reactor_max_output_mw,
                'battery_charge': power.battery_charge_mwh,
                'battery_capacity': power.battery_capacity_mwh,
                'reactor_temp': power.reactor_temperature_k,
                'main_drive_status': propulsion.main_drive_status,
                'main_drive_fuel': propulsion.main_drive_fuel_kg,
                'oxygen_level': life_support.atmosphere.get('oxygen_percent', 0),
                'co2_level': life_support.atmosphere.get('co2_ppm', 0),
                'pressure': life_support.atmosphere.get('pressure_kpa', 0),
                'qiki_status': computing.qiki_core_status,
                'qiki_temp': computing.qiki_temperature_k,
                'active_sensors': len(sensors.active_sensors),
                'propulsion_mode': self.actuator_controller.current_mode.value,
                'ship_state': self.logic_controller.current_state.value
            }
            
        except Exception as e:
            self.log("TELEMETRY", f"❌ Telemetry update failed: {e}")
    
    def _check_system_alerts(self):
        """Проверяет системы на предмет аварийных ситуаций."""
        try:
            prev_alert = self.alert_level
            
            # Критические проверки
            if (self.telemetry_data.get('hull_integrity', 100) < 30 or
                self.telemetry_data.get('oxygen_level', 21) < 16 or
                self.telemetry_data.get('reactor_temp', 0) > 3500):
                self.alert_level = "EMERGENCY"
            
            # Предупреждения
            elif (self.telemetry_data.get('hull_integrity', 100) < 60 or
                  self.telemetry_data.get('battery_charge', 0) / max(self.telemetry_data.get('battery_capacity', 1), 1) < 0.2 or
                  self.telemetry_data.get('main_drive_fuel', 0) < 50):
                self.alert_level = "WARNING"
            
            # Осторожность
            elif (self.telemetry_data.get('hull_integrity', 100) < 80 or
                  self.telemetry_data.get('co2_level', 0) > 1000 or
                  self.telemetry_data.get('reactor_temp', 0) > 3000):
                self.alert_level = "CAUTION"
            
            else:
                self.alert_level = "NOMINAL"
            
            # Лог изменений уровня тревоги
            if prev_alert != self.alert_level:
                self.log("ALERT SYSTEM", f"🚨 Alert level changed: {prev_alert} → {self.alert_level}")
                
        except Exception as e:
            self.log("ALERT SYSTEM", f"❌ Alert check failed: {e}")
    
    def _get_alert_color(self) -> str:
        """Возвращает цвет для текущего уровня тревоги."""
        colors = {
            "NOMINAL": "ansigreen",
            "CAUTION": "ansiyellow", 
            "WARNING": "ansired",
            "EMERGENCY": "ansiwhite bg:ansired blink"
        }
        return colors.get(self.alert_level, "ansiwhite")
    
    def _create_header(self) -> Window:
        """Создает заголовок Mission Control."""
        mission_time = self._get_mission_time()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        header_text = FormattedText([
            ("class:header", "╔══════════════════════════════════════════════════════════════════════════════════════════╗\n"),
            ("class:header", "║"),
            ("class:title", " QIKI MISSION CONTROL TERMINAL "),
            ("class:header", "                    "),
            ("class:mission_time", f"MISSION TIME: {mission_time}"),
            ("class:header", " ║\n"),
            ("class:header", "║"),
            ("class:spacecraft", f" SPACECRAFT: {self.ship_core.get_id()}"),
            ("class:header", "  "),
            ("class:time", f"UTC: {current_time}"),
            ("class:header", " ║\n"),
            ("class:header", "║"),
            ("class:alert", f" SYSTEM STATUS: "),
            (self._get_alert_color(), f"{self.alert_level}"),
            ("class:header", "                                           "),
            ("class:mode", f"MODE: {'AUTO' if self.autopilot_enabled else 'MANUAL'}"),
            ("class:header", " ║\n"),
            ("class:header", "╚══════════════════════════════════════════════════════════════════════════════════════════╝"),
        ])
        
        return Window(FormattedTextControl(header_text), height=5)
    
    def _create_telemetry_panel(self) -> Window:
        """Создает панель телеметрии."""
        hull_int = self.telemetry_data.get('hull_integrity', 0)
        reactor_pct = (self.telemetry_data.get('reactor_output', 0) / 
                      max(self.telemetry_data.get('reactor_max', 1), 1)) * 100
        battery_pct = (self.telemetry_data.get('battery_charge', 0) /
                      max(self.telemetry_data.get('battery_capacity', 1), 1)) * 100
        
        def format_bar(value: float, max_val: float = 100) -> str:
            """Форматирует значение как progress bar."""
            pct = min(100, max(0, (value / max_val) * 100))
            filled = int(pct / 5)  # 20 символов = 100%
            bar = "█" * filled + "░" * (20 - filled)
            return f"[{bar}] {value:6.1f}"
        
        telemetry_text = FormattedText([
            ("class:panel_title", "┌─ SPACECRAFT TELEMETRY ──────────────────────────┐\n"),
            ("class:panel", "│ "),
            ("class:label", "HULL INTEGRITY : "),
            ("ansigreen" if hull_int > 80 else "ansiyellow" if hull_int > 50 else "ansired", 
             format_bar(hull_int)),
            ("class:unit", " %"),
            ("class:panel", " │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "REACTOR OUTPUT : "),
            ("ansigreen" if reactor_pct > 50 else "ansiyellow", 
             format_bar(reactor_pct)),
            ("class:unit", " %"),
            ("class:panel", " │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "BATTERY CHARGE : "),
            ("ansigreen" if battery_pct > 50 else "ansiyellow" if battery_pct > 20 else "ansired",
             format_bar(battery_pct)),
            ("class:unit", " %"),
            ("class:panel", " │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "REACTOR TEMP   : "),
            ("ansiwhite", f"{self.telemetry_data.get('reactor_temp', 0):8.0f}"),
            ("class:unit", " K"),
            ("class:panel", "              │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "OXYGEN LEVEL   : "),
            ("ansigreen" if self.telemetry_data.get('oxygen_level', 0) > 18 else "ansired",
             f"{self.telemetry_data.get('oxygen_level', 0):8.1f}"),
            ("class:unit", " %"),
            ("class:panel", "              │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "CO2 LEVEL      : "),
            ("ansigreen" if self.telemetry_data.get('co2_level', 0) < 1000 else "ansiyellow",
             f"{self.telemetry_data.get('co2_level', 0):8.0f}"),
            ("class:unit", " ppm"),
            ("class:panel", "             │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "QIKI STATUS    : "),
            ("ansigreen" if self.telemetry_data.get('qiki_status') == 'active' else "ansired",
             f"{self.telemetry_data.get('qiki_status', 'unknown'):>8}"),
            ("class:panel", "                │\n"),
            
            ("class:panel_title", "└─────────────────────────────────────────────────┘"),
        ])
        
        return Window(FormattedTextControl(telemetry_text), height=10)
    
    def _create_propulsion_panel(self) -> Window:
        """Создает панель двигательной системы."""
        main_fuel = self.telemetry_data.get('main_drive_fuel', 0)
        prop_mode = self.telemetry_data.get('propulsion_mode', 'idle')
        drive_status = self.telemetry_data.get('main_drive_status', 'unknown')
        
        def fuel_bar(fuel_kg: float) -> str:
            max_fuel = 500  # Примерная максимальная емкость
            pct = min(100, (fuel_kg / max_fuel) * 100)
            filled = int(pct / 5)
            bar = "█" * filled + "░" * (20 - filled)
            return f"[{bar}] {fuel_kg:6.1f} kg"
        
        propulsion_text = FormattedText([
            ("class:panel_title", "┌─ PROPULSION SYSTEMS ────────────────────────────┐\n"),
            ("class:panel", "│ "),
            ("class:label", "MAIN DRIVE     : "),
            ("ansigreen" if drive_status in ['ready', 'idle', 'active'] else "ansired",
             f"{drive_status:>8}"),
            ("class:panel", "                │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "PROPULSION MODE: "),
            ("ansigreen" if prop_mode == 'idle' else "ansiyellow" if prop_mode == 'maneuvering' else "ansiblue",
             f"{prop_mode.upper():>8}"),
            ("class:panel", "               │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "MAIN FUEL      : "),
            ("ansigreen" if main_fuel > 100 else "ansiyellow" if main_fuel > 50 else "ansired",
             fuel_bar(main_fuel)),
            ("class:panel", " │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "ACTIVE SENSORS : "),
            ("ansiwhite", f"{self.telemetry_data.get('active_sensors', 0):8d}"),
            ("class:panel", "                │\n"),
            
            ("class:panel", "│ "),
            ("class:label", "SHIP STATE     : "),
            ("ansiblue" if 'FLIGHT' in self.telemetry_data.get('ship_state', '') else "ansigreen",
             f"{self.telemetry_data.get('ship_state', 'UNKNOWN'):>8}"),
            ("class:panel", "   │\n"),
            
            ("class:panel_title", "└─────────────────────────────────────────────────┘"),
        ])
        
        return Window(FormattedTextControl(propulsion_text), height=8)
    
    def _create_command_log(self) -> Window:
        """Создает окно лога команд и событий."""
        log_text = "┌─ MISSION LOG ─────────────────────────────────────────────────────────────────────────┐\n"
        
        # Показываем последние 15 записей лога
        recent_logs = self.log_messages[-15:] if len(self.log_messages) > 15 else self.log_messages
        
        for log_entry in recent_logs:
            # Обрезаем длинные сообщения
            if len(log_entry) > 85:
                log_entry = log_entry[:82] + "..."
            log_text += f"│ {log_entry:<85} │\n"
        
        # Заполняем пустые строки если лог короткий
        for _ in range(15 - len(recent_logs)):
            log_text += f"│{' ' * 87}│\n"
        
        log_text += "└───────────────────────────────────────────────────────────────────────────────────────┘"
        
        return Window(FormattedTextControl(log_text), height=18)
    
    def _create_command_input(self) -> TextArea:
        """Создает поле ввода команд."""
        command_area = TextArea(
            prompt="MISSION CONTROL> ",
            multiline=False,
            wrap_lines=False,
            height=3,
            scrollbar=False
        )
        return command_area
    
    def _create_layout(self) -> Layout:
        """Создает основной layout интерфейса."""
        
        # Верхняя панель - заголовок
        header = self._create_header()
        
        # Левая колонка - телеметрия и двигатели
        left_column = HSplit([
            self._create_telemetry_panel(),
            self._create_propulsion_panel(),
        ])
        
        # Правая колонка - лог
        right_column = self._create_command_log()
        
        # Средняя панель - данные
        middle_panel = VSplit([
            left_column,
            Window(width=2),  # Разделитель
            right_column,
        ])
        
        # Нижняя панель - ввод команд
        command_input = Frame(
            self._create_command_input(),
            title="COMMAND INTERFACE"
        )
        
        # Основной layout
        main_layout = HSplit([
            header,
            Window(height=1),  # Разделитель
            middle_panel,
            Window(height=1),  # Разделитель
            command_input,
        ])
        
        return Layout(main_layout)
    
    def _create_keybindings(self) -> KeyBindings:
        """Создает привязки клавиш для управления."""
        kb = KeyBindings()
        
        @kb.add('c-c')
        def exit_app(event):
            """Выход из приложения (Ctrl+C)."""
            self.running = False
            self.log("SYSTEM", "👨‍🚀 Mission Control Terminal shutting down...")
            event.app.exit()
        
        @kb.add('f1')
        def toggle_autopilot(event):
            """Переключение автопилота (F1)."""
            self.autopilot_enabled = not self.autopilot_enabled
            mode = "ENABLED" if self.autopilot_enabled else "DISABLED"
            self.log("AUTOPILOT", f"🤖 Autopilot {mode}")
        
        @kb.add('f2')
        def emergency_stop(event):
            """Аварийная остановка (F2)."""
            success = self.actuator_controller.emergency_stop()
            if success:
                self.log("EMERGENCY", "🚨 EMERGENCY STOP EXECUTED")
            else:
                self.log("EMERGENCY", "❌ Emergency stop failed")
        
        @kb.add('f3')
        def diagnostics_mode(event):
            """Режим диагностики (F3)."""
            self.diagnostics_mode = not self.diagnostics_mode
            mode = "ENABLED" if self.diagnostics_mode else "DISABLED"
            self.log("DIAGNOSTICS", f"🔧 Diagnostics mode {mode}")
        
        @kb.add('enter')
        def execute_command(event):
            """Выполнение команды (Enter)."""
            command = event.app.layout.current_window.content.text.strip()
            if command:
                self._execute_command(command)
                event.app.layout.current_window.content.text = ""
        
        return kb
    
    def _execute_command(self, command: str):
        """Выполняет команду оператора."""
        self.log("OPERATOR", f"💬 Command: {command}")
        
        cmd_parts = command.lower().split()
        if not cmd_parts:
            return
        
        cmd = cmd_parts[0]
        
        try:
            # Команды двигательной системы
            if cmd == "thrust":
                if len(cmd_parts) >= 2:
                    thrust_pct = float(cmd_parts[1])
                    success = self.actuator_controller.set_main_drive_thrust(thrust_pct)
                    if success:
                        self.log("PROPULSION", f"🚀 Main drive thrust set to {thrust_pct}%")
                    else:
                        self.log("PROPULSION", f"❌ Failed to set thrust to {thrust_pct}%")
                else:
                    self.log("COMMAND", "❌ Usage: thrust <percentage>")
            
            # RCS команды
            elif cmd == "rcs":
                if len(cmd_parts) >= 3:
                    direction = cmd_parts[1].upper()
                    thrust_pct = float(cmd_parts[2])
                    
                    axis_map = {
                        "FORWARD": ThrusterAxis.FORWARD,
                        "BACKWARD": ThrusterAxis.BACKWARD,
                        "PORT": ThrusterAxis.PORT,
                        "STARBOARD": ThrusterAxis.STARBOARD
                    }
                    
                    if direction in axis_map:
                        success = self.actuator_controller.fire_rcs_thruster(
                            axis_map[direction], thrust_pct, 2.0
                        )
                        if success:
                            self.log("RCS", f"🎯 {direction} thruster fired at {thrust_pct}%")
                        else:
                            self.log("RCS", f"❌ Failed to fire {direction} thruster")
                    else:
                        self.log("COMMAND", "❌ Invalid RCS direction. Use: forward, backward, port, starboard")
                else:
                    self.log("COMMAND", "❌ Usage: rcs <direction> <percentage>")
            
            # Управление питанием
            elif cmd == "power":
                if len(cmd_parts) >= 2:
                    if cmd_parts[1] == "status":
                        power_status = self.ship_core.get_power_status()
                        self.log("POWER", f"⚡ Reactor: {power_status.reactor_output_mw:.1f}MW")
                        self.log("POWER", f"⚡ Battery: {power_status.battery_charge_mwh:.1f}MWh")
                    else:
                        self.log("COMMAND", "❌ Usage: power status")
                else:
                    self.log("COMMAND", "❌ Usage: power <subcommand>")
            
            # Управление сенсорами
            elif cmd == "sensor":
                if len(cmd_parts) >= 3:
                    action = cmd_parts[1]
                    sensor_id = cmd_parts[2]
                    
                    if action == "activate":
                        success = self.actuator_controller.activate_sensor(sensor_id)
                        if success:
                            self.log("SENSORS", f"📡 Sensor {sensor_id} activated")
                        else:
                            self.log("SENSORS", f"❌ Failed to activate {sensor_id}")
                    elif action == "deactivate":
                        success = self.actuator_controller.deactivate_sensor(sensor_id)
                        if success:
                            self.log("SENSORS", f"📡 Sensor {sensor_id} deactivated")
                        else:
                            self.log("SENSORS", f"❌ Failed to deactivate {sensor_id}")
                    else:
                        self.log("COMMAND", "❌ Usage: sensor <activate|deactivate> <sensor_id>")
                else:
                    self.log("COMMAND", "❌ Usage: sensor <activate|deactivate> <sensor_id>")
            
            # Статус систем
            elif cmd == "status":
                summary = self.logic_controller.get_ship_status_summary()
                self.log("STATUS", f"🛰️ Ship State: {summary.get('current_state', 'UNKNOWN')}")
                self.log("STATUS", f"🛰️ Systems: {summary.get('overall_status', 'UNKNOWN')}")
                self.log("STATUS", f"🛰️ Navigation: {'OK' if summary.get('navigation_capable') else 'LIMITED'}")
            
            # Справка
            elif cmd == "help":
                self.log("HELP", "💡 Available commands:")
                self.log("HELP", "  thrust <0-100>        - Set main drive thrust")
                self.log("HELP", "  rcs <dir> <0-100>     - Fire RCS thruster")
                self.log("HELP", "  power status          - Show power status")
                self.log("HELP", "  sensor activate <id>  - Activate sensor")
                self.log("HELP", "  status                - Show ship status")
                self.log("HELP", "  help                  - Show this help")
                self.log("HELP", "💡 Hotkeys: F1=Autopilot, F2=Emergency, F3=Diagnostics")
            
            else:
                self.log("COMMAND", f"❌ Unknown command '{cmd}'. Type 'help' for available commands.")
                
        except ValueError:
            self.log("COMMAND", "❌ Invalid numeric parameter")
        except Exception as e:
            self.log("COMMAND", f"❌ Command execution error: {e}")
    
    def _create_style(self) -> Style:
        """Создает стиль интерфейса в стиле NASA Mission Control."""
        return Style.from_dict({
            # Основные элементы
            'header': 'ansiwhite bg:ansiblue',
            'title': 'ansiwhite bg:ansiblue bold',
            'panel': 'ansiwhite bg:ansiblack',
            'panel_title': 'ansiwhite bg:ansiblue',
            
            # Время и статусы
            'mission_time': 'ansigreen bg:ansiblue bold',
            'time': 'ansiwhite bg:ansiblue',
            'spacecraft': 'ansiyellow bg:ansiblue bold',
            'alert': 'ansiwhite bg:ansiblue',
            'mode': 'ansiwhite bg:ansiblue',
            
            # Телеметрия
            'label': 'ansicyan',
            'unit': 'ansiwhite',
            
            # Текстовые поля
            'text-area': 'ansiwhite bg:ansiblack',
            'text-area.prompt': 'ansigreen bg:ansiblack bold',
        })
    
    async def run_async(self):
        """Запускает асинхронный интерфейс."""
        app = Application(
            layout=self._create_layout(),
            key_bindings=self._create_keybindings(),
            style=self._create_style(),
            full_screen=True,
            refresh_interval=1.0  # Обновление каждую секунду
        )
        
        try:
            await app.run_async()
        finally:
            self.running = False
    
    def run(self):
        """Запускает Mission Control Terminal."""
        print("🚀 Starting QIKI Mission Control Terminal...")
        print("   Press F1 for Autopilot, F2 for Emergency Stop, F3 for Diagnostics")
        print("   Press Ctrl+C to exit")
        print()
        
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            print("\n👨‍🚀 Mission Control Terminal terminated. Farewell, operator.")


# Точка входа
if __name__ == "__main__":
    try:
        terminal = MissionControlTerminal()
        terminal.run()
    except Exception as e:
        print(f"❌ Failed to start Mission Control Terminal: {e}")
        import traceback
        traceback.print_exc()