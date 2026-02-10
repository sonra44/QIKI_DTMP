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
from qiki.services.q_core_agent.core.radar_pipeline import (  # noqa: E402
    RadarPipeline,
    RadarRenderConfig,
)
from qiki.services.q_core_agent.core.radar_controls import (  # noqa: E402
    RadarInputController,
    RadarMouseEvent,
)
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState  # noqa: E402
from qiki.services.q_core_agent.core.terminal_radar_renderer import (  # noqa: E402
    build_scene_from_events,
    load_events_jsonl,
    render_terminal_screen,
)
from qiki.services.q_core_agent.core.terminal_input_backend import (  # noqa: E402
    InputEvent,
    TerminalInputBackend,
    select_input_backend,
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
        self.radar_input = RadarInputController()
        self.view_state = RadarViewState.from_env()
        try:
            self.radar_pipeline = RadarPipeline()
            self.view_state = self.radar_pipeline.view_state
        except RuntimeError as exc:
            self.radar_pipeline_error = str(exc)
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core, event_store=self.event_store)
        self.logic_controller = ShipLogicController(self.ship_core, self.actuator_controller)
        self.autopilot_enabled = False
        self.running = True
        self.last_cycle: Optional[Dict[str, str]] = None

    def run(self, *, real_input: bool = False) -> None:
        """Запускает основной цикл терминала."""

        print(f"{self.variant_name} готов. Команда 'help' покажет список команд.")
        if real_input:
            status = self.live_radar_loop(prefer_real=True)
            if status == 0:
                return
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

    def configure_radar_pipeline(self, *, renderer: str | None = None, fps: int | None = None) -> None:
        """Apply renderer/fps overrides for live/replay loops."""

        base = RadarRenderConfig.from_env()
        effective_renderer = (renderer or base.renderer).strip().lower()
        if not effective_renderer:
            effective_renderer = "auto"
        effective_fps = base.fps_max
        if fps is not None:
            effective_fps = max(1, int(fps))
        try:
            self.radar_pipeline = RadarPipeline(
                RadarRenderConfig(
                    renderer=effective_renderer,
                    view=base.view,
                    fps_max=effective_fps,
                    color=base.color,
                )
            )
            self.radar_pipeline_error = ""
            self.view_state = self.radar_pipeline.view_state
        except RuntimeError as exc:
            self.radar_pipeline = None
            self.radar_pipeline_error = str(exc)

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
            print(render_terminal_screen(events, pipeline=self.radar_pipeline, view_state=self.view_state))
        except RuntimeError as exc:
            print(f"Radar backend configuration error: {exc}")

    @staticmethod
    def replay_events(
        jsonl_path: str,
        *,
        interactive: bool = False,
        real_input: bool = False,
        renderer: str | None = None,
        fps: int | None = None,
    ) -> int:
        """Render HUD from exported EventStore JSONL trace."""
        path = Path(jsonl_path)
        if not path.exists():
            print(f"Replay trace not found: {path}")
            return 2
        events = load_events_jsonl(str(path))
        try:
            pipeline = MissionControlTerminal._build_pipeline(renderer=renderer, fps=fps)
        except RuntimeError as exc:
            print(f"Radar backend configuration error: {exc}")
            return 2
        if interactive or real_input:
            return MissionControlTerminal._replay_interactive(events, pipeline, real_input=real_input)
        try:
            print(render_terminal_screen(events, pipeline=pipeline, view_state=pipeline.view_state))
        except RuntimeError as exc:
            print(f"Radar backend configuration error: {exc}")
            return 2
        return 0

    @staticmethod
    def _build_pipeline(*, renderer: str | None = None, fps: int | None = None) -> RadarPipeline:
        base = RadarRenderConfig.from_env()
        effective_renderer = (renderer or base.renderer).strip().lower()
        if not effective_renderer:
            effective_renderer = "auto"
        effective_fps = base.fps_max if fps is None else max(1, int(fps))
        return RadarPipeline(
            RadarRenderConfig(
                renderer=effective_renderer,
                view=base.view,
                fps_max=effective_fps,
                color=base.color,
            )
        )

    @staticmethod
    def _replay_interactive(
        events: list[dict[str, object]],
        pipeline: RadarPipeline,
        *,
        real_input: bool = False,
    ) -> int:
        controller = RadarInputController()
        view_state = pipeline.view_state
        backend, warning = select_input_backend(prefer_real=real_input)
        if warning:
            print(f"[WARN] {warning}")
        print(
            "Replay controls: 1/2/3/4 view, r reset, o overlays, c color, +/- zoom, q quit."
            " Mouse: wheel/click/drag in real-input mode."
        )
        print("Line mode emulation: 'wheel up|down', 'click <x> <y>', 'drag <dx> <dy>'")

        frame_interval = 1.0 / max(1, pipeline.config.fps_max)
        last_render_ts = 0.0
        needs_render = True
        try:
            while True:
                now = time.monotonic()
                timeout = max(1, int(max(0.0, frame_interval - (now - last_render_ts)) * 1000.0))
                input_events = backend.poll_events(timeout_ms=timeout)
                scene = build_scene_from_events(events)
                should_quit = False
                for event in input_events:
                    view_state, should_quit = MissionControlTerminal._apply_input_event(
                        controller=controller,
                        view_state=view_state,
                        event=event,
                        scene=scene,
                    )
                    if should_quit:
                        break
                    needs_render = True
                if should_quit:
                    return 0
                if needs_render and (time.monotonic() - last_render_ts) >= frame_interval:
                    if backend.name == "real-terminal":
                        print("\x1b[2J\x1b[H", end="")
                    print(render_terminal_screen(events, pipeline=pipeline, view_state=view_state))
                    last_render_ts = time.monotonic()
                    needs_render = False
        finally:
            backend.close()

    @staticmethod
    def _apply_input_event(
        *,
        controller: RadarInputController,
        view_state: RadarViewState,
        event: InputEvent,
        scene,
    ) -> tuple[RadarViewState, bool]:
        if event.kind == "key":
            if event.key in {"q", "quit", "exit"}:
                return view_state, True
            return controller.apply_key(view_state, event.key, scene=scene), False
        if event.kind == "wheel":
            action = controller.handle_mouse(RadarMouseEvent(kind="wheel", delta=event.delta))
            return controller.apply_action(view_state, action), False
        if event.kind == "click":
            action = controller.handle_mouse(RadarMouseEvent(kind="click", x=event.x, y=event.y, button="left"))
            return controller.apply_action(view_state, action, scene=scene), False
        if event.kind == "drag":
            action = controller.handle_mouse(
                RadarMouseEvent(kind="drag", button="left", is_button_down=True, dx=event.dx, dy=event.dy)
            )
            return controller.apply_action(view_state, action), False
        if event.kind == "line":
            raw = event.raw
            if raw in {"q", "quit", "exit"}:
                return view_state, True
            if raw.startswith("wheel "):
                direction = raw.split(" ", 1)[1].strip()
                delta = 1.0 if direction == "up" else -1.0 if direction == "down" else 0.0
                action = controller.handle_mouse(RadarMouseEvent(kind="wheel", delta=delta))
                return controller.apply_action(view_state, action), False
            if raw.startswith("click "):
                parts = raw.split()
                if len(parts) == 3:
                    try:
                        x = float(parts[1])
                        y = float(parts[2])
                    except ValueError:
                        return view_state, False
                    action = controller.handle_mouse(RadarMouseEvent(kind="click", x=x, y=y, button="left"))
                    return controller.apply_action(view_state, action, scene=scene), False
                return view_state, False
            if raw.startswith("drag "):
                parts = raw.split()
                if len(parts) == 3:
                    try:
                        dx = float(parts[1])
                        dy = float(parts[2])
                    except ValueError:
                        return view_state, False
                    action = controller.handle_mouse(
                        RadarMouseEvent(kind="drag", button="left", is_button_down=True, dx=dx, dy=dy)
                    )
                    return controller.apply_action(view_state, action), False
            return controller.apply_key(view_state, raw, scene=scene), False
        return view_state, False

    def live_radar_loop(
        self,
        *,
        prefer_real: bool,
        heartbeat_s: float = 1.0,
        max_iterations: int | None = None,
        backend_override: TerminalInputBackend | None = None,
    ) -> int:
        """Live cockpit loop driven by EventStore + input events."""

        if self.radar_pipeline is None:
            print(f"Radar backend configuration error: {self.radar_pipeline_error or 'unknown'}")
            return 2

        backend = backend_override
        warning = ""
        if backend is None:
            backend, warning = select_input_backend(prefer_real=prefer_real)

        if prefer_real and backend.name == "line":
            if warning:
                print(f"[WARN] {warning}")
            print("[INFO] Real input unavailable; staying in command mode.")
            return 3

        if warning:
            print(f"[WARN] {warning}")
        print(
            "Live controls: 1/2/3/4 view, r reset, o overlays, c color, +/- zoom, q quit."
            " Mouse: wheel/click/drag."
        )

        frame_interval = 1.0 / max(1, self.radar_pipeline.config.fps_max)
        last_render_ts = -frame_interval
        last_heartbeat_ts = 0.0
        last_event_marker: tuple[int, str] | None = None
        needs_render = True
        iterations = 0
        controller = self.radar_input

        try:
            while True:
                iterations += 1
                now = time.monotonic()
                timeout = max(1, int(max(0.0, frame_interval - (now - last_render_ts)) * 1000.0))
                input_events = backend.poll_events(timeout_ms=timeout)
                events = self.event_store.recent(300)
                marker = (len(events), events[-1].event_id if events else "")
                has_new_events = marker != last_event_marker
                if has_new_events:
                    last_event_marker = marker

                scene = build_scene_from_events(events)
                should_quit = False
                for event in input_events:
                    self.view_state, should_quit = self._apply_input_event(
                        controller=controller,
                        view_state=self.view_state,
                        event=event,
                        scene=scene,
                    )
                    if should_quit:
                        break

                if should_quit:
                    return 0

                if input_events or has_new_events or (now - last_heartbeat_ts) >= heartbeat_s:
                    needs_render = True

                if needs_render and (now - last_render_ts) >= frame_interval:
                    if backend.name == "real-terminal":
                        print("\x1b[2J\x1b[H", end="")
                    print(render_terminal_screen(events, pipeline=self.radar_pipeline, view_state=self.view_state))
                    stamp = time.monotonic()
                    last_render_ts = stamp
                    last_heartbeat_ts = stamp
                    needs_render = False

                if max_iterations is not None and iterations >= max_iterations:
                    return 0
        finally:
            backend.close()

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

        if cmd == "radar":
            prefer_real = True
            if len(parts) > 1 and parts[1].lower() in {"line", "--line"}:
                prefer_real = False
            status = self.live_radar_loop(prefer_real=prefer_real)
            return status in {0, 3}

        if cmd in {"1", "2", "3", "4", "r", "o", "c", "+", "-"}:
            self.view_state = self.radar_input.apply_key(self.view_state, cmd)
            return True

        if cmd == "mouse":
            return self._handle_mouse(parts[1:])

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
        print("  radar [line]         — live cockpit loop (real input upgrade, q to exit)")
        print("  1|2|3|4              — вид радара top/side/front/iso")
        print("  r                    — reset view")
        print("  o                    — toggle overlays")
        print("  c                    — toggle color")
        print("  +|-                  — zoom in/out")
        print("  mouse wheel up|down  — zoom мышью (эмуляция)")
        print("  mouse click x y      — выбор ближайшей цели")
        print("  mouse drag dx dy     — pan/rotate (iso)")
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

    def _handle_mouse(self, args: list[str]) -> bool:
        if len(args) >= 2 and args[0] == "wheel":
            delta = 1.0 if args[1] == "up" else -1.0 if args[1] == "down" else 0.0
            action = self.radar_input.handle_mouse(RadarMouseEvent(kind="wheel", delta=delta))
            self.view_state = self.radar_input.apply_action(self.view_state, action)
            return True
        if len(args) == 3 and args[0] == "click":
            try:
                x = float(args[1])
                y = float(args[2])
            except ValueError:
                print("Пример: mouse click 0.2 -0.1")
                return True
            action = self.radar_input.handle_mouse(RadarMouseEvent(kind="click", x=x, y=y, button="left"))
            self.view_state = self.radar_input.apply_action(
                self.view_state,
                action,
                scene=build_scene_from_events(self.event_store.recent(300)),
            )
            return True
        if len(args) == 3 and args[0] == "drag":
            try:
                dx = float(args[1])
                dy = float(args[2])
            except ValueError:
                print("Пример: mouse drag 0.1 -0.1")
                return True
            action = self.radar_input.handle_mouse(
                RadarMouseEvent(kind="drag", button="left", is_button_down=True, dx=dx, dy=dy)
            )
            self.view_state = self.radar_input.apply_action(self.view_state, action)
            return True
        print("mouse: wheel up|down | click <x> <y> | drag <dx> <dy>")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Mission Control Terminal (ASCII radar/HUD)")
    parser.add_argument(
        "--replay",
        metavar="JSONL",
        help="Render one truthful radar/HUD screen from EventStore JSONL trace.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive replay controls for --replay (hotkeys + mouse emulation).",
    )
    parser.add_argument(
        "--real-input",
        action="store_true",
        help="Enable live cockpit with real key/mouse backend; fallback to command mode when unavailable.",
    )
    parser.add_argument(
        "--renderer",
        choices=["auto", "unicode", "kitty", "sixel"],
        help="Radar renderer backend for replay/live loops.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        help="Override RADAR_FPS_MAX for replay/live loops.",
    )
    args = parser.parse_args()
    if args.replay:
        raise SystemExit(
            MissionControlTerminal.replay_events(
                args.replay,
                interactive=args.interactive,
                real_input=args.real_input,
                renderer=args.renderer,
                fps=args.fps,
            )
        )
    terminal = MissionControlTerminal()
    terminal.configure_radar_pipeline(renderer=args.renderer, fps=args.fps)
    terminal.run(real_input=args.real_input)


if __name__ == "__main__":
    main()
