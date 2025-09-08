#!/usr/bin/env python3
"""
QIKI Mission Control Ultimate - Версия для реального терминала
Использует prompt_toolkit с правильной обработкой терминала.
Работает в любом Unix/Linux терминале, включая Termux.
"""

import sys
import os
import asyncio
import time
import threading
import math
import random
from datetime import datetime

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Robust prompt_toolkit import with fallback
try:
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.application import get_app

    PROMPT_TOOLKIT_AVAILABLE = True
    print("✅ prompt_toolkit loaded successfully")
except ImportError as e:
    print(f"❌ prompt_toolkit not available: {e}")
    print("📦 Installing prompt_toolkit...")
    try:
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "prompt_toolkit"]
        )
        from prompt_toolkit import Application
        from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import Frame, TextArea
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style
        from prompt_toolkit.formatted_text import FormattedText

        PROMPT_TOOLKIT_AVAILABLE = True
        print("✅ prompt_toolkit installed and loaded")
    except Exception as install_error:
        print(f"❌ Failed to install prompt_toolkit: {install_error}")
        PROMPT_TOOLKIT_AVAILABLE = False

from ship_core import ShipCore
from ship_actuators import ShipActuatorController, PropulsionMode
from test_ship_fsm import ShipLogicController


class QIKIMissionControlUltimate:
    """
    Ultimate Mission Control Terminal с prompt_toolkit.
    Профессиональный живой интерфейс для управления космическим аппаратом.
    """

    def __init__(self):
        print("🚀 Initializing QIKI Mission Control Ultimate...")

        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core)
        self.logic_controller = ShipLogicController(
            self.ship_core, self.actuator_controller
        )

        # Инициализируем autopilot_enabled
        self.autopilot_enabled = False

        # Состояние Mission Control
        self.mission_start_time = time.time()
        self.running = True
        self.language = "RU"  # RU или EN
        self.current_view = "MAIN"  # MAIN, SENSORS, POWER, DIAG

        # Живые параметры миссии
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

        self.event_log = []
        self.command_input = ""

        # Динамические переменные для реализма
        self.simulation_time = 0
        self.last_update = time.time()
        self.fuel_consumption_rate = 0.1  # кг/час
        self.power_fluctuation = 0

        # Инициализируем живые параметры сразу
        self.live_telemetry = {
            "hull_integrity": 100.0,
            "reactor_output": 35.0,
            "reactor_max": 50.0,
            "battery_charge": 10.5,
            "battery_capacity": 12.0,
            "reactor_temp": 2800.0,
            "main_drive_fuel": 450.0,
            "oxygen_level": 21.0,
            "co2_level": 400.0,
            "pressure": 101.3,
            "qiki_status": "active",
            "qiki_temp": 295.0,
            "active_sensors": 2,
            "propulsion_mode": "IDLE",
            "ship_state": "SHIP_STARTUP",
            "nav_x": 324167.89,
            "nav_y": -52631.44,
            "nav_z": 125.61,
            "velocity_abs": 2437.0,
            "velocity_rel": 18.0,
            "anomaly_distance": 32.17,
            "deep_scan_progress": 0.0,
            "comm_signal_strength": 80.0,
            "comm_quality": 80.0,
            "solar_efficiency": 100.0,
            "thruster_efficiency": [98.0, 98.0, 98.0, 98.0],
            "sensor_power": 1.2,
        }

        # Фоновые процессы
        self.background_thread = threading.Thread(
            target=self._background_simulation, daemon=True
        )
        self.background_thread.start()

        self.log(
            "СИСТЕМА / SYSTEM",
            "✅ QIKI Mission Control Ultimate инициализирован / initialized",
        )
        self.log(
            "КОРАБЛЬ / SPACECRAFT",
            f"🛰️ Подключен к / Connected to {self.ship_core.get_id()}",
        )

        print(f"✅ Connected to spacecraft: {self.ship_core.get_id()}")
        print("🎯 Mission Control Ultimate ready!")

    def log(self, system: str, message: str):
        """Добавляет событие в журнал."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        mission_time = self._get_mission_time()
        self.event_log.append(
            {
                "time": timestamp,
                "mission_time": mission_time,
                "system": system,
                "message": message,
            }
        )
        if len(self.event_log) > 20:
            self.event_log = self.event_log[-20:]

    def _get_mission_time(self) -> str:
        """Получает время миссии в формате T+HH:MM:SS."""
        elapsed = int(time.time() - self.mission_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _background_simulation(self):
        """Фоновая симуляция живых параметров."""
        while self.running:
            try:
                current_time = time.time()
                dt = current_time - self.last_update
                self.simulation_time += dt
                self.last_update = current_time

                # Обновление живых параметров
                self._update_live_telemetry(dt)

                # Логические события
                if random.random() < 0.02:  # 2% шанс события каждые 2 секунды
                    self._generate_random_event()

                # Автопилот
                if hasattr(self, "autopilot_enabled") and self.autopilot_enabled:
                    result = self.logic_controller.process_logic_cycle()
                    if result.get("state_changed"):
                        self.log(
                            "АВТОПИЛОТ / AUTOPILOT",
                            f"🤖 Состояние: {result['current_state']}",
                        )

                time.sleep(2)  # Обновление каждые 2 секунды

            except Exception as e:
                self.log(
                    "СИСТЕМА / SYSTEM", f"❌ Ошибка симуляции / Simulation error: {e}"
                )
                time.sleep(5)

    def _update_live_telemetry(self, dt: float):
        """Обновляет живые телеметрические данные."""
        try:
            # Получаем базовые данные корабля
            hull = self.ship_core.get_hull_status()
            power = self.ship_core.get_power_status()
            propulsion = self.ship_core.get_propulsion_status()
            sensors = self.ship_core.get_sensor_status()
            life_support = self.ship_core.get_life_support_status()
            computing = self.ship_core.get_computing_status()

            # Добавляем живые флуктуации
            self.power_fluctuation = 0.5 * math.sin(
                self.simulation_time * 0.1
            ) + random.uniform(-0.3, 0.3)

            # Расход топлива зависит от режима двигателей
            fuel_rate = self.fuel_consumption_rate
            if self.actuator_controller.current_mode == PropulsionMode.CRUISE:
                fuel_rate *= 3.0
            elif self.actuator_controller.current_mode == PropulsionMode.MANEUVERING:
                fuel_rate *= 1.5

            # Обновляем топливо (симуляция)
            current_fuel = propulsion.main_drive_fuel_kg
            new_fuel = max(0, current_fuel - fuel_rate * dt / 3600)  # dt в часах

            self.live_telemetry = {
                # Базовые параметры с живыми изменениями
                "hull_integrity": hull.integrity,
                "reactor_output": power.reactor_output_mw + self.power_fluctuation,
                "reactor_max": power.reactor_max_output_mw,
                "battery_charge": power.battery_charge_mwh,
                "battery_capacity": power.battery_capacity_mwh,
                "reactor_temp": power.reactor_temperature_k + random.uniform(-5, 5),
                "main_drive_fuel": new_fuel,
                "oxygen_level": life_support.atmosphere.get("oxygen_percent", 0)
                + random.uniform(-0.1, 0.1),
                "co2_level": life_support.atmosphere.get("co2_ppm", 0)
                + random.uniform(-5, 10),
                "pressure": life_support.atmosphere.get("pressure_kpa", 0)
                + random.uniform(-0.5, 0.5),
                "qiki_status": computing.qiki_core_status,
                "qiki_temp": computing.qiki_temperature_k + random.uniform(-2, 2),
                "active_sensors": len(sensors.active_sensors),
                "propulsion_mode": self.actuator_controller.current_mode.value,
                "ship_state": self.logic_controller.current_state.value,
                # Дополнительные живые параметры для панелей
                "nav_x": 324167.89 + random.uniform(-10, 10),
                "nav_y": -52631.44 + random.uniform(-10, 10),
                "nav_z": 125.61 + random.uniform(-1, 1),
                "velocity_abs": 2437 + random.uniform(-5, 5),
                "velocity_rel": 18 + random.uniform(-2, 2),
                "anomaly_distance": max(
                    0.5, 32.17 - (self.simulation_time * 0.01)
                ),  # Приближаемся
                "deep_scan_progress": min(100, (self.simulation_time * 0.8) % 100),
                "comm_signal_strength": 80 + random.uniform(-5, 5),
                "comm_quality": 80 + random.uniform(-3, 3),
                "solar_efficiency": 100 if random.random() > 0.1 else 95,  # Иногда пыль
                "thruster_efficiency": [98 + random.uniform(-2, 2) for _ in range(4)],
                "sensor_power": 1.2 + random.uniform(-0.1, 0.1),
            }

            # Обновление прогресса миссии
            if self.mission_data["progress"] < 100:
                self.mission_data["progress"] += dt * 0.5  # 0.5% в секунду
                self.mission_data["eta_seconds"] = max(
                    0, self.mission_data["eta_seconds"] - dt
                )

        except Exception as e:
            self.log(
                "ТЕЛЕМЕТРИЯ / TELEMETRY", f"❌ Ошибка обновления / Update error: {e}"
            )

    def _generate_random_event(self):
        """Генерирует случайные события для реализма."""
        events_ru_en = [
            ("СЕНСОРЫ / SENSORS", "📡 Обнаружен микро-мусор / Micro-debris detected"),
            (
                "ПИТАНИЕ / POWER",
                "⚡ Флуктуация солнечных панелей / Solar panel fluctuation",
            ),
            ("НАВИГАЦИЯ / NAV", "🧭 Корректировка курса / Course correction"),
            ("СВЯЗЬ / COMM", "📻 Переключение частоты / Frequency switch"),
            ("ДИАГНОСТ. / DIAG", "🔧 Автопроверка систем / System self-check"),
            (
                "ДВИГАТЕЛИ / PROP",
                "🚀 Микрокоррекция ориентации / Orientation microcorrection",
            ),
        ]

        system, message = random.choice(events_ru_en)
        self.log(system, message)

    def _format_bar(self, value: float, max_val: float = 100, width: int = 10) -> str:
        """Форматирует прогресс-бар."""
        pct = min(100, max(0, (value / max_val) * 100))
        filled = int(pct * width / 100)
        return "█" * filled + "░" * (width - filled)

    def _create_header_window(self) -> Window:
        """Создает заголовок с переключением языка и времени."""
        mission_time = self._get_mission_time()
        current_time = datetime.now().strftime("%H:%M:%S UTC")

        if self.language == "RU":
            title = "🚀 КИКИ ЦЕНТР УПРАВЛЕНИЯ ПОЛЕТОМ ULTIMATE"
            lang_hint = "[F12] Switch to English"
        else:
            title = "🚀 QIKI MISSION CONTROL CENTER ULTIMATE"
            lang_hint = "[F12] Переключить на Русский"

        header_text = FormattedText(
            [
                ("class:header", "╔" + "═" * 98 + "╗\\n"),
                ("class:header", "║"),
                ("class:title", f"{title:^98}"),
                ("class:header", "║\\n"),
                ("class:header", "║ "),
                ("class:spacecraft", f"🛰️ {self.ship_core.get_id():<30}"),
                ("class:mission_time", f"{mission_time:>15}"),
                ("class:time", f"{current_time:>15}"),
                ("class:lang", f"{lang_hint:>30}"),
                ("class:header", " ║\\n"),
                ("class:header", "╚" + "═" * 98 + "╝"),
            ]
        )

        return Window(FormattedTextControl(header_text), height=4)

    def _create_main_content_window(self) -> Window:
        """Создает основное содержимое интерфейса."""
        # Телеметрия
        hull_int = self.live_telemetry.get("hull_integrity", 100)
        reactor_out = self.live_telemetry.get("reactor_output", 35)
        reactor_max = self.live_telemetry.get("reactor_max", 50)
        battery_charge = self.live_telemetry.get("battery_charge", 10.5)
        battery_cap = self.live_telemetry.get("battery_capacity", 12)
        reactor_temp = self.live_telemetry.get("reactor_temp", 2800)
        oxygen = self.live_telemetry.get("oxygen_level", 21.0)
        co2 = self.live_telemetry.get("co2_level", 400)

        # Навигация
        nav_x = self.live_telemetry.get("nav_x", 324167.89)
        nav_y = self.live_telemetry.get("nav_y", -52631.44)
        nav_z = self.live_telemetry.get("nav_z", 125.61)
        vel_abs = self.live_telemetry.get("velocity_abs", 2437)
        vel_rel = self.live_telemetry.get("velocity_rel", 18)
        anomaly_dist = self.live_telemetry.get("anomaly_distance", 32.17)

        # Миссия
        progress = self.mission_data["progress"]
        eta_hours = int(self.mission_data["eta_seconds"] // 3600)
        eta_mins = int((self.mission_data["eta_seconds"] % 3600) // 60)

        reactor_pct = (reactor_out / reactor_max) * 100
        battery_pct = (battery_charge / battery_cap) * 100

        if self.language == "RU":
            system_title = "СИСТЕМЫ / SYSTEMS"
            nav_title = "НАВИГАЦИЯ / NAVIGATION"
            mission_title = "МИССИЯ / MISSION"
            coords_label = "Координаты"
            velocity_label = "Скорость"
            progress_label = "Прогресс"
            etc_label = f"ETC: {eta_hours:02}ч {eta_mins:02}м"
        else:
            system_title = "SYSTEMS / СИСТЕМЫ"
            nav_title = "NAVIGATION / НАВИГАЦИЯ"
            mission_title = "MISSION / МИССИЯ"
            coords_label = "Coordinates"
            velocity_label = "Velocity"
            progress_label = "Progress"
            etc_label = f"ETC: {eta_hours:02}h {eta_mins:02}m"

        content_text = FormattedText(
            [
                # Системы
                ("class:panel_title", f"┌─ {system_title} " + "─" * 30 + "┐\\n"),
                ("class:panel", "│ "),
                ("class:label", "🛡️  КОРПУС / HULL    : "),
                (
                    "ansigreen"
                    if hull_int > 80
                    else "ansiyellow"
                    if hull_int > 50
                    else "ansired",
                    f"[{self._format_bar(hull_int)}] {hull_int:5.1f}%",
                ),
                ("class:panel", " │\\n"),
                ("class:panel", "│ "),
                ("class:label", "⚡ РЕАКТОР / REACTOR : "),
                (
                    "ansigreen" if reactor_pct > 50 else "ansiyellow",
                    f"[{self._format_bar(reactor_pct)}] {reactor_pct:5.1f}%",
                ),
                ("class:panel", " │\\n"),
                ("class:panel", "│ "),
                ("class:label", "🔋 БАТАРЕЯ / BATTERY : "),
                (
                    "ansigreen"
                    if battery_pct > 50
                    else "ansiyellow"
                    if battery_pct > 20
                    else "ansired",
                    f"[{self._format_bar(battery_pct)}] {battery_pct:5.1f}%",
                ),
                ("class:panel", " │\\n"),
                ("class:panel", "│ "),
                ("class:label", "🌡️  ТЕМП.РЕАК / R.TEMP: "),
                ("ansiwhite", f"{reactor_temp:8.0f} К"),
                ("class:panel", "             │\\n"),
                ("class:panel", "│ "),
                ("class:label", "💨 КИСЛОРОД / OXYGEN : "),
                ("ansigreen" if oxygen > 18 else "ansired", f"{oxygen:8.1f} %"),
                ("class:panel", "             │\\n"),
                ("class:panel_title", "└" + "─" * 48 + "┘\\n\\n"),
                # Навигация
                ("class:panel_title", f"┌─ {nav_title} " + "─" * 25 + "┐\\n"),
                ("class:panel", f"│ {coords_label}:\\n"),
                ("class:panel", f"│ ├─ X: {nav_x:+12.2f} km\\n"),
                ("class:panel", f"│ ├─ Y: {nav_y:+12.2f} km\\n"),
                ("class:panel", f"│ ├─ Z: {nav_z:+12.2f} km\\n"),
                ("class:panel", "│ │\\n"),
                ("class:panel", f"│ {velocity_label}:\\n"),
                ("class:panel", f"│ ├─ Абсолютная: {vel_abs:4.0f} м/с\\n"),
                ("class:panel", f"│ ├─ Относительная: {vel_rel:+3.0f} м/с\\n"),
                ("class:panel", f"│ ╰─ До цели: {anomaly_dist:6.2f} км\\n"),
                ("class:panel_title", "└" + "─" * 48 + "┘\\n\\n"),
                # Миссия
                ("class:panel_title", f"┌─ {mission_title} " + "─" * 30 + "┐\\n"),
                ("class:panel", f"│ ID: {self.mission_data['designator']}\\n"),
                (
                    "class:panel",
                    f"│ {progress_label}: [{self._format_bar(progress)}] {progress:4.1f}%\\n",
                ),
                ("class:panel", f"│ {etc_label}\\n"),
                (
                    "class:panel",
                    f"│ Этапы: {sum(1 for s in self.mission_data['steps'] if s['done'])}/{len(self.mission_data['steps'])} завершено\\n",
                ),
                ("class:panel_title", "└" + "─" * 48 + "┘"),
            ]
        )

        return Window(FormattedTextControl(content_text), height=30)

    def _create_log_window(self) -> Window:
        """Создает окно журнала событий."""
        if self.language == "RU":
            title = "ЖУРНАЛ СОБЫТИЙ / EVENT LOG"
        else:
            title = "EVENT LOG / ЖУРНАЛ СОБЫТИЙ"

        log_text = FormattedText(
            [("class:panel_title", f"┌─ {title} " + "─" * 15 + "┐\\n")]
        )

        # Показываем последние 8 событий
        recent_events = (
            self.event_log[-8:] if len(self.event_log) >= 8 else self.event_log
        )

        for event in recent_events:
            message = event["message"]
            if len(message) > 44:
                message = message[:41] + "..."
            log_text.append(
                (
                    "class:panel",
                    f"│ [{event['time']}] {event['system'][:12]}: {message}\\n",
                )
            )

        # Заполняем пустые строки
        for _ in range(8 - len(recent_events)):
            log_text.append(("class:panel", "│" + " " * 48 + "\\n"))

        log_text.append(("class:panel_title", "└" + "─" * 48 + "┘"))

        return Window(FormattedTextControl(log_text), height=11)

    def _process_command(self, command: str):
        """Обрабатывает введенную команду."""
        if not command.strip():
            return

        cmd_parts = command.lower().split()
        cmd = cmd_parts[0]

        self.log("ОПЕРАТОР / OPERATOR", f"💬 Команда: {command}")

        try:
            if cmd == "thrust":
                if len(cmd_parts) >= 2:
                    thrust_pct = float(cmd_parts[1])
                    if 0 <= thrust_pct <= 100:
                        success = self.actuator_controller.set_main_drive_thrust(
                            thrust_pct
                        )
                        if success:
                            self.log(
                                "ДВИГАТЕЛИ / PROPULSION",
                                f"🚀 Главный двигатель: {thrust_pct}%",
                            )
                    else:
                        self.log("ОШИБКА / ERROR", "❌ Тяга должна быть 0-100%")
                else:
                    self.log("ОШИБКА / ERROR", "❌ Использование: thrust <0-100>")

            elif cmd == "autopilot":
                self.autopilot_enabled = not getattr(self, "autopilot_enabled", False)
                status = (
                    "ВКЛЮЧЕН / ENABLED"
                    if self.autopilot_enabled
                    else "ВЫКЛЮЧЕН / DISABLED"
                )
                self.log("АВТОПИЛОТ / AUTOPILOT", f"🤖 Автопилот {status}")

            elif cmd in ["lang", "language", "язык"]:
                self.language = "EN" if self.language == "RU" else "RU"
                lang_name = "Русский" if self.language == "RU" else "English"
                self.log("ИНТЕРФЕЙС / INTERFACE", f"🌐 Язык: {lang_name}")

            elif cmd == "emergency":
                success = self.actuator_controller.emergency_stop()
                if success:
                    self.log("АВАРИЙН. / EMERGENCY", "🚨 АВАРИЙНАЯ ОСТАНОВКА")
                else:
                    self.log("ОШИБКА / ERROR", "❌ Ошибка аварийной остановки")

            elif cmd == "status":
                summary = self.logic_controller.get_ship_status_summary()
                self.log(
                    "СТАТУС / STATUS", f"🛰️ Состояние: {summary.get('current_state')}"
                )
                self.log(
                    "СТАТУС / STATUS", f"🔧 Системы: {summary.get('overall_status')}"
                )

            else:
                self.log(
                    "ОШИБКА / ERROR",
                    f"❌ Неизвестная команда '{cmd}'. Доступные: thrust, autopilot, lang, emergency, status",
                )

        except ValueError:
            self.log("ОШИБКА / ERROR", "❌ Неверный числовой параметр")
        except Exception as e:
            self.log("ОШИБКА / ERROR", f"❌ Ошибка команды: {e}")

    def _create_command_window(self) -> TextArea:
        """Создает окно ввода команд."""
        if self.language == "RU":
            prompt = "КОМАНДА> "
        else:
            prompt = "COMMAND> "

        command_area = TextArea(
            prompt=prompt, multiline=False, wrap_lines=False, height=3, scrollbar=False
        )

        # Обработчик ввода команд
        def accept_handler(buffer):
            command = buffer.text
            buffer.reset()
            self._process_command(command)

        command_area.buffer.accept_handler = accept_handler
        return command_area

    def _create_layout(self) -> Layout:
        """Создает основной layout интерфейса."""

        # Заголовок
        header = self._create_header_window()

        # Основной контент
        main_content = self._create_main_content_window()

        # Журнал событий
        log_panel = self._create_log_window()

        # Основная панель
        main_panel = HSplit(
            [
                VSplit(
                    [
                        main_content,
                        Window(width=2),  # Разделитель
                        log_panel,
                    ]
                ),
            ]
        )

        # Командная строка
        command_input = Frame(
            self._create_command_window(),
            title="КОМАНДНЫЙ ИНТЕРФЕЙС / COMMAND INTERFACE",
        )

        # Финальный layout
        return Layout(
            HSplit(
                [
                    header,
                    Window(height=1),
                    main_panel,
                    Window(height=1),
                    command_input,
                ]
            )
        )

    def _create_keybindings(self) -> KeyBindings:
        """Создает привязки клавиш."""
        kb = KeyBindings()

        @kb.add("c-c")
        def exit_app(event):
            self.running = False
            self.log("СИСТЕМА / SYSTEM", "👨‍🚀 Завершение работы / Shutting down")
            event.app.exit()

        @kb.add("f12")
        def toggle_language(event):
            self.language = "EN" if self.language == "RU" else "RU"
            lang_name = "Русский" if self.language == "RU" else "English"
            self.log("ИНТЕРФЕЙС / UI", f"🌐 Язык: {lang_name} / Language: {lang_name}")

        @kb.add("f1")
        def toggle_autopilot(event):
            self.autopilot_enabled = not getattr(self, "autopilot_enabled", False)
            status = (
                "ВКЛЮЧЕН / ENABLED" if self.autopilot_enabled else "ВЫКЛЮЧЕН / DISABLED"
            )
            self.log("АВТОПИЛОТ / AUTOPILOT", f"🤖 {status}")

        @kb.add("f2")
        def emergency_stop(event):
            success = self.actuator_controller.emergency_stop()
            if success:
                self.log(
                    "АВАРИЙН. / EMERGENCY", "🚨 АВАРИЙНАЯ ОСТАНОВКА / EMERGENCY STOP"
                )
            else:
                self.log("АВАРИЙН. / EMERGENCY", "❌ Ошибка остановки / Stop failed")

        return kb

    def _create_style(self) -> Style:
        """Создает стиль интерфейса."""
        return Style.from_dict(
            {
                "header": "ansiwhite bg:ansiblue",
                "title": "ansiwhite bg:ansiblue bold",
                "spacecraft": "ansiyellow bg:ansiblue bold",
                "mission_time": "ansigreen bg:ansiblue bold",
                "time": "ansiwhite bg:ansiblue",
                "lang": "ansicyan bg:ansiblue",
                "panel": "ansiwhite bg:ansiblack",
                "panel_title": "ansiwhite bg:ansiblue bold",
                "label": "ansicyan",
                "text-area": "ansiwhite bg:ansiblack",
                "text-area.prompt": "ansigreen bg:ansiblack bold",
            }
        )

    async def run_async(self):
        """Запускает асинхронный интерфейс."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            print("❌ prompt_toolkit not available, falling back to simple mode")
            return self.run_simple_mode()

        try:
            app = Application(
                layout=self._create_layout(),
                key_bindings=self._create_keybindings(),
                style=self._create_style(),
                full_screen=True,
                refresh_interval=1.0,  # Обновление каждую секунду
            )

            await app.run_async()

        except Exception as e:
            self.log("СИСТЕМА / SYSTEM", f"❌ prompt_toolkit error: {e}")
            print(f"❌ prompt_toolkit failed: {e}")
            print("🔄 Falling back to simple terminal mode...")
            return self.run_simple_mode()
        finally:
            self.running = False

    def run_simple_mode(self):
        """Запускает простой режим без prompt_toolkit."""
        print("🚀 Running in Simple Terminal Mode")
        print("   This fallback mode works without prompt_toolkit")
        print("   Type 'exit' to quit, 'help' for commands")

        try:
            while self.running:
                # Показать основную информацию
                hull = self.ship_core.get_hull_status()
                power = self.ship_core.get_power_status()
                mission_time = self._get_mission_time()

                print(f"\\n🛰️ {self.ship_core.get_id()} | {mission_time}")
                print(
                    f"🛡️ Hull: {hull.integrity:.1f}% | ⚡ Power: {power.reactor_output_mw:.1f}MW"
                )
                print(
                    f"🎯 Mission: {self.mission_data['progress']:.1f}% | 📡 Distance: {self.live_telemetry.get('anomaly_distance', 32.17):.2f}km"
                )

                # Ввод команды
                try:
                    command = input("\\n🚀 COMMAND> ").strip()
                    if command.lower() in ["exit", "quit"]:
                        break
                    elif command.lower() == "help":
                        print("Commands: exit, lang, status, autopilot, thrust <0-100>")
                    elif command.lower() == "lang":
                        self.language = "EN" if self.language == "RU" else "RU"
                        print(
                            f"Language: {'English' if self.language == 'EN' else 'Русский'}"
                        )
                    elif command.lower() == "status":
                        print(
                            f"Ship State: {self.logic_controller.current_state.value}"
                        )
                    else:
                        print(f"Command received: {command}")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    break

        except Exception as e:
            print(f"❌ Simple mode error: {e}")
        finally:
            self.running = False
            print("\\n👨‍🚀 QIKI Mission Control Ultimate terminated.")

    def run(self):
        """Запускает Mission Control Ultimate."""
        print("🚀 Запуск QIKI Mission Control Ultimate...")
        print(
            "   F1=Автопилот/Autopilot | F2=Аварийная остановка/Emergency | F12=Язык/Language"
        )
        print("   Ctrl+C для выхода / Ctrl+C to exit")
        print()

        if PROMPT_TOOLKIT_AVAILABLE:
            print("✅ Using advanced prompt_toolkit interface")
        else:
            print("⚠️ Using simple fallback interface")

        try:
            if PROMPT_TOOLKIT_AVAILABLE:
                asyncio.run(self.run_async())
            else:
                self.run_simple_mode()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            print("\\n👨‍🚀 QIKI Mission Control Ultimate завершен / terminated")


# Точка входа
if __name__ == "__main__":
    try:
        terminal = QIKIMissionControlUltimate()
        terminal.run()
    except Exception as e:
        print(f"❌ Ошибка запуска / Startup failed: {e}")
        import traceback

        traceback.print_exc()
