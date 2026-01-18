from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import asdict
import json
import math
import os
import time
from typing import Any, Optional

from pydantic import ValidationError
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, RichLog, Static

from qiki.services.operator_console.clients.nats_client import NATSClient
from qiki.services.operator_console.core.incident_rules import FileRulesRepository
from qiki.services.operator_console.core.incidents import IncidentStore
from qiki.services.operator_console.ui import i18n as I18N
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel
from qiki.shared.nats_subjects import COMMANDS_CONTROL, QIKI_INTENTS

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


class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    #confirm-dialog {
        width: 72;
        padding: 1 2;
        border: round #ffb000;
        background: #050505;
    }
    #confirm-prompt {
        padding: 0 0 1 0;
        color: #ffffff;
    }
    #confirm-actions {
        height: 3;
        align: center middle;
    }
    #confirm-actions Button {
        margin: 0 1;
        width: 16;
    }
    """

    BINDINGS = [
        Binding("y", "confirm_yes", "Yes/Да", show=False),
        Binding("n", "confirm_no", "No/Нет", show=False),
        Binding("enter", "confirm_yes", "Yes/Да", show=False),
        Binding("escape", "confirm_no", "No/Нет", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Static(self._prompt, id="confirm-prompt")
            with Horizontal(id="confirm-actions"):
                yield Button(I18N.bidi("Yes", "Да"), id="confirm-yes")
                yield Button(I18N.bidi("No", "Нет"), id="confirm-no")

    def action_confirm_yes(self) -> None:
        self.dismiss(True)

    def action_confirm_no(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        elif event.button.id == "confirm-no":
            self.dismiss(False)


class BootLog(Static):
    """Boot log with sequential line output (no-mocks: statuses only when proven)."""

    def __init__(self, *, id: str) -> None:
        super().__init__(id=id)
        self._text = Text()

    def clear(self) -> None:
        self._text = Text()
        self.update(self._text)

    def add_line(self, line: str, *, style: str = "green") -> None:
        if self._text.plain:
            self._text.append("\n")
        self._text.append(str(line), style=style)
        self.update(self._text)


class BootScreen(ModalScreen[bool]):
    """Cold-boot splash + BIOS POST visualization (no-mocks)."""

    DEFAULT_CSS = """
    BootScreen {
        align: center middle;
        background: #050505;
    }
    #boot-container {
        width: 1fr;
        max-width: 84;
        min-width: 44;
        height: auto;
        border: double #ffb000;
        padding: 1 2;
        background: #000000;
    }
    #boot-header {
        text-align: center;
        color: #ffb000;
        text-style: bold;
        margin-bottom: 1;
    }
    #boot-hint {
        color: #a0a0a0;
        margin-bottom: 1;
    }
    BootLog {
        height: 1fr;
        min-height: 10;
        color: #00ff66;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._task: Optional[asyncio.Task[None]] = None

    def compose(self) -> ComposeResult:
        with Container(id="boot-container"):
            yield Static("QIKI ORION OS — Cold Boot [BIOS]", id="boot-header")
            yield Static(I18N.bidi("Press Ctrl+C to exit", "Ctrl+C — выход"), id="boot-hint")
            yield BootLog(id="boot-log")

    def on_mount(self) -> None:
        log = self.query_one("#boot-log", BootLog)
        log.clear()
        self._task = asyncio.create_task(self._run())

    def on_unmount(self) -> None:
        if self._task is not None:
            try:
                self._task.cancel()
            except Exception:
                pass

    async def _sleep_chunked(self, seconds: float) -> None:
        # Keep UI responsive.
        remaining = max(0.0, float(seconds))
        while remaining > 0:
            step = min(0.1, remaining)
            await asyncio.sleep(step)
            remaining -= step

    async def _run(self) -> None:
        log = self.query_one("#boot-log", BootLog)

        # Phase 0: cosmetic boot (no statuses, no percentages).
        cosmetic_sec = float(os.getenv("ORION_BOOT_COSMETIC_SEC", "2.0"))
        cosmetic_sec = max(0.0, min(30.0, cosmetic_sec))
        lines = [
            I18N.bidi("INIT: Allocating terminal buffers...", "INIT: Выделение буферов терминала..."),
            I18N.bidi("CORE: Loading ORION UI modules...", "CORE: Загрузка модулей ORION UI..."),
            I18N.bidi("TDE: Rendering console chrome...", "TDE: Отрисовка интерфейса..."),
        ]
        per_line = cosmetic_sec / max(1, len(lines))
        for line in lines:
            log.add_line(line, style="dim green")
            await self._sleep_chunked(per_line)

        # Phase 1: NATS (real).
        log.add_line(I18N.bidi("NET: Connecting to NATS bus...", "NET: Подключение к шине NATS..."), style="yellow")
        nats_timeout = float(os.getenv("ORION_BOOT_NATS_TIMEOUT_SEC", "8.0"))
        nats_timeout = max(0.5, min(60.0, nats_timeout))

        start = time.time()
        app = self.app  # type: ignore[assignment]
        while time.time() - start < nats_timeout:
            # _boot_nats_init_done is set by OrionApp._init_nats.
            done = bool(getattr(app, "_boot_nats_init_done", False))
            if done:
                break
            await self._sleep_chunked(0.1)

        nats_ok = bool(getattr(app, "nats_connected", False))
        if nats_ok:
            log.add_line(I18N.bidi("NET: NATS connected [OK]", "NET: NATS подключен [OK]"), style="bold green")
        else:
            err = str(getattr(app, "_boot_nats_error", "") or "").strip()
            tail = f": {err}" if err else ""
            log.add_line(I18N.bidi(f"NET: NATS connect failed [FAIL]{tail}", f"NET: NATS не подключился [СБОЙ]{tail}"), style="bold red")

        # Phase 2: BIOS event (real, from NATS).
        log.add_line(
            I18N.bidi("BIOS: Waiting for POST status event...", "BIOS: Ожидание события статуса POST..."),
            style="yellow",
        )
        bios_timeout = float(os.getenv("ORION_BOOT_BIOS_TIMEOUT_SEC", "12.0"))
        bios_timeout = max(0.5, min(120.0, bios_timeout))
        bios_env = None
        start = time.time()
        while time.time() - start < bios_timeout:
            try:
                bios_env = getattr(app, "_snapshots").get_last("bios")
            except Exception:
                bios_env = None
            if bios_env is not None:
                break
            await self._sleep_chunked(0.2)

        payload = getattr(bios_env, "payload", None) if bios_env is not None else None
        if isinstance(payload, dict):
            all_go = payload.get("all_systems_go")
            post = payload.get("post_results") if isinstance(payload.get("post_results"), list) else []
            if isinstance(all_go, bool):
                if all_go:
                    log.add_line(
                        I18N.bidi(f"BIOS: POST complete [OK] (devices: {len(post)})", f"BIOS: POST завершён [OK] (устройств: {len(post)})"),
                        style="bold green",
                    )
                else:
                    log.add_line(
                        I18N.bidi(f"BIOS: POST complete [FAIL] (devices: {len(post)})", f"BIOS: POST завершён [СБОЙ] (устройств: {len(post)})"),
                        style="bold red",
                    )
            else:
                log.add_line(I18N.bidi("BIOS: POST status unknown", "BIOS: Статус POST неизвестен"), style="yellow")

            # Row-by-row visualization (real data).
            # Keep it readable: show non-OK first, then a limited number of OK rows.
            max_rows = int(os.getenv("ORION_BOOT_POST_MAX_ROWS", "30"))
            max_rows = max(5, min(200, max_rows))
            line_delay = float(os.getenv("ORION_BOOT_POST_LINE_DELAY_SEC", "0.02"))
            line_delay = max(0.0, min(0.5, line_delay))

            bad: list[dict[str, Any]] = []
            ok: list[dict[str, Any]] = []
            for row in post:
                if not isinstance(row, dict):
                    continue
                status = row.get("status")
                if status == 1:
                    ok.append(row)
                else:
                    bad.append(row)

            shown: list[dict[str, Any]] = []
            shown.extend(bad[:max_rows])
            if len(shown) < max_rows:
                shown.extend(ok[: max_rows - len(shown)])

            for row in shown:
                if not isinstance(row, dict):
                    continue
                did = str(row.get("device_id") or row.get("deviceId") or "").strip() or I18N.UNKNOWN
                dname = str(row.get("device_name") or row.get("deviceName") or "").strip() or I18N.UNKNOWN
                status = row.get("status")
                msg = str(row.get("status_message") or row.get("statusMessage") or "").strip()
                label = "N/A"
                style = "dim"
                if status == 1:
                    label, style = "OK", "green"
                elif status == 2:
                    label, style = "DEGRADED", "yellow"
                elif status == 3:
                    label, style = "ERROR", "red"
                suffix = f" — {msg}" if msg else ""
                log.add_line(f"{did} ({dname}): {label}{suffix}", style=style)
                if line_delay:
                    await self._sleep_chunked(line_delay)

            remaining = len(post) - len(shown)
            if remaining > 0:
                log.add_line(
                    I18N.bidi(
                        f"… ({remaining} more devices not shown)",
                        f"… (ещё устройств не показано: {remaining})",
                    ),
                    style="dim",
                )
        else:
            # No-mocks: no fake OK. Show N/A and proceed.
            log.add_line(I18N.bidi("BIOS: No data (N/A)", "BIOS: Нет данных (N/A)"), style="yellow")

        log.add_line(I18N.bidi("HANDOVER: Switching to operator view...", "ПЕРЕДАЧА: Переход в режим оператора..."), style="dim")
        await self._sleep_chunked(0.4)
        self.dismiss(True)


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
            return I18N.bidi("Fresh", "Свежо")
        if f == "stale":
            return I18N.bidi("Stale", "Устарело")
        return I18N.bidi("Dead", "Нет обновлений")


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
        screen="sensors",
        title=I18N.bidi("Sensors", "Сенсоры"),
        hotkey="ctrl+n",
        hotkey_label="Ctrl+N",
        aliases=("sensors", "сенсоры", "sensor", "сенсор", "imu", "иму"),
    ),
    OrionAppSpec(
        screen="propulsion",
        title=I18N.bidi("Propulsion", "Двигатели"),
        hotkey="ctrl+p",
        hotkey_label="Ctrl+P",
        aliases=("propulsion", "двигатели", "rcs", "рдс", "prop", "двиг"),
    ),
    OrionAppSpec(
        screen="thermal",
        title=I18N.bidi("Thermal", "Тепло"),
        hotkey="ctrl+t",
        hotkey_label="Ctrl+T",
        aliases=("thermal", "тепло", "temps", "темп", "temperature", "температура"),
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
    OrionAppSpec(
        screen="rules",
        title=I18N.bidi("Rules", "Правила"),
        hotkey="ctrl+r",
        hotkey_label="Ctrl+R",
        aliases=("rules", "правила", "rule", "правило"),
    ),
)

ORION_MENU_LABELS: dict[str, str] = {
    "system": I18N.bidi("Sys", "Систем"),
    "radar": I18N.bidi("Radar", "Радар"),
    "events": I18N.bidi("Events", "Событ"),
    "console": I18N.bidi("Console", "Консоль"),
    "summary": I18N.bidi("Summary", "Сводка"),
    "power": I18N.bidi("Power", "Пит"),
    "sensors": I18N.bidi("Sens", "Сенс"),
    "propulsion": I18N.bidi("Prop", "Двиг"),
    "thermal": I18N.bidi("Therm", "Тепло"),
    "diagnostics": I18N.bidi("Diag", "Диагн"),
    "mission": I18N.bidi("Mission", "Миссия"),
    "rules": I18N.bidi("Rules", "Прав"),
}

# Sidebar labels must stay readable without truncation (no abbreviations by default).
# Keep them short-but-clear; full long titles remain available in other chrome/help.
ORION_SIDEBAR_LABELS: dict[str, str] = {
    "system": I18N.bidi("System", "Система"),
    "radar": I18N.bidi("Radar", "Радар"),
    "events": I18N.bidi("Events", "События"),
    "console": I18N.bidi("Console", "Консоль"),
    "summary": I18N.bidi("Summary", "Сводка"),
    "power": I18N.bidi("Power", "Питание"),
    "sensors": I18N.bidi("Sensors", "Сенсоры"),
    "propulsion": I18N.bidi("Propulsion", "Двигатели"),
    "thermal": I18N.bidi("Thermal", "Тепло"),
    "diagnostics": I18N.bidi("Diagnostics", "Диагностика"),
    "mission": I18N.bidi("Mission", "Миссия"),
    "rules": I18N.bidi("Rules", "Правила"),
}

# Narrow/tiny sidebar: keep it readable without abbreviations by dropping the English part.
ORION_SIDEBAR_LABELS_NARROW: dict[str, str] = {
    "system": "Система",
    "radar": "Радар",
    "events": "События",
    "console": "Консоль",
    "summary": "Сводка",
    "power": "Питание",
    "sensors": "Сенсоры",
    "propulsion": "Двигатели",
    "thermal": "Тепло",
    "diagnostics": "Диагностика",
    "mission": "Миссия",
    "rules": "Правила",
}


def menu_label(app: OrionAppSpec) -> str:
    return ORION_MENU_LABELS.get(app.screen, app.title)

def menu_label_for_density(app: OrionAppSpec, *, density: str | None) -> str:
    # Full titles are readable on wide screens; on narrow/tiny prefer compact labels.
    d = (density or "").strip().lower()
    if d in {"wide", "normal"}:
        return app.title
    return menu_label(app)


SCREEN_BY_ALIAS: dict[str, str] = {a: app.screen for app in ORION_APPS for a in app.aliases}


class OrionHeaderCell(Static):
    """One compact header field with an optional tooltip (scalable)."""

    can_focus = False

    def __init__(self, *, id: str) -> None:
        super().__init__(id=id)
        self._value: str = ""

    def set_value(self, value: str, *, tooltip: str) -> None:
        self._value = value
        self.tooltip = tooltip
        self.refresh()

    def render(self) -> Text:
        return Text(self._value, no_wrap=True, overflow="ellipsis")


class OrionHeader(Container):
    """Top status bar for ORION (no-mocks, scalable)."""

    can_focus = False

    online = reactive(False)
    battery = reactive(I18N.NA)
    hull = reactive(I18N.NA)
    rad = reactive(I18N.NA)
    t_ext = reactive(I18N.NA)
    t_core = reactive(I18N.NA)
    age = reactive(I18N.NA)
    freshness = reactive(I18N.NA)

    def compose(self) -> ComposeResult:
        with Container(id="orion-header-grid"):
            yield OrionHeaderCell(id="hdr-online")
            yield OrionHeaderCell(id="hdr-battery")
            yield OrionHeaderCell(id="hdr-hull")
            yield OrionHeaderCell(id="hdr-radiation")
            yield OrionHeaderCell(id="hdr-t-ext")
            yield OrionHeaderCell(id="hdr-t-core")
            yield OrionHeaderCell(id="hdr-age")
            yield OrionHeaderCell(id="hdr-freshness")

    def _refresh_cells(self) -> None:
        def set_cell(cell_id: str, value: str, tooltip: str) -> None:
            try:
                self.query_one(f"#{cell_id}", OrionHeaderCell).set_value(value, tooltip=tooltip)
            except Exception:
                return

        online_value = I18N.online_offline(self.online)
        set_cell(
            "hdr-online",
            f"{I18N.bidi('Link', 'Связь')} {online_value}",
            tooltip=f"{I18N.bidi('Link status', 'Состояние связи')}: {online_value}",
        )
        set_cell(
            "hdr-battery",
            f"{I18N.bidi('Bat', 'Бат')} {self.battery}",
            tooltip=f"{I18N.bidi('Battery level', 'Уровень батареи')}: {self.battery}",
        )
        set_cell(
            "hdr-hull",
            f"{I18N.bidi('Hull', 'Корпус')} {self.hull}",
            tooltip=f"{I18N.bidi('Hull integrity', 'Целостность корпуса')}: {self.hull}",
        )
        set_cell(
            "hdr-radiation",
            f"{I18N.bidi('Rad', 'Рад')} {self.rad}",
            tooltip=f"{I18N.bidi('Radiation dose rate', 'Мощность дозы радиации')}: {self.rad}",
        )
        set_cell(
            "hdr-t-ext",
            f"{I18N.bidi('Ext temp', 'Нар темп')} {self.t_ext}",
            tooltip=f"{I18N.bidi('External temperature', 'Наружная температура')}: {self.t_ext}",
        )
        set_cell(
            "hdr-t-core",
            f"{I18N.bidi('Core temp', 'Темп ядра')} {self.t_core}",
            tooltip=f"{I18N.bidi('Core temperature', 'Температура ядра')}: {self.t_core}",
        )
        set_cell(
            "hdr-age",
            f"{I18N.bidi('Age', 'Возраст')} {self.age}",
            tooltip=f"{I18N.bidi('Telemetry age', 'Возраст телеметрии')}: {self.age}",
        )
        set_cell(
            "hdr-freshness",
            f"{I18N.bidi('Fresh', 'Свеж')} {self.freshness}",
            tooltip=f"{I18N.bidi('Freshness', 'Свежесть')}: {self.freshness}",
        )

    def update_from_telemetry(
        self,
        payload: dict[str, Any],
        *,
        nats_connected: bool,
        telemetry_age_s: Optional[float],
        telemetry_freshness_label: str,
        telemetry_freshness_kind: Optional[str],
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
            "µSv/h",
            "мкЗв/ч",
            digits=2,
        )
        self.t_ext = I18N.num_unit(normalized.get("temp_external_c"), "°C", "°C", digits=1)
        self.t_core = I18N.num_unit(normalized.get("temp_core_c"), "°C", "°C", digits=1)
        self.age = I18N.fmt_age_compact(telemetry_age_s)
        self.freshness = telemetry_freshness_label

        # Online is a function of connectivity + freshness (no magic).
        self.online = bool(nats_connected and telemetry_freshness_kind == "fresh")
        self._refresh_cells()


