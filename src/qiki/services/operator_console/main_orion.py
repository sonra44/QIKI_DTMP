from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import time
from typing import Any, Optional

from pydantic import ValidationError
from rich.table import Table
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static

from qiki.services.operator_console.clients.nats_client import NATSClient
from qiki.services.operator_console.ui import i18n as I18N
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel
from qiki.shared.nats_subjects import COMMANDS_CONTROL

try:
    from qiki.services.operator_console.ui.charts import PpiScopeRenderer
except Exception:
    # Radar is not a priority; ORION must still boot even if optional radar renderer is absent.
    PpiScopeRenderer = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class OrionAppSpec:
    screen: str
    title: str
    hotkey: str
    hotkey_label: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectionContext:
    app_id: str
    key: str
    kind: str
    source: str
    created_at_epoch: float
    payload: Any
    ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    type: str
    source: str
    ts_epoch: float
    level: str
    payload: Any
    subject: str = ""


@dataclass(frozen=True, slots=True)
class SystemStateBlock:
    block_id: str
    title: str
    status: str
    value: str
    ts_epoch: Optional[float]
    envelope: Optional[EventEnvelope] = None


@dataclass(frozen=True, slots=True)
class FreshnessThresholds:
    fresh_max_s: float
    stale_max_s: float


class SnapshotStore:
    """Last-known snapshots per type (and optional per key), with freshness."""

    def __init__(self) -> None:
        self._last_by_type: dict[str, EventEnvelope] = {}
        self._last_by_type_by_key: dict[str, dict[str, EventEnvelope]] = {}

    def put(self, env: EventEnvelope, *, key: Optional[str] = None) -> None:
        t = (env.type or "").strip().lower() or I18N.UNKNOWN
        self._last_by_type[t] = env
        k = key if key is not None else (env.subject or env.event_id or "")
        if not k:
            return
        bucket = self._last_by_type_by_key.setdefault(t, {})
        bucket[k] = env

    def get_last(self, type_name: str) -> Optional[EventEnvelope]:
        t = (type_name or "").strip().lower()
        if not t:
            return None
        return self._last_by_type.get(t)

    def get_last_by_key(self, type_name: str, key: str) -> Optional[EventEnvelope]:
        t = (type_name or "").strip().lower()
        k = (key or "").strip()
        if not t or not k:
            return None
        return self._last_by_type_by_key.get(t, {}).get(k)

    def age_s(self, type_name: str, *, now_epoch: Optional[float] = None) -> Optional[float]:
        env = self.get_last(type_name)
        if env is None:
            return None
        now = time.time() if now_epoch is None else float(now_epoch)
        return max(0.0, now - float(env.ts_epoch))

    def last_ts_epoch(self) -> Optional[float]:
        if not self._last_by_type:
            return None
        return max((float(env.ts_epoch) for env in self._last_by_type.values()), default=None)

    def last_by_type_values(self) -> tuple[EventEnvelope, ...]:
        return tuple(self._last_by_type.values())

    def last_event_age_s(self, *, now_epoch: Optional[float] = None) -> Optional[float]:
        ts = self.last_ts_epoch()
        if ts is None:
            return None
        now = time.time() if now_epoch is None else float(now_epoch)
        return max(0.0, now - float(ts))

    def get_last_event(self) -> Optional[EventEnvelope]:
        if not self._last_by_type:
            return None
        return max(self._last_by_type.values(), key=lambda e: float(e.ts_epoch), default=None)

    @staticmethod
    def _thresholds_for_type(type_name: str) -> FreshnessThresholds:
        t = (type_name or "").strip().lower()
        if t in {"telemetry"}:
            return FreshnessThresholds(fresh_max_s=30.0, stale_max_s=300.0)
        if t in {"mission", "task"}:
            return FreshnessThresholds(fresh_max_s=300.0, stale_max_s=3600.0)
        if t in {"power"}:
            return FreshnessThresholds(fresh_max_s=60.0, stale_max_s=900.0)
        return FreshnessThresholds(fresh_max_s=60.0, stale_max_s=600.0)

    @classmethod
    def freshness_for_age(cls, type_name: str, age_s: Optional[float]) -> Optional[str]:
        if age_s is None:
            return None
        thresholds = cls._thresholds_for_type(type_name)
        age = max(0.0, float(age_s))
        if age < thresholds.fresh_max_s:
            return "fresh"
        if age < thresholds.stale_max_s:
            return "stale"
        return "dead"

    def freshness(self, type_name: str, *, now_epoch: Optional[float] = None) -> Optional[str]:
        age = self.age_s(type_name, now_epoch=now_epoch)
        if age is None:
            return None
        return self.freshness_for_age(type_name, age)

    def freshness_label(self, type_name: str, *, now_epoch: Optional[float] = None) -> str:
        f = self.freshness(type_name, now_epoch=now_epoch)
        if f is None:
            return I18N.NA
        if f == "fresh":
            return I18N.bidi("FRESH", "СВЕЖО")
        if f == "stale":
            return I18N.bidi("STALE", "УСТАРЕЛО")
        return I18N.bidi("DEAD", "НЕТ")


ORION_APPS: tuple[OrionAppSpec, ...] = (
    OrionAppSpec(
        screen="system",
        title=I18N.bidi("System", "Система"),
        hotkey="f1",
        hotkey_label="F1",
        aliases=("system", "система", "sys", "сист"),
    ),
    OrionAppSpec(
        screen="radar",
        title=I18N.bidi("Radar", "Радар"),
        hotkey="f2",
        hotkey_label="F2",
        aliases=("radar", "радар"),
    ),
    OrionAppSpec(
        screen="events",
        title=I18N.bidi("Events", "События"),
        hotkey="f3",
        hotkey_label="F3",
        aliases=("events", "события", "event", "событие", "log", "лог"),
    ),
    OrionAppSpec(
        screen="console",
        title=I18N.bidi("Console", "Консоль"),
        hotkey="f4",
        hotkey_label="F4",
        aliases=("console", "консоль", "logs", "логи", "shell", "оболочка"),
    ),
    OrionAppSpec(
        screen="summary",
        title=I18N.bidi("Summary", "Сводка"),
        hotkey="f5",
        hotkey_label="F5",
        aliases=("summary", "сводка", "home", "дом"),
    ),
    OrionAppSpec(
        screen="power",
        title=I18N.bidi("Power systems", "Система питания"),
        hotkey="f6",
        hotkey_label="F6",
        aliases=("power", "питание", "energy", "энергия"),
    ),
    OrionAppSpec(
        screen="diagnostics",
        title=I18N.bidi("Diagnostics", "Диагностика"),
        hotkey="f7",
        hotkey_label="F7",
        aliases=("diagnostics", "диагностика", "diag", "диаг"),
    ),
    OrionAppSpec(
        screen="mission",
        title=I18N.bidi("Mission control", "Управление миссией"),
        hotkey="f8",
        hotkey_label="F8",
        aliases=("mission", "миссия", "tasks", "задачи", "task", "задача"),
    ),
)


SCREEN_BY_ALIAS: dict[str, str] = {a: app.screen for app in ORION_APPS for a in app.aliases}


class OrionHeader(Static):
    """Top status bar for ORION (no-mocks)."""

    online = reactive(False)
    battery = reactive(I18N.NA)
    hull = reactive(I18N.NA)
    rad = reactive(I18N.NA)
    t_ext = reactive(I18N.NA)
    t_core = reactive(I18N.NA)
    age = reactive(I18N.NA)
    freshness = reactive(I18N.NA)

    def render(self) -> str:
        online = I18N.online_offline(self.online)
        return (
            f"{online}  "
            f"{I18N.bidi('Battery', 'Батарея')} {self.battery}  "
            f"{I18N.bidi('Hull', 'Корпус')} {self.hull}  "
            f"{I18N.bidi('Radiation', 'Радиация')} {self.rad}  "
            f"{I18N.bidi('External temperature', 'Наружная температура')} {self.t_ext}  "
            f"{I18N.bidi('Core temperature', 'Температура ядра')} {self.t_core}  "
            f"{I18N.bidi('Age', 'Возраст')} {self.age}  "
            f"{I18N.bidi('Freshness', 'Свежесть')} {self.freshness}"
        )

    def update_from_telemetry(
        self,
        payload: dict[str, Any],
        *,
        nats_connected: bool,
        telemetry_age_s: Optional[float],
        telemetry_freshness_label: str,
    ) -> None:
        try:
            normalized = TelemetrySnapshotModel.normalize_payload(payload)
        except ValidationError:
            return

        self.battery = I18N.pct(normalized.get("battery"), digits=2)
        hull = normalized.get("hull")
        if isinstance(hull, dict):
            self.hull = I18N.pct(hull.get("integrity"), digits=1)
        self.rad = I18N.num_unit(
            normalized.get("radiation_usvh"),
            "microsieverts per hour",
            "микрозиверты в час",
            digits=2,
        )
        self.t_ext = I18N.num_unit(normalized.get("temp_external_c"), "°C", "°C", digits=1)
        self.t_core = I18N.num_unit(normalized.get("temp_core_c"), "°C", "°C", digits=1)
        self.age = I18N.fmt_age(telemetry_age_s)
        self.freshness = telemetry_freshness_label

        # ONLINE is a function of connectivity + freshness (no magic).
        self.online = bool(nats_connected and telemetry_freshness_label == I18N.bidi("FRESH", "СВЕЖО"))


class OrionSidebar(Static):
    can_focus = True
    active_screen = reactive("system")

    def set_active(self, screen: str) -> None:
        self.active_screen = screen
        self.refresh()

    @staticmethod
    def _line(label: str, *, active: bool) -> str:
        mark = "▶" if active else " "
        return f"{mark} {label}"

    def render(self) -> str:
        items = [
            (app.screen, self._line(app.title, active=self.active_screen == app.screen))
            for app in ORION_APPS
        ]
        lines = [
            I18N.bidi("ORION SHELL", "ORION ОБОЛОЧКА"),
            "—" * 18,
            *(f"{app.hotkey_label} {line}" for (app, (_sid, line)) in zip(ORION_APPS, items, strict=False)),
            "",
            f"{I18N.bidi('TAB', 'TAB')} {I18N.bidi('focus cycle', 'цикл фокуса')}",
            f"{I18N.bidi('Enter', 'Enter')} {I18N.bidi('run command', 'выполнить команду')}",
            f"{I18N.bidi('Ctrl+C', 'Ctrl+C')} {I18N.bidi('quit', 'выход')}",
        ]
        return "\n".join(lines)


