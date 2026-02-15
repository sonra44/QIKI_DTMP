# ruff: noqa: E501
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import asdict
import json
import logging
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Literal, Optional, cast
from uuid import uuid4

from pydantic import ValidationError
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, RichLog, Static
from textual import events

from qiki.services.operator_console.clients.nats_client import NATSClient
from qiki.services.operator_console.core.incident_rules import FileRulesRepository, IncidentRulesConfig
from qiki.services.operator_console.core.incidents import IncidentStore
from qiki.services.operator_console.ui import i18n as I18N
from qiki.services.operator_console.ui.profile_panel import ProfilePanel
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiChatResponseV1
from qiki.shared.models.qiki_chat import QikiProposalDecisionV1, SelectionContext as QikiSelectionContext
from qiki.shared.models.qiki_chat import UiContext
from qiki.shared.models.telemetry import TelemetrySnapshotModel
from qiki.shared.record_replay import record_jsonl, replay_jsonl
from qiki.shared.nats_subjects import (
    COMMANDS_CONTROL,
    EVENTS_STREAM_NAME,
    EVENTS_V1_WILDCARD,
    OPENAI_API_KEY_UPDATE,
    OPERATOR_ACTIONS,
    QIKI_INTENTS,
    RADAR_TRACKS,
    RESPONSES_CONTROL,
    SYSTEM_MODE_EVENT,
    SYSTEM_TELEMETRY,
)

logger = logging.getLogger("orion")

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    from qiki.services.operator_console.ui.charts import PpiScopeRenderer
except Exception:
    # Radar is not a priority; ORION must still boot even if optional radar renderer is absent.
    PpiScopeRenderer = None  # type: ignore[assignment,misc]

try:
    from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer
except Exception:
    # Radar must never block ORION boot; keep a best-effort fallback.
    BraillePpiRenderer = None  # type: ignore[assignment,misc]

try:
    from qiki.services.operator_console.radar.unicode_ppi import pick_nearest_track_id
except Exception:
    pick_nearest_track_id = None  # type: ignore[assignment]

try:
    from qiki.services.operator_console.radar.bitmap_ppi import render_bitmap_ppi
except Exception:
    render_bitmap_ppi = None  # type: ignore[assignment]

try:
    from textual_image.widget import AutoImage as _RadarAutoImage
    from textual_image.widget import SixelImage as _RadarSixelImage
    from textual_image.widget import TGPImage as _RadarTGPImage
except Exception:
    _RadarAutoImage = None  # type: ignore[assignment]
    _RadarSixelImage = None  # type: ignore[assignment]
    _RadarTGPImage = None  # type: ignore[assignment]


def _textual_image_best_backend_kind() -> str | None:
    """Return bitmap backend kind selected by textual-image auto-detection, if any.

    We only accept true bitmap protocols here (Kitty TGP / SIXEL). If textual-image selects a
    Unicode/halfcell backend, we keep ORION on the Braille Unicode baseline (RFC).
    """

    try:
        from textual_image import renderable as _ti_renderable
    except Exception:
        return None
    mod = str(getattr(getattr(_ti_renderable, "Image", None), "__module__", "") or "")
    if mod.endswith(".tgp"):
        return "kitty"
    if mod.endswith(".sixel"):
        return "sixel"
    return None