class OrionSidebar(Static):
    can_focus = True
    active_screen = reactive("system")

    def set_active(self, screen: str) -> None:
        self.active_screen = screen
        self.refresh()

    @staticmethod
    def _line(label: str, *, active: bool) -> str:
        mark = "▶" if active else " "
        return f"{mark} [{label}]"

    def render(self) -> str:
        orion = getattr(self, "app", None)
        density = getattr(orion, "_density", None)

        def fit(text: str, max_width: int) -> str:
            if max_width <= 0:
                return text
            if len(text) <= max_width:
                return text
            if max_width <= 1:
                return "…"
            return f"{text[: max_width - 1]}…"

        def sidebar_label(app: OrionAppSpec) -> str:
            # Sidebar must stay readable in tmux: prefer Russian-only full words.
            return ORION_SIDEBAR_LABELS_NARROW.get(app.screen) or ORION_SIDEBAR_LABELS.get(
                app.screen, menu_label_for_density(app, density=density)
            )

        def title_with_state(app: OrionAppSpec) -> str:
            base = sidebar_label(app)
            if app.screen != "events":
                return base
            live = bool(getattr(orion, "_events_live", True))
            unread = int(getattr(orion, "_events_unread_count", 0) or 0)
            suffix: list[str] = []
            if not live:
                suffix.append(I18N.bidi("Paused", "Пауза"))
            if unread > 0:
                suffix.append(f"{unread} {I18N.bidi('Unread', 'Непрочитано')}")
            if not suffix:
                return base
            return f"{base} ({', '.join(suffix)})"

        width = int(getattr(self.size, "width", 0) or 0)
        usable = max(0, width - 1) if width else 0

        lines: list[str] = [
            fit(I18N.bidi("ORION SHELL", "ORION ОБОЛОЧКА"), usable),
            "—" * (usable or 18),
        ]

        for app in ORION_APPS:
            active = self.active_screen == app.screen
            mark = "▶" if active else " "
            label = title_with_state(app)
            line = f"{mark} {app.hotkey_label} {label}"
            lines.append(fit(line, usable))

        def sidebar_help_lines() -> list[str]:
            # Keep the sidebar stable in narrow tmux panes: no long bilingual phrases here.
            if density in {"tiny", "narrow"}:
                return [
                    fit("Tab фокус", usable),
                    fit("Enter команда", usable),
                    fit("Ctrl+C выход", usable),
                ]
            return [
                fit(f"{I18N.bidi('Tab', 'Табуляция')} {I18N.bidi('Focus', 'Фокус')}", usable),
                fit(f"{I18N.bidi('Enter', 'Ввод')} {I18N.bidi('Command', 'Команда')}", usable),
                fit(f"{I18N.bidi('Ctrl+C', 'Ctrl+C')} {I18N.bidi('Quit', 'Выход')}", usable),
            ]

        lines.extend(["", *sidebar_help_lines()])
        return "\n".join(lines)


class OrionKeybar(Static):
    def render(self) -> str:
        orion = getattr(self, "app", None)
        density = getattr(orion, "_density", "wide")
        active_screen = getattr(self.app, "active_screen", "system")
        width = int(getattr(self.size, "width", 0) or 0)

        label_density = density if width >= 200 else "narrow"

        def keybar_label(app: OrionAppSpec) -> str:
            if label_density in {"tiny", "narrow"}:
                return ORION_SIDEBAR_LABELS_NARROW.get(app.screen) or ORION_SIDEBAR_LABELS.get(
                    app.screen, menu_label_for_density(app, density="narrow")
                )
            return menu_label_for_density(app, density=label_density)

        def desired_screens(max_width: int) -> list[str]:
            if max_width and max_width < 90:
                return ["system", "events", "console", "sensors"]
            if max_width and max_width < 120:
                return ["system", "radar", "events", "console", "sensors", "power"]
            if max_width and max_width < 160:
                return [
                    "system",
                    "radar",
                    "events",
                    "console",
                    "summary",
                    "power",
                    "sensors",
                    "propulsion",
                    "thermal",
                    "diagnostics",
                ]
            return [app.screen for app in ORION_APPS]

        screens = desired_screens(width)
        if active_screen not in screens:
            screens.append(active_screen)

        apps_by_screen = {app.screen: app for app in ORION_APPS}
        nav_apps = [apps_by_screen[s] for s in screens if s in apps_by_screen]

        nav_tokens: list[str] = []
        for app in nav_apps:
            label = keybar_label(app)
            if app.screen == active_screen:
                nav_tokens.append(f"▶{app.hotkey_label} {label}")
            else:
                nav_tokens.append(f"{app.hotkey_label} {label}")

        help_token = f"F9 {I18N.bidi('Help', 'Помощь')}"
        quit_token = f"F10 {I18N.bidi('Quit', 'Выход')}"

        sep = " · "

        def joined(tokens: list[str]) -> str:
            return sep.join(tokens)

        def fit_tokens(tokens: list[str], max_width: int) -> str:
            if not max_width:
                return joined(tokens)
            if max_width <= 1:
                return "…"
            text = joined(tokens)
            if len(text) <= max_width:
                return text
            return text[: max_width - 1] + "…"

        # Ensure Help/Quit are always visible: drop nav tokens from the end until it fits.
        tokens = nav_tokens + [help_token, quit_token]
        if width:
            while len(nav_tokens) > 0 and len(joined(tokens)) > width:
                nav_tokens.pop()
                tokens = nav_tokens + [help_token, quit_token]

        return fit_tokens(tokens, width)


class OrionPanel(Static):
    can_focus = True


