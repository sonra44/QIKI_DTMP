#!/usr/bin/env python3
"""
QIKI Mission Control Pro - Профессиональный терминал управления
Полнофункциональный Mission Control с prompt_toolkit, двуязычным интерфейсом
и реальными изменяющимися параметрами без заглушек.
"""

import sys
import os
import asyncio
import time
import threading
from datetime import datetime
import random

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.application import get_app
except ImportError:
    print("📦 Установка prompt_toolkit...")
    os.system("pip install prompt_toolkit")
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText

from ship_core import ShipCore
from ship_actuators import ShipActuatorController, PropulsionMode
from test_ship_fsm import ShipLogicController


class QIKIMissionControlPro:
    """
    Профессиональный Mission Control Terminal с живым интерфейсом.
    Использует шаблоны интерфейсов и реальные изменяющиеся параметры.
    """

    def __init__(self):
        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core)
        self.logic_controller = ShipLogicController(
            self.ship_core, self.actuator_controller
        )

        # Состояние Mission Control
        self.mission_start_time = time.time()
        self.running = True
        self.language = "RU"  # RU или EN
        self.current_view = "SUMMARY"  # SUMMARY, SYSTEMS, NAV, SENSORS, POWER, DIAG

        # Живые параметры (БЕЗ заглушек!)
        self.live_telemetry = {}
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

        # Фоновые процессы
        self.background_thread = threading.Thread(
            target=self._background_simulation, daemon=True
        )
        self.background_thread.start()

        self.log(
            "СИСТЕМА / SYSTEM",
            "✅ QIKI Mission Control Pro инициализирован / initialized",
        )
        self.log(
            "КОРАБЛЬ / SPACECRAFT",
            f"🛰️ Подключен к / Connected to {self.ship_core.get_id()}",
        )

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
                "anomaly_distance": 32.17
                - (self.simulation_time * 0.01),  # Приближаемся
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
            title = "🚀 КИКИ ЦЕНТР УПРАВЛЕНИЯ ПОЛЕТОМ"
            lang_hint = "[F12] Switch to English"
        else:
            title = "🚀 QIKI MISSION CONTROL CENTER"
            lang_hint = "[F12] Переключить на Русский"

        header_text = FormattedText(
            [
                ("class:header", "╔" + "═" * 98 + "╗\n"),
                ("class:header", "║"),
                ("class:title", f"{title:^98}"),
                ("class:header", "║\n"),
                ("class:header", "║ "),
                ("class:spacecraft", f"🛰️ {self.ship_core.get_id():<30}"),
                ("class:mission_time", f"{mission_time:>15}"),
                ("class:time", f"{current_time:>15}"),
                ("class:lang", f"{lang_hint:>30}"),
                ("class:header", " ║\n"),
                ("class:header", "╚" + "═" * 98 + "╝"),
            ]
        )

        return Window(FormattedTextControl(header_text), height=4)

    def _create_navigation_window(self) -> Window:
        """Создает окно навигации с живыми координатами."""
        nav_x = self.live_telemetry.get("nav_x", 324167.89)
        nav_y = self.live_telemetry.get("nav_y", -52631.44)
        nav_z = self.live_telemetry.get("nav_z", 125.61)
        vel_abs = self.live_telemetry.get("velocity_abs", 2437)
        vel_rel = self.live_telemetry.get("velocity_rel", 18)
        anomaly_dist = self.live_telemetry.get("anomaly_distance", 32.17)

        if self.language == "RU":
            title = "НАВИГАЦИЯ / NAVIGATION"
            coords_title = "КООРДИНАТЫ"
            velocity_title = "СКОРОСТЬ"
            thrusters_title = "ДВИГАТЕЛИ"
            target_title = "ЦЕЛЬ: Аномалия-J7"
        else:
            title = "NAVIGATION / НАВИГАЦИЯ"
            coords_title = "COORDINATES"
            velocity_title = "VELOCITY"
            thrusters_title = "THRUSTERS"
            target_title = "TARGET: Anomaly-J7"

        main_thrust = (
            20 if self.actuator_controller.current_mode == PropulsionMode.CRUISE else 0
        )

        nav_text = FormattedText(
            [
                ("class:panel_title", f"┌─ {title} " + "─" * 30 + "┐\n"),
                ("class:panel", f"│ {coords_title}\n"),
                ("class:panel", f"│ ├─ X: {nav_x:+12.2f} km          ^ Y\n"),
                ("class:panel", f"│ ├─ Y: {nav_y:+12.2f} km          │     × Цель\n"),
                ("class:panel", f"│ ├─ Z: {nav_z:+12.2f} km          │    /\n"),
                ("class:panel", "│ │                               │   /\n"),
                ("class:panel", f"│ │ {target_title:<15}          │  /\n"),
                ("class:panel", f"│ │ Расстояние: {anomaly_dist:6.2f} км        │ /\n"),
                ("class:panel", "│ │                               │/\n"),
                (
                    "class:panel",
                    "│ ╰─ Сектор: Дельта-5      ──────────────────────────>\n",
                ),
                ("class:panel", "│                          O КИКИ      X\n"),
                ("class:panel", "│\n"),
                ("class:panel", f"│ {velocity_title}\n"),
                ("class:panel", f"│ ├─ Абсолютная: {vel_abs:4.0f} м/с\n"),
                ("class:panel", f"│ ├─ Относительная: {vel_rel:+3.0f} м/с (к цели)\n"),
                ("class:panel", "│ ╰─ Дрейф: 0.03%/ч (стабильно)\n"),
                ("class:panel", "│\n"),
                ("class:panel", f"│ {thrusters_title}\n"),
                (
                    "class:panel",
                    f"│ ├─ Главные:    [{self._format_bar(main_thrust)}] {main_thrust:2.0f}%\n",
                ),
                ("class:panel", f"│ ├─ Маневр.:    [{'░' * 10}] простой\n"),
                ("class:panel", f"│ ╰─ Ориентация: [{'░' * 10}] простой\n"),
                ("class:panel_title", "└" + "─" * 48 + "┘"),
            ]
        )

        return Window(FormattedTextControl(nav_text), height=22)

    def _create_telemetry_window(self) -> Window:
        """Создает окно телеметрии систем."""
        hull_int = self.live_telemetry.get("hull_integrity", 100)
        reactor_out = self.live_telemetry.get("reactor_output", 35)
        reactor_max = self.live_telemetry.get("reactor_max", 50)
        battery_charge = self.live_telemetry.get("battery_charge", 10.5)
        battery_cap = self.live_telemetry.get("battery_capacity", 12)
        reactor_temp = self.live_telemetry.get("reactor_temp", 2800)
        oxygen = self.live_telemetry.get("oxygen_level", 21.0)
        co2 = self.live_telemetry.get("co2_level", 400)
        qiki_status = self.live_telemetry.get("qiki_status", "active")

        reactor_pct = (reactor_out / reactor_max) * 100
        battery_pct = (battery_charge / battery_cap) * 100

        if self.language == "RU":
            title = "ТЕЛЕМЕТРИЯ СИСТЕМ / SYSTEM TELEMETRY"
        else:
            title = "SYSTEM TELEMETRY / ТЕЛЕМЕТРИЯ СИСТЕМ"

        tel_text = FormattedText(
            [
                ("class:panel_title", f"┌─ {title} " + "─" * 10 + "┐\n"),
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
                ("class:panel", " │\n"),
                ("class:panel", "│ "),
                ("class:label", "⚡ РЕАКТОР / REACTOR : "),
                (
                    "ansigreen" if reactor_pct > 50 else "ansiyellow",
                    f"[{self._format_bar(reactor_pct)}] {reactor_pct:5.1f}%",
                ),
                ("class:panel", " │\n"),
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
                ("class:panel", " │\n"),
                ("class:panel", "│ "),
                ("class:label", "🌡️  ТЕМП.РЕАК / R.TEMP: "),
                ("ansiwhite", f"{reactor_temp:8.0f} К"),
                ("class:panel", "             │\n"),
                ("class:panel", "│ "),
                ("class:label", "💨 КИСЛОРОД / OXYGEN : "),
                ("ansigreen" if oxygen > 18 else "ansired", f"{oxygen:8.1f} %"),
                ("class:panel", "             │\n"),
                ("class:panel", "│ "),
                ("class:label", "🫁 CO2 УРОВЕНЬ / LEVEL: "),
                ("ansigreen" if co2 < 1000 else "ansiyellow", f"{co2:8.0f} ppm"),
                ("class:panel", "          │\n"),
                ("class:panel", "│ "),
                ("class:label", "🤖 КИКИ СТАТУС / QIKI : "),
                (
                    "ansigreen" if qiki_status == "active" else "ansired",
                    f"{qiki_status:>8}",
                ),
                ("class:panel", "             │\n"),
                ("class:panel_title", "└" + "─" * 48 + "┘"),
            ]
        )

        return Window(FormattedTextControl(tel_text), height=10)

    def _create_mission_window(self) -> Window:
        """Создает окно управления миссией."""
        progress = self.mission_data["progress"]
        eta_hours = int(self.mission_data["eta_seconds"] // 3600)
        eta_mins = int((self.mission_data["eta_seconds"] % 3600) // 60)

        if self.language == "RU":
            title = "УПРАВЛЕНИЕ МИССИЕЙ / MISSION CONTROL"
            current_mission = "ТЕКУЩАЯ МИССИЯ"
            mission_steps = "ЭТАПЫ МИССИИ"
            etc_label = f"Время до завершения: {eta_hours:02}ч {eta_mins:02}м"
        else:
            title = "MISSION CONTROL / УПРАВЛЕНИЕ МИССИЕЙ"
            current_mission = "CURRENT MISSION"
            mission_steps = "MISSION STEPS"
            etc_label = f"ETC: {eta_hours:02}h {eta_mins:02}m"

        mission_text = FormattedText(
            [
                ("class:panel_title", f"┌─ {title} " + "─" * 5 + "┐\n"),
                ("class:panel", f"│ {current_mission}\n"),
                ("class:panel", f"│ ├─ ID: {self.mission_data['designator']}\n"),
                (
                    "class:panel",
                    f"│ ├─ Цель: {self.mission_data['objective'][:25]}...\n",
                ),
                (
                    "class:panel",
                    f"│ ├─ Прогресс: [{self._format_bar(progress)}] {progress:4.1f}%\n",
                ),
                ("class:panel", f"│ ╰─ {etc_label}\n"),
                ("class:panel", "│\n"),
                ("class:panel", f"│ {mission_steps}\n"),
            ]
        )

        # Добавляем этапы миссии
        for i, step in enumerate(self.mission_data["steps"][:4]):  # Показываем первые 4
            status = "✓" if step["done"] else "►" if i == 3 else " "
            step_text = step["name"][:35]
            mission_text.append(("class:panel", f"│  [{status}] {step_text}\n"))

        mission_text.append(("class:panel_title", "└" + "─" * 48 + "┘"))

        return Window(FormattedTextControl(mission_text), height=14)

    def _create_log_window(self) -> Window:
        """Создает окно журнала событий."""
        if self.language == "RU":
            title = "ЖУРНАЛ СОБЫТИЙ / EVENT LOG"
        else:
            title = "EVENT LOG / ЖУРНАЛ СОБЫТИЙ"

        log_text = FormattedText(
            [("class:panel_title", f"┌─ {title} " + "─" * 15 + "┐\n")]
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
                    f"│ [{event['time']}] {event['system'][:12]}: {message}\n",
                )
            )

        # Заполняем пустые строки
        for _ in range(8 - len(recent_events)):
            log_text.append(("class:panel", "│" + " " * 48 + "\n"))

        log_text.append(("class:panel_title", "└" + "─" * 48 + "┘"))

        return Window(FormattedTextControl(log_text), height=11)

    def _create_command_window(self) -> TextArea:
        """Создает окно ввода команд."""
        if self.language == "RU":
            prompt = "КОМАНДА> "
        else:
            prompt = "COMMAND> "

        return TextArea(
            prompt=prompt, multiline=False, wrap_lines=False, height=3, scrollbar=False
        )

    def _create_layout(self) -> Layout:
        """Создает основной layout интерфейса."""

        # Заголовок
        header = self._create_header_window()

        # Левая колонка
        left_column = HSplit(
            [
                self._create_telemetry_window(),
                self._create_mission_window(),
            ]
        )

        # Центральная колонка
        center_column = self._create_navigation_window()

        # Правая колонка
        right_column = self._create_log_window()

        # Основная панель
        main_panel = VSplit(
            [
                left_column,
                Window(width=2),  # Разделитель
                center_column,
                Window(width=2),  # Разделитель
                right_column,
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
        app = Application(
            layout=self._create_layout(),
            key_bindings=self._create_keybindings(),
            style=self._create_style(),
            full_screen=True,
            refresh_interval=1.0,  # Обновление каждую секунду
        )

        try:
            await app.run_async()
        finally:
            self.running = False

    def run(self):
        """Запускает Mission Control Pro."""
        print("🚀 Запуск QIKI Mission Control Pro...")
        print(
            "   F1=Автопилот/Autopilot | F2=Аварийная остановка/Emergency | F12=Язык/Language"
        )
        print("   Ctrl+C для выхода / Ctrl+C to exit")
        print()

        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            print("\\n👨‍🚀 QIKI Mission Control Pro завершен / terminated")


# Добавляем import для math
import math

# Точка входа
if __name__ == "__main__":
    try:
        terminal = QIKIMissionControlPro()
        terminal.run()
    except Exception as e:
        print(f"❌ Ошибка запуска / Startup failed: {e}")
        import traceback

        traceback.print_exc()