class OrionKeybar(Static):
    def render(self) -> str:
        active_screen = getattr(self.app, "active_screen", "system")
        extra: list[str] = [f"{I18N.bidi('TAB', 'TAB')} {I18N.bidi('Focus', 'Фокус')}"]
        if active_screen in {"radar", "events", "console", "summary"}:
            extra.append(
                f"{I18N.bidi('Up/Down arrows', 'Стрелки вверх/вниз')} {I18N.bidi('Selection', 'Выбор')}"
            )
        extra.extend(
            [
                f"F9 {I18N.bidi('Help', 'Помощь')}",
                f"F10 {I18N.bidi('Quit', 'Выход')}",
            ]
        )
        return "  ".join([*(f"{app.hotkey_label} {app.title}" for app in ORION_APPS), *extra])


class OrionPanel(Static):
    can_focus = True


class OrionInspector(Static):
    """Right-side detail pane (no-mocks)."""

    can_focus = True

    @staticmethod
    def _table(rows: list[tuple[str, str]]) -> Table:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=2, no_wrap=False, overflow="fold")
        table.add_column(justify="left", ratio=3, no_wrap=False, overflow="fold")
        for label, value in rows:
            table.add_row(label, value)
        return table

    @staticmethod
    def safe_preview(value: Any, *, max_chars: int = 260, max_lines: int = 12) -> str:
        if value is None:
            return I18N.NA
        if isinstance(value, (bytes, bytearray)):
            return f"{I18N.bidi('bytes', 'байты')}: {len(value)}"
        try:
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except TypeError:
            rendered = str(value)

        lines = rendered.splitlines()
        if max_lines > 0 and len(lines) > max_lines:
            rendered = "\n".join(lines[:max_lines]) + "\n…"

        if len(rendered) <= max_chars:
            return rendered
        return rendered[: max(0, max_chars - 1)] + "…"

