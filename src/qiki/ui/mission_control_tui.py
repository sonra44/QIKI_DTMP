#!/usr/bin/env python3
# ruff: noqa
"""
QIKI Mission Control TUI
Modern terminal interface for spacecraft telemetry and control
Built with Textual framework
"""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import Dict, Any, Optional, List
import os
import sys

# Add project paths for direct execution.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if not __package__:
    # Running as a script; ensure `import qiki` works.
    for path in (SRC_ROOT, REPO_ROOT):
        if path not in sys.path:
            sys.path.insert(0, path)

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Input, Log, TabbedContent, TabPane
from textual.reactive import reactive
from textual.timer import Timer
from textual import events
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table
from rich.align import Align

# Import QIKI components
try:
    from qiki.services.q_core_agent.core.ship_core import ShipCore
    from qiki.services.q_core_agent.core.ship_actuators import ShipActuatorController, ThrusterAxis, PropulsionMode
    from qiki.services.q_core_agent.core.test_ship_fsm import ShipLogicController
except ImportError as e:
    print(f"Failed to import QIKI components: {e}")
    sys.exit(1)


class SystemStatusWidget(Static):
    """System status panel widget"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ship_data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with new ship data"""
        self.ship_data = data
        self.refresh()

    def render(self) -> Panel:
        """Render system status panel"""
        if not self.ship_data:
            return Panel("Loading system data...", title="SYSTEM STATUS | СОСТОЯНИЕ СИСТЕМ")

        # Create status content
        content = []

        # Power status
        power = self.ship_data.get("power", {})
        power_pct = int((power.get("reactor_output_mw", 0) / 25.0) * 100)
        power_bar = self._create_progress_bar(power_pct)
        content.append(f"POWER     │ ПИТАНИЕ      {power_bar}   {power_pct}%")
        content.append(f"          │              {power.get('reactor_output_mw', 0):.1f} MW    NOMINAL")
        content.append("")

        # Hull status
        hull = self.ship_data.get("hull", {})
        hull_pct = int(hull.get("integrity", 0))
        hull_bar = self._create_progress_bar(hull_pct)
        content.append(f"HULL      │ КОРПУС       {hull_bar}   {hull_pct}%")
        content.append(f"          │              INTEGRITY  {'GOOD' if hull_pct > 90 else 'DAMAGED'}")
        content.append("")

        # Life support
        life = self.ship_data.get("life_support", {})
        o2_pct = life.get("oxygen_percent", 21.0)
        life_status = "NORMAL" if 20.0 <= o2_pct <= 22.0 else "WARNING"
        life_bar = self._create_progress_bar(95)  # Usually nominal
        content.append(f"LIFE SUP  │ ЖО           {life_bar}  100%")
        content.append(f"          │              O2: {o2_pct:.1f}%   {life_status}")
        content.append("")

        # Computing
        computing = self.ship_data.get("computing", {})
        comp_temp = computing.get("qiki_temperature_k", 318)
        comp_status = computing.get("qiki_core_status", "ACTIVE")
        comp_bar = self._create_progress_bar(100 if comp_status == "ACTIVE" else 0)
        content.append(f"COMPUTE   │ ВЫЧИСЛЕНИЯ   {comp_bar}  100%")
        content.append(f"          │              {comp_temp:.0f} K      {comp_status}")

        panel_content = "\n".join(content)
        return Panel(panel_content, title="SYSTEM STATUS | СОСТОЯНИЕ СИСТЕМ", border_style="bright_blue")

    def _create_progress_bar(self, percentage: int) -> str:
        """Create ASCII progress bar"""
        filled = int(percentage / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}]"


