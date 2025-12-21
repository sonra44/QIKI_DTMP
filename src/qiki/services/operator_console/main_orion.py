from __future__ import annotations

import math
import time
from typing import Any, Optional

from pydantic import ValidationError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, RichLog, Static

from qiki.services.operator_console.clients.nats_client import NATSClient
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel
from qiki.shared.nats_subjects import COMMANDS_CONTROL


class OrionHeader(Static):
    """Top status bar for ORION (no-mocks)."""

    online = reactive(False)
    battery = reactive("N/A")
    hull = reactive("N/A")
    rad = reactive("N/A")
    t_ext = reactive("N/A")
    t_core = reactive("N/A")
    age_ms = reactive("—")

    def render(self) -> str:
        online = "ONLINE" if self.online else "OFFLINE"
        return (
            f"{online}  "
            f"BAT {self.battery}%  "
            f"HULL {self.hull}%  "
            f"RAD {self.rad} µSv/h  "
            f"T_EXT {self.t_ext}°C  "
            f"T_CORE {self.t_core}°C  "
            f"AGE {self.age_ms}ms"
        )

    def update_from_telemetry(self, payload: dict[str, Any], *, nats_connected: bool) -> None:
        try:
            normalized = TelemetrySnapshotModel.normalize_payload(payload)
        except ValidationError:
            return

        now_ms = int(time.time() * 1000)
        ts_unix_ms = normalized.get("ts_unix_ms")
        age = None
        if isinstance(ts_unix_ms, int):
            age = max(0, now_ms - ts_unix_ms)

        self.battery = str(normalized.get("battery", "N/A"))
        hull = normalized.get("hull")
        if isinstance(hull, dict):
            self.hull = str(hull.get("integrity", "N/A"))
        self.rad = str(normalized.get("radiation_usvh", "N/A"))
        self.t_ext = str(normalized.get("temp_external_c", "N/A"))
        self.t_core = str(normalized.get("temp_core_c", "N/A"))
        self.age_ms = "—" if age is None else str(age)

        # ONLINE is a function of connectivity + freshness (no magic).
        self.online = bool(nats_connected and age is not None and age <= 3_000)