def _is_ssh_tmux_operator_env() -> bool:
    """Return True when we are in the canonical Phase1 operator environment (SSH + tmux).

    RFC/ADR: in SSH+tmux we must keep the radar on the Unicode baseline by default, because
    bitmap protocols are often unreliable end-to-end.
    """

    try:
        import os

        tmux = (os.getenv("TMUX", "") or "").strip()
        if not tmux:
            return False
        ssh = any((os.getenv(k, "") or "").strip() for k in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"))
        return bool(ssh)
    except Exception:
        return False


def _emit_xterm_mouse_tracking(*, enabled: bool) -> None:
    """Best-effort: request mouse reporting from the operator terminal.

    Needed when ORION is started detached and the operator attaches later: the initial
    mouse-enable sequences won't reach the real terminal.
    """

    try:
        import sys

        if not getattr(sys.stdout, "isatty", lambda: False)():
            return
        if enabled:
            seq = "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
        else:
            seq = "\x1b[?1000l\x1b[?1002l\x1b[?1006l"
        sys.stdout.write(seq)
        sys.stdout.flush()
    except Exception:
        return


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


class SecretInputDialog(ModalScreen[str | None]):
    AUTO_FOCUS = "#secret-input"
    DEFAULT_CSS = """
    SecretInputDialog {
        align: center middle;
    }
    #secret-dialog {
        width: 78;
        padding: 1 2;
        border: round #ffb000;
        background: #050505;
    }
    #secret-title {
        padding: 0 0 1 0;
        color: #ffb000;
    }
    #secret-prompt {
        padding: 0 0 1 0;
        color: #ffffff;
    }
    #secret-actions {
        height: 3;
        align: center middle;
    }
    #secret-actions Button {
        margin: 0 1;
        width: 16;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel/Отмена", show=False),
        Binding("enter", "submit", "Submit/Отправить", show=False),
        Binding("ctrl+w", "cancel", "Cancel/Отмена", show=False),
        Binding("tab", "focus_next", "Next field/Далее", show=False),
        Binding("shift+tab", "focus_previous", "Prev field/Назад", show=False),
    ]

    def __init__(self, *, title: str, prompt: str) -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(id="secret-dialog"):
            yield Static(self._title, id="secret-title")
            yield Static(self._prompt, id="secret-prompt")
            yield Static(
                I18N.bidi(
                    "Esc/Ctrl+W to cancel; Enter to save",
                    "Esc/Ctrl+W — отмена; Enter — сохранить",
                )
            )
            yield Input(placeholder="sk-...", password=True, id="secret-input")
            with Horizontal(id="secret-actions"):
                yield Button(I18N.bidi("Save", "Сохранить"), id="secret-ok", variant="primary")
                yield Button(I18N.bidi("Cancel", "Отмена"), id="secret-cancel")

    def on_mount(self) -> None:
        # Ensure the secret input is focused; otherwise typing appears to do nothing.
        def _focus() -> None:
            try:
                self.set_focus(self.query_one("#secret-input", Input))
            except Exception:
                return

        self.call_after_refresh(_focus)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        value = (self.query_one("#secret-input", Input).value or "").strip()
        self.dismiss(value or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "secret-cancel":
            self.dismiss(None)
        elif event.button.id == "secret-ok":
            value = (self.query_one("#secret-input", Input).value or "").strip()
            self.dismiss(value or None)


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
                logger.debug("orion_exception_swallowed", exc_info=True)

    async def _sleep_chunked(self, seconds: float) -> None:
        # Keep UI responsive.
        remaining = max(0.0, float(seconds))
        while remaining > 0:
            step = min(0.1, remaining)
            try:
                await asyncio.sleep(step)
            except asyncio.CancelledError:
                return
            remaining -= step

    async def _run(self) -> None:
        try:
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
                log.add_line(
                    I18N.bidi(f"NET: NATS connect failed [FAIL]{tail}", f"NET: NATS не подключился [СБОЙ]{tail}"),
                    style="bold red",
                )

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
                post_raw = payload.get("post_results")
                post_list: list[Any] = cast(list[Any], post_raw) if isinstance(post_raw, list) else []
                if isinstance(all_go, bool):
                    if all_go:
                        log.add_line(
                            I18N.bidi(
                                f"BIOS: POST complete [OK] (devices: {len(post_list)})",
                                f"BIOS: POST завершён [OK] (устройств: {len(post_list)})",
                            ),
                            style="bold green",
                        )
                    else:
                        log.add_line(
                            I18N.bidi(
                                f"BIOS: POST complete [FAIL] (devices: {len(post_list)})",
                                f"BIOS: POST завершён [СБОЙ] (устройств: {len(post_list)})",
                            ),
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
                for row in post_list:
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

                remaining = len(post_list) - len(shown)
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

            log.add_line(
                I18N.bidi(
                    "HANDOVER: Switching to operator view...",
                    "ПЕРЕДАЧА: Переход в режим оператора...",
                ),
                style="dim",
            )
            await self._sleep_chunked(0.4)
            self.dismiss(True)
        except asyncio.CancelledError:
            return


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
        screen="qiki",
        title=I18N.bidi("QIKI", "QIKI"),
        hotkey="f9",
        hotkey_label="F9",
        aliases=("qiki", "кики", "q"),
    ),
    OrionAppSpec(
        screen="profile",
        title=I18N.bidi("Profile", "Профиль"),
        hotkey="f10",
        hotkey_label="F10",
        aliases=("profile", "профиль", "bot", "бот", "spec", "спек"),
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
        hotkey="ctrl+q",
        hotkey_label="Ctrl+Q",
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
    "qiki": I18N.bidi("QIKI", "QIKI"),
    "profile": I18N.bidi("Prof", "Проф"),
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
    "qiki": I18N.bidi("QIKI", "QIKI"),
    "profile": I18N.bidi("Profile", "Профиль"),
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
    "qiki": "QIKI",
    "profile": "Профиль",
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
    mode = reactive(I18N.NA)
    sim = reactive(I18N.NA)

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
            yield OrionHeaderCell(id="hdr-mode")
            yield OrionHeaderCell(id="hdr-sim")

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
            f"{I18N.bidi('Battery', 'Батарея')} {self.battery}",
            tooltip=f"{I18N.bidi('Battery level', 'Уровень батареи')}: {self.battery}",
        )
        set_cell(
            "hdr-hull",
            f"{I18N.bidi('Hull', 'Корпус')} {self.hull}",
            tooltip=f"{I18N.bidi('Hull integrity', 'Целостность корпуса')}: {self.hull}",
        )
        set_cell(
            "hdr-radiation",
            f"{I18N.bidi('Radiation', 'Радиация')} {self.rad}",
            tooltip=f"{I18N.bidi('Radiation dose rate', 'Мощность дозы радиации')}: {self.rad}",
        )
        set_cell(
            "hdr-t-ext",
            f"{I18N.bidi('External temperature', 'Наружная температура')} {self.t_ext}",
            tooltip=f"{I18N.bidi('External temperature', 'Наружная температура')}: {self.t_ext}",
        )
        set_cell(
            "hdr-t-core",
            f"{I18N.bidi('Core temperature', 'Температура ядра')} {self.t_core}",
            tooltip=f"{I18N.bidi('Core temperature', 'Температура ядра')}: {self.t_core}",
        )
        set_cell(
            "hdr-age",
            f"{I18N.bidi('Age', 'Возраст')} {self.age}",
            tooltip=f"{I18N.bidi('Telemetry age', 'Возраст телеметрии')}: {self.age}",
        )
        set_cell(
            "hdr-freshness",
            f"{I18N.bidi('Freshness', 'Свежесть')} {self.freshness}",
            tooltip=f"{I18N.bidi('Freshness', 'Свежесть')}: {self.freshness}",
        )
        set_cell(
            "hdr-mode",
            f"{I18N.bidi('Mode', 'Режим')} {self.mode}",
            tooltip=f"{I18N.bidi('System mode', 'Режим системы')}: {self.mode}",
        )
        set_cell(
            "hdr-sim",
            f"{I18N.bidi('Sim', 'Сим')} {self.sim}",
            tooltip=f"{I18N.bidi('Simulation state', 'Состояние симуляции')}: {self.sim}",
        )

    def update_mode(self, mode: str) -> None:
        value = (mode or "").strip() or I18N.NA
        if value == self.mode:
            return
        self.mode = value
        self._refresh_cells()

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

        power = normalized.get("power")
        if isinstance(power, dict):
            self.battery = I18N.pct(power.get("soc_pct"), digits=2)
        else:
            self.battery = I18N.NA
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

        self.sim = I18N.NA
        sim_state = normalized.get("sim_state")
        if isinstance(sim_state, dict):
            fsm_state = sim_state.get("fsm_state")
            running = sim_state.get("running")
            paused = sim_state.get("paused")
            raw_speed = sim_state.get("speed")
            speed: float | None = None
            if isinstance(raw_speed, (int, float, str)):
                try:
                    speed = float(raw_speed)
                except Exception:
                    speed = None
            state_norm = str(fsm_state).strip().upper() if isinstance(fsm_state, str) else ""
            if paused is True or state_norm == "PAUSED":
                self.sim = I18N.bidi("Paused", "Пауза")
            elif running is True or state_norm == "RUNNING":
                self.sim = I18N.bidi("Running", "Работает")
            elif running is False or state_norm == "STOPPED":
                self.sim = I18N.bidi("Stopped", "Остановлено")

            if self.sim != I18N.NA and speed is not None and speed > 0 and abs(speed - 1.0) > 1e-6:
                # Keep it short: x2, x0.5, x2.5.
                speed_s = f"{speed:.2f}".rstrip("0").rstrip(".")
                self.sim = f"{self.sim} x{speed_s}"

        # Online is a function of connectivity + freshness (no magic).
        self.online = bool(nats_connected and telemetry_freshness_kind == "fresh")
        self._refresh_cells()


class _RadarMouseMixin:
    """Shared mouse interaction for radar widgets (Unicode/bitmap)."""

    def _init_radar_mouse(self) -> None:
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_last_x = 0
        self._drag_last_y = 0
        self._drag_start_pan_u_m = 0.0
        self._drag_start_pan_v_m = 0.0
        self._drag_start_iso_yaw_deg = 45.0
        self._drag_start_iso_pitch_deg = 35.0
        self._mouse_debug_last_ts = 0.0

    def _mouse_debug(self, msg: str) -> None:
        try:
            app = getattr(self, "app", None)
            if app is None:
                return
            enabled = bool(getattr(app, "_mouse_debug", False))
            if not enabled:
                return
            now = time.time()
            # Throttle move spam; down/up always log.
            if msg.startswith("move") and now - float(self._mouse_debug_last_ts) < 0.25:
                return
            if msg.startswith("move"):
                self._mouse_debug_last_ts = now
            if hasattr(app, "_console_log"):
                app._console_log(f"mouse-debug/radar: {msg}", level="info")
        except Exception:
            return

    def on_mouse_scroll_up(self, event) -> None:  # noqa: ANN001
        try:
            app = getattr(self, "app", None)
            if app is None:
                return
            if hasattr(app, "_apply_radar_zoom"):
                app._apply_radar_zoom("in")
            event.stop()
        except Exception:
            return

    def on_mouse_scroll_down(self, event) -> None:  # noqa: ANN001
        try:
            app = getattr(self, "app", None)
            if app is None:
                return
            if hasattr(app, "_apply_radar_zoom"):
                app._apply_radar_zoom("out")
            event.stop()
        except Exception:
            return

    def on_mouse_down(self, event) -> None:  # noqa: ANN001
        try:
            button = getattr(event, "button", None)
            if not isinstance(button, (int, float, str)):
                return
            try:
                button_i = int(button)
            except Exception:
                return
            if button_i != 1:
                return
            app = getattr(self, "app", None)
            if app is None:
                return
            try:
                app.capture_mouse(self)  # keep delivering move events while dragging
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            self._dragging = True
            self._drag_start_x = int(getattr(event, "x", 0) or 0)
            self._drag_start_y = int(getattr(event, "y", 0) or 0)
            self._drag_last_x = self._drag_start_x
            self._drag_last_y = self._drag_start_y
            self._drag_start_pan_u_m = float(getattr(app, "_radar_pan_u_m", 0.0) or 0.0)
            self._drag_start_pan_v_m = float(getattr(app, "_radar_pan_v_m", 0.0) or 0.0)
            self._drag_start_iso_yaw_deg = float(getattr(app, "_radar_iso_yaw_deg", 45.0) or 45.0)
            self._drag_start_iso_pitch_deg = float(getattr(app, "_radar_iso_pitch_deg", 35.0) or 35.0)
            self._mouse_debug(
                f"down x={self._drag_start_x} y={self._drag_start_y} "
                f"view={getattr(app, '_radar_view', '?')} "
                f"zoom={getattr(app, '_radar_zoom', '?')} "
                f"pan={getattr(app, '_radar_pan_u_m', '?')},{getattr(app, '_radar_pan_v_m', '?')} "
                f"iso={getattr(app, '_radar_iso_yaw_deg', '?')}/{getattr(app, '_radar_iso_pitch_deg', '?')}"
            )
            event.stop()
        except Exception:
            return

    def on_mouse_move(self, event) -> None:  # noqa: ANN001
        try:
            if not self._dragging:
                return
            buttons = getattr(event, "buttons", None)
            if buttons is not None:
                try:
                    if int(buttons) == 0:
                        self._dragging = False
                        return
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
            x = int(getattr(event, "x", 0) or 0)
            y = int(getattr(event, "y", 0) or 0)
            self._drag_last_x = x
            self._drag_last_y = y
            dx = x - self._drag_start_x
            dy = y - self._drag_start_y
            if dx == 0 and dy == 0:
                return
            app = getattr(self, "app", None)
            if app is None:
                return
            if hasattr(app, "_apply_radar_drag_from_mouse"):
                self._mouse_debug(f"move x={x} y={y} dx={dx} dy={dy}")
                app._apply_radar_drag_from_mouse(
                    start_pan_u_m=self._drag_start_pan_u_m,
                    start_pan_v_m=self._drag_start_pan_v_m,
                    start_iso_yaw_deg=self._drag_start_iso_yaw_deg,
                    start_iso_pitch_deg=self._drag_start_iso_pitch_deg,
                    dx_cells=dx,
                    dy_cells=dy,
                )
                event.stop()
        except Exception:
            return

    def on_mouse_up(self, event) -> None:  # noqa: ANN001
        try:
            button = getattr(event, "button", None)
            if button is not None:
                if not isinstance(button, (int, float, str)):
                    return
                try:
                    button_i = int(button)
                except Exception:
                    return
                if button_i != 1:
                    return
            dx = self._drag_last_x - self._drag_start_x
            dy = self._drag_last_y - self._drag_start_y
            if abs(dx) + abs(dy) <= 1:
                app = getattr(self, "app", None)
                if app is None:
                    return
                if hasattr(app, "_handle_radar_ppi_click"):
                    app._handle_radar_ppi_click(self._drag_last_x, self._drag_last_y)
            self._dragging = False
            try:
                app = getattr(self, "app", None)
                if app is not None:
                    app.capture_mouse(None)
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            self._mouse_debug(f"up x={self._drag_last_x} y={self._drag_last_y} dx={dx} dy={dy}")
        except Exception:
            self._dragging = False
            try:
                app = getattr(self, "app", None)
                if app is not None:
                    app.capture_mouse(None)
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)


class RadarPpi(_RadarMouseMixin, Static):
    """Radar PPI widget with mouse interaction (terminal-first; no mocks)."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
        super().__init__(*args, **kwargs)
        self._init_radar_mouse()


if _RadarAutoImage is not None:
    # textual-image>=0.8.5 uses a base Image class with a metaclass that requires a `Renderable=...`
    # argument on *subclassing* (even when subclassing an already-concrete widget like AutoImage/TGPImage).
    # Older versions don't require it, so we keep a compatibility fallback.
    try:

        class RadarBitmapAuto(_RadarMouseMixin, _RadarAutoImage, Renderable=_RadarAutoImage._Renderable):  # type: ignore[misc,attr-defined,call-arg]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()

    except (TypeError, AttributeError):

        class RadarBitmapAuto(_RadarMouseMixin, _RadarAutoImage):  # type: ignore[misc,no-redef]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()


else:  # pragma: no cover
    RadarBitmapAuto = None  # type: ignore[assignment,misc]


if _RadarTGPImage is not None:
    try:

        class RadarBitmapTGP(_RadarMouseMixin, _RadarTGPImage, Renderable=_RadarTGPImage._Renderable):  # type: ignore[misc,attr-defined,call-arg]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()

    except (TypeError, AttributeError):

        class RadarBitmapTGP(_RadarMouseMixin, _RadarTGPImage):  # type: ignore[misc,no-redef]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()


else:  # pragma: no cover
    RadarBitmapTGP = None  # type: ignore[assignment,misc]


if _RadarSixelImage is not None:
    try:

        class RadarBitmapSixel(_RadarMouseMixin, _RadarSixelImage, Renderable=_RadarSixelImage._Renderable):  # type: ignore[misc,attr-defined,call-arg]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()

    except (TypeError, AttributeError):

        class RadarBitmapSixel(_RadarMouseMixin, _RadarSixelImage):  # type: ignore[misc,no-redef]
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
                super().__init__(*args, **kwargs)
                self._init_radar_mouse()


else:  # pragma: no cover
    RadarBitmapSixel = None  # type: ignore[assignment,misc]


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
            if unread > 0:
                suffix.append(f"{unread} {I18N.bidi('Unread', 'Непрочитано')}")
            if not live:
                suffix.append(I18N.bidi("Paused", "Пауза"))
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
                base = [
                    fit("Tab фокус", usable),
                    fit("Enter команда", usable),
                    fit("Ctrl+C выход", usable),
                ]
                if self.active_screen == "qiki":
                    base.extend(
                        [
                            fit("V принять", usable),
                            fit("B отклон", usable),
                        ]
                    )
                return base

            base = [
                fit(f"{I18N.bidi('Tab', 'Таб')} {I18N.bidi('Focus', 'Фокус')}", usable),
                fit(f"{I18N.bidi('Enter', 'Ввод')} {I18N.bidi('Command', 'Команда')}", usable),
                fit(f"{I18N.bidi('Ctrl+C', 'Ctrl+C')} {I18N.bidi('Quit', 'Выход')}", usable),
            ]

            if self.active_screen == "qiki":
                base.extend(
                    [
                        fit(f"V {I18N.bidi('Accept', 'Принять')}", usable),
                        fit(f"B {I18N.bidi('Reject', 'Отклонить')}", usable),
                    ]
                )
            return base

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
            if app.screen == "events" and app.screen == active_screen:
                live = bool(getattr(orion, "_events_live", True))
                if not live:
                    unread = int(getattr(orion, "_events_unread_count", 0) or 0)
                    prefix: list[str] = []
                    if unread > 0:
                        prefix.append(str(unread))
                    prefix.append(I18N.bidi("Paused", "Пауза"))
                    label = f"{' '.join(prefix)} {label}"
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


class OrionDataTable(DataTable):
    def on_mount(self) -> None:
        # Row-based navigation is required for selection-driven inspector updates.
        self.cursor_type = "row"
        self.show_cursor = True

    async def _on_key(self, event) -> None:
        key = getattr(event, "key", "")
        char = getattr(event, "character", "")
        if key in {"tab", "shift+tab", "backtab", "ctrl+i"} or char == "\t":
            event.stop()
            try:
                cast(Any, self.app).action_cycle_focus()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return
        await super()._on_key(event)


class OrionCommandInput(Input):
    async def _on_key(self, event) -> None:
        key = getattr(event, "key", "")
        char = getattr(event, "character", "")
        if key in {"tab", "shift+tab", "backtab", "ctrl+i"} or char == "\t":
            event.stop()
            try:
                cast(Any, self.app).action_cycle_focus()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return
        await super()._on_key(event)


class OrionOutputLog(RichLog):
    """Output log with reliable mouse-wheel scrolling (no focus required)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        try:
            wheel_lines = int(os.getenv("OPERATOR_CONSOLE_OUTPUT_WHEEL_LINES", "3"))
        except Exception:
            wheel_lines = 3
        self._wheel_lines = max(1, min(20, wheel_lines))

    def _scroll_by_wheel(self, *, delta_lines: int) -> None:
        if delta_lines == 0:
            return
        if delta_lines < 0:
            self.auto_scroll = False

        target_y = max(0, min(int(self.scroll_y) + delta_lines, int(self.max_scroll_y)))
        self.scroll_to(y=target_y, animate=False, immediate=True)
        if target_y >= int(self.max_scroll_y):
            self.auto_scroll = True

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self._scroll_by_wheel(delta_lines=-self._wheel_lines)
        event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self._scroll_by_wheel(delta_lines=self._wheel_lines)
        event.stop()


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
    #orion-header-grid { layout: grid; grid-size:  5 2; grid-gutter: 0 2; }
    #orion-header-grid.header-2x4 { grid-size:  2 5; grid-gutter: 0 2; }
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
    #radar-left { width: 47; }
    #radar-ppi { width: 47; height: 25; color: #00ff66; background: #050505; }
    #radar-legend { width: 47; height: 5; border: round #303030; padding: 0 1; color: #e0e0e0; background: #050505; }
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
        Binding("tab", "cycle_focus", I18N.bidi("Tab focus", "Таб фокус")),
        Binding("ctrl+e", "focus_command", "Command input/Ввод команды"),
        # Radar view hotkeys (RFC): only active on the Radar screen.
        Binding("1", "radar_view_top", "Radar view top", show=False),
        Binding("2", "radar_view_side", "Radar view side", show=False),
        Binding("3", "radar_view_front", "Radar view front", show=False),
        Binding("4", "radar_view_iso", "Radar view iso", show=False),
        Binding("n", "radar_select_next", "Radar select next", show=False),
        Binding("p", "radar_select_prev", "Radar select prev", show=False),
        Binding("k", "radar_toggle_vectors", "Radar vectors toggle", show=False),
        Binding("l", "radar_toggle_labels", "Radar labels toggle", show=False),
        Binding("ctrl+up", "output_grow", I18N.bidi("Output +", "Вывод +"), show=False),
        Binding("ctrl+down", "output_shrink", I18N.bidi("Output -", "Вывод -"), show=False),
        Binding("ctrl+0", "output_reset", I18N.bidi("Output reset", "Вывод сброс"), show=False),
        Binding("ctrl+y", "toggle_events_live", "Events live or pause/События живое или пауза"),
        Binding("ctrl+i", "toggle_inspector", "Inspector toggle/Инспектор вкл/выкл"),
        Binding(
            "v",
            "accept_selected_proposal",
            I18N.bidi("Accept selected proposal", "Принять выбранное предложение"),
            show=False,
        ),
        Binding(
            "b",
            "reject_selected_proposal",
            I18N.bidi("Reject selected proposal", "Отклонить выбранное предложение"),
            show=False,
        ),
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
        self._power_compact_override: Optional[bool] = None
        self._tracks_by_id: dict[str, tuple[dict[str, Any], float]] = {}
        self._last_event: Optional[dict[str, Any]] = None
        self._events_live: bool = True
        self._events_unread_count: int = 0
        self._events_unread_incident_ids: set[str] = set()
        self._last_unread_refresh_ts: float = 0.0
        self._max_event_incidents: int = int(os.getenv("OPERATOR_CONSOLE_MAX_EVENT_INCIDENTS", "500"))
        self._max_events_table_rows: int = int(os.getenv("OPERATOR_CONSOLE_MAX_EVENTS_TABLE_ROWS", "200"))
        self._console_by_key: dict[str, dict[str, Any]] = {}
        self._qiki_by_key: dict[str, dict[str, Any]] = {}
        self._qiki_last_response: Optional[QikiChatResponseV1] = None
        self._qiki_mode: str = I18N.NA
        self._bios_loaded_announced: bool = False
        self._bios_first_status_ts_epoch: Optional[float] = None

        self._summary_by_key: dict[str, dict[str, Any]] = {}
        self._power_by_key: dict[str, dict[str, Any]] = {}
        self._sensors_by_key: dict[str, dict[str, Any]] = {}
        self._propulsion_by_key: dict[str, dict[str, Any]] = {}
        self._thermal_by_key: dict[str, dict[str, Any]] = {}
        self._diagnostics_by_key: dict[str, dict[str, Any]] = {}
        self._mission_by_key: dict[str, dict[str, Any]] = {}
        # Keep a stable rendered row order per table id to avoid cursor jumps.
        self._datatable_row_keys: dict[str, list[str]] = {}
        self._selection_by_app: dict[str, SelectionContext] = {}
        self._snapshots = SnapshotStore()

        # Secret entry mode (avoid modal dialogs; use the main input as a password field).
        self._secret_entry_mode: str | None = None
        self._secret_entry_prev_password: bool | None = None
        # Boot UI coordination flags (no-mocks).
        self._boot_nats_init_done: bool = False
        self._boot_nats_error: str = ""
        self._events_filter_type: Optional[str] = None
        self._events_filter_text: Optional[str] = None

        raw_dev_docking = os.getenv("OPERATOR_CONSOLE_DEV_DOCKING_COMMANDS", "0").strip().lower()
        self._dev_docking_commands_enabled: bool = raw_dev_docking in {"1", "true", "yes", "on"}

        self._telemetry_dictionary_by_path: dict[str, dict[str, str]] | None = None
        self._telemetry_dictionary_mtime_ns: int | None = None

        self._command_max_chars: int = int(os.getenv("OPERATOR_CONSOLE_COMMAND_MAX_CHARS", "1024"))
        self._warned_command_trim: bool = False
        self._qiki_pending: dict[str, tuple[float, str]] = {}
        self._qiki_response_timeout_sec: float = float(os.getenv("QIKI_RESPONSE_TIMEOUT_SEC", "3.0"))
        self._qiki_last_request_id: Optional[str] = None
        repo_root = os.getenv("QIKI_REPO_ROOT", "").strip() or "."
        default_rules = os.path.join(repo_root, "config", "incident_rules.yaml")
        # History is optional; keep it disabled by default to avoid creating extra files in the repo.
        history_path = os.getenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", "").strip() or None
        self._rules_repo = FileRulesRepository(
            os.getenv("OPERATOR_CONSOLE_INCIDENT_RULES", default_rules),
            history_path,
        )
        self._incident_rules: IncidentRulesConfig | None = None
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
        # Record/Replay (local tools) — keep state in-app, no new NATS contracts.
        self._record_task: asyncio.Task | None = None
        self._record_output_path: str | None = None
        self._record_started_ts_epoch: float | None = None
        self._record_last_result: dict[str, Any] | None = None
        self._replay_task: asyncio.Task | None = None
        self._replay_input_path: str | None = None
        self._replay_started_ts_epoch: float | None = None
        self._replay_last_result: dict[str, Any] | None = None
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

        # Output zone sizing (user-adjustable). Start from env override (if set), else CSS default (8).
        base_out = self._output_height_override if self._output_height_override is not None else 8
        self._output_height_rows = int(max(3, min(40, base_out)))
        self._output_height_default_rows = int(self._output_height_rows)
        self._output_follow = True
        self._radar_ppi_swap_pending: bool = False

        ppi_width = int(os.getenv("OPERATOR_CONSOLE_PPI_WIDTH", "47"))
        ppi_height = int(os.getenv("OPERATOR_CONSOLE_PPI_HEIGHT", "25"))
        ppi_max_range = float(os.getenv("OPERATOR_CONSOLE_PPI_MAX_RANGE_M", "500.0"))
        self._ppi_width_cells: int = int(ppi_width)
        self._ppi_height_cells: int = int(ppi_height)
        self._ppi_max_range_m: float = float(ppi_max_range)

        radar_view = (os.getenv("RADAR_VIEW", "top") or "top").strip().lower()
        if radar_view not in {"top", "side", "front", "iso"}:
            radar_view = "top"
        self._radar_view: str = radar_view
        self._radar_zoom: float = 1.0
        self._radar_pan_u_m: float = 0.0
        self._radar_pan_v_m: float = 0.0
        self._radar_iso_yaw_deg: float = 45.0
        self._radar_iso_pitch_deg: float = 35.0
        self._radar_overlay_vectors: bool = True
        self._radar_overlay_labels: bool = False

        radar_renderer = (os.getenv("RADAR_RENDERER", "unicode") or "unicode").strip().lower()
        if radar_renderer not in {"unicode", "auto", "kitty", "sixel"}:
            radar_renderer = "unicode"
        self._radar_renderer_requested: str = radar_renderer
        if radar_renderer == "auto":
            if _is_ssh_tmux_operator_env():
                self._radar_renderer_effective = "unicode"
            else:
                self._radar_renderer_effective = _textual_image_best_backend_kind() or "unicode"
        else:
            self._radar_renderer_effective = radar_renderer

        if self._radar_renderer_effective != "unicode":
            if render_bitmap_ppi is None:
                self._radar_renderer_effective = "unicode"
            elif self._radar_renderer_effective == "kitty" and RadarBitmapTGP is None:
                self._radar_renderer_effective = "unicode"
            elif self._radar_renderer_effective == "sixel" and RadarBitmapSixel is None:
                self._radar_renderer_effective = "unicode"

        if BraillePpiRenderer is not None:
            self._ppi_renderer = BraillePpiRenderer(
                width_cells=self._ppi_width_cells,
                height_cells=self._ppi_height_cells,
                max_range_m=self._ppi_max_range_m,
            )
        elif PpiScopeRenderer is not None:
            self._ppi_renderer = PpiScopeRenderer(width=ppi_width, height=ppi_height, max_range_m=ppi_max_range)
        else:
            self._ppi_renderer = None
        self._update_system_snapshot()
        self._load_incident_rules(initial=True)

    def _apply_output_layout(self) -> None:
        """Apply current output height to the bottom bar.

        Bottom bar height = output + command input (3) + keybar (1).
        """
        try:
            output = self.query_one("#command-output-log", RichLog)
            bottom = self.query_one("#bottom-bar", Vertical)
        except Exception:
            return

        term_h = int(getattr(getattr(self, "size", None), "height", 0) or 0)
        max_out = 40
        if term_h:
            max_out = max(3, min(40, int(term_h * 0.6)))

        self._output_height_rows = max(3, min(max_out, int(self._output_height_rows)))
        output.styles.height = int(self._output_height_rows)
        bottom.styles.height = int(self._output_height_rows + 4)

    def action_output_grow(self) -> None:
        self._output_height_rows += 1
        self._apply_output_layout()

    def action_output_shrink(self) -> None:
        self._output_height_rows -= 1
        self._apply_output_layout()

    def action_output_reset(self) -> None:
        self._output_height_rows = int(self._output_height_default_rows)
        self._apply_output_layout()

    def _radar_hotkeys_allowed(self) -> bool:
        if self.active_screen != "radar":
            return False
        try:
            from textual.widgets import Input as _Input

            focused = getattr(self, "focused", None)
            if isinstance(focused, _Input):
                return False
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        return True

    def action_radar_view_top(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_view = "top"
        self._radar_pan_u_m = 0.0
        self._radar_pan_v_m = 0.0
        self._render_radar_ppi()

    def action_radar_view_side(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_view = "side"
        self._radar_pan_u_m = 0.0
        self._radar_pan_v_m = 0.0
        self._render_radar_ppi()

    def action_radar_view_front(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_view = "front"
        self._radar_pan_u_m = 0.0
        self._radar_pan_v_m = 0.0
        self._render_radar_ppi()

    def action_radar_view_iso(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_view = "iso"
        self._radar_pan_u_m = 0.0
        self._radar_pan_v_m = 0.0
        self._render_radar_ppi()

    def action_radar_select_next(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_select_relative(delta=1)

    def action_radar_select_prev(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_select_relative(delta=-1)

    def action_radar_toggle_vectors(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_overlay_vectors = not bool(self._radar_overlay_vectors)
        self._refresh_radar()

    def action_radar_toggle_labels(self) -> None:
        if not self._radar_hotkeys_allowed():
            return
        self._radar_overlay_labels = not bool(self._radar_overlay_labels)
        self._refresh_radar()

    def _radar_select_relative(self, *, delta: int) -> None:
        if self.active_screen != "radar":
            return

        items = self._active_tracks_sorted()
        if not items:
            return

        ordered_ids = [str(track_id) for track_id, _payload, _seen in items]
        radar_sel = self._selection_by_app.get("radar")
        current = radar_sel.key if radar_sel is not None else None
        if current in ordered_ids:
            idx = ordered_ids.index(str(current))
            new_id = ordered_ids[(idx + int(delta)) % len(ordered_ids)]
        else:
            new_id = ordered_ids[0]

        if new_id not in self._tracks_by_id:
            return
        payload, seen = self._tracks_by_id[new_id]
        self._set_selection(
            SelectionContext(
                app_id="radar",
                key=new_id,
                kind="track",
                source="radar",
                created_at_epoch=float(seen),
                payload=payload,
                ids=(new_id,),
            )
        )
        self._refresh_radar()

    def _output_log(self) -> RichLog | None:
        try:
            return self.query_one("#command-output-log", RichLog)
        except Exception:
            return None

    def _output_apply_follow(self, enabled: bool) -> None:
        self._output_follow = bool(enabled)
        log = self._output_log()
        if log is None:
            return
        try:
            log.auto_scroll = bool(enabled)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

    def _output_scroll_relative(self, delta_lines: int) -> None:
        log = self._output_log()
        if log is None:
            if delta_lines < 0:
                self._output_follow = False
            return

        if delta_lines < 0:
            self._output_apply_follow(False)

        try:
            log.scroll_relative(y=float(delta_lines), animate=False, immediate=True)
        except Exception:
            return

        try:
            if int(getattr(log, "scroll_y", 0)) >= int(getattr(log, "max_scroll_y", 0)):
                self._output_apply_follow(True)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

    def _output_scroll_end(self) -> None:
        log = self._output_log()
        if log is None:
            self._output_apply_follow(True)
            return
        try:
            log.scroll_end(animate=False, immediate=True, x_axis=False, y_axis=True)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        self._output_apply_follow(True)

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
                    "events_filter_trust": self._normalize_events_trust_filter_token(self._events_filter_text),
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
    def _sensor_status_label(
        raw_value: Any,
        rendered_value: str,
        *,
        warning: bool = False,
        status_kind: str | None = None,
    ) -> str:
        if status_kind is not None:
            kind = str(status_kind).strip().lower()
            if kind == "ok":
                return I18N.bidi("Normal", "Норма")
            if kind == "warn":
                return I18N.bidi("Warning", "Предупреждение")
            if kind == "crit":
                return I18N.bidi("Abnormal", "Не норма")
            if kind in {"na", "disabled"}:
                return I18N.bidi("Disabled", "Отключено")
            return I18N.NA

        if isinstance(raw_value, dict):
            enabled = raw_value.get("enabled")
            if isinstance(enabled, bool) and enabled is False:
                return I18N.bidi("Disabled", "Отключено")
            # A dict is an aggregate; without an explicit status_kind it is safer to show N/A than pretend "Normal".
            return I18N.NA

        if raw_value is None:
            return I18N.NA
        if warning:
            return I18N.bidi("Warning", "Предупреждение")
        if rendered_value == I18N.INVALID:
            return I18N.bidi("Abnormal", "Не норма")
        return I18N.bidi("Normal", "Норма")

    @staticmethod
    def _radar_status_code(payload: dict[str, Any]) -> str:
        raw = payload.get("status")
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.RadarTrackStatusEnum (aligned with proto):
            # 0 UNSPECIFIED, 1 NEW, 2 TRACKED, 3 LOST, 4 COASTING
            return {0: "—", 1: "NEW", 2: "TRK", 3: "LOST", 4: "CST"}.get(raw, str(raw))
        if isinstance(raw, str) and raw:
            for token, label in (
                ("COAST", "CST"),
                ("TRACK", "TRK"),
                ("LOST", "LOST"),
                ("NEW", "NEW"),
            ):
                if token in raw:
                    return label
            return raw
        return "—"

    @staticmethod
    def _radar_range_band_code(payload: dict[str, Any]) -> str:
        raw = payload.get("range_band", payload.get("rangeBand"))
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.RangeBand: 0 UNSPEC, 1 LR, 2 SR
            return {0: "—", 1: "LR", 2: "SR"}.get(raw, str(raw))
        if isinstance(raw, str) and raw:
            for token in ("LR", "SR"):
                if token in raw:
                    return token
            return raw
        return "—"

    @staticmethod
    def _radar_iff_code(payload: dict[str, Any]) -> str:
        raw = payload.get("iff", payload.get("iff_class", payload.get("iffClass")))
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.FriendFoeEnum (aligned with proto):
            # 0 UNSPECIFIED, 1 FRIEND, 2 FOE, 3 UNKNOWN
            return {0: "—", 1: "FRND", 2: "FOE", 3: "UNK"}.get(raw, str(raw))
        if isinstance(raw, str) and raw:
            for token, label in (("FRIEND", "FRND"), ("FOE", "FOE"), ("UNKNOWN", "UNK")):
                if token in raw:
                    return label
            return raw
        return "—"

    @staticmethod
    def _radar_object_type_code(payload: dict[str, Any]) -> str:
        raw = payload.get("object_type", payload.get("objectType", payload.get("type")))
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.ObjectTypeEnum (aligned with proto):
            # 0 UNSPECIFIED, 1 DRONE, 2 SHIP, 3 STATION, 4 ASTEROID, 5 DEBRIS
            return {0: "—", 1: "DRONE", 2: "SHIP", 3: "STN", 4: "AST", 5: "DEBR"}.get(raw, str(raw))
        if isinstance(raw, str) and raw:
            for token, label in (
                ("DEBRIS", "DEBR"),
                ("ASTEROID", "AST"),
                ("STATION", "STN"),
                ("SHIP", "SHIP"),
                ("DRONE", "DRONE"),
            ):
                if token in raw:
                    return label
            return raw
        return "—"

    @staticmethod
    def _radar_transponder_mode_code(payload: dict[str, Any]) -> str:
        raw = payload.get("transponder_mode", payload.get("transponderMode", payload.get("mode")))
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.TransponderModeEnum (aligned with proto):
            # 0 OFF, 1 ON, 2 SILENT, 3 SPOOF
            return {0: "OFF", 1: "ON", 2: "SILENT", 3: "SPOOF"}.get(raw, str(raw))
        if isinstance(raw, str) and raw:
            for token in ("OFF", "ON", "SILENT", "SPOOF"):
                if token in raw:
                    return token
            return raw
        return "—"

    @staticmethod
    def _fmt_age_s(seconds: Optional[float]) -> str:
        return I18N.fmt_age(seconds)

    @staticmethod
    def _canonicalize_telemetry_path(path: str) -> str:
        s = str(path or "").strip()
        if not s:
            return ""
        # Examples:
        # - thermal.nodes[id=core].temp_c -> thermal.nodes[*].temp_c
        # - propulsion.rcs.thrusters[index=3].duty_pct -> propulsion.rcs.thrusters[*].duty_pct
        return re.sub(r"\[[a-zA-Z_]+=[^\]]+\]", "[*]", s)

    def _get_telemetry_dictionary_by_path(self) -> dict[str, dict[str, str]] | None:
        if yaml is None:
            return None

        rel = os.getenv(
            "ORION_TELEMETRY_DICTIONARY_PATH",
            "docs/design/operator_console/TELEMETRY_DICTIONARY.yaml",
        ).strip()
        repo_root_env = os.getenv("QIKI_REPO_ROOT", "").strip()
        if repo_root_env:
            repo_root = Path(repo_root_env).expanduser().resolve()
        else:
            try:
                repo_root = Path(__file__).resolve().parents[4]
            except Exception:
                repo_root = Path.cwd()
        dict_path = (repo_root / rel) if rel and not Path(rel).is_absolute() else Path(rel)
        try:
            stat = dict_path.stat()
            mtime_ns = int(getattr(stat, "st_mtime_ns", 0) or 0)
        except Exception:
            return None

        if (
            self._telemetry_dictionary_by_path is not None
            and self._telemetry_dictionary_mtime_ns is not None
            and mtime_ns
            and self._telemetry_dictionary_mtime_ns == mtime_ns
        ):
            return self._telemetry_dictionary_by_path

        try:
            raw = yaml.safe_load(dict_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(raw, dict):
            return None
        subsystems = raw.get("subsystems")
        if not isinstance(subsystems, dict):
            return None

        by_path: dict[str, dict[str, str]] = {}
        for subsystem_id, subsystem in subsystems.items():
            if not isinstance(subsystem_id, str) or not isinstance(subsystem, dict):
                continue
            fields = subsystem.get("fields")
            if not isinstance(fields, list):
                continue
            for field in fields:
                if not isinstance(field, dict):
                    continue
                p = field.get("path")
                if not isinstance(p, str) or not p.strip():
                    continue
                label = field.get("label")
                unit = field.get("unit")
                typ = field.get("type")
                why_operator = field.get("why_operator")
                actions_hint = field.get("actions_hint")
                if not isinstance(label, str) or not label.strip():
                    continue
                by_path[p.strip()] = {
                    "label": label.strip(),
                    "unit": str(unit).strip() if unit is not None else "",
                    "type": str(typ).strip() if typ is not None else "",
                    "why_operator": str(why_operator).strip() if isinstance(why_operator, str) else "",
                    "actions_hint": str(actions_hint).strip() if isinstance(actions_hint, str) else "",
                    "subsystem": subsystem_id.strip(),
                }

        self._telemetry_dictionary_by_path = by_path
        self._telemetry_dictionary_mtime_ns = mtime_ns
        return by_path

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
            "info": I18N.bidi("info", "инфо"),
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

        items = self._active_tracks_sorted()
        if not items:
            self._selection_by_app.pop("radar", None)
            status = I18N.NA
            info = I18N.NO_TRACKS_YET
            empty_num = "—"
            telemetry_env = self._snapshots.get_last("telemetry")
            if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
                try:
                    normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
                except ValidationError:
                    normalized = {}
                sim_state = normalized.get("sim_state") if isinstance(normalized, dict) else None
                if isinstance(sim_state, dict):
                    fsm_state = sim_state.get("fsm_state")
                    running = sim_state.get("running")
                    paused = sim_state.get("paused")
                    state_norm = str(fsm_state).strip().upper() if isinstance(fsm_state, str) else ""
                    if paused is True or state_norm == "PAUSED":
                        status = I18N.bidi("Paused", "Пауза")
                        info = I18N.bidi("No tracks while paused", "Нет треков на паузе")
                    elif running is False or state_norm == "STOPPED":
                        status = I18N.bidi("Stopped", "Остановлено")
                        info = I18N.bidi(
                            "Simulation stopped (start to see tracks)",
                            "Симуляция остановлена (запустите, чтобы увидеть треки)",
                        )
                    elif running is True or state_norm == "RUNNING":
                        status = I18N.bidi("No tracks", "Треков нет")
                        info = I18N.NO_TRACKS_YET
            self._sync_datatable_rows(
                table,
                rows=[
                    (
                        "seed",
                        "—",
                        status,
                        empty_num,
                        empty_num,
                        empty_num,
                        empty_num,
                        info,
                    )
                ],
            )
            return

        radar_sel = self._selection_by_app.get("radar")
        selected_track_id = radar_sel.key if radar_sel is not None else None

        by_track_id: dict[str, tuple[dict[str, Any], float]] = {
            str(track_id): (payload, float(seen)) for track_id, payload, seen in items
        }

        table_id = str(getattr(table, "id", "") or "")
        prev_keys = self._datatable_row_keys.get(table_id)

        ordered_track_ids: list[str] = []
        if prev_keys:
            for key in prev_keys:
                if key in by_track_id:
                    ordered_track_ids.append(key)

        for track_id, _payload, _seen in items:
            tid = str(track_id)
            if tid not in by_track_id or tid in ordered_track_ids:
                continue
            ordered_track_ids.append(tid)

        rows: list[tuple[Any, ...]] = []
        for track_id in ordered_track_ids:
            payload, seen = by_track_id[track_id]
            age_s = max(0.0, time.time() - seen)
            ttl = self._track_ttl_sec
            freshness = f"{age_s:.1f}s"
            if ttl > 0 and age_s > ttl:
                freshness = I18N.stale(freshness)
            status = OrionApp._radar_status_code(payload)
            quality = self._fmt_num(payload.get("quality"), digits=2)
            band = OrionApp._radar_range_band_code(payload)
            id_present = payload.get("id_present", payload.get("idPresent"))
            miss_count = payload.get("miss_count", payload.get("missCount"))
            id_flag = ""
            if isinstance(id_present, bool) and id_present:
                id_flag = "/ID"
            miss_flag = ""
            if isinstance(miss_count, int) and miss_count > 0:
                miss_flag = f" m{miss_count}"
            info = f"{band}{id_flag}{miss_flag} ({freshness})"
            rows.append(
                (
                    track_id,
                    track_id,
                    self._fmt_num(payload.get("range_m")),
                    self._fmt_num(payload.get("bearing_deg"), digits=1),
                    self._fmt_num(payload.get("vr_mps"), digits=2),
                    status,
                    quality,
                    info,
                )
            )

        self._sync_datatable_rows(table, rows=rows)

        if selected_track_id is None or str(selected_track_id) not in by_track_id:
            track_id, payload, seen = items[0]
            self._set_selection(
                SelectionContext(
                    app_id="radar",
                    key=str(track_id),
                    kind="track",
                    source="radar",
                    created_at_epoch=float(seen),
                    payload=payload,
                    ids=(str(track_id),),
                )
            )
            selected_track_id = str(track_id)

        if selected_track_id is not None and selected_track_id in ordered_track_ids:
            try:
                cursor_row = getattr(table, "cursor_row", None)
                keys = self._datatable_row_keys.get(table_id) or []
                cursor_key = keys[cursor_row] if isinstance(cursor_row, int) and 0 <= cursor_row < len(keys) else None
                if cursor_key != selected_track_id:
                    table.move_cursor(
                        row=ordered_track_ids.index(selected_track_id),
                        column=0,
                        animate=False,
                        scroll=False,
                    )
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)

    def _render_radar_ppi(self) -> None:
        try:
            ppi = self.query_one("#radar-ppi")
        except Exception:
            return

        # Ensure the mounted PPI widget matches the effective renderer. This allows seamless
        # runtime fallback without restart (RFC).
        desired_kind = getattr(self, "_radar_renderer_effective", "unicode") or "unicode"
        try:
            if desired_kind == "unicode":
                if not isinstance(ppi, RadarPpi):
                    self._schedule_radar_ppi_widget_swap("unicode")
                    return
            elif desired_kind == "kitty" and RadarBitmapTGP is not None:
                if not isinstance(ppi, RadarBitmapTGP):
                    self._schedule_radar_ppi_widget_swap("kitty")
                    return
            elif desired_kind == "sixel" and RadarBitmapSixel is not None:
                if not isinstance(ppi, RadarBitmapSixel):
                    self._schedule_radar_ppi_widget_swap("sixel")
                    return
            elif desired_kind != "unicode" and RadarBitmapAuto is not None:
                if not isinstance(ppi, RadarBitmapAuto):
                    self._schedule_radar_ppi_widget_swap(desired_kind)
                    return
            elif desired_kind != "unicode":
                # Effective bitmap requested but widget class is unavailable: fallback.
                self._fallback_radar_to_unicode("bitmap widget unavailable")
                return
        except Exception:
            # If widget checks fail, avoid crashing the UI refresh loop; fallback.
            self._fallback_radar_to_unicode("renderer widget mismatch")
            return

        tracks_items = self._active_tracks_sorted()
        radar_sel = self._selection_by_app.get("radar")
        selected_track_id = radar_sel.key if radar_sel is not None else None
        tracks = [(str(tid), payload) for tid, payload, _seen in tracks_items]
        payloads = [payload for _tid, payload, _seen in tracks_items]
        if self._ppi_renderer is None:
            try:
                ppi.update(I18N.bidi("Radar display unavailable", "Экран радара недоступен"))
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return
        if self._radar_renderer_effective != "unicode":
            if render_bitmap_ppi is None or not hasattr(ppi, "image"):
                self._fallback_radar_to_unicode("bitmap renderer unavailable")
                return
            try:
                img = render_bitmap_ppi(
                    tracks,
                    width_px=int(self._ppi_width_cells) * 12,
                    height_px=int(self._ppi_height_cells) * 24,
                    max_range_m=float(self._ppi_max_range_m),
                    view=self._radar_view,
                    zoom=self._radar_zoom,
                    pan_u_m=self._radar_pan_u_m,
                    pan_v_m=self._radar_pan_v_m,
                    iso_yaw_deg=self._radar_iso_yaw_deg,
                    iso_pitch_deg=self._radar_iso_pitch_deg,
                    selected_track_id=str(selected_track_id) if selected_track_id is not None else None,
                    draw_overlays=True,
                    draw_vectors=bool(self._radar_overlay_vectors),
                    draw_labels=bool(self._radar_overlay_labels),
                )
                ppi.image = img  # type: ignore[attr-defined]
            except Exception:
                self._fallback_radar_to_unicode("bitmap render error")
                return
            self._render_radar_legend()
            return
        if BraillePpiRenderer is not None and isinstance(self._ppi_renderer, BraillePpiRenderer):
            try:
                cast(Any, ppi).update(
                    self._ppi_renderer.render_tracks(
                        tracks,
                        view=self._radar_view,
                        zoom=self._radar_zoom,
                        pan_u_m=self._radar_pan_u_m,
                        pan_v_m=self._radar_pan_v_m,
                        rich=True,
                        selected_track_id=str(selected_track_id) if selected_track_id is not None else None,
                        iso_yaw_deg=self._radar_iso_yaw_deg,
                        iso_pitch_deg=self._radar_iso_pitch_deg,
                        draw_vectors=bool(self._radar_overlay_vectors),
                        draw_labels=bool(self._radar_overlay_labels),
                    )
                )
            except Exception:
                return
            self._render_radar_legend()
            return
        try:
            ppi.update(self._ppi_renderer.render_tracks(payloads))
        except Exception:
            return
        self._render_radar_legend()

    def _schedule_radar_ppi_widget_swap(self, desired_kind: str) -> None:
        if self._radar_ppi_swap_pending:
            return
        self._radar_ppi_swap_pending = True

        def _do() -> None:
            try:
                asyncio.create_task(self._swap_radar_ppi_widget_async(desired_kind))
            except Exception:
                self._radar_ppi_swap_pending = False

        try:
            self.call_after_refresh(_do)
        except Exception:
            self._radar_ppi_swap_pending = False

    async def _swap_radar_ppi_widget_async(self, desired_kind: str) -> None:
        try:
            radar_left = self.query_one("#radar-left", Vertical)
            legend = self.query_one("#radar-legend", Static)
        except Exception:
            self._radar_ppi_swap_pending = False
            return

        try:
            existing = self.query_one("#radar-ppi")
            try:
                await existing.remove()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

        kind = (desired_kind or "unicode").strip().lower()
        if kind == "unicode":
            widget = RadarPpi(id="radar-ppi")
        elif kind == "kitty" and RadarBitmapTGP is not None:
            widget = RadarBitmapTGP(id="radar-ppi")
        elif kind == "sixel" and RadarBitmapSixel is not None:
            widget = RadarBitmapSixel(id="radar-ppi")
        elif kind != "unicode" and RadarBitmapAuto is not None:
            widget = RadarBitmapAuto(id="radar-ppi")
        else:
            widget = RadarPpi(id="radar-ppi")

        try:
            await radar_left.mount(widget, before=legend)
        except Exception:
            try:
                await radar_left.mount(widget)
            except Exception:
                return
        finally:
            self._radar_ppi_swap_pending = False

    def _fallback_radar_to_unicode(self, reason: str) -> None:
        prev = str(getattr(self, "_radar_renderer_effective", "unicode") or "unicode")
        self._radar_renderer_effective = "unicode"
        try:
            self._console_log(
                I18N.bidi(
                    f"Radar renderer fallback: {prev} -> unicode ({reason})",
                    f"Фолбэк рендера радара: {prev} -> unicode ({reason})",
                ),
                level="warn",
            )
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        self._schedule_radar_ppi_widget_swap("unicode")

    def _render_radar_legend(self) -> None:
        try:
            legend = self.query_one("#radar-legend", Static)
        except Exception:
            return
        try:
            from rich.style import Style
            from rich.text import Text
        except Exception:
            legend.update(I18N.NA)
            return

        hint_style = Style(color="#a0a0a0")

        t = Text()
        t.append(I18N.bidi("Legend", "Легенда") + ": ")
        t.append("FRND", Style(color="#00ff66"))
        t.append(" ")
        t.append("FOE", Style(color="#ff3355", bold=True))
        t.append(" ")
        t.append("UNK", Style(color="#ffb000", bold=True))
        t.append(" ")
        t.append(I18N.bidi("SEL", "ВЫБР"), Style(color="#ffffff", bold=True))
        t.append("\n")

        t.append(
            f"{I18N.bidi('View', 'Вид')}: {self._radar_view}  {I18N.bidi('Zoom', 'Масштаб')}: x{self._radar_zoom:.2f}",
            hint_style,
        )
        radar_sel = self._selection_by_app.get("radar")
        selected_track_id = radar_sel.key if radar_sel is not None else None
        t.append(
            f"  {I18N.bidi('Sel', 'Выбор')}: {str(selected_track_id) if selected_track_id is not None else I18N.NA}",
            hint_style,
        )
        t.append("\n")

        third_line = f"{I18N.bidi('Pan', 'Сдвиг')}: {self._radar_pan_u_m:.0f},{self._radar_pan_v_m:.0f}m"
        overlays = []
        if bool(getattr(self, "_radar_overlay_vectors", False)):
            overlays.append("VEC")
        if bool(getattr(self, "_radar_overlay_labels", False)):
            lbl_active = bool(float(getattr(self, "_radar_zoom", 1.0) or 1.0) >= 2.0)
            overlays.append("LBL" if lbl_active else "LBL:req")
        if overlays:
            third_line += f" {I18N.bidi('Overlays', 'Оверлеи')}: {','.join(overlays)}"
        if self._radar_view == "iso":
            third_line += f" ISO:{self._radar_iso_yaw_deg:.0f}/{self._radar_iso_pitch_deg:.0f}°"
        else:
            if getattr(self, "_radar_renderer_effective", "unicode") != "unicode":
                third_line += f" {I18N.bidi('Renderer', 'Рендер')}: {self._radar_renderer_effective}"

        t.append(third_line, hint_style)

        # Selected-track 3D readout (no-mocks): show altitude and vertical rate only if
        # the underlying keys are explicitly present in the payload.
        if selected_track_id is not None:
            payload = None
            try:
                if selected_track_id in self._tracks_by_id:
                    payload = self._tracks_by_id[selected_track_id][0]
            except Exception:
                payload = None
            try:
                from qiki.services.operator_console.radar.unicode_ppi import (
                    format_vz_token,
                    format_z_token,
                    radar_vz_mps_if_present,
                    radar_z_m_if_present,
                )
            except Exception:
                format_z_token = None  # type: ignore[assignment]
                format_vz_token = None  # type: ignore[assignment]
                radar_z_m_if_present = None  # type: ignore[assignment]
                radar_vz_mps_if_present = None  # type: ignore[assignment]

            t.append("\n")
            if (
                payload is not None
                and callable(radar_z_m_if_present)
                and callable(radar_vz_mps_if_present)
                and callable(format_z_token)
                and callable(format_vz_token)
            ):
                z_m = radar_z_m_if_present(payload)
                vz_mps = radar_vz_mps_if_present(payload)
                z_txt = format_z_token(float(z_m)) if z_m is not None else I18N.NA
                vz_txt = format_vz_token(float(vz_mps)) if vz_mps is not None else I18N.NA
            else:
                z_txt = I18N.NA
                vz_txt = I18N.NA
            t.append(
                f"3D: Z {z_txt}  Vz {vz_txt}",
                hint_style,
            )
        legend.update(t)

    def _apply_radar_drag_from_mouse(
        self,
        *,
        start_pan_u_m: float,
        start_pan_v_m: float,
        start_iso_yaw_deg: float,
        start_iso_pitch_deg: float,
        dx_cells: int,
        dy_cells: int,
    ) -> None:
        if self._radar_view == "iso":
            self._radar_iso_yaw_deg = float(start_iso_yaw_deg) + float(dx_cells) * 4.0
            self._radar_iso_pitch_deg = float(start_iso_pitch_deg) - float(dy_cells) * 2.0
            # Keep it stable: prevent gimbal-like flips.
            self._radar_iso_pitch_deg = max(-80.0, min(80.0, float(self._radar_iso_pitch_deg)))
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                return
            return
        self._apply_radar_pan_from_drag(
            start_pan_u_m=float(start_pan_u_m),
            start_pan_v_m=float(start_pan_v_m),
            dx_cells=int(dx_cells),
            dy_cells=int(dy_cells),
        )

    def _apply_radar_pan_from_drag(
        self,
        *,
        start_pan_u_m: float,
        start_pan_v_m: float,
        dx_cells: int,
        dy_cells: int,
    ) -> None:
        effective_range_m = max(1.0, float(self._ppi_max_range_m) / max(0.1, float(self._radar_zoom)))
        denom_u = max(1.0, float(self._ppi_width_cells) / 2.0 - 1.0)
        denom_v = max(1.0, float(self._ppi_height_cells) / 2.0 - 1.0)
        meters_per_cell_u = effective_range_m / denom_u
        meters_per_cell_v = effective_range_m / denom_v

        self._radar_pan_u_m = float(start_pan_u_m) - float(dx_cells) * meters_per_cell_u
        self._radar_pan_v_m = float(start_pan_v_m) + float(dy_cells) * meters_per_cell_v

        try:
            if self.active_screen == "radar":
                self._render_radar_ppi()
        except Exception:
            return

    def _apply_radar_zoom(self, op: str) -> None:
        low = (op or "").strip().lower()
        if low == "reset":
            self._radar_zoom = 1.0
        elif low == "in":
            self._radar_zoom = max(0.1, min(100.0, float(self._radar_zoom) * 1.25))
        elif low == "out":
            self._radar_zoom = max(0.1, min(100.0, float(self._radar_zoom) / 1.25))
        else:
            return

        try:
            if self.active_screen == "radar":
                self._render_radar_ppi()
        except Exception:
            return

    def _handle_radar_ppi_click(self, x: int, y: int) -> None:
        if pick_nearest_track_id is None:
            return

        items = self._active_tracks_sorted()
        if not items:
            return

        candidates: list[tuple[str, dict[str, Any]]] = [(str(tid), payload) for tid, payload, _seen in items]
        picked = pick_nearest_track_id(
            candidates,
            click_cell_x=int(x),
            click_cell_y=int(y),
            width_cells=self._ppi_width_cells,
            height_cells=self._ppi_height_cells,
            max_range_m=self._ppi_max_range_m,
            view=self._radar_view,
            zoom=self._radar_zoom,
            pan_u_m=self._radar_pan_u_m,
            pan_v_m=self._radar_pan_v_m,
            iso_yaw_deg=self._radar_iso_yaw_deg,
            iso_pitch_deg=self._radar_iso_pitch_deg,
        )
        if picked is None:
            return

        for track_id, payload, seen in items:
            if str(track_id) != str(picked):
                continue
            self._set_selection(
                SelectionContext(
                    app_id="radar",
                    key=str(track_id),
                    kind="track",
                    source="radar",
                    created_at_epoch=float(seen),
                    payload=payload,
                    ids=(str(track_id),),
                )
            )
            self._render_tracks_table()
            if self.active_screen == "radar":
                self._refresh_inspector()
            return

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
        if s in {"non_goal", "nongoal", "non-goal"}:
            return I18N.bidi("Non-goal", "Не цель")
        return I18N.NA

    def _freshness_to_status(self, freshness: Optional[str]) -> str:
        if freshness is None:
            return "na"
        if freshness == "fresh":
            return "ok"
        if freshness == "stale":
            return "warn"
        return "crit"

    def _summary_compact_enabled(self) -> bool:
        # Keep startup summary glanceable by default; full verbose strings can be enabled explicitly.
        raw_default = os.getenv("ORION_SUMMARY_COMPACT_DEFAULT", "1").strip().lower()
        default_compact = raw_default not in {"0", "false", "no", "off"}
        if self._density in {"tiny", "narrow"}:
            return True
        return default_compact

    def _summary_value_with_causal_badge(self, block_id: str, value: Any) -> str:
        text = str(value if value is not None else I18N.NA)
        if not self._summary_compact_enabled():
            return text
        if block_id not in {"energy", "threats"}:
            return text

        match = re.search(r"cause=([^;]+?)\s*->\s*effect=([^;]+?)\s*->\s*next=(.+)$", text)
        if match is None:
            return text

        cause = match.group(1).strip()
        effect = match.group(2).strip()
        next_step = match.group(3).strip()
        head = text[: match.start()].strip().rstrip(";")
        badge = f"[{cause}->{effect}]"
        if head:
            return f"{badge} {head}; next={next_step}"
        return f"{badge} next={next_step}"

    def _summary_action_hint(self, hint_id: str) -> str:
        compact = self._summary_compact_enabled()
        if compact:
            compact_map = {
                "monitor": I18N.bidi("monitor", "наблюдать"),
                "pause_power_faults": I18N.bidi("pause+power", "пауза+питание"),
                "reduce_loads": I18N.bidi("shed+trim", "сброс+снижение"),
                "trim_non_critical": I18N.bidi("trim-noncritical", "снять вторичное"),
                "reduce_propulsion": I18N.bidi("thrust-down", "тяга-ниже"),
                "pause_radiation": I18N.bidi("pause+radiation", "пауза+радиация"),
                "minimize_exposure": I18N.bidi("exposure-down", "экспозиция-ниже"),
                "cooling_thermal_check": I18N.bidi("cool+inspect", "охладить+проверить"),
                "pause_threat": I18N.bidi("pause+threat", "пауза+угроза"),
            }
            return compact_map.get(hint_id, compact_map["monitor"])

        verbose_map = {
            "monitor": I18N.bidi("monitor", "наблюдать"),
            "pause_power_faults": I18N.bidi("pause + inspect power faults", "пауза + проверка аварий питания"),
            "reduce_loads": I18N.bidi("reduce loads", "снизить нагрузку"),
            "trim_non_critical": I18N.bidi("trim non-critical systems", "отключить вторичные системы"),
            "reduce_propulsion": I18N.bidi("reduce propulsion demand", "снизить потребление двигателей"),
            "pause_radiation": I18N.bidi("pause + execute radiation protocol", "пауза + протокол радиации"),
            "minimize_exposure": I18N.bidi("minimize exposure", "снизить экспозицию"),
            "cooling_thermal_check": I18N.bidi(
                "cooling + inspect thermal nodes", "охлаждение + проверка thermal узлов"
            ),
            "pause_threat": I18N.bidi("pause + threat protocol", "пауза + протокол угроз"),
        }
        return verbose_map.get(hint_id, verbose_map["monitor"])

    def _system_compact_enabled(self) -> bool:
        # Startup system panels are compact by default; verbose mode remains opt-in via env.
        raw_default = os.getenv("ORION_SYSTEM_COMPACT_DEFAULT", "1").strip().lower()
        default_compact = raw_default not in {"0", "false", "no", "off"}
        if self._density in {"tiny", "narrow"}:
            return True
        return default_compact

    def _compact_system_panel_rows(
        self,
        rows: list[tuple[str, str, str]],
        *,
        essential_keys: set[str],
        max_rows: int,
    ) -> list[tuple[str, str, str]]:
        if not rows or not self._system_compact_enabled():
            return rows

        def has_signal(value: str) -> bool:
            txt = str(value).strip()
            return bool(txt) and txt != I18N.NA

        filtered = [row for row in rows if row[0] in essential_keys or has_signal(row[2])]
        if not filtered:
            return rows[:1]

        if max_rows <= 0 or len(filtered) <= max_rows:
            return filtered

        essentials = [row for row in filtered if row[0] in essential_keys]
        extras = [row for row in filtered if row[0] not in essential_keys]
        if len(essentials) >= max_rows:
            return essentials[:max_rows]
        return essentials + extras[: (max_rows - len(essentials))]

    def _build_summary_blocks(self) -> list[SystemStateBlock]:
        now = time.time()
        compact_summary = self._summary_compact_enabled()

        telemetry_env = self._snapshots.get_last("telemetry")
        telemetry_age_s = self._snapshots.age_s("telemetry", now_epoch=now)
        telemetry_freshness = self._snapshots.freshness("telemetry", now_epoch=now)
        online = bool(self.nats_connected and telemetry_freshness == "fresh")
        telemetry_status = self._freshness_to_status(telemetry_freshness)
        normalized: dict[str, Any] = {}
        if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
            try:
                normalized = TelemetrySnapshotModel.normalize_payload(telemetry_env.payload)
            except ValidationError:
                normalized = {}
        sim_state = (
            cast(dict[str, Any], normalized.get("sim_state")) if isinstance(normalized.get("sim_state"), dict) else {}
        )
        power = cast(dict[str, Any], normalized.get("power")) if isinstance(normalized.get("power"), dict) else {}
        propulsion = (
            cast(dict[str, Any], normalized.get("propulsion")) if isinstance(normalized.get("propulsion"), dict) else {}
        )
        comms = cast(dict[str, Any], normalized.get("comms")) if isinstance(normalized.get("comms"), dict) else {}
        sensor_plane = (
            cast(dict[str, Any], normalized.get("sensor_plane"))
            if isinstance(normalized.get("sensor_plane"), dict)
            else {}
        )
        radiation = (
            cast(dict[str, Any], sensor_plane.get("radiation"))
            if isinstance(sensor_plane.get("radiation"), dict)
            else {}
        )
        thermal = cast(dict[str, Any], normalized.get("thermal")) if isinstance(normalized.get("thermal"), dict) else {}
        thermal_nodes = cast(list[Any], thermal.get("nodes")) if isinstance(thermal.get("nodes"), list) else []
        faults = cast(list[Any], power.get("faults")) if isinstance(power.get("faults"), list) else []
        shed_loads = cast(list[Any], power.get("shed_loads")) if isinstance(power.get("shed_loads"), list) else []

        state_txt = str(sim_state.get("fsm_state") or I18N.NA)
        health_status = "na" if telemetry_env is None else telemetry_status
        if telemetry_status == "crit":
            health_status = "crit"
        if compact_summary:
            health_value = (
                f"state={state_txt}; link={I18N.online_offline(online)}; age={I18N.fmt_age_compact(telemetry_age_s)}"
            )
        else:
            health_value = (
                f"{I18N.bidi('State', 'Состояние')}={state_txt}; "
                f"{I18N.bidi('Link', 'Связь')}={I18N.online_offline(online)}; "
                f"{I18N.bidi('Age', 'Возраст')}={I18N.fmt_age_compact(telemetry_age_s)}"
            )

        soc_raw = power.get("soc_pct")
        soc_value = I18N.pct(soc_raw, digits=2)
        low_soc = False
        try:
            if soc_raw is not None and float(soc_raw) < 20.0:
                low_soc = True
        except Exception:
            low_soc = False
        energy_status = "na" if telemetry_env is None else "ok"
        if bool(power.get("load_shedding")):
            energy_status = "warn"
        if bool(power.get("pdu_throttled")):
            energy_status = "warn"
        if low_soc:
            energy_status = "warn"
        if len(faults) > 0:
            energy_status = "crit"
        energy_cause = "balanced"
        energy_effect = "stable"
        energy_next = self._summary_action_hint("monitor")
        if len(faults) > 0:
            energy_cause = "power_faults"
            energy_effect = f"faults={len(faults)}"
            energy_next = self._summary_action_hint("pause_power_faults")
        elif bool(power.get("pdu_throttled")):
            energy_cause = "pdu_limit"
            energy_effect = f"shed={len(shed_loads)}"
            energy_next = self._summary_action_hint("reduce_loads")
        elif bool(power.get("load_shedding")):
            energy_cause = "load_shedding"
            energy_effect = f"shed={len(shed_loads)}"
            energy_next = self._summary_action_hint("trim_non_critical")
        elif low_soc:
            energy_cause = "low_soc"
            energy_effect = "reduced power margin"
            energy_next = self._summary_action_hint("reduce_propulsion")
        energy_value = (
            f"SoC={soc_value}; "
            f"In/Out={I18N.num_unit(power.get('power_in_w'), 'W', 'Вт', digits=0)}/"
            f"{I18N.num_unit(power.get('power_out_w'), 'W', 'Вт', digits=0)}; "
            f"cause={energy_cause} -> effect={energy_effect} -> next={energy_next}"
        )

        velocity = normalized.get("velocity")
        vel_txt = I18N.num_unit(velocity, "m/s", "м/с", digits=1)
        motion_status = "na" if telemetry_env is None else "ok"
        rcs = cast(dict[str, Any], propulsion.get("rcs")) if isinstance(propulsion.get("rcs"), dict) else {}
        if bool(rcs.get("throttled")):
            motion_status = "warn"
        if compact_summary:
            motion_value = (
                f"v={vel_txt}; hdg={I18N.num_unit(normalized.get('heading'), '°', '°', digits=1)}; "
                f"rcs={I18N.yes_no(bool(rcs.get('active')))}"
            )
        else:
            motion_value = (
                f"V={vel_txt}; Hdg={I18N.num_unit(normalized.get('heading'), '°', '°', digits=1)}; "
                f"RCS={I18N.yes_no(bool(rcs.get('active')))}"
            )

        trip_count = 0
        for node in thermal_nodes:
            if isinstance(node, dict) and bool(node.get("tripped")):
                trip_count += 1
        rad_status = str(radiation.get("status") or "").strip().lower()
        limits = cast(dict[str, Any], radiation.get("limits")) if isinstance(radiation.get("limits"), dict) else {}
        threats_status = "na" if telemetry_env is None else "ok"
        if rad_status in {"warn", "warning"}:
            threats_status = "warn"
        if rad_status in {"crit", "critical"} or trip_count > 0:
            threats_status = "crit"
        threats_cause = "none"
        threats_effect = "stable"
        threats_next = self._summary_action_hint("monitor")
        if rad_status in {"crit", "critical"}:
            threats_cause = "radiation_critical"
            threats_effect = "unsafe exposure risk"
            threats_next = self._summary_action_hint("pause_radiation")
        elif rad_status in {"warn", "warning"}:
            threats_cause = "radiation_warning"
            threats_effect = "reduced safety margin"
            threats_next = self._summary_action_hint("minimize_exposure")
        elif trip_count > 0:
            threats_cause = "thermal_trip"
            threats_effect = f"tripped_nodes={trip_count}"
            threats_next = self._summary_action_hint("cooling_thermal_check")
        if compact_summary:
            threats_value = (
                f"rad={str(radiation.get('status') or I18N.NA)}; "
                f"trips={trip_count}; "
                f"cause={threats_cause} -> effect={threats_effect} -> next={threats_next}"
            )
        else:
            threats_value = (
                f"{I18N.bidi('Radiation', 'Радиация')}={str(radiation.get('status') or I18N.NA)}; "
                f"bg={I18N.num_unit(radiation.get('background_usvh'), 'uSv/h', 'мкЗв/ч', digits=2)} "
                f"(warn={I18N.num_unit(limits.get('warn_usvh'), 'uSv/h', 'мкЗв/ч', digits=2)}, "
                f"crit={I18N.num_unit(limits.get('crit_usvh'), 'uSv/h', 'мкЗв/ч', digits=2)}); "
                f"cause={threats_cause} -> effect={threats_effect} -> next={threats_next}"
            )

        xpdr = cast(dict[str, Any], comms.get("xpdr")) if isinstance(comms.get("xpdr"), dict) else {}
        actions_status = "na" if telemetry_env is None else "ok"
        if energy_status == "warn" or threats_status == "warn" or len(faults) > 0:
            actions_status = "warn"
        if threats_status == "crit":
            actions_status = "crit"
        action_hint = self._summary_action_hint("monitor")
        # Deterministic startup priority: threat mitigation over energy mitigation.
        if energy_status == "warn":
            action_hint = energy_next
        if threats_status == "warn":
            action_hint = threats_next
        if len(faults) > 0:
            action_hint = self._summary_action_hint("pause_power_faults")
        if threats_status == "crit":
            action_hint = self._summary_action_hint("pause_threat")
        trust_token = self._normalize_events_trust_filter_token(self._events_filter_text)
        actions_value = (
            f"{I18N.bidi('Next', 'Действие')}={action_hint}; "
            f"XPDR={str(xpdr.get('mode') or I18N.NA)}/{I18N.yes_no(bool(xpdr.get('allowed')))}"
        )
        if not compact_summary or trust_token not in {"all", "off"}:
            actions_value = f"{actions_value}; trust={trust_token}"

        return [
            SystemStateBlock(
                block_id="health",
                title=I18N.bidi("Health", "Состояние"),
                status=health_status,
                value=health_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="energy",
                title=I18N.bidi("Energy", "Энергия"),
                status=energy_status,
                value=energy_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="motion_safety",
                title=I18N.bidi("Motion/Safety", "Движение/Безопасность"),
                status=motion_status,
                value=motion_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="threats",
                title=I18N.bidi("Threats", "Угрозы"),
                status=threats_status,
                value=threats_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
            SystemStateBlock(
                block_id="actions_incidents",
                title=I18N.bidi("Actions/Incidents", "Действия/Инциденты"),
                status=actions_status,
                value=actions_value,
                ts_epoch=None if telemetry_env is None else float(telemetry_env.ts_epoch),
                envelope=telemetry_env,
            ),
        ]

    def _sync_datatable_rows(self, table: DataTable, *, rows: list[tuple[Any, ...]]) -> None:
        """
        Update a DataTable with minimal redraw to avoid cursor jumps.

        Contract:
        - Each row tuple MUST be: (row_key, col0, col1, ...).
        - Column count must match the DataTable's existing columns.
        """

        table_id = str(getattr(table, "id", "") or "")
        if not table_id:
            table_id = str(id(table))

        desired_keys: list[str] = []
        for row in rows:
            if not row:
                continue
            desired_keys.append(str(row[0]))

        prev_keys = self._datatable_row_keys.get(table_id)
        cursor_key: str | None = None
        if prev_keys is not None:
            try:
                cr = getattr(table, "cursor_row", None)
                if isinstance(cr, int) and 0 <= cr < len(prev_keys):
                    cursor_key = prev_keys[cr]
            except Exception:
                cursor_key = None

        def rebuild() -> None:
            try:
                table.clear()
            except Exception:
                return
            for row in rows:
                if not row:
                    continue
                row_key = str(row[0])
                cells = list(row[1:])
                try:
                    table.add_row(*cells, key=row_key)
                except Exception:
                    # If adding fails (bad columns), bail out without crashing the UI loop.
                    return
            self._datatable_row_keys[table_id] = desired_keys

            # Preserve cursor only if it was previously set and still exists.
            if cursor_key is not None and cursor_key in desired_keys:
                try:
                    table.move_cursor(row=desired_keys.index(cursor_key), column=0, animate=False, scroll=False)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)

        if prev_keys != desired_keys:
            rebuild()
            return

        # Fast path: same row keys → update cells in place.
        try:
            for row in rows:
                if not row:
                    continue
                row_key = str(row[0])
                cells = list(row[1:])
                row_index = table.get_row_index(row_key)
                for col_index, value in enumerate(cells):
                    table.update_cell_at(Coordinate(row_index, col_index), value)
            self._datatable_row_keys[table_id] = desired_keys
        except Exception:
            rebuild()

    def _render_summary_table(self) -> None:
        try:
            table = self.query_one("#summary-table", DataTable)
        except Exception:
            return

        now = time.time()
        blocks = self._build_summary_blocks()

        self._summary_by_key = {}
        current = self._selection_by_app.get("summary")
        rows: list[tuple[Any, ...]] = []
        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status_label = self._block_status_label(block.status)
            value_for_table = self._summary_value_with_causal_badge(block.block_id, block.value)
            rows.append((block.block_id, block.title, status_label, value_for_table, I18N.fmt_age_compact(age_s)))
            self._summary_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status_label,
                "value": value_for_table,
                "age": I18N.fmt_age_compact(age_s),
                "envelope": block.envelope,
            }
        if not rows:
            rows = [("seed", "—", I18N.NA, I18N.NA, I18N.NA)]

        self._sync_datatable_rows(table, rows=rows)

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

    def _render_power_table(self) -> None:
        try:
            table = self.query_one("#power-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._power_by_key = {}
            self._selection_by_app.pop("power", None)
            self._sync_datatable_rows(table, rows=[("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)])

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

        def fmt_w_breakdown(value: Any) -> str:
            if not isinstance(value, dict):
                return I18N.NA
            items: list[tuple[str, float]] = []
            for k, raw in value.items():
                key = str(k).strip()
                if not key:
                    continue
                try:
                    v = float(raw)
                except Exception:
                    continue
                if abs(v) <= 1e-9:
                    continue
                items.append((key, v))

            if not items:
                return I18N.bidi("none", "нет")

            label_by_key = {
                "base": I18N.bidi("Base", "База"),
                "dock": I18N.bidi("Dock", "Док"),
                "motion": I18N.bidi("Motion", "Движ"),
                "mcqpu": I18N.bidi("MCQPU", "MCQPU"),
                "radar": I18N.bidi("Radar", "Радар"),
                "transponder": I18N.bidi("XPDR", "XPDR"),
                "nbl": I18N.bidi("NBL", "NBL"),
                "rcs": I18N.bidi("RCS", "РДС"),
                "supercap_charge": I18N.bidi("Supercap", "Суперкап"),
                "supercap_discharge": I18N.bidi("Supercap", "Суперкап"),
            }

            items.sort(key=lambda kv: abs(float(kv[1])), reverse=True)
            shown = items[:3]
            parts = [f"{label_by_key.get(k, k)} {I18N.num_unit(v, 'W', 'Вт', digits=1)}" for k, v in shown]
            s = ", ".join(parts)
            remaining = len(items) - len(shown)
            if remaining > 0:
                s = f"{s} (+{remaining})"
            return s if len(s) <= 32 else s[:29] + "..."

        def mk_row(
            row_key: str,
            label: str,
            source_path: str,
            render: Any,
        ) -> tuple[str, str, str, Any, tuple[str, ...]]:
            raw = get(source_path)
            value = render(raw)
            return (row_key, label, value, raw, (source_path,))

        rows: list[tuple[str, str, str, Any, tuple[str, ...]]] = [
            mk_row(
                "state_of_charge",
                I18N.bidi("State of charge", "Уровень заряда"),
                "power.soc_pct",
                lambda v: I18N.pct(v, digits=1),
            ),
            mk_row(
                "load_shedding",
                I18N.bidi("Load shed", "Сброс нагрузки"),
                "power.load_shedding",
                lambda v: I18N.yes_no(bool(v)) if v is not None else I18N.NA,
            ),
            mk_row(
                "shed_reasons",
                I18N.bidi("Shed reason", "Причины"),
                "power.shed_reasons",
                fmt_list,
            ),
            mk_row(
                "nbl_active",
                I18N.bidi("Neutrino Burst Link", "Нейтринный канал"),
                "power.nbl_active",
                lambda v: I18N.yes_no(bool(v)) if v is not None else I18N.NA,
            ),
            mk_row(
                "nbl_allowed",
                I18N.bidi("Neutrino Burst Link allowed", "Нейтринный канал разрешен"),
                "power.nbl_allowed",
                lambda v: I18N.yes_no(bool(v)) if v is not None else I18N.NA,
            ),
            mk_row(
                "nbl_budget",
                I18N.bidi("Neutrino Burst Link budget", "Бюджет нейтринного канала"),
                "power.nbl_budget_w",
                lambda v: I18N.num_unit(v, "W", "Вт", digits=1),
            ),
            (
                "nbl_power",
                I18N.bidi("Neutrino Burst Link power", "Мощность нейтринного канала"),
                I18N.num_unit(get("power.nbl_power_w"), "W", "Вт", digits=1),
                get("power.nbl_power_w"),
                ("power.nbl_power_w",),
            ),
            (
                "shed_loads",
                I18N.bidi("Shed loads", "Сброшено"),
                fmt_list(get("power.shed_loads")),
                get("power.shed_loads"),
                ("power.shed_loads",),
            ),
            (
                "faults",
                I18N.bidi("Faults", "Аварии"),
                fmt_faults(get("power.faults")),
                get("power.faults"),
                ("power.faults",),
            ),
            (
                "pdu_limit",
                I18N.bidi("Power distribution unit limit", "Лимит распределителя питания"),
                I18N.num_unit(get("power.pdu_limit_w"), "W", "Вт", digits=1),
                get("power.pdu_limit_w"),
                ("power.pdu_limit_w",),
            ),
            (
                "pdu_throttled",
                I18N.bidi("Power distribution unit throttled", "Ограничение распределителя питания"),
                I18N.yes_no(bool(get("power.pdu_throttled"))) if get("power.pdu_throttled") is not None else I18N.NA,
                get("power.pdu_throttled"),
                ("power.pdu_throttled",),
            ),
            (
                "throttled_loads",
                I18N.bidi("Throttled", "Троттлено"),
                fmt_list(get("power.throttled_loads")),
                get("power.throttled_loads"),
                ("power.throttled_loads",),
            ),
            (
                "supercap_soc",
                I18N.bidi("Supercap state of charge", "Уровень заряда суперкап"),
                I18N.pct(get("power.supercap_soc_pct"), digits=1),
                get("power.supercap_soc_pct"),
                ("power.supercap_soc_pct",),
            ),
            (
                "dock_connected",
                I18N.bidi("Dock", "Стыковка"),
                I18N.yes_no(bool(get("power.dock_connected"))) if get("power.dock_connected") is not None else I18N.NA,
                get("power.dock_connected"),
                ("power.dock_connected",),
            ),
            (
                "docking_state",
                I18N.bidi("Dock state", "Состояние дока"),
                I18N.fmt_na(get("docking.state")),
                get("docking.state"),
                ("docking.state",),
            ),
            (
                "docking_port",
                I18N.bidi("Dock port", "Порт дока"),
                I18N.fmt_na(get("docking.port")),
                get("docking.port"),
                ("docking.port",),
            ),
            (
                "dock_soft_start",
                I18N.bidi("Dock ramp", "Разгон дока"),
                I18N.pct(get("power.dock_soft_start_pct"), digits=0),
                get("power.dock_soft_start_pct"),
                ("power.dock_soft_start_pct",),
            ),
            (
                "dock_power",
                I18N.bidi("Dock P", "Стыковка P"),
                I18N.num_unit(get("power.dock_power_w"), "W", "Вт", digits=1),
                get("power.dock_power_w"),
                ("power.dock_power_w",),
            ),
            (
                "dock_v",
                I18N.bidi("Dock V", "Док В"),
                I18N.num_unit(get("power.dock_v"), "V", "В", digits=2),
                get("power.dock_v"),
                ("power.dock_v",),
            ),
            (
                "dock_a",
                I18N.bidi("Dock A", "Док А"),
                I18N.num_unit(get("power.dock_a"), "A", "А", digits=2),
                get("power.dock_a"),
                ("power.dock_a",),
            ),
            (
                "power_input",
                I18N.bidi("Power input", "Входная мощность"),
                I18N.num_unit(get("power.power_in_w"), "W", "Вт", digits=1),
                get("power.power_in_w"),
                ("power.power_in_w",),
            ),
            (
                "power_consumption",
                I18N.bidi("Power output", "Выходная мощность"),
                I18N.num_unit(get("power.power_out_w"), "W", "Вт", digits=1),
                get("power.power_out_w"),
                ("power.power_out_w",),
            ),
            (
                "battery_charge",
                I18N.bidi("Battery charge", "Заряд батареи"),
                I18N.num_unit(get("power.battery_charge_w"), "W", "Вт", digits=1),
                get("power.battery_charge_w"),
                ("power.battery_charge_w",),
            ),
            (
                "battery_discharge",
                I18N.bidi("Battery discharge", "Разряд батареи"),
                I18N.num_unit(get("power.battery_discharge_w"), "W", "Вт", digits=1),
                get("power.battery_discharge_w"),
                ("power.battery_discharge_w",),
            ),
            (
                "battery_spill",
                I18N.bidi("Battery spill", "Сброс заряда"),
                I18N.num_unit(get("power.battery_spill_w"), "W", "Вт", digits=1),
                get("power.battery_spill_w"),
                ("power.battery_spill_w",),
            ),
            (
                "battery_unserved",
                I18N.bidi("Unserved load", "Недостающая мощность"),
                I18N.num_unit(get("power.battery_unserved_w"), "W", "Вт", digits=1),
                get("power.battery_unserved_w"),
                ("power.battery_unserved_w",),
            ),
            mk_row(
                "power_sources",
                I18N.bidi("Power sources", "Источники мощности"),
                "power.sources_w",
                fmt_w_breakdown,
            ),
            mk_row(
                "power_loads",
                I18N.bidi("Power loads", "Нагрузки мощности"),
                "power.loads_w",
                fmt_w_breakdown,
            ),
            (
                "dock_temp",
                I18N.bidi("Dock temperature", "Температура стыковки"),
                I18N.num_unit(get("power.dock_temp_c"), "C", "°C", digits=1),
                get("power.dock_temp_c"),
                ("power.dock_temp_c",),
            ),
            (
                "supercap_charge",
                I18N.bidi("Supercap charge", "Заряд суперкап"),
                I18N.num_unit(get("power.supercap_charge_w"), "W", "Вт", digits=1),
                get("power.supercap_charge_w"),
                ("power.supercap_charge_w",),
            ),
            (
                "supercap_discharge",
                I18N.bidi("Supercap discharge", "Разряд суперкап"),
                I18N.num_unit(get("power.supercap_discharge_w"), "W", "Вт", digits=1),
                get("power.supercap_discharge_w"),
                ("power.supercap_discharge_w",),
            ),
            (
                "bus_voltage",
                I18N.bidi("Bus voltage", "Напряжение шины"),
                I18N.num_unit(get("power.bus_v"), "V", "В", digits=2),
                get("power.bus_v"),
                ("power.bus_v",),
            ),
            (
                "bus_current",
                I18N.bidi("Bus current", "Ток шины"),
                I18N.num_unit(get("power.bus_a"), "A", "А", digits=2),
                get("power.bus_a"),
                ("power.bus_a",),
            ),
        ]
        rows = self._compact_power_rows(rows)

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

        self._power_by_key = {}
        current = self._selection_by_app.get("power")
        table_rows: list[tuple[Any, ...]] = []
        for row_key, label, value, raw, source_keys in rows:
            status = status_label(raw, value)
            table_rows.append((row_key, label, status, value, age, source))
            self._power_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "source_keys": source_keys,
                "raw": raw,
                "envelope": telemetry_env,
            }

        if not table_rows:
            table_rows = [("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)]

        self._sync_datatable_rows(table, rows=table_rows)

        if current is None or current.key not in self._power_by_key:
            first_key = rows[0][0]
            first_source_keys = rows[0][4]
            created_at_epoch = float(telemetry_env.ts_epoch)
            self._set_selection(
                SelectionContext(
                    app_id="power",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=created_at_epoch,
                    payload=telemetry_env.payload,
                    ids=first_source_keys,
                )
            )

    def _render_thermal_table(self) -> None:
        try:
            table = self.query_one("#thermal-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._thermal_by_key = {}
            self._selection_by_app.pop("thermal", None)
            self._sync_datatable_rows(table, rows=[("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)])

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
        current = self._selection_by_app.get("thermal")
        table_rows: list[tuple[Any, ...]] = []

        def status_label(node_id: str, temp: Any, *, tripped: Any, warned: Any) -> str:
            if temp is None:
                return I18N.NA
            # Prefer explicit node state (newer telemetry), fallback to power faults (legacy).
            if isinstance(tripped, bool):
                if tripped:
                    return I18N.bidi("Abnormal", "Не норма")
                if isinstance(warned, bool) and warned:
                    return I18N.bidi("Warning", "Предупреждение")
                return I18N.bidi("Normal", "Норма")
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
            tripped = raw.get("tripped")
            warned = raw.get("warned")
            warn_c = raw.get("warn_c")
            trip_c = raw.get("trip_c")
            hys_c = raw.get("hys_c")
            status = status_label(nid, temp, tripped=tripped, warned=warned)
            source_keys = (
                f"thermal.nodes[id={nid}].temp_c",
                f"thermal.nodes[id={nid}].tripped",
                f"thermal.nodes[id={nid}].warned",
                f"thermal.nodes[id={nid}].warn_c",
                f"thermal.nodes[id={nid}].trip_c",
                f"thermal.nodes[id={nid}].hys_c",
                "power.faults",
            )
            table_rows.append((nid, nid, status, value, age, source))
            self._thermal_by_key[nid] = {
                "node_id": nid,
                "status": status,
                "temp_c": temp,
                "tripped": tripped,
                "warned": warned,
                "warn_c": warn_c,
                "trip_c": trip_c,
                "hys_c": hys_c,
                "value": value,
                "age": age,
                "source": source,
                "source_keys": source_keys,
                "envelope": telemetry_env,
            }

        if not table_rows:
            table_rows = [("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)]
        self._sync_datatable_rows(table, rows=table_rows)

        if current is None or current.key not in self._thermal_by_key:
            first_key = next(iter(self._thermal_by_key.keys()), "seed")
            first_source_keys: tuple[str, ...] = (first_key,)
            if first_key in self._thermal_by_key and isinstance(self._thermal_by_key[first_key], dict):
                sk = self._thermal_by_key[first_key].get("source_keys")
                if isinstance(sk, (list, tuple)):
                    first_source_keys = tuple(str(x) for x in sk if str(x).strip()) or (first_key,)
            self._set_selection(
                SelectionContext(
                    app_id="thermal",
                    key=first_key,
                    kind="thermal_node",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=first_source_keys,
                )
            )

    def _render_propulsion_table(self) -> None:
        try:
            table = self.query_one("#propulsion-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._propulsion_by_key = {}
            self._selection_by_app.pop("propulsion", None)
            self._sync_datatable_rows(table, rows=[("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)])

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

        rows: list[tuple[str, str, str, Any, bool, tuple[str, ...]]] = []
        enabled = rcs.get("enabled")
        active = rcs.get("active")
        throttled = rcs.get("throttled")
        axis = rcs.get("axis")
        cmd_pct = rcs.get("command_pct")
        time_left = rcs.get("time_left_s")
        propellant = rcs.get("propellant_kg")
        power_w = rcs.get("power_w")
        active_bool = None if active is None else bool(active)

        axis_label = I18N.fmt_na(axis)
        axis_raw = axis
        if active_bool is False and axis_label == I18N.NA:
            # If RCS is not active, having no axis is expected (not unknown).
            axis_label = I18N.bidi("none", "нет")
            axis_raw = "none"

        rows.extend(
            [
                (
                    "rcs_enabled",
                    I18N.bidi("RCS enabled", "РДС включено"),
                    I18N.yes_no(bool(enabled)),
                    enabled,
                    False,
                    ("propulsion.rcs.enabled",),
                ),
                (
                    "rcs_active",
                    I18N.bidi("RCS active", "РДС активно"),
                    I18N.yes_no(bool(active)),
                    active,
                    bool(throttled),
                    ("propulsion.rcs.active", "propulsion.rcs.throttled"),
                ),
                (
                    "rcs_axis",
                    I18N.bidi("Axis", "Ось"),
                    axis_label,
                    axis_raw,
                    bool(throttled),
                    ("propulsion.rcs.axis", "propulsion.rcs.throttled"),
                ),
                (
                    "rcs_command",
                    I18N.bidi("Command", "Команда"),
                    I18N.num_unit(cmd_pct, "%", "%", digits=0),
                    cmd_pct,
                    bool(throttled),
                    ("propulsion.rcs.command_pct", "propulsion.rcs.throttled"),
                ),
                (
                    "rcs_time_left",
                    I18N.bidi("Time left", "Осталось"),
                    I18N.num_unit(time_left, "s", "с", digits=1),
                    time_left,
                    bool(throttled),
                    ("propulsion.rcs.time_left_s", "propulsion.rcs.throttled"),
                ),
                (
                    "rcs_propellant",
                    I18N.bidi("Propellant", "Топливо"),
                    I18N.num_unit(propellant, "kg", "кг", digits=2),
                    propellant,
                    bool(throttled),
                    ("propulsion.rcs.propellant_kg", "propulsion.rcs.throttled"),
                ),
                (
                    "rcs_power",
                    I18N.bidi("RCS power", "РДС мощн"),
                    I18N.num_unit(power_w, "W", "Вт", digits=1),
                    power_w,
                    bool(throttled),
                    ("propulsion.rcs.power_w", "propulsion.rcs.throttled"),
                ),
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
                rows.append(
                    (
                        f"thruster_{idx}",
                        label,
                        value,
                        duty,
                        bool(throttled),
                        (
                            f"propulsion.rcs.thrusters[index={idx}].duty_pct",
                            f"propulsion.rcs.thrusters[index={idx}].valve_open",
                            "propulsion.rcs.throttled",
                        ),
                    )
                )

        self._propulsion_by_key = {}
        current = self._selection_by_app.get("propulsion")
        table_rows: list[tuple[Any, ...]] = []
        for row_key, label, value, raw, warn, source_keys in rows:
            status = status_label(raw, value, warning=warn)
            table_rows.append((row_key, label, status, value, age, source))
            self._propulsion_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "source_keys": source_keys,
                "raw": raw,
                "envelope": telemetry_env,
            }

        if not table_rows:
            table_rows = [("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA)]

        self._sync_datatable_rows(table, rows=table_rows)

        if current is None or current.key not in self._propulsion_by_key:
            first_key = rows[0][0] if rows else "seed"
            first_source_keys: tuple[str, ...] = (first_key,)
            if rows:
                first_source_keys = rows[0][5]
            self._set_selection(
                SelectionContext(
                    app_id="propulsion",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=first_source_keys,
                )
            )

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
            self._sync_datatable_rows(table, rows=[("seed", "—", I18N.NA, I18N.NA)])

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

        def status_label(
            raw_value: Any, rendered_value: str, *, warning: bool = False, status_kind: str | None = None
        ) -> str:
            return OrionApp._sensor_status_label(
                raw_value,
                rendered_value,
                warning=warning,
                status_kind=status_kind,
            )

        rows: list[tuple[str, str, str, Any, bool, str | None, tuple[str, ...]]] = []

        if compact:
            imu_raw = sp.get("imu")
            imu: dict[str, Any] = cast(dict[str, Any], imu_raw) if isinstance(imu_raw, dict) else {}
            imu_status = imu.get("status") if isinstance(imu.get("status"), str) else None
            imu_rates = [
                ("r", imu.get("roll_rate_rps")),
                ("p", imu.get("pitch_rate_rps")),
                ("y", imu.get("yaw_rate_rps")),
            ]
            imu_rates_txt = " ".join([f"{k}={float(v):.3f}" for (k, v) in imu_rates if isinstance(v, (int, float))])
            imu_value = f"{imu_rates_txt} rad/s" if imu_rates_txt else I18N.NA
            rows.append(
                (
                    "imu",
                    I18N.bidi("IMU", "ИМУ"),
                    imu_value,
                    imu,
                    False,
                    imu_status,
                    (
                        "sensor_plane.imu.roll_rate_rps",
                        "sensor_plane.imu.pitch_rate_rps",
                        "sensor_plane.imu.yaw_rate_rps",
                        "sensor_plane.imu.status",
                    ),
                )
            )

            rad: dict[str, Any] = (
                cast(dict[str, Any], sp.get("radiation")) if isinstance(sp.get("radiation"), dict) else {}
            )
            rad_status = rad.get("status") if isinstance(rad.get("status"), str) else None
            rows.append(
                (
                    "radiation",
                    I18N.bidi("Radiation", "Радиация"),
                    I18N.num_unit(rad.get("background_usvh"), "µSv/h", "мкЗв/ч", digits=2),
                    rad,
                    False,
                    rad_status,
                    ("sensor_plane.radiation.background_usvh", "sensor_plane.radiation.status"),
                )
            )

            prox: dict[str, Any] = (
                cast(dict[str, Any], sp.get("proximity")) if isinstance(sp.get("proximity"), dict) else {}
            )
            prox_value = I18N.fmt_na(prox.get("contacts"))
            if prox_value == I18N.NA:
                prox_value = I18N.num_unit(prox.get("min_range_m"), "m", "м", digits=2)
            rows.append(
                (
                    "proximity",
                    I18N.bidi("Proximity", "Близость"),
                    prox_value,
                    prox,
                    False,
                    None,
                    ("sensor_plane.proximity.contacts", "sensor_plane.proximity.min_range_m"),
                )
            )

            solar: dict[str, Any] = cast(dict[str, Any], sp.get("solar")) if isinstance(sp.get("solar"), dict) else {}
            rows.append(
                (
                    "solar",
                    I18N.bidi("Solar", "Солнце"),
                    I18N.pct(solar.get("illumination_pct"), digits=1),
                    solar,
                    False,
                    None,
                    ("sensor_plane.solar.illumination_pct",),
                )
            )

            st: dict[str, Any] = (
                cast(dict[str, Any], sp.get("star_tracker")) if isinstance(sp.get("star_tracker"), dict) else {}
            )
            st_status = st.get("status") if isinstance(st.get("status"), str) else None
            st_value = I18N.yes_no(bool(st.get("locked"))) if st.get("locked") is not None else I18N.NA
            rows.append(
                (
                    "star_tracker",
                    I18N.bidi("Star tracker", "Звёздн. трекер"),
                    st_value,
                    st,
                    False,
                    st_status,
                    ("sensor_plane.star_tracker.locked", "sensor_plane.star_tracker.status"),
                )
            )

            mag_raw = sp.get("magnetometer")
            mag: dict[str, Any] = cast(dict[str, Any], mag_raw) if isinstance(mag_raw, dict) else {}
            field_raw = mag.get("field_ut")
            field: dict[str, Any] | None = cast(dict[str, Any], field_raw) if isinstance(field_raw, dict) else None
            mag_value = I18N.NA
            if isinstance(field, dict):
                x_raw = field.get("x")
                y_raw = field.get("y")
                z_raw = field.get("z")
                if (
                    isinstance(x_raw, (int, float))
                    and isinstance(y_raw, (int, float))
                    and isinstance(z_raw, (int, float))
                ):
                    x = float(x_raw)
                    y = float(y_raw)
                    z = float(z_raw)
                    mag_value = f"|B|={math.sqrt(x * x + y * y + z * z):.2f} µT"
                else:
                    mag_value = I18N.INVALID
            rows.append(
                (
                    "magnetometer",
                    I18N.bidi("Magnetometer", "Магнитометр"),
                    mag_value,
                    mag,
                    mag_value == I18N.INVALID,
                    None,
                    ("sensor_plane.magnetometer.field_ut", "sensor_plane.magnetometer.enabled"),
                )
            )
        else:
            imu_raw = sp.get("imu")
            imu_detail: dict[str, Any] = cast(dict[str, Any], imu_raw) if isinstance(imu_raw, dict) else {}
            imu_status = imu_detail.get("status") if isinstance(imu_detail.get("status"), str) else None
            rows.extend(
                [
                    (
                        "imu_enabled",
                        I18N.bidi("IMU enabled", "ИМУ включено"),
                        I18N.yes_no(bool(imu_detail.get("enabled"))),
                        imu_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.imu.enabled",),
                    ),
                    (
                        "imu_ok",
                        I18N.bidi("IMU ok", "ИМУ ок"),
                        I18N.yes_no(bool(imu_detail.get("ok"))) if imu_detail.get("ok") is not None else I18N.NA,
                        imu_detail.get("ok"),
                        bool(imu_detail.get("ok") is False),
                        imu_status,
                        ("sensor_plane.imu.ok", "sensor_plane.imu.status"),
                    ),
                    (
                        "imu_roll_rate",
                        I18N.bidi("Roll rate", "Скор. крена"),
                        I18N.num_unit(imu_detail.get("roll_rate_rps"), "rad/s", "рад/с", digits=3),
                        imu_detail.get("roll_rate_rps"),
                        False,
                        imu_status,
                        ("sensor_plane.imu.roll_rate_rps", "sensor_plane.imu.status"),
                    ),
                    (
                        "imu_pitch_rate",
                        I18N.bidi("Pitch rate", "Скор. тангажа"),
                        I18N.num_unit(imu_detail.get("pitch_rate_rps"), "rad/s", "рад/с", digits=3),
                        imu_detail.get("pitch_rate_rps"),
                        False,
                        imu_status,
                        ("sensor_plane.imu.pitch_rate_rps", "sensor_plane.imu.status"),
                    ),
                    (
                        "imu_yaw_rate",
                        I18N.bidi("Yaw rate", "Скор. рыск"),
                        I18N.num_unit(imu_detail.get("yaw_rate_rps"), "rad/s", "рад/с", digits=3),
                        imu_detail.get("yaw_rate_rps"),
                        False,
                        imu_status,
                        ("sensor_plane.imu.yaw_rate_rps", "sensor_plane.imu.status"),
                    ),
                ]
            )

            rad_raw = sp.get("radiation")
            rad_detail: dict[str, Any] = cast(dict[str, Any], rad_raw) if isinstance(rad_raw, dict) else {}
            rad_status = rad_detail.get("status") if isinstance(rad_detail.get("status"), str) else None
            rows.extend(
                [
                    (
                        "rad_enabled",
                        I18N.bidi("Radiation enabled", "Радиация вкл"),
                        I18N.yes_no(bool(rad_detail.get("enabled"))),
                        rad_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.radiation.enabled",),
                    ),
                    (
                        "rad_background",
                        I18N.bidi("Background", "Фон"),
                        I18N.num_unit(rad_detail.get("background_usvh"), "µSv/h", "мкЗв/ч", digits=2),
                        rad_detail.get("background_usvh"),
                        False,
                        rad_status,
                        ("sensor_plane.radiation.background_usvh", "sensor_plane.radiation.status"),
                    ),
                    (
                        "rad_dose",
                        I18N.bidi("Dose total", "Доза сумм"),
                        I18N.num_unit(rad_detail.get("dose_total_usv"), "µSv", "мкЗв", digits=3),
                        rad_detail.get("dose_total_usv"),
                        False,
                        None,
                        ("sensor_plane.radiation.dose_total_usv",),
                    ),
                ]
            )

            prox_detail: dict[str, Any] = (
                cast(dict[str, Any], sp.get("proximity")) if isinstance(sp.get("proximity"), dict) else {}
            )
            rows.extend(
                [
                    (
                        "prox_enabled",
                        I18N.bidi("Proximity enabled", "Близость вкл"),
                        I18N.yes_no(bool(prox_detail.get("enabled"))),
                        prox_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.proximity.enabled",),
                    ),
                    (
                        "prox_min",
                        I18N.bidi("Min range", "Мин. дальн"),
                        I18N.num_unit(prox_detail.get("min_range_m"), "m", "м", digits=2),
                        prox_detail.get("min_range_m"),
                        False,
                        None,
                        ("sensor_plane.proximity.min_range_m",),
                    ),
                    (
                        "prox_contacts",
                        I18N.bidi("Contacts", "Контакты"),
                        I18N.fmt_na(prox_detail.get("contacts")),
                        prox_detail.get("contacts"),
                        False,
                        None,
                        ("sensor_plane.proximity.contacts",),
                    ),
                ]
            )

            solar_detail: dict[str, Any] = (
                cast(dict[str, Any], sp.get("solar")) if isinstance(sp.get("solar"), dict) else {}
            )
            rows.extend(
                [
                    (
                        "solar_enabled",
                        I18N.bidi("Solar enabled", "Солнце вкл"),
                        I18N.yes_no(bool(solar_detail.get("enabled"))),
                        solar_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.solar.enabled",),
                    ),
                    (
                        "solar_illum",
                        I18N.bidi("Illumination", "Освещённ"),
                        I18N.pct(solar_detail.get("illumination_pct"), digits=1),
                        solar_detail.get("illumination_pct"),
                        False,
                        None,
                        ("sensor_plane.solar.illumination_pct",),
                    ),
                ]
            )

            st_detail: dict[str, Any] = (
                cast(dict[str, Any], sp.get("star_tracker")) if isinstance(sp.get("star_tracker"), dict) else {}
            )
            st_status = st_detail.get("status") if isinstance(st_detail.get("status"), str) else None
            rows.extend(
                [
                    (
                        "st_enabled",
                        I18N.bidi("Star tracker enabled", "Звёздн. трекер"),
                        I18N.yes_no(bool(st_detail.get("enabled"))),
                        st_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.star_tracker.enabled",),
                    ),
                    (
                        "st_locked",
                        I18N.bidi("Star lock", "Звёзд. захват"),
                        I18N.yes_no(bool(st_detail.get("locked"))) if st_detail.get("locked") is not None else I18N.NA,
                        st_detail.get("locked"),
                        bool(st_detail.get("locked") is False),
                        st_status,
                        ("sensor_plane.star_tracker.locked", "sensor_plane.star_tracker.status"),
                    ),
                    (
                        "st_err",
                        I18N.bidi("Att err", "Ошибка атт"),
                        I18N.num_unit(st_detail.get("attitude_err_deg"), "deg", "°", digits=2),
                        st_detail.get("attitude_err_deg"),
                        False,
                        st_status,
                        ("sensor_plane.star_tracker.attitude_err_deg", "sensor_plane.star_tracker.status"),
                    ),
                ]
            )

            mag_detail_raw = sp.get("magnetometer")
            mag_detail: dict[str, Any] = (
                cast(dict[str, Any], mag_detail_raw) if isinstance(mag_detail_raw, dict) else {}
            )
            field_raw = mag_detail.get("field_ut")
            field_detail: dict[str, Any] | None = (
                cast(dict[str, Any], field_raw) if isinstance(field_raw, dict) else None
            )
            field_txt = I18N.NA
            if isinstance(field_detail, dict):
                x_mag = field_detail.get("x")
                y_mag = field_detail.get("y")
                z_mag = field_detail.get("z")
                if (
                    isinstance(x_mag, (int, float))
                    and isinstance(y_mag, (int, float))
                    and isinstance(z_mag, (int, float))
                ):
                    field_txt = f"x={float(x_mag):.2f}, y={float(y_mag):.2f}, z={float(z_mag):.2f}"
                else:
                    field_txt = I18N.INVALID
            rows.extend(
                [
                    (
                        "mag_enabled",
                        I18N.bidi("Magnetometer enabled", "Магнитометр"),
                        I18N.yes_no(bool(mag_detail.get("enabled"))),
                        mag_detail.get("enabled"),
                        False,
                        None,
                        ("sensor_plane.magnetometer.enabled",),
                    ),
                    (
                        "mag_field",
                        I18N.bidi("Mag field", "Поле магн"),
                        field_txt,
                        field_detail,
                        field_txt == I18N.INVALID,
                        None,
                        ("sensor_plane.magnetometer.field_ut",),
                    ),
                ]
            )

        self._sensors_by_key = {}
        current = self._selection_by_app.get("sensors")
        table_rows: list[tuple[Any, ...]] = []
        for row_key, label, value, raw, warn, status_kind, source_keys in rows:
            status = status_label(raw, value, warning=warn, status_kind=status_kind)
            table_rows.append((row_key, label, style_status(status, status_kind), value))
            self._sensors_by_key[row_key] = {
                "component_id": row_key,
                "component": label,
                "status": status,
                "value": value,
                "age": age,
                "source": source,
                "source_keys": source_keys,
                "raw": raw,
                "envelope": telemetry_env,
            }

        if not table_rows:
            table_rows = [("seed", "—", I18N.NA, I18N.NA)]
        self._sync_datatable_rows(table, rows=table_rows)

        if current is None or current.key not in self._sensors_by_key:
            first_key = rows[0][0] if rows else "seed"
            first_source_keys: tuple[str, ...] = (first_key,)
            if rows:
                first_source_keys = rows[0][6]
            self._set_selection(
                SelectionContext(
                    app_id="sensors",
                    key=first_key,
                    kind="metric",
                    source="telemetry",
                    created_at_epoch=float(telemetry_env.ts_epoch),
                    payload=telemetry_env.payload,
                    ids=first_source_keys,
                )
            )

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
        system_payload = (
            system_env.payload if isinstance(system_env, EventEnvelope) and isinstance(system_env.payload, dict) else {}
        )
        nats_connected = (
            bool(system_payload.get("nats_connected"))
            if isinstance(system_payload, dict)
            else bool(self.nats_connected)
        )
        events_filter_type = system_payload.get("events_filter_type") if isinstance(system_payload, dict) else None
        events_filter_text = system_payload.get("events_filter_text") if isinstance(system_payload, dict) else None
        events_filter_trust = system_payload.get("events_filter_trust") if isinstance(system_payload, dict) else None
        events_filter_trust = self._normalize_events_trust_filter_token(
            events_filter_trust if events_filter_trust is not None else events_filter_text
        )

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
                        thermal_faults = {
                            str(x) for x in faults if isinstance(x, str) and x.startswith("THERMAL_TRIP:")
                        }

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
                status="ok",
                value=str(events_filter_type or I18N.bidi("off", "выкл")),
                ts_epoch=None if system_env is None else float(system_env.ts_epoch),
                envelope=system_env,
            ),
            SystemStateBlock(
                block_id="events_filter_text",
                title=I18N.bidi("Events text filter", "Фильтр событий по тексту"),
                status="ok",
                value=str(events_filter_text or I18N.bidi("off", "выкл")),
                ts_epoch=None if system_env is None else float(system_env.ts_epoch),
                envelope=system_env,
            ),
            SystemStateBlock(
                block_id="events_filter_trust",
                title=I18N.bidi("Events trust filter", "Фильтр событий по доверию"),
                status="ok",
                value=str(events_filter_trust),
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
        current = self._selection_by_app.get("diagnostics")
        table_rows: list[tuple[Any, ...]] = []
        for block in blocks:
            age_s = None if block.ts_epoch is None else max(0.0, now - float(block.ts_epoch))
            status = status_label(block.status)
            table_rows.append((block.block_id, block.title, status, block.value, I18N.fmt_age_compact(age_s)))
            self._diagnostics_by_key[block.block_id] = {
                "block_id": block.block_id,
                "title": block.title,
                "status": status,
                "value": block.value,
                "age": I18N.fmt_age_compact(age_s),
                "envelope": block.envelope,
            }
        if not table_rows:
            table_rows = [("seed", "—", I18N.NA, I18N.NA, I18N.NA)]
        self._sync_datatable_rows(table, rows=table_rows)

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
                    payload=env.payload
                    if isinstance(env, EventEnvelope)
                    else self._diagnostics_by_key.get(first_key, {}),
                    ids=(first_key,),
                )
            )

    def _render_mission_table(self) -> None:
        try:
            table = self.query_one("#mission-table", DataTable)
        except Exception:
            return

        def seed_empty() -> None:
            self._mission_by_key = {}
            self._selection_by_app.pop("mission", None)
            self._sync_datatable_rows(
                table,
                rows=[
                    (
                        "seed",
                        I18N.bidi("Mission", "Миссия"),
                        I18N.bidi("Non-goal", "Не цель"),
                        I18N.bidi("No mission/task data", "Нет данных миссии/задач"),
                    )
                ],
            )

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
        current = self._selection_by_app.get("mission")
        table_rows: list[tuple[Any, ...]] = []

        def row(key: str, item: str, status: str, value: str, *, record: dict[str, Any]) -> None:
            table_rows.append((key, item, status, value))
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

        if not table_rows:
            table_rows = [
                (
                    "seed",
                    I18N.bidi("Mission", "Миссия"),
                    I18N.NA,
                    I18N.bidi("No mission/task data", "Нет данных миссии/задач"),
                )
            ]
        self._sync_datatable_rows(table, rows=table_rows)

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

    def _events_filtered_sorted(self) -> list[Any]:
        if self._incident_store is None:
            return []

        def severity_rank(sev: str) -> int:
            return {"A": 0, "C": 1, "W": 2, "I": 3}.get((sev or "").upper(), 4)

        def passes(inc: Any) -> bool:
            if self._events_filter_type and (inc.type or "") != self._events_filter_type:
                return False
            if not self._events_filter_text:
                return True
            needle = self._normalize_events_trust_filter_token(self._events_filter_text)
            trust_marker = str(self._provenance_marker(channel="events", subject=inc.subject)).lower()
            if needle in {"trusted", "untrusted"}:
                return trust_marker == needle
            hay = " ".join(
                [
                    str(inc.type or ""),
                    str(inc.source or ""),
                    str(inc.subject or ""),
                    trust_marker,
                    str(inc.title or ""),
                    str(inc.description or ""),
                ]
            ).lower()
            return needle in hay

        self._incident_store.refresh()
        incidents = [inc for inc in self._incident_store.list_incidents() if passes(inc)]
        if not incidents:
            return []
        return sorted(
            incidents,
            key=lambda inc: (bool(inc.acked), severity_rank(inc.severity), -float(inc.last_seen)),
        )

    def _move_events_selection(self, direction: int) -> None:
        incidents_sorted = self._events_filtered_sorted()
        if not incidents_sorted:
            return
        visible = incidents_sorted[: self._max_events_table_rows]
        if not visible:
            return
        current = self._selection_by_app.get("events")
        current_key = current.key if current is not None else None
        keys = [inc.incident_id for inc in visible]
        try:
            idx = keys.index(current_key) if current_key is not None else 0
        except ValueError:
            idx = 0
        new_idx = max(0, min(len(visible) - 1, idx + int(direction)))
        selected = visible[new_idx]
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
        self._render_events_table()
        if self.active_screen == "events":
            self._refresh_inspector()

    def _render_events_table(self) -> None:
        try:
            table = self.query_one("#events-table", DataTable)
        except Exception:
            return

        if self._incident_store is None:
            self._selection_by_app.pop("events", None)
            self._sync_datatable_rows(
                table,
                rows=[("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA)],
            )
            return

        incidents_sorted = self._events_filtered_sorted()
        if not incidents_sorted:
            self._selection_by_app.pop("events", None)
            self._sync_datatable_rows(
                table,
                rows=[("seed", "—", I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA, I18N.NA)],
            )
            return

        current = self._selection_by_app.get("events")
        selected_key = current.key if current is not None else None

        by_incident_id = {str(inc.incident_id): inc for inc in incidents_sorted}

        table_id = str(getattr(table, "id", "") or "")
        prev_keys = self._datatable_row_keys.get(table_id)

        ordered_incident_ids: list[str] = []
        if prev_keys:
            for key in prev_keys:
                if key in by_incident_id:
                    ordered_incident_ids.append(key)

        for inc in incidents_sorted:
            inc_id = str(inc.incident_id)
            if inc_id in ordered_incident_ids:
                continue
            ordered_incident_ids.append(inc_id)

        rows: list[tuple[Any, ...]] = []
        now = time.time()
        for incident_id in ordered_incident_ids[: self._max_events_table_rows]:
            inc = by_incident_id[incident_id]
            age_s = max(0.0, now - float(inc.last_seen))
            age_text = I18N.fmt_age_compact(age_s)
            acked_text = I18N.yes_no(bool(inc.acked))
            trust_text = self._provenance_marker(channel="events", subject=inc.subject)
            rows.append(
                (
                    incident_id,
                    inc.severity,
                    self._event_type_label(inc.type),
                    I18N.fmt_na(inc.source),
                    I18N.fmt_na(inc.subject),
                    trust_text,
                    age_text,
                    str(int(inc.count)) if isinstance(inc.count, int) else I18N.NA,
                    acked_text,
                )
            )

        self._sync_datatable_rows(table, rows=rows)

        if selected_key is None or str(selected_key) not in by_incident_id:
            selected = incidents_sorted[0]
            self._set_selection(
                SelectionContext(
                    app_id="events",
                    key=str(selected.incident_id),
                    kind="incident",
                    source=selected.source,
                    created_at_epoch=selected.first_seen,
                    payload=selected,
                    ids=(selected.rule_id, selected.type, selected.subject),
                )
            )
            selected_key = str(selected.incident_id)

        if selected_key is not None and selected_key in ordered_incident_ids:
            try:
                cursor_row = getattr(table, "cursor_row", None)
                keys = self._datatable_row_keys.get(table_id) or []
                cursor_key = keys[cursor_row] if isinstance(cursor_row, int) and 0 <= cursor_row < len(keys) else None
                if cursor_key != selected_key:
                    table.move_cursor(
                        row=ordered_incident_ids.index(selected_key),
                        column=0,
                        animate=False,
                        scroll=False,
                    )
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)

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
                        with Vertical(id="radar-left"):
                            if self._radar_renderer_effective == "unicode":
                                yield RadarPpi(id="radar-ppi")
                            elif self._radar_renderer_effective == "kitty" and RadarBitmapTGP is not None:
                                yield RadarBitmapTGP(id="radar-ppi")
                            elif self._radar_renderer_effective == "sixel" and RadarBitmapSixel is not None:
                                yield RadarBitmapSixel(id="radar-ppi")
                            elif RadarBitmapAuto is not None:
                                yield RadarBitmapAuto(id="radar-ppi")
                            else:
                                yield RadarPpi(id="radar-ppi")
                            legend = Static(id="radar-legend")
                            legend.border_title = I18N.bidi("Legend", "Легенда")
                            yield legend
                        radar_table: OrionDataTable = OrionDataTable(id="radar-table")
                        radar_table.add_columns(
                            I18N.bidi("Track", "Трек"),
                            I18N.bidi("Status", "Статус"),
                            I18N.bidi("Range", "Дальность"),
                            I18N.bidi("Bearing", "Пеленг"),
                            I18N.bidi("Vr", "Скорость"),
                            I18N.bidi("Q", "Кач"),
                            I18N.bidi("Info", "Инфо"),
                        )
                        yield radar_table

                with Container(id="screen-events"):
                    events_table: OrionDataTable = OrionDataTable(id="events-table")
                    events_table.add_columns(
                        I18N.bidi("Severity", "Серьёзн"),
                        I18N.bidi("Type", "Тип"),
                        I18N.bidi("Source", "Источник"),
                        I18N.bidi("Subject", "Тема"),
                        I18N.bidi("Trust", "Доверие"),
                        I18N.bidi("Age", "Возраст"),
                        I18N.bidi("Count", "Счётчик"),
                        I18N.bidi("Ack", "Подтв"),
                    )
                    yield events_table

                with Container(id="screen-console"):
                    console_table: OrionDataTable = OrionDataTable(id="console-table")
                    console_table.add_columns(
                        I18N.bidi("Time", "Время"),
                        I18N.bidi("Level", "Уровень"),
                        I18N.bidi("Message", "Сообщение"),
                    )
                    yield console_table

                with Container(id="screen-qiki"):
                    qiki_table: OrionDataTable = OrionDataTable(id="qiki-table")
                    qiki_table.add_columns(
                        I18N.bidi("Priority", "Приоритет"),
                        I18N.bidi("Confidence", "Уверенность"),
                        I18N.bidi("Title", "Заголовок"),
                        I18N.bidi("Justification", "Обоснование"),
                    )
                    yield qiki_table

                with Container(id="screen-profile"):
                    yield ProfilePanel(id="profile-panel")

                with Container(id="screen-summary"):
                    summary_table: OrionDataTable = OrionDataTable(id="summary-table")
                    summary_table.add_column(I18N.bidi("Block", "Блок"), width=44)
                    summary_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    summary_table.add_column(I18N.bidi("Value", "Значение"), width=30)
                    summary_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    yield summary_table

                with Container(id="screen-power"):
                    power_table: OrionDataTable = OrionDataTable(id="power-table")
                    power_table.add_column(I18N.bidi("Component", "Компонент"), width=40)
                    power_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    power_table.add_column(I18N.bidi("Value", "Значение"), width=24)
                    power_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    power_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                    yield power_table

                with Container(id="screen-sensors"):
                    sensors_table: OrionDataTable = OrionDataTable(id="sensors-table")
                    sensors_table.add_column(I18N.bidi("Sensor", "Сенсор"), width=40)
                    sensors_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    sensors_table.add_column(I18N.bidi("Value", "Значение"), width=36)
                    yield sensors_table

                with Container(id="screen-propulsion"):
                    propulsion_table: OrionDataTable = OrionDataTable(id="propulsion-table")
                    propulsion_table.add_column(I18N.bidi("Component", "Компонент"), width=40)
                    propulsion_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    propulsion_table.add_column(I18N.bidi("Value", "Значение"), width=24)
                    propulsion_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    propulsion_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                    yield propulsion_table

                with Container(id="screen-thermal"):
                    thermal_table: OrionDataTable = OrionDataTable(id="thermal-table")
                    thermal_table.add_column(I18N.bidi("Node", "Узел"), width=26)
                    thermal_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    thermal_table.add_column(I18N.bidi("Temperature", "Температура"), width=18)
                    thermal_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    thermal_table.add_column(I18N.bidi("Source", "Источник"), width=20)
                    yield thermal_table

                with Container(id="screen-diagnostics"):
                    diagnostics_table: OrionDataTable = OrionDataTable(id="diagnostics-table")
                    diagnostics_table.add_column(I18N.bidi("Block", "Блок"), width=46)
                    diagnostics_table.add_column(I18N.bidi("Status", "Статус"), width=16)
                    diagnostics_table.add_column(I18N.bidi("Value", "Значение"), width=28)
                    diagnostics_table.add_column(I18N.bidi("Age", "Возраст"), width=24)
                    yield diagnostics_table

                with Container(id="screen-mission"):
                    mission_table: OrionDataTable = OrionDataTable(id="mission-table")
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
                    rules_table: OrionDataTable = OrionDataTable(id="rules-table")
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
                output = OrionOutputLog(
                    id="command-output-log",
                    highlight=False,
                    markup=False,
                    wrap=True,
                    max_lines=output_max_lines,
                )
                output.can_focus = False
                output.border_title = I18N.bidi("Output", "Вывод")
                yield output
                yield OrionCommandInput(
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
        # Capture any stray print() output from dependencies.
        # Direct stdout/stderr writes can corrupt full-screen TUIs in some terminals.
        try:
            self.begin_capture_print(self, stdout=True, stderr=True)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

        # Cold-boot splash (no-mocks): it will render only proven statuses (NATS, BIOS event).
        self.push_screen(BootScreen(), callback=self._on_boot_complete)
        self.action_show_screen("system")
        self._init_system_panels()
        self._seed_system_panels()
        self._seed_radar_table()
        self._seed_radar_ppi()
        self._seed_events_table()
        self._seed_console_table()
        self._seed_qiki_table()
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
        self._apply_output_layout()

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
            logger.debug("orion_exception_swallowed", exc_info=True)

    def on_print(self, event: events.Print) -> None:
        # Default: drop captured print output to avoid redraw jitter.
        # If needed for debugging, set ORION_PRINT_TO_CONSOLE=1.
        if os.getenv("ORION_PRINT_TO_CONSOLE", "0") != "1":
            return
        text = (event.text or "").rstrip("\n")
        if text:
            prefix = "STDERR" if event.stderr else "STDOUT"
            self._console_log(f"{prefix}> {text}", level="warning" if event.stderr else "info")

    def _on_boot_complete(self, result: bool | None) -> None:
        # Boot screen is informational; even on failure we proceed (no-mocks: values will stay N/A).
        # Re-arm xterm mouse tracking after boot/attach to recover from terminal reset cases.
        _emit_xterm_mouse_tracking(enabled=True)
        try:
            self.set_focus(self.query_one("#command-dock", Input))
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        if result:
            self._console_log(I18N.bidi("System online", "Система в сети"), level="info")
        else:
            self._console_log(I18N.bidi("Boot aborted", "Загрузка прервана"), level="warning")

    def on_resize(self, event: events.Resize) -> None:
        # Apply after refresh so Textual has the updated terminal size; otherwise we may
        # compute density from stale dimensions under tmux/docker attach.
        self.call_after_refresh(self._apply_responsive_chrome)

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
            logger.debug("orion_exception_swallowed", exc_info=True)

        # System dashboard reflow: 2x2 -> 1x4 on narrow/tiny.
        try:
            dashboard = self.query_one("#system-dashboard")
            dashboard.set_class(density in {"tiny", "narrow"}, "dashboard-1x4")
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

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
            logger.debug("orion_exception_swallowed", exc_info=True)

        try:
            inspector = self.query_one("#orion-inspector", OrionInspector)
            inspector.styles.display = "block" if inspector_visible else "none"
            if inspector_visible:
                inspector.styles.width = inspector_width
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

        # Radar: prefer the table on narrow terminals (PPI is dense and becomes unreadable).
        try:
            ppi = self.query_one("#radar-ppi", Static)
            ppi.styles.display = "none" if density in {"tiny", "narrow"} else "block"
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

        # Compact tables on narrow panes by reducing fixed column widths.
        try:
            self._apply_table_column_widths(density=density, total_width=width)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

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
            logger.debug("orion_exception_swallowed", exc_info=True)

        # Keep the command line readable at all densities.
        self._update_command_placeholder()

    def _load_incident_rules(self, *, initial: bool = False) -> None:
        try:
            if initial:
                config = self._rules_repo.load()
                self._incident_rules = config
                self._incident_store = IncidentStore(config, max_incidents=self._max_event_incidents)
                self._console_log(
                    f"{I18N.bidi('Incident rules loaded', 'Правила инцидентов загружены')}: {len(config.rules)}",
                    level="info",
                )
                return
            result = self._rules_repo.reload(source="file/reload")
            self._incident_rules = result.config
            self._incident_store = IncidentStore(result.config, max_incidents=self._max_event_incidents)
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
                    logger.debug("orion_exception_swallowed", exc_info=True)
            try:
                table.refresh()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)

        # These tables were created with fixed widths; narrow terminals need smaller presets.
        if density in {"tiny", "narrow"}:
            set_widths("summary-table", [28, 10, 20, 12])
            set_widths("power-table", [26, 10, 16, 12, 12])
            set_widths("sensors-table", [26, 10, 38])
            set_widths("propulsion-table", [26, 10, 16, 12, 12])
            set_widths("thermal-table", [20, 10, 14, 12, 12])
            set_widths("diagnostics-table", [28, 10, 20, 12])
            set_widths("mission-table", [22, 10, 34])
            set_widths("events-table", [8, 14, 14, 22, 11, 10, 8, 6])
            set_widths("console-table", [12, 9, 40])
            set_widths("radar-table", [10, 8, 12, 12, 12, 6, 18])
        elif density == "normal":
            set_widths("summary-table", [36, 14, 26, 18])
            set_widths("power-table", [32, 14, 20, 18, 16])
            set_widths("sensors-table", [32, 14, 64])
            set_widths("propulsion-table", [32, 14, 20, 18, 16])
            set_widths("thermal-table", [24, 14, 16, 18, 16])
            set_widths("diagnostics-table", [36, 14, 24, 18])
            set_widths("mission-table", [28, 14, 52])
            set_widths("events-table", [10, 18, 16, 28, 11, 12, 10, 6])
            set_widths("console-table", [14, 10, 64])
            set_widths("radar-table", [12, 10, 14, 14, 14, 8, 26])
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
            logger.debug("orion_exception_swallowed", exc_info=True)

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
            logger.debug("orion_exception_swallowed", exc_info=True)

        console_active = self.active_screen == "console"
        cursor_row_before = getattr(table, "cursor_row", None)
        was_at_bottom = (
            isinstance(cursor_row_before, int) and table.row_count > 0 and cursor_row_before == table.row_count - 1
        )
        current_selection = self._selection_by_app.get("console")

        try:
            table.add_row(ts, str(level_label), msg, key=key)
            self._console_by_key[key] = {
                "kind": "console",
                "timestamp": ts,
                "created_at_epoch": time.time(),
                "level": normalized_level,
                "message": msg,
            }

            if current_selection is None:
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

            # Avoid cursor jumps while other screens are active.
            if console_active and (was_at_bottom or current_selection is None):
                try:
                    table.move_cursor(row=table.row_count - 1, column=0, animate=False, scroll=True)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)

            if self._max_console_rows > 0:
                try:
                    while table.row_count > self._max_console_rows:
                        cast(Any, table).remove_row(0)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

        if console_active:
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

        nav_rows_raw = [
            ("link", I18N.bidi("Link", "Связь"), I18N.online_offline(online)),
            ("updated", I18N.bidi("Updated", "Обновлено"), updated),
            ("age", I18N.bidi("Age", "Возраст"), age_value),
            ("position", I18N.bidi("Position", "Позиция"), fmt_pos()),
            (
                "velocity",
                I18N.bidi("Velocity", "Скорость"),
                I18N.num_unit(get("velocity"), "m/s", "м/с", digits=2),
            ),
            ("heading", I18N.bidi("Heading", "Курс"), I18N.num_unit(get("heading"), "°", "°", digits=1)),
            ("roll", I18N.bidi("Roll", "Крен"), fmt_att_deg("roll_rad")),
            ("pitch", I18N.bidi("Pitch", "Тангаж"), fmt_att_deg("pitch_rad")),
            ("yaw", I18N.bidi("Yaw", "Рыскание"), fmt_att_deg("yaw_rad")),
        ]

        # Power panel height may be small in tmux; keep the first rows as the most important.
        power_rows_raw = [
            (
                "state_of_charge",
                I18N.bidi("State of charge", "Уровень заряда"),
                I18N.pct(get("power.soc_pct"), digits=2),
            ),
            (
                "power_input",
                I18N.bidi("Power input", "Входная мощность"),
                I18N.num_unit(get("power.power_in_w"), "W", "Вт", digits=1),
            ),
            (
                "power_output",
                I18N.bidi("Power output", "Выходная мощность"),
                I18N.num_unit(get("power.power_out_w"), "W", "Вт", digits=1),
            ),
            (
                "bus_voltage",
                I18N.bidi("Bus voltage", "Напряжение шины"),
                I18N.num_unit(get("power.bus_v"), "V", "В", digits=2),
            ),
            (
                "bus_current",
                I18N.bidi("Bus current", "Ток шины"),
                I18N.num_unit(get("power.bus_a"), "A", "А", digits=2),
            ),
        ]

        def thermal_nodes_map() -> dict[str, Any]:
            nodes = get("thermal.nodes")
            if not isinstance(nodes, list):
                return {}
            out: dict[str, Any] = {}
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = node.get("id")
                if isinstance(node_id, str) and node_id:
                    out[node_id] = node.get("temp_c")
            return out

        def thermal_node_label(node_id: str) -> str:
            labels = {
                "core": I18N.bidi("Core", "Ядро"),
                "pdu": I18N.bidi("PDU", "ПДУ"),
                "battery": I18N.bidi("Battery", "Батарея"),
                "supercap": I18N.bidi("Supercap", "Суперкап"),
                "dock_bridge": I18N.bidi("Dock bridge", "Док-мост"),
                "hull": I18N.bidi("Hull", "Корпус"),
            }
            return labels.get(node_id, node_id)

        thermal_nodes = thermal_nodes_map()
        thermal_node_order = ["core", "pdu", "battery", "supercap", "dock_bridge", "hull"]
        thermal_node_rows: list[tuple[str, str]] = []
        used = set()
        for node_id in thermal_node_order:
            if node_id not in thermal_nodes:
                continue
            thermal_node_rows.append(
                (thermal_node_label(node_id), I18N.num_unit(thermal_nodes.get(node_id), "°C", "°C", digits=1))
            )
            used.add(node_id)

        for node_id in sorted(thermal_nodes.keys()):
            if node_id in used:
                continue
            thermal_node_rows.append(
                (thermal_node_label(node_id), I18N.num_unit(thermal_nodes.get(node_id), "°C", "°C", digits=1))
            )

        # Keep the panel compact: show a few most important nodes + canonical external/core temps.
        thermal_node_rows = thermal_node_rows[:4]

        thermal_rows_raw = [
            *((f"node_{idx}", label, value) for idx, (label, value) in enumerate(thermal_node_rows)),
            (
                "external_temp",
                I18N.bidi("External temperature", "Наружная температура"),
                I18N.num_unit(get("temp_external_c"), "°C", "°C", digits=1),
            ),
            (
                "core_temp",
                I18N.bidi("Core temperature", "Температура ядра"),
                I18N.num_unit(get("temp_core_c"), "°C", "°C", digits=1),
            ),
        ]

        struct_rows_raw = [
            ("hull", I18N.bidi("Hull", "Корпус"), I18N.pct(get("hull.integrity"), digits=1)),
            (
                "radiation",
                I18N.bidi("Radiation", "Радиация"),
                I18N.num_unit(get("radiation_usvh"), "µSv/h", "мкЗв/ч", digits=2),
            ),
            (
                "cpu",
                I18N.bidi("Central processing unit usage", "Загрузка центрального процессора"),
                I18N.pct(get("cpu_usage"), digits=1),
            ),
            ("memory", I18N.bidi("Memory usage", "Загрузка памяти"), I18N.pct(get("memory_usage"), digits=1)),
        ]

        nav_rows = self._compact_system_panel_rows(
            nav_rows_raw,
            essential_keys={"link", "age", "velocity", "heading"},
            max_rows=6,
        )
        power_rows = self._compact_system_panel_rows(
            power_rows_raw,
            essential_keys={"state_of_charge", "power_input", "power_output"},
            max_rows=5,
        )
        thermal_rows = self._compact_system_panel_rows(
            thermal_rows_raw,
            essential_keys={"external_temp", "core_temp"},
            max_rows=5,
        )
        struct_rows = self._compact_system_panel_rows(
            struct_rows_raw,
            essential_keys={"hull", "radiation"},
            max_rows=3,
        )

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
            panel.update(self._system_table([(label, value) for _, label, value in rows]))

    def _seed_radar_table(self) -> None:
        try:
            table = self.query_one("#radar-table", DataTable)
        except Exception:
            return
        self._selection_by_app.pop("radar", None)
        table.clear()
        empty = "—"
        table.add_row(empty, empty, empty, empty, empty, empty, I18N.NO_TRACKS_YET)

    def _seed_radar_ppi(self) -> None:
        try:
            ppi = self.query_one("#radar-ppi")
        except Exception:
            return
        if self._ppi_renderer is None:
            try:
                cast(Any, ppi).update(I18N.bidi("Radar display unavailable", "Экран радара недоступен"))
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return
        if self._radar_renderer_effective != "unicode":
            if render_bitmap_ppi is None or not hasattr(ppi, "image"):
                try:
                    cast(Any, ppi).update(I18N.bidi("Bitmap radar unavailable", "Битмап-радар недоступен"))
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
                self._render_radar_legend()
                return
            try:
                img = render_bitmap_ppi(
                    [],
                    width_px=int(self._ppi_width_cells) * 12,
                    height_px=int(self._ppi_height_cells) * 24,
                    max_range_m=float(self._ppi_max_range_m),
                    view=self._radar_view,
                    zoom=self._radar_zoom,
                    pan_u_m=self._radar_pan_u_m,
                    pan_v_m=self._radar_pan_v_m,
                    iso_yaw_deg=self._radar_iso_yaw_deg,
                    iso_pitch_deg=self._radar_iso_pitch_deg,
                    selected_track_id=None,
                    draw_overlays=True,
                )
                ppi.image = img  # type: ignore[attr-defined]
            except Exception:
                try:
                    cast(Any, ppi).update(I18N.bidi("Bitmap radar error", "Ошибка битмап-радара"))
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
            self._render_radar_legend()
            return
        if BraillePpiRenderer is not None and isinstance(self._ppi_renderer, BraillePpiRenderer):
            try:
                cast(Any, ppi).update(
                    self._ppi_renderer.render_tracks(
                        [],
                        view=self._radar_view,
                        zoom=self._radar_zoom,
                        pan_u_m=self._radar_pan_u_m,
                        pan_v_m=self._radar_pan_v_m,
                        rich=True,
                        selected_track_id=None,
                        iso_yaw_deg=self._radar_iso_yaw_deg,
                        iso_pitch_deg=self._radar_iso_pitch_deg,
                    )
                )
            except Exception:
                return
            self._render_radar_legend()
            return
        try:
            ppi.update(self._ppi_renderer.render_tracks([]))
        except Exception:
            return
        self._render_radar_legend()

    def _seed_events_table(self) -> None:
        try:
            table = self.query_one("#events-table", DataTable)
        except Exception:
            return
        if self._incident_rules is not None:
            self._incident_store = IncidentStore(self._incident_rules, max_incidents=self._max_event_incidents)
        self._events_live = True
        self._events_unread_count = 0
        self._selection_by_app.pop("events", None)
        self._events_filter_type = None
        self._events_filter_text = None
        table.clear()
        table.add_row(
            "—",
            I18N.bidi("No events yet", "Событий нет"),
            "—",
            "—",
            "—",
            "—",
            "—",
            "—",
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
                logger.debug("orion_exception_swallowed", exc_info=True)

    def _seed_qiki_table(self) -> None:
        try:
            table = self.query_one("#qiki-table", DataTable)
        except Exception:
            return
        self._qiki_by_key = {}
        self._qiki_last_response = None
        self._selection_by_app.pop("qiki", None)
        table.clear()
        table.add_row("—", "—", I18N.bidi("No proposals", "Нет предложений"), "—", key="seed")

    def _render_qiki_table(self) -> None:
        try:
            table = self.query_one("#qiki-table", DataTable)
        except Exception:
            return

        resp = self._qiki_last_response
        self._qiki_by_key = {}

        if resp is None or not resp.proposals:
            self._selection_by_app.pop("qiki", None)
            self._sync_datatable_rows(
                table,
                rows=[("seed", "—", "—", I18N.bidi("No proposals", "Нет предложений"), "—")],
            )
            return

        rows_by_key: dict[str, tuple[Any, ...]] = {}
        for p in resp.proposals:
            key = str(p.proposal_id)
            rows_by_key[key] = (
                key,
                str(p.priority),
                f"{p.confidence:.2f}",
                I18N.bidi(p.title.en, p.title.ru),
                I18N.bidi(p.justification.en, p.justification.ru),
            )
            self._qiki_by_key[key] = {
                "kind": "qiki_proposal",
                "proposal": p.model_dump(mode="json"),
                "request_id": str(resp.request_id),
                "mode": str(resp.mode),
                "ok": bool(resp.ok),
            }

        table_id = str(getattr(table, "id", "") or "")
        prev_keys = self._datatable_row_keys.get(table_id) or []

        ordered_keys: list[str] = []
        for key in prev_keys:
            if key in rows_by_key:
                ordered_keys.append(key)
        for key in rows_by_key:
            if key not in ordered_keys:
                ordered_keys.append(key)

        rows: list[tuple[Any, ...]] = [rows_by_key[key] for key in ordered_keys]
        self._sync_datatable_rows(table, rows=rows)

        current = self._selection_by_app.get("qiki")
        selected_key = current.key if current is not None else None
        if selected_key is None or str(selected_key) not in self._qiki_by_key:
            first_key = ordered_keys[0]
            self._set_selection(
                SelectionContext(
                    app_id="qiki",
                    key=first_key,
                    kind="proposal",
                    source="qiki",
                    created_at_epoch=time.time(),
                    payload=self._qiki_by_key[first_key],
                    ids=(first_key,),
                )
            )

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
                logger.debug("orion_exception_swallowed", exc_info=True)

    async def _init_nats(self) -> None:
        self._boot_nats_init_done = False
        self._boot_nats_error = ""
        self.nats_client = NATSClient()
        try:
            await self.nats_client.connect()
            self.nats_connected = True
            self._log_msg(f"{I18N.bidi('NATS connected', 'NATS подключен')}")
            self._update_system_snapshot()
        except Exception as e:
            self.nats_connected = False
            self._boot_nats_error = str(e)
            self._log_msg(f"{I18N.bidi('NATS connect failed', 'NATS не подключился')}: {e}")
            self._update_system_snapshot()
            return
        finally:
            self._boot_nats_init_done = True

        # Subscriptions are best-effort; missing streams shouldn't crash UI.
        try:
            await self.nats_client.subscribe_system_telemetry(self.handle_telemetry_data)
            self._log_msg(f"{I18N.bidi('Subscribed', 'Подписка')}: qiki.telemetry")
        except Exception as e:
            self._log_msg(f"{I18N.bidi('Telemetry subscribe failed', 'Подписка телеметрии не удалась')}: {e}")

        try:
            await self.nats_client.subscribe_tracks(self.handle_track_data)
            self._log_msg(f"{I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('radar tracks', 'радар треки')}")
        except Exception as e:
            self._log_msg(f"{I18N.bidi('Radar tracks subscribe failed', 'Подписка треков радара не удалась')}: {e}")

        try:
            await self.nats_client.subscribe_events(self.handle_event_data)
            self._log_msg(f"{I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('events wildcard', 'события *')}")
        except Exception as e:
            self._log_msg(f"{I18N.bidi('Events subscribe failed', 'Подписка событий не удалась')}: {e}")

        try:
            await self.nats_client.subscribe_control_responses(self.handle_control_response)
            self._log_msg(
                f"{I18N.bidi('Subscribed', 'Подписка')}: {I18N.bidi('control responses', 'ответы управления')}"
            )
        except Exception as e:
            self._log_msg(
                f"{I18N.bidi('Control responses subscribe failed', 'Подписка ответов управления не удалась')}: {e}"
            )

        try:
            await self.nats_client.subscribe_qiki_responses(self.handle_qiki_response)
            self._log_msg(f"{I18N.bidi('Subscribed', 'Подписка')}: QIKI")
        except Exception as e:
            self._log_msg(f"{I18N.bidi('QIKI subscribe failed', 'Подписка QIKI не удалась')}: {e}")

        await self._hydrate_qiki_mode_from_jetstream()

    async def _hydrate_qiki_mode_from_jetstream(self) -> None:
        """Hydrate QIKI mode from JetStream (no-mocks, no new contracts).

        Core-NATS events are not persistent; if `qiki.events.v1.system_mode` is published
        before ORION subscribes, the header may remain `N/A/—` until the next mode change.

        If the events stream is enabled, we can fetch the last-known mode from JetStream
        and render it immediately.
        """
        if not self.nats_client:
            return
        try:
            data = await self.nats_client.fetch_last_event_json(stream=EVENTS_STREAM_NAME, subject=SYSTEM_MODE_EVENT)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        mode = data.get("mode")
        if isinstance(mode, str) and mode.strip():
            self._qiki_mode = mode.strip()
            try:
                self.query_one("#orion-header", OrionHeader).update_mode(self._qiki_mode)
            except Exception:
                return

    def _refresh_header(self) -> None:
        try:
            header = self.query_one("#orion-header", OrionHeader)
            header.update_mode(self._qiki_mode)
        except Exception:
            return

        telemetry_env = self._snapshots.get_last("telemetry")
        if telemetry_env is None or not isinstance(telemetry_env.payload, dict):
            return
        try:
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
        height = int(getattr(getattr(inspector, "size", None), "height", 0) or 0)
        compact = bool(self._density in {"tiny", "narrow"} or (height and height < 28))

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
            env = self._snapshots.get_last("telemetry")
            if env is not None and isinstance(env.payload, dict):
                raw_preview = OrionInspector.safe_preview(env.payload, max_lines=8 if compact else 24)
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
                mission: dict[str, Any] = {}
                if env is not None and isinstance(env.payload, dict):
                    payload = env.payload
                    mission = (
                        cast(dict[str, Any], payload.get("mission"))
                        if isinstance(payload.get("mission"), dict)
                        else cast(dict[str, Any], payload)
                    )
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
                    (
                        I18N.bidi("Source keys", "Ключи источника")
                        if ctx.source == "telemetry"
                        else I18N.bidi("Identifiers", "Идентификаторы"),
                        ", ".join(ctx.ids) if ctx.ids else I18N.NA,
                    ),
                    (
                        I18N.bidi("Timestamp", "Время"),
                        time.strftime("%H:%M:%S", time.localtime(ctx.created_at_epoch))
                        if isinstance(ctx.created_at_epoch, (int, float))
                        else I18N.NA,
                    ),
                ]
            )

            if ctx.source == "telemetry" and ctx.ids:
                dictionary = self._get_telemetry_dictionary_by_path()
                lines: list[str] = []
                why_lines: list[str] = []
                action_lines: list[str] = []
                for raw_key in ctx.ids[:12]:
                    canon = self._canonicalize_telemetry_path(raw_key)
                    meta = dictionary.get(canon) if isinstance(dictionary, dict) else None
                    if not isinstance(meta, dict):
                        lines.append(f"{raw_key}: {I18N.NA}")
                        continue
                    label = meta.get("label") or I18N.NA
                    unit = meta.get("unit") or ""
                    typ = meta.get("type") or ""
                    why = meta.get("why_operator") or ""
                    hint = meta.get("actions_hint") or ""
                    suffix = ", ".join([x for x in (unit, typ) if str(x).strip()])
                    if suffix:
                        lines.append(f"{raw_key}: {label} ({suffix})")
                    else:
                        lines.append(f"{raw_key}: {label}")

                    if str(why).strip():
                        why_lines.append(f"{raw_key}: {why}" if len(ctx.ids) > 1 else str(why))
                    if str(hint).strip():
                        action_lines.append(f"{raw_key}: {hint}" if len(ctx.ids) > 1 else str(hint))

                fields_rows.append(
                    (
                        I18N.bidi("Meaning", "Смысл"),
                        "\n".join(lines) if lines else I18N.NA,
                    )
                )

                if why_lines:
                    fields_rows.append(
                        (
                            I18N.bidi("Why", "Зачем"),
                            "\n".join(why_lines[:6]),
                        )
                    )
                if action_lines:
                    fields_rows.append(
                        (
                            I18N.bidi("Actions hint", "Подсказка действий"),
                            "\n".join(action_lines[:6]),
                        )
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
                            (I18N.bidi("Type", "Тип"), self._event_type_label(str(incident.type or ""))),
                            (I18N.bidi("Source", "Источник"), I18N.fmt_na(incident.source)),
                            (I18N.bidi("Subject", "Тема"), I18N.fmt_na(incident.subject)),
                            (
                                I18N.bidi("Trust", "Доверие"),
                                self._provenance_marker(channel="events", subject=incident.subject),
                            ),
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
                # Keep Events inspector compact so Raw data remains visible in tmux splits.
                max_fields = 10
                if len(fields_rows) > max_fields:
                    fields_rows[:] = fields_rows[:max_fields]
                    fields_rows.append(
                        (
                            I18N.bidi("More", "Ещё"),
                            I18N.bidi("See raw data", "Смотрите сырые данные"),
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
                    logger.debug("orion_exception_swallowed", exc_info=True)
                try:
                    th = rule.threshold
                except Exception:
                    th = None
                if th is not None:
                    fields_rows.extend(
                        [
                            (I18N.bidi("Op", "Операция"), I18N.fmt_na(getattr(th, "op", None))),
                            (I18N.bidi("Value", "Значение"), I18N.fmt_na(getattr(th, "value", None))),
                            (
                                I18N.bidi("Min duration", "Мин длительность"),
                                I18N.fmt_na(getattr(th, "min_duration_s", None)),
                            ),
                            (I18N.bidi("Cooldown", "Кулдаун"), I18N.fmt_na(getattr(th, "cooldown_s", None))),
                        ]
                    )
            if ctx.app_id == "radar" and isinstance(ctx.payload, dict):
                payload = ctx.payload
                range_m = payload.get("range_m", payload.get("range"))
                bearing_deg = payload.get("bearing_deg", payload.get("bearing"))
                vr_mps = payload.get("vr_mps", payload.get("velocity"))
                object_type = OrionApp._radar_object_type_code(payload)
                iff = OrionApp._radar_iff_code(payload)
                status = OrionApp._radar_status_code(payload)
                quality = payload.get("quality")
                miss_count = payload.get("miss_count", payload.get("missCount"))
                range_band = OrionApp._radar_range_band_code(payload)
                id_present = payload.get("id_present", payload.get("idPresent"))
                transponder_on = payload.get("transponder_on", payload.get("transponderOn"))
                transponder_mode = OrionApp._radar_transponder_mode_code(payload)
                transponder_id = payload.get("transponder_id", payload.get("transponderId"))
                ts_event = payload.get("ts_event", payload.get("tsEvent", payload.get("timestamp")))
                ts_ingest = payload.get("ts_ingest", payload.get("tsIngest"))
                summary_rows.extend(
                    [
                        (I18N.bidi("Range", "Дальность"), I18N.num_unit(range_m, "m", "м", digits=1)),
                        (I18N.bidi("Bearing", "Пеленг"), I18N.num_unit(bearing_deg, "°", "°", digits=1)),
                        (I18N.bidi("Status", "Статус"), I18N.fmt_na(status)),
                        (I18N.bidi("Quality", "Качество"), I18N.fmt_na(self._fmt_num(quality, digits=2))),
                        (I18N.bidi("Object type", "Тип объекта"), I18N.fmt_na(object_type)),
                        (I18N.bidi("IFF", "Свой-чужой"), I18N.fmt_na(iff)),
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
                        (I18N.bidi("IFF", "Свой-чужой"), I18N.fmt_na(iff)),
                        (I18N.bidi("Status", "Статус"), I18N.fmt_na(status)),
                        (I18N.bidi("Quality", "Качество"), I18N.fmt_na(self._fmt_num(quality, digits=2))),
                        (I18N.bidi("Range band", "Диапазон"), I18N.fmt_na(range_band)),
                        (I18N.bidi("ID present", "IFF/ID"), I18N.fmt_na(id_present)),
                        (I18N.bidi("Transponder on", "Транспондер вкл"), I18N.fmt_na(transponder_on)),
                        (I18N.bidi("Transponder mode", "Режим транспондера"), I18N.fmt_na(transponder_mode)),
                        (I18N.bidi("Transponder id", "ID транспондера"), I18N.fmt_na(transponder_id)),
                        (I18N.bidi("Miss count", "Пропуски"), I18N.fmt_na(miss_count)),
                        (I18N.bidi("ts_event", "ts_event"), I18N.fmt_na(ts_event)),
                        (I18N.bidi("ts_ingest", "ts_ingest"), I18N.fmt_na(ts_ingest)),
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
                raw_preview = OrionInspector.safe_preview(ctx.payload.model_dump(), max_lines=8 if compact else 24)
            elif ctx.app_id == "events" and hasattr(ctx.payload, "__dataclass_fields__"):
                raw_preview = OrionInspector.safe_preview(asdict(ctx.payload), max_lines=8 if compact else 24)
            else:
                raw_preview = OrionInspector.safe_preview(ctx.payload, max_lines=8 if compact else 24)

        if self.active_screen == "events":
            state = I18N.bidi("Live", "Живое") if self._events_live else I18N.bidi("Paused", "Пауза")
            unread = int(self._events_unread_count) if not self._events_live else 0
            if unread > 0:
                # Put the number first so it stays visible even when truncated.
                actions.append(f"{unread} {I18N.bidi('Unread', 'Непрочитано')}")
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

        def _cap_rows(rows: list[tuple[str, str]], max_rows: int) -> list[tuple[str, str]]:
            if max_rows <= 0 or len(rows) <= max_rows:
                return rows
            more = len(rows) - max_rows
            capped = rows[:max_rows]
            capped.append((I18N.bidi("More", "Ещё"), f"{more} {I18N.bidi('rows', 'строк')}"))
            return capped

        def _cap_actions(lines: list[str], max_lines: int) -> list[str]:
            if max_lines <= 0 or len(lines) <= max_lines:
                return lines
            more = len(lines) - max_lines
            capped = lines[:max_lines]
            capped.append(f"{I18N.bidi('More actions', 'Ещё действий')}: {more}")
            return capped

        summary_rows = _cap_rows(summary_rows, 8 if compact else 16)
        fields_rows = _cap_rows(fields_rows, 10 if compact else 28)
        actions = _cap_actions(actions, 6 if compact else 20)

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
            self._log_msg(f"{I18N.bidi('Bad telemetry payload', 'Плохая телеметрия')}: {e}")
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

        if self._selection_by_app.get(self.active_screen) is None:
            self._refresh_inspector()

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
        self._log_msg(f"{I18N.bidi('Track update', 'Обновление трека')} ({updated}): {track_id}")

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
        if isinstance(payload, dict):
            ts_raw = payload.get("ts_epoch")
            if isinstance(ts_raw, (int, float)):
                ts_epoch = float(ts_raw)
        subj = str(subject or "")
        if subj == "qiki.events.v1.system_mode" and isinstance(payload, dict):
            mode = payload.get("mode")
            if isinstance(mode, str) and mode.strip():
                self._qiki_mode = mode.strip()
                try:
                    self.query_one("#orion-header", OrionHeader).update_mode(self._qiki_mode)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)

        etype = "bios" if subj == "qiki.events.v1.bios_status" else self._derive_event_type(subject, payload)
        if etype == "bios" and not self._bios_loaded_announced:
            self._bios_loaded_announced = True
            self._bios_first_status_ts_epoch = ts_epoch
            status_label = I18N.bidi("Unknown", "Неизвестно")
            components_count: Optional[int] = None
            if isinstance(payload, dict):
                all_go = payload.get("all_systems_go")
                if isinstance(all_go, bool):
                    status_label = I18N.bidi("OK", "ОК") if all_go else I18N.bidi("FAIL", "СБОЙ")
                components = payload.get("components")
                if isinstance(components, list):
                    components_count = len(components)
            msg = f"{I18N.bidi('BIOS loaded', 'BIOS загрузился')}: {status_label}"
            if components_count is not None:
                msg = f"{msg} ({I18N.bidi('components', 'компоненты')}: {components_count})"
            self._calm_log(msg, level="info")
            self._log_msg(msg)
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

        # P0 observability (no new subjects): publish a best-effort audit event when an incident is opened.
        # This makes incident creation provable via record/replay without scraping the TUI.
        if matched_incidents and self.nats_client:
            for inc in matched_incidents:
                if int(getattr(inc, "count", 0) or 0) != 1:
                    continue
                if str(getattr(inc, "state", "") or "") != "active":
                    continue
                try:
                    await self._publish_audit_event(
                        {
                            "schema_version": 1,
                            "category": "audit",
                            "kind": "incident_open",
                            "source": "orion",
                            "subject": "incident",
                            # Use the event timestamp when available (replay determinism).
                            "ts_epoch": ts_epoch,
                            "incident_key": str(getattr(inc, "key", "") or getattr(inc, "incident_id", "")),
                            "incident_id": str(getattr(inc, "incident_id", "")) or None,
                            "rule_id": str(getattr(inc, "rule_id", "")) or None,
                            "severity": str(getattr(inc, "severity", "")) or None,
                        }
                    )
                except Exception as exc:
                    self._console_log(
                        f"{I18N.bidi('Audit publish failed', 'Не удалось отправить аудит')}: {exc}",
                        level="warning",
                    )

        if self._events_live:
            # Re-render under active filter and keep selection consistent.
            self._render_events_table()
        else:
            for inc in matched_incidents:
                try:
                    self._events_unread_incident_ids.add(
                        str(getattr(inc, "incident_id", "")) or str(getattr(inc, "key", ""))
                    )
                except Exception:
                    continue
            self._events_unread_count = len(self._events_unread_incident_ids)
            try:
                self.query_one("#orion-sidebar", OrionSidebar).refresh()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            try:
                self.query_one("#orion-keybar", OrionKeybar).refresh()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
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

    @staticmethod
    def _provenance_marker(*, channel: str, subject: Any) -> str:
        subj = str(subject or "").strip().lower()
        if channel == "events":
            events_prefix = EVENTS_V1_WILDCARD.replace(">", "").strip().lower()
            return "TRUSTED" if bool(events_prefix) and subj.startswith(events_prefix) else "UNTRUSTED"
        if channel == "control_response":
            trusted_subject = str(RESPONSES_CONTROL).strip().lower()
            return "TRUSTED" if trusted_subject and subj == trusted_subject else "UNTRUSTED"
        return "UNTRUSTED"

    @staticmethod
    def _normalize_events_trust_filter_token(token: Any) -> str:
        raw = str(token or "").strip().lower()
        if raw in {"trusted", "доверенный", "доверено"}:
            return "trusted"
        if raw in {"untrusted", "недоверенный", "недоверено"}:
            return "untrusted"
        if raw in {"off", "none", "all", "*", "выкл", "выключить", "откл", "сброс", "нет", ""}:
            return "off"
        return raw

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
        # Operator intent for "X" is to clear (remove) acknowledged incidents.
        # Implement it deterministically: mark all acked incidents as cleared (to apply cooldown),
        # then sweep cleared+acked from the store.
        for inc in list(self._incident_store.list_incidents()):
            try:
                if bool(getattr(inc, "acked", False)):
                    self._incident_store.clear(str(getattr(inc, "incident_id", "")))
            except Exception:
                continue
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
            logger.debug("orion_exception_swallowed", exc_info=True)
        try:
            self.query_one("#orion-keybar", OrionKeybar).refresh()
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

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

        prompt = f"{I18N.bidi('Acknowledge incident?', 'Подтвердить инцидент?')} {key} ({I18N.bidi('Y/N', 'Да/Нет')})"

        def after(decision: bool | None) -> None:
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
            title = I18N.bidi("Neutrino Burst Link", "Нейтринный канал")

        prompt = (
            f"{I18N.bidi('Send command?', 'Отправить команду?')} "
            f"{title} → {I18N.yes_no(not is_on)} ({cmd}) "
            f"({I18N.bidi('Y/N', 'Да/Нет')})"
        )

        def after(decision: bool | None) -> None:
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
            logger.debug("orion_exception_swallowed", exc_info=True)
        try:
            self.query_one("#orion-keybar", OrionKeybar).refresh()
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
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
            self._incident_store = IncidentStore(result.config, max_incidents=self._max_event_incidents)
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

        def after(decision: bool | None) -> None:
            if decision:
                self._apply_rule_enabled_change(rid, target_enabled)
            else:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")

        self.push_screen(ConfirmDialog(prompt), after)

    async def handle_control_response(self, data: dict) -> None:
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        subject = data.get("subject") if isinstance(data, dict) else None
        trust_marker = self._provenance_marker(channel="control_response", subject=subject)
        success_raw = payload.get("success")
        if success_raw is None:
            success_raw = payload.get("ok")
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
        if not message:
            err_detail = payload.get("error_detail")
            if isinstance(err_detail, dict):
                message = err_detail.get("message")
        level = "warning" if trust_marker == "UNTRUSTED" else "info"
        self._console_log(
            f"{I18N.bidi('Control response', 'Ответ управления')}[{trust_marker}]: "
            f"{I18N.bidi('success', 'успех')}={success} {I18N.bidi('request', 'запрос')}={request} {message or ''}".strip(),
            level=level,
        )

    async def handle_qiki_response(self, data: dict) -> None:
        verbose = os.getenv("ORION_QIKI_VERBOSE", "0") == "1"
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        raw_req_id = payload.get("request_id") or payload.get("requestId")

        try:
            resp = QikiChatResponseV1.model_validate(payload)
        except ValidationError as e:
            # Best-effort: keep request_id visible even if schema is invalid.
            request = I18N.NA if raw_req_id is None else str(raw_req_id)
            kind = payload.get("kind") or payload.get("type") or "response"
            errors = e.errors()
            if errors:
                first = errors[0]
                loc = ".".join(str(x) for x in first["loc"])
                msg = str(first["msg"])
            else:
                loc = ""
                msg = "invalid"
            detail = f"{loc}: {msg}" if loc else str(msg)
            self._console_log(f"QIKI: invalid {kind} ({I18N.bidi('request', 'запрос')}={request})")
            self._calm_log(f"QIKI schema error: {detail}")
            return
        except Exception:
            kind = payload.get("kind") or payload.get("type") or "response"
            request = I18N.NA if raw_req_id is None else str(raw_req_id)
            self._console_log(f"QIKI: invalid {kind} ({I18N.bidi('request', 'запрос')}={request}) {payload}".strip())
            return

        req_id = str(resp.request_id)
        if req_id not in self._qiki_pending and os.getenv("QIKI_LOG_FOREIGN_RESPONSES", "0") != "1":
            return
        self._qiki_pending.pop(req_id, None)

        if not resp.ok:
            code = resp.error.code if resp.error else "UNKNOWN"
            if resp.error and resp.error.message:
                msg_en = resp.error.message.en
                msg_ru = resp.error.message.ru
                msg = I18N.bidi(msg_en, msg_ru)
            else:
                msg = I18N.NA
            self._console_log(
                f"QIKI: {I18N.bidi('error', 'ошибка')} "
                f"({I18N.bidi('code', 'код')}={code}, {I18N.bidi('request', 'запрос')}={resp.request_id}) "
                f"{msg}".strip(),
                level="warning",
            )

        if not verbose:
            if resp.ok:
                body_en = resp.reply.body.en if resp.reply and resp.reply.body else ""
                body_ru = resp.reply.body.ru if resp.reply and resp.reply.body else ""
                body = I18N.bidi(body_en or "QIKI", body_ru or "QIKI")
            else:
                body = I18N.bidi("QIKI error", "Ошибка QIKI")
            self._calm_log(body)
            self._qiki_last_response = resp
            self._render_qiki_table()
            return

        title = resp.reply.title.en if resp.reply else "QIKI"
        ru_title = resp.reply.title.ru if resp.reply else "QIKI"
        proposals = len(resp.proposals or [])
        ok = I18N.yes_no(resp.ok)
        self._console_log(
            f"QIKI: {I18N.bidi(title, ru_title)} "
            f"({I18N.bidi('ok', 'ок')}={ok}, {I18N.bidi('proposals', 'предложений')}={proposals}, "
            f"{I18N.bidi('request', 'запрос')}={resp.request_id})"
        )
        if resp.warnings:
            for warning in resp.warnings:
                msg = I18N.bidi(warning.en, warning.ru)
                self._console_log(
                    f"QIKI: {I18N.bidi('warning', 'предупреждение')}: {msg}",
                    level="warning",
                )
        for idx, p in enumerate(resp.proposals[:3], start=1):
            self._console_log(f"  {idx}) {I18N.bidi(p.title.en, p.title.ru)}")
        if proposals > 3:
            self._console_log(f"  … {I18N.bidi('more proposals', 'ещё предложений')}: {proposals - 3}")

        if resp.mode:
            self._qiki_mode = str(resp.mode)
            try:
                self.query_one("#orion-header", OrionHeader).update_mode(self._qiki_mode)
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)

        self._qiki_last_response = resp
        self._render_qiki_table()

    def action_show_screen(self, screen: str) -> None:
        if screen not in {app.screen for app in ORION_APPS}:
            self._console_log(f"{I18N.bidi('Unknown screen', 'Неизвестный экран')}: {screen}", level="info")
            return
        self.active_screen = screen
        if screen == "radar":
            # Ensure radar click/wheel events keep working after tmux/terminal resets.
            _emit_xterm_mouse_tracking(enabled=True)
        try:
            self.query_one("#orion-sidebar", OrionSidebar).set_active(screen)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        try:
            # Keybar is a pure renderer; it won't necessarily re-render on app state changes
            # unless explicitly refreshed.
            self.query_one("#orion-keybar", OrionKeybar).refresh()
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)
        for sid in (
            "system",
            "radar",
            "events",
            "console",
            "qiki",
            "profile",
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
                logger.debug("orion_exception_swallowed", exc_info=True)

        # Render the target screen immediately so the first frame is consistent.
        if screen == "events":
            self._render_events_table()
        if screen == "qiki":
            self._render_qiki_table()
        if screen == "summary":
            self._render_summary_table()
        if screen == "power":
            self._render_power_table()
        if screen == "sensors":
            self._render_sensors_table()
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

        # Avoid focus/cursor flicker on screen switches: keep focus deterministic.
        self.call_after_refresh(self.action_focus_command)

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
                return self.query_one(selector, Static)
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
        elif self.active_screen == "qiki":
            workspace = safe_query("#qiki-table")
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
        idx = order.index(focused) if isinstance(focused, Static) and focused in order else -1
        target = order[(idx + 1) % len(order)]
        try:
            self.set_focus(target)
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

    def action_focus_command(self) -> None:
        try:
            self.set_focus(self.query_one("#command-dock", Input))
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

    def action_help(self) -> None:
        self._show_help()

    def on_key(self, event) -> None:
        key = getattr(event, "key", "")
        if key not in {"up", "down"}:
            return
        if isinstance(self.focused, Input):
            return
        if isinstance(self.focused, DataTable):
            return

        if self.active_screen == "events":
            self._move_events_selection(-1 if key == "up" else 1)
            event.stop()
            return

        table_id: Optional[str] = None
        if self.active_screen == "radar":
            table_id = "#radar-table"
        elif self.active_screen == "events":
            table_id = "#events-table"
        elif self.active_screen == "console":
            table_id = "#console-table"
        elif self.active_screen == "qiki":
            table_id = "#qiki-table"
        elif self.active_screen == "summary":
            table_id = "#summary-table"
        elif self.active_screen == "power":
            table_id = "#power-table"
        elif self.active_screen == "sensors":
            table_id = "#sensors-table"
        elif self.active_screen == "propulsion":
            table_id = "#propulsion-table"
        elif self.active_screen == "thermal":
            table_id = "#thermal-table"
        elif self.active_screen == "diagnostics":
            table_id = "#diagnostics-table"
        elif self.active_screen == "mission":
            table_id = "#mission-table"
        elif self.active_screen == "rules":
            table_id = "#rules-table"

        if table_id is None:
            return
        try:
            table = self.query_one(table_id, DataTable)
        except Exception:
            return
        try:
            if key == "up":
                table.action_cursor_up()
            else:
                table.action_cursor_down()
            event.stop()
        except Exception:
            logger.debug("orion_exception_swallowed", exc_info=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "rules-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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

        if event.data_table.id == "qiki-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
            except Exception:
                return
            if row_key == "seed":
                return
            selected = self._qiki_by_key.get(row_key)
            if isinstance(selected, dict):
                self._set_selection(
                    SelectionContext(
                        app_id="qiki",
                        key=row_key,
                        kind="proposal",
                        source="qiki",
                        created_at_epoch=time.time(),
                        payload=selected,
                        ids=(row_key,),
                    )
                )
            return

        if event.data_table.id == "summary-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
                source_keys = selected.get("source_keys")
                if isinstance(source_keys, (list, tuple)):
                    ids = tuple(str(x) for x in source_keys if str(x).strip())
                else:
                    ids = (row_key,)
                self._set_selection(
                    SelectionContext(
                        app_id="power",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=ids,
                    )
                )
            return

        if event.data_table.id == "sensors-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
                source_keys = selected.get("source_keys")
                if isinstance(source_keys, (list, tuple)):
                    ids = tuple(str(x) for x in source_keys if str(x).strip())
                else:
                    ids = (row_key,)
                self._set_selection(
                    SelectionContext(
                        app_id="sensors",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=ids,
                    )
                )
            return

        if event.data_table.id == "propulsion-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
                source_keys = selected.get("source_keys")
                if isinstance(source_keys, (list, tuple)):
                    ids = tuple(str(x) for x in source_keys if str(x).strip())
                else:
                    ids = (row_key,)
                self._set_selection(
                    SelectionContext(
                        app_id="propulsion",
                        key=row_key,
                        kind="metric",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=ids,
                    )
                )
            return

        if event.data_table.id == "thermal-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
                source_keys = selected.get("source_keys")
                if isinstance(source_keys, (list, tuple)):
                    ids = tuple(str(x) for x in source_keys if str(x).strip())
                else:
                    ids = (row_key,)
                self._set_selection(
                    SelectionContext(
                        app_id="thermal",
                        key=row_key,
                        kind="thermal_node",
                        source="telemetry",
                        created_at_epoch=created_at_epoch,
                        payload=env.payload if isinstance(env, EventEnvelope) else selected,
                        ids=ids,
                    )
                )
            return

        if event.data_table.id == "diagnostics-table":
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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
            row_key_obj = getattr(event, "row_key", None)
            try:
                row_key = str(getattr(row_key_obj, "value", row_key_obj))
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

    def _power_compact_enabled(self) -> bool:
        if self._power_compact_override is not None:
            return bool(self._power_compact_override)
        # Compact by default for operator-first startup view; full list remains available via env toggle.
        raw_default = os.getenv("ORION_POWER_COMPACT_DEFAULT", "1").strip().lower()
        default_compact = raw_default not in {"0", "false", "no", "off"}
        if self._density in {"tiny", "narrow"}:
            return True
        return default_compact

    @staticmethod
    def _power_row_has_signal(raw: Any) -> bool:
        if raw is None:
            return False
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            try:
                return abs(float(raw)) > 1e-9
            except Exception:
                return True
        if isinstance(raw, str):
            return bool(raw.strip())
        if isinstance(raw, (list, dict, tuple, set)):
            return len(raw) > 0
        return True

    def _compact_power_rows(
        self,
        rows: list[tuple[str, str, str, Any, tuple[str, ...]]],
    ) -> list[tuple[str, str, str, Any, tuple[str, ...]]]:
        if not rows or not self._power_compact_enabled():
            return rows
        tier_a_order = [
            "state_of_charge",
            "faults",
            "pdu_throttled",
            "load_shedding",
            "shed_loads",
            "power_input",
            "power_consumption",
        ]
        tier_a_keys = set(tier_a_order)
        tier_a_rank = {key: idx for idx, key in enumerate(tier_a_order)}
        # Extras are sorted for operator startup triage:
        # docking/available energy context first, low-level bus and NBL details later.
        extra_order = [
            "pdu_limit",
            "dock_connected",
            "docking_state",
            "docking_port",
            "dock_power",
            "dock_v",
            "dock_a",
            "power_sources",
            "power_loads",
            "supercap_soc",
            "bus_voltage",
            "bus_current",
            "nbl_active",
            "nbl_allowed",
            "nbl_budget",
            "nbl_power",
        ]
        extra_rank = {key: idx for idx, key in enumerate(extra_order)}
        row_pos = {row[0]: idx for idx, row in enumerate(rows)}
        filtered = [row for row in rows if row[0] in tier_a_keys or self._power_row_has_signal(row[3])]
        if not filtered:
            return [rows[0]]

        raw_max_rows = os.getenv("ORION_POWER_COMPACT_MAX_ROWS", "12").strip()
        try:
            max_rows = int(raw_max_rows)
        except Exception:
            max_rows = 12
        tier_rows = sorted(
            (row for row in filtered if row[0] in tier_a_keys),
            key=lambda row: (tier_a_rank.get(row[0], 999), row_pos.get(row[0], 999)),
        )
        extra_rows = sorted(
            (row for row in filtered if row[0] not in tier_a_keys),
            key=lambda row: (extra_rank.get(row[0], 999), row_pos.get(row[0], 999)),
        )
        ordered = tier_rows + extra_rows
        if max_rows <= 0 or len(ordered) <= max_rows:
            return ordered

        if len(tier_rows) >= max_rows:
            return tier_rows[:max_rows]
        return tier_rows + extra_rows[: (max_rows - len(tier_rows))]

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

    @classmethod
    def _should_route_to_system_by_default(cls, raw: str) -> bool:
        """
        Default routing policy for the command dock:

        - QIKI is the default for free-form text.
        - But "operator console system commands" should work without forcing `S:`.
          Use `q:` or `//` to force QIKI when needed.
        """
        text = (raw or "").strip()
        if not text:
            return False
        low = text.lower()

        # Screen aliases and canonical screen names.
        if cls._normalize_screen_token(low) is not None:
            return True

        # One-word console/system commands (no QIKI).
        if low in {
            "output",
            "вывод",
            "help",
            "помощь",
            "?",
            "h",
            "events",
            "события",
            "ack",
            "acknowledge",
            "clear",
            "очистить",
            "record",
            "replay",
            "trust",
            "доверие",
        }:
            return True

        # Multi-token console/system commands.
        if low.startswith(
            (
                "output ",
                "output.",
                "вывод ",
                "вывод.",
                "screen ",
                "экран ",
                "events ",
                "events.",
                "события ",
                "события.",
                "type ",
                "тип ",
                "filter ",
                "фильтр ",
                "trust ",
                "доверие ",
                "ack ",
                "acknowledge ",
                "подтвердить ",
                "record ",
                "replay ",
            )
        ):
            return True

        # Control-plane commands: sim/rcs/xpdr/dock/power must be system by default.
        if low.startswith(
            (
                "simulation.",
                "simulation ",
                "sim.",
                "sim ",
                "симуляция.",
                "симуляция ",
                "rcs.",
                "dock.",
                "nbl.",
                "power.",
                "xpdr.",
                "ответчик.",
                "radar.",
                "радар.",
                "mouse ",
                "mouse.",
                "мышь ",
                "мышь.",
            )
        ):
            return True

        # Rules maintenance.
        if low in {"reload rules", "rules reload", "rules refresh", "перезагрузить правила", "правила перезагрузить"}:
            return True

        return False

    def _show_help(self) -> None:
        def display_aliases(app: OrionAppSpec) -> str:
            # Never show abbreviated aliases in UI help; keep the help readable and fully spelled out.
            # We rely on the convention that the first two aliases are the canonical EN/RU names.
            aliases = list(app.aliases[:2]) if app.aliases else []
            if not aliases:
                return I18N.NA
            return "|".join(aliases)

        apps = " | ".join(f"{app.hotkey_label} {app.title} ({display_aliases(app)})" for app in ORION_APPS)
        screens = ", ".join(app.screen for app in ORION_APPS)
        self._console_log(f"{I18N.bidi('Applications', 'Приложения')}: {apps}", level="info")
        self._console_log(
            f"{I18N.bidi('Commands', 'Команды')}: "
            f"help/помощь | screen/экран <{screens}> | {I18N.bidi('or type a screen alias', 'или введите алиас экрана')}",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Rules', 'Правила')}: {I18N.bidi('reload rules', 'перезагрузить правила')}",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Simulation', 'Симуляция')}: "
            f"simulation.start [speed]/симуляция.старт [скорость] | simulation.pause/симуляция.пауза | simulation.stop/симуляция.стоп | "
            f"simulation.reset/симуляция.сброс ({I18N.bidi('confirm', 'подтвердить')}: Y)",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Radar', 'Радар')}: "
            f"radar.view <top|side|front|iso> | radar.zoom <in|out|reset> | radar.pan reset | radar.iso reset | "
            f"radar.iso rotate <dyaw_deg> <dpitch_deg> | "
            f"{I18N.bidi('hotkeys', 'горячие')}: "
            f"1 top · 2 side · 3 front · 4 iso · N next · P prev · K vectors · L labels (Radar screen)",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Mouse', 'Мышь')}: mouse on/off | {I18N.bidi('selection', 'выделение')}: Shift+drag",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Output', 'Вывод')}: output up|down|end | output follow on/off",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('Filters', 'Фильтры')}: "
            f"type/тип <name/имя> | type off/тип отключить | "
            f"filter/фильтр <text/текст> | filter off/фильтр отключить | "
            f"trust/доверие <trusted|untrusted|off|status|доверенный|недоверенный|выкл|статус>",
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
            f"{I18N.bidi('Record/Replay', 'Запись/реплей')}: "
            f"record start [path] [duration_s] | record stop | replay <path> [speed=1.0] [prefix=...] [no_timing] | replay stop",
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
            f"{I18N.bidi('Routing', 'Маршрутизация')}: "
            f"{I18N.bidi('system commands work without', 'системные команды работают без')} `S:` "
            f"({I18N.bidi('e.g.', 'например')}: sim.*, power.*, xpdr.*, rcs.*, dock.*). "
            f"{I18N.bidi('Force QIKI with', 'Принудительно QIKI через')}: q: <text> | // <text>",
            level="info",
        )
        self._console_log(
            f"{I18N.bidi('QIKI intent', 'Намерение QIKI')}: q: <text> | // <text>",
            level="info",
        )
        self._console_log(f"{I18N.bidi('Menu glossary', 'Глоссарий меню')}: ", level="info")
        self._console_log(f"- System/Система: {I18N.bidi('System', 'Система')}", level="info")
        self._console_log(f"- Events/События: {I18N.bidi('Events', 'События')}", level="info")
        self._console_log(
            f"- Power systems/Система питания: {I18N.bidi('Power systems', 'Система питания')}",
            level="info",
        )
        self._console_log(f"- Diagnostics/Диагностика: {I18N.bidi('Diagnostics', 'Диагностика')}", level="info")
        self._console_log(
            f"- Mission control/Управление миссией: {I18N.bidi('Mission control', 'Управление миссией')}", level="info"
        )
        self._console_log(f"{I18N.bidi('Panels glossary', 'Глоссарий панелей')}: ", level="info")
        self._console_log(f"- Updated/Обновлено: {I18N.bidi('Updated', 'Обновлено')}", level="info")
        self._console_log(
            f"- State of charge/Уровень заряда: {I18N.bidi('State of charge', 'Уровень заряда')}", level="info"
        )
        self._console_log(
            f"- Power input/Входная мощность: {I18N.bidi('Power input', 'Входная мощность')}", level="info"
        )
        self._console_log(
            f"- Power output/Выходная мощность: {I18N.bidi('Power output/consumption', 'Выходная/потребляемая мощность')}",
            level="info",
        )
        self._console_log(f"- Bus voltage/Напряжение шины: {I18N.bidi('Bus voltage', 'Напряжение шины')}", level="info")
        self._console_log(f"- Bus current/Ток шины: {I18N.bidi('Bus current', 'Ток шины')}", level="info")
        self._console_log(
            f"- External temperature/Наружная температура: {I18N.bidi('External temperature', 'Наружная температура')}",
            level="info",
        )
        self._console_log(
            f"- Core temperature/Температура ядра: {I18N.bidi('Core temperature', 'Температура ядра')}",
            level="info",
        )
        self._console_log(
            f"- CPU usage/Загрузка процессора: {I18N.bidi('CPU usage', 'Загрузка процессора')}", level="info"
        )
        self._console_log(
            f"- Memory usage/Загрузка памяти: {I18N.bidi('Memory usage', 'Загрузка памяти')}", level="info"
        )
        self._console_log(f"{I18N.bidi('Header glossary', 'Глоссарий хедера')}: ", level="info")
        self._console_log(
            f"- {I18N.bidi('Link', 'Связь')}: {I18N.bidi('Link status', 'Состояние связи')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Battery', 'Батарея')}: {I18N.bidi('Battery level', 'Уровень батареи')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Hull', 'Корпус')}: {I18N.bidi('Hull integrity', 'Целостность корпуса')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Radiation', 'Радиация')}: {I18N.bidi('Radiation dose rate', 'Мощность дозы радиации')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('External temperature', 'Наружная температура')}: "
            f"{I18N.bidi('External temperature', 'Наружная температура')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Core temperature', 'Температура ядра')}: "
            f"{I18N.bidi('Core temperature', 'Температура ядра')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Age', 'Возраст')}: {I18N.bidi('Telemetry age', 'Возраст телеметрии')} ({I18N.bidi('compact units', 'краткие единицы')}: sec/с, min/мин, h/ч)",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Freshness', 'Свежесть')}: {I18N.bidi('Telemetry freshness', 'Свежесть телеметрии')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Simulation', 'Симуляция')}: {I18N.bidi('Simulation state', 'Состояние симуляции')}",
            level="info",
        )
        self._console_log(
            f"- {I18N.bidi('Position', 'Позиция')}: {I18N.bidi('Position', 'Позиция')} ({I18N.bidi('meters', 'метры')}: m/м)",
            level="info",
        )
        self._console_log(f"{I18N.bidi('Tables glossary', 'Глоссарий таблиц')}: ", level="info")
        self._console_log(
            f"- Acknowledged/Подтверждено: {I18N.bidi('Acknowledged', 'Подтверждено')}",
            level="info",
        )
        self._console_log(
            f"- Radial velocity/Радиальная скорость: {I18N.bidi('Radial velocity', 'Радиальная скорость')}",
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

        # Secret entry mode: treat the next non-system line as the secret value.
        if self._secret_entry_mode == "openai_api_key" and cmd[:2].lower() != "s:":
            api_key = cmd
            nats = self.nats_client
            if nats is None:
                self._console_log(
                    f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}",
                    level="warning",
                )
                return
            try:
                payload = {"op": "set_key", "api_key": api_key, "ts_epoch_ms": int(time.time() * 1000)}
                acked = False
                if nats.nc is not None:
                    try:
                        msg = await nats.nc.request(
                            OPENAI_API_KEY_UPDATE,
                            json.dumps(payload).encode("utf-8"),
                            timeout=1.5,
                        )
                        data = json.loads(msg.data.decode("utf-8"))
                        acked = bool(isinstance(data, dict) and data.get("ok"))
                    except Exception:
                        acked = False
                else:
                    await nats.publish_command(OPENAI_API_KEY_UPDATE, payload)

                self._console_log(
                    f"{I18N.bidi('OpenAI key set', 'OpenAI ключ установлен')}{' (ACK)' if acked else ''}",
                    level="info" if acked else "warning",
                )
            except Exception as exc:
                self._console_log(
                    f"{I18N.bidi('Failed to send key', 'Не удалось отправить ключ')}: {exc}",
                    level="warning",
                )

            # Exit secret mode and restore input behavior.
            self._secret_entry_mode = None
            try:
                dock = self.query_one("#command-dock", Input)
                if self._secret_entry_prev_password is not None:
                    dock.password = self._secret_entry_prev_password
                dock.value = ""
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            self._update_command_placeholder()
            return

        # Default input mode: QIKI intent.
        # Use explicit prefixes to force routing:
        # - `q:` / `//` => QIKI
        # - `s:`        => system/console command (bypass default-QIKI)
        forced_command = False
        if cmd[:2].lower() == "s:":
            forced_command = True
            cmd = cmd[2:].strip()
            if not cmd:
                self._console_log(
                    f"{I18N.bidi('System command', 'Системная команда')}: {I18N.bidi('empty', 'пусто')}",
                    level="info",
                )
                return

            low_cmd = cmd.lower()
            # Allow both `openai.key` and `openai key` spelling.
            if low_cmd.startswith("openai") and " " in low_cmd and "." not in low_cmd:
                low_cmd = low_cmd.replace(" ", ".")
            key_inline: str | None = None
            if (
                low_cmd.startswith("openai.key")
                or low_cmd.startswith("openai.api_key")
                or low_cmd.startswith("openai.apikey")
            ):
                # Support: `S: openai.key <key>`
                parts = cmd.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    key_inline = parts[1].strip()

            if low_cmd in {"openai.key", "openai.api_key", "openai.apikey"} or key_inline is not None:
                api_key_inline = key_inline
                if api_key_inline is not None:
                    nats = self.nats_client
                    if nats is None:
                        self._console_log(
                            f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}",
                            level="warning",
                        )
                        return
                    # Set key from command line; do not echo the key.
                    payload = {"op": "set_key", "api_key": api_key_inline, "ts_epoch_ms": int(time.time() * 1000)}
                    try:
                        acked = False
                        if nats.nc is not None:
                            try:
                                msg = await nats.nc.request(
                                    OPENAI_API_KEY_UPDATE,
                                    json.dumps(payload).encode("utf-8"),
                                    timeout=1.5,
                                )
                                data = json.loads(msg.data.decode("utf-8"))
                                acked = bool(isinstance(data, dict) and data.get("ok"))
                            except Exception:
                                acked = False
                        else:
                            await nats.publish_command(OPENAI_API_KEY_UPDATE, payload)
                        self._console_log(
                            f"{I18N.bidi('OpenAI key set', 'OpenAI ключ установлен')}{' (ACK)' if acked else ''}",
                            level="info" if acked else "warning",
                        )
                    except Exception as exc:
                        self._console_log(
                            f"{I18N.bidi('Failed to send key', 'Не удалось отправить ключ')}: {exc}",
                            level="warning",
                        )
                    return

                # Enter secret mode: the next line will be treated as the key.
                self._secret_entry_mode = "openai_api_key"
                try:
                    dock = self.query_one("#command-dock", Input)
                    self._secret_entry_prev_password = bool(getattr(dock, "password", False))
                    dock.password = True
                    dock.value = ""
                    dock.focus()
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
                self._update_command_placeholder()
                return

            if low_cmd in {"openai.cancel", "openai.abort"}:
                self._secret_entry_mode = None
                try:
                    dock = self.query_one("#command-dock", Input)
                    if self._secret_entry_prev_password is not None:
                        dock.password = self._secret_entry_prev_password
                    dock.value = ""
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
                self._update_command_placeholder()
                self._console_log(I18N.bidi("Canceled", "Отменено"), level="info")
                return

            if low_cmd in {"openai.status", "openai.check", "openai.ping"}:
                nats = self.nats_client
                if nats is None or nats.nc is None:
                    self._console_log(
                        f"{I18N.bidi('NATS not connected', 'NATS не подключен')}",
                        level="warning",
                    )
                    return
                try:
                    msg = await nats.nc.request(
                        OPENAI_API_KEY_UPDATE,
                        json.dumps({"op": "status"}).encode("utf-8"),
                        timeout=1.5,
                    )
                    data = json.loads(msg.data.decode("utf-8"))
                    key_set = bool(isinstance(data, dict) and data.get("key_set"))
                    model = data.get("model") if isinstance(data, dict) else None
                    self._console_log(
                        f"OpenAI: {I18N.bidi('ready', 'готово') if key_set else I18N.bidi('not set', 'не задано')}"
                        f" (model={model or 'n/a'})",
                        level="info" if key_set else "warning",
                    )
                except Exception as exc:
                    self._console_log(
                        f"OpenAI: {I18N.bidi('status failed', 'ошибка статуса')}: {exc}",
                        level="warning",
                    )
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

        # Default input mode is QIKI, but operator console system commands should work without forcing `S:`.
        if not forced_command and not self._should_route_to_system_by_default(cmd):
            await self._publish_qiki_intent(cmd)
            return

        self._console_log(f"{I18N.bidi('command', 'команда')}> {cmd}", level="info")

        low = cmd.lower()
        if low in {"help", "помощь", "?", "h"}:
            self._show_help()
            return

        if low == "output" or low == "вывод" or low.startswith(("output ", "output.", "вывод ", "вывод.")):
            parts = cmd.split()
            if len(parts) == 1:
                state = I18N.bidi("follow", "следить") if self._output_follow else I18N.bidi("manual", "ручной")
                self._console_log(
                    f"{I18N.bidi('Output', 'Вывод')}: {state}",
                    level="info",
                )
                return

            action = (parts[1] or "").strip().lower()
            arg = (parts[2] if len(parts) > 2 else "").strip()

            def parse_lines(default: int) -> int:
                if not arg:
                    return default
                try:
                    return max(1, min(100, int(float(arg))))
                except Exception:
                    return default

            if action in {"up", "вверх"}:
                self._output_scroll_relative(-parse_lines(10))
                return
            if action in {"down", "вниз"}:
                self._output_scroll_relative(parse_lines(10))
                return
            if action in {"end", "bottom", "низ", "конец"}:
                self._output_scroll_end()
                return
            if action in {"follow", "autofollow", "следить"}:
                onoff = (arg or "").strip().lower()
                if onoff in {"on", "1", "true", "yes", "вкл", "включить"}:
                    self._output_apply_follow(True)
                    self._console_log(
                        f"{I18N.bidi('Output', 'Вывод')}: {I18N.bidi('follow on', 'следить вкл')}", level="info"
                    )
                    return
                if onoff in {"off", "0", "false", "no", "выкл", "выключить"}:
                    self._output_apply_follow(False)
                    self._console_log(
                        f"{I18N.bidi('Output', 'Вывод')}: {I18N.bidi('follow off', 'следить выкл')}", level="info"
                    )
                    return
                self._console_log(
                    f"{I18N.bidi('Output follow', 'Вывод следить')}: on/off",
                    level="info",
                )
                return

            self._console_log(
                f"{I18N.bidi('Output', 'Вывод')}: output up|down|end|follow on|off",
                level="info",
            )
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

        if low == "record" or low.startswith("record "):
            parts = cmd.split()
            action = parts[1].lower() if len(parts) > 1 else ""

            def _task_state(task: asyncio.Task | None) -> str:
                if task is None:
                    return I18N.bidi("idle", "нет")
                if task.cancelled():
                    return I18N.bidi("canceled", "отменено")
                if task.done():
                    return I18N.bidi("done", "готово")
                return I18N.bidi("running", "работает")

            if not action or action in {"status", "info"}:
                self._console_log(
                    f"{I18N.bidi('Record', 'Запись')}: {_task_state(self._record_task)} "
                    f"(path={self._record_output_path or I18N.NA})",
                    level="info",
                )
                return

            if action in {"stop", "cancel", "abort"}:
                if self._record_task is None or self._record_task.done():
                    self._console_log(
                        f"{I18N.bidi('Record', 'Запись')}: {I18N.bidi('not running', 'не запущена')}",
                        level="info",
                    )
                    self._record_task = None
                    return
                self._record_task.cancel()
                self._console_log(
                    f"{I18N.bidi('Record', 'Запись')}: {I18N.bidi('stop requested', 'остановка')}",
                    level="info",
                )
                return

            if action in {"start", "on"}:
                if self._record_task is not None and not self._record_task.done():
                    self._console_log(
                        f"{I18N.bidi('Record already running', 'Запись уже запущена')}: {self._record_output_path or I18N.NA}",
                        level="info",
                    )
                    return
                if self.nats_client is None:
                    self._console_log(
                        f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}",
                        level="warning",
                    )
                    return
                nats_client = self.nats_client

                output_path = parts[2].strip() if len(parts) > 2 else ""
                if not output_path:
                    out_dir = (
                        os.getenv("OPERATOR_CONSOLE_RECORD_DIR", "/tmp/qiki_records").strip() or "/tmp/qiki_records"
                    )
                    output_path = str(Path(out_dir) / f"qiki_record_{int(time.time())}.jsonl")
                output_path = os.path.expanduser(output_path)

                duration_s = None
                for tok in parts[3:]:
                    if tok.startswith("duration="):
                        duration_s = self._parse_duration_s(tok.split("=", 1)[1])
                        continue
                    if duration_s is None:
                        duration_s = self._parse_duration_s(tok)
                if duration_s is None:
                    duration_s = float(os.getenv("OPERATOR_CONSOLE_RECORD_DEFAULT_DURATION_S", "86400") or "86400")

                subjects = [
                    SYSTEM_TELEMETRY,
                    EVENTS_V1_WILDCARD,
                    RADAR_TRACKS,
                    RESPONSES_CONTROL,
                ]
                self._record_output_path = output_path
                self._record_started_ts_epoch = float(time.time())
                self._record_last_result = None

                async def _record_job() -> dict[str, Any]:
                    return await record_jsonl(
                        nats_url=nats_client.url,
                        subjects=subjects,
                        duration_s=float(duration_s or 0.0),
                        output_path=output_path,
                    )

                task = asyncio.create_task(_record_job())
                self._record_task = task

                def _on_done(t: asyncio.Task) -> None:
                    if self._record_task is not t:
                        return
                    try:
                        if t.cancelled():
                            self._record_last_result = {"ok": False, "canceled": True, "path": self._record_output_path}
                            self._console_log(f"{I18N.bidi('Record canceled', 'Запись отменена')}", level="info")
                        else:
                            res = t.result()
                            self._record_last_result = dict(res) if isinstance(res, dict) else {"result": res}
                            self._console_log(
                                f"{I18N.bidi('Record finished', 'Запись завершена')}: "
                                f"{self._record_output_path} ({I18N.bidi('total', 'всего')}={self._record_last_result.get('counts', {}).get('total', I18N.NA)})",
                                level="info",
                            )
                    except Exception as exc:
                        self._record_last_result = {"ok": False, "error": str(exc), "path": self._record_output_path}
                        self._console_log(f"{I18N.bidi('Record failed', 'Запись ошибка')}: {exc}", level="warning")
                    finally:
                        self._record_task = None

                task.add_done_callback(_on_done)
                self._console_log(
                    f"{I18N.bidi('Record started', 'Запись запущена')}: {output_path} "
                    f"(duration_s={float(duration_s):g}, subjects={len(subjects)})",
                    level="info",
                )
                return

            self._console_log(
                f"{I18N.bidi('Unknown record command', 'Неизвестная команда записи')}: {cmd}",
                level="info",
            )
            return

        if low == "replay" or low.startswith("replay "):
            parts = cmd.split()
            action = parts[1].lower() if len(parts) > 1 else ""

            if not action or action in {"status", "info"}:
                state = I18N.bidi("idle", "нет")
                if self._replay_task is not None and not self._replay_task.done():
                    state = I18N.bidi("running", "работает")
                elif self._replay_task is not None and self._replay_task.done():
                    state = I18N.bidi("done", "готово")
                self._console_log(
                    f"{I18N.bidi('Replay', 'Реплей')}: {state} (path={self._replay_input_path or I18N.NA})",
                    level="info",
                )
                return

            if action in {"stop", "cancel", "abort"}:
                if self._replay_task is None or self._replay_task.done():
                    self._console_log(
                        f"{I18N.bidi('Replay', 'Реплей')}: {I18N.bidi('not running', 'не запущен')}",
                        level="info",
                    )
                    self._replay_task = None
                    return
                self._replay_task.cancel()
                self._console_log(
                    f"{I18N.bidi('Replay', 'Реплей')}: {I18N.bidi('stop requested', 'остановка')}",
                    level="info",
                )
                return

            input_path = parts[1].strip() if len(parts) > 1 else ""
            if not input_path:
                self._console_log(
                    f"{I18N.bidi('Usage', 'Использование')}: replay <path> [speed=1.0] [prefix=...] [no_timing]",
                    level="info",
                )
                return
            if self._replay_task is not None and not self._replay_task.done():
                self._console_log(f"{I18N.bidi('Replay already running', 'Реплей уже запущен')}", level="info")
                return
            if self.nats_client is None:
                self._console_log(
                    f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}",
                    level="warning",
                )
                return
            nats_client = self.nats_client

            speed = 1.0
            subject_prefix: str | None = None
            no_timing = False
            for tok in parts[2:]:
                low_tok = tok.strip().lower()
                if not low_tok:
                    continue
                if low_tok in {"no_timing", "notiming", "no-timing"}:
                    no_timing = True
                    continue
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "speed":
                        try:
                            speed = float(v)
                        except Exception:
                            logger.debug("orion_exception_swallowed", exc_info=True)
                        continue
                    if k in {"prefix", "subject_prefix"}:
                        subject_prefix = v or None
                        continue
                if subject_prefix is None:
                    try:
                        speed = float(tok)
                        continue
                    except Exception:
                        subject_prefix = tok

            input_path = os.path.expanduser(input_path)
            self._replay_input_path = input_path
            self._replay_started_ts_epoch = float(time.time())
            self._replay_last_result = None

            async def _replay_job() -> dict[str, Any]:
                return await replay_jsonl(
                    nats_url=nats_client.url,
                    input_path=input_path,
                    speed=float(speed),
                    subject_prefix=subject_prefix,
                    no_timing=bool(no_timing),
                )

            task = asyncio.create_task(_replay_job())
            self._replay_task = task

            def _on_done(t: asyncio.Task) -> None:
                if self._replay_task is not t:
                    return
                try:
                    if t.cancelled():
                        self._replay_last_result = {"ok": False, "canceled": True, "path": self._replay_input_path}
                        self._console_log(f"{I18N.bidi('Replay canceled', 'Реплей отменен')}", level="info")
                    else:
                        res = t.result()
                        self._replay_last_result = dict(res) if isinstance(res, dict) else {"result": res}
                        self._console_log(
                            f"{I18N.bidi('Replay finished', 'Реплей завершен')}: {self._replay_input_path} "
                            f"({I18N.bidi('published', 'отправлено')}={self._replay_last_result.get('published', I18N.NA)})",
                            level="info",
                        )
                except Exception as exc:
                    self._replay_last_result = {"ok": False, "error": str(exc), "path": self._replay_input_path}
                    self._console_log(f"{I18N.bidi('Replay failed', 'Реплей ошибка')}: {exc}", level="warning")
                finally:
                    self._replay_task = None

            task.add_done_callback(_on_done)
            self._console_log(
                f"{I18N.bidi('Replay started', 'Реплей запущен')}: {input_path} "
                f"(speed={float(speed):g}, prefix={subject_prefix or I18N.NA}, no_timing={no_timing})",
                level="info",
            )
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
                inc = self._incident_store.get(key) if self._incident_store is not None else None
                audit_payload_ru: dict[str, Any] = {
                    "schema_version": 1,
                    "category": "audit",
                    "kind": "incident_ack",
                    "source": "orion",
                    "subject": "incident",
                    "ts_epoch": time.time(),
                    "incident_key": key,
                }
                if inc is not None:
                    audit_payload_ru["incident_id"] = str(getattr(inc, "incident_id", "")) or None
                    audit_payload_ru["rule_id"] = str(getattr(inc, "rule_id", "")) or None
                    audit_payload_ru["severity"] = str(getattr(inc, "severity", "")) or None
                try:
                    await self._publish_audit_event(audit_payload_ru)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
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
                inc = self._incident_store.get(key) if self._incident_store is not None else None
                audit_payload: dict[str, Any] = {
                    "schema_version": 1,
                    "category": "audit",
                    "kind": "incident_ack",
                    "source": "orion",
                    "subject": "incident",
                    "ts_epoch": time.time(),
                    "incident_key": key,
                }
                if inc is not None:
                    audit_payload["incident_id"] = str(getattr(inc, "incident_id", "")) or None
                    audit_payload["rule_id"] = str(getattr(inc, "rule_id", "")) or None
                    audit_payload["severity"] = str(getattr(inc, "severity", "")) or None
                try:
                    await self._publish_audit_event(audit_payload)
                except Exception:
                    logger.debug("orion_exception_swallowed", exc_info=True)
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
            acked_snapshot: list[dict[str, str]] = []
            if self._incident_store is not None:
                for inc in list(self._incident_store.list_incidents()):
                    try:
                        if bool(getattr(inc, "acked", False)):
                            acked_snapshot.append(
                                {
                                    "incident_id": str(getattr(inc, "incident_id", "")),
                                    "rule_id": str(getattr(inc, "rule_id", "")),
                                    "incident_key": str(getattr(inc, "key", "")),
                                }
                            )
                    except Exception:
                        continue
            cleared = self._clear_acked_incidents()
            try:
                await self._publish_audit_event(
                    {
                        "schema_version": 1,
                        "category": "audit",
                        "kind": "incident_clear",
                        "source": "orion",
                        "subject": "incidents",
                        "ts_epoch": time.time(),
                        "cleared_count": int(cleared),
                        "cleared_total": int(len(acked_snapshot)),
                        "cleared_incidents": acked_snapshot[:10],
                    }
                )
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
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
                self._console_log(
                    f"{I18N.bidi('Events type filter', 'Фильтр событий по типу')}: {current}", level="info"
                )
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

        # trust/доверие <trusted|untrusted|off|status|доверенный|недоверенный|выкл|статус>
        if low in {"trust", "доверие"} or low.startswith("trust ") or low.startswith("доверие "):
            _, _, tail = cmd.partition(" ")
            token_raw = tail.strip()
            if not token_raw:
                current = self._events_filter_text or I18N.NA
                self._console_log(
                    f"{I18N.bidi('Events trust filter', 'Фильтр событий по доверию')}: {current}",
                    level="info",
                )
                return
            if token_raw.lower() in {"status", "статус", "info", "инфо"}:
                current = self._normalize_events_trust_filter_token(self._events_filter_text)
                self._console_log(
                    f"{I18N.bidi('Events trust filter', 'Фильтр событий по доверию')}: {current}",
                    level="info",
                )
                return
            token = self._normalize_events_trust_filter_token(token_raw)
            if token in {"off", "none", "all", "*"}:
                self._events_filter_text = None
                self._console_log(
                    f"{I18N.bidi('Events trust filter cleared', 'Фильтр событий по доверию снят')}",
                    level="info",
                )
            elif token in {"trusted", "untrusted"}:
                self._events_filter_text = token
                self._console_log(
                    f"{I18N.bidi('Events trust filter', 'Фильтр событий по доверию')}: {token}",
                    level="info",
                )
            else:
                self._console_log(
                    f"{I18N.bidi('Events trust filter', 'Фильтр событий по доверию')}: "
                    f"trusted|untrusted|off|status|доверенный|недоверенный|выкл|статус",
                    level="info",
                )
                return
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
                self._console_log(
                    f"{I18N.bidi('Events text filter', 'Фильтр событий по тексту')}: {current}", level="info"
                )
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
                    self._console_log(
                        f"{I18N.bidi('Events type filter', 'Фильтр событий по типу')}: {token}", level="info"
                    )
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

        # mouse <on|off> / мышь <вкл|выкл> (xterm mouse reporting)
        if low.startswith(("mouse", "мышь")):
            parts = low.split()
            raw_op = parts[1] if len(parts) >= 2 else ""
            op = "".join(ch for ch in raw_op if ch.isalnum()).lower()
            if op == "debug" and len(parts) >= 3:
                flag = "".join(ch for ch in parts[2] if ch.isalnum()).lower()
                self._mouse_debug = flag in {
                    "on",
                    "enable",
                    "enabled",
                    "1",
                    "true",
                    "да",
                    "вкл",
                    "включить",
                    "включена",
                }
                self._console_log(
                    f"{I18N.bidi('Mouse debug', 'Отладка мыши')}: "
                    f"{I18N.bidi('on', 'вкл') if self._mouse_debug else I18N.bidi('off', 'выкл')}",
                    level="info",
                )
                return
            if op in {"on", "enable", "enabled", "вкл", "включить", "включена"}:
                _emit_xterm_mouse_tracking(enabled=True)
                self._console_log(
                    f"{I18N.bidi('Mouse tracking', 'Отчёты мыши')}: {I18N.bidi('enabled', 'включено')} "
                    f"({I18N.bidi('selection', 'выделение')}: Shift+drag)",
                    level="info",
                )
                return
            if op in {"off", "disable", "disabled", "выкл", "отключить", "отключена"}:
                _emit_xterm_mouse_tracking(enabled=False)
                self._console_log(
                    f"{I18N.bidi('Mouse tracking', 'Отчёты мыши')}: {I18N.bidi('disabled', 'выключено')}",
                    level="info",
                )
                return
            self._console_log(
                f"{I18N.bidi('Mouse', 'Мышь')}: mouse on/off | mouse debug on/off | "
                f"{I18N.bidi('selection', 'выделение')}: Shift+drag",
                level="info",
            )
            return

        # radar.view <top|side|front|iso>
        if low.startswith(("radar.view", "радар.вид")):
            parts = cmd.split()
            token = parts[1].strip().lower() if len(parts) >= 2 else ""
            view = {
                "top": "top",
                "xy": "top",
                "верх": "top",
                "side": "side",
                "xz": "side",
                "бок": "side",
                "front": "front",
                "yz": "front",
                "фронт": "front",
                "iso": "iso",
                "3d": "iso",
                "изо": "iso",
                "изометрия": "iso",
            }.get(token)
            if view is None:
                self._console_log(
                    f"{I18N.bidi('Radar view', 'Вид радара')}: {self._radar_view} "
                    f"({I18N.bidi('use', 'используйте')}: radar.view top|side|front|iso)",
                    level="info",
                )
                return
            self._radar_view = view
            self._console_log(f"{I18N.bidi('Radar view', 'Вид радара')}: {view}", level="info")
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return

        # radar.iso rotate <dyaw_deg> <dpitch_deg>
        if low.startswith(("radar.iso rotate", "радар.изо повернуть")):
            parts = cmd.split()
            if len(parts) < 4:
                self._console_log(
                    "ISO rotate/Поворот ISO: radar.iso rotate <dyaw_deg> <dpitch_deg>",
                    level="info",
                )
                return
            try:
                dyaw = float(parts[2])
                dpitch = float(parts[3])
            except Exception:
                self._console_log(
                    "ISO rotate/Поворот ISO: radar.iso rotate <dyaw_deg> <dpitch_deg>",
                    level="info",
                )
                return

            self._radar_iso_yaw_deg = (float(self._radar_iso_yaw_deg) + float(dyaw)) % 360.0
            self._radar_iso_pitch_deg = float(self._radar_iso_pitch_deg) + float(dpitch)
            self._radar_iso_pitch_deg = max(-80.0, min(80.0, float(self._radar_iso_pitch_deg)))
            self._console_log(
                f"ISO yaw/pitch: {self._radar_iso_yaw_deg:.0f}°/{self._radar_iso_pitch_deg:.0f}°",
                level="info",
            )
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return

        # radar.iso reset
        if low in {"radar.iso reset", "радар.изо сброс"}:
            self._radar_iso_yaw_deg = 45.0
            self._radar_iso_pitch_deg = 35.0
            self._console_log("ISO yaw/pitch: reset/сброс", level="info")
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return

        # radar.zoom <in|out|reset>
        if low.startswith(("radar.zoom", "радар.зум", "радар.масштаб")):
            parts = cmd.split()
            token = parts[1].strip().lower() if len(parts) >= 2 else ""
            zoom_op = {
                "in": "in",
                "plus": "in",
                "+": "in",
                "внутрь": "in",
                "out": "out",
                "minus": "out",
                "-": "out",
                "наружу": "out",
                "reset": "reset",
                "0": "reset",
                "сброс": "reset",
            }.get(token)
            if zoom_op is None:
                self._console_log(
                    f"{I18N.bidi('Radar zoom', 'Масштаб радара')}: x{round(float(self._radar_zoom), 2)} "
                    f"({I18N.bidi('use', 'используйте')}: radar.zoom in|out|reset)",
                    level="info",
                )
                return
            if zoom_op == "reset":
                self._radar_zoom = 1.0
            elif zoom_op == "in":
                self._radar_zoom = max(0.1, min(100.0, float(self._radar_zoom) * 1.25))
            else:
                self._radar_zoom = max(0.1, min(100.0, float(self._radar_zoom) / 1.25))
            self._console_log(
                f"{I18N.bidi('Radar zoom', 'Масштаб радара')}: x{round(float(self._radar_zoom), 2)}",
                level="info",
            )
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return

        # radar.pan reset
        if low in {"radar.pan reset", "радар.пан сброс", "радар.сдвиг сброс"}:
            self._radar_pan_u_m = 0.0
            self._radar_pan_v_m = 0.0
            self._console_log(f"{I18N.bidi('Radar pan', 'Сдвиг радара')}: reset/сброс", level="info")
            try:
                if self.active_screen == "radar":
                    self._render_radar_ppi()
            except Exception:
                logger.debug("orion_exception_swallowed", exc_info=True)
            return

        # radar.select <next|prev>
        if low.startswith(("radar.select", "радар.выбор", "радар.выбрать")):
            parts = cmd.split()
            token = parts[1].strip().lower() if len(parts) >= 2 else ""
            select_op = {
                "next": "next",
                "n": "next",
                "след": "next",
                "следующий": "next",
                "prev": "prev",
                "p": "prev",
                "пред": "prev",
                "предыдущий": "prev",
            }.get(token)
            if select_op is None:
                self._console_log(
                    f"{I18N.bidi('Radar select', 'Выбор радара')}: "
                    f"{I18N.bidi('use', 'используйте')}: radar.select next|prev",
                    level="info",
                )
                return
            self._radar_select_relative(delta=1 if select_op == "next" else -1)
            return

        # radar.overlay <vectors|labels> <on|off|toggle>
        if low.startswith(("radar.overlay", "радар.оверлей", "радар.оверлеи")):
            parts = cmd.split()
            if len(parts) < 3:
                self._console_log(
                    f"{I18N.bidi('Radar overlays', 'Оверлеи радара')}: radar.overlay vectors|labels on|off|toggle",
                    level="info",
                )
                return
            kind = parts[1].strip().lower()
            op = parts[2].strip().lower()
            enabled: bool | None
            if op in {"on", "1", "true", "yes", "вкл", "включить"}:
                enabled = True
            elif op in {"off", "0", "false", "no", "выкл", "отключить"}:
                enabled = False
            elif op in {"toggle", "t", "перекл", "переключить"}:
                enabled = None
            else:
                self._console_log(
                    f"{I18N.bidi('Radar overlays', 'Оверлеи радара')}: radar.overlay vectors|labels on|off|toggle",
                    level="info",
                )
                return

            if kind in {"vectors", "vec", "векторы", "вектор"}:
                self._radar_overlay_vectors = (
                    (not bool(self._radar_overlay_vectors)) if enabled is None else bool(enabled)
                )
                self._console_log(
                    f"{I18N.bidi('Vectors enabled', 'Векторы включены')}: {I18N.yes_no(bool(self._radar_overlay_vectors))}",
                    level="info",
                )
                self._refresh_radar()
                return
            if kind in {"labels", "lbl", "метки", "подписи", "лейблы"}:
                self._radar_overlay_labels = (
                    (not bool(self._radar_overlay_labels)) if enabled is None else bool(enabled)
                )
                self._console_log(
                    f"{I18N.bidi('Labels enabled', 'Подписи включены')}: {I18N.yes_no(bool(self._radar_overlay_labels))}",
                    level="info",
                )
                self._refresh_radar()
                return

            self._console_log(
                f"{I18N.bidi('Unknown overlay', 'Неизвестный оверлей')}: {kind or I18N.NA}",
                level="info",
            )
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
        # Alias (RU): ответчик.режим <on|off|silent|spoof>
        if low.startswith(("xpdr.mode", "xpdr.режим", "ответчик.режим")):
            parsed = self._parse_xpdr_cli_command(cmd)
            if parsed is None:
                self._console_log(
                    f"{I18N.bidi('Invalid XPDR command', 'Некорректная команда XPDR')}: {cmd}",
                    level="warn",
                )
                return
            # Pre-check: if telemetry already proves comms is disabled, deny locally with a clear message.
            comms_enabled: bool | None = None
            telemetry_env = self._snapshots.get_last("telemetry")
            if telemetry_env is not None and isinstance(telemetry_env.payload, dict):
                comms = telemetry_env.payload.get("comms")
                if isinstance(comms, dict):
                    enabled_raw = comms.get("enabled")
                    if isinstance(enabled_raw, bool):
                        comms_enabled = enabled_raw
            if comms_enabled is False:
                self._console_log(
                    I18N.bidi(
                        "XPDR rejected: comms is disabled by hardware profile",
                        "XPDR отклонён: связь отключена профилем железа",
                    ),
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
            if not self._dev_docking_commands_enabled:
                self._console_log(f"{I18N.bidi('Unknown command', 'Неизвестная команда')}: {cmd}", level="info")
                return
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

        # simulation.start [<speed>] (active pause + speed multiplier).
        # NOTE: `simulation.reset` is handled separately and requires confirmation.
        if low.startswith(("simulation.start", "sim.start", "симуляция.старт")):
            parts = cmd.split()
            start_speed: float | None = None
            if len(parts) >= 2:
                token = parts[1].strip().lower()
                if token.startswith("speed="):
                    token = token.split("=", 1)[1].strip()
                if token.startswith("x"):
                    token = token[1:].strip()
                if token.endswith("x"):
                    token = token[:-1].strip()
                try:
                    start_speed = float(token)
                except Exception:
                    self._console_log(
                        f"{I18N.bidi('Invalid speed', 'Некорректная скорость')}: {parts[1]}",
                        level="warn",
                    )
                    return
            await self._publish_sim_command(
                "sim.start", parameters={} if start_speed is None else {"speed": start_speed}
            )
            return

        if (sim_cmd := self._canonicalize_sim_command(low)) is not None:
            if (not self._dev_docking_commands_enabled) and sim_cmd.startswith("power.dock."):
                self._console_log(f"{I18N.bidi('Unknown command', 'Неизвестная команда')}: {cmd}", level="info")
                return
            if sim_cmd == "sim.reset":
                prompt = (
                    f"{I18N.bidi('Reset simulation?', 'Сбросить симуляцию?')} "
                    f"{I18N.bidi('(stop + clear world)', '(стоп + очистка мира)')} "
                    f"({I18N.bidi('Y/N', 'Да/Нет')})"
                )

                def after(decision: bool | None) -> None:
                    if not decision:
                        self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")
                        return
                    asyncio.create_task(self._publish_sim_command(sim_cmd))

                self.push_screen(ConfirmDialog(prompt), after)
                return

            await self._publish_sim_command(sim_cmd)
            return

        self._console_log(f"{I18N.bidi('Unknown command', 'Неизвестная команда')}: {cmd}", level="info")

    async def _publish_qiki_intent(self, text: str) -> None:
        if not text:
            return
        verbose = os.getenv("ORION_QIKI_VERBOSE", "0") == "1"
        if verbose:
            self._console_log(f"{I18N.bidi('QIKI intent', 'Намерение QIKI')}> {text}", level="info")
        else:
            # Chat-style: keep it quiet and avoid transport noise.
            self._calm_log(f"> {text}")
        if not self.nats_client:
            self._console_log(f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}", level="error")
            return
        req = self._build_qiki_chat_request(text)
        try:
            await self.nats_client.publish_command(
                QIKI_INTENTS,
                req.model_dump(mode="json"),
            )
            req_id = str(req.request_id)
            self._qiki_pending[req_id] = (time.time(), text)
            self._qiki_last_request_id = req_id
            asyncio.create_task(self._qiki_watch_timeout(req_id))
            if verbose:
                self._console_log(
                    f"{I18N.bidi('Sent to QIKI', 'Отправлено в QIKI')}: {QIKI_INTENTS} "
                    f"({I18N.bidi('request', 'запрос')}={req.request_id})",
                    level="info",
                )
        except Exception as e:
            self._console_log(
                f"{I18N.bidi('Failed to send', 'Не удалось отправить')}: {e}",
                level="error",
            )

    async def _publish_qiki_proposal_decision(self, *, proposal_id: str, decision: str) -> None:
        pid = (proposal_id or "").strip()
        dec = (decision or "").strip().upper()
        if not pid or dec not in {"ACCEPT", "REJECT"}:
            return
        dec_lit = cast(Literal["ACCEPT", "REJECT"], dec)
        if not self.nats_client:
            self._console_log(f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}", level="error")
            return

        screen_label = next((app.title for app in ORION_APPS if app.screen == self.active_screen), "System/Система")
        req = QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(time.time() * 1000),
            input=QikiChatInput(text=f"proposal {dec_lit.lower()} {pid}", lang_hint="auto"),
            decision=QikiProposalDecisionV1(proposal_id=pid, decision=dec_lit),
            ui_context=UiContext(screen=screen_label, selection=QikiSelectionContext(kind="proposal", id=pid)),
        )

        try:
            await self.nats_client.publish_command(QIKI_INTENTS, req.model_dump(mode="json"))
            req_id = str(req.request_id)
            self._qiki_pending[req_id] = (time.time(), req.input.text)
            self._qiki_last_request_id = req_id
            asyncio.create_task(self._qiki_watch_timeout(req_id))
            self._console_log(
                f"{I18N.bidi('Sent to QIKI', 'Отправлено в QIKI')}: {QIKI_INTENTS} "
                f"({I18N.bidi('request', 'запрос')}={req.request_id})",
                level="info",
            )
        except Exception as e:
            self._console_log(f"{I18N.bidi('Failed to send', 'Не удалось отправить')}: {e}", level="error")

    async def _qiki_watch_timeout(self, request_id: str) -> None:
        timeout = max(0.1, float(self._qiki_response_timeout_sec))
        await asyncio.sleep(timeout)
        pending = self._qiki_pending.get(request_id)
        if not pending:
            return
        started_ts, _text = pending
        self._qiki_pending.pop(request_id, None)
        age_s = max(0.0, time.time() - started_ts)
        self._console_log(
            f"QIKI: {I18N.bidi('timeout', 'таймаут')} "
            f"({I18N.bidi('request', 'запрос')}={request_id}, "
            f"{I18N.bidi('wait', 'ожидание')}={self._fmt_age_s(age_s)})",
            level="warning",
        )

    def _build_qiki_chat_request(self, text: str) -> QikiChatRequestV1:
        screen_label = next((app.title for app in ORION_APPS if app.screen == self.active_screen), "System/Система")
        sel = self._selection_by_app.get(self.active_screen)
        kind: Literal["event", "incident", "track", "snapshot", "proposal", "none"] = "none"
        sel_id = None
        if sel is not None:
            if sel.kind in {"event", "incident", "track", "snapshot", "proposal", "none"}:
                kind = cast(Literal["event", "incident", "track", "snapshot", "proposal", "none"], sel.kind)
            sel_id = sel.key
        return QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(time.time() * 1000),
            input=QikiChatInput(text=text, lang_hint="auto"),
            ui_context=UiContext(screen=screen_label, selection=QikiSelectionContext(kind=kind, id=sel_id)),
        )

    def action_accept_selected_proposal(self) -> None:
        if self.active_screen != "qiki":
            return
        if isinstance(self.focused, Input):
            return
        ctx = self._selection_by_app.get("qiki")
        pid = (ctx.key if ctx is not None else "").strip()
        if not pid or pid == "seed" or getattr(ctx, "kind", "") != "proposal":
            self._console_log(
                f"{I18N.bidi('No proposal selected', 'Предложение не выбрано')}",
                level="info",
            )
            return

        prompt = f"{I18N.bidi('Accept proposal?', 'Принять предложение?')} {pid} ({I18N.bidi('Y/N', 'Да/Нет')})"

        def after(decision: bool | None) -> None:
            if not decision:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")
                return
            asyncio.create_task(self._publish_qiki_proposal_decision(proposal_id=pid, decision="ACCEPT"))

        self.push_screen(ConfirmDialog(prompt), after)

    def action_reject_selected_proposal(self) -> None:
        if self.active_screen != "qiki":
            return
        if isinstance(self.focused, Input):
            return
        ctx = self._selection_by_app.get("qiki")
        pid = (ctx.key if ctx is not None else "").strip()
        if not pid or pid == "seed" or getattr(ctx, "kind", "") != "proposal":
            self._console_log(
                f"{I18N.bidi('No proposal selected', 'Предложение не выбрано')}",
                level="info",
            )
            return

        prompt = f"{I18N.bidi('Reject proposal?', 'Отклонить предложение?')} {pid} ({I18N.bidi('Y/N', 'Да/Нет')})"

        def after(decision: bool | None) -> None:
            if not decision:
                self._console_log(f"{I18N.bidi('Canceled', 'Отменено')}", level="info")
                return
            asyncio.create_task(self._publish_qiki_proposal_decision(proposal_id=pid, decision="REJECT"))

        self.push_screen(ConfirmDialog(prompt), after)

    def _update_command_placeholder(self) -> None:
        try:
            dock = self.query_one("#command-dock", Input)
        except Exception:
            return

        density = getattr(self, "_density", "wide")

        prefix = f"{I18N.bidi('command', 'команда')}> "
        help_part = I18N.bidi("help", "помощь")
        screen_part = f"{I18N.bidi('screen', 'экран')} <name>/<имя>"
        sim_part = "simulation.start [speed]/симуляция.старт [скорость]"
        trust_part = "trust/доверие <trusted|untrusted|off|status|доверенный|недоверенный|выкл|статус>"
        qiki_part = f"{I18N.bidi('QIKI', 'QIKI')}: <text> ({I18N.bidi('default', 'по умолчанию')})"
        sys_part = f"S: <{I18N.bidi('command', 'команда')}>"
        if self._secret_entry_mode == "openai_api_key":
            sys_part = I18N.bidi("OpenAI key: paste and Enter", "OpenAI ключ: вставьте и Enter")

        # Keep the command line readable in tmux splits: show less on narrow/tiny.
        if density == "tiny":
            parts = [help_part, screen_part]
        elif density == "narrow":
            parts = [help_part, screen_part, sim_part, sys_part, trust_part, qiki_part]
        elif density == "normal":
            docking_parts: list[str] = []
            if getattr(self, "_dev_docking_commands_enabled", False):
                docking_parts = [
                    "dock.engage [A|B]",
                    "dock.release",
                ]
            parts = [
                help_part,
                screen_part,
                sim_part,
                sys_part,
                trust_part,
                *docking_parts,
                "xpdr.mode <on|off|silent|spoof>",
                "ответчик.режим <on|off|silent|spoof>",
                "rcs.<axis> <pct> <dur>",
                "rcs.stop",
                qiki_part,
            ]
        else:
            docking_parts = []
            if getattr(self, "_dev_docking_commands_enabled", False):
                docking_parts = [
                    "dock.engage [A|B]",
                    "dock.release",
                    "dock.on/off",
                ]
            parts = [
                help_part,
                screen_part,
                sim_part,
                sys_part,
                trust_part,
                *docking_parts,
                "nbl.on/off",
                "nbl.max <W>",
                "xpdr.mode <on|off|silent|spoof>",
                "ответчик.режим <on|off|silent|spoof>",
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
            "power.dock.on": "power.dock.on",
            "power.dock.off": "power.dock.off",
            "dock.on": "power.dock.on",
            "dock.off": "power.dock.off",
            "док.вкл": "power.dock.on",
            "док.выкл": "power.dock.off",
            "стыковка.вкл": "power.dock.on",
            "стыковка.выкл": "power.dock.off",
            "power.nbl.on": "power.nbl.on",
            "power.nbl.off": "power.nbl.off",
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
        - ответчик.режим <on|off|silent|spoof>
        """
        text = (raw or "").strip()
        parts = text.split()
        if len(parts) < 2:
            return None
        head = parts[0].strip().lower()
        if head not in {"xpdr.mode", "xpdr.режим", "ответчик.режим"}:
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
            logger.debug("orion_exception_swallowed", exc_info=True)
        if not self._warned_command_trim:
            self._warned_command_trim = True
            self._console_log(
                f"{I18N.bidi('Input trimmed', 'Ввод обрезан')}: "
                f"{self._command_max_chars} {I18N.bidi('characters', 'символов')}",
                level="warn",
            )

    async def _publish_sim_command(self, cmd_name: str, *, parameters: Optional[dict[str, Any]] = None) -> None:
        if not self.nats_client:
            self._console_log(f"{I18N.bidi('NATS not initialized', 'NATS не инициализирован')}", level="error")
            return

        destination = "q_sim_service" if cmd_name.startswith(("sim.", "power.")) else "faststream_bridge"
        request_id = uuid4()
        cmd = CommandMessage(
            command_name=cmd_name,
            parameters=parameters or {},
            metadata=MessageMetadata(
                correlation_id=request_id,
                message_type="control_command",
                source="operator_console.orion",
                destination=destination,
            ),
        )
        try:
            await self.nats_client.publish_command(COMMANDS_CONTROL, cmd.model_dump(mode="json"))
            self._console_log(
                f"{I18N.bidi('Published', 'Отправлено')}: {cmd_name} ({I18N.bidi('request', 'запрос')}={request_id})",
                level="info",
            )
        except Exception as e:
            self._console_log(
                f"{I18N.bidi('Publish failed', 'Отправка не удалась')}: {e}",
                level="error",
            )

    async def _publish_audit_event(self, payload: dict[str, Any]) -> None:
        if not self.nats_client:
            return
        try:
            await self.nats_client.publish_command(OPERATOR_ACTIONS, payload)
        except Exception as exc:
            # Audit is best-effort, but failures must be visible (no silent drops).
            self._console_log(
                f"{I18N.bidi('Audit publish failed', 'Не удалось отправить аудит')}: {exc}",
                level="warning",
            )


if __name__ == "__main__":
    OrionApp().run()