class NavigationWidget(Static):
    """Navigation and position panel widget"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.nav_data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with navigation data"""
        self.nav_data = data
        self.refresh()

    def render(self) -> Panel:
        """Render navigation panel"""
        if not self.nav_data:
            return Panel("Loading navigation data...", title="NAVIGATION | НАВИГАЦИЯ")

        content = []

        # Position
        pos_x = self.nav_data.get("pos_x", 1250.4)
        pos_y = self.nav_data.get("pos_y", -890.1)
        pos_z = self.nav_data.get("pos_z", 45.2)
        alt = self.nav_data.get("altitude", 45.2)

        content.append("POSITION  │ ПОЗИЦИЯ")
        content.append(f"X: {pos_x:+8.1f} m     │ Y: {pos_y:+8.1f} m")
        content.append(f"Z: {pos_z:+8.1f} m     │ ALT: {alt:+8.1f} m")
        content.append("")

        # Velocity
        vel_x = self.nav_data.get("vel_x", 2.1)
        vel_y = self.nav_data.get("vel_y", -0.5)
        vel_z = self.nav_data.get("vel_z", 0.0)
        vel_total = (vel_x**2 + vel_y**2 + vel_z**2) ** 0.5

        content.append("VELOCITY  │ СКОРОСТЬ")
        content.append(f"ΔX: {vel_x:+5.1f} m/s      │ ΔY: {vel_y:+5.1f} m/s")
        content.append(f"ΔZ: {vel_z:+5.1f} m/s      │ |V|: {vel_total:.2f} m/s")
        content.append("")

        # Attitude
        pitch = self.nav_data.get("pitch", 2.0)
        roll = self.nav_data.get("roll", -1.0)
        yaw = self.nav_data.get("yaw", 45.0)
        heading = self.nav_data.get("heading", 45)

        content.append("ATTITUDE  │ ОРИЕНТАЦИЯ")
        content.append(f"PITCH: {pitch:+5.1f}°      │ ROLL: {roll:+5.1f}°")
        content.append(f"YAW: {yaw:+5.1f}°         │ HDG: {heading:03.0f}°")
        content.append("")

        # Autopilot
        autopilot = self.nav_data.get("autopilot_enabled", False)
        ap_status = "ENABLED" if autopilot else "DISABLED"
        ap_status_ru = "ВКЛЮЧЕН" if autopilot else "ОТКЛЮЧЕН"

        content.append(f"AUTOPILOT │ АВТОПИЛОТ    [{ap_status}]")
        content.append(f"          │              [{ap_status_ru}]")

        panel_content = "\n".join(content)
        return Panel(panel_content, title="NAVIGATION | НАВИГАЦИЯ", border_style="bright_green")


class RadarWidget(Static):
    """Radar contacts and tracking panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.radar_data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with radar data"""
        self.radar_data = data
        self.refresh()

    def render(self) -> Panel:
        """Render radar panel"""
        content = []

        # Mock radar data for demonstration
        tracks: List[Dict[str, Any]] = [
            {"id": "T01", "type": "SHIP", "range": 850, "bearing": 45, "velocity": 2.1, "snr": 24.5, "iff": "FRIEND"},
            {
                "id": "T02",
                "type": "DRONE",
                "range": 1200,
                "bearing": 120,
                "velocity": -1.8,
                "snr": 18.2,
                "iff": "UNKNOWN",
            },
            {
                "id": "T03",
                "type": "DEBRIS",
                "range": 3800,
                "bearing": 280,
                "velocity": 0.0,
                "snr": 12.1,
                "iff": "NEUTRAL",
            },
        ]

        # Table header
        content.append("┌─ TRACK ─┬─ TYPE ─┬─ RANGE ──┬─ BEARING ─┬─ VELOCITY ─┬─ SNR ──┬─ STATUS ─┬─ IFF ───┐")
        content.append("│   ЦЕЛ   │  ТИП   │  ДАЛ-м   │   ПЕЛ-°   │   СКР-м/с  │ СШ-дБ  │  СТАТУС  │  СВО-В  │")
        content.append("├─────────┼────────┼──────────┼───────────┼────────────┼────────┼──────────┼─────────┤")

        # Table data
        type_map = {"SHIP": "КОР", "DRONE": "БЛА", "DEBRIS": "ОСК"}
        iff_map = {"FRIEND": "ДРУГ", "UNKNOWN": "НЕИЗВ", "NEUTRAL": "НЕЙТР"}

        for track in tracks:
            tid = track["id"]
            tid_ru = tid.replace("T", "Ц")
            ttype = track["type"]
            ttype_ru = type_map.get(ttype, ttype)

            content.append(
                f"│   {tid}   │  {ttype:<4}  │   {track['range']:<4}   │    {track['bearing']:03d}    │    {track['velocity']:+4.1f}    │  {track['snr']:4.1f}  │  TRACK   │ {track['iff']:<7} │"
            )
            content.append(
                f"│   {tid_ru}   │  {ttype_ru:<4}  │   {track['range']:<4}   │    {track['bearing']:03d}    │    {track['velocity']:+4.1f}    │  {track['snr']:4.1f}  │  СЛЕЖ    │ {iff_map[track['iff']]:<7} │"
            )
            if track != tracks[-1]:  # Add separator except for last item
                content.append("│         │        │          │           │            │        │          │         │")

        content.append("└─────────┴────────┴──────────┴───────────┴────────────┴────────┴──────────┴─────────┘")
        content.append("")
        content.append("RADAR STATUS  │ СОСТОЯНИЕ РАДАРА")
        content.append(
            "LR: ACTIVE    │ ДД: АКТИВЕН          SR: ACTIVE    │ БД: АКТИВЕН          RANGE: 5.0 km    │    TRACKS: 3/16"
        )

        panel_content = "\n".join(content)
        return Panel(panel_content, title="RADAR CONTACTS | РАДАРНЫЕ ЦЕЛИ", border_style="bright_yellow")