class OrionApp(App):
    TITLE = "QIKI — ORION"
    CSS = """
    Screen { background: #050505; }
    #orion-root { padding: 1; }
    #orion-header { color: #ffb000; background: #050505; }
    #command-dock { dock: bottom; }
    """

    BINDINGS = [
        Binding("f1", "show_screen('system')", "System"),
        Binding("f2", "show_screen('radar')", "Radar"),
        Binding("f3", "show_screen('events')", "Events"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    nats_connected: bool = False
    latest_telemetry: Optional[dict[str, Any]] = None

    def __init__(self) -> None:
        super().__init__()
        self.nats_client: Optional[NATSClient] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="orion-root"):
            yield OrionHeader(id="orion-header")

            with Container(id="screen-system"):
                table = DataTable(id="telemetry-table")
                table.add_columns("Metric", "Value", "Unit", "Updated")
                yield table

            with Container(id="screen-radar"):
                radar_table = DataTable(id="radar-table")
                radar_table.add_columns("Track", "range_m", "bearing_deg", "vr_mps", "obj_type")
                yield radar_table

            with Container(id="screen-events"):
                yield RichLog(id="events-log", wrap=True, highlight=True)

            yield Input(
                placeholder="command> (help, screen system|radar|events, sim.start/stop/...)",
                id="command-dock",
            )

    async def on_mount(self) -> None:
        self.action_show_screen("system")
        self._seed_system_table()
        self._seed_radar_table()
        await self._init_nats()
        self.set_interval(0.5, self._refresh_header)

    def _log(self, msg: str) -> None:
        try:
            log = self.query_one("#events-log", RichLog)
            log.write(msg)
        except Exception:
            pass

    def _seed_system_table(self) -> None:
        try:
            table = self.query_one("#telemetry-table", DataTable)
        except Exception:
            return
        table.clear()
        updated = "—"
        table.add_row("ONLINE", "no", "—", updated)
        table.add_row("Position X", "N/A", "m", updated)
        table.add_row("Position Y", "N/A", "m", updated)
        table.add_row("Position Z", "N/A", "m", updated)
        table.add_row("Velocity", "N/A", "m/s", updated)
        table.add_row("Heading", "N/A", "deg", updated)
        table.add_row("Roll", "N/A", "deg", updated)
        table.add_row("Pitch", "N/A", "deg", updated)
        table.add_row("Yaw", "N/A", "deg", updated)
        table.add_row("Thermal core", "N/A", "°C", updated)
        table.add_row("Thermal bus", "N/A", "°C", updated)
        table.add_row("Thermal battery", "N/A", "°C", updated)
        table.add_row("Thermal radiator", "N/A", "°C", updated)
        table.add_row("Battery", "N/A", "%", updated)
        table.add_row("Power in", "N/A", "W", updated)
        table.add_row("Power out", "N/A", "W", updated)
        table.add_row("Bus V", "N/A", "V", updated)
        table.add_row("Bus A", "N/A", "A", updated)
        table.add_row("Hull", "N/A", "%", updated)
        table.add_row("Radiation", "N/A", "µSv/h", updated)
        table.add_row("Temp external", "N/A", "°C", updated)
        table.add_row("Temp core", "N/A", "°C", updated)

    def _seed_radar_table(self) -> None:
        try:
            table = self.query_one("#radar-table", DataTable)
        except Exception:
            return
        table.clear()
        table.add_row("—", "N/A", "N/A", "N/A", "no tracks yet")

    @staticmethod
    def _telemetry_age_ms(normalized: dict[str, Any]) -> Optional[int]:
        ts_unix_ms = normalized.get("ts_unix_ms")
        if not isinstance(ts_unix_ms, int):
            return None
        now_ms = int(time.time() * 1000)
        return max(0, now_ms - ts_unix_ms)

    def _telemetry_online(self, normalized: dict[str, Any]) -> bool:
        age = self._telemetry_age_ms(normalized)
        return bool(self.nats_connected and age is not None and age <= 3_000)

    async def _init_nats(self) -> None:
        self.nats_client = NATSClient()
        try:
            await self.nats_client.connect()
            self.nats_connected = True
            self._log("✅ NATS connected")
        except Exception as e:
            self.nats_connected = False
            self._log(f"❌ NATS connect failed: {e}")
            return

        # Subscriptions are best-effort; missing streams shouldn't crash UI.
        try:
            await self.nats_client.subscribe_system_telemetry(self.handle_telemetry_data)
            self._log("📈 Subscribed: qiki.telemetry")
        except Exception as e:
            self._log(f"⚠️ Telemetry subscribe failed: {e}")

        try:
            await self.nats_client.subscribe_tracks(self.handle_track_data)
            self._log("📡 Subscribed: radar tracks")
        except Exception as e:
            self._log(f"⚠️ Radar tracks subscribe failed: {e}")

        try:
            await self.nats_client.subscribe_events(self.handle_event_data)
            self._log("🧾 Subscribed: events wildcard")
        except Exception as e:
            self._log(f"⚠️ Events subscribe failed: {e}")

        try:
            await self.nats_client.subscribe_control_responses(self.handle_control_response)
            self._log("↩️ Subscribed: control responses")
        except Exception as e:
            self._log(f"⚠️ Control responses subscribe failed: {e}")

    def _refresh_header(self) -> None:
        if not self.latest_telemetry:
            return
        try:
            header = self.query_one("#orion-header", OrionHeader)
            header.update_from_telemetry(self.latest_telemetry, nats_connected=self.nats_connected)
        except Exception:
            return

    async def handle_telemetry_data(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return
        self.latest_telemetry = payload

        # Header refresh
        self._refresh_header()

        # System table update
        try:
            table = self.query_one("#telemetry-table", DataTable)
        except Exception:
            return

        try:
            normalized = TelemetrySnapshotModel.normalize_payload(payload)
        except ValidationError as e:
            self._log(f"⚠️ Bad telemetry payload: {e}")
            return

        updated = time.strftime("%H:%M:%S")
        table.clear()

        def get(path: str, default: str = "N/A") -> str:
            cur: Any = normalized
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return default if cur is None else str(cur)

        def fmt_deg_from_rad(value: Any) -> str:
            if not isinstance(value, (int, float)):
                return "N/A"
            return str(round(math.degrees(value), 3))

        def thermal_temp(node_id: str) -> str:
            thermal = normalized.get("thermal") if isinstance(normalized, dict) else None
            thermal = thermal if isinstance(thermal, dict) else {}
            nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
            if not isinstance(nodes, list):
                return "N/A"
            for node in nodes:
                if isinstance(node, dict) and node.get("id") == node_id:
                    value = node.get("temp_c")
                    return "N/A" if value is None else str(value)
            return "N/A"

        online = self._telemetry_online(normalized)
        att = normalized.get("attitude") if isinstance(normalized, dict) else None
        att = att if isinstance(att, dict) else {}
        table.add_row("ONLINE", "yes" if online else "no", "—", updated)
        table.add_row("Position X", get("position.x"), "m", updated)
        table.add_row("Position Y", get("position.y"), "m", updated)
        table.add_row("Position Z", get("position.z"), "m", updated)
        table.add_row("Velocity", get("velocity"), "m/s", updated)
        table.add_row("Heading", get("heading"), "deg", updated)
        table.add_row("Roll", fmt_deg_from_rad(att.get("roll_rad")), "deg", updated)
        table.add_row("Pitch", fmt_deg_from_rad(att.get("pitch_rad")), "deg", updated)
        table.add_row("Yaw", fmt_deg_from_rad(att.get("yaw_rad")), "deg", updated)
        table.add_row("Thermal core", thermal_temp("core"), "°C", updated)
        table.add_row("Thermal bus", thermal_temp("bus"), "°C", updated)
        table.add_row("Thermal battery", thermal_temp("battery"), "°C", updated)
        table.add_row("Thermal radiator", thermal_temp("radiator"), "°C", updated)
        table.add_row("Battery", get("battery"), "%", updated)
        table.add_row("Power in", get("power.power_in_w"), "W", updated)
        table.add_row("Power out", get("power.power_out_w"), "W", updated)
        table.add_row("Bus V", get("power.bus_v"), "V", updated)
        table.add_row("Bus A", get("power.bus_a"), "A", updated)
        table.add_row("Hull", get("hull.integrity"), "%", updated)
        table.add_row("Radiation", get("radiation_usvh"), "µSv/h", updated)
        table.add_row("Temp external", get("temp_external_c"), "°C", updated)
        table.add_row("Temp core", get("temp_core_c"), "°C", updated)

    async def handle_track_data(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return
        try:
            table = self.query_one("#radar-table", DataTable)
        except Exception:
            return

        updated = time.strftime("%H:%M:%S")
        track_id = payload.get("track_id") or payload.get("trackId") or "unknown"
        table.clear()
        table.add_row(
            str(track_id),
            str(payload.get("range_m", "N/A")),
            str(payload.get("bearing_deg", "N/A")),
            str(payload.get("vr_mps", "N/A")),
            str(payload.get("object_type", "N/A")),
        )
        self._log(f"🎯 Track update ({updated}): {track_id}")

    async def handle_event_data(self, data: dict) -> None:
        subject = data.get("subject") if isinstance(data, dict) else None
        payload = data.get("data") if isinstance(data, dict) else None
        event_type = None
        severity = None
        if isinstance(payload, dict):
            event_type = payload.get("type") or payload.get("event_type")
            severity = payload.get("severity")
        self._log(f"🧾 Event: {severity or '-'} {event_type or 'unknown'} ({subject or 'n/a'})")

    async def handle_control_response(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        success = payload.get("success")
        request_id = payload.get("requestId") or payload.get("request_id")
        message = None
        inner_payload = payload.get("payload")
        if isinstance(inner_payload, dict):
            message = inner_payload.get("status") or inner_payload.get("message")
        self._log(f"↩️ Control response: success={success} request={request_id} {message or ''}".strip())

    def action_show_screen(self, screen: str) -> None:
        for sid in ("system", "radar", "events"):
            try:
                self.query_one(f"#screen-{sid}", Container).display = sid == screen
            except Exception:
                pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-dock":
            return

        raw = (event.value or "").strip()
        event.input.value = ""
        if not raw:
            return

        if raw == "help":
            self._log("Commands: help | screen system|radar|events | sim.start|sim.pause|sim.stop|sim.reset")
            return

        if raw.startswith("screen "):
            _, _, name = raw.partition(" ")
            name = name.strip()
            if name in {"system", "radar", "events"}:
                self.action_show_screen(name)
                return
            self._log(f"Unknown screen: {name}")
            return

        if raw.startswith("sim."):
            await self._publish_sim_command(raw)
            return

        self._log(f"Unknown command: {raw}")

    async def _publish_sim_command(self, cmd_name: str) -> None:
        if not self.nats_client:
            self._log("❌ NATS not initialized")
            return

        cmd = CommandMessage(
            command_name=cmd_name,
            parameters={},
            metadata=MessageMetadata(
                message_type="control_command",
                source="operator_console.orion",
                destination="faststream_bridge",
            ),
        )
        try:
            await self.nats_client.publish_command(COMMANDS_CONTROL, cmd.model_dump(mode="json"))
            self._log(f"📤 Published: {cmd_name}")
        except Exception as e:
            self._log(f"❌ Publish failed: {e}")


if __name__ == "__main__":
    OrionApp().run()