class OrionInspector(Static):
    """Right-side detail pane (no-mocks)."""

    can_focus = True

    @staticmethod
    def _table(rows: list[tuple[str, str]]) -> Table:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="left", ratio=2, no_wrap=True, overflow="ellipsis")
        table.add_column(justify="left", ratio=3, no_wrap=False, overflow="fold")
        for label, value in rows:
            table.add_row(label, value)
        return table

    @staticmethod
    def safe_preview(value: Any, *, max_chars: int = 1024, max_lines: int = 24) -> str:
        try:
            max_chars = int(os.getenv("OPERATOR_CONSOLE_PREVIEW_MAX_CHARS", str(max_chars)))
        except Exception:
            max_chars = 1024
        try:
            max_lines = int(os.getenv("OPERATOR_CONSOLE_PREVIEW_MAX_LINES", str(max_lines)))
        except Exception:
            max_lines = 24
        max_chars = max(32, min(16_384, max_chars))
        max_lines = max(4, min(200, max_lines))
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
    #orion-workspace { height: 1fr; }
    #orion-header { dock: top; height: 2; overflow: hidden; padding: 0 1; color: #ffb000; background: #050505; }
    #orion-header-grid { layout: grid; grid-size: 4 2; grid-gutter: 0 2; }
    #orion-header-grid.header-2x4 { grid-size: 2 4; grid-gutter: 0 2; }
    #orion-sidebar { dock: left; width: 28; border: round #303030; padding: 1; color: #e0e0e0; background: #050505; }
    #bottom-bar { dock: bottom; height: 12; }
    #command-output-log { height: 8; padding: 0 1; color: #e0e0e0; background: #050505; border: round #303030; }
    #command-dock { height: 3; padding: 0 1; width: 1fr; color: #e0e0e0; background: #101010; border: round #303030; }
    #command-dock:focus { border: round #ffb000; background: #101010; color: #ffffff; }
    #command-dock { overflow: hidden; }
    Input { color: #e0e0e0; background: #101010; overflow: hidden; }
    Input:focus { color: #ffffff; background: #101010; }
    #orion-keybar { height: 1; color: #a0a0a0; background: #050505; }
    #system-dashboard { layout: grid; grid-size: 2 2; grid-gutter: 1 1; }
    #system-dashboard.dashboard-1x4 { grid-size: 1 4; grid-gutter: 1 1; }
    .mfd-panel { border: round #303030; padding: 0 1; color: #e0e0e0; background: #050505; }
    #radar-layout { height: 1fr; }
    #radar-ppi { width: 47; height: 25; color: #00ff66; background: #050505; }
    #radar-table { width: 1fr; }
    #orion-inspector { dock: right; width: 44; border: round #303030; padding: 1; color: #e0e0e0; background: #050505; }
    #events-table { height: 1fr; }
    #console-table { height: 1fr; }
    #summary-table { height: 1fr; }
    #power-table { height: 1fr; }
    #sensors-table { height: 1fr; }
    #propulsion-table { height: 1fr; }
    #thermal-table { height: 1fr; }
    #diagnostics-table { height: 1fr; }
    #mission-table { height: 1fr; }
    #rules-toolbar { height: 3; padding: 0 1; border: round #303030; background: #050505; }
    #rules-hint { padding: 0 1; color: #a0a0a0; background: #050505; }
    #rules-toggle-hint { padding: 0 1; color: #a0a0a0; background: #050505; }
    #rules-reload { width: 22; }
    #rules-table { height: 1fr; }
    """

    BINDINGS = [
        *(Binding(app.hotkey, f"show_screen('{app.screen}')", app.title) for app in ORION_APPS),
        Binding("tab", "cycle_focus", I18N.bidi("Tab focus", "Табуляция фокус")),
        Binding("ctrl+e", "focus_command", "Command input/Ввод команды"),
        Binding("ctrl+y", "toggle_events_live", "Events live or pause/События живое или пауза"),
        Binding("ctrl+i", "toggle_inspector", "Inspector toggle/Инспектор вкл/выкл"),
        Binding("c", "toggle_sensors_compact", "Sensors compact/Сенсоры компакт", show=False),
        Binding(
            "t",
            "toggle_selected_rule_enabled",
            I18N.bidi("Toggle rule enabled", "Переключить правило"),
            show=False,
        ),
        Binding(
            "a",
            "acknowledge_selected_incident",
            I18N.bidi("Acknowledge selected incident", "Подтвердить выбранный инцидент"),
            show=False,
        ),
        Binding(
            "x",
            "clear_acknowledged_incidents",
            I18N.bidi("Clear acknowledged incidents", "Очистить подтвержденные инциденты"),
            show=False,
        ),
        Binding(
            "r",
            "mark_events_read",
            I18N.bidi("Mark events read", "Отметить прочитанным"),
            show=False,
        ),
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
        self._density: str = "wide"
        self._sensors_compact_override: Optional[bool] = None
        self._tracks_by_id: dict[str, tuple[dict[str, Any], float]] = {}
        self._last_event: Optional[dict[str, Any]] = None
        self._events_live: bool = True
        self._events_unread_count: int = 0
        self._events_unread_incident_ids: set[str] = set()
        self._last_unread_refresh_ts: float = 0.0
        self._max_event_incidents: int = int(os.getenv("OPERATOR_CONSOLE_MAX_EVENT_INCIDENTS", "500"))
        self._max_events_table_rows: int = int(os.getenv("OPERATOR_CONSOLE_MAX_EVENTS_TABLE_ROWS", "200"))
        self._console_by_key: dict[str, dict[str, Any]] = {}
        self._summary_by_key: dict[str, dict[str, Any]] = {}
        self._power_by_key: dict[str, dict[str, Any]] = {}
        self._sensors_by_key: dict[str, dict[str, Any]] = {}
        self._propulsion_by_key: dict[str, dict[str, Any]] = {}
        self._thermal_by_key: dict[str, dict[str, Any]] = {}
        self._diagnostics_by_key: dict[str, dict[str, Any]] = {}
        self._mission_by_key: dict[str, dict[str, Any]] = {}
        self._selection_by_app: dict[str, SelectionContext] = {}
        self._snapshots = SnapshotStore()
        # Boot UI coordination flags (no-mocks).
        self._boot_nats_init_done: bool = False
        self._boot_nats_error: str = ""
        self._events_filter_type: Optional[str] = None
        self._events_filter_text: Optional[str] = None
        self._command_max_chars: int = int(os.getenv("OPERATOR_CONSOLE_COMMAND_MAX_CHARS", "1024"))
        self._warned_command_trim: bool = False
        repo_root = os.getenv("QIKI_REPO_ROOT", "").strip() or "."
        default_rules = os.path.join(repo_root, "config", "incident_rules.yaml")
        # History is optional; keep it disabled by default to avoid creating extra files in the repo.
        history_path = os.getenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", "").strip() or None
        self._rules_repo = FileRulesRepository(
            os.getenv("OPERATOR_CONSOLE_INCIDENT_RULES", default_rules),
            history_path,
        )
        self._incident_rules = None
        self._incident_store: Optional[IncidentStore] = None
        # TTL is used only to mark tracks as stale in UI (no-mocks: we show last known + age).
        # Keep it reasonably large by default so operators can actually observe the pipeline.
        self._track_ttl_sec: float = float(os.getenv("OPERATOR_CONSOLE_TRACK_TTL_SEC", "60.0"))
        self._max_track_rows: int = int(os.getenv("OPERATOR_CONSOLE_MAX_TRACK_ROWS", "25"))
        self._max_console_rows: int = int(os.getenv("OPERATOR_CONSOLE_MAX_CONSOLE_ROWS", "200"))
        self._output_height_override: Optional[int] = None
        self._bottom_bar_height_override: Optional[int] = None
        self._inspector_override: Optional[bool] = None
        self._sidebar_override: Optional[bool] = None
        try:
            raw_output_height = os.getenv("OPERATOR_CONSOLE_OUTPUT_HEIGHT")
            if raw_output_height:
                self._output_height_override = max(3, int(raw_output_height))
        except Exception:
            self._output_height_override = None
        try:
            raw_bottom_bar_height = os.getenv("OPERATOR_CONSOLE_BOTTOM_BAR_HEIGHT")
            if raw_bottom_bar_height:
                self._bottom_bar_height_override = max(7, int(raw_bottom_bar_height))
        except Exception:
            self._bottom_bar_height_override = None
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
        self._load_incident_rules(initial=True)

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
    def _event_type_label(event_type: str) -> str:
        """Render event type as a user-facing label (EN/RU) without polluting storage keys."""

        t = (event_type or "").strip().lower()
        if not t or t in {"unknown", "неизвестно"}:
            return I18N.UNKNOWN
        return event_type

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
            return I18N.bidi("NATS message bus", "NATS шина сообщений")
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

    def _refresh_thermal(self) -> None:
        if self.active_screen == "thermal":
            self._render_thermal_table()

    def _refresh_mission(self) -> None:
        if self.active_screen == "mission":
            self._render_mission_table()

    @staticmethod
    def _block_status_label(status: str) -> str:
        s = (status or "").strip().lower()
        if s in {"ok", "good", "normal"}:
            return I18N.bidi("Normal", "Норма")
        if s in {"warn", "warning"}:
            return I18N.bidi("Warning", "Предупреждение")
        if s in {"crit", "critical"}:
            return I18N.bidi("Critical", "Критично")
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
                value=I18N.fmt_age_compact(telemetry_age_s),
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # Power is derived from telemetry (no-mocks): if telemetry is missing -> Not available/Нет данных.
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

        # MCQPU utilization is telemetry-derived (virtual hardware, no-mocks).
        cpu_value = I18N.NA
        cpu_status = "na"
        mem_value = I18N.NA
        mem_status = "na"
        if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
            try:
                normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
            except ValidationError:
                normalized = {}
            if isinstance(normalized, dict):
                cpu_usage = normalized.get("cpu_usage")
                memory_usage = normalized.get("memory_usage")
                if cpu_usage is not None:
                    cpu_status = "ok"
                    cpu_value = I18N.pct(cpu_usage, digits=1)
                if memory_usage is not None:
                    mem_status = "ok"
                    mem_value = I18N.pct(memory_usage, digits=1)
        blocks.append(
            SystemStateBlock(
                block_id="cpu_usage",
                title=I18N.bidi("CPU", "ЦП"),
                status=cpu_status,
                value=cpu_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )
        blocks.append(
            SystemStateBlock(
                block_id="memory_usage",
                title=I18N.bidi("Memory", "Пам"),
                status=mem_status,
                value=mem_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        bios_env = self._snapshots.get_last("bios")
        bios_status = "na"
        bios_value = I18N.NA
        if bios_env is not None and isinstance(bios_env.payload, dict):
            all_go = bios_env.payload.get("all_systems_go")
            if isinstance(all_go, bool):
                bios_status = "ok" if all_go else "crit"
                bios_value = I18N.bidi("OK", "ОК") if all_go else I18N.bidi("FAIL", "СБОЙ")
            else:
                bios_status = "warn"
                bios_value = I18N.bidi("Unknown", "Неизвестно")
        blocks.append(
            SystemStateBlock(
                block_id="bios",
                title=I18N.bidi("BIOS", "БИОС"),
                status=bios_status,
                value=bios_value,
                ts_epoch=None if bios_env is None else float(bios_env.ts_epoch),
                envelope=bios_env,
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
                value=I18N.fmt_age_compact(last_event_age_s),
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
        current = self._selection_by_app.get("summary")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status_label = self._block_status_label(block.status)
            table.add_row(block.title, status_label, block.value, I18N.fmt_age_compact(age_s), key=block.block_id)
            self._summary_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status_label,
                "value": block.value,
                "age": I18N.fmt_age_compact(age_s),
                "envelope": block.envelope,
            }
            if selected_key is not None and block.block_id == selected_key:
                selected_row = table.row_count - 1

        # Keep an always-valid selection on Summary.
        first_key = blocks[0].block_id if blocks else "seed"
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
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
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

        def fmt_list(value: Any) -> str:
            if not isinstance(value, list):
                return I18N.NA
            items = [str(x).strip() for x in value if str(x).strip()]
            if not items:
                return I18N.bidi("none", "нет")
            s = ", ".join(items)
            return s if len(s) <= 32 else s[:29] + "..."

        def fmt_faults(value: Any) -> str:
            if not isinstance(value, list):
                return I18N.NA
            items = [str(x).strip() for x in value if str(x).strip()]
            if not items:
                return I18N.bidi("none", "нет")
            if len(items) == 1:
                return items[0]
            head = items[0]
            return f"{head} (+{len(items) - 1})"

        rows: list[tuple[str, str, str, Any]] = [
            (
                "battery_level",
                I18N.bidi("Battery level", "Уровень батареи"),
                I18N.pct(normalized.get("battery"), digits=2),
                normalized.get("battery"),
            ),
            (
                "state_of_charge",
                I18N.bidi("SoC", "Заряд"),
                I18N.pct(get("power.soc_pct"), digits=1),
                get("power.soc_pct"),
            ),
            (
                "load_shedding",
                I18N.bidi("Load shed", "Сброс нагрузки"),
                I18N.yes_no(bool(get("power.load_shedding"))) if get("power.load_shedding") is not None else I18N.NA,
                get("power.load_shedding"),
            ),
            (
                "shed_reasons",
                I18N.bidi("Shed reason", "Причины"),
                fmt_list(get("power.shed_reasons")),
                get("power.shed_reasons"),
            ),
            (
                "nbl_active",
                I18N.bidi("NBL", "NBL"),
                I18N.yes_no(bool(get("power.nbl_active"))) if get("power.nbl_active") is not None else I18N.NA,
                get("power.nbl_active"),
            ),
            (
                "nbl_allowed",
                I18N.bidi("NBL ok", "NBL ок"),
                I18N.yes_no(bool(get("power.nbl_allowed"))) if get("power.nbl_allowed") is not None else I18N.NA,
                get("power.nbl_allowed"),
            ),
            (
                "nbl_budget",
                I18N.bidi("NBL budget", "Бюджет NBL"),
                I18N.num_unit(get("power.nbl_budget_w"), "W", "Вт", digits=1),
                get("power.nbl_budget_w"),
            ),
            (
                "nbl_power",
                I18N.bidi("NBL P", "NBL P"),
                I18N.num_unit(get("power.nbl_power_w"), "W", "Вт", digits=1),
                get("power.nbl_power_w"),
            ),
            (
                "shed_loads",
                I18N.bidi("Shed loads", "Сброшено"),
                fmt_list(get("power.shed_loads")),
                get("power.shed_loads"),
            ),
            (
                "faults",
                I18N.bidi("Faults", "Аварии"),
                fmt_faults(get("power.faults")),
                get("power.faults"),
            ),
            (
                "pdu_limit",
                I18N.bidi("PDU limit", "Лимит PDU"),
                I18N.num_unit(get("power.pdu_limit_w"), "W", "Вт", digits=1),
                get("power.pdu_limit_w"),
            ),
            (
                "pdu_throttled",
                I18N.bidi("PDU throttled", "PDU троттл"),
                I18N.yes_no(bool(get("power.pdu_throttled"))) if get("power.pdu_throttled") is not None else I18N.NA,
                get("power.pdu_throttled"),
            ),
            (
                "throttled_loads",
                I18N.bidi("Throttled", "Троттлено"),
                fmt_list(get("power.throttled_loads")),
                get("power.throttled_loads"),
            ),
            (
                "supercap_soc",
                I18N.bidi("SC SoC", "Суперкап"),
                I18N.pct(get("power.supercap_soc_pct"), digits=1),
                get("power.supercap_soc_pct"),
            ),
            (
                "dock_connected",
                I18N.bidi("Dock", "Стыковка"),
                I18N.yes_no(bool(get("power.dock_connected"))) if get("power.dock_connected") is not None else I18N.NA,
                get("power.dock_connected"),
            ),
            (
                "docking_state",
                I18N.bidi("Dock state", "Состояние дока"),
                I18N.fmt_na(get("docking.state")),
                get("docking.state"),
            ),
            (
                "docking_port",
                I18N.bidi("Dock port", "Порт дока"),
                I18N.fmt_na(get("docking.port")),
                get("docking.port"),
            ),
            (
                "dock_soft_start",
                I18N.bidi("Dock ramp", "Разгон дока"),
                I18N.pct(get("power.dock_soft_start_pct"), digits=0),
                get("power.dock_soft_start_pct"),
            ),
            (
                "dock_power",
                I18N.bidi("Dock P", "Стыковка P"),
                I18N.num_unit(get("power.dock_power_w"), "W", "Вт", digits=1),
                get("power.dock_power_w"),
            ),
            (
                "dock_v",
                I18N.bidi("Dock V", "Док В"),
                I18N.num_unit(get("power.dock_v"), "V", "В", digits=2),
                get("power.dock_v"),
            ),
            (
                "dock_a",
                I18N.bidi("Dock A", "Док А"),
                I18N.num_unit(get("power.dock_a"), "A", "А", digits=2),
                get("power.dock_a"),
            ),
            (
                "power_input",
                I18N.bidi("P in", "Вх мощн"),
                I18N.num_unit(get("power.power_in_w"), "W", "Вт", digits=1),
                get("power.power_in_w"),
            ),
            (
                "power_consumption",
                I18N.bidi("P out", "Вых мощн"),
                I18N.num_unit(get("power.power_out_w"), "W", "Вт", digits=1),
                get("power.power_out_w"),
            ),
            (
                "dock_temp",
                I18N.bidi("Dock temp", "Темп стыковки"),
                I18N.num_unit(get("power.dock_temp_c"), "C", "°C", digits=1),
                get("power.dock_temp_c"),
            ),
            (
                "supercap_charge",
                I18N.bidi("SC charge", "Заряд СК"),
                I18N.num_unit(get("power.supercap_charge_w"), "W", "Вт", digits=1),
                get("power.supercap_charge_w"),
            ),
            (
                "supercap_discharge",
                I18N.bidi("SC discharge", "Разряд СК"),
                I18N.num_unit(get("power.supercap_discharge_w"), "W", "Вт", digits=1),
                get("power.supercap_discharge_w"),
            ),
            (
                "bus_voltage",
                I18N.bidi("Bus V", "Шина В"),
                I18N.num_unit(get("power.bus_v"), "V", "В", digits=2),
                get("power.bus_v"),
            ),
            (
                "bus_current",
                I18N.bidi("Bus A", "Шина А"),
                I18N.num_unit(get("power.bus_a"), "A", "А", digits=2),
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
        age = I18N.fmt_age_compact(age_s)
        source = I18N.bidi("telemetry", "телеметрия")

        def status_label(raw_value: Any, rendered_value: str) -> str:
            if raw_value is None:
                return I18N.NA
            if rendered_value == I18N.INVALID:
                return I18N.bidi("Abnormal", "Не норма")
            return I18N.bidi("Normal", "Норма")

        current = self._selection_by_app.get("power")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
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
            if selected_key is not None and row_key == selected_key:
                selected_row = table.row_count - 1

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
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def _render_thermal_table(self) -> None:
        try:
            table = self.query_one("#thermal-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._thermal_by_key = {}
            self._selection_by_app.pop("thermal", None)
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

        thermal = normalized.get("thermal") if isinstance(normalized, dict) else None
        if not isinstance(thermal, dict):
            seed_empty()
            return
        nodes = thermal.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            seed_empty()
            return

        faults_set: set[str] = set()
        power = normalized.get("power") if isinstance(normalized, dict) else None
        if isinstance(power, dict):
            faults = power.get("faults")
            if isinstance(faults, list):
                faults_set = {str(x) for x in faults if isinstance(x, str) and x.startswith("THERMAL_TRIP:")}

        now = time.time()
        age_s = max(0.0, now - float(telemetry_env.ts_epoch))
        age = I18N.fmt_age_compact(age_s)
        source = I18N.bidi("telemetry", "телеметрия")

        self._thermal_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        current = self._selection_by_app.get("thermal")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        def status_label(node_id: str, temp: Any) -> str:
            if temp is None:
                return I18N.NA
            if f"THERMAL_TRIP:{node_id}" in faults_set:
                return I18N.bidi("Abnormal", "Не норма")
            return I18N.bidi("Normal", "Норма")

        for raw in nodes[:64]:
            if not isinstance(raw, dict):
                continue
            node_id = raw.get("id")
            temp = raw.get("temp_c")
            if not isinstance(node_id, str) or not node_id.strip():
                continue
            nid = node_id.strip()
            value = I18N.num_unit(temp, "C", "°C", digits=1)
            status = status_label(nid, temp)
            table.add_row(nid, status, value, age, source, key=nid)
            self._thermal_by_key[nid] = {
                "node_id": nid,
                "status": status,
                "temp_c": temp,
                "value": value,
                "age": age,
                "source": source,
                "envelope": telemetry_env,
            }
            if selected_key is not None and nid == selected_key:
                selected_row = table.row_count - 1

        if current is None or current.key not in self._thermal_by_key:
            first_key = next(iter(self._thermal_by_key.keys()), "seed")
            self._set_selection(
                SelectionContext(
                    app_id="thermal",
                    key=first_key,
                    kind="thermal_node",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=(first_key,),
                )
            )
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def _render_propulsion_table(self) -> None:
        try:
            table = self.query_one("#propulsion-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._propulsion_by_key = {}
            self._selection_by_app.pop("propulsion", None)
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

        propulsion = normalized.get("propulsion") if isinstance(normalized, dict) else None
        if not isinstance(propulsion, dict):
            seed_empty()
            return
        rcs = propulsion.get("rcs")
        if not isinstance(rcs, dict):
            seed_empty()
            return

        now = time.time()
        age_s = max(0.0, now - float(telemetry_env.ts_epoch))
        age = I18N.fmt_age_compact(age_s)
        source = I18N.bidi("telemetry", "телеметрия")

        def status_label(raw_value: Any, rendered_value: str, *, warning: bool = False) -> str:
            if raw_value is None:
                return I18N.NA
            if warning:
                return I18N.bidi("Warning", "Предупреждение")
            if rendered_value == I18N.INVALID:
                return I18N.bidi("Abnormal", "Не норма")
            return I18N.bidi("Normal", "Норма")

        rows: list[tuple[str, str, str, Any, bool]] = []
        enabled = rcs.get("enabled")
        active = rcs.get("active")
        throttled = rcs.get("throttled")
        axis = rcs.get("axis")
        cmd_pct = rcs.get("command_pct")
        time_left = rcs.get("time_left_s")
        propellant = rcs.get("propellant_kg")
        power_w = rcs.get("power_w")

        rows.extend(
            [
                ("rcs_enabled", I18N.bidi("RCS enabled", "РДС включено"), I18N.yes_no(bool(enabled)), enabled, False),
                ("rcs_active", I18N.bidi("RCS active", "РДС активно"), I18N.yes_no(bool(active)), active, bool(throttled)),
                ("rcs_axis", I18N.bidi("Axis", "Ось"), I18N.fmt_na(axis), axis, bool(throttled)),
                ("rcs_command", I18N.bidi("Command", "Команда"), I18N.num_unit(cmd_pct, "%", "%", digits=0), cmd_pct, bool(throttled)),
                ("rcs_time_left", I18N.bidi("Time left", "Осталось"), I18N.num_unit(time_left, "s", "с", digits=1), time_left, bool(throttled)),
                ("rcs_propellant", I18N.bidi("Propellant", "Топливо"), I18N.num_unit(propellant, "kg", "кг", digits=2), propellant, bool(throttled)),
                ("rcs_power", I18N.bidi("RCS power", "РДС мощн"), I18N.num_unit(power_w, "W", "Вт", digits=1), power_w, bool(throttled)),
            ]
        )

        thrusters = rcs.get("thrusters")
        if isinstance(thrusters, list) and thrusters:
            for t in thrusters[:32]:
                if not isinstance(t, dict):
                    continue
                idx = t.get("index")
                cluster = t.get("cluster_id")
                duty = t.get("duty_pct")
                valve = t.get("valve_open")
                if not isinstance(idx, int):
                    continue
                label = f"{I18N.bidi('Thruster', 'Сопло')} {idx} ({cluster})"
                valve_txt = I18N.yes_no(bool(valve))
                value = f"{I18N.num_unit(duty, '%', '%', digits=0)} {I18N.bidi('open', 'откр')}={valve_txt}"
                rows.append((f"thruster_{idx}", label, value, duty, bool(throttled)))

        self._propulsion_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        current = self._selection_by_app.get("propulsion")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        for row_key, label, value, raw, warn in rows:
            status = status_label(raw, value, warning=warn)
            table.add_row(label, status, value, age, source, key=row_key)
            self._propulsion_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "raw": raw,
                "envelope": telemetry_env,
            }
            if selected_key is not None and row_key == selected_key:
                selected_row = table.row_count - 1

        if current is None or current.key not in self._propulsion_by_key:
            first_key = rows[0][0] if rows else "seed"
            self._set_selection(
                SelectionContext(
                    app_id="propulsion",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=(first_key,),
                )
            )
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def _render_sensors_table(self) -> None:
        try:
            table = self.query_one("#sensors-table", DataTable)
        except Exception:
            return
        compact = self._sensors_compact_enabled()

        def style_status(text: str, kind: str | None) -> Text:
            k = (kind or "").strip().lower()
            if k == "ok":
                return Text(text, style="green")
            if k == "warn":
                return Text(text, style="yellow")
            if k == "crit":
                return Text(text, style="bold red")
            # na / unknown
            return Text(text, style="dim")

        def seed_empty() -> None:
            self._sensors_by_key = {}
            self._selection_by_app.pop("sensors", None)
            try:
                table.clear()
            except Exception:
                return
            table.add_row("—", I18N.NA, I18N.NA, key="seed")

        telemetry_env = self._snapshots.get_last("telemetry")
        if telemetry_env is None or not isinstance(telemetry_env.payload, dict):
            seed_empty()
            return

        try:
            normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
        except ValidationError:
            seed_empty()
            return

        sp = normalized.get("sensor_plane") if isinstance(normalized, dict) else None
        if not isinstance(sp, dict):
            seed_empty()
            return

        now = time.time()
        age_s = max(0.0, now - float(telemetry_env.ts_epoch))
        age = I18N.fmt_age_compact(age_s)
        source = I18N.bidi("telemetry", "телеметрия")

        def status_label(raw_value: Any, rendered_value: str, *, warning: bool = False, status_kind: str | None = None) -> str:
            if status_kind is not None:
                kind = str(status_kind).strip().lower()
                if kind == "ok":
                    return I18N.bidi("Normal", "Норма")
                if kind == "warn":
                    return I18N.bidi("Warning", "Предупреждение")
                if kind == "crit":
                    return I18N.bidi("Abnormal", "Не норма")
                return I18N.NA
            if isinstance(raw_value, dict):
                # A dict is an aggregate; without an explicit status_kind it is safer to show N/A than pretend "Normal".
                return I18N.NA
            if raw_value is None:
                return I18N.NA
            if warning:
                return I18N.bidi("Warning", "Предупреждение")
            if rendered_value == I18N.INVALID:
                return I18N.bidi("Abnormal", "Не норма")
            return I18N.bidi("Normal", "Норма")

        rows: list[tuple[str, str, str, Any, bool, str | None]] = []

        if compact:
            imu = sp.get("imu") if isinstance(sp.get("imu"), dict) else {}
            imu_status = imu.get("status") if isinstance(imu.get("status"), str) else None
            imu_rates = [
                ("r", imu.get("roll_rate_rps")),
                ("p", imu.get("pitch_rate_rps")),
                ("y", imu.get("yaw_rate_rps")),
            ]
            imu_rates_txt = " ".join(
                [f"{k}={float(v):.3f}" for (k, v) in imu_rates if isinstance(v, (int, float))]
            )
            imu_value = f"{imu_rates_txt} rad/s" if imu_rates_txt else I18N.NA
            rows.append(("imu", I18N.bidi("IMU", "ИМУ"), imu_value, imu, False, imu_status))

            rad = sp.get("radiation") if isinstance(sp.get("radiation"), dict) else {}
            rad_status = rad.get("status") if isinstance(rad.get("status"), str) else None
            rows.append(
                (
                    "radiation",
                    I18N.bidi("Radiation", "Радиация"),
                    I18N.num_unit(rad.get("background_usvh"), "µSv/h", "мкЗв/ч", digits=2),
                    rad,
                    False,
                    rad_status,
                )
            )

            prox = sp.get("proximity") if isinstance(sp.get("proximity"), dict) else {}
            prox_value = I18N.fmt_na(prox.get("contacts"))
            if prox_value == I18N.NA:
                prox_value = I18N.num_unit(prox.get("min_range_m"), "m", "м", digits=2)
            rows.append(("proximity", I18N.bidi("Proximity", "Близость"), prox_value, prox, False, None))

            solar = sp.get("solar") if isinstance(sp.get("solar"), dict) else {}
            rows.append(
                (
                    "solar",
                    I18N.bidi("Solar", "Солнце"),
                    I18N.pct(solar.get("illumination_pct"), digits=1),
                    solar,
                    False,
                    None,
                )
            )

            st = sp.get("star_tracker") if isinstance(sp.get("star_tracker"), dict) else {}
            st_status = st.get("status") if isinstance(st.get("status"), str) else None
            st_value = I18N.yes_no(bool(st.get("locked"))) if st.get("locked") is not None else I18N.NA
            rows.append(("star_tracker", I18N.bidi("Star tracker", "Звёздн. трекер"), st_value, st, False, st_status))

            mag = sp.get("magnetometer") if isinstance(sp.get("magnetometer"), dict) else {}
            field = mag.get("field_ut") if isinstance(mag.get("field_ut"), dict) else None
            mag_value = I18N.NA
            if isinstance(field, dict):
                try:
                    x = float(field.get("x"))
                    y = float(field.get("y"))
                    z = float(field.get("z"))
                    mag_value = f"|B|={math.sqrt(x*x + y*y + z*z):.2f} µT"
                except Exception:
                    mag_value = I18N.INVALID
            rows.append(("magnetometer", I18N.bidi("Magnetometer", "Магнитометр"), mag_value, mag, mag_value == I18N.INVALID, None))
        else:
            imu = sp.get("imu") if isinstance(sp.get("imu"), dict) else {}
            imu_status = imu.get("status") if isinstance(imu.get("status"), str) else None
            rows.extend(
                [
                    ("imu_enabled", I18N.bidi("IMU enabled", "ИМУ включено"), I18N.yes_no(bool(imu.get("enabled"))), imu.get("enabled"), False, None),
                    ("imu_ok", I18N.bidi("IMU ok", "ИМУ ок"), I18N.yes_no(bool(imu.get("ok"))) if imu.get("ok") is not None else I18N.NA, imu.get("ok"), bool(imu.get("ok") is False), imu_status),
                    ("imu_roll_rate", I18N.bidi("Roll rate", "Скор. крена"), I18N.num_unit(imu.get("roll_rate_rps"), "rad/s", "рад/с", digits=3), imu.get("roll_rate_rps"), False, imu_status),
                    ("imu_pitch_rate", I18N.bidi("Pitch rate", "Скор. тангажа"), I18N.num_unit(imu.get("pitch_rate_rps"), "rad/s", "рад/с", digits=3), imu.get("pitch_rate_rps"), False, imu_status),
                    ("imu_yaw_rate", I18N.bidi("Yaw rate", "Скор. рыск"), I18N.num_unit(imu.get("yaw_rate_rps"), "rad/s", "рад/с", digits=3), imu.get("yaw_rate_rps"), False, imu_status),
                ]
            )

            rad = sp.get("radiation") if isinstance(sp.get("radiation"), dict) else {}
            rad_status = rad.get("status") if isinstance(rad.get("status"), str) else None
            rows.extend(
                [
                    ("rad_enabled", I18N.bidi("Radiation enabled", "Радиация вкл"), I18N.yes_no(bool(rad.get("enabled"))), rad.get("enabled"), False, None),
                    ("rad_background", I18N.bidi("Background", "Фон"), I18N.num_unit(rad.get("background_usvh"), "µSv/h", "мкЗв/ч", digits=2), rad.get("background_usvh"), False, rad_status),
                    ("rad_dose", I18N.bidi("Dose total", "Доза сумм"), I18N.num_unit(rad.get("dose_total_usv"), "µSv", "мкЗв", digits=3), rad.get("dose_total_usv"), False, None),
                ]
            )

            prox = sp.get("proximity") if isinstance(sp.get("proximity"), dict) else {}
            rows.extend(
                [
                    ("prox_enabled", I18N.bidi("Proximity enabled", "Близость вкл"), I18N.yes_no(bool(prox.get("enabled"))), prox.get("enabled"), False, None),
                    ("prox_min", I18N.bidi("Min range", "Мин. дальн"), I18N.num_unit(prox.get("min_range_m"), "m", "м", digits=2), prox.get("min_range_m"), False, None),
                    ("prox_contacts", I18N.bidi("Contacts", "Контакты"), I18N.fmt_na(prox.get("contacts")), prox.get("contacts"), False, None),
                ]
            )

            solar = sp.get("solar") if isinstance(sp.get("solar"), dict) else {}
            rows.extend(
                [
                    ("solar_enabled", I18N.bidi("Solar enabled", "Солнце вкл"), I18N.yes_no(bool(solar.get("enabled"))), solar.get("enabled"), False, None),
                    ("solar_illum", I18N.bidi("Illumination", "Освещённ"), I18N.pct(solar.get("illumination_pct"), digits=1), solar.get("illumination_pct"), False, None),
                ]
            )

            st = sp.get("star_tracker") if isinstance(sp.get("star_tracker"), dict) else {}
            st_status = st.get("status") if isinstance(st.get("status"), str) else None
            rows.extend(
                [
                    ("st_enabled", I18N.bidi("Star tracker enabled", "Звёздн. трекер"), I18N.yes_no(bool(st.get("enabled"))), st.get("enabled"), False, None),
                    ("st_locked", I18N.bidi("Star lock", "Звёзд. захват"), I18N.yes_no(bool(st.get("locked"))) if st.get("locked") is not None else I18N.NA, st.get("locked"), bool(st.get("locked") is False), st_status),
                    ("st_err", I18N.bidi("Att err", "Ошибка атт"), I18N.num_unit(st.get("attitude_err_deg"), "deg", "°", digits=2), st.get("attitude_err_deg"), False, st_status),
                ]
            )

            mag = sp.get("magnetometer") if isinstance(sp.get("magnetometer"), dict) else {}
            field = mag.get("field_ut") if isinstance(mag.get("field_ut"), dict) else None
            field_txt = I18N.NA
            if isinstance(field, dict):
                try:
                    field_txt = f"x={float(field.get('x')):.2f}, y={float(field.get('y')):.2f}, z={float(field.get('z')):.2f}"
                except Exception:
                    field_txt = I18N.INVALID
            rows.extend(
                [
                    ("mag_enabled", I18N.bidi("Magnetometer enabled", "Магнитометр"), I18N.yes_no(bool(mag.get("enabled"))), mag.get("enabled"), False, None),
                    ("mag_field", I18N.bidi("Mag field", "Поле магн"), field_txt, field, field_txt == I18N.INVALID, None),
                ]
            )

        self._sensors_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        current = self._selection_by_app.get("sensors")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        for row_key, label, value, raw, warn, status_kind in rows:
            status = status_label(raw, value, warning=warn, status_kind=status_kind)
            table.add_row(label, style_status(status, status_kind), value, key=row_key)
            self._sensors_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "raw": raw,
                "envelope": telemetry_env,
            }
            if selected_key is not None and row_key == selected_key:
                selected_row = table.row_count - 1

        if current is None or current.key not in self._sensors_by_key:
            first_key = rows[0][0] if rows else "seed"
            self._set_selection(
                SelectionContext(
                    app_id="sensors",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=(first_key,),
                )
            )
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
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
                return I18N.bidi("Normal", "Норма")
            if s in {"warn"}:
                return I18N.bidi("Warning", "Предупреждение")
            if s in {"crit"}:
                return I18N.bidi("Abnormal", "Не норма")
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
        hardware_profile_hash = None
        comms_enabled = None
        xpdr_mode = None
        xpdr_active = None
        xpdr_allowed = None
        xpdr_id = None
        thermal_nodes = None
        thermal_faults: set[str] = set()
        if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
            try:
                normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
            except ValidationError:
                normalized = {}
            if isinstance(normalized, dict):
                cpu_usage = normalized.get("cpu_usage")
                memory_usage = normalized.get("memory_usage")
                hph = normalized.get("hardware_profile_hash")
                hardware_profile_hash = str(hph).strip() if isinstance(hph, str) and hph.strip() else None
                comms = normalized.get("comms")
                if isinstance(comms, dict):
                    comms_enabled = comms.get("enabled")
                    xpdr = comms.get("xpdr")
                    if isinstance(xpdr, dict):
                        xpdr_mode = xpdr.get("mode")
                        xpdr_active = xpdr.get("active")
                        xpdr_allowed = xpdr.get("allowed")
                        xpdr_id = xpdr.get("id")
                th = normalized.get("thermal")
                if isinstance(th, dict):
                    nodes = th.get("nodes")
                    if isinstance(nodes, list):
                        thermal_nodes = nodes
                pw = normalized.get("power")
                if isinstance(pw, dict):
                    faults = pw.get("faults")
                    if isinstance(faults, list):
                        thermal_faults = {str(x) for x in faults if isinstance(x, str) and x.startswith("THERMAL_TRIP:")}

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
                value=I18N.fmt_age_compact(telemetry_age_s),
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
                value=I18N.fmt_age_compact(last_event_age_s),
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
            SystemStateBlock(
                block_id="hardware_profile_hash",
                title=I18N.bidi("Hardware profile hash", "Хэш профиля железа"),
                status="na" if hardware_profile_hash is None else "ok",
                value=hardware_profile_hash or I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
        ]

        # Comms/XPDR (no-mocks): reflect simulation truth; do not invent values.
        mode_txt = str(xpdr_mode) if isinstance(xpdr_mode, str) and xpdr_mode else None
        allowed_bool = None if xpdr_allowed is None else bool(xpdr_allowed)
        active_bool = None if xpdr_active is None else bool(xpdr_active)
        enabled_bool = None if comms_enabled is None else bool(comms_enabled)
        desired_active = mode_txt in {"ON", "SPOOF"} if mode_txt else None

        # Comms enabled flag.
        blocks.append(
            SystemStateBlock(
                block_id="comms_enabled",
                title=I18N.bidi("Comms enabled", "Связь вкл"),
                status="na" if enabled_bool is None else "ok",
                value=I18N.yes_no(enabled_bool) if enabled_bool is not None else I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # XPDR mode.
        blocks.append(
            SystemStateBlock(
                block_id="xpdr_mode",
                title=I18N.bidi("XPDR mode", "Режим XPDR"),
                status="na" if mode_txt is None else "ok",
                value=mode_txt or I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # XPDR allowed (power gating).
        allowed_status = "na"
        if allowed_bool is not None:
            if allowed_bool:
                allowed_status = "ok"
            else:
                allowed_status = "warn" if desired_active else "ok"
        blocks.append(
            SystemStateBlock(
                block_id="xpdr_allowed",
                title=I18N.bidi("XPDR allowed", "XPDR разрешён"),
                status=allowed_status,
                value=I18N.yes_no(allowed_bool) if allowed_bool is not None else I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # XPDR active (actual transponder activity as seen by radar and loads).
        active_status = "na"
        if active_bool is not None:
            if desired_active is None:
                active_status = "ok" if active_bool else "ok"
            else:
                if active_bool == desired_active:
                    active_status = "ok"
                else:
                    active_status = "warn" if allowed_bool is False else "crit"
        blocks.append(
            SystemStateBlock(
                block_id="xpdr_active",
                title=I18N.bidi("XPDR active", "XPDR активен"),
                status=active_status,
                value=I18N.yes_no(active_bool) if active_bool is not None else I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # XPDR ID.
        xpdr_id_txt = str(xpdr_id) if isinstance(xpdr_id, str) and xpdr_id.strip() else None
        blocks.append(
            SystemStateBlock(
                block_id="xpdr_id",
                title=I18N.bidi("XPDR id", "ID XPDR"),
                status="na" if xpdr_id_txt is None else "ok",
                value=xpdr_id_txt or I18N.NA,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            )
        )

        # Thermal nodes (no-mocks): show real node temps from telemetry or nothing.
        if isinstance(thermal_nodes, list):
            for node in thermal_nodes[:24]:
                if not isinstance(node, dict):
                    continue
                node_id = node.get("id")
                temp = node.get("temp_c")
                if not isinstance(node_id, str) or not node_id.strip():
                    continue
                key = f"thermal_{node_id.strip()}"
                fault_key = f"THERMAL_TRIP:{node_id.strip()}"
                status = "na" if temp is None else ("crit" if fault_key in thermal_faults else "ok")
                blocks.append(
                    SystemStateBlock(
                        block_id=key,
                        title=f"{I18N.bidi('Thermal', 'Температура')}: {node_id.strip()}",
                        status=status,
                        value=I18N.num_unit(temp, "C", "°C", digits=1),
                        ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                        envelope=telemetry_env,
                    )
                )

        self._diagnostics_by_key = {}
        try:
            table.clear()
        except Exception:
            return

        current = self._selection_by_app.get("diagnostics")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status = status_label(block.status)
            table.add_row(block.title, status, block.value, I18N.fmt_age_compact(age_s), key=block.block_id)
            self._diagnostics_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status,
                "value": block.value,
                "age": I18N.fmt_age_compact(age_s),
                "envelope": block.envelope,
            }
            if selected_key is not None and block.block_id == selected_key:
                selected_row = table.row_count - 1

        first_key = blocks[0].block_id if blocks else "seed"
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
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
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

        current = self._selection_by_app.get("mission")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None

        def row(key: str, item: str, status: str, value: str, *, record: dict[str, Any]) -> None:
            table.add_row(item, status, value, key=key)
            self._mission_by_key[key] = record
            nonlocal selected_row
            if selected_key is not None and key == selected_key:
                selected_row = table.row_count - 1

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
                    return I18N.bidi("Completed", "Завершено")
                if s in {"in_progress", "progress", "active", "current"}:
                    return I18N.bidi("In progress", "В работе")
                if s in {"pending", "todo", "planned", "next"}:
                    return I18N.bidi("Pending", "Ожидает")
            if isinstance(v, bool):
                return I18N.bidi("Completed", "Завершено") if v else I18N.bidi("Pending", "Ожидает")
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
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def _render_events_table(self) -> None:
        try:
            table = self.query_one("#events-table", DataTable)
        except Exception:
            return

        table.clear()
        if self._incident_store is None:
            table.add_row(
                "—",
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                key="seed",
            )
            self._selection_by_app.pop("events", None)
            return

        def severity_rank(sev: str) -> int:
            return {"A": 0, "C": 1, "W": 2, "I": 3}.get((sev or "").upper(), 4)

        def passes(inc: Any) -> bool:
            if self._events_filter_type and (inc.type or "") != self._events_filter_type:
                return False
            if not self._events_filter_text:
                return True
            needle = self._events_filter_text.lower()
            hay = " ".join(
                [
                    str(inc.type or ""),
                    str(inc.source or ""),
                    str(inc.subject or ""),
                    str(inc.title or ""),
                    str(inc.description or ""),
                ]
            ).lower()
            return needle in hay

        self._incident_store.refresh()
        incidents = [inc for inc in self._incident_store.list_incidents() if passes(inc)]
        if not incidents:
            table.add_row(
                "—",
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                I18N.NA,
                key="seed",
            )
            self._selection_by_app.pop("events", None)
            return

        incidents_sorted = sorted(
            incidents,
            key=lambda inc: (bool(inc.acked), severity_rank(inc.severity), -float(inc.last_seen)),
        )
        current = self._selection_by_app.get("events")
        selected_key = current.key if current is not None else None
        selected_row: Optional[int] = None
        now = time.time()
        for inc in incidents_sorted[: self._max_events_table_rows]:
            age_s = max(0.0, now - float(inc.last_seen))
            age_text = I18N.fmt_age_compact(age_s)
            acked_text = I18N.yes_no(bool(inc.acked))
            table.add_row(
                inc.severity,
                self._event_type_label(inc.type),
                I18N.fmt_na(inc.source),
                I18N.fmt_na(inc.subject),
                age_text,
                str(int(inc.count)) if isinstance(inc.count, int) else I18N.NA,
                acked_text,
                key=inc.incident_id,
            )
            if selected_key is not None and inc.incident_id == selected_key:
                selected_row = table.row_count - 1

        if current is None or current.key not in {inc.incident_id for inc in incidents_sorted}:
            selected = incidents_sorted[0]
            self._set_selection(
                SelectionContext(
                    app_id="events",
                    key=selected.incident_id,
                    kind="incident",
                    source=selected.source,
                    created_at_epoch=selected.first_seen,
                    payload=selected,
                    ids=(selected.rule_id, selected.type, selected.subject),
                )
            )
            selected_row = 0

        if selected_row is not None:
            try:
                if getattr(table, "cursor_row", None) != selected_row:
                    table.move_cursor(row=selected_row, column=0, animate=False, scroll=False)
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        with Vertical(id="orion-root"):
            yield OrionHeader(id="orion-header")

            with Container(id="orion-workspace"):
                yield OrionSidebar(id="orion-sidebar")
                inspector = OrionInspector(id="orion-inspector")
                inspector.border_title = I18N.bidi("Inspector", "Инспектор")
                yield inspector

                # Screens must all live in the same workspace container so they
                # share chrome (sidebar/inspector) consistently.
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
                            I18N.bidi("Range", "Дальность"),
                            I18N.bidi("Bearing", "Пеленг"),
                            I18N.bidi("Vr", "Скорость"),
                            I18N.bidi("Object", "Объект"),
                        )
                        yield radar_table

                with Container(id="screen-events"):
                    events_table: DataTable = DataTable(id="events-table")
                    events_table.add_columns(
                        I18N.bidi("Severity", "Серьёзн"),
                        I18N.bidi("Type", "Тип"),
                        I18N.bidi("Source", "Источник"),
                        I18N.bidi("Subject", "Тема"),
                        I18N.bidi("Age", "Возраст"),
                        I18N.bidi("Count", "Счётчик"),
                        I18N.bidi("Ack", "Подтв"),
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

                with Container(id="screen-sensors"):
                    sensors_table: DataTable = DataTable(id="sensors-table")
                    sensors_table.add_column(I18N.bidi("Sensor", "Сенсор"), width=40)
                    sensors_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    sensors_table.add_column(I18N.bidi("Value", "Значение"), width=36)
                    yield sensors_table

                with Container(id="screen-propulsion"):
                    propulsion_table: DataTable = DataTable(id="propulsion-table")
                    propulsion_table.add_column(I18N.bidi("Component", "Компонент"), width=40)
                    propulsion_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    propulsion_table.add_column(I18N.bidi("Value", "Значение"), width=24)
                    propulsion_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    propulsion_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                    yield propulsion_table

                with Container(id="screen-thermal"):
                    thermal_table: DataTable = DataTable(id="thermal-table")
                    thermal_table.add_column(I18N.bidi("Node", "Узел"), width=26)
                    thermal_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    thermal_table.add_column(I18N.bidi("Temp", "Темп"), width=18)
                    thermal_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    thermal_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                    yield thermal_table

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

                with Container(id="screen-rules"):
                    with Horizontal(id="rules-toolbar"):
                        yield Button(I18N.bidi("Reload rules", "Перезагрузить правила"), id="rules-reload")
                        yield Static(
                            I18N.bidi(
                                f"Rules are loaded from {self._rules_repo.rules_path}",
                                f"Правила загружаются из {self._rules_repo.rules_path}",
                            ),
                            id="rules-hint",
                        )
                        yield Static(
                            I18N.bidi("T — toggle enabled", "T — переключить включено"),
                            id="rules-toggle-hint",
                        )
                    rules_table: DataTable = DataTable(id="rules-table")
                    rules_table.add_columns(
                        I18N.bidi("ID", "ID"),
                        I18N.bidi("Enabled", "Вкл"),
                        I18N.bidi("Severity", "Серьезность"),
                        I18N.bidi("Match", "Совпадение"),
                    )
                    yield rules_table

            with Vertical(id="bottom-bar"):
                try:
                    output_max_lines = int(os.getenv("OPERATOR_CONSOLE_OUTPUT_MAX_LINES", "1024"))
                except Exception:
                    output_max_lines = 1024
                output_max_lines = max(100, min(10_000, output_max_lines))
                output = RichLog(
                    id="command-output-log",
                    highlight=False,
                    markup=False,
                    wrap=True,
                    max_lines=output_max_lines,
                )
                output.can_focus = False
                output.border_title = I18N.bidi("Output", "Вывод")
                yield output
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

    async def on_mount(self) -> None:
        # Cold-boot splash (no-mocks): it will render only proven statuses (NATS, BIOS event).
        self.push_screen(BootScreen(), callback=self._on_boot_complete)
        self.action_show_screen("system")
        self._init_system_panels()
        self._seed_system_panels()
        self._seed_radar_table()
        self._seed_radar_ppi()
        self._seed_events_table()
        self._seed_console_table()
        self._seed_summary_table()
        self._seed_power_table()
        self._seed_sensors_table()
        self._seed_propulsion_table()
        self._seed_thermal_table()
        self._seed_diagnostics_table()
        self._seed_mission_table()
        self._seed_rules_table()
        self._update_system_snapshot()
        self._update_command_placeholder()
        self._refresh_inspector()
        self._apply_responsive_chrome()
        await self._init_nats()
        self.set_interval(0.5, self._refresh_header)
        self.set_interval(1.0, self._refresh_radar)
        self.set_interval(1.0, self._refresh_summary)
        self.set_interval(1.0, self._refresh_thermal)
        self.set_interval(1.0, self._refresh_diagnostics)
        self.set_interval(1.0, self._refresh_mission)
        try:
            # Focus is set after boot screen dismisses to avoid stealing input during boot.
            pass
        except Exception:
            pass

    def _on_boot_complete(self, result: bool) -> None:
        # Boot screen is informational; even on failure we proceed (no-mocks: values will stay N/A).
        try:
            self.set_focus(self.query_one("#command-dock", Input))
        except Exception:
            pass
        if result:
            self._console_log(I18N.bidi("System online", "Система в сети"), level="info")
        else:
            self._console_log(I18N.bidi("Boot aborted", "Загрузка прервана"), level="warning")

    def on_resize(self) -> None:
        self._apply_responsive_chrome()

    def action_toggle_inspector(self) -> None:
        # None -> auto (depending on density), otherwise hard override.
        if self._inspector_override is None:
            self._inspector_override = False
        elif self._inspector_override is False:
            self._inspector_override = True
        else:
            self._inspector_override = None
        self._apply_responsive_chrome()

    def action_toggle_sidebar(self) -> None:
        if self._sidebar_override is None:
            self._sidebar_override = False
        elif self._sidebar_override is False:
            self._sidebar_override = True
        else:
            self._sidebar_override = None
        self._apply_responsive_chrome()

    def _apply_responsive_chrome(self) -> None:
        width = int(getattr(self.size, "width", 0) or 0)
        height = int(getattr(self.size, "height", 0) or 0)

        # Density breakpoints (aimed at tmux splits).
        if width and width < 90:
            density = "tiny"
        elif width and width < 120:
            density = "narrow"
        elif width and width < 170:
            density = "normal"
        else:
            density = "wide"
        self._density = density

        if density == "tiny":
            sidebar_width = 0
            inspector_width = 0
        elif density == "narrow":
            sidebar_width = 18
            inspector_width = 26
        elif density == "normal":
            sidebar_width = 22
            inspector_width = 34
        else:
            sidebar_width = 28
            inspector_width = 44

        # Header grid: 4x2 normally, 2x4 in tiny/narrow.
        try:
            header_grid = self.query_one("#orion-header-grid")
            header_grid.set_class(density in {"tiny", "narrow"}, "header-2x4")
        except Exception:
            pass

        # System dashboard reflow: 2x2 -> 1x4 on narrow/tiny.
        try:
            dashboard = self.query_one("#system-dashboard")
            dashboard.set_class(density in {"tiny", "narrow"}, "dashboard-1x4")
        except Exception:
            pass

        # Sidebar / Inspector visibility: reduce chrome first, keep content stable.
        sidebar_visible = density != "tiny"
        if self._sidebar_override is not None:
            sidebar_visible = bool(self._sidebar_override)

        inspector_visible = density in {"wide", "normal"}
        if self._inspector_override is not None:
            inspector_visible = bool(self._inspector_override)

        try:
            sidebar = self.query_one("#orion-sidebar", OrionSidebar)
            sidebar.styles.display = "block" if sidebar_visible else "none"
            if sidebar_visible:
                sidebar.styles.width = sidebar_width
        except Exception:
            pass

        try:
            inspector = self.query_one("#orion-inspector", OrionInspector)
            inspector.styles.display = "block" if inspector_visible else "none"
            if inspector_visible:
                inspector.styles.width = inspector_width
        except Exception:
            pass

        # Radar: prefer the table on narrow terminals (PPI is dense and becomes unreadable).
        try:
            ppi = self.query_one("#radar-ppi", Static)
            ppi.styles.display = "none" if density in {"tiny", "narrow"} else "block"
        except Exception:
            pass

        # Compact tables on narrow panes by reducing fixed column widths.
        try:
            self._apply_table_column_widths(density=density, total_width=width)
        except Exception:
            pass

        # Calm output strip should be visible, but must not crush content on short terminals.
        try:
            if self._output_height_override is not None:
                output_height = self._output_height_override
            elif height and height < 30:
                output_height = 5
            elif height and height < 36:
                output_height = 6
            else:
                output_height = 8

            if self._bottom_bar_height_override is not None:
                bottom_bar_height = self._bottom_bar_height_override
            elif self._output_height_override is not None:
                # bottom-bar contains: output log + command input + keybar
                bottom_bar_height = output_height + 4
            elif height and height < 30:
                bottom_bar_height = 9
            elif height and height < 36:
                bottom_bar_height = 10
            else:
                bottom_bar_height = 12

            self.query_one("#command-output-log", RichLog).styles.height = output_height
            self.query_one("#bottom-bar").styles.height = bottom_bar_height
        except Exception:
            pass

        # Keep the command line readable at all densities.
        self._update_command_placeholder()

    def _load_incident_rules(self, *, initial: bool = False) -> None:
        try:
            if initial:
                config = self._rules_repo.load()
                self._incident_rules = config
                self._incident_store = IncidentStore(config)
                self._console_log(
                    f"{I18N.bidi('Incident rules loaded', 'Правила инцидентов загружены')}: "
                    f"{len(config.rules)}",
                    level="info",
                )
                return
            result = self._rules_repo.reload(source="file/reload")
            self._incident_rules = result.config
            self._incident_store = IncidentStore(result.config)
            self._console_log(
                f"{I18N.bidi('Incident rules reloaded', 'Правила инцидентов перезагружены')}: "
                f"{len(result.config.rules)} "
                f"({I18N.bidi('hash', 'хэш')}: {result.new_hash[:8]})",
                level="info",
            )
        except Exception as exc:
            self._console_log(
                f"{I18N.bidi('Failed to load incident rules', 'Ошибка загрузки правил инцидентов')}: {exc}",
                level="error",
            )

    def _apply_table_column_widths(self, *, density: str, total_width: int) -> None:
        """Best-effort DataTable column resizing for tmux splits."""

        if total_width <= 0:
            return

        def set_widths(table_id: str, widths: list[int]) -> None:
            try:
                table = self.query_one(f"#{table_id}", DataTable)
            except Exception:
                return
            try:
                cols = list(getattr(table, "columns", []) or [])
            except Exception:
                cols = []
            if not cols:
                return
            for idx, w in enumerate(widths):
                if idx >= len(cols):
                    break
                if w <= 0:
                    continue
                try:
                    cols[idx].width = int(w)
                except Exception:
                    pass
            try:
                table.refresh()
            except Exception:
                pass

        # These tables were created with fixed widths; narrow terminals need smaller presets.
        if density in {"tiny", "narrow"}:
            set_widths("summary-table", [28, 10, 20, 12])
            set_widths("power-table", [26, 10, 16, 12, 12])
            set_widths("sensors-table", [26, 10, 38])
            set_widths("propulsion-table", [26, 10, 16, 12, 12])
            set_widths("thermal-table", [20, 10, 14, 12, 12])
            set_widths("diagnostics-table", [28, 10, 20, 12])
            set_widths("mission-table", [22, 10, 34])
            set_widths("events-table", [8, 14, 14, 22, 10, 8, 6])
            set_widths("console-table", [12, 9, 40])
            set_widths("radar-table", [10, 12, 12, 12, 20])
        elif density == "normal":
            set_widths("summary-table", [36, 14, 26, 18])
            set_widths("power-table", [32, 14, 20, 18, 16])
            set_widths("sensors-table", [32, 14, 64])
            set_widths("propulsion-table", [32, 14, 20, 18, 16])
            set_widths("thermal-table", [24, 14, 16, 18, 16])
            set_widths("diagnostics-table", [36, 14, 24, 18])
            set_widths("mission-table", [28, 14, 52])
            set_widths("events-table", [10, 18, 16, 28, 12, 10, 6])
            set_widths("console-table", [14, 10, 64])
            set_widths("radar-table", [12, 14, 14, 14, 26])
        else:
            # Keep the original compose-time widths on wide screens.
            return

    def _console_log(self, msg: str, *, level: str = "info") -> None:
        # Operator-facing confirmations: calm strip + console history.
        self._calm_log(msg, level=level)
        self._console_table_log(msg, level=level)

    def _calm_log(self, msg: str, *, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        normalized_level = self._normalize_level(level)
        level_label = self._level_label(normalized_level)
        try:
            log = self.query_one("#command-output-log", RichLog)
        except Exception:
            return
        try:
            log.write(f"{ts} {level_label} {msg}")
        except Exception:
            pass

    def _console_table_log(self, msg: str, *, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        normalized_level = self._normalize_level(level)
        level_label = self._level_label(normalized_level)
        try:
            table = self.query_one("#console-table", DataTable)
        except Exception:
            return
        key = f"con-{int(time.time() * 1000)}"
        try:
            if table.row_count == 1:
                table.clear()
        except Exception:
            pass
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
            if self._max_console_rows > 0:
                try:
                    while table.row_count > self._max_console_rows:
                        table.remove_row(0)
                except Exception:
                    pass
        except Exception:
            pass
        if self.active_screen == "console":
            self._refresh_inspector()

    def _log_msg(self, msg: str) -> None:
        # Background/system chatter: console history only (keeps calm strip clean).
        self._console_table_log(msg, level="info")

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
        table.add_column(justify="left", ratio=2, no_wrap=True, overflow="ellipsis")
        table.add_column(justify="left", ratio=3, no_wrap=True, overflow="ellipsis")
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
            return f"{round(float(x), 2)},{round(float(y), 2)},{round(float(z), 2)}"

        def fmt_att_deg(key: str) -> str:
            value = get(f"attitude.{key}")
            if not isinstance(value, (int, float)):
                return I18N.NA
            return I18N.num_unit(math.degrees(float(value)), "°", "°", digits=1)

        online = bool(self.nats_connected and self._snapshots.freshness("telemetry") == "fresh")
        age_value = I18N.fmt_age_compact(self._snapshots.age_s("telemetry"))

        nav_rows = [
            (I18N.bidi("Link", "Связь"), I18N.online_offline(online)),
            (I18N.bidi("Upd", "Обн"), updated),
            (I18N.bidi("Age", "Возраст"), age_value),
            (I18N.bidi("Pos", "Поз"), fmt_pos()),
            (
                I18N.bidi("Velocity", "Скорость"),
                I18N.num_unit(get("velocity"), "m/s", "м/с", digits=2),
            ),
            (I18N.bidi("Heading", "Курс"), I18N.num_unit(get("heading"), "°", "°", digits=1)),
            (I18N.bidi("Roll", "Крен"), fmt_att_deg("roll_rad")),
            (I18N.bidi("Pitch", "Тангаж"), fmt_att_deg("pitch_rad")),
            (I18N.bidi("Yaw", "Рыскание"), fmt_att_deg("yaw_rad")),
        ]

        # Power panel height may be small in tmux; keep the first rows as the most important.
        power_rows = [
            (I18N.bidi("SoC", "Заряд"), I18N.pct(get("power.soc_pct"), digits=2)),
            (I18N.bidi("P in", "Вх мощн"), I18N.num_unit(get("power.power_in_w"), "W", "Вт", digits=1)),
            (I18N.bidi("P out", "Вых мощн"), I18N.num_unit(get("power.power_out_w"), "W", "Вт", digits=1)),
            (I18N.bidi("Bus V", "Шина В"), I18N.num_unit(get("power.bus_v"), "V", "В", digits=2)),
            (I18N.bidi("Bus A", "Шина А"), I18N.num_unit(get("power.bus_a"), "A", "А", digits=2)),
            (I18N.bidi("Bat", "Бат"), I18N.pct(get("battery"), digits=2)),
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
            (I18N.bidi("Ext temp", "Нар темп"), I18N.num_unit(get("temp_external_c"), "°C", "°C", digits=1)),
            (I18N.bidi("Core temp", "Темп ядра"), I18N.num_unit(get("temp_core_c"), "°C", "°C", digits=1)),
        ]

        struct_rows = [
            (I18N.bidi("Hull", "Корпус"), I18N.pct(get("hull.integrity"), digits=1)),
            (
                I18N.bidi("Radiation", "Радиация"),
                I18N.num_unit(get("radiation_usvh"), "µSv/h", "мкЗв/ч", digits=2),
            ),
            (I18N.bidi("CPU", "ЦП"), I18N.pct(get("cpu_usage"), digits=1)),
            (I18N.bidi("Mem", "Пам"), I18N.pct(get("memory_usage"), digits=1)),
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
        if self._incident_rules is not None:
            self._incident_store = IncidentStore(self._incident_rules)
        self._events_live = True
        self._events_unread_count = 0
        self._selection_by_app.pop("events", None)
        self._events_filter_type = None
        self._events_filter_text = None
        table.clear()
        table.add_row(
            "—",
            I18N.NA,
            I18N.NA,
            I18N.NA,
            I18N.NA,
            I18N.NA,
            I18N.NA,
            key="seed",
        )

    def _seed_console_table(self) -> None:
        try:
            table = self.query_one("#console-table", DataTable)
        except Exception:
            return
        self._console_by_key = {}
        self._selection_by_app.pop("console", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, key="seed")

        try:
            log = self.query_one("#command-output-log", RichLog)
        except Exception:
            log = None
        if log is not None:
            try:
                log.clear()
                log.write(f"— {I18N.bidi('Console ready', 'Консоль готова')} —")
            except Exception:
                pass

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

    def _seed_sensors_table(self) -> None:
        try:
            table = self.query_one("#sensors-table", DataTable)
        except Exception:
            return
        self._sensors_by_key = {}
        self._selection_by_app.pop("sensors", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, key="seed")

    def _seed_propulsion_table(self) -> None:
        try:
            table = self.query_one("#propulsion-table", DataTable)
        except Exception:
            return
        self._propulsion_by_key = {}
        self._selection_by_app.pop("propulsion", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _seed_thermal_table(self) -> None:
        try:
            table = self.query_one("#thermal-table", DataTable)
        except Exception:
            return
        self._thermal_by_key = {}
        self._selection_by_app.pop("thermal", None)
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

    def _seed_rules_table(self) -> None:
        try:
            table = self.query_one("#rules-table", DataTable)
        except Exception:
            return
        self._selection_by_app.pop("rules", None)
        table.clear()
        table.add_row("—", I18N.NA, I18N.NA, I18N.NA, key="seed")

    def _render_rules_table(self) -> None:
        try:
            table = self.query_one("#rules-table", DataTable)
        except Exception:
            return
        table.clear()
        if self._incident_rules is None:
            table.add_row("—", I18N.NA, I18N.NA, I18N.NA, key="seed")
            return

        def match_summary(rule: Any) -> str:
            try:
                m = rule.match
            except Exception:
                return I18N.NA
            parts: list[str] = []
            for label, value in (
                (I18N.bidi("type", "тип"), getattr(m, "type", None)),
                (I18N.bidi("source", "источник"), getattr(m, "source", None)),
                (I18N.bidi("subject", "тема"), getattr(m, "subject", None)),
                (I18N.bidi("field", "поле"), getattr(m, "field", None)),
            ):
                if value:
                    parts.append(f"{label}={value}")
            try:
                th = rule.threshold
            except Exception:
                th = None
            if th is not None and getattr(th, "op", None) and getattr(th, "value", None) is not None:
                parts.append(f"{th.op}{th.value}")
            return " ".join(parts) if parts else I18N.NA

        rules = list(self._incident_rules.rules or [])
        rules.sort(key=lambda r: (not bool(getattr(r, "enabled", True)), str(getattr(r, "id", ""))))
        for rule in rules:
            rule_id = str(getattr(rule, "id", "")) or I18N.NA
            table.add_row(
                rule_id,
                I18N.yes_no(bool(getattr(rule, "enabled", True))),
                str(getattr(rule, "severity", "")) or I18N.NA,
                match_summary(rule),
                key=rule_id,
            )

        # Keep a deterministic selection on Rules so operators can toggle immediately.
        if not rules:
            self._selection_by_app.pop("rules", None)
            return
        current = self._selection_by_app.get("rules")
        current_key = (current.key if current is not None else "").strip()
        desired_id = None
        desired_rule = None
        for rule in rules:
            rid = str(getattr(rule, "id", "")).strip()
            if not rid:
                continue
            if current_key and rid == current_key:
                desired_id = rid
                desired_rule = rule
                break
        if desired_id is None:
            desired_rule = rules[0]
            desired_id = str(getattr(desired_rule, "id", "")).strip() or "seed"

        if desired_id != "seed" and desired_rule is not None:
            self._selection_by_app["rules"] = SelectionContext(
                app_id="rules",
                key=desired_id,
                kind="rule",
                source="rules",
                created_at_epoch=time.time(),
                payload=desired_rule,
                ids=(desired_id,),
            )
            try:
                idx = 0
                for i, rule in enumerate(rules):
                    if str(getattr(rule, "id", "")).strip() == desired_id:
                        idx = i
                        break
                table.move_cursor(row=idx, column=0, animate=False, scroll=False)
            except Exception:
                pass

    async def _init_nats(self) -> None:
        self._boot_nats_init_done = False
        self._boot_nats_error = ""
        self.nats_client = NATSClient()
        try:
            await self.nats_client.connect()
            self.nats_connected = True
            self._log_msg(f"✅ {I18N.bidi('NATS connected', 'NATS подключен')}")
            self._update_system_snapshot()
        except Exception as e:
            self.nats_connected = False
            self._boot_nats_error = str(e)
            self._log_msg(f"❌ {I18N.bidi('NATS connect failed', 'NATS не подключился')}: {e}")
            self._update_system_snapshot()
            return
        finally:
            self._boot_nats_init_done = True

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
                telemetry_freshness_kind=self._snapshots.freshness("telemetry"),
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

        ctx = self._selection_by_app.get(self.active_screen)
        summary_rows: list[tuple[str, str]] = [
            (I18N.bidi("Active screen", "Активный экран"), app_title(self.active_screen)),
        ]
        fields_rows: list[tuple[str, str]] = []
        raw_preview = I18N.NA
        actions: list[str] = []
        if ctx is None:
            summary_rows.append((I18N.bidi("Selection", "Выбор"), I18N.bidi("No selection", "Выбора нет")))
        else:
            age_s = time.time() - ctx.created_at_epoch
            freshness = self._fmt_age_s(age_s)
            if ctx.app_id == "radar":
                ttl = self._track_ttl_sec
                if ttl > 0 and isinstance(age_s, (int, float)) and age_s > ttl:
                    freshness = I18N.stale(freshness)

            summary_rows.extend(
                [
                    (I18N.bidi("Selection", "Выбор"), self._kind_label(ctx.kind)),
                    (I18N.bidi("Key", "Ключ"), ctx.key or I18N.NA),
                    (I18N.bidi("Age", "Возраст"), freshness),
                ]
            )

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

            fields_rows.extend(
                [
                    (I18N.bidi("Type", "Тип"), self._kind_label(ctx.kind)),
                    (I18N.bidi("Source", "Источник"), self._source_label(ctx.source)),
                    (I18N.bidi("Age", "Возраст"), freshness),
                    (I18N.bidi("Key", "Ключ"), ctx.key or I18N.NA),
                    (I18N.bidi("Identifiers", "Идентификаторы"), ", ".join(ctx.ids) if ctx.ids else I18N.NA),
                    (
                        I18N.bidi("Timestamp", "Время"),
                        time.strftime("%H:%M:%S", time.localtime(ctx.created_at_epoch))
                        if isinstance(ctx.created_at_epoch, (int, float))
                        else I18N.NA,
                    ),
                ]
            )
            if ctx.app_id == "events":
                incident = self._incident_store.get(ctx.key) if self._incident_store is not None else None
                if incident is not None:
                    summary_rows.extend(
                        [
                            (I18N.bidi("Severity", "Серьезность"), incident.severity),
                            (I18N.bidi("State", "Состояние"), I18N.bidi(incident.state, incident.state)),
                            (I18N.bidi("Acknowledged", "Подтверждено"), I18N.yes_no(bool(incident.acked))),
                        ]
                    )
                    fields_rows.extend(
                        [
                            (I18N.bidi("Rule", "Правило"), I18N.fmt_na(incident.rule_id)),
                            (I18N.bidi("Title", "Название"), I18N.fmt_na(incident.title)),
                            (I18N.bidi("Description", "Описание"), I18N.fmt_na(incident.description)),
                            (I18N.bidi("Severity", "Серьезность"), incident.severity),
                            (I18N.bidi("Type", "Тип"), self._event_type_label(incident.type)),
                            (I18N.bidi("Source", "Источник"), I18N.fmt_na(incident.source)),
                            (I18N.bidi("Subject", "Тема"), I18N.fmt_na(incident.subject)),
                            (I18N.bidi("Count", "Счётчик"), str(incident.count)),
                            (I18N.bidi("Acknowledged", "Подтверждено"), I18N.yes_no(bool(incident.acked))),
                            (I18N.bidi("State", "Состояние"), I18N.bidi(incident.state, incident.state)),
                            (
                                I18N.bidi("First seen", "Первое появление"),
                                I18N.fmt_age_compact(max(0.0, time.time() - float(incident.first_seen))),
                            ),
                            (
                                I18N.bidi("Last seen", "Последнее появление"),
                                I18N.fmt_age_compact(max(0.0, time.time() - float(incident.last_seen))),
                            ),
                        ]
                    )
                    if incident.peak_value is not None:
                        fields_rows.append(
                            (I18N.bidi("Peak value", "Пиковое значение"), self._fmt_num(incident.peak_value))
                        )
                    if incident.cleared_at is not None:
                        fields_rows.append(
                            (
                                I18N.bidi("Cleared", "Очищено"),
                                I18N.fmt_age_compact(max(0.0, time.time() - float(incident.cleared_at))),
                            )
                        )

            if ctx.app_id == "rules" and hasattr(ctx.payload, "id"):
                rule = ctx.payload
                summary_rows.extend(
                    [
                        (I18N.bidi("Enabled", "Включено"), I18N.yes_no(bool(getattr(rule, "enabled", True)))),
                        (I18N.bidi("Severity", "Серьезность"), I18N.fmt_na(getattr(rule, "severity", None))),
                    ]
                )
                fields_rows.extend(
                    [
                        (I18N.bidi("Title", "Название"), I18N.fmt_na(getattr(rule, "title", None))),
                        (I18N.bidi("Description", "Описание"), I18N.fmt_na(getattr(rule, "description", None))),
                        (
                            I18N.bidi("Require ack", "Требует подтверждения"),
                            I18N.yes_no(bool(getattr(rule, "require_ack", False))),
                        ),
                        (I18N.bidi("Auto clear", "Авто очистка"), I18N.yes_no(bool(getattr(rule, "auto_clear", True)))),
                    ]
                )
                try:
                    m = rule.match
                    fields_rows.extend(
                        [
                            (I18N.bidi("Match type", "Тип совпадения"), I18N.fmt_na(getattr(m, "type", None))),
                            (I18N.bidi("Match source", "Источник совпадения"), I18N.fmt_na(getattr(m, "source", None))),
                            (I18N.bidi("Match subject", "Тема совпадения"), I18N.fmt_na(getattr(m, "subject", None))),
                            (I18N.bidi("Match field", "Поле совпадения"), I18N.fmt_na(getattr(m, "field", None))),
                        ]
                    )
                except Exception:
                    pass
                try:
                    th = rule.threshold
                except Exception:
                    th = None
                if th is not None:
                    fields_rows.extend(
                        [
                            (I18N.bidi("Op", "Операция"), I18N.fmt_na(getattr(th, "op", None))),
                            (I18N.bidi("Value", "Значение"), I18N.fmt_na(getattr(th, "value", None))),
                            (I18N.bidi("Min duration", "Мин длительность"), I18N.fmt_na(getattr(th, "min_duration_s", None))),
                            (I18N.bidi("Cooldown", "Кулдаун"), I18N.fmt_na(getattr(th, "cooldown_s", None))),
                        ]
                    )
            if ctx.app_id == "radar" and isinstance(ctx.payload, dict):
                payload = ctx.payload
                range_m = payload.get("range_m", payload.get("range"))
                bearing_deg = payload.get("bearing_deg", payload.get("bearing"))
                vr_mps = payload.get("vr_mps", payload.get("velocity"))
                object_type = payload.get("object_type", payload.get("type"))
                summary_rows.extend(
                    [
                        (I18N.bidi("Range", "Дальность"), I18N.num_unit(range_m, "m", "м", digits=1)),
                        (I18N.bidi("Bearing", "Пеленг"), I18N.num_unit(bearing_deg, "°", "°", digits=1)),
                    ]
                )
                fields_rows.extend(
                    [
                        (I18N.bidi("Range", "Дальность"), I18N.num_unit(range_m, "meters", "метры", digits=1)),
                        (I18N.bidi("Bearing", "Пеленг"), I18N.num_unit(bearing_deg, "°", "°", digits=1)),
                        (
                            I18N.bidi("Radial velocity", "Радиальная скорость"),
                            I18N.num_unit(vr_mps, "meters per second", "метры в секунду", digits=2),
                        ),
                        (I18N.bidi("Object type", "Тип объекта"), I18N.fmt_na(object_type)),
                    ]
                )
            if ctx.app_id == "console" and isinstance(ctx.payload, dict):
                payload = ctx.payload
                summary_rows.append((I18N.bidi("Level", "Уровень"), I18N.fmt_na(payload.get("level"))))
                fields_rows.extend(
                    [
                        (I18N.bidi("Level", "Уровень"), I18N.fmt_na(payload.get("level"))),
                        (I18N.bidi("Message", "Сообщение"), I18N.fmt_na(payload.get("message"))),
                    ]
                )
            if ctx.app_id == "mission":
                fields_rows.append(
                    (
                        I18N.bidi("Mission context", "Контекст миссии"),
                        mission_context if mission_context is not None else I18N.NA,
                    )
                )

            if hasattr(ctx.payload, "model_dump"):
                raw_preview = OrionInspector.safe_preview(ctx.payload.model_dump())
            elif ctx.app_id == "events" and hasattr(ctx.payload, "__dataclass_fields__"):
                raw_preview = OrionInspector.safe_preview(asdict(ctx.payload))
            else:
                raw_preview = OrionInspector.safe_preview(ctx.payload)

        if self.active_screen == "events":
            state = I18N.bidi("Live", "Живое") if self._events_live else I18N.bidi("Paused", "Пауза")
            unread = int(self._events_unread_count) if not self._events_live else 0
            actions.append(f"Ctrl+Y — {I18N.bidi('toggle events mode', 'переключить режим событий')} ({state})")
            if ctx is not None and ctx.app_id == "events":
                actions.append(
                    f"{I18N.bidi('Acknowledge', 'Подтвердить')}: acknowledge <key/ключ> | подтвердить <ключ>"
                )
                actions.append(f"A — {I18N.bidi('Acknowledge selected incident', 'Подтвердить выбранный инцидент')}")
            actions.append(f"{I18N.bidi('Clear acknowledged', 'Очистить подтвержденные')}: clear/очистить")
            actions.append(f"X — {I18N.bidi('Clear acknowledged incidents', 'Очистить подтвержденные инциденты')}")
            if not self._events_live:
                actions.append(f"R — {I18N.bidi('Mark events read', 'Отметить события прочитанными')}")
            if unread > 0:
                # Put the number first so it stays visible even when truncated.
                actions.append(f"{unread} {I18N.bidi('Unread', 'Непрочитано')}")

        if self.active_screen == "rules":
            actions.append(
                f"{I18N.bidi('Reload rules', 'Перезагрузить правила')}: "
                f"{I18N.bidi('button', 'кнопка')} | {I18N.bidi('reload rules', 'перезагрузить правила')}"
            )
            actions.append(
                f"T — {I18N.bidi('Toggle enabled (with confirmation)', 'Переключить включено (с подтверждением)')}"
            )

        nats = I18N.yes_no(self.nats_connected) if isinstance(self.nats_connected, bool) else I18N.NA
        summary_rows.append((I18N.bidi("NATS connectivity", "Связь с NATS"), nats))
        telemetry_age_s = self._snapshots.age_s("telemetry")
        summary_rows.append(
            (
                I18N.bidi("Telemetry age", "Возраст телеметрии"),
                I18N.fmt_age_compact(telemetry_age_s) if telemetry_age_s is not None else I18N.NA,
            )
        )

        outer = Table.grid(expand=True)
        outer.add_column(ratio=1)
        outer.add_row(Text(I18N.bidi("Summary", "Сводка"), style="bold"))
        outer.add_row(OrionInspector._table(summary_rows))
        outer.add_row(Text(I18N.bidi("Fields", "Поля"), style="bold"))
        outer.add_row(OrionInspector._table(fields_rows))
        outer.add_row(Text(I18N.bidi("Raw data (JSON)", "Сырые данные (JSON)"), style="bold"))
        outer.add_row(Text(raw_preview, style="dim"))
        if actions:
            outer.add_row(Text(I18N.bidi("Actions", "Действия"), style="bold"))
            for line in actions:
                outer.add_row(Text(f"- {line}", no_wrap=True, overflow="ellipsis"))

        inspector.update(outer)

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
        self._render_sensors_table()
        self._render_propulsion_table()
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
        ts_epoch = time.time()
        subj = str(subject or "")
        etype = "bios" if subj == "qiki.events.v1.bios_status" else self._derive_event_type(subject, payload)
        env = EventEnvelope(
            event_id=str(subject or ""),
            type=etype,
            source="nats",
            ts_epoch=ts_epoch,
            level=normalized_level,
            payload=payload,
            subject=str(subject or ""),
        )
        self._snapshots.put(env)

        if self._incident_store is not None:
            incident_event = {
                "type": etype,
                "source": self._derive_event_source(payload, subject),
                "subject": self._derive_event_subject(payload, subject),
                "ts_epoch": ts_epoch,
                "payload": payload if isinstance(payload, dict) else {},
            }
            matched_incidents = self._incident_store.ingest(incident_event)
        else:
            matched_incidents = []

        if self._events_live:
            # Re-render under active filter and keep selection consistent.
            self._render_events_table()
        else:
            for inc in matched_incidents:
                try:
                    self._events_unread_incident_ids.add(str(getattr(inc, "incident_id", "")) or str(getattr(inc, "key", "")))
                except Exception:
                    continue
            self._events_unread_count = len(self._events_unread_incident_ids)
            try:
                self.query_one("#orion-sidebar", OrionSidebar).refresh()
            except Exception:
                pass
            # While paused, the table stays stable, but the operator still needs a live unread counter.
            # Refresh the inspector with a small throttle to avoid repaint storms under high event rates.
            if self.active_screen == "events":
                now = time.time()
                if now - float(self._last_unread_refresh_ts) >= 0.5:
                    self._last_unread_refresh_ts = now
                    self._refresh_inspector()

        if self.active_screen == "events":
            if self._events_live:
                self._refresh_inspector()
        if self.active_screen == "mission" and env.type in {"mission", "task"}:
            self._render_mission_table()
            self._refresh_inspector()
        if self.active_screen == "summary":
            self._render_summary_table()
        if etype == "bios":
            self._refresh_summary()

    @staticmethod
    def _derive_event_source(payload: Any, subject: Any) -> str:
        if isinstance(payload, dict):
            for field in ("source", "system", "subsystem", "module"):
                value = payload.get(field)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value).strip()
        if subject:
            return str(subject).strip()
        return "nats"

    @staticmethod
    def _derive_event_subject(payload: Any, subject: Any) -> str:
        if isinstance(payload, dict):
            for field in ("subject", "name", "id", "event_id", "track_id", "mission_id", "task_id"):
                value = payload.get(field)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value).strip()
        if subject:
            return str(subject).strip()
        return I18N.UNKNOWN

    def _ack_incident(self, key: str) -> bool:
        k = (key or "").strip()
        if not k:
            return False
        if self._incident_store is None:
            return False
        return self._incident_store.ack(k)

    def _clear_acked_incidents(self) -> int:
        if self._incident_store is None:
            return 0
        return self._incident_store.clear_acked_cleared()

    def action_toggle_events_live(self) -> None:
        self._events_live = not self._events_live
        if self._events_live:
            self._events_unread_count = 0
            self._events_unread_incident_ids.clear()
            self._render_events_table()
            if self.active_screen == "events":
                self._refresh_inspector()
            self._console_log(f"{I18N.bidi('Events live', 'События живое')}", level="info")
        else:
            self._events_unread_count = 0
            self._events_unread_incident_ids.clear()
            self._console_log(f"{I18N.bidi('Events paused', 'События пауза')}", level="info")
        try:
            self.query_one("#orion-sidebar", OrionSidebar).refresh()
        except Exception:
            pass

    def action_acknowledge_selected_incident(self) -> None:
        if self.active_screen != "events":
            return
        if isinstance(self.focused, Input):
            return
        ctx = self._selection_by_app.get("events")
        key = ctx.key if ctx is not None else ""
        if not key or key == "seed":
            self._console_log(f"{I18N.bidi('No incident selected', 'Инцидент не выбран')}", level="info")
            return
        if self._ack_incident(key):
            self._console_log(f"{I18N.bidi('Acknowledged', 'Подтверждено')}: {key}", level="info")
            self._render_events_table()
            self._refresh_inspector()
        else:
            self._console_log(
                f"{I18N.bidi('Unknown incident key', 'Неизвестный ключ инцидента')}: {key}",
                level="info",
            )

    def _confirm_acknowledge_selected_incident(self) -> None:
        if self.active_screen != "events":
            return
        if isinstance(self.focused, Input):
            return
        ctx = self._selection_by_app.get("events")
        key = ctx.key if ctx is not None else ""
        if not key or key == "seed":
            self._console_log(f"{I18N.bidi('No incident selected', 'Инцидент не выбран')}", level="info")
            return
        incident = self._incident_store.get(key) if self._incident_store is not None else None
        if incident is None:
            self._console_log(
                f"{I18N.bidi('Unknown incident key', 'Неизвестный ключ инцидента')}: {key}",
                level="info",
            )
            return
        if bool(getattr(incident, "acked", False)):
            self._console_log(f"{I18N.bidi('Already acknowledged', 'Уже подтверждено')}: {key}", level="info")
            return

        prompt = (
            f"{I18N.bidi('Acknowledge incident?', 'Подтвердить инцидент?')} {key} "
            f"({I18N.bidi('Y/N', 'Да/Нет')})"
        )

        def after(decision: bool) -> None:
            if decision:
                self.action_acknowledge_selected_incident()
            else:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")

        self.push_screen(ConfirmDialog(prompt), after)

    def _confirm_power_toggle(self, *, row_key: str, current: object) -> None:
        if self.active_screen != "power":
            return
        if isinstance(self.focused, Input):
            return
        key = (row_key or "").strip()
        if not key or key == "seed":
            return
        if key not in {"dock_connected", "nbl_active"}:
            self._console_log(
                f"{I18N.bidi('No action for row', 'Нет действия для строки')}: {key}",
                level="info",
            )
            return

        if current is None:
            self._console_log(
                f"{I18N.bidi('No telemetry for toggle', 'Нет телеметрии для переключения')}: {key}",
                level="warn",
            )
            return

        is_on = bool(current)
        if key == "dock_connected":
            cmd = "power.dock.off" if is_on else "power.dock.on"
            title = I18N.bidi("Dock", "Стыковка")
        else:
            cmd = "power.nbl.off" if is_on else "power.nbl.on"
            title = I18N.bidi("NBL", "NBL")

        prompt = (
            f"{I18N.bidi('Send command?', 'Отправить команду?')} "
            f"{title} → {I18N.yes_no(not is_on)} ({cmd}) "
            f"({I18N.bidi('Y/N', 'Да/Нет')})"
        )

        def after(decision: bool) -> None:
            if not decision:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")
                return
            try:
                asyncio.create_task(self._publish_sim_command(cmd))
            except Exception as exc:
                self._console_log(
                    f"{I18N.bidi('Failed to schedule command', 'Не удалось отправить команду')}: {exc}",
                    level="error",
                )

        self.push_screen(ConfirmDialog(prompt), after)

    def action_clear_acknowledged_incidents(self) -> None:
        if self.active_screen != "events":
            return
        if isinstance(self.focused, Input):
            return
        cleared = self._clear_acked_incidents()
        self._console_log(
            f"{I18N.bidi('Cleared acknowledged incidents', 'Очищено подтвержденных инцидентов')}: {cleared}",
            level="info",
        )
        self._render_events_table()
        self._refresh_inspector()

    def action_mark_events_read(self) -> None:
        if self.active_screen != "events":
            return
        if isinstance(self.focused, Input):
            return
        if self._events_live:
            return
        self._events_unread_count = 0
        self._events_unread_incident_ids.clear()
        try:
            self.query_one("#orion-sidebar", OrionSidebar).refresh()
        except Exception:
            pass
        if self.active_screen == "events":
            self._refresh_inspector()
        self._console_log(f"{I18N.bidi('Unread cleared', 'Непрочитано очищено')}", level="info")

    def _apply_rule_enabled_change(self, rule_id: str, enabled: bool) -> None:
        rid = (rule_id or "").strip()
        if not rid:
            return
        try:
            result = self._rules_repo.set_rule_enabled(rid, bool(enabled), source="ui/toggle")
            self._incident_rules = result.config
            self._incident_store = IncidentStore(result.config)
            ctx = self._selection_by_app.get("rules")
            if ctx is not None and ctx.key == rid:
                refreshed_rule = None
                for rule in result.config.rules:
                    if str(getattr(rule, "id", "")) == rid:
                        refreshed_rule = rule
                        break
                if refreshed_rule is not None:
                    self._selection_by_app["rules"] = SelectionContext(
                        app_id="rules",
                        key=rid,
                        kind="rule",
                        source="rules",
                        created_at_epoch=time.time(),
                        payload=refreshed_rule,
                        ids=(rid,),
                    )
            self._render_rules_table()
            if self.active_screen == "rules":
                self._refresh_inspector()
            self._console_log(
                f"{I18N.bidi('Rule updated', 'Правило обновлено')}: {rid} "
                f"{I18N.bidi('enabled', 'включено')}={I18N.yes_no(bool(enabled))} "
                f"({I18N.bidi('hash', 'хэш')}: {result.new_hash[:8]})",
                level="info",
            )
        except Exception as exc:
            self._console_log(
                f"{I18N.bidi('Failed to update rule', 'Ошибка обновления правила')}: {rid} — {exc}",
                level="error",
            )

    def action_toggle_selected_rule_enabled(self) -> None:
        if self.active_screen != "rules":
            return
        if isinstance(self.focused, Input):
            return
        if self._incident_rules is None:
            return
        ctx = self._selection_by_app.get("rules")
        rid = (ctx.key if ctx is not None else "").strip()
        if not rid or rid == "seed":
            self._console_log(f"{I18N.bidi('No rule selected', 'Правило не выбрано')}", level="info")
            return
        selected_rule = None
        for rule in self._incident_rules.rules:
            if str(getattr(rule, "id", "")) == rid:
                selected_rule = rule
                break
        if selected_rule is None:
            self._console_log(f"{I18N.bidi('Unknown rule', 'Неизвестное правило')}: {rid}", level="info")
            return
        current_enabled = bool(getattr(selected_rule, "enabled", True))
        target_enabled = not current_enabled
        prompt = (
            f"{I18N.bidi('Save changes?', 'Сохранить изменения?')} "
            f"{I18N.bidi('Toggle rule', 'Переключить правило')} {rid} → "
            f"{I18N.bidi('enabled', 'включено')}={I18N.yes_no(target_enabled)} "
            f"({I18N.bidi('Y/N', 'Да/Нет')})"
        )

        def after(decision: bool) -> None:
            if decision:
                self._apply_rule_enabled_change(rid, target_enabled)
            else:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")

        self.push_screen(ConfirmDialog(prompt), after)

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
        self._console_log(
            f"↩️ {I18N.bidi('Control response', 'Ответ управления')}: "
            f"{I18N.bidi('success', 'успех')}={success} {I18N.bidi('request', 'запрос')}={request} {message or ''}".strip()
        )

    def action_show_screen(self, screen: str) -> None:
        if screen not in {app.screen for app in ORION_APPS}:
            self._console_log(f"{I18N.bidi('Unknown screen', 'Неизвестный экран')}: {screen}", level="info")
            return
        self.active_screen = screen
        try:
            self.query_one("#orion-sidebar", OrionSidebar).set_active(screen)
        except Exception:
            pass
        for sid in (
            "system",
            "radar",
            "events",
            "console",
            "summary",
            "power",
            "sensors",
            "propulsion",
            "thermal",
            "diagnostics",
            "mission",
            "rules",
        ):
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
        if screen == "sensors":
            self._render_sensors_table()

            # Make selection/Inspector discoverable: focus + initial highlight.
            # Important: do it after layout refresh, иначе фокус может уйти в sidebar.
            def _focus_sensors() -> None:
                try:
                    table = self.query_one("#sensors-table", DataTable)
                    self.set_focus(table)
                    cursor_row = getattr(table, "cursor_row", None)
                    if (cursor_row is None or cursor_row < 0) and table.row_count:
                        table.move_cursor(row=0, column=0, animate=False, scroll=False)
                except Exception:
                    pass

            self.call_after_refresh(_focus_sensors)
        if screen == "propulsion":
            self._render_propulsion_table()
        if screen == "thermal":
            self._render_thermal_table()
        if screen == "diagnostics":
            self._render_diagnostics_table()
        if screen == "mission":
            self._render_mission_table()
        if screen == "rules":
            self._render_rules_table()

            # Rules interactions (toggle with confirmation) must be available without
            # requiring the operator to manually fight focus first.
            def _focus_rules() -> None:
                try:
                    table = self.query_one("#rules-table", DataTable)
                    self.set_focus(table)
                    table.move_cursor(row=0, column=0, animate=False, scroll=False)
                except Exception:
                    pass

            self.call_after_refresh(_focus_rules)

        self._refresh_inspector()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "rules-reload":
            return
        self._load_incident_rules(initial=False)
        self._render_rules_table()

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
        elif self.active_screen == "thermal":
            workspace = safe_query("#thermal-table")
        elif self.active_screen == "diagnostics":
            workspace = safe_query("#diagnostics-table")
        elif self.active_screen == "mission":
            workspace = safe_query("#mission-table")
        elif self.active_screen == "rules":
            workspace = safe_query("#rules-table")
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

    def action_focus_command(self) -> None:
        try:
            self.set_focus(self.query_one("#command-dock", Input))
        except Exception:
            pass

    def action_help(self) -> None:
        self._show_help()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "rules-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            if self._incident_rules is None:
                return
            selected_rule = None
            for rule in self._incident_rules.rules:
                if str(getattr(rule, "id", "")) == row_key:
                    selected_rule = rule
                    break
            if selected_rule is None:
                return
            self._set_selection(
                SelectionContext(
                    app_id="rules",
                    key=row_key,
                    kind="rule",
                    source="rules",
                    created_at_epoch=time.time(),
                    payload=selected_rule,
                    ids=(row_key,),
                )
            )
            return

        if event.data_table.id == "events-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            incident = self._incident_store.get(row_key) if self._incident_store is not None else None
            if incident is not None:
                self._set_selection(
                    SelectionContext(
                        app_id="events",
                        key=row_key,
                        kind="incident",
                        source=incident.source or I18N.NA,
                        created_at_epoch=incident.first_seen,
                        payload=incident,
                        ids=(incident.rule_id, incident.type or I18N.NA, incident.subject or I18N.NA),
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

        if event.data_table.id == "sensors-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._sensors_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="sensors",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "propulsion-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._propulsion_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="propulsion",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "thermal-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._thermal_by_key.get(row_key)
            if isinstance(selected, dict):
                created_at_epoch = time.time()
                env = selected.get("envelope")
                if isinstance(env, EventEnvelope):
                    created_at_epoch = float(env.ts_epoch)
                self._set_selection(
                    SelectionContext(
                        app_id="thermal",
                        key=row_key,
                        kind="thermal_node",
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id

        if table_id == "rules-table":
            self.action_toggle_selected_rule_enabled()
            return

        if table_id == "events-table":
            self._confirm_acknowledge_selected_incident()
            return

        if table_id == "sensors-table":
            self.action_toggle_sensors_compact()
            return

        if table_id == "power-table":
            try:
                row_key = str(event.row_key)
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._power_by_key.get(row_key, {})
            current = selected.get("raw")
            self._confirm_power_toggle(row_key=row_key, current=current)
            return

    def _sensors_compact_enabled(self) -> bool:
        if self._sensors_compact_override is not None:
            return bool(self._sensors_compact_override)
        # Default to compact to keep Sensors screen glanceable; details are available via Inspector or toggle.
        raw_default = os.getenv("ORION_SENSORS_COMPACT_DEFAULT", "1").strip().lower()
        default_compact = raw_default not in {"0", "false", "no", "off"}
        if self._density in {"tiny", "narrow"}:
            return True
        return default_compact

    def action_toggle_sensors_compact(self) -> None:
        current = self._sensors_compact_enabled()
        self._sensors_compact_override = not current
        self._render_sensors_table()

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
            f"{I18N.bidi('Rules', 'Правила')}: "
            f"{I18N.bidi('reload rules', 'перезагрузить правила')}",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Simulation', 'Симуляция')}: "
            f"simulation.start/симуляция.старт | simulation.pause/симуляция.пауза | simulation.stop/симуляция.стоп | simulation.reset/симуляция.сброс",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Filters', 'Фильтры')}: "
            f"type/тип <name/имя> | type off/тип отключить | filter/фильтр <text/текст> | filter off/фильтр отключить",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Events mode', 'Режим событий')}: "
            f"{I18N.bidi('live', 'живое')} | {I18N.bidi('pause', 'пауза')} | Ctrl+Y",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Incidents', 'Инциденты')}: "
            f"{I18N.bidi('Acknowledge', 'Подтвердить')} acknowledge <key/ключ> | подтвердить <ключ> | "
            f"{I18N.bidi('Clear acknowledged', 'Очистить подтвержденные')} clear/очистить",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Incidents quick actions', 'Быстрые действия по инцидентам')}: "
            f"A — {I18N.bidi('acknowledge selected incident', 'подтвердить выбранный инцидент')} | "
            f"X — {I18N.bidi('clear acknowledged incidents', 'очистить подтвержденные инциденты')} | "
            f"R — {I18N.bidi('mark events read (paused)', 'отметить прочитанным (пауза)')}",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('QIKI intent', 'Намерение QIKI')}: q: <text> | // <text>",
            level="info",
        )
        self._console_log(f"{I18N.bidi('Menu glossary', 'Глоссарий меню')}: ", level="info")
        self._console_log(f"- Sys/Систем: {I18N.bidi('System', 'Система')}", level="info")
        self._console_log(f"- Events/Событ: {I18N.bidi('Events', 'События')}", level="info")
        self._console_log(f"- Power/Пит: {I18N.bidi('Power systems', 'Система питания')}", level="info")
        self._console_log(f"- Diag/Диагн: {I18N.bidi('Diagnostics', 'Диагностика')}", level="info")
        self._console_log(f"- Mission/Миссия: {I18N.bidi('Mission control', 'Управление миссией')}", level="info")
        self._console_log(f"{I18N.bidi('Panels glossary', 'Глоссарий панелей')}: ", level="info")
        self._console_log(f"- Upd/Обн: {I18N.bidi('Updated', 'Обновлено')}", level="info")
        self._console_log(f"- SoC/Заряд: {I18N.bidi('State of charge', 'Уровень заряда')}", level="info")
        self._console_log(f"- P in/Вх мощн: {I18N.bidi('Power input', 'Входная мощность')}", level="info")
        self._console_log(f"- P out/Вых мощн: {I18N.bidi('Power output/consumption', 'Выходная/потребляемая мощность')}", level="info")
        self._console_log(f"- Bus V/Шина В: {I18N.bidi('Bus voltage', 'Напряжение шины')}", level="info")
        self._console_log(f"- Bus A/Шина А: {I18N.bidi('Bus current', 'Ток шины')}", level="info")
        self._console_log(f"- Ext temp/Нар темп: {I18N.bidi('External temperature', 'Наружная температура')}", level="info")
        self._console_log(f"- Core temp/Темп ядра: {I18N.bidi('Core temperature', 'Температура ядра')}", level="info")
        self._console_log(f"- CPU/ЦП: {I18N.bidi('CPU usage', 'Загрузка процессора')}", level="info")
        self._console_log(f"- Mem/Пам: {I18N.bidi('Memory usage', 'Загрузка памяти')}", level="info")
        self._console_log(f"{I18N.bidi('Header glossary', 'Глоссарий хедера')}: ", level="info")
        self._console_log(
            f"- {I18N.bidi('Link', 'Связь')}: {I18N.bidi('Link status', 'Состояние связи')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Bat', 'Бат')}: {I18N.bidi('Battery level', 'Уровень батареи')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Hull', 'Корпус')}: {I18N.bidi('Hull integrity', 'Целостность корпуса')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Rad', 'Рад')}: {I18N.bidi('Radiation dose rate', 'Мощность дозы радиации')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Ext temp', 'Нар темп')}: {I18N.bidi('External temperature', 'Наружная температура')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Core temp', 'Темп ядра')}: {I18N.bidi('Core temperature', 'Температура ядра')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Age', 'Возраст')}: {I18N.bidi('Telemetry age', 'Возраст телеметрии')} ({I18N.bidi('compact units', 'краткие единицы')}: sec/с, min/мин, h/ч)",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Fresh', 'Свеж')}: {I18N.bidi('Telemetry freshness', 'Свежесть телеметрии')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Pos', 'Поз')}: {I18N.bidi('Position', 'Позиция')} ({I18N.bidi('meters', 'метры')}: m/м)",
            level="info",
        )
        self._console_log(f"{I18N.bidi('Tables glossary', 'Глоссарий таблиц')}: ", level="info")
        self._console_log(
            f"- Ack/Подтв: {I18N.bidi('Acknowledged', 'Подтверждено')}",
            level="info",
        )
        self._console_log(
            f"- Vr/Скорость: {I18N.bidi('Radial velocity', 'Радиальная скорость')}",
            level="info",
        )
        self._console_log(f"{I18N.bidi('Units glossary', 'Глоссарий единиц')}: ", level="info")
        self._console_log(
            f"- m/s/м/с: {I18N.bidi('meters per second', 'метры в секунду')}",
            level="info",
        )
        self._console_log(
            f"- °: {I18N.bidi('degrees', 'градусы')}",
            level="info",
        )
        self._console_log(
            f"- m/м: {I18N.bidi('meters', 'метры')}",
            level="info",
        )
        self._console_log(
            f"- sec/с: {I18N.bidi('seconds', 'секунды')}",
            level="info",
        )
        self._console_log(
            f"- min/мин: {I18N.bidi('minutes', 'минуты')}",
            level="info",
        )
        self._console_log(
            f"- W/Вт: {I18N.bidi('watts', 'ватты')}",
            level="info",
        )
        self._console_log(
            f"- V/В: {I18N.bidi('volts', 'вольты')}",
            level="info",
        )
        self._console_log(
            f"- A/А: {I18N.bidi('amperes', 'амперы')}",
            level="info",
        )

    async def _run_command(self, raw: str) -> None:
        cmd = (raw or "").strip()
        if not cmd:
            return

        is_qiki, qiki_text = self._parse_qiki_intent(cmd)
        if is_qiki:
            if not qiki_text:
                self._console_log(
                    f"{I18N.bidi('QIKI intent', 'Намерение QIKI')}: {I18N.bidi('empty', 'пусто')}",
                    level="info",
                )
                return
            await self._publish_qiki_intent(qiki_text)
            return

        self._console_log(f"{I18N.bidi('command', 'команда')}> {cmd}", level="info")

        low = cmd.lower()
        if low in {"help", "помощь", "?", "h"}:
            self._show_help()
            return

        if low in {"events", "события"}:
            state = I18N.bidi("Live", "Живое") if self._events_live else I18N.bidi("Paused", "Пауза")
            unread = self._events_unread_count if not self._events_live else 0
            self._console_log(
                f"{I18N.bidi('Events mode', 'Режим событий')}: {state} "
                f"({I18N.bidi('Unread', 'Непрочитано')}: {unread})",
                level="info",
            )
            return

        if low in {
            "events live",
            "events.live",
            "events on",
            "события живое",
            "события.живое",
            "события вживую",
            "события включить",
        }:
            if not self._events_live:
                self.action_toggle_events_live()
            else:
                self._console_log(f"{I18N.bidi('Events live', 'События живое')}", level="info")
            return

        if low in {
            "events pause",
            "events.pause",
            "events paused",
            "events.paused",
            "events off",
            "события пауза",
            "события.пауза",
            "события выключить",
        }:
            if self._events_live:
                self.action_toggle_events_live()
            else:
                self._console_log(f"{I18N.bidi('Events paused', 'События пауза')}", level="info")
            return

        if low == "ack" or low.startswith("ack ") or low == "acknowledge" or low.startswith("acknowledge "):
            _, _, tail = cmd.partition(" ")
            key = tail.strip()
            if not key:
                ctx = self._selection_by_app.get("events")
                key = ctx.key if ctx is not None else ""
            if not key:
                self._console_log(f"{I18N.bidi('No incident selected', 'Инцидент не выбран')}", level="info")
                return
            if self._ack_incident(key):
                self._console_log(f"{I18N.bidi('Acknowledged', 'Подтверждено')}: {key}", level="info")
                self._render_events_table()
                if self.active_screen == "events":
                    self._refresh_inspector()
            else:
                self._console_log(
                    f"{I18N.bidi('Unknown incident key', 'Неизвестный ключ инцидента')}: {key}",
                    level="info",
                )
            return

        if low == "подтвердить" or low.startswith("подтвердить "):
            _, _, tail = cmd.partition(" ")
            key = tail.strip()
            if not key:
                ctx = self._selection_by_app.get("events")
                key = ctx.key if ctx is not None else ""
            if not key:
                self._console_log(f"{I18N.bidi('No incident selected', 'Инцидент не выбран')}", level="info")
                return
            if self._ack_incident(key):
                self._console_log(f"{I18N.bidi('Acknowledged', 'Подтверждено')}: {key}", level="info")
                self._render_events_table()
                if self.active_screen == "events":
                    self._refresh_inspector()
            else:
                self._console_log(
                    f"{I18N.bidi('Unknown incident key', 'Неизвестный ключ инцидента')}: {key}",
                    level="info",
                )
            return

        if low in {"clear", "очистить"} or low.startswith("clear ") or low.startswith("очистить "):
            cleared = self._clear_acked_incidents()
            self._console_log(
                f"{I18N.bidi('Cleared acknowledged incidents', 'Очищено подтвержденных инцидентов')}: {cleared}"
            )
            self._render_events_table()
            if self.active_screen == "events":
                self._refresh_inspector()
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

        if low in {"reload rules", "rules reload", "rules refresh", "перезагрузить правила", "правила перезагрузить"}:
            self._load_incident_rules(initial=False)
            return

        # screen/экран <name>
        if low.startswith("screen ") or low.startswith("экран "):
            _, _, tail = cmd.partition(" ")
            token = tail.strip()
            screen = self._normalize_screen_token(token)
            if screen is None:
                self._console_log(
                    f"{I18N.bidi('Unknown screen', 'Неизвестный экран')}: {token or I18N.NA}",
                    level="info",
                )
                return
            self.action_show_screen(screen)
            return

        # Allow bare screen aliases: "system" / "система" / "radar" / ...
        if (screen := self._normalize_screen_token(low)) is not None:
            self.action_show_screen(screen)
            return

        # nbl.max <W> (Power Plane runtime control; no mocks).
        if low.startswith(("nbl.max ", "nbl.limit ", "nbl.set ")):
            _, _, tail = cmd.partition(" ")
            raw_w = tail.strip()
            try:
                max_w = float(raw_w)
            except Exception:
                self._console_log(
                    f"{I18N.bidi('Invalid value', 'Некорректное значение')}: {raw_w or I18N.NA}",
                    level="warn",
                )
                return
            await self._publish_sim_command("power.nbl.set_max", parameters={"max_power_w": max_w})
            return

        # xpdr.mode <on|off|silent|spoof> (Comms/XPDR runtime control; no mocks).
        if low.startswith("xpdr.mode"):
            parsed = self._parse_xpdr_cli_command(cmd)
            if parsed is None:
                self._console_log(
                    f"{I18N.bidi('Invalid XPDR command', 'Некорректная команда XPDR')}: {cmd}",
                    level="warn",
                )
                return
            await self._publish_sim_command("sim.xpdr.mode", parameters={"mode": parsed["mode"]})
            return

        # rcs.<axis> <pct> [<duration>] | rcs.stop  (Propulsion/RCS operator control; no mocks).
        if low.startswith("rcs."):
            parsed = self._parse_rcs_cli_command(cmd)
            if parsed is None:
                self._console_log(
                    f"{I18N.bidi('Invalid RCS command', 'Некорректная команда RCS')}: {cmd}",
                    level="warn",
                )
                return
            if parsed["kind"] == "stop":
                await self._publish_sim_command("sim.rcs.stop")
                return
            await self._publish_sim_command(
                "sim.rcs.fire",
                parameters={
                    "axis": parsed["axis"],
                    "pct": parsed["pct"],
                    "duration_s": parsed["duration_s"],
                },
            )
            return

        # Docking Plane (mechanical) operator control (no mocks).
        # Supported:
        # - dock.engage [A|B]
        # - dock.release
        if low.startswith("dock.engage") or low.startswith("dock.release"):
            parsed = self._parse_docking_cli_command(cmd)
            if parsed is None:
                self._console_log(
                    f"{I18N.bidi('Invalid docking command', 'Некорректная команда стыковки')}: {cmd}",
                    level="warn",
                )
                return
            if parsed["kind"] == "release":
                await self._publish_sim_command("sim.dock.release")
                return
            await self._publish_sim_command(
                "sim.dock.engage",
                parameters={"port": parsed["port"]} if parsed.get("port") else {},
            )
            return

        if (sim_cmd := self._canonicalize_sim_command(low)) is not None:
            await self._publish_sim_command(sim_cmd)
            return

        self._console_log(f"{I18N.bidi('Unknown command', 'Неизвестная команда')}: {cmd}", level="info")

    async def _publish_qiki_intent(self, text: str) -> None:
        if not text:
            return
        self._console_log(f"{I18N.bidi('QIKI intent', 'Намерение QIKI')}> {text}", level="info")
        if not self.nats_client:
            self._console_log(f"❌ {I18N.bidi('NATS not initialized', 'NATS не инициализирован')}", level="error")
            return
        try:
            await self.nats_client.publish_command(
                QIKI_INTENTS,
                {
                    "text": text,
                    "source": "operator-console",
                    "ts_epoch": time.time(),
                },
            )
            self._console_log(f"📤 {I18N.bidi('Sent to QIKI', 'Отправлено в QIKI')}: {QIKI_INTENTS}", level="info")
        except Exception as e:
            self._console_log(
                f"❌ {I18N.bidi('Failed to send', 'Не удалось отправить')}: {e}",
                level="error",
            )

    def _update_command_placeholder(self) -> None:
        try:
            dock = self.query_one("#command-dock", Input)
        except Exception:
            return

        density = getattr(self, "_density", "wide")

        prefix = f"{I18N.bidi('command', 'команда')}> "
        help_part = I18N.bidi("help", "помощь")
        screen_part = f"{I18N.bidi('screen', 'экран')} <name>/<имя>"
        sim_part = "simulation.start/симуляция.старт"
        qiki_part = f"{I18N.bidi('QIKI', 'QIKI')} q: <text>"

        # Keep the command line readable in tmux splits: show less on narrow/tiny.
        if density == "tiny":
            parts = [help_part, screen_part]
        elif density == "narrow":
            parts = [help_part, screen_part, sim_part, qiki_part]
        elif density == "normal":
            parts = [
                help_part,
                screen_part,
                sim_part,
                "dock.engage [A|B]",
                "dock.release",
                "xpdr.mode <on|off|silent|spoof>",
                "rcs.<axis> <pct> <dur>",
                "rcs.stop",
                qiki_part,
            ]
        else:
            parts = [
                help_part,
                screen_part,
                sim_part,
                "dock.engage [A|B]",
                "dock.release",
                "dock.on/off",
                "nbl.on/off",
                "nbl.max <W>",
                "xpdr.mode <on|off|silent|spoof>",
                "rcs.<axis> <pct> <dur>",
                "rcs.stop",
                qiki_part,
            ]

        placeholder = prefix + " | ".join(parts)

        # Pre-ellipsize so the line doesn't end with broken tokens like a dangling "|".
        width = int(getattr(self.size, "width", 0) or 0)
        max_chars = 200
        if width:
            # Approximate visible width: borders/padding eat a few columns.
            max_chars = max(48, width - 10)

        if len(placeholder) > max_chars:
            placeholder = placeholder[: max(0, max_chars - 1)] + "…"

        dock.placeholder = placeholder

    @staticmethod
    def _parse_qiki_intent(raw: str) -> tuple[bool, Optional[str]]:
        trimmed = (raw or "").strip()
        if not trimmed:
            return False, None
        if trimmed.lower().startswith("q:"):
            text = trimmed[2:].strip()
            return True, text or None
        if trimmed.startswith("//"):
            text = trimmed[2:].strip()
            return True, text or None
        return False, None

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
            # Power Plane runtime control (no mocks): Dock / NBL.
            "dock.on": "power.dock.on",
            "dock.off": "power.dock.off",
            "док.вкл": "power.dock.on",
            "док.выкл": "power.dock.off",
            "стыковка.вкл": "power.dock.on",
            "стыковка.выкл": "power.dock.off",
            "nbl.on": "power.nbl.on",
            "nbl.off": "power.nbl.off",
            "нбл.вкл": "power.nbl.on",
            "нбл.выкл": "power.nbl.off",
        }
        return mapping.get(key)

    @staticmethod
    def _parse_duration_s(token: str) -> Optional[float]:
        raw = (token or "").strip().lower()
        if not raw:
            return None
        try:
            if raw.endswith("ms"):
                return float(raw[:-2].strip()) / 1000.0
            if raw.endswith("s"):
                return float(raw[:-1].strip())
            return float(raw)
        except Exception:
            return None

    @classmethod
    def _parse_docking_cli_command(cls, raw: str) -> Optional[dict[str, Any]]:
        """
        Parse operator CLI Docking command.

        Supported:
        - dock.engage [<port>]
        - dock.release
        """
        text = (raw or "").strip()
        low = text.lower()
        if low == "dock.release":
            return {"kind": "release"}
        parts = text.split()
        if not parts:
            return None
        head = parts[0].strip().lower()
        if head != "dock.engage":
            return None
        port = None
        if len(parts) >= 2:
            token = parts[1].strip()
            port = token or None
        return {"kind": "engage", "port": port}

    @classmethod
    def _parse_xpdr_cli_command(cls, raw: str) -> Optional[dict[str, Any]]:
        """
        Parse operator CLI Comms/XPDR command.

        Supported:
        - xpdr.mode <on|off|silent|spoof>
        """
        text = (raw or "").strip()
        parts = text.split()
        if len(parts) < 2:
            return None
        head = parts[0].strip().lower()
        if head != "xpdr.mode":
            return None
        mode = parts[1].strip().lower()
        if mode not in {"on", "off", "silent", "spoof"}:
            return None
        return {"mode": mode.upper()}

    @classmethod
    def _parse_rcs_cli_command(cls, raw: str) -> Optional[dict[str, Any]]:
        """
        Parse operator CLI RCS command.

        Supported:
        - rcs.<axis> <pct> [<duration>]    duration default is 1.0s (safety; no indefinite fire)
        - rcs.stop
        """
        text = (raw or "").strip()
        low = text.lower()
        if low == "rcs.stop":
            return {"kind": "stop"}

        parts = text.split()
        if not parts:
            return None
        head = parts[0].strip().lower()
        if not head.startswith("rcs."):
            return None
        axis = head.split(".", 1)[1].strip().lower()
        if axis not in {"forward", "aft", "port", "starboard", "up", "down"}:
            return None
        if len(parts) < 2:
            return None
        try:
            pct = float(parts[1])
        except Exception:
            return None
        pct = max(0.0, min(100.0, pct))

        duration_s = 1.0
        if len(parts) >= 3:
            parsed = cls._parse_duration_s(parts[2])
            if parsed is None:
                return None
            duration_s = parsed
        if duration_s <= 0.0:
            return None

        return {"kind": "fire", "axis": axis, "pct": pct, "duration_s": duration_s}

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-dock":
            return

        raw = (event.value or "").strip()
        event.input.value = ""
        self._warned_command_trim = False
        if not raw:
            return

        await self._run_command(raw)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "command-dock":
            return
        if self._command_max_chars <= 0:
            return
        value = event.value or ""
        if len(value) <= self._command_max_chars:
            return
        trimmed = value[: self._command_max_chars]
        try:
            event.input.value = trimmed
            event.input.cursor_position = len(trimmed)
        except Exception:
            pass
        if not self._warned_command_trim:
            self._warned_command_trim = True
            self._console_log(
                f"{I18N.bidi('Input trimmed', 'Ввод обрезан')}: "
                f"{self._command_max_chars} {I18N.bidi('characters', 'символов')}",
                level="warn",
            )

    async def _publish_sim_command(
        self, cmd_name: str, *, parameters: Optional[dict[str, Any]] = None
    ) -> None:
        if not self.nats_client:
            self._console_log(f"❌ {I18N.bidi('NATS not initialized', 'NATS не инициализирован')}", level="error")
            return

        destination = "q_sim_service" if cmd_name.startswith(("sim.", "power.")) else "faststream_bridge"
        cmd = CommandMessage(
            command_name=cmd_name,
            parameters=parameters or {},
            metadata=MessageMetadata(
                message_type="control_command",
                source="operator_console.orion",
                destination=destination,
            ),
        )
        try:
            await self.nats_client.publish_command(COMMANDS_CONTROL, cmd.model_dump(mode="json"))
            self._console_log(f"📤 {I18N.bidi('Published', 'Отправлено')}: {cmd_name}", level="info")
        except Exception as e:
            self._console_log(
                f"❌ {I18N.bidi('Publish failed', 'Отправка не удалась')}: {e}",
                level="error",
            )


if __name__ == "__main__":
    OrionApp().run()