class PropulsionWidget(Static):
    """Propulsion system panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prop_data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with propulsion data"""
        self.prop_data = data
        self.refresh()

    def render(self) -> Panel:
        """Render propulsion panel"""
        content = []

        # Main drive
        thrust_pct = self.prop_data.get("main_drive_thrust_pct", 0)
        thrust_bar = self._create_progress_bar(thrust_pct)
        content.append("MAIN DRIVE   │   ОСНОВНОЙ ДВИГАТЕЛЬ")
        content.append("")
        content.append(f"THRUST       │   ТЯГА        {thrust_bar}  {thrust_pct:.1f}%")
        content.append(
            f"             │               {self.prop_data.get('main_drive_thrust_n', 0):.1f} N      {'ACTIVE' if thrust_pct > 0 else 'IDLE'}"
        )
        content.append("")

        # Fuel
        fuel_kg = self.prop_data.get("main_drive_fuel_kg", 1245)
        fuel_pct = int((fuel_kg / 1400) * 100)  # Assume max 1400kg
        fuel_bar = self._create_progress_bar(fuel_pct)
        content.append(f"FUEL         │   ТОПЛИВО     {fuel_bar}  {fuel_pct}%")
        content.append(f"             │               {fuel_kg:.0f} kg    {'GOOD' if fuel_pct > 50 else 'LOW'}")
        content.append("")

        # Delta-V
        delta_v = self.prop_data.get("delta_v_available", 2450)
        content.append(f"DELTA-V      │   ЗАПАС ΔV    {delta_v:.0f} m/s AVAIL")
        content.append("             │               ДОСТУПНО")
        content.append("")

        # RCS
        rcs_status = self.prop_data.get("rcs_status", {"F": True, "B": True, "P": True, "S": True})
        rcs_indicators = []
        for direction, status in rcs_status.items():
            rcs_indicators.append(f"{direction}: {'●' if status else '○'}")

        content.append("RCS          │   РДО         READY    ГОТОВ")
        content.append(f"             │   {' '.join(rcs_indicators)}")
        content.append("")

        # Mode and last burn
        mode = self.prop_data.get("mode", "MANUAL")
        mode_ru = "РУЧНОЙ" if mode == "MANUAL" else "АВТО"
        content.append(f"MODE         │   РЕЖИМ       {mode}   {mode_ru}")
        content.append("")
        content.append("LAST BURN    │   ПОСЛ. РАБОТА  -02:30s")
        content.append("             │                  1.2s duration")

        panel_content = "\n".join(content)
        return Panel(panel_content, title="PROPULSION | ДВИГАТЕЛЬНАЯ УСТАНОВКА", border_style="bright_cyan")

    def _create_progress_bar(self, percentage: int) -> str:
        """Create ASCII progress bar"""
        filled = int(percentage / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}]"