class OrionApp(App):
    TITLE = "QIKI — ORION"
    CSS = """
    Screen { background: #050505; }
    #orion-root { padding: 1; }
    #orion-header { dock: top; height: 2; color: #ffb000; background: #050505; }
    #orion-sidebar { dock: left; width: 28; border: round #303030; padding: 1; color: #e0e0e0; background: #050505; }
    #bottom-bar { dock: bottom; height: 4; }
    #command-dock { height: 3; padding: 0 1; width: 1fr; color: #e0e0e0; background: #101010; border: round #303030; }
    #command-dock:focus { border: round #ffb000; }
    #orion-keybar { height: 1; color: #a0a0a0; background: #050505; }
    #system-dashboard { layout: grid; grid-size: 2 2; grid-gutter: 1 1; }
    .mfd-panel { border: round #303030; padding: 0 1; color: #e0e0e0; background: #050505; }
    #radar-layout { height: 1fr; }
    #radar-ppi { width: 47; height: 25; color: #00ff66; background: #050505; }
    #radar-table { width: 1fr; }
    #orion-inspector { dock: right; width: 44; border: round #303030; padding: 1; color: #e0e0e0; background: #050505; }
    #events-table { height: 1fr; }
    #console-table { height: 1fr; }
    #summary-table { height: 1fr; }
    #power-table { height: 1fr; }
    #diagnostics-table { height: 1fr; }
    #mission-table { height: 1fr; }
    """

    BINDINGS = [
        *(Binding(app.hotkey, f"show_screen('{app.screen}')", app.title) for app in ORION_APPS),
        Binding("tab", "cycle_focus", "TAB focus/фокус"),
        Binding("f9", "help", "Help/Помощь"),
        Binding("f10", "quit", "Quit/Выход"),
        Binding("ctrl+c", "quit", "Quit/Выход"),
    ]

    nats_connected: bool = False
    latest_telemetry: Optional[dict[str, Any]] = None
    active_screen = reactive("system")

    def __init__(self) -> None:
        super().__init__()
        self.nats_client: Optional[NATSClient] = None
        self._tracks_by_id: dict[str, tuple[dict[str, Any], float]] = {}
        self._last_event: Optional[dict[str, Any]] = None
        self._events_by_key: dict[str, dict[str, Any]] = {}
        self._console_by_key: dict[str, dict[str, Any]] = {}
        self._summary_by_key: dict[str, dict[str, Any]] = {}
        self._power_by_key: dict[str, dict[str, Any]] = {}
        self._diagnostics_by_key: dict[str, dict[str, Any]] = {}
        self._mission_by_key: dict[str, dict[str, Any]] = {}
        self._selection_by_app: dict[str, SelectionContext] = {}
        self._snapshots = SnapshotStore()
        self._events_filter_type: Optional[str] = None
        self._events_filter_text: Optional[str] = None
        # TTL is used only to mark tracks as stale in UI (no-mocks: we show last known + age).
        # Keep it reasonably large by default so operators can actually observe the pipeline.
        self._track_ttl_sec: float = float(os.getenv("OPERATOR_CONSOLE_TRACK_TTL_SEC", "60.0"))
        self._max_track_rows: int = int(os.getenv("OPERATOR_CONSOLE_MAX_TRACK_ROWS", "25"))
        self._ppi_renderer = (
            None
            if PpiScopeRenderer is None
            else PpiScopeRenderer(
                width=int(os.getenv("OPERATOR_CONSOLE_PPI_WIDTH", "47")),
                height=int(os.getenv("OPERATOR_CONSOLE_PPI_HEIGHT", "25")),
                max_range_m=float(os.getenv("OPERATOR_CONSOLE_PPI_MAX_RANGE_M", "500.0")),
            )
        )
        self._update_system_snapshot()

    def _update_system_snapshot(self) -> None:
        now = time.time()
        self._snapshots.put(
            EventEnvelope(
                event_id=f"system-{int(now * 1000)}",
                type="system",
                source="orion",
                ts_epoch=now,
                level="info",
                payload={
                    "nats_connected": bool(self.nats_connected),
                    "events_filter_type": self._events_filter_type,
                    "events_filter_text": self._events_filter_text,
                },
            ),
            key="system",
        )

    @staticmethod
    def _fmt_num(value: Any, *, digits: int = 2) -> str:
        if not isinstance(value, (int, float)):
            return I18N.NA
        return str(round(float(value), digits))

    @staticmethod
    def _fmt_age_s(seconds: Optional[float]) -> str:
        return I18N.fmt_age(seconds)

    @staticmethod
    def _kind_label(kind: str) -> str:
        k = (kind or "").strip().lower()
        return {
            "event": I18N.bidi("event", "событие"),
            "console": I18N.bidi("console", "консоль"),
            "metric": I18N.bidi("metric", "метрика"),
            "track": I18N.bidi("track", "трек"),
            "log": I18N.bidi("log", "лог"),
        }.get(k, kind or I18N.UNKNOWN)

    @staticmethod
    def _source_label(source: str) -> str:
        s = (source or "").strip().lower()
        if s in {"shell", "оболочка"}:
            return I18N.bidi("shell", "оболочка")
        if s in {"telemetry", "телеметрия"}:
            return I18N.bidi("telemetry", "телеметрия")
        if s in {"diagnostics", "диагностика"}:
            return I18N.bidi("diagnostics", "диагностика")
        if s in {"radar", "радар"}:
            return I18N.bidi("radar", "радар")
        if s in {"nats"}:
            return "NATS"
        return source or I18N.NA

    @staticmethod
    def _derive_event_type(subject: Any, payload: Any) -> str:
        if isinstance(payload, dict):
            for k in ("category", "domain", "orion_type", "ui_type"):
                v = payload.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip().lower()
        s = str(subject or "").lower()
        if "power" in s:
            return "power"
        if "nav" in s or "navigation" in s:
            return "nav"
        if "diag" in s or "diagnostic" in s:
            return "diag"
        if "mission" in s or "task" in s:
            return "mission"
        if "radar" in s or "track" in s:
            return "radar"
        if "comm" in s or "comms" in s:
            return "comms"
        if "sensor" in s:
            return "sensor"
        if "system" in s or "telemetry" in s:
            return "system"
        return "unknown"

    @staticmethod
    def _normalize_level(raw: Any) -> str:
        if not isinstance(raw, str):
            return "info"
        v = raw.strip().lower()
        return {
            "dbg": "debug",
            "debug": "debug",
            "inf": "info",
            "info": "info",
            "warn": "warn",
            "warning": "warn",
            "err": "error",
            "error": "error",
            "crit": "critical",
            "critical": "critical",
        }.get(v, "info")

    @classmethod
    def _level_label(cls, raw: Any) -> str:
        level = cls._normalize_level(raw)
        return {
            "debug": I18N.bidi("debug", "отладка"),
            "info": I18N.bidi("info", "информация"),
            "warn": I18N.bidi("warning", "предупреждение"),
            "error": I18N.bidi("error", "ошибка"),
            "critical": I18N.bidi("critical", "критично"),
        }.get(level, I18N.NA)

    def _set_selection(self, ctx: SelectionContext) -> None:
        self._selection_by_app[ctx.app_id] = ctx
        if self.active_screen == ctx.app_id:
            self._refresh_inspector()

    def _active_tracks_sorted(self) -> list[tuple[str, dict[str, Any], float]]:
        items = list(self._tracks_by_id.items())

        def sort_key(item: tuple[str, tuple[dict[str, Any], float]]) -> tuple[int, float, float]:
            _tid, (payload, seen) = item
            range_m = payload.get("range_m")
            if isinstance(range_m, (int, float)):
                return (0, float(range_m), -seen)
            return (1, float("inf"), -seen)

        items_sorted = sorted(items, key=sort_key)[: max(1, self._max_track_rows)]
        return [(tid, payload, seen) for tid, (payload, seen) in items_sorted]

    def _render_tracks_table(self) -> None:
        try:
            table = self.query_one("#radar-table", DataTable)
        except Exception:
            return

        table.clear()
        items = self._active_tracks_sorted()
        if not items:
            table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NO_TRACKS_YET)
            return

        selected_row: Optional[int] = None
        selected_track_id = self._selection_by_app.get("radar").key if "radar" in self._selection_by_app else None
        for track_id, payload, _seen in items:
            age_s = max(0.0, time.time() - _seen)
            ttl = self._track_ttl_sec
            freshness = f"{age_s:.1f}s"
            if ttl > 0 and age_s > ttl:
                freshness = I18N.stale(freshness)
            table.add_row(
                track_id,
                self._fmt_num(payload.get("range_m")),
                self._fmt_num(payload.get("bearing_deg"), digits=1),
                self._fmt_num(payload.get("vr_mps"), digits=2),
                f"{payload.get('object_type', I18N.NA)} ({freshness})",
            )
            if selected_track_id is not None and track_id == selected_track_id:
                selected_row = table.row_count - 1

        if selected_track_id is None and items:
            track_id, payload, seen = items[0]
            self._set_selection(
                SelectionContext(
                    app_id="radar",
                    key=track_id,
                    kind="track",
                    source="radar",
                    created_at_epoch=float(seen),
                    payload=payload,
                    ids=(track_id,),
                )
            )
            selected_row = 0

        if selected_row is not None:
            try:
                table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def _render_radar_ppi(self) -> None:
        try:
            ppi = self.query_one("#radar-ppi", Static)
        except Exception:
            return

        tracks = [payload for _tid, payload, _seen in self._active_tracks_sorted()]
        if self._ppi_renderer is None:
            ppi.update(I18N.bidi("Radar display unavailable", "Экран радара недоступен"))
            return
        ppi.update(self._ppi_renderer.render_tracks(tracks))

    def _refresh_radar(self) -> None:
        self._render_tracks_table()
        self._render_radar_ppi()
        if self.active_screen == "radar":
            self._refresh_inspector()

    def _refresh_summary(self) -> None:
        if self.active_screen == "summary":
            self._render_summary_table()

    def _refresh_diagnostics(self) -> None:
        if self.active_screen == "diagnostics":
            self._render_diagnostics_table()

    def _refresh_mission(self) -> None:
        if self.active_screen == "mission":
            self._render_mission_table()

    @staticmethod
    def _block_status_label(status: str) -> str:
        s = (status or "").strip().lower()
        if s in {"ok", "good"}:
            return I18N.bidi("OK", "ОК")
        if s in {"warn", "warning"}:
            return I18N.bidi("WARNING", "ПРЕДУПРЕЖДЕНИЕ")
        if s in {"crit", "critical"}:
            return I18N.bidi("CRITICAL", "КРИТИЧНО")
        return I18N.NA

    def _freshness_to_status(self, freshness: Optional[str]) -> str:
        if freshness is None:
            return "na"
        if freshness == "fresh":
            return "ok"
        if freshness == "stale":
            return "warn"
        return "crit"

    def _build_summary_blocks(self) -> list[SystemStateBlock]:
        now = time.time()

        telemetry_env = self._snapshots.get_last("telemetry")
        telemetry_age_s = self._snapshots.age_s("telemetry", now_epoch=now)
        telemetry_freshness = self._snapshots.freshness("telemetry", now_epoch=now)
        online = bool(self.nats_connected and telemetry_freshness == "fresh")
        telemetry_status = self._freshness_to_status(telemetry_freshness)

        blocks: list[SystemStateBlock] = []
        blocks.append(
            SystemStateBlock(
                block_id="telemetry_link",
                title=I18N.bidi("Telemetry link", "Канал телеметрии"),
                status="ok" if online else ("na" if telemetry_env is None else telemetry_status),
                value=f"{I18N.online_offline(online)} {self._snapshots.freshness_label('telemetry', now_epoch=now)}",
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )
        blocks.append(
            SystemStateBlock(
                block_id="telemetry_age",
                title=I18N.bidi("Telemetry age", "Возраст телеметрии"),
                status="na" if telemetry_age_s is None else telemetry_status,
                value=I18N.fmt_age(telemetry_age_s),
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # Power is derived from telemetry (no-mocks): if telemetry is missing -> N/A/НД.
        power_value = I18N.NA
        if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
            try:
                normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
            except ValidationError:
                normalized = {}
            if isinstance(normalized, dict):
                power_value = I18N.pct(normalized.get("battery"), digits=2)
        blocks.append(
            SystemStateBlock(
                block_id="power",
                title=I18N.bidi("Power systems", "Система питания"),
                status="na" if telemetry_env is None else telemetry_status,
                value=power_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        mission_env: Optional[EventEnvelope] = None
        for t in ("mission", "task"):
            mission_env = self._snapshots.get_last(t)
            if mission_env is not None:
                break
        mission_age_s = None
        mission_freshness = None
        if mission_env is not None:
            mission_age_s = max(0.0, now - float(mission_env.ts_epoch))
            mission_freshness = self._snapshots.freshness(mission_env.type, now_epoch=now)
        mission_status = self._freshness_to_status(mission_freshness)

        mission_value = I18N.NA
        if mission_env is not None:
            payload = mission_env.payload
            mission: dict[str, Any] = {}
            if isinstance(payload, dict):
                mission = payload.get("mission") if isinstance(payload.get("mission"), dict) else payload
            designator = mission.get("designator") or mission.get("mission_id") or mission.get("id")
            objective = mission.get("objective") or mission.get("goal") or mission.get("name")
            if designator and objective:
                mission_value = f"{designator} — {objective}"
            elif designator:
                mission_value = str(designator)
            elif objective:
                mission_value = str(objective)
        blocks.append(
            SystemStateBlock(
                block_id="mission",
                title=I18N.bidi("Mission control", "Управление миссией"),
                status="na" if mission_env is None else mission_status,
                value=mission_value,
                ts_epoch=None if mission_env is None else float(mission_env.ts_epoch),
                envelope=mission_env,
            )
        )

        last_event_age_s = self._snapshots.last_event_age_s(now_epoch=now)
        blocks.append(
            SystemStateBlock(
                block_id="last_event_age",
                title=I18N.bidi("Last event age", "Возраст последнего события"),
                status="na" if last_event_age_s is None else "ok",
                value=I18N.fmt_age(last_event_age_s),
                ts_epoch=self._snapshots.last_ts_epoch(),
                envelope=None,
            )
        )
        blocks.append(
            SystemStateBlock(
                block_id="events_filters",
                title=I18N.bidi("Events filters", "Фильтры событий"),
                status="na",
                value=f"type={self._events_filter_type or I18N.NA}; filter={self._events_filter_text or I18N.NA}",
                ts_epoch=None,
                envelope=None,
            )
        )

        return blocks

    def _render_summary_table(self) -> None:
        try:
            table = self.query_one("#summary-table", DataTable)
        except Exception:
            return

        table.clear()
        now = time.time()
        blocks = self._build_summary_blocks()

        self._summary_by_key = {}
        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status_label = self._block_status_label(block.status)
            table.add_row(block.title, status_label, block.value, I18N.fmt_age(age_s), key=block.block_id)
            self._summary_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status_label,
                "value": block.value,
                "age": I18N.fmt_age(age_s),
                "envelope": block.envelope,
            }

        # Keep an always-valid selection on Summary.
        first_key = blocks[0].block_id if blocks else "seed"
        current = self._selection_by_app.get("summary")
        if current is None or current.key not in self._summary_by_key:
            created_at_epoch = time.time()
            if blocks and blocks[0].ts_epoch is not None:
                created_at_epoch = float(blocks[0].ts_epoch)
            self._set_selection(
                SelectionContext(
                    app_id="summary",
                    key=first_key,
                    kind="metric",
                    source="summary",
                    created_at_epoch=created_at_epoch,
                    payload=self._summary_by_key.get(first_key, {}),
                    ids=(first_key,),
                )
            )
        try:
            table.move_cursor(row=0, column=0, animate=False, scroll=False)
        except Exception:
            pass

    def _render_power_table(self) -> None:
        try:
            table = self.query_one("#power-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._power_by_key = {}
            self._selection_by_app.pop("power", None)
            try:
                table.clear()
            except Exception:
                return
            table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, key="seed")

        telemetry_env = self._snapshots.get_last("telemetry")
        if telemetry_env is None or not isinstance(telemetry_env.payload, dict):
            seed_empty()
            return

        try:
            normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
        except ValidationError:
            seed_empty()
            return

        def get(path: str) -> Any:
            cur: Any = normalized
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return None
                cur = cur[part]
            return cur

        rows: list[tuple[str, str, str, Any]] = [
            (
                "battery_level",
                I18N.bidi("Battery level", "Уровень батареи"),
                I18N.pct(normalized.get("battery"), digits=2),
                normalized.get("battery"),
            ),
            (
                "state_of_charge",
                I18N.bidi("State of charge", "Уровень заряда"),
                I18N.pct(get("power.soc_pct"), digits=1),
                get("power.soc_pct"),
            ),
            (
                "power_input",
                I18N.bidi("Power input", "Входная мощность"),
                I18N.num_unit(get("power.power_in_w"), "watts", "ватты", digits=1),
                get("power.power_in_w"),
            ),
            (
                "power_consumption",
                I18N.bidi("Power consumption", "Потребляемая мощность"),
                I18N.num_unit(get("power.power_out_w"), "watts", "ватты", digits=1),
                get("power.power_out_w"),
            ),
            (
                "bus_voltage",
                I18N.bidi("Bus voltage", "Напряжение шины"),
                I18N.num_unit(get("power.bus_v"), "volts", "вольты", digits=2),
                get("power.bus_v"),
            ),
            (
                "bus_current",
                I18N.bidi("Bus current", "Ток шины"),
                I18N.num_unit(get("power.bus_a"), "amperes", "амперы", digits=2),
                get("power.bus_a"),
            ),
        ]

        self._power_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        now = time.time()
        age_s = max(0.0, now - float(telemetry_env.ts_epoch))
        age = I18N.fmt_age(age_s)
        source = I18N.bidi("telemetry", "телеметрия")

        def status_label(raw_value: Any, rendered_value: str) -> str:
            if raw_value is None:
                return I18N.NA
            if rendered_value == I18N.INVALID:
                return I18N.bidi("ABNORMAL", "НЕ НОРМА")
            return I18N.bidi("NORMAL", "НОРМА")

        for row_key, label, value, raw in rows:
            status = status_label(raw, value)
            table.add_row(label, status, value, age, source, key=row_key)
            self._power_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "raw": raw,
                "envelope": telemetry_env,
            }

        current = self._selection_by_app.get("power")
        if current is None or current.key not in self._power_by_key:
            first_key = rows[0][0]
            created_at_epoch = float(telemetry_env.ts_epoch)
            self._set_selection(
                SelectionContext(
                    app_id="power",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=created_at_epoch,
                    payload=telemetry_env.payload,
                    ids=(first_key,),
                )
            )
        try:
            table.move_cursor(row=0, column=0, animate=False, scroll=False)
        except Exception:
            pass

    def _render_diagnostics_table(self) -> None:
        try:
            table = self.query_one("#diagnostics-table", DataTable)
        except Exception:
            return

        now = time.time()

        def status_label(status: str) -> str:
            s = (status or "").strip().lower()
            if s in {"ok"}:
                return I18N.bidi("NORMAL", "НОРМА")
            if s in {"warn"}:
                return I18N.bidi("WARNING", "ПРЕДУПРЕЖДЕНИЕ")
            if s in {"crit"}:
                return I18N.bidi("ABNORMAL", "НЕ НОРМА")
            return I18N.NA

        system_env = self._snapshots.get_last_by_key("system", "system") or self._snapshots.get_last("system")
        system_payload = system_env.payload if isinstance(system_env, EventEnvelope) and isinstance(system_env.payload, dict) else {}
        nats_connected = bool(system_payload.get("nats_connected")) if isinstance(system_payload, dict) else bool(self.nats_connected)
        events_filter_type = system_payload.get("events_filter_type") if isinstance(system_payload, dict) else None
        events_filter_text = system_payload.get("events_filter_text") if isinstance(system_payload, dict) else None

        telemetry_env = self._snapshots.get_last("telemetry")
        telemetry_age_s = self._snapshots.age_s("telemetry", now_epoch=now)
        telemetry_freshness = self._snapshots.freshness("telemetry", now_epoch=now)
        telemetry_freshness_label = self._snapshots.freshness_label("telemetry", now_epoch=now)
        telemetry_status = "na"
        if telemetry_freshness == "fresh":
            telemetry_status = "ok"
        elif telemetry_freshness == "stale":
            telemetry_status = "warn"
        elif telemetry_freshness == "dead":
            telemetry_status = "crit"

        online = bool(nats_connected and telemetry_freshness == "fresh")
        last_event_age_s = self._snapshots.last_event_age_s(now_epoch=now)
        last_event_env = self._snapshots.get_last_event()

        cpu_usage = None
        memory_usage = None
        if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
            try:
                normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
            except ValidationError:
                normalized = {}
            if isinstance(normalized, dict):
                cpu_usage = normalized.get("cpu_usage")
                memory_usage = normalized.get("memory_usage")

        blocks: list[SystemStateBlock] = [
            SystemStateBlock(
                block_id="nats_connectivity",
                title=I18N.bidi("NATS connectivity", "Связь с NATS"),
                status="ok" if nats_connected else "crit",
                value=I18N.yes_no(nats_connected),
                ts_epoch=None if system_env is None else float(system_env.ts_epoch),
                envelope=system_env,
            ),
            SystemStateBlock(
                block_id="telemetry_link",
                title=I18N.bidi("Telemetry link", "Канал телеметрии"),
                status="ok" if online else telemetry_status,
                value=f"{I18N.online_offline(online)} {telemetry_freshness_label}",
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="telemetry_age",
                title=I18N.bidi("Telemetry age", "Возраст телеметрии"),
                status="na" if telemetry_age_s is None else telemetry_status,
                value=I18N.fmt_age(telemetry_age_s),
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="telemetry_freshness",
                title=I18N.bidi("Telemetry freshness", "Свежесть телеметрии"),
                status="na" if telemetry_freshness is None else telemetry_status,
                value=telemetry_freshness_label,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="last_event_age",
                title=I18N.bidi("Last event age", "Возраст последнего события"),
                status="na" if last_event_age_s is None else "ok",
                value=I18N.fmt_age(last_event_age_s),
                ts_epoch=None if last_event_env is None else float(last_event_env.ts_epoch),
                envelope=last_event_env,
            ),
            SystemStateBlock(
                block_id="events_filter_type",
                title=I18N.bidi("Events type filter", "Фильтр событий по типу"),
                status="na" if not events_filter_type else "ok",
                value=str(events_filter_type or I18N.NA),
                ts_epoch=None if system_env is None else float(system_env.ts_epoch),
                envelope=system_env,
            ),
            SystemStateBlock(
                block_id="events_filter_text",
                title=I18N.bidi("Events text filter", "Фильтр событий по тексту"),
                status="na" if not events_filter_text else "ok",
                value=str(events_filter_text or I18N.NA),
                ts_epoch=None if system_env is None else float(system_env.ts_epoch),
                envelope=system_env,
            ),
            SystemStateBlock(
                block_id="central_processing_unit_usage",
                title=I18N.bidi("Central processing unit usage", "Загрузка центрального процессора"),
                status="na" if cpu_usage is None else "ok",
                value=I18N.pct(cpu_usage, digits=1),
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="memory_usage",
                title=I18N.bidi("Memory usage", "Загрузка памяти"),
                status="na" if memory_usage is None else "ok",
                value=I18N.pct(memory_usage, digits=1),
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
        ]

        self._diagnostics_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status = status_label(block.status)
            table.add_row(block.title, status, block.value, I18N.fmt_age(age_s), key=block.block_id)
            self._diagnostics_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status,
                "value": block.value,
                "age": I18N.fmt_age(age_s),
                "envelope": block.envelope,
            }

        first_key = blocks[0].block_id if blocks else "seed"
        current = self._selection_by_app.get("diagnostics")
        if current is None or current.key not in self._diagnostics_by_key:
            created_at_epoch = time.time()
            env = self._diagnostics_by_key.get(first_key, {}).get("envelope")
            if isinstance(env, EventEnvelope):
                created_at_epoch = float(env.ts_epoch)
            self._set_selection(
                SelectionContext(
                    app_id="diagnostics",
                    key=first_key,
                    kind="metric",
                    source="diagnostics",
                    created_at_epoch=created_at_epoch,
                    payload=env.payload if isinstance(env, EventEnvelope) else self._diagnostics_by_key.get(first_key, {}),
                    ids=(first_key,),
                )
            )
        try:
            table.move_cursor(row=0, column=0, animate=False, scroll=False)
        except Exception:
            pass

    def _render_mission_table(self) -> None:
        try:
            table = self.query_one("#mission-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._mission_by_key = {}
            self._selection_by_app.pop("mission", None)
            try:
                table.clear()
            except Exception:
                return
            table.add_row("—", I18N.NA, I18N.NA, key="seed")

        def mission_env() -> Optional[EventEnvelope]:
            for t in ("mission", "task"):
                env = self._snapshots.get_last(t)
                if env is not None:
                    return env
            return None

        env = mission_env()
        if env is None:
            seed_empty()
            return

        payload = env.payload
        mission: dict[str, Any] = {}
        if isinstance(payload, dict):
            if isinstance(payload.get("mission"), dict):
                mission = payload["mission"]
            else:
                mission = payload

        designator = mission.get("designator") or mission.get("mission_id") or mission.get("id") or I18N.NA
        objective = mission.get("objective") or mission.get("goal") or mission.get("name") or I18N.NA
        priority = mission.get("priority") or mission.get("prio") or I18N.NA
        progress = mission.get("progress_pct") or mission.get("progress") or mission.get("completion_pct")

        steps_raw = mission.get("steps") or mission.get("mission_steps") or mission.get("tasks") or []
        steps: list[Any] = steps_raw if isinstance(steps_raw, list) else []

        self._mission_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        def row(key: str, item: str, status: str, value: str, *, record: dict[str, Any]) -> None:
            table.add_row(item, status, value, key=key)
            self._mission_by_key[key] = record

        row(
            "mission-designator",
            I18N.bidi("Designator", "Обозначение"),
            I18N.NA,
            str(designator) if designator is not None else I18N.NA,
            record={"kind": "mission", "field": "designator", "value": designator, "envelope": env},
        )
        row(
            "mission-objective",
            I18N.bidi("Objective", "Цель"),
            I18N.NA,
            str(objective) if objective is not None else I18N.NA,
            record={"kind": "mission", "field": "objective", "value": objective, "envelope": env},
        )
        row(
            "mission-priority",
            I18N.bidi("Priority", "Приоритет"),
            I18N.NA,
            str(priority) if priority is not None else I18N.NA,
            record={"kind": "mission", "field": "priority", "value": priority, "envelope": env},
        )
        row(
            "mission-progress",
            I18N.bidi("Progress", "Прогресс"),
            I18N.NA,
            I18N.pct(progress, digits=0) if progress is not None else I18N.NA,
            record={"kind": "mission", "field": "progress", "value": progress, "envelope": env},
        )

        def step_status(v: Any) -> str:
            if isinstance(v, str):
                s = v.strip().lower()
                if s in {"done", "completed", "ok"}:
                    return I18N.bidi("DONE", "ГОТОВО")
                if s in {"in_progress", "progress", "active", "current"}:
                    return I18N.bidi("IN PROGRESS", "В РАБОТЕ")
                if s in {"pending", "todo", "planned", "next"}:
                    return I18N.bidi("PENDING", "ОЖИДАЕТ")
            if isinstance(v, bool):
                return I18N.bidi("DONE", "ГОТОВО") if v else I18N.bidi("PENDING", "ОЖИДАЕТ")
            return I18N.NA

        for idx, step in enumerate(steps[:50]):
            title = None
            status_val = None
            detail = None
            if isinstance(step, str):
                title = step
            elif isinstance(step, dict):
                title = step.get("title") or step.get("name") or step.get("step") or step.get("id")
                status_val = step.get("status")
                if status_val is None:
                    if isinstance(step.get("done"), bool):
                        status_val = step.get("done")
                    elif isinstance(step.get("completed"), bool):
                        status_val = step.get("completed")
                    elif isinstance(step.get("current"), bool) and step.get("current") is True:
                        status_val = "in_progress"
                detail = step.get("detail") or step.get("description")

            title_str = str(title) if title else f"{I18N.bidi('Step', 'Шаг')} {idx + 1}"
            status_str = step_status(status_val)
            detail_str = str(detail) if detail else I18N.NA
            row(
                f"mission-step-{idx}",
                title_str,
                status_str,
                detail_str,
                record={"kind": "mission_step", "index": idx, "step": step, "envelope": env},
            )

        current = self._selection_by_app.get("mission")
        if current is None or current.key not in self._mission_by_key:
            self._set_selection(
                SelectionContext(
                    app_id="mission",
                    key="mission-designator",
                    kind="metric",
                    source="nats",
                    created_at_epoch=float(env.ts_epoch),
                    payload=self._mission_by_key.get("mission-designator", {}),
                    ids=("mission-designator", env.type),
                )
            )
        try:
            table.move_cursor(row=0, column=0, animate=False, scroll=False)
        except Exception:
            pass

    def _render_events_table(self) -> None:
        try:
            table = self.query_one("#events-table", DataTable)
        except Exception:
            return

        table.clear()
        items = [
            (key, rec)
            for key, rec in self._events_by_key.items()
            if isinstance(rec, dict) and isinstance(rec.get("envelope"), EventEnvelope)
        ]

        def passes(rec: dict[str, Any]) -> bool:
            if not self._events_filter_type:
                type_ok = True
            else:
                env: EventEnvelope = rec["envelope"]
                type_ok = env.type == self._events_filter_type
            if not type_ok:
                return False
            if not self._events_filter_text:
                return True
            env = rec["envelope"]
            needle = self._events_filter_text.lower()
            hay = " ".join(
                [
                    str(env.type or ""),
                    str(env.source or ""),
                    str(env.subject or ""),
                ]
            ).lower()
            if needle in hay:
                return True
            payload = env.payload
            try:
                payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            except TypeError:
                payload_str = str(payload)
            return needle in payload_str.lower()[:2000]

        items = [(k, r) for (k, r) in items if passes(r)]
        items.sort(key=lambda kv: float(kv[1]["envelope"].ts_epoch))  # oldest → newest

        if not items:
            table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, key="seed")
            self._selection_by_app.pop("events", None)
            return

        now = time.time()
        for key, rec in items[-200:]:
            env: EventEnvelope = rec["envelope"]
            age_s = max(0.0, now - float(env.ts_epoch))
            age_text = I18N.fmt_age(age_s)
            freshness = self._snapshots.freshness_for_age(env.type, age_s)
            if freshness == "stale":
                age_text = I18N.stale(age_text)
            elif freshness == "dead":
                age_text = f"{I18N.bidi('DEAD', 'НЕТ')}: {age_text}"
            table.add_row(
                time.strftime("%H:%M:%S", time.localtime(env.ts_epoch)),
                self._level_label(env.level),
                env.type,
                self._source_label(env.source),
                age_text,
                env.subject or I18N.NA,
                key=key,
            )

        # Ensure selection is visible under filter.
        current = self._selection_by_app.get("events")
        if current is None or current.key not in {k for (k, _r) in items}:
            key, rec = items[-1]
            env = rec["envelope"]
            self._set_selection(
                SelectionContext(
                    app_id="events",
                    key=key,
                    kind="event",
                    source=env.source,
                    created_at_epoch=env.ts_epoch,
                    payload=env.payload,
                    ids=(env.subject or I18N.NA, env.type),
                )
            )
        try:
            table.move_cursor(row=table.row_count - 1, column=0, animate=False, scroll=True)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        with Vertical(id="orion-root"):
            yield OrionSidebar(id="orion-sidebar")
            yield OrionHeader(id="orion-header")
            inspector = OrionInspector(id="orion-inspector")
            inspector.border_title = I18N.bidi("Inspector", "Инспектор")
            yield inspector

            with Vertical(id="bottom-bar"):
                yield Input(
                    placeholder=(
                        f"{I18N.bidi('command', 'команда')}> "
                        f"{I18N.bidi('help', 'помощь')} | "
                        f"{I18N.bidi('screen', 'экран')} <name>/<имя> | "
                        f"simulation.start/симуляция.старт"
                    ),
                    id="command-dock",
                )
                yield OrionKeybar(id="orion-keybar")

            with Container(id="screen-system"):
                with Container(id="system-dashboard"):
                    yield OrionPanel(id="panel-nav", classes="mfd-panel")
                    yield OrionPanel(id="panel-power", classes="mfd-panel")
                    yield OrionPanel(id="panel-thermal", classes="mfd-panel")
                    yield OrionPanel(id="panel-struct", classes="mfd-panel")

                with Container(id="screen-radar"):
                    with Horizontal(id="radar-layout"):
                        yield Static(id="radar-ppi")
                        radar_table: DataTable = DataTable(id="radar-table")
                        radar_table.add_columns(
                            I18N.bidi("Track", "Трек"),
                            I18N.bidi("Range (meters)", "Дальность (метры)"),
                            I18N.bidi("Bearing (degrees)", "Пеленг (градусы)"),
                            I18N.bidi("Radial velocity (meters per second)", "Радиальная скорость (метры в секунду)"),
                            I18N.bidi("Type", "Тип"),
                        )
                        yield radar_table

            with Container(id="screen-events"):
                events_table: DataTable = DataTable(id="events-table")
                events_table.add_columns(
                    I18N.bidi("Time", "Время"),
                    I18N.bidi("Severity", "Серьезность"),
                    I18N.bidi("Type", "Тип"),
                    I18N.bidi("Source", "Источник"),
                    I18N.bidi("Age", "Возраст"),
                    I18N.bidi("Subject", "Тема"),
                )
                yield events_table

            with Container(id="screen-console"):
                console_table: DataTable = DataTable(id="console-table")
                console_table.add_columns(
                    I18N.bidi("Time", "Время"),
                    I18N.bidi("Level", "Уровень"),
                    I18N.bidi("Message", "Сообщение"),
                )
                yield console_table

            with Container(id="screen-summary"):
                summary_table: DataTable = DataTable(id="summary-table")
                summary_table.add_column(I18N.bidi("Block", "Блок"), width=44)
                summary_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                summary_table.add_column(I18N.bidi("Value", "Значение"), width=30)
                summary_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                yield summary_table

            with Container(id="screen-power"):
                power_table: DataTable = DataTable(id="power-table")
                power_table.add_column(I18N.bidi("Component", "Компонент"), width=40)
                power_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                power_table.add_column(I18N.bidi("Value", "Значение"), width=24)
                power_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                power_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                yield power_table

            with Container(id="screen-diagnostics"):
                diagnostics_table: DataTable = DataTable(id="diagnostics-table")
                diagnostics_table.add_column(I18N.bidi("Block", "Блок"), width=46)
                diagnostics_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                diagnostics_table.add_column(I18N.bidi("Value", "Значение"), width=28)
                diagnostics_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                yield diagnostics_table

            with Container(id="screen-mission"):
                mission_table: DataTable = DataTable(id="mission-table")
                mission_table.add_column(I18N.bidi("Item", "Элемент"), width=34)
                mission_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                mission_table.add_column(I18N.bidi("Value", "Значение"), width=60)
                yield mission_table

    async def on_mount(self) -> None:
        self.action_show_screen("system")
        self._init_system_panels()
        self._seed_system_panels()
        self._seed_radar_table()
        self._seed_radar_ppi()
        self._seed_events_table()
        self._seed_console_table()
        self._seed_summary_table()
        self._seed_power_table()
        self._seed_diagnostics_table()
        self._seed_mission_table()
        self._update_system_snapshot()
        self._refresh_inspector()
        self._apply_responsive_chrome()
        await self._init_nats()
        self.set_interval(0.5, self._refresh_header)
        self.set_interval(1.0, self._refresh_radar)
        self.set_interval(1.0, self._refresh_summary)
        self.set_interval(1.0, self._refresh_diagnostics)
        self.set_interval(1.0, self._refresh_mission)
        try:
            self.set_focus(self.query_one("#command-dock", Input))
        except Exception:
            pass

    def on_resize(self) -> None:
        self._apply_responsive_chrome()

    def _apply_responsive_chrome(self) -> None:
        width = int(getattr(self.size, "width", 0) or 0)
        if width and width < 140:
            sidebar_width = 20
            inspector_width = 32
        elif width and width < 170:
            sidebar_width = 22
            inspector_width = 36
        else:
            sidebar_width = 28
            inspector_width = 44

        try:
            self.query_one("#orion-sidebar", OrionSidebar).styles.width = sidebar_width
        except Exception:
            pass
        try:
            self.query_one("#orion-inspector", OrionInspector).styles.width = inspector_width
        except Exception:
            pass

    def _console_log(self, msg: str, *, level: str = "info") -> None:
        try:
            table = self.query_one("#console-table", DataTable)
        except Exception:
            return

        ts = time.strftime("%H:%M:%S")
        key = f"con-{int(time.time() * 1000)}"
        try:
            if table.row_count == 1:
                table.clear()
        except Exception:
            pass

        normalized_level = self._normalize_level(level)
        level_label = self._level_label(normalized_level)

        try:
            table.add_row(ts, str(level_label), msg, key=key)
            self._console_by_key[key] = {
                "kind": "console",
                "timestamp": ts,
                "created_at_epoch": time.time(),
                "level": normalized_level,
                "message": msg,
            }
            if "console" not in self._selection_by_app:
                self._set_selection(
                    SelectionContext(
                        app_id="console",
                        key=key,
                        kind="console",
                        source="shell",
                        created_at_epoch=time.time(),
                        payload=self._console_by_key[key],
                        ids=(key,),
                    )
                )
            table.move_cursor(row=table.row_count - 1, column=0, animate=False, scroll=True)
        except Exception:
            pass

        if self.active_screen == "console":
            self._refresh_inspector()

    def _log_msg(self, msg: str) -> None:
        # Backwards-compatible name: shell logs go to Console/Консоль.
        self._console_log(msg, level="info")

    def _init_system_panels(self) -> None:
        for panel_id, title in (
            ("#panel-nav", I18N.bidi("Navigation", "Навигация")),
            ("#panel-power", I18N.bidi("Power", "Питание")),
            ("#panel-thermal", I18N.bidi("Thermal system", "Тепловая система")),
            ("#panel-struct", I18N.bidi("Structure and environment", "Корпус и среда")),
        ):
            try:
                panel = self.query_one(panel_id, Static)
            except Exception:
                continue
            panel.border_title = title

    def _seed_system_panels(self) -> None:
        updated = "—"
        self._render_system_panels({}, updated=updated)

    @staticmethod
    def _system_table(rows: list[tuple[str, str]]) -> Table:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=2, no_wrap=False, overflow="fold")
        table.add_column(justify="left", ratio=3, no_wrap=False, overflow="fold")
        for label, value in rows:
            table.add_row(label, value)
        return table

    def _render_system_panels(self, normalized: dict[str, Any], *, updated: str) -> None:
        def get(path: str) -> Any:
            cur: Any = normalized
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return None
                cur = cur[part]
            return cur

        def fmt_pos() -> str:
            x = get("position.x")
            y = get("position.y")
            z = get("position.z")
            if not all(isinstance(v, (int, float)) for v in (x, y, z)):
                return I18N.NA
            return (
                f"{round(float(x), 2)},{round(float(y), 2)},{round(float(z), 2)}"
                f"{I18N.bidi('m', 'м')}"
            )

        def fmt_att_deg(key: str) -> str:
            value = get(f"attitude.{key}")
            if not isinstance(value, (int, float)):
                return I18N.NA
            return I18N.num_unit(math.degrees(float(value)), "degrees", "градусы", digits=1)

        online = bool(self.nats_connected and self._snapshots.freshness("telemetry") == "fresh")
        age_value = I18N.fmt_age(self._snapshots.age_s("telemetry"))

        nav_rows = [
            (I18N.bidi("Link", "Связь"), I18N.online_offline(online)),
            (I18N.bidi("Updated", "Обновлено"), updated),
            (I18N.bidi("Age", "Возраст"), age_value),
            (I18N.bidi("Position", "Позиция"), fmt_pos()),
            (
                I18N.bidi("Velocity", "Скорость"),
                I18N.num_unit(get("velocity"), "meters per second", "метры в секунду", digits=2),
            ),
            (I18N.bidi("Heading", "Курс"), I18N.num_unit(get("heading"), "degrees", "градусы", digits=1)),
            (I18N.bidi("Roll", "Крен"), fmt_att_deg("roll_rad")),
            (I18N.bidi("Pitch", "Тангаж"), fmt_att_deg("pitch_rad")),
            (I18N.bidi("Yaw", "Рыскание"), fmt_att_deg("yaw_rad")),
        ]

        power_rows = [
            (I18N.bidi("Battery", "Батарея"), I18N.pct(get("battery"), digits=2)),
            (I18N.bidi("State of charge", "Уровень заряда"), I18N.pct(get("power.soc_pct"), digits=2)),
            (I18N.bidi("Power input", "Входная мощность"), I18N.num_unit(get("power.power_in_w"), "watts", "ватты", digits=1)),
            (I18N.bidi("Power output", "Выходная мощность"), I18N.num_unit(get("power.power_out_w"), "watts", "ватты", digits=1)),
            (I18N.bidi("Bus voltage", "Напряжение шины"), I18N.num_unit(get("power.bus_v"), "volts", "вольты", digits=2)),
            (I18N.bidi("Bus current", "Ток шины"), I18N.num_unit(get("power.bus_a"), "amperes", "амперы", digits=2)),
        ]

        def thermal_node(node_id: str) -> Any:
            nodes = get("thermal.nodes")
            if not isinstance(nodes, list):
                return None
            for node in nodes:
                if isinstance(node, dict) and node.get("id") == node_id:
                    return node.get("temp_c")
            return None

        thermal_rows = [
            (I18N.bidi("Core", "Ядро"), I18N.num_unit(thermal_node("core"), "°C", "°C", digits=1)),
            (I18N.bidi("Bus", "Шина"), I18N.num_unit(thermal_node("bus"), "°C", "°C", digits=1)),
            (I18N.bidi("Battery", "Батарея"), I18N.num_unit(thermal_node("battery"), "°C", "°C", digits=1)),
            (I18N.bidi("Radiator", "Радиатор"), I18N.num_unit(thermal_node("radiator"), "°C", "°C", digits=1)),
            (I18N.bidi("External temperature", "Наружная температура"), I18N.num_unit(get("temp_external_c"), "°C", "°C", digits=1)),
            (I18N.bidi("Core temperature", "Температура ядра"), I18N.num_unit(get("temp_core_c"), "°C", "°C", digits=1)),
        ]

        struct_rows = [
            (I18N.bidi("Hull integrity", "Целостность корпуса"), I18N.pct(get("hull.integrity"), digits=1)),
            (
                I18N.bidi("Radiation", "Радиация"),
                I18N.num_unit(get("radiation_usvh"), "microsieverts per hour", "микрозиверты в час", digits=2),
            ),
            (I18N.bidi("Central processing unit usage", "Загрузка центрального процессора"), I18N.pct(get("cpu_usage"), digits=1)),
            (I18N.bidi("Memory usage", "Загрузка памяти"), I18N.pct(get("memory_usage"), digits=1)),
        ]

        for panel_id, rows in (
            ("#panel-nav", nav_rows),
            ("#panel-power", power_rows),
            ("#panel-thermal", thermal_rows),
            ("#panel-struct", struct_rows),
        ):
            try:
                panel = self.query_one(panel_id, Static)
            except Exception:
                continue
            panel.update(self._system_table(rows))

    def _seed_radar_table(self) -> None:
        try:
            table = self.query_one("#radar-table", DataTable)
        except Exception:
            return
        self._selection_by_app.pop("radar", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NO_TRACKS_YET)

    def _seed_radar_ppi(self) -> None:
        try:
            ppi = self.query_one("#radar-ppi", Static)
        except Exception:
            return
        if self._ppi_renderer is None:
            ppi.update(I18N.bidi("Radar display unavailable", "Экран радара недоступен"))
            return
        ppi.update(self._ppi_renderer.render_tracks([]))

    def _seed_events_table(self) -> None:
        try:
            table = self.query_one("#events-table", DataTable)
        except Exception:
            return
        self._events_by_key = {}
        self._selection_by_app.pop("events", None)
        self._events_filter_type = None
        self._events_filter_text = None
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _seed_console_table(self) -> None:
        try:
            table = self.query_one("#console-table", DataTable)
        except Exception:
            return
        self._console_by_key = {}
        self._selection_by_app.pop("console", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, key="seed")

    def _seed_summary_table(self) -> None:
        try:
            table = self.query_one("#summary-table", DataTable)
        except Exception:
            return
        self._selection_by_app.pop("summary", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _seed_power_table(self) -> None:
        try:
            table = self.query_one("#power-table", DataTable)
        except Exception:
            return
        self._power_by_key = {}
        self._selection_by_app.pop("power", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _seed_diagnostics_table(self) -> None:
        try:
            table = self.query_one("#diagnostics-table", DataTable)
        except Exception:
            return
        self._diagnostics_by_key = {}
        self._selection_by_app.pop("diagnostics", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _seed_mission_table(self) -> None:
        try:
            table = self.query_one("#mission-table", DataTable)
        except Exception:
            return
        self._mission_by_key = {}
        self._selection_by_app.pop("mission", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, key="seed")

    async def _init_nats(self) -> None:
        self.nats_client = NATSClient()
        try:
            await self.nats_client.connect()
            self.nats_connected = True
            self._log_msg(f"✅ {I18N.bidi('NATS connected', 'NATS подключен')}")
            self._update_system_snapshot()
        except Exception as e:
            self.nats_connected = False
            self._log_msg(f"❌ {I18N.bidi('NATS connect failed', 'NATS не подключился')}: {e}")
            self._update_system_snapshot()
            return

        # Subscriptions are best-effort; missing streams shouldn't crash UI.
        try:
            await self.nats_client.subscribe_system_telemetry(self.handle_telemetry_data)
            self._log_msg(f"📈 {I18N.bidi('Subscribed', 'Подписка')}: qiki.telemetry")
        except Exception as e:
            self._log_msg(f"⚠️ {I18N.bidi('Telemetry subscribe failed', 'Подписка телеметрии не удалась')}: {e}")

        try:
            await self.nats_client.subscribe_tracks(self.handle_track_data)
            self._log_msg(f"📡 {I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('radar tracks', 'радар треки')}")
        except Exception as e:
            self._log_msg(
                f"⚠️ {I18N.bidi('Radar tracks subscribe failed', 'Подписка треков радара не удалась')}: {e}"
            )

        try:
            await self.nats_client.subscribe_events(self.handle_event_data)
            self._log_msg(f"🧾 {I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('events wildcard', 'события *')}")
        except Exception as e:
            self._log_msg(f"⚠️ {I18N.bidi('Events subscribe failed', 'Подписка событий не удалась')}: {e}")

        try:
            await self.nats_client.subscribe_control_responses(self.handle_control_response)
            self._log_msg(f"↩️ {I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('control responses', 'ответы управления')}")
        except Exception as e:
            self._log_msg(
                f"⚠️ {I18N.bidi('Control responses subscribe failed', 'Подписка ответов управления не удалась')}: {e}"
            )

    def _refresh_header(self) -> None:
        telemetry_env = self._snapshots.get_last("telemetry")
        if telemetry_env is None or not isinstance(telemetry_env.payload, dict):
            return
        try:
            header = self.query_one("#orion-header", OrionHeader)
            header.update_from_telemetry(
                telemetry_env.payload,
                nats_connected=self.nats_connected,
                telemetry_age_s=self._snapshots.age_s("telemetry"),
                telemetry_freshness_label=self._snapshots.freshness_label("telemetry"),
            )
        except Exception:
            return
        if self.active_screen == "system":
            self._refresh_inspector()

    def _refresh_inspector(self) -> None:
        try:
            inspector = self.query_one("#orion-inspector", OrionInspector)
        except Exception:
            return

        def app_title(screen: str) -> str:
            for app in ORION_APPS:
                if app.screen == screen:
                    return app.title
            return screen

        rows: list[tuple[str, str]] = [
            (I18N.bidi("Active", "Актив"), app_title(self.active_screen)),
            (I18N.bidi("NATS", "NATS"), I18N.yes_no(self.nats_connected) if isinstance(self.nats_connected, bool) else I18N.NA),
        ]

        telemetry_age_s = self._snapshots.age_s("telemetry")
        if telemetry_age_s is None:
            rows.append((I18N.bidi("Telemetry", "Телеметрия"), I18N.NA))
        else:
            rows.append((I18N.bidi("Telemetry age", "Возраст телеметрии"), I18N.fmt_age(telemetry_age_s)))

        ctx = self._selection_by_app.get(self.active_screen)
        if ctx is None:
            rows.append((I18N.bidi("Selection", "Выбор"), I18N.bidi("No selection", "Выбора нет")))
        else:
            age_s = time.time() - ctx.created_at_epoch
            freshness = self._fmt_age_s(age_s)
            if ctx.app_id == "radar":
                ttl = self._track_ttl_sec
                if ttl > 0 and isinstance(age_s, (int, float)) and age_s > ttl:
                    freshness = I18N.stale(freshness)
            mission_context = None
            if ctx.app_id == "mission":
                env = None
                for t in ("mission", "task"):
                    env = self._snapshots.get_last(t)
                    if env is not None:
                        break
                mission = {}
                if env is not None and isinstance(env.payload, dict):
                    payload = env.payload
                    mission = payload.get("mission") if isinstance(payload.get("mission"), dict) else payload
                designator = I18N.fmt_na(mission.get("designator") or mission.get("mission_id") or mission.get("id"))
                objective = I18N.fmt_na(mission.get("objective") or mission.get("goal") or mission.get("name"))
                priority = I18N.fmt_na(mission.get("priority") or mission.get("prio"))
                mission_context = f"{designator} — {objective} ({I18N.bidi('Priority', 'Приоритет')}: {priority})"

            detail_rows: list[tuple[str, str]] = [
                (I18N.bidi("Type", "Тип"), self._kind_label(ctx.kind)),
                (I18N.bidi("Source", "Источник"), self._source_label(ctx.source)),
                (I18N.bidi("Freshness", "Возраст"), freshness),
                (I18N.bidi("Key", "Ключ"), ctx.key or I18N.NA),
                (I18N.bidi("Identifier", "Идентификатор"), ", ".join(ctx.ids) if ctx.ids else I18N.NA),
                (
                    I18N.bidi("Timestamp", "Время"),
                    time.strftime("%H:%M:%S", time.localtime(ctx.created_at_epoch))
                    if isinstance(ctx.created_at_epoch, (int, float))
                    else I18N.NA,
                ),
            ]
            if ctx.app_id == "mission":
                detail_rows.append(
                    (
                        I18N.bidi("Mission context", "Контекст миссии"),
                        mission_context if mission_context is not None else I18N.NA,
                    )
                )
            detail_rows.append((I18N.bidi("Preview", "Превью"), OrionInspector.safe_preview(ctx.payload)))
            rows.extend(detail_rows)

        inspector.update(OrionInspector._table(rows))

    async def handle_telemetry_data(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return

        try:
            normalized = TelemetrySnapshotModel.normalize_payload(payload)
        except ValidationError as e:
            self._log_msg(f"⚠️ {I18N.bidi('Bad telemetry payload', 'Плохая телеметрия')}: {e}")
            return

        ts_unix_ms = normalized.get("ts_unix_ms")
        if isinstance(ts_unix_ms, int):
            ts_epoch = float(ts_unix_ms) / 1000.0
        else:
            ts_epoch = time.time()

        self.latest_telemetry = payload
        self._snapshots.put(
            EventEnvelope(
                event_id=f"telemetry-{int(ts_epoch * 1000)}",
                type="telemetry",
                source="telemetry",
                ts_epoch=ts_epoch,
                level="info",
                payload=payload,
                subject="qiki.telemetry",
            ),
            key="telemetry",
        )

        # Header refresh
        self._refresh_header()

        updated = time.strftime("%H:%M:%S")
        self._render_system_panels(normalized, updated=updated)
        self._render_power_table()
        self._render_diagnostics_table()
        self._refresh_summary()

    async def handle_track_data(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return

        updated = time.strftime("%H:%M:%S")
        track_id_raw = payload.get("track_id") or payload.get("trackId") or I18N.UNKNOWN
        track_id = str(track_id_raw)
        self._tracks_by_id[track_id] = (payload, time.time())
        if "radar" not in self._selection_by_app:
            self._set_selection(
                SelectionContext(
                    app_id="radar",
                    key=track_id,
                    kind="track",
                    source="radar",
                    created_at_epoch=self._tracks_by_id[track_id][1],
                    payload=payload,
                    ids=(track_id,),
                )
            )
        self._render_tracks_table()
        self._render_radar_ppi()
        if self.active_screen == "radar":
            self._refresh_inspector()
        self._log_msg(f"🎯 {I18N.bidi('Track update', 'Обновление трека')} ({updated}): {track_id}")

    async def handle_event_data(self, data: dict) -> None:
        if isinstance(data, dict):
            self._last_event = data
        subject = data.get("subject") if isinstance(data, dict) else None
        payload = data.get("data") if isinstance(data, dict) else None
        severity = None
        if isinstance(payload, dict):
            severity = payload.get("severity")

        normalized_level = self._normalize_level(severity)
        key = f"evt-{int(time.time() * 1000)}"
        ts_epoch = time.time()
        etype = self._derive_event_type(subject, payload)
        env = EventEnvelope(
            event_id=key,
            type=etype,
            source="nats",
            ts_epoch=ts_epoch,
            level=normalized_level,
            payload=payload,
            subject=str(subject or ""),
        )
        self._events_by_key[key] = {"envelope": env}
        self._snapshots.put(env)

        # Re-render under active filter and keep selection consistent.
        self._render_events_table()

        if self.active_screen == "events":
            self._refresh_inspector()
        if self.active_screen == "mission" and env.type in {"mission", "task"}:
            self._render_mission_table()
            self._refresh_inspector()
        if self.active_screen == "summary":
            self._render_summary_table()

    async def handle_control_response(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        success_raw = payload.get("success")
        if isinstance(success_raw, bool):
            success = I18N.yes_no(success_raw)
        elif success_raw is None:
            success = I18N.NA
        else:
            success = str(success_raw)

        request_id = payload.get("requestId") or payload.get("request_id")
        request = I18N.NA if request_id is None else str(request_id)
        message = None
        inner_payload = payload.get("payload")
        if isinstance(inner_payload, dict):
            message = inner_payload.get("status") or inner_payload.get("message")
        self._log_msg(
            f"↩️ {I18N.bidi('Control response', 'Ответ управления')}: "
            f"{I18N.bidi('success', 'успех')}={success} {I18N.bidi('request', 'запрос')}={request} {message or ''}".strip()
        )

    def action_show_screen(self, screen: str) -> None:
        if screen not in {app.screen for app in ORION_APPS}:
            self._log_msg(f"{I18N.bidi('Unknown screen', 'Неизвестный экран')}: {screen}")
            return
        self.active_screen = screen
        try:
            self.query_one("#orion-sidebar", OrionSidebar).set_active(screen)
        except Exception:
            pass
        for sid in ("system", "radar", "events", "console", "summary", "power", "diagnostics", "mission"):
            try:
                self.query_one(f"#screen-{sid}", Container).display = sid == screen
            except Exception:
                pass
        if screen == "events":
            self._render_events_table()
        if screen == "summary":
            self._render_summary_table()
        if screen == "power":
            self._render_power_table()
        if screen == "diagnostics":
            self._render_diagnostics_table()
        if screen == "mission":
            self._render_mission_table()
        self._refresh_inspector()

    def action_cycle_focus(self) -> None:
        """Cycle focus: Sidebar → Workspace → Inspector → Command."""

        def safe_query(selector: str) -> Optional[Static]:
            try:
                return self.query_one(selector)  # type: ignore[no-any-return]
            except Exception:
                return None

        sidebar = safe_query("#orion-sidebar")
        inspector = safe_query("#orion-inspector")
        command = safe_query("#command-dock")

        workspace: Optional[Static] = None
        if self.active_screen == "radar":
            workspace = safe_query("#radar-table")
        elif self.active_screen == "events":
            workspace = safe_query("#events-table")
        elif self.active_screen == "console":
            workspace = safe_query("#console-table")
        elif self.active_screen == "summary":
            workspace = safe_query("#summary-table")
        elif self.active_screen == "power":
            workspace = safe_query("#power-table")
        elif self.active_screen == "diagnostics":
            workspace = safe_query("#diagnostics-table")
        elif self.active_screen == "mission":
            workspace = safe_query("#mission-table")
        else:
            workspace = safe_query("#panel-nav")

        order = [w for w in (sidebar, workspace, inspector, command) if w is not None]
        if not order:
            return

        focused = self.focused
        try:
            idx = order.index(focused) if focused in order else -1
        except Exception:
            idx = -1
        target = order[(idx + 1) % len(order)]
        try:
            self.set_focus(target)
        except Exception:
            pass

    def action_help(self) -> None:
        self._show_help()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "events-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._events_by_key.get(row_key)
            if isinstance(selected, dict) and isinstance(selected.get("envelope"), EventEnvelope):
                env: EventEnvelope = selected["envelope"]
                self._set_selection(
                    SelectionContext(
                        app_id="events",
                        key=row_key,
                        kind="event",
                        source=env.source,
                        created_at_epoch=env.ts_epoch,
                        payload=env.payload,
                        ids=(env.subject or I18N.NA, env.type),
                    )
                )
            return

        if event.data_table.id == "console-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._console_by_key.get(row_key)
            if isinstance(selected, dict):
                self._set_selection(
                    SelectionContext(
                        app_id="console",
                        key=row_key,
                        kind="console",
                        source="shell",
                        created_at_epoch=float(selected.get("created_at_epoch") or time.time()),
                        payload=selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "summary-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._summary_by_key.get(row_key, {})
            created_at_epoch = time.time()
            env = selected.get("envelope")
            if isinstance(env, EventEnvelope):
                created_at_epoch = float(env.ts_epoch)
            self._set_selection(
                SelectionContext(
                    app_id="summary",
                    key=row_key,
                    kind="metric",
                    source="summary",
                    created_at_epoch=created_at_epoch,
                    payload=selected,
                    ids=(row_key,),
                )
            )
            return

        if event.data_table.id == "power-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._power_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="power",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "diagnostics-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._diagnostics_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="diagnostics",
                        key=row_key,
                        kind="metric",
                        source="diagnostics",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "mission-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._mission_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="mission",
                        key=row_key,
                        kind="metric",
                        source="nats",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id != "radar-table":
            return
        try:
            values = event.data_table.get_row_at(event.cursor_row)
        except Exception:
            return
        if not values:
            return
        track_id = str(values[0])
        if track_id == "—":
            return
        if track_id in self._tracks_by_id:
            payload, seen = self._tracks_by_id[track_id]
            self._set_selection(
                SelectionContext(
                    app_id="radar",
                    key=track_id,
                    kind="track",
                    source="radar",
                    created_at_epoch=float(seen),
                    payload=payload,
                    ids=(track_id,),
                )
            )

    @staticmethod
    def _normalize_screen_token(token: str) -> Optional[str]:
        key = (token or "").strip().lower()
        if not key:
            return None
        if key in SCREEN_BY_ALIAS:
            return SCREEN_BY_ALIAS[key]
        if key in {app.screen for app in ORION_APPS}:
            return key
        return None

    def _show_help(self) -> None:
        def display_aliases(app: OrionAppSpec) -> str:
            # Never show abbreviated aliases in UI help; keep the help readable and fully spelled out.
            # We rely on the convention that the first two aliases are the canonical EN/RU names.
            aliases = list(app.aliases[:2]) if app.aliases else []
            if not aliases:
                return I18N.NA
            return "|".join(aliases)

        apps = " | ".join(
            f"{app.hotkey_label} {app.title} ({display_aliases(app)})" for app in ORION_APPS
        )
        screens = ", ".join(app.screen for app in ORION_APPS)
        self._console_log(f"{I18N.bidi('Applications', 'Приложения')}: {apps}", level="info")
        self._console_log(
            f"{I18N.bidi('Commands', 'Команды')}: "
            f"help/помощь | screen/экран <{screens}> | {I18N.bidi('or type a screen alias', 'или введите алиас экрана')}"
            ,
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Simulation', 'Симуляция')}: "
            f"simulation.start/симуляция.старт | simulation.pause/симуляция.пауза | simulation.stop/симуляция.стоп | simulation.reset/симуляция.сброс",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Filters', 'Фильтры')}: type <name> | type off | filter <text> | filter off",
            level="info",
        )

    async def _run_command(self, raw: str) -> None:
        cmd = (raw or "").strip()
        if not cmd:
            return

        low = cmd.lower()
        if low in {"help", "помощь", "?", "h"}:
            self._show_help()
            return

        # type <name> | type off
        if low == "type" or low.startswith("type "):
            _, _, tail = cmd.partition(" ")
            token = tail.strip().lower()
            if not token:
                current = self._events_filter_type or I18N.NA
                self._console_log(f"{I18N.bidi('Events type filter', 'Фильтр событий по типу')}: {current}", level="info")
                return
            if token in {"off", "none", "all", "*"}:
                self._events_filter_type = None
                self._console_log(
                    f"{I18N.bidi('Events type filter cleared', 'Фильтр событий по типу снят')}",
                    level="info",
                )
                self._update_system_snapshot()
                self._render_events_table()
                if self.active_screen == "summary":
                    self._render_summary_table()
                if self.active_screen == "diagnostics":
                    self._render_diagnostics_table()
                return
            self._events_filter_type = token
            self._console_log(f"{I18N.bidi('Events type filter', 'Фильтр событий по типу')}: {token}", level="info")
            self._update_system_snapshot()
            self._render_events_table()
            if self.active_screen == "summary":
                self._render_summary_table()
            if self.active_screen == "diagnostics":
                self._render_diagnostics_table()
            return

        # filter <text> | filter off | filter type=<name>
        if low == "filter" or low.startswith("filter "):
            if low == "filter":
                self._events_filter_text = None
                self._console_log(
                    f"{I18N.bidi('Events text filter cleared', 'Фильтр событий по тексту снят')}",
                    level="info",
                )
                self._update_system_snapshot()
                self._render_events_table()
                if self.active_screen == "summary":
                    self._render_summary_table()
                if self.active_screen == "diagnostics":
                    self._render_diagnostics_table()
                return
            _, _, tail = cmd.partition(" ")
            expr = tail.strip()
            if not expr:
                current = self._events_filter_text or I18N.NA
                self._console_log(f"{I18N.bidi('Events text filter', 'Фильтр событий по тексту')}: {current}", level="info")
                return
            if expr.lower().startswith("type="):
                token = expr.split("=", 1)[1].strip().lower()
                if token in {"off", "none", "all", "*", ""}:
                    self._events_filter_type = None
                    self._console_log(
                        f"{I18N.bidi('Events type filter cleared', 'Фильтр событий по типу снят')}",
                        level="info",
                    )
                else:
                    self._events_filter_type = token
                    self._console_log(f"{I18N.bidi('Events type filter', 'Фильтр событий по типу')}: {token}", level="info")
                self._update_system_snapshot()
                self._render_events_table()
                if self.active_screen == "summary":
                    self._render_summary_table()
                if self.active_screen == "diagnostics":
                    self._render_diagnostics_table()
                return
            token = expr.strip()
            if token.lower() in {"off", "none", "all", "*"}:
                self._events_filter_text = None
                self._console_log(
                    f"{I18N.bidi('Events text filter cleared', 'Фильтр событий по тексту снят')}",
                    level="info",
                )
            else:
                self._events_filter_text = token
                self._console_log(
                    f"{I18N.bidi('Events text filter', 'Фильтр событий по тексту')}: {token}",
                    level="info",
                )
            self._update_system_snapshot()
            self._render_events_table()
            if self.active_screen == "summary":
                self._render_summary_table()
            if self.active_screen == "diagnostics":
                self._render_diagnostics_table()
            return

        # screen/экран <name>
        if low.startswith("screen ") or low.startswith("экран "):
            _, _, tail = cmd.partition(" ")
            token = tail.strip()
            screen = self._normalize_screen_token(token)
            if screen is None:
                self._log_msg(f"{I18N.bidi('Unknown screen', 'Неизвестный экран')}: {token or I18N.NA}")
                return
            self.action_show_screen(screen)
            return

        # Allow bare screen aliases: "system" / "система" / "radar" / ...
        if (screen := self._normalize_screen_token(low)) is not None:
            self.action_show_screen(screen)
            return

        if (sim_cmd := self._canonicalize_sim_command(low)) is not None:
            await self._publish_sim_command(sim_cmd)
            return

        self._log_msg(f"{I18N.bidi('Unknown command', 'Неизвестная команда')}: {cmd}")

    @staticmethod
    def _canonicalize_sim_command(cmd: str) -> Optional[str]:
        key = (cmd or "").strip().lower()
        mapping = {
            "sim.start": "sim.start",
            "sim.pause": "sim.pause",
            "sim.stop": "sim.stop",
            "sim.reset": "sim.reset",
            "simulation.start": "sim.start",
            "simulation.pause": "sim.pause",
            "simulation.stop": "sim.stop",
            "simulation.reset": "sim.reset",
            "симуляция.старт": "sim.start",
            "симуляция.пауза": "sim.pause",
            "симуляция.стоп": "sim.stop",
            "симуляция.сброс": "sim.reset",
        }
        return mapping.get(key)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-dock":
            return

        raw = (event.value or "").strip()
        event.input.value = ""
        if not raw:
            return

        await self._run_command(raw)

    async def _publish_sim_command(self, cmd_name: str) -> None:
        if not self.nats_client:
            self._log_msg(f"❌ {I18N.bidi('NATS not initialized', 'NATS не инициализирован')}")
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
            self._log_msg(f"📤 {I18N.bidi('Published', 'Отправлено')}: {cmd_name}")
        except Exception as e:
            self._log_msg(f"❌ {I18N.bidi('Publish failed', 'Отправка не удалась')}: {e}")


if __name__ == "__main__":
    OrionApp().run()
