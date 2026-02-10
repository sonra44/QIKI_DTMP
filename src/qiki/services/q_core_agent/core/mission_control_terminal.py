#!/usr/bin/env python3
"""Текстовый терминал управления кораблём без зависимостей prompt_toolkit."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if not __package__:
    # Allow direct execution while keeping normal package imports clean.
    repo_root = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "..", "..", ".."))
    src_root = os.path.join(repo_root, "src")
    for path in (src_root, repo_root):
        if path not in sys.path:
            sys.path.append(path)

from qiki.services.q_core_agent.core.ship_core import ShipCore  # noqa: E402
from qiki.services.q_core_agent.core.ship_actuators import (  # noqa: E402
    ShipActuatorController,
    ThrusterAxis,
    PropulsionMode,
)
from qiki.services.q_core_agent.core.event_store import EventStore  # noqa: E402
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline  # noqa: E402
from qiki.services.q_core_agent.core.terminal_radar_renderer import (  # noqa: E402
    load_events_jsonl,
    render_terminal_screen,
)
from qiki.services.q_core_agent.core.test_ship_fsm import ShipLogicController  # noqa: E402


class MissionControlTerminal:
    """Простая консольная реализация Mission Control."""

    def __init__(self, variant_name: str = "Mission Control Terminal"):
        self.variant_name = variant_name
        q_core_agent_root = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
        self.event_store = EventStore.from_env()
        self.radar_pipeline: RadarPipeline | None = None
        self.radar_pipeline_error = ""
        try:
            self.radar_pipeline = RadarPipeline()
        except RuntimeError as exc:
            self.radar_pipeline_error = str(exc)
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core, event_store=self.event_store)
        self.logic_controller = ShipLogicController(self.ship_core, self.actuator_controller)
        self.autopilot_enabled = False
        self.running = True
        self.last_cycle: Optional[Dict[str, str]] = None

    def run(self) -> None:
        """Запускает основной цикл терминала."""

        print(f"{self.variant_name} готов. Команда 'help' покажет список команд.")
        try:
            while self.running:
                if self.autopilot_enabled:
                    self.last_cycle = self.logic_controller.process_logic_cycle()
                    time.sleep(0.2)
                self.render()
                command = input("command> ").strip()
                if not command:
                    continue
                if not self.handle_command(command):
                    break
        except KeyboardInterrupt:
            print("\nСессия прервана пользователем.")

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Возвращает снимок ключевых систем корабля."""

        snapshot: Dict[str, Dict[str, float]] = {
            "identity": {},
            "hull": {},
            "power": {},
            "propulsion": {},
            "life_support": {},
            "computing": {},
        }

        snapshot["identity"] = {
            "ship_id": self.ship_core.get_id(),
            "ship_class": self.ship_core.get_ship_class(),
        }

        try:
            hull = self.ship_core.get_hull_status()
            snapshot["hull"] = {
                "integrity": hull.integrity,
                "mass_kg": hull.mass_kg,
            }
        except Exception as exc:  # noqa: BLE001
            snapshot["hull"] = {"error": str(exc)}

        try:
            power = self.ship_core.get_power_status()
            snapshot["power"] = {
                "reactor_output_mw": power.reactor_output_mw,
                "battery_charge_mwh": power.battery_charge_mwh,
            }
        except Exception as exc:  # noqa: BLE001
            snapshot["power"] = {"error": str(exc)}

        try:
            propulsion = self.ship_core.get_propulsion_status()
            snapshot["propulsion"] = {
                "main_drive_status": propulsion.main_drive_status,
                "main_drive_fuel_kg": propulsion.main_drive_fuel_kg,
            }
        except Exception as exc:  # noqa: BLE001
            snapshot["propulsion"] = {"error": str(exc)}

        try:
            life_support = self.ship_core.get_life_support_status()
            snapshot["life_support"] = {
                "oxygen_percent": life_support.atmosphere.get("oxygen_percent", 0.0),
                "co2_ppm": life_support.atmosphere.get("co2_ppm", 0.0),
            }
        except Exception as exc:  # noqa: BLE001
            snapshot["life_support"] = {"error": str(exc)}

        try:
            computing = self.ship_core.get_computing_status()
            snapshot["computing"] = {
                "status": computing.qiki_core_status,
                "temperature_k": computing.qiki_temperature_k,
            }
        except Exception as exc:  # noqa: BLE001
            snapshot["computing"] = {"error": str(exc)}

        return snapshot

    def render(self) -> None:
        """Выводит текущую телеметрию."""

        snapshot = self.snapshot()
        print()
        print(f"=== {self.variant_name} ===")
        identity = snapshot["identity"]
        ship_id = identity.get("ship_id")
        ship_class = identity.get("ship_class")
        print(f"Корабль: {ship_id} | Класс: {ship_class}")
        print(f"Автопилот: {'ON' if self.autopilot_enabled else 'OFF'}")

        if self.last_cycle:
            state = self.last_cycle.get("current_state", "unknown")
            trigger = self.last_cycle.get("trigger_event", "-")
            mode = self.last_cycle.get("propulsion_mode", PropulsionMode.IDLE.value)
            print(f"Состояние: {state} | Драйв: {mode} | Триггер: {trigger}")

        hull = snapshot["hull"]
        print(f"Корпус: {hull.get('integrity', 'n/a')}% | Масса: {hull.get('mass_kg', 'n/a')} кг")

        power = snapshot["power"]
        print(
            "Энергия: "
            f"реактор {power.get('reactor_output_mw', 'n/a')} МВт | "
            f"аккум {power.get('battery_charge_mwh', 'n/a')} МВт·ч"
        )

        propulsion = snapshot["propulsion"]
        print(
            "Двигатель: "
            f"статус {propulsion.get('main_drive_status', 'n/a')} | "
            f"топливо {propulsion.get('main_drive_fuel_kg', 'n/a')} кг"
        )

        life_support = snapshot["life_support"]
        print(f"ЖО: O₂ {life_support.get('oxygen_percent', 'n/a')}% | CO₂ {life_support.get('co2_ppm', 'n/a')} ppm")

        computing = snapshot["computing"]
        print(f"Вычисления: статус {computing.get('status', 'n/a')} | t={computing.get('temperature_k', 'n/a')} К")

    def render_event_hud(self) -> None:
        """Render EventStore-driven radar/HUD/log screen."""
        events = self.event_store.recent(300)
        if self.radar_pipeline is None:
            print(f"Radar backend configuration error: {self.radar_pipeline_error or 'unknown'}")
            return
        try:
            print(render_terminal_screen(events, pipeline=self.radar_pipeline))
        except RuntimeError as exc:
            print(f"Radar backend configuration error: {exc}")

    @staticmethod
    def replay_events(jsonl_path: str) -> int:
        """Render HUD from exported EventStore JSONL trace."""
        path = Path(jsonl_path)
        if not path.exists():
            print(f"Replay trace not found: {path}")
            return 2
        events = load_events_jsonl(str(path))
        try:
            print(render_terminal_screen(events, pipeline=RadarPipeline()))
        except RuntimeError as exc:
            print(f"Radar backend configuration error: {exc}")
            return 2
        return 0

    def handle_command(self, raw_command: str) -> bool:
        """Обрабатывает пользовательскую команду."""

        parts = raw_command.split()
        if not parts:
            return True

        cmd = parts[0].lower()
        if cmd in {"exit", "quit"}:
            self.running = False
            print("Завершение работы терминала.")
            return False

        if cmd == "help":
            self.print_help()
            return True

        if cmd == "status":
            self.last_cycle = self.logic_controller.process_logic_cycle()
            return True

        if cmd == "hud":
            self.render_event_hud()
            return True

        if cmd == "autopilot" and len(parts) == 2:
            return self._handle_autopilot(parts[1].lower())

        if cmd == "thrust" and len(parts) >= 2:
            return self._handle_thrust(parts[1])

        if cmd == "rcs" and len(parts) >= 3:
            return self._handle_rcs(parts[1], parts[2])

        if cmd == "stop":
            self._handle_stop()
            return True

        print("Неизвестная команда. Используйте 'help'.")
        return True

    def print_help(self) -> None:
        """Выводит информацию по доступным командам."""

        print("Доступные команды:")
        print("  help                 — список команд")
        print("  status               — выполнить цикл логики и обновить статус")
        print("  hud                  — рендер Radar/HUD/EventLog из EventStore")
        print("  autopilot on|off     — включить или отключить автопилот")
        print("  thrust <0-100>       — установить тягу основного двигателя")
        rcs_help = "  rcs <axis> <0-100>   — импульс РДО (axis: forward/back/port/starboard)"
        print(rcs_help)
        print("  stop                 — аварийная остановка")
        print("  exit|quit            — завершить работу")

    def _handle_autopilot(self, value: str) -> bool:
        if value not in {"on", "off"}:
            print("Используйте 'autopilot on' или 'autopilot off'.")
            return True

        self.autopilot_enabled = value == "on"
        print(f"Автопилот {'включён' if self.autopilot_enabled else 'выключен'}.")
        return True

    def _handle_thrust(self, value: str) -> bool:
        try:
            percent = float(value)
        except ValueError:
            print("Неверное значение тяги. Пример: thrust 25")
            return True

        if self.actuator_controller.set_main_drive_thrust(percent):
            print(f"Тяга установлена на {percent:.1f}%.")
        else:
            print("Не удалось изменить тягу.")
        return True

    def _handle_rcs(self, axis_name: str, value: str) -> bool:
        axis_map = {
            "forward": ThrusterAxis.FORWARD,
            "back": ThrusterAxis.BACKWARD,
            "backward": ThrusterAxis.BACKWARD,
            "port": ThrusterAxis.PORT,
            "starboard": ThrusterAxis.STARBOARD,
        }

        axis = axis_map.get(axis_name.lower())
        if axis is None:
            print("Неизвестная ось. Допустимые: forward, back, port, starboard.")
            return True

        try:
            percent = float(value)
        except ValueError:
            print("Неверное значение тяги РДО. Пример: rcs port 15")
            return True

        if self.actuator_controller.fire_rcs_thruster(axis, percent, 0.5):
            print(f"Импульс РДО {axis.value} на {percent:.1f}% выполнен.")
        else:
            print("Не удалось выполнить команду РДО.")
        return True

    def _handle_stop(self) -> None:
        if self.actuator_controller.emergency_stop():
            print("Аварийная остановка выполнена успешно.")
        else:
            print("Аварийная остановка завершилась ошибкой.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mission Control Terminal (ASCII radar/HUD)")
    parser.add_argument(
        "--replay",
        metavar="JSONL",
        help="Render one truthful radar/HUD screen from EventStore JSONL trace.",
    )
    args = parser.parse_args()
    if args.replay:
        raise SystemExit(MissionControlTerminal.replay_events(args.replay))
    terminal = MissionControlTerminal()
    terminal.run()


if __name__ == "__main__":
    main()