class PowerWidget(Static):
    """Power distribution panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.power_data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update widget with power data"""
        self.power_data = data
        self.refresh()

    def render(self) -> Panel:
        """Render power panel"""
        content = []

        # Sources
        reactor_mw = self.power_data.get("reactor_output_mw", 22.5)
        battery_mwh = self.power_data.get("battery_charge_mwh", 4.8)

        content.append("SOURCES       │  ИСТОЧНИКИ")
        content.append("")
        content.append(f"REACTOR       │  РЕАКТОР      {reactor_mw:.1f} MW")
        content.append(f"              │               {reactor_mw:.1f} МВт")
        content.append("")
        content.append(f"BATTERY       │  АККУМУЛЯТОР   {battery_mwh:.1f} MWh")
        content.append(f"              │                {battery_mwh:.1f} МВтч")
        content.append("")

        # Consumers
        consumers: List[Dict[str, Any]] = [
            {"name": "MAIN SYSTEMS", "name_ru": "ОСНОВНЫЕ", "power": 15.0, "pct": 67},
            {"name": "SENSORS", "name_ru": "СЕНСОРЫ", "power": 3.5, "pct": 16},
            {"name": "LIFE SUPPORT", "name_ru": "ЖО", "power": 2.0, "pct": 9},
            {"name": "COMPUTING", "name_ru": "ВЫЧИСЛЕНИЯ", "power": 2.0, "pct": 9},
        ]

        content.append("CONSUMERS     │  ПОТРЕБИТЕЛИ")
        content.append("")

        for consumer in consumers:
            bar = self._create_progress_bar(consumer["pct"])
            content.append(
                f"{consumer['name']:<13} │  {consumer['name_ru']:<8}      {consumer['power']:.1f} MW  {consumer['pct']}%"
            )
            content.append(f"              │                 {consumer['power']:.1f} МВт        {bar}")
            content.append("")

        panel_content = "\n".join(content)
        return Panel(panel_content, title="POWER DISTRIBUTION | РАСПРЕДЕЛЕНИЕ ЭНЕРГИИ", border_style="bright_magenta")

    def _create_progress_bar(self, percentage: int) -> str:
        """Create ASCII progress bar with custom length"""
        filled = int(percentage / 12.5)  # 8 chars max
        empty = 8 - filled
        return f"[{'█' * filled}{'░' * empty}]"


class EventLogWidget(Static):
    """System events log panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events: List[Dict[str, Any]] = []

    def add_event(self, level: str, message_en: str, message_ru: str) -> None:
        """Add new event to log"""
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        self.events.append({"time": timestamp, "level": level, "message_en": message_en, "message_ru": message_ru})

        # Keep only last 6 events
        if len(self.events) > 6:
            self.events = self.events[-6:]

        self.refresh()

    def render(self) -> Panel:
        """Render events log panel"""
        if not self.events:
            # Add some initial events for demo
            self.add_event("INFO", "System initialization complete", "Инициализация системы завершена")
            self.add_event("INFO", "All sensors online", "Все сенсоры в сети")
            self.add_event("WARN", "Battery discharge rate elevated", "Повышенная скорость разряда батареи")

        content = []
        for event in self.events[-6:]:  # Show last 6 events
            content.append(
                f"{event['time']}  [{event['level']}]   │  {event['message_en']:<35}  │  {event['message_ru']}"
            )

        # Fill empty lines if needed
        while len(content) < 6:
            content.append("")

        panel_content = "\n".join(content)
        return Panel(panel_content, title="SYSTEM EVENTS | СИСТЕМНЫЕ СОБЫТИЯ", border_style="white")


class CommandInputWidget(Container):
    """Command input panel with status"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_command = ""
        self.last_status = "OK"

    def compose(self) -> ComposeResult:
        """Compose the command input widget"""
        yield Static("COMMAND INPUT | ВВОД КОМАНД", id="cmd_title")
        yield Input(placeholder="Enter command... | Введите команду...", id="cmd_input")
        yield Static(
            f"LAST COMMAND | ПОСЛЕДНЯЯ КОМАНДА:  {self.last_command}        STATUS | СТАТУС:  {self.last_status}",
            id="cmd_status",
        )
        yield Static(
            "HOTKEYS | ГОРЯЧИЕ КЛАВИШИ:    F1-Help  F2-Radar  F3-Systems  F4-Power  ESC-Exit", id="cmd_hotkeys"
        )


class QIKIMissionControlApp(App):
    """Main QIKI Mission Control TUI Application"""

    CSS = """
    Screen {
        background: $surface;
    }
    
    .panel {
        margin: 1;
        padding: 1;
    }
    
    #system_status {
        width: 1fr;
        height: 12;
    }
    
    #navigation {
        width: 1fr; 
        height: 12;
    }
    
    #radar {
        width: 1fr;
        height: 16;
    }
    
    #propulsion {
        width: 1fr;
        height: 20;
    }
    
    #power {
        width: 1fr;
        height: 20;
    }
    
    #events {
        width: 1fr;
        height: 10;
    }
    
    #command {
        width: 1fr;
        height: 6;
        border: solid $primary;
    }
    
    Input {
        margin: 1 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f1", "help", "Help"),
        ("f2", "toggle_radar", "Toggle Radar"),
        ("f3", "toggle_systems", "Toggle Systems"),
        ("f4", "toggle_power", "Toggle Power"),
    ]

    def __init__(self):
        super().__init__()
        self.ship_core: Optional[ShipCore] = None
        self.actuator_controller: Optional[ShipActuatorController] = None
        self.logic_controller: Optional[ShipLogicController] = None
        self.update_timer: Optional[Timer] = None

        # Initialize QIKI components
        self._initialize_qiki_components()

    def _initialize_qiki_components(self):
        """Initialize QIKI ship components"""
        try:
            q_core_agent_root = os.path.abspath(os.path.join(REPO_ROOT, "src", "qiki", "services", "q_core_agent"))
            self.ship_core = ShipCore(base_path=q_core_agent_root)
            self.actuator_controller = ShipActuatorController(self.ship_core)
            self.logic_controller = ShipLogicController(self.ship_core, self.actuator_controller)
        except Exception as e:
            self.notify(f"Failed to initialize QIKI components: {e}", severity="error")

    def compose(self) -> ComposeResult:
        """Compose the main application layout"""
        yield Header(show_clock=True)

        with Horizontal():
            with Vertical():
                yield SystemStatusWidget(classes="panel", id="system_status")
                yield PropulsionWidget(classes="panel", id="propulsion")

            with Vertical():
                yield NavigationWidget(classes="panel", id="navigation")
                yield PowerWidget(classes="panel", id="power")

        yield RadarWidget(classes="panel", id="radar")
        yield EventLogWidget(classes="panel", id="events")
        yield CommandInputWidget(classes="panel", id="command")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = "QIKI Mission Control | QИКИ Центр Управления Полетом"
        self.sub_title = "v2.1 - NASA/Military Command Interface"

        # Start update timer
        self.update_timer = self.set_interval(0.2, self.update_telemetry)

        # Add initial log event
        events_widget = self.query_one("#events", EventLogWidget)
        events_widget.add_event("INFO", "Mission Control interface started", "Интерфейс центра управления запущен")

    def update_telemetry(self) -> None:
        """Update all telemetry data"""
        if not self.ship_core:
            return

        try:
            # Get ship data
            hull_status = self.ship_core.get_hull_status()
            power_status = self.ship_core.get_power_status()
            prop_status = self.ship_core.get_propulsion_status()
            life_status = self.ship_core.get_life_support_status()
            comp_status = self.ship_core.get_computing_status()

            # Prepare data dictionaries
            system_data = {
                "hull": {"integrity": hull_status.integrity, "mass_kg": hull_status.mass_kg},
                "power": {
                    "reactor_output_mw": power_status.reactor_output_mw,
                    "battery_charge_mwh": power_status.battery_charge_mwh,
                },
                "life_support": {"oxygen_percent": life_status.atmosphere.get("oxygen_percent", 21.2)},
                "computing": {
                    "qiki_core_status": comp_status.qiki_core_status,
                    "qiki_temperature_k": comp_status.qiki_temperature_k,
                },
            }

            nav_data = {
                "pos_x": 1250.4,
                "pos_y": -890.1,
                "pos_z": 45.2,
                "vel_x": 2.1,
                "vel_y": -0.5,
                "vel_z": 0.0,
                "pitch": 2.0,
                "roll": -1.0,
                "yaw": 45.0,
                "heading": 45,
                "autopilot_enabled": False,
                "altitude": 45.2,
            }

            prop_data = {
                "main_drive_thrust_pct": 0.0,
                "main_drive_thrust_n": prop_status.main_drive_thrust_n,
                "main_drive_fuel_kg": prop_status.main_drive_fuel_kg,
                "delta_v_available": 2450,
                "rcs_status": {"F": True, "B": True, "P": True, "S": True},
                "mode": "MANUAL",
            }

            power_data = {
                "reactor_output_mw": power_status.reactor_output_mw,
                "battery_charge_mwh": power_status.battery_charge_mwh,
            }

            # Update widgets
            self.query_one("#system_status", SystemStatusWidget).update_data(system_data)
            self.query_one("#navigation", NavigationWidget).update_data(nav_data)
            self.query_one("#propulsion", PropulsionWidget).update_data(prop_data)
            self.query_one("#power", PowerWidget).update_data(power_data)
            self.query_one("#radar", RadarWidget).update_data({})

        except Exception as e:
            events_widget = self.query_one("#events", EventLogWidget)
            events_widget.add_event("ERROR", f"Telemetry update failed: {e}", f"Ошибка обновления телеметрии: {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input"""
        command = event.value.strip()
        if not command:
            return

        # Clear input
        event.input.value = ""

        # Process command
        success = self.process_command(command)
        status = "OK" if success else "ERROR"

        # Update command status
        cmd_widget = self.query_one("#cmd_status", Static)
        cmd_widget.update(f"LAST COMMAND | ПОСЛЕДНЯЯ КОМАНДА:  {command}        STATUS | СТАТУС:  {status}")

        # Add to event log
        events_widget = self.query_one("#events", EventLogWidget)
        events_widget.add_event("CMD", f"Command executed: {command}", f"Команда выполнена: {command}")

    def process_command(self, command: str) -> bool:
        """Process user command"""
        parts = command.split()
        if not parts:
            return False

        cmd = parts[0].lower()

        try:
            if cmd == "thrust" and len(parts) >= 2:
                thrust_pct = float(parts[1])
                if self.actuator_controller:
                    return self.actuator_controller.set_main_drive_thrust(thrust_pct)

            elif cmd == "rcs" and len(parts) >= 3:
                axis_map = {
                    "forward": ThrusterAxis.FORWARD,
                    "backward": ThrusterAxis.BACKWARD,
                    "port": ThrusterAxis.PORT,
                    "starboard": ThrusterAxis.STARBOARD,
                }
                axis = axis_map.get(parts[1].lower())
                if axis and self.actuator_controller:
                    thrust_pct = float(parts[2])
                    return self.actuator_controller.fire_rcs_thruster(axis, thrust_pct, 0.5)

            elif cmd == "stop":
                if self.actuator_controller:
                    return self.actuator_controller.emergency_stop()

            elif cmd in ["help", "?", "h"]:
                self.notify("Commands: thrust <0-100>, rcs <direction> <0-100>, stop", severity="information")
                return True

            return False

        except (ValueError, TypeError):
            return False

    def action_help(self) -> None:
        """Show help dialog"""
        self.notify("F1-Help F2-Radar F3-Systems F4-Power ESC-Exit", severity="information")

    def action_toggle_radar(self) -> None:
        """Toggle radar panel visibility"""
        radar = self.query_one("#radar", RadarWidget)
        radar.visible = not radar.visible

    def action_toggle_systems(self) -> None:
        """Toggle systems panel visibility"""
        system = self.query_one("#system_status", SystemStatusWidget)
        system.visible = not system.visible

    def action_toggle_power(self) -> None:
        """Toggle power panel visibility"""
        power = self.query_one("#power", PowerWidget)
        power.visible = not power.visible


def main():
    """Main entry point"""
    app = QIKIMissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
