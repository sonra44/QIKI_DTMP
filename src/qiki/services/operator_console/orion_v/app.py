from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Static

from qiki.services.operator_console.clients.nats_client import NATSClient
from qiki.services.operator_console.orion_v.cockpit_playable_view_model import (
    build_cockpit_event_history_item,
    build_cockpit_playable_state,
    cockpit_playable_action_by_id,
    cockpit_playable_effect_panel_id,
    next_cockpit_focus_panel_id,
    next_cockpit_playable_action_id,
    normalize_cockpit_focus_panel_id,
    normalize_cockpit_playable_action_id,
    normalize_cockpit_playable_phase,
)
from qiki.services.operator_console.orion_v.dialogs import ConfirmDialog
from qiki.services.operator_console.orion_v.events_store import BoundedEventsStore, now_epoch_s
from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector
from qiki.services.operator_console.orion_v.hardware_view_model.types import HardwareViewModel
from qiki.services.operator_console.orion_v.i18n_ru import state_ru, tr
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
    run_body_structure_interactive_self_check,
    select_next_body_structure_face,
    select_previous_body_structure_face,
)
from qiki.services.operator_console.orion_v.operator_state import (
    OperatorShellState,
    build_operator_shell_state,
)
from qiki.services.operator_console.orion_v.mfd_layout import (
    MFD_DEFAULT_LEFT_PAGE,
    MFD_DEFAULT_RIGHT_PAGE,
    mfd_button_selection_from_id,
    mfd_button_specs,
    normalize_mfd_page,
)
from qiki.services.operator_console.orion_v.procedure_engine import (
    ProcedureDefinition,
    ProcedureEngine,
    resolve_procedures_dir,
)
from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen
from qiki.services.operator_console.orion_v.screens.deep_dive import OrionVDeepDiveScreen
from qiki.services.operator_console.orion_v.screens.evidence_stream import OrionVEvidenceScreen
from qiki.services.operator_console.orion_v.screens.raw import OrionVRawScreen
from qiki.services.operator_console.orion_v.screens.systems import OrionVSystemsScreen
from qiki.services.operator_console.orion_v.screens.audit import OrionVAuditScreen
from qiki.services.operator_console.orion_v.screens.system_health import OrionVSystemHealthScreen
from qiki.services.operator_console.orion_v.widgets.alerts_overlay import OrionVAlertsOverlay
from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar
from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader
from qiki.services.operator_console.orion_v.widgets.status_bars import OrionVStatusBars
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatInput,
    QikiChatRequestV1,
    QikiChatResponseV1,
    QikiConsequenceV1,
    QikiMode,
    SelectionContext,
    SystemContext,
    TelemetryFreshness,
    UiContext,
)
from qiki.shared.nats_subjects import (
    COMMANDS_CONTROL,
    EVENTS_AUDIT,
    EVENTS_STREAM_NAME,
    OPERATOR_ACTIONS,
    OPERATOR_COMBAT,
    OPERATOR_INCIDENTS,
    OPERATOR_OBJECTIVES,
    OPERATOR_PROCEDURES,
    QIKI_INTENTS,
)

logger = logging.getLogger(__name__)


class OrionVApp(App[None]):
    """ORION V operator console running in parallel with legacy ORION."""

    ENABLE_COMMAND_PALETTE = True
    CSS_PATH = "orion_v.tcss"

    CSS = """
    Screen {
        layout: vertical;
        background: $surface-darken-1;
    }

    #orionv-root {
        height: 1fr;
        layout: vertical;
    }

    #orionv-header {
        height: auto;
        margin: 0 1;
        padding: 0 1;
        /* DISPLAY_CANON (цвет, оператор 2026-07-04): верхняя «палуба» пульта —
           янтарный акцент; severity живёт на кодах, рамка = оформление */
        border: round #d6a65b 60%;
        background: $panel-darken-1 4%;
    }

    #orionv-safety-strip {
        height: auto;
        layout: vertical;
        margin: 0 1;
        padding: 0 1;
        border: round #d6a65b 60%;
        background: $panel 4%;
        border-title-style: bold;
        border-subtitle-style: italic;
    }

    #orionv-overlay,
    #orionv-bars {
        height: auto;
        margin: 0;
        padding: 0;
        border: none;
        background: transparent;
    }

    .orionv-level {
        height: 1fr;
        margin: 0 1;
        padding: 0 1;
        border: round $surface-lighten-1 15%;
    }

    .hidden {
        display: none;
    }

    #orionv-actions {
        height: auto;
        margin: 0 1;
        padding: 0 1;
        border: round $surface-lighten-1 30%;
        background: $panel 4%;
    }

    #orionv-actions Button {
        min-width: 7;
        height: 1;
        margin: 0 1 0 0;
    }

    #orionv-command {
        border: round $surface-lighten-1 30%;
    }

    .ui-dense #orionv-actions Button {
        min-width: 7;
        margin: 0;
    }

    .ui-clean #orionv-actions Button,
    .ui-clean #orionv-bars Button {
        margin-right: 1;
    }

    .ui-dense .orionv-level {
        padding: 0;
    }
    """

    BINDINGS = [
        ("f1", "show_level('f1')", "Кокпит"),
        ("f2", "show_level('f2')", "Подсистемы"),
        ("f3", "show_level('f3')", "Глубокий анализ"),
        ("f4", "show_level('f4')", "Консоль"),
        ("f6", "show_level('f6')", "Журнал"),
        ("f7", "show_level('f7')", "Система"),
        ("f8", "show_level('f8')", "Evidence"),
        ("b", "run_body_structure_self_check", "BODY attach"),
        ("n", "select_next_body_structure_face", "BODY face next"),
        ("p", "select_previous_body_structure_face", "BODY face prev"),
        ("left", "cockpit_playable_prev", "F1 action prev"),
        ("right", "cockpit_playable_next", "F1 action next"),
        ("space", "cockpit_playable_preview", "F1 preview"),
        ("enter", "cockpit_playable_apply", "F1 apply"),
        ("e", "show_level('f8')", "BODY evidence"),
        ("r", "reset_body_structure_self_check", "BODY reset"),
        ("alt+1", "status_chip('power')", "Чип: Питание"),
        ("alt+2", "status_chip('thermal')", "Чип: Тепло"),
        ("alt+3", "status_chip('propulsion')", "Чип: Двигатели"),
        ("alt+4", "status_chip('hull')", "Чип: Корпус"),
        ("alt+5", "status_chip('compute')", "Чип: Вычисления"),
        ("alt+6", "status_chip('qiki')", "Чип: QIKI"),
        ("pagedown", "events_page_next", "Следующая страница"),
        ("pageup", "events_page_prev", "Предыдущая страница"),
        ("up", "cockpit_focus_prev", "F1 panel prev"),
        ("down", "cockpit_focus_next", "F1 panel next"),
        ("h", "cockpit_toggle_help", "F1 help"),
        ("left_square_bracket", "mfd_page_cycle('left')", "Левый MFD: след. страница"),
        ("right_square_bracket", "mfd_page_cycle('right')", "Правый MFD: след. страница"),
        ("a", "ack_selected_incident", "Подтвердить"),
        ("x", "clear_acknowledged_incidents", "Снять подтвержденные"),
        ("slash", "open_command_mode", "Команда"),
        ("colon", "open_command_mode", "Команда"),
        ("escape", "close_command_mode", "Закрыть ввод"),
        ("q", "quit", "Выход"),
    ]

    LEVEL_META = {
        "f1": {"label": "F1 Кокпит", "widget_id": "orionv-cockpit"},
        "f2": {"label": "F2 Системы", "widget_id": "orionv-systems"},
        "f3": {"label": "F3 Глубокий анализ", "widget_id": "orionv-deep"},
        "f4": {"label": "F4 Консоль", "widget_id": "orionv-raw"},
        "f6": {"label": "F6 Журнал", "widget_id": "orionv-audit"},
        "f7": {"label": "F7 Состояние системы", "widget_id": "orionv-health"},
        "f8": {"label": "F8 Улики", "widget_id": "orionv-evidence"},
    }

    def __init__(self) -> None:
        super().__init__()
        self._nats_url = os.getenv("NATS_URL", "nats://nats:4222")
        self._ui_profile = os.getenv("ORIONV_UI_PROFILE", "clean").strip().lower() or "clean"
        self._nats_state = "lost"
        self._current_level = "f1"
        self._active_mfd_left_page = MFD_DEFAULT_LEFT_PAGE
        self._active_mfd_right_page = MFD_DEFAULT_RIGHT_PAGE
        self._f1_playable_loop_state = build_cockpit_playable_state()
        self._telemetry: dict[str, Any] = {}
        self._snapshot: dict[str, Any] = {}
        self._latest_radar_tracks: dict[str, dict[str, Any]] = {}
        self.hardware_collector = HardwareCollector()
        self.hardware_model: HardwareViewModel | None = None
        self._events_preview = max(1, int(os.getenv("ORIONV_EVENTS_PREVIEW", "12")))
        self._events_store = BoundedEventsStore(max_events=int(os.getenv("ORIONV_MAX_EVENTS", "500")))
        self._replay_store = BoundedEventsStore(max_events=int(os.getenv("ORIONV_MAX_EVENTS", "500")))
        self._audit_store = BoundedEventsStore(max_events=int(os.getenv("ORIONV_MAX_AUDIT_EVENTS", "1000")))
        self._nats_client = NATSClient(url=self._nats_url)
        self._nats_client.set_lifecycle_callback(self._on_nats_lifecycle_state)
        self._subscriptions_started = False
        self._selected_incident_id: str | None = None
        self._selected_system_module_slug: str | None = None
        self._events_page_size = max(10, int(os.getenv("ORIONV_EVENTS_PAGE_SIZE", "50")))
        self._events_page = 0
        self._audit_page_size = max(10, int(os.getenv("ORIONV_AUDIT_PAGE_SIZE", "50")))
        self._audit_page = 0
        self._audit_filter_type: str | None = None
        self._filter_severities: set[str] = set()
        self._filter_subsystem: str | None = None
        self._filter_window_sec: int | None = None
        self._replay_mode = False
        self._procedure_engine = ProcedureEngine()
        self._procedure_task: asyncio.Task[None] | None = None
        self._control_acks: deque[dict[str, Any]] = deque(maxlen=100)
        self._pending_ack_command_id: str | None = None
        self._ack_wait_started_mono: float | None = None
        self._qiki_pending: dict[str, tuple[float, str]] = {}
        self._qiki_last_response: QikiChatResponseV1 | None = None
        self._qiki_pending_action: dict[str, Any] | None = None
        self._active_observation_objective: dict[str, Any] | None = None
        self._event_timestamps: deque[float] = deque(maxlen=4000)
        self._incident_first_seen: dict[str, float] = {}
        self._console_history: deque[str] = deque(maxlen=max(50, int(os.getenv("ORIONV_CONSOLE_HISTORY", "200"))))
        self._command_mode_open = False
        self._help_text = "Команды: help"
        self._last_command_status = "idle"
        self._last_command_summary = "Команда ещё не подавалась"
        self._operator_shell_state = OperatorShellState.empty()
        self._last_telemetry_received_wall: float | None = None
        self._safe_mode_state: dict[str, Any] = {
            "active": None,
            "reason": "",
            "authority": "q-core-agent(events)",
            "updated_ts": None,
        }
        self._metrics: dict[str, Any] = {
            "events_per_sec": 0.0,
            "queue_depth": 0,
            "procedure_latency_ms": 0.0,
            "ack_time_ms": 0.0,
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "bounded_store_size": 0,
            "bounded_store_limit": self._events_store.max_events,
            "active_subscriptions": 0,
            "nats_state": "lost",
            "replay_mode": False,
        }
        self._last_proc_start_mono: float | None = None
        self._last_cpu_usage_us: float | None = None
        self._last_cpu_read_mono: float | None = None
        self._refresh_pending = False
        procedures_dir = resolve_procedures_dir(
            os.getenv("ORIONV_PROCEDURES_DIR"),
            repo_root=os.getenv("QIKI_REPO_ROOT"),
        )
        self._procedure_engine.load_from_dir(procedures_dir)

    def compose(self) -> ComposeResult:
        with Container(id="orionv-root"):
            # DISPLAY_CANON: бренд живёт НАД рамками (заголовок консоли), не в
            # строке данных; внутримирово ORION V — терминал станции обслуживания.
            yield Static("[dim][b]ORION V[/b] — терминал оператора[/dim]", id="orionv-console-brand")
            yield OrionVHeader(id="orionv-header")
            with Container(id="orionv-safety-strip"):
                yield OrionVAlertsOverlay(id="orionv-overlay")
                yield OrionVStatusBars(id="orionv-bars")
            yield OrionVCockpitScreen(id="orionv-cockpit", classes="orionv-level")
            yield OrionVSystemsScreen(id="orionv-systems", classes="orionv-level hidden")
            yield OrionVDeepDiveScreen(id="orionv-deep", classes="orionv-level hidden")
            yield OrionVRawScreen(id="orionv-raw", classes="orionv-level hidden")
            yield OrionVEvidenceScreen(self._snapshot, id="orionv-evidence", classes="orionv-level hidden")
            yield OrionVAuditScreen(id="orionv-audit", classes="orionv-level hidden")
            yield OrionVSystemHealthScreen(id="orionv-health", classes="orionv-level hidden")
            yield OrionVActionBar(id="orionv-actions")

    async def on_mount(self) -> None:
        if self._ui_profile == "dense":
            self.add_class("ui-dense")
        else:
            self.add_class("ui-clean")
        # DISPLAY_CANON: зона = ОДИН русский титул (Союз/Буран-стиль), без нижней
        # подписи-дубля (назначение зоны → tooltip). Титул хедера с якорем экрана
        # ставит сам виджет (динамически, по текущему уровню).
        safety_strip = self.query_one("#orionv-safety-strip", Container)
        safety_strip.border_title = "СОСТОЯНИЕ БОРТА"  # DISPLAY_CANON строка №3 (оператор)
        actions = self.query_one("#orionv-actions", OrionVActionBar)
        actions.border_title = "ACTION RAIL"  # имя зоны — при её строке прохода
        command = self.query_one("#orionv-command", Input)
        command.border_title = "ВВОД/INPUT"
        command.border_subtitle = "q: <команда> | q confirm | q cancel"
        await self._connect_and_subscribe()
        await self._hydrate_last_observation_objective_from_jetstream()
        self._refresh_ui()
        self.set_interval(1.0, self._refresh_nats_state)
        self.set_interval(1.0, self._refresh_runtime_metrics)

    async def on_unmount(self) -> None:
        try:
            await self._nats_client.disconnect()
        except Exception:
            logger.debug("orion_v_disconnect_failed", exc_info=True)

    async def _connect_and_subscribe(self) -> None:
        try:
            if not (self._nats_client.nc and self._nats_client.nc.is_connected):
                await self._nats_client.connect()
            self._nats_state = self._nats_client.connection_state
            if not self._subscriptions_started:
                await self._nats_client.subscribe_system_telemetry(self._on_telemetry)
                await self._nats_client.subscribe_tracks(self._on_track)
                await self._nats_client.subscribe_events(self._on_event)
                await self._nats_client.subscribe_control_responses(self._on_control_response)
                await self._nats_client.subscribe_qiki_responses(self._on_qiki_response)
                self._subscriptions_started = True
        except Exception:
            self._nats_state = "lost"
            logger.debug("orion_v_connect_or_subscribe_failed", exc_info=True)

    async def _hydrate_last_observation_objective_from_jetstream(self) -> None:
        if self._active_observation_objective is not None:
            return
        try:
            payload = await self._nats_client.fetch_last_event_json(
                stream=EVENTS_STREAM_NAME,
                subject=OPERATOR_OBJECTIVES,
            )
        except Exception:
            logger.debug("orion_v_hydrate_objective_from_jetstream_failed", exc_info=True)
            return
        if not isinstance(payload, dict):
            return
        if str(payload.get("objective_type") or "observation").strip().lower() != "observation":
            return
        await self._on_event(
            {
                "stream": "EVENTS_REPLAY",
                "timestamp": str(payload.get("timestamp") or datetime.now(tz=timezone.utc).isoformat()),
                "subject": OPERATOR_OBJECTIVES,
                "data": payload,
            }
        )

    async def _refresh_nats_state(self) -> None:
        next_state = self._nats_client.connection_state
        if next_state == self._nats_state:
            return
        self._nats_state = next_state
        self._request_refresh_ui()

    def _request_refresh_ui(self) -> None:
        if not self.is_mounted:
            self._refresh_ui()
            return
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self.call_later(self._run_scheduled_refresh_ui)

    def _run_scheduled_refresh_ui(self) -> None:
        self._refresh_pending = False
        self._refresh_ui()

    async def _on_nats_lifecycle_state(self, state: str) -> None:
        self._nats_state = state
        if state == "connected" and not self._subscriptions_started:
            try:
                await self._connect_and_subscribe()
            except Exception:
                logger.debug("orion_v_lifecycle_connect_failed", exc_info=True)
        self._request_refresh_ui()

    async def _on_telemetry(self, envelope: dict[str, Any]) -> None:
        payload = envelope.get("data") if isinstance(envelope, dict) else None
        if isinstance(payload, dict):
            self._telemetry = payload
            self._last_telemetry_received_wall = time.time()
            self._merge_snapshot(self._snapshot, payload)
            self.hardware_model = self.hardware_collector.update(self._snapshot)
        self._request_refresh_ui()

    async def _on_track(self, envelope: dict[str, Any]) -> None:
        payload = envelope.get("data") if isinstance(envelope, dict) else None
        if not isinstance(payload, dict):
            return
        track_id = str(payload.get("track_id") or "").strip()
        if not track_id:
            return
        if str(payload.get("status") or "").strip().upper() == "LOST":
            self._latest_radar_tracks.pop(track_id, None)
            return
        track_payload = dict(payload)
        source_timestamp = _extract_event_timestamp(payload, envelope.get("timestamp"))
        if source_timestamp is not None:
            track_payload["_orion_source_timestamp_unix_s"] = source_timestamp
        track_payload["_orion_received_at_unix_s"] = time.time()
        self._latest_radar_tracks[track_id] = track_payload

    async def _on_event(self, envelope: dict[str, Any]) -> None:
        if isinstance(envelope, dict):
            self._events_store.append(envelope)
            self._event_timestamps.append(time.monotonic())
            self._update_safe_mode_from_event(envelope)
            payload = envelope.get("data")
            if isinstance(payload, dict):
                if str(envelope.get("subject") or "").strip() == OPERATOR_OBJECTIVES:
                    self._active_observation_objective = dict(payload)
                    self._enrich_active_observation_with_live_public_track()
                    if str(payload.get("reason_code") or "").strip() in {
                        "OBJECTIVE_REVIEW_CLOSED",
                        "OBJECTIVE_POST_REVIEW_HOLD_SELECTED",
                        "OBJECTIVE_RESUME_OBSERVATION_SELECTED",
                    }:
                        self._apply_observation_follow_up_to_qiki(self._observation_follow_up_contract(payload))
                    elif self._observation_result_contract(payload) is not None:
                        self._apply_observation_result_to_qiki(self._observation_result_contract(payload))
                incident_id = str(
                    payload.get("incident_id") or payload.get("incident_key") or payload.get("id") or ""
                ).strip()
                first_seen = False
                incident_ts: float | None = None
                if incident_id and incident_id not in self._incident_first_seen:
                    first_seen = True
                    incident_ts = _extract_event_timestamp(payload, envelope.get("timestamp"))
                    if incident_ts is None:
                        incident_ts = datetime.now(tz=timezone.utc).timestamp()
                    self._incident_first_seen[incident_id] = incident_ts
                if first_seen:
                    incident_open_audit = _incident_open_audit_payload(
                        incident_id=incident_id,
                        payload=payload,
                        incident_ts=incident_ts,
                    )
                    if incident_open_audit is not None:
                        asyncio.create_task(self._publish_audit_event(OPERATOR_INCIDENTS, incident_open_audit))
        self._request_refresh_ui()

    async def _on_control_response(self, envelope: dict[str, Any]) -> None:
        if isinstance(envelope, dict):
            envelope.setdefault("_received_mono", time.monotonic())
            self._control_acks.append(envelope)
        self._request_refresh_ui()

    def _update_f1_playable_loop_state(
        self,
        *,
        selected_action_id: str | None = None,
        phase: str | None = None,
        last_event_id: str | None = None,
        last_event_summary: str | None = None,
        last_action_id: str | None = None,
        last_effect_panel_id: str | None = None,
        last_effect_summary: str | None = None,
        append_history_item: dict[str, str] | None = None,
        focused_panel_id: str | None = None,
        focus_reason: str | None = None,
        help_visible: bool | None = None,
        increment_cycle: bool = False,
    ) -> None:
        state = dict(self._f1_playable_loop_state or {})
        if selected_action_id is not None:
            state["selected_action_id"] = normalize_cockpit_playable_action_id(selected_action_id)
        else:
            state["selected_action_id"] = normalize_cockpit_playable_action_id(state.get("selected_action_id"))
        if phase is not None:
            state["phase"] = normalize_cockpit_playable_phase(phase)
        else:
            state["phase"] = normalize_cockpit_playable_phase(state.get("phase"))
        if last_event_id is not None:
            state["last_event_id"] = str(last_event_id or "").strip()
        if last_event_summary is not None:
            state["last_event_summary"] = str(last_event_summary or "").strip()
        if last_action_id is not None:
            state["last_action_id"] = (
                normalize_cockpit_playable_action_id(last_action_id)
                if str(last_action_id or "").strip()
                else ""
            )
        if last_effect_panel_id is not None:
            state["last_effect_panel_id"] = str(last_effect_panel_id or "").strip().lower()
        if last_effect_summary is not None:
            state["last_effect_summary"] = str(last_effect_summary or "").strip()
        if append_history_item is not None:
            history = list(state.get("action_history") or [])
            history.append(dict(append_history_item))
            state["action_history"] = history
        if focused_panel_id is not None:
            state["focused_panel_id"] = normalize_cockpit_focus_panel_id(
                focused_panel_id, selected_action_id=state.get("selected_action_id")
            )
        else:
            state["focused_panel_id"] = normalize_cockpit_focus_panel_id(
                state.get("focused_panel_id"), selected_action_id=state.get("selected_action_id")
            )
        if focus_reason is not None:
            state["focus_reason"] = str(focus_reason or "").strip() or "selected_by_key"
        else:
            state["focus_reason"] = str(state.get("focus_reason") or "default").strip() or "default"
        if help_visible is not None:
            state["help_visible"] = bool(help_visible)
        else:
            state["help_visible"] = bool(state.get("help_visible", True))
        if increment_cycle:
            try:
                state["cycle_count"] = int(state.get("cycle_count", 0)) + 1
            except Exception:
                state["cycle_count"] = 1
        self._f1_playable_loop_state = build_cockpit_playable_state(
            selected_action_id=state.get("selected_action_id"),
            phase=state.get("phase"),
            cycle_count=state.get("cycle_count", 0),
            last_event_id=state.get("last_event_id"),
            last_event_summary=state.get("last_event_summary"),
            last_action_id=state.get("last_action_id"),
            last_effect_panel_id=state.get("last_effect_panel_id"),
            last_effect_summary=state.get("last_effect_summary"),
            action_history=state.get("action_history"),
            focused_panel_id=state.get("focused_panel_id"),
            focus_reason=state.get("focus_reason"),
            help_visible=state.get("help_visible"),
        )

    def _f1_playable_selected_action_id(self) -> str:
        return normalize_cockpit_playable_action_id(self._f1_playable_loop_state.get("selected_action_id"))

    def _f1_focused_panel_id(self) -> str:
        return normalize_cockpit_focus_panel_id(
            self._f1_playable_loop_state.get("focused_panel_id"),
            selected_action_id=self._f1_playable_selected_action_id(),
        )

    def action_cockpit_palette_select(self, action_id: str) -> None:
        """Select one F1 action from Textual command palette without executing runtime commands."""
        if self._current_level != "f1":
            self._current_level = "f1"
            self._events_page = 0
            self._audit_page = 0
            self._refresh_visible_level()
        normalized_action_id = normalize_cockpit_playable_action_id(action_id)
        action_vm = cockpit_playable_action_by_id(normalized_action_id)
        summary = f"F1 PALETTE selected: {action_vm.label}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            selected_action_id=normalized_action_id,
            phase="selected",
            focused_panel_id=cockpit_playable_effect_panel_id(normalized_action_id),
            focus_reason="palette",
            help_visible=True,
            last_event_summary=summary,
        )
        self._refresh_ui()

    def get_system_commands(self, screen: Any) -> Iterable[Any]:
        """Expose the F1 local cockpit loop through Textual's command palette.

        These palette entries are discoverability affordances only. Selecting one
        moves ORION to F1 and arms the local action; it does not publish a runtime
        command, claim ACK, or claim physical effect confirmation.
        """
        yield from super().get_system_commands(screen)
        try:
            from textual.command import SystemCommand
        except Exception:
            return

        f1_commands = (
            (
                "Ф1 Проверка корпуса",
                "Выбрать ПРОВЕРКУ КОРПУСА в локальном цикле кокпита; команда боту не отправляется.",
                "body_self_check",
            ),
            (
                "Ф1 Обновить питание",
                "Выбрать ОБНОВИТЬ ПИТАНИЕ; обновляет только проекцию питания, не PDU-runtime.",
                "power_refresh",
            ),
            (
                "Ф1 Смена страницы НАВ",
                "Выбрать СМЕНУ СТРАНИЦЫ НАВ; листает только состояние MFD, команда манёвра не отправляется.",
                "nav_cycle",
            ),
            (
                "Ф1 Фокус сенсоров",
                "Выбрать ФОКУС СЕНСОРОВ; открывает проекцию только для чтения, скан не активируется.",
                "sensor_focus",
            ),
            (
                "Ф1 Репетиция команды",
                "Выбрать РЕПЕТИЦИЮ КОМАНДЫ; показывает семантику запроса без publish/ACK/effect.",
                "command_preview",
            ),
        )
        for title, help_text, action_id in f1_commands:
            yield SystemCommand(
                title=title,
                help=help_text,
                callback=lambda action_id=action_id: self.action_cockpit_palette_select(action_id),
                discover=True,
            )

    def action_cockpit_focus_next(self) -> None:
        """Move F1 panel focus forward; outside F1 preserve incident navigation."""
        if self._current_level != "f1":
            self.action_incident_next()
            return
        panel_id = next_cockpit_focus_panel_id(self._f1_focused_panel_id(), delta=1)
        summary = f"F1 FOCUS panel selected: {panel_id.upper()}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            phase="selected",
            focused_panel_id=panel_id,
            focus_reason="panel_key",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_focus_prev(self) -> None:
        """Move F1 panel focus backward; outside F1 preserve incident navigation."""
        if self._current_level != "f1":
            self.action_incident_prev()
            return
        panel_id = next_cockpit_focus_panel_id(self._f1_focused_panel_id(), delta=-1)
        summary = f"F1 FOCUS panel selected: {panel_id.upper()}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            phase="selected",
            focused_panel_id=panel_id,
            focus_reason="panel_key",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_toggle_help(self) -> None:
        """Toggle the local F1 help/context rows."""
        if self._current_level != "f1":
            return
        next_visible = not bool(self._f1_playable_loop_state.get("help_visible", True))
        summary = f"F1 HELP {'shown' if next_visible else 'hidden'}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            phase="selected",
            help_visible=next_visible,
            focus_reason="help_toggle",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_playable_next(self) -> None:
        """Select the next local F1 cockpit action; no runtime command is executed."""
        if self._current_level != "f1":
            return
        action_id = next_cockpit_playable_action_id(self._f1_playable_selected_action_id(), delta=1)
        action_vm = cockpit_playable_action_by_id(action_id)
        summary = f"Ф1 выбрано: {action_vm.label}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            selected_action_id=action_id,
            phase="selected",
            focused_panel_id=cockpit_playable_effect_panel_id(action_id),
            focus_reason="action_key",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_playable_prev(self) -> None:
        """Select the previous local F1 cockpit action; no runtime command is executed."""
        if self._current_level != "f1":
            return
        action_id = next_cockpit_playable_action_id(self._f1_playable_selected_action_id(), delta=-1)
        action_vm = cockpit_playable_action_by_id(action_id)
        summary = f"Ф1 выбрано: {action_vm.label}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            selected_action_id=action_id,
            phase="selected",
            focused_panel_id=cockpit_playable_effect_panel_id(action_id),
            focus_reason="action_key",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_playable_preview(self) -> None:
        """Preview the selected F1 action in the cockpit command strip."""
        if self._current_level != "f1":
            return
        action_vm = cockpit_playable_action_by_id(self._f1_playable_selected_action_id())
        summary = f"Ф1 предпросмотр: {action_vm.label} → {action_vm.cycle_effect}"
        self._console_history.append(summary)
        self._last_command_status = "preview"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            phase="preview",
            focused_panel_id=cockpit_playable_effect_panel_id(action_vm.action_id),
            focus_reason="preview",
            last_event_summary=summary,
        )
        self._refresh_ui()

    def action_cockpit_playable_apply(self) -> None:
        """Apply one normal-only F1 local loop action and record an operator audit event.

        This method deliberately does not publish a runtime command.  It changes only
        ORION cockpit/local adapter state, except for BODY SELF-CHECK which reuses the
        existing body-structure self-check seed.
        """
        if self._current_level != "f1":
            return
        # цикл требует явного предпросмотра: случайный ENTER (глобальный биндинг)
        # не должен порождать событие/аудит — сначала SPACE, потом применение
        current_phase = normalize_cockpit_playable_phase(
            (self._f1_playable_loop_state or {}).get("phase")
        )
        if current_phase != "preview":
            summary = "Ф1: сначала предпросмотр — SPACE (или кнопка «Предпросмотр»)"
            self._console_history.append(summary)
            self._last_command_status = "blocked"
            self._last_command_summary = summary
            self._refresh_ui()
            return
        action_vm = cockpit_playable_action_by_id(self._f1_playable_selected_action_id())
        event_id = f"f1-loop:{uuid4().hex[:12]}"

        if action_vm.action_id == "body_self_check":
            snapshot = run_body_structure_interactive_self_check()
            decision = snapshot.decision
            if decision is None:
                effect = "проверка корпуса не дала решения"
            elif snapshot.interaction_state == "already_attached":
                effect = "корпус уже с модулем; конфигурация не перезаписана"
            else:
                effect = f"проверка корпуса: {decision.status} @ {decision.mount_point}"
        elif action_vm.action_id == "power_refresh":
            effect = "проекция питания и накопителей обновлена из текущего снимка"
        elif action_vm.action_id == "nav_cycle":
            next_left_page = {
                "radar": "nav",
                "nav": "target",
                "target": "sector",
                "sector": "mission",
                "mission": "radar",
            }.get(self._active_mfd_left_page, "radar")
            self._active_mfd_left_page = normalize_mfd_page("left", next_left_page)
            effect = f"левый MFD переключён на страницу {self._active_mfd_left_page}"
        elif action_vm.action_id == "sensor_focus":
            self._active_mfd_right_page = normalize_mfd_page("right", "sensors")
            self._selected_system_module_slug = "sensors"
            effect = "правый MFD: сенсорная проекция (только чтение)"
        else:
            effect = "репетиция команды записана; publish/ACK/effect не заявляются"

        effect_panel_id = cockpit_playable_effect_panel_id(action_vm.action_id)
        history_item = build_cockpit_event_history_item(
            event_id=event_id,
            action_label=action_vm.label,
            target_panel_id=effect_panel_id,
            effect_summary=effect,
        )
        summary = f"Ф1 применено: {action_vm.label}; {effect}; улика={event_id}"
        self._console_history.append(summary)
        self._last_command_status = "ok"
        self._last_command_summary = summary
        self._update_f1_playable_loop_state(
            phase="evidence_visible",
            last_event_id=event_id,
            last_event_summary=summary,
            last_action_id=action_vm.action_id,
            last_effect_panel_id=effect_panel_id,
            last_effect_summary=effect,
            append_history_item=history_item,
            focused_panel_id=effect_panel_id,
            focus_reason="after_apply",
            increment_cycle=True,
        )
        asyncio.create_task(
            self._publish_audit_event(
                OPERATOR_ACTIONS,
                {
                    "kind": "f1_playable_loop",
                    "action_type": "f1_playable_loop",
                    "event_id": event_id,
                    "action_id": action_vm.action_id,
                    "action_label": action_vm.label,
                    "phase": "evidence_visible",
                    "effect_summary": effect,
                    "effect_panel_id": effect_panel_id,
                    "runtime_claim_status": "local_ui_loop_no_runtime_command",
                    "source_owner": action_vm.source_owner,
                    "evidence_policy": action_vm.evidence_policy,
                    "operator": "orion_v",
                },
            )
        )
        self._refresh_ui()

    def action_run_body_structure_self_check(self) -> None:
        """Run the visible local body-structure attach loop and refresh F1/F2/F8."""
        snapshot = run_body_structure_interactive_self_check()
        decision = snapshot.decision
        if decision is None:
            summary = "КОРПУС: проверка ожидает запуска"
        elif snapshot.interaction_state == "already_attached":
            summary = "КОРПУС: модуль уже установлен; R — сброс"
        else:
            summary = (
                f"КОРПУС: проверка — {state_ru(decision.status)} @ {decision.mount_point}; "
                f"аудит={decision.audit_event_id}"
            )
        self._console_history.append(summary)
        self._last_command_status = "ok"
        self._last_command_summary = summary
        self._refresh_ui()


    def action_select_next_body_structure_face(self) -> None:
        """Cycle the visible Face Map selection without mutating body_config."""
        snapshot = select_next_body_structure_face()
        summary = f"КОРПУС: выбрана грань {snapshot.selected_face_id}"
        self._console_history.append(summary)
        self._last_command_status = "ok"
        self._last_command_summary = summary
        self._refresh_ui()


    def action_select_previous_body_structure_face(self) -> None:
        """Cycle the visible Face Map selection backwards without mutating body_config."""
        snapshot = select_previous_body_structure_face()
        summary = f"КОРПУС: выбрана грань {snapshot.selected_face_id}"
        self._console_history.append(summary)
        self._last_command_status = "ok"
        self._last_command_summary = summary
        self._refresh_ui()

    def action_reset_body_structure_self_check(self) -> None:
        """Reset the visible local body-structure loop to modules=0/F06=free."""
        reset_body_structure_interactive_state()
        summary = "КОРПУС: сброс проверки — модулей 0; F06 свободна"
        self._console_history.append(summary)
        self._last_command_status = "ok"
        self._last_command_summary = summary
        self._refresh_ui()

    def action_show_level(self, level: str) -> None:
        key = level.strip().lower()
        if key not in self.LEVEL_META:
            return
        self._current_level = key
        self._events_page = 0
        self._audit_page = 0
        self._refresh_visible_level()
        if key == "f8":
            self._prefer_f8_evidence_card_for_current_context()
        asyncio.create_task(
            self._publish_audit_event(
                OPERATOR_ACTIONS,
                {
                    "kind": "level_switch",
                    "action_type": "level",
                    "level": key,
                    "operator": "orion_v",
                },
            )
        )
        self._request_refresh_ui()

    def _preferred_f8_evidence_subsystem(self) -> str:
        """Return the preferred read-only evidence detail for the current ORION context."""
        subsystem = (self._selected_system_module_slug or "").strip().lower()
        right_page = (self._active_mfd_right_page or "").strip().lower()
        if subsystem in {"power", "thermal"} or right_page in {"power", "thermal"}:
            return "POWER/ACCUMULATOR"
        return "BODY"

    def _prefer_f8_evidence_card_for_current_context(self) -> None:
        """When entering F8, pick the evidence detail matching the current MFD context."""
        try:
            evidence = self.query_one("#orionv-evidence", OrionVEvidenceScreen)
        except Exception:
            return
        evidence.prefer_evidence_card(self._preferred_f8_evidence_subsystem())

    def action_evidence_select_next(self) -> None:
        """Keyboard parity for F8 evidence detail selection; no command execution."""
        if self._current_level != "f8":
            return
        self.query_one("#orionv-evidence", OrionVEvidenceScreen).select_next_evidence_card()

    def action_evidence_select_previous(self) -> None:
        """Keyboard parity for F8 evidence detail selection; no command execution."""
        if self._current_level != "f8":
            return
        self.query_one("#orionv-evidence", OrionVEvidenceScreen).select_previous_evidence_card()

    def action_select_subsystem(self, subsystem_slug: str) -> None:
        slug = subsystem_slug.strip().lower()
        if not slug:
            return
        self._selected_system_module_slug = slug
        page_by_subsystem = {
            "body_structure": "systems",
            "power": "power",
            "thermal": "thermal",
            "sensors": "sensors",
            "comms": "comms",
            "propulsion": "propulsion",
            "docking": "docking",
            "safety": "journal",
        }
        if slug in page_by_subsystem:
            self._active_mfd_right_page = normalize_mfd_page("right", page_by_subsystem[slug])
        if self._current_level != "f2":
            self._current_level = "f2"
            self._events_page = 0
            self._audit_page = 0
            self._refresh_visible_level()
        self._set_help_text(f"Подсистема выбрана/Subsystem selected: {slug}")
        asyncio.create_task(
            self._publish_operator_action(
                {
                    "kind": "subsystem_select",
                    "action_type": "systems",
                    "subsystem": slug,
                    "input_mode": "mouse",
                    "operator": "orion_v",
                }
            )
        )
        self._request_refresh_ui()

    def action_select_incident(self, incident_id: str) -> None:
        selected = incident_id.strip()
        if not selected:
            return
        self._selected_incident_id = selected
        self._set_help_text(f"Выбран/Selected incident: {selected}")
        asyncio.create_task(
            self._publish_operator_action(
                {
                    "kind": "incident_select",
                    "action_type": "incidents",
                    "incident_id": selected,
                    "input_mode": "mouse",
                    "operator": "orion_v",
                }
            )
        )
        self._request_refresh_ui()

    def action_incident_next(self) -> None:
        if self._current_level == "f8":
            self.action_evidence_select_next()
            return
        self._shift_incident_selection(step=1)

    def action_incident_prev(self) -> None:
        if self._current_level == "f8":
            self.action_evidence_select_previous()
            return
        self._shift_incident_selection(step=-1)

    def on_orion_v_alerts_overlay_incident_selected(self, message: OrionVAlertsOverlay.IncidentSelected) -> None:
        self._selected_incident_id = message.incident_id
        self._set_help_text(f"Выбран/Selected incident: {message.incident_id}")
        asyncio.create_task(
            self._publish_operator_action(
                {
                    "kind": "incident_select",
                    "action_type": "incidents",
                    "incident_id": message.incident_id,
                    "input_mode": "mouse",
                    "operator": "orion_v",
                }
            )
        )
        self._request_refresh_ui()

    def on_orion_v_action_bar_action_triggered(self, message: OrionVActionBar.ActionTriggered) -> None:
        self._handle_action_bar_action(message.action)

    def _route_metric_action(self, action: str, target: str) -> None:
        if action == "select_subsystem":
            self.action_select_subsystem(target)
        elif action == "show_level":
            self.action_show_level(target)

    def on_orion_v_status_bars_metric_action_triggered(self, message: OrionVStatusBars.MetricActionTriggered) -> None:
        self._route_metric_action(message.action, message.target)

    def action_status_chip(self, slug: str) -> None:
        # Keyboard parity (Alt+1..6) for the clickable status-bar chips: trigger the chip's
        # own action/target by slug — identical to clicking it, no index/order coupling.
        chip = next((item for item in self._operator_shell_state.chips if item.slug == slug), None)
        if chip is not None:
            self._route_metric_action(chip.action, chip.target)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        mfd_selection = mfd_button_selection_from_id(button_id)
        if mfd_selection is not None:
            side, page = mfd_selection
            self._select_mfd_page(side=side, page=page)
            return
        if button_id == "orionv-command-open":
            self.action_open_command_mode()
            return
        if button_id.startswith("orionv-cockpit-jump-"):
            target = button_id.removeprefix("orionv-cockpit-jump-").strip().lower()
            if target == "power":
                self.action_select_subsystem("power")
                return
            if target == "navigation":
                self.action_select_subsystem("navigation")
                return
            if target == "docking":
                self.action_select_subsystem("docking")
                return
            if target == "comms":
                self.action_select_subsystem("comms")
                return
            if target == "thermal":
                self.action_select_subsystem("thermal")
                return
            if target == "incidents":
                self.action_show_level("f3")
                return
            if target == "procedures":
                self.action_show_level("f6")
                self._set_audit_filter("procedures")
                return
        if button_id == "orionv-cockpit-qiki-confirm":
            self._confirm_qiki_pending_action()
            return
        if button_id == "orionv-cockpit-qiki-cancel":
            self._cancel_qiki_pending_action()
            return
        if button_id == "orionv-cockpit-loop-prev":
            self.action_cockpit_playable_prev()
            return
        if button_id == "orionv-cockpit-loop-next":
            self.action_cockpit_playable_next()
            return
        if button_id == "orionv-cockpit-loop-preview":
            self.action_cockpit_playable_preview()
            return
        if button_id == "orionv-cockpit-loop-apply":
            self.action_cockpit_playable_apply()
            return
        if button_id == "orionv-cockpit-focus-prev":
            self.action_cockpit_focus_prev()
            return
        if button_id == "orionv-cockpit-focus-next":
            self.action_cockpit_focus_next()
            return
        if button_id == "orionv-cockpit-help-toggle":
            self.action_cockpit_toggle_help()
            return
        if button_id.startswith("orionv-status-") and button_id.endswith("-action"):
            metric_slug = button_id.removeprefix("orionv-status-").removesuffix("-action").strip().lower()
            if metric_slug in {"power", "thermal", "comms", "hull"}:
                self.action_select_subsystem(metric_slug)
                return
            if metric_slug == "incidents":
                self.action_show_level("f3")
                return
        if not button_id.startswith("orionv-action-"):
            return
        action = button_id.removeprefix("orionv-action-").strip().lower()
        if not action:
            return
        self._handle_action_bar_action(action)


    def action_mfd_page_cycle(self, side: str) -> None:
        """Листание страниц MFD с клавиатуры ([ — левый, ] — правый).

        Только смена UI-страницы: команд боту не отправляет. Работает на
        F1/F2, где MFD-панели видимы.
        """
        if self._current_level not in {"f1", "f2"}:
            return
        normalized_side = "left" if str(side).strip().lower() == "left" else "right"
        pages = [spec.page for spec in mfd_button_specs(normalized_side)]
        if not pages:
            return
        current = (
            self._active_mfd_left_page if normalized_side == "left" else self._active_mfd_right_page
        )
        try:
            next_page = pages[(pages.index(current) + 1) % len(pages)]
        except ValueError:
            next_page = pages[0]
        self._select_mfd_page(side=normalized_side, page=next_page)

    def _select_mfd_page(self, *, side: str, page: str) -> None:
        normalized_side = str(side or "").strip().lower()
        if normalized_side == "left":
            self._active_mfd_left_page = normalize_mfd_page("left", page)
            label = f"левый MFD: страница {self._active_mfd_left_page}"
        elif normalized_side == "right":
            self._active_mfd_right_page = normalize_mfd_page("right", page)
            label = f"правый MFD: страница {self._active_mfd_right_page}"
            subsystem_by_page = {
                "systems": "body_structure",
                "sensors": "sensors",
                "power": "power",
                "thermal": "power",
                "comms": "comms",
                "propulsion": "propulsion",
                "docking": "docking",
                "journal": "safety",
                "procedures": "safety",
            }
            self._selected_system_module_slug = subsystem_by_page.get(
                self._active_mfd_right_page,
                self._selected_system_module_slug,
            )
        else:
            return
        self._console_history.append(label)
        self._last_command_status = "ok"
        self._last_command_summary = label
        self._refresh_ui()

    def _handle_action_bar_action(self, action: str) -> None:
        if action in {"f1", "f2", "f3", "f4", "f6", "f7", "f8"}:
            self.action_show_level(action)
            return
        if action == "incident_next":
            self.action_incident_next()
            return
        if action == "incident_prev":
            self.action_incident_prev()
            return
        if action == "ack":
            self.action_ack_selected_incident()
            return
        if action == "clear":
            self.action_clear_acknowledged_incidents()
            return
        if action == "page_next":
            self.action_events_page_next()
            return
        if action == "page_prev":
            self.action_events_page_prev()
            return

    def action_ack_selected_incident(self) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        incident_id = self._selected_incident_id
        if not incident_id:
            self._set_help_text("Инцидент не выбран")
            return
        self.push_screen(
            ConfirmDialog(f"Подтвердить инцидент {incident_id}?"),
            lambda confirmed: self._run_after_confirm(
                confirmed,
                lambda: self._ack_incident(incident_id),
            ),
        )

    def action_ack_incident(self, incident_id: str) -> None:
        if self._replay_mode:
            self.action_ack_selected_incident()
            return
        selected = incident_id.strip()
        if not selected:
            self._set_help_text("Инцидент не выбран")
            return
        self._selected_incident_id = selected
        self.action_ack_selected_incident()

    def action_clear_acknowledged_incidents(self) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        self.push_screen(
            ConfirmDialog("Снять подтвержденные инциденты?"),
            lambda confirmed: self._run_after_confirm(confirmed, self._clear_acknowledged_incidents),
        )

    def action_events_page_next(self) -> None:
        if self._current_level == "f6":
            self._audit_page += 1
        else:
            self._events_page += 1
        self._request_refresh_ui()

    def action_events_page_prev(self) -> None:
        if self._current_level == "f6":
            self._audit_page = max(0, self._audit_page - 1)
        else:
            self._events_page = max(0, self._events_page - 1)
        self._request_refresh_ui()

    def _run_after_confirm(self, confirmed: bool, action: Any) -> None:
        if not confirmed:
            self._set_help_text("Отмена")
            return
        try:
            action()
        except Exception:
            logger.debug("orion_v_confirmed_action_failed", exc_info=True)
            self._set_help_text("Ошибка выполнения")

    def action_open_command_mode(self) -> None:
        command = self.query_one("#orionv-command", Input)
        if self._command_mode_open:
            command.focus()
            return
        self._command_mode_open = True
        self.query_one("#orionv-command-shell", Static).add_class("hidden")
        self.query_one("#orionv-command-open", Button).add_class("hidden")
        command.remove_class("hidden")
        command.focus()
        self._set_help_text("Командный режим открыт: введите команду и нажмите Enter, Esc — закрыть.")

    def action_close_command_mode(self) -> None:
        if not self._command_mode_open:
            return
        self._command_mode_open = False
        command = self.query_one("#orionv-command", Input)
        if self.focused is command:
            self.set_focus(None)
        command.value = ""
        command.add_class("hidden")
        self.query_one("#orionv-command-shell", Static).remove_class("hidden")
        self.query_one("#orionv-command-open", Button).remove_class("hidden")
        self._set_help_text("Командный режим закрыт. '/' или ':' — открыть ввод.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw_command = event.value.strip()
        command = raw_command.lower()
        event.input.value = ""
        self.action_close_command_mode()
        if not command:
            return

        is_qiki, qiki_text = self._parse_qiki_intent(raw_command)
        if is_qiki:
            if not qiki_text:
                self._set_help_text("QIKI: пустой запрос. Используйте q: <команда>")
                return
            asyncio.create_task(self._publish_qiki_intent(qiki_text))
            return

        if command in {"q confirm", "q execute"}:
            self._confirm_qiki_pending_action()
            return
        if command in {"q cancel", "q clear"}:
            self._cancel_qiki_pending_action()
            return
        if command in {"review confirm", "review ack", "review acknowledge"}:
            self.action_ack_observation_review()
            return
        if command in {"follow-up hold", "followup hold", "post-review hold", "hold for recheck"}:
            self.action_select_observation_recheck_hold()
            return
        if command in {"resume observation", "resume_observation", "observation resume"}:
            self.action_resume_observation_follow_up()
            return

        if command in {"f1", "f2", "f3", "f4", "f6", "f7"}:
            self.action_show_level(command)
            return
        if command in {"help", "h", "?"}:
            self._show_help()
            return
        if command in {"q", "quit", "exit"}:
            self.action_quit()
            return
        if command in {"inc next", "incident next", "next"}:
            self.action_incident_next()
            return
        if command in {"inc prev", "incident prev", "prev"}:
            self.action_incident_prev()
            return
        if command.startswith("select "):
            target = command.split(" ", 1)[1].strip()
            self._selected_incident_id = target or None
            self._request_refresh_ui()
            return
        if command.startswith("module "):
            self._selected_system_module_slug = command.split(" ", 1)[1].strip() or None
            self._request_refresh_ui()
            return
        if command.startswith("sev "):
            self._set_severity_filter(command.split(" ", 1)[1].strip())
            return
        if command.startswith("subsys "):
            self._set_subsystem_filter(command.split(" ", 1)[1].strip())
            return
        if command.startswith("range "):
            self._set_time_filter(command.split(" ", 1)[1].strip())
            return
        if command in {"page next", "next page"}:
            self.action_events_page_next()
            return
        if command in {"page prev", "prev page"}:
            self.action_events_page_prev()
            return
        if command.startswith("audit "):
            self._set_audit_filter(command.split(" ", 1)[1].strip())
            return
        if command in {"proc list", "procedure list"}:
            names = self._procedure_engine.names()
            self._set_help_text("Procedures: " + (", ".join(names) if names else "none"))
            return
        if command.startswith("proc run "):
            self._start_procedure(command.split(" ", 2)[2].strip())
            return
        if command in {"proc status", "procedure status"}:
            self._set_help_text(self._procedure_status_line())
            return
        if command.startswith("replay on"):
            parts = command.split(" ", 2)
            raw_window = parts[2].strip() if len(parts) > 2 else "900"
            self._start_replay(raw_window)
            return
        if command in {"replay off", "replay live"}:
            self._replay_mode = False
            self._request_refresh_ui()
            self._set_help_text("Анализ истории отключен (режим реального времени)")
            asyncio.create_task(
                self._publish_audit_event(
                    OPERATOR_ACTIONS,
                    {"kind": "replay_mode", "action_type": "replay", "enabled": False, "operator": "orion_v"},
                )
            )
            return
        if command in {"replay status"}:
            self._set_help_text(
                f"Анализ истории {'ВКЛ' if self._replay_mode else 'ВЫКЛ'} | событий={self._replay_store.count()}"
            )
            return
        if self._try_sim_world_command(command):
            return
        if command in {"ack", "acknowledge"}:
            self.action_ack_selected_incident()
            return
        if command.startswith("ack "):
            target = command.split(" ", 1)[1].strip()
            if target:
                self._selected_incident_id = target
            self.action_ack_selected_incident()
            return
        if command in {"clear", "clear acked"}:
            self.action_clear_acknowledged_incidents()
            return

        self._set_help_text(f"Неизвестная команда: {command}. Введите help.")

    @staticmethod
    def _parse_qiki_intent(raw: str) -> tuple[bool, str | None]:
        stripped = (raw or "").strip()
        if stripped.startswith("q:"):
            return True, stripped[2:].strip() or None
        if stripped.startswith("//"):
            return True, stripped[2:].strip() or None
        return False, None

    def _show_help(self) -> None:
        self._set_help_text(
            "Уровни f1/f2/f3/f4/f6/f7 | Инциденты up/down ack clear select <id> | "
            "Фильтры sev <...> subsys <...> range <sec|all> | "
            "Страницы pgup/pgdn page next/prev | Подсистемы module <slug> | "
            "Процедуры proc list|proc run <name>|proc status | "
            "Мир sim.start [скорость]|sim.pause|sim.stop | "
            "Анализ replay on [sec]|replay off|replay status | "
            "Журнал audit <all|actions|procedures|incidents|level|replay> | "
            "QIKI q: <запрос> q confirm q cancel | Review review confirm | Follow-up follow-up hold | "
            "Resume resume observation | q"
        )

    def action_ack_observation_review(self) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Review: нет активной observation-цели")
            return
        follow_up = self._observation_follow_up_contract(objective)
        if follow_up is None or follow_up["status"] != "review_required":
            self._set_help_text("Review: hidden-event follow-up не требует подтверждения")
            return
        self.push_screen(
            ConfirmDialog("Подтвердить review связанного hidden fact?"),
            lambda confirmed: self._run_after_confirm(
                confirmed,
                lambda: asyncio.create_task(self._ack_observation_review()),
            ),
        )

    def action_select_observation_recheck_hold(self) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Follow-up: нет активной observation-цели")
            return
        follow_up = self._observation_follow_up_contract(objective)
        if follow_up is None or follow_up["status"] != "review_completed":
            self._set_help_text("Follow-up: post-review choice пока не открыт")
            return
        self.push_screen(
            ConfirmDialog("Выбрать post-review follow-up: hold for recheck?"),
            lambda confirmed: self._run_after_confirm(
                confirmed,
                lambda: asyncio.create_task(self._select_observation_recheck_hold()),
            ),
        )

    def action_resume_observation_follow_up(self) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Resume: нет активной observation-цели")
            return
        follow_up = self._observation_follow_up_contract(objective)
        if follow_up is None or follow_up["status"] != "hold_for_recheck":
            self._set_help_text("Resume: hold_for_recheck ещё не активен")
            return
        self.push_screen(
            ConfirmDialog("Возобновить observation contour после hold_for_recheck?"),
            lambda confirmed: self._run_after_confirm(
                confirmed,
                lambda: asyncio.create_task(self._resume_observation_follow_up()),
            ),
        )

    async def _ack_observation_review(self) -> None:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Review: нет активной observation-цели")
            return
        follow_up = self._observation_follow_up_contract(objective)
        if (
            follow_up is None
            or follow_up["status"] != "review_required"
            or follow_up["event_type"] != "HIDDEN_EVENT_REVEALED"
        ):
            self._set_help_text("Review: hidden-event follow-up уже закрыт или не найден")
            return
        hidden_event = self._matching_observation_hidden_event(objective)

        payload = {
            "kind": "observation_review_ack",
            "action_type": "review",
            "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "message": (
                "Оператор подтвердил review связанного hidden fact и снял блокировку следующей observation-цели."
            ),
            "summary_ru": (
                "Оператор подтвердил review связанного hidden fact; closure review-контура подтверждён."
            ),
            "summary_en": (
                "The operator acknowledged the linked hidden fact and closed the review loop on the canonical path."
            ),
            "objective_id": str(objective.get("objective_id") or "").strip(),
            "proposal_id": str(objective.get("proposal_id") or "").strip(),
            "request_id": str(objective.get("request_id") or "").strip(),
            "procedure_name": str(objective.get("procedure_name") or hidden_event.get("procedure_name") or "").strip(),
            "target_designator": str(
                objective.get("target_designator") or hidden_event.get("target_designator") or ""
            ).strip(),
            "route_role": str(objective.get("route_role") or hidden_event.get("route_role") or "").strip().lower(),
            "operator": "orion_v",
            "ok": True,
        }
        await self._publish_operator_action(payload)
        self._set_help_text("Review action published: waiting for canonical follow-up update")
        self._request_refresh_ui()

    async def _select_observation_recheck_hold(self) -> None:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Follow-up: нет активной observation-цели")
            return
        hidden_event = self._matching_observation_hidden_event(objective)
        follow_up = self._observation_follow_up_contract(objective)
        if follow_up is None or follow_up["status"] != "review_completed":
            self._set_help_text("Follow-up: post-review choice ещё не доступен")
            return

        payload = {
            "kind": "observation_post_review_choice",
            "action_type": "follow_up",
            "event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "message": (
                "Оператор выбрал post-review hold for recheck: "
                "следующая observation-петля должна пройти через осторожный recheck."
            ),
            "summary_ru": (
                "Выбран post-review hold for recheck; следующий observation contour переведён в осторожный recheck."
            ),
            "summary_en": (
                "The operator selected post-review hold for recheck; "
                "the next observation contour now requires a cautious recheck."
            ),
            "objective_id": str(objective.get("objective_id") or "").strip(),
            "proposal_id": str(objective.get("proposal_id") or "").strip(),
            "request_id": str(objective.get("request_id") or "").strip(),
            "procedure_name": str(objective.get("procedure_name") or hidden_event.get("procedure_name") or "").strip(),
            "target_designator": str(
                objective.get("target_designator") or hidden_event.get("target_designator") or ""
            ).strip(),
            "route_role": str(objective.get("route_role") or hidden_event.get("route_role") or "").strip().lower(),
            "operator": "orion_v",
            "ok": True,
        }
        await self._publish_operator_action(payload)
        self._set_help_text("Post-review action published: waiting for canonical follow-up update")
        self._request_refresh_ui()

    async def _resume_observation_follow_up(self) -> None:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            self._set_help_text("Resume: нет активной observation-цели")
            return
        follow_up = self._observation_follow_up_contract(objective)
        if follow_up is None or follow_up["status"] != "hold_for_recheck":
            self._set_help_text("Resume: hold_for_recheck уже закрыт или не найден")
            return

        target_designator = str(objective.get("target_designator") or "").strip() or "the same target"
        payload = {
            "kind": "observation_resume_action",
            "action_type": "resume",
            "event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "message": (
                "Оператор подтвердил resume observation: hold_for_recheck закрыт, следующий шаг — один cautious "
                "safe observation для той же цели."
            ),
            "summary_ru": (
                "Выбран resume observation: hold_for_recheck закрыт, observation contour снова может идти через "
                "один cautious safe observation."
            ),
            "summary_en": (
                "The operator selected resume observation: hold_for_recheck is closed, and the contour may continue "
                "through one cautious safe observation."
            ),
            "objective_id": str(objective.get("objective_id") or "").strip(),
            "proposal_id": str(objective.get("proposal_id") or "").strip(),
            "request_id": str(objective.get("request_id") or "").strip(),
            "procedure_name": str(objective.get("procedure_name") or "").strip(),
            "target_designator": target_designator,
            "route_role": str(objective.get("route_role") or "").strip().lower(),
            "operator": "orion_v",
            "ok": True,
        }
        await self._publish_operator_action(payload)
        self._set_help_text("Resume action published: waiting for canonical follow-up update")
        self._request_refresh_ui()

    def _apply_observation_follow_up_to_qiki(self, updated_follow_up: dict[str, str] | None) -> None:
        if self._qiki_last_response is None or updated_follow_up is None:
            return
        legality = self._qiki_last_response.legality
        if legality is not None:
            legality = legality.model_copy(
                update={
                    "allowed_when": BilingualText(
                        en=updated_follow_up["allowed_when_en"],
                        ru=updated_follow_up["allowed_when_ru"],
                    )
                }
            )
        telemetry_confirmation = None
        if self._qiki_last_response.consequence is not None:
            telemetry_confirmation = self._qiki_last_response.consequence.telemetry_confirmation
        self._qiki_last_response = self._qiki_last_response.model_copy(
            update={
                "consequence": QikiConsequenceV1(
                    status="confirmed",
                    summary=BilingualText(
                        en=updated_follow_up["summary_en"],
                        ru=updated_follow_up["summary_ru"],
                    ),
                    telemetry_confirmation=telemetry_confirmation,
                ),
                "legality": legality,
                "proposals": [],
            }
        )

    def _start_replay(self, raw_window: str) -> None:
        try:
            window_s = int(raw_window or "900")
        except ValueError:
            self._set_help_text("replay on [секунды]")
            return
        if window_s <= 0:
            self._set_help_text("Окно анализа истории должно быть > 0")
            return
        asyncio.create_task(self._load_replay(window_s))
        self._set_help_text(f"Загрузка анализа истории за последние {window_s}с ...")

    async def _load_replay(self, window_s: int) -> None:
        history = await self._nats_client.fetch_events_history(limit=self._events_store.max_events)
        replay_store = BoundedEventsStore(max_events=self._events_store.max_events)
        since_epoch = now_epoch_s() - float(window_s)
        for event in history:
            replay_store.append(event)
        self._replay_store = replay_store
        self._replay_mode = True
        self._filter_window_sec = window_s
        # Force page reset so replay opens from first page.
        self._events_page = 0
        self._set_help_text(
            f"Анализ истории включен ({window_s}с), событий={self._replay_store.query_count(since_epoch_s=since_epoch)}"
        )
        await self._publish_audit_event(
            OPERATOR_ACTIONS,
            {
                "kind": "replay_mode",
                "action_type": "replay",
                "enabled": True,
                "window_seconds": window_s,
                "operator": "orion_v",
            },
        )
        self._request_refresh_ui()

    def _procedure_status_line(self) -> str:
        st = self._procedure_engine.state
        if st.running:
            return f"Процедура {st.procedure_name}: шаг {st.step_index}/{st.total_steps} выполняется"
        if st.status == "failed":
            return f"Процедура {st.procedure_name}: Ошибка выполнения ({st.last_error})"
        if st.status == "ok":
            return f"Процедура {st.procedure_name}: {tr('ok')}"
        return "Процедура: ожидание"

    def _start_procedure(self, name: str) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        if not name:
            self._set_help_text("Использование: proc run <имя>")
            return
        definition = self._procedure_engine.get(name)
        if definition is None:
            self._set_help_text(f"Неизвестная процедура: {name}")
            return
        if self._procedure_task and not self._procedure_task.done():
            self._set_help_text("Процедура уже выполняется")
            return
        self._last_proc_start_mono = time.monotonic()
        self._procedure_task = asyncio.create_task(self._run_procedure(definition.name))
        self._set_last_command_loop_state("procedure-started", f"Procedure queued: {definition.name}")
        self._set_help_text(f"Запустить процедуру: {definition.name}")

    async def _run_procedure(self, name: str) -> None:
        definition = self._procedure_engine.get(name)
        if definition is None:
            return
        try:
            await self._publish_audit_event(
                OPERATOR_PROCEDURES,
                {
                    "kind": "procedure_start",
                    "action_type": "procedures",
                    "procedure": name,
                    "operator": "orion_v",
                },
            )
            await self._procedure_engine.run(
                definition,
                publish_command=self._publish_sim_command,
                wait_ack=self._wait_for_ack,
                publish_audit=self._publish_procedure_audit,
            )
        except Exception:
            logger.debug("orion_v_procedure_run_failed", exc_info=True)
        finally:
            elapsed_ms = 0.0
            if self._last_proc_start_mono is not None:
                elapsed_ms = max(0.0, (time.monotonic() - self._last_proc_start_mono) * 1000.0)
                self._metrics["procedure_latency_ms"] = elapsed_ms
                self._last_proc_start_mono = None
            await self._publish_audit_event(
                OPERATOR_PROCEDURES,
                {
                    "kind": "procedure_finish",
                    "action_type": "procedures",
                    "procedure": name,
                    "status": self._procedure_engine.state.status,
                    "ok": self._procedure_engine.state.status == "ok",
                    "latency_ms": elapsed_ms,
                    "operator": "orion_v",
                },
            )
            self._request_refresh_ui()

    def _try_sim_world_command(self, command: str) -> bool:
        """Operator world-control commands: sim.start [speed] / sim.pause / sim.stop.

        Vocabulary parity with the legacy console (simulation.start / симуляция.старт);
        publishing goes through _publish_sim_command — the same ACK-awaited
        CommandMessage path procedures use (ACK != effect confirmation).
        Returns True when the command was consumed (even on argument errors).
        """
        parts = command.split()
        if not parts:
            return False
        aliases = {
            "sim.start": "sim.start",
            "simulation.start": "sim.start",
            "симуляция.старт": "sim.start",
            "sim.pause": "sim.pause",
            "simulation.pause": "sim.pause",
            "симуляция.пауза": "sim.pause",
            "sim.stop": "sim.stop",
            "simulation.stop": "sim.stop",
            "симуляция.стоп": "sim.stop",
        }
        name = aliases.get(parts[0])
        if name is None:
            return False
        args = parts[1:]
        parameters: dict[str, Any] = {}
        if name == "sim.start" and args:
            try:
                speed = float(args[0].replace(",", "."))
            except ValueError:
                self._set_help_text(f"Мир: скорость должна быть числом, получено «{args[0]}»")
                return True
            if speed <= 0:
                self._set_help_text("Мир: скорость должна быть больше нуля")
                return True
            parameters["speed"] = speed
        elif args:
            self._set_help_text(f"Мир: {name} не принимает аргументов")
            return True
        asyncio.create_task(self._publish_sim_command(name, parameters))
        self._set_help_text(f"Мир: {name} отправлена — ждём ACK (ACK ≠ эффект)")
        return True

    async def _publish_sim_command(self, command_name: str, parameters: dict[str, Any] | None = None) -> None:
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return
        request_id = uuid4()
        request_id_str = str(request_id)
        self._control_acks.clear()
        self._pending_ack_command_id = request_id_str
        self._ack_wait_started_mono = time.monotonic()
        cmd = CommandMessage(
            command_name=command_name,
            parameters=parameters or {},
            metadata=MessageMetadata(
                correlation_id=request_id,
                message_type="control_command",
                source="operator_console.orion_v",
                destination="q_sim_service",
            ),
        )
        self._set_last_command_loop_state("awaiting_ack", f"Command sent: {command_name}")
        await self._nats_client.publish_command(COMMANDS_CONTROL, cmd.model_dump(mode="json"))

    async def _wait_for_ack(self, expected_ack: str, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        expected = expected_ack.strip().lower()
        expected_command_id = self._pending_ack_command_id
        wait_started_mono = self._ack_wait_started_mono or time.monotonic()
        while time.monotonic() < deadline:
            for envelope in reversed(self._control_acks):
                payload = envelope.get("data")
                if not isinstance(payload, dict):
                    continue
                ack_received_mono = envelope.get("_received_mono")
                if isinstance(ack_received_mono, (int, float)) and (
                    float(ack_received_mono) < wait_started_mono or float(ack_received_mono) > deadline
                ):
                    continue
                ack_command_id = str(
                    payload.get("command_id") or payload.get("request_id") or payload.get("requestId") or ""
                ).strip()
                if expected_command_id and ack_command_id != expected_command_id:
                    continue
                if not _ack_payload_success(payload):
                    continue
                kind = str(payload.get("kind") or "").strip().lower()
                command_name = str(((payload.get("payload") or {}).get("command_name"))).strip().lower()
                status = str(((payload.get("payload") or {}).get("status"))).strip().lower()
                if expected in {kind, command_name, status}:
                    return True
            await asyncio.sleep(0.1)
        return False

    def _set_severity_filter(self, raw: str) -> None:
        token = raw.strip().upper()
        if token in {"", "ALL", "*"}:
            self._filter_severities.clear()
            self._events_page = 0
            self._request_refresh_ui()
            return
        allowed = {"INFO", "WARN", "ERROR", "A", "C"}
        selected: set[str] = set()
        for part in token.replace(",", " ").split():
            part_upper = part.upper()
            if part_upper in {"WARNING"}:
                part_upper = "WARN"
            if part_upper in {"CRIT", "CRITICAL"}:
                part_upper = "C"
            if part_upper in {"ALARM"}:
                part_upper = "A"
            if part_upper not in allowed:
                self._set_help_text(f"Неизвестный уровень серьезности: {part}")
                return
            if part_upper == "ERROR":
                part_upper = "C"
            selected.add(part_upper)
        self._filter_severities = selected
        self._events_page = 0
        self._request_refresh_ui()

    def _set_subsystem_filter(self, raw: str) -> None:
        token = raw.strip().lower()
        if token in {"", "all", "*"}:
            self._filter_subsystem = None
        else:
            self._filter_subsystem = token
        self._events_page = 0
        self._request_refresh_ui()

    def _set_time_filter(self, raw: str) -> None:
        token = raw.strip().lower()
        if token in {"", "all", "*", "none"}:
            self._filter_window_sec = None
            self._events_page = 0
            self._request_refresh_ui()
            return
        try:
            window = int(token)
        except ValueError:
            self._set_help_text("range ожидает целые секунды или 'all'")
            return
        if window <= 0:
            self._set_help_text("range должно быть > 0")
            return
        self._filter_window_sec = window
        self._events_page = 0
        self._request_refresh_ui()

    def _set_audit_filter(self, raw: str) -> None:
        token = raw.strip().lower()
        if token in {"", "all", "*"}:
            self._audit_filter_type = None
            self._audit_page = 0
            self._request_refresh_ui()
            return
        aliases = {
            "action": "actions",
            "actions": "actions",
            "procedure": "procedures",
            "procedures": "procedures",
            "incident": "incidents",
            "incidents": "incidents",
            "level": "level",
            "levels": "level",
            "replay": "replay",
        }
        resolved = aliases.get(token)
        if not resolved:
            self._set_help_text("audit <all|actions|procedures|incidents|level|replay>")
            return
        self._audit_filter_type = resolved
        self._audit_page = 0
        self._request_refresh_ui()

    def _refresh_runtime_metrics(self) -> None:
        now_mono = time.monotonic()
        cutoff = now_mono - 1.0
        while self._event_timestamps and self._event_timestamps[0] < cutoff:
            self._event_timestamps.popleft()
        cpu_usage_us, mem_mb = _read_container_metrics()
        cpu_pct = 0.0
        if self._last_cpu_usage_us is not None and self._last_cpu_read_mono is not None:
            delta_usage_us = max(0.0, cpu_usage_us - self._last_cpu_usage_us)
            delta_wall_s = max(0.001, now_mono - self._last_cpu_read_mono)
            cpu_pct = max(0.0, min(100.0, (delta_usage_us / 1_000_000.0) / delta_wall_s * 100.0))
        self._last_cpu_usage_us = cpu_usage_us
        self._last_cpu_read_mono = now_mono
        self._metrics.update(
            {
                "events_per_sec": float(len(self._event_timestamps)),
                "queue_depth": int(self._events_store.count()),
                "bounded_store_size": int(self._events_store.count()),
                "bounded_store_limit": int(self._events_store.max_events),
                "cpu_percent": float(cpu_pct),
                "memory_mb": float(mem_mb),
                "active_subscriptions": int(self._nats_client.active_subscriptions),
                "nats_state": self._nats_state,
                "replay_mode": bool(self._replay_mode),
            }
        )
        self._request_refresh_ui()

    def _set_help_text(self, text: str) -> None:
        normalized = str(text).strip()
        if normalized:
            if not self._console_history or self._console_history[-1] != normalized:
                self._console_history.append(normalized)
            self._help_text = normalized
        if self.is_mounted:
            self._request_refresh_ui()

    def _set_last_command_loop_state(self, status: str, summary: str | None = None) -> None:
        normalized_status = str(status or "idle").strip().lower() or "idle"
        self._last_command_status = normalized_status
        if summary is not None:
            text = str(summary).strip()
            if text:
                self._last_command_summary = text

    def _build_qiki_chat_request(self, text: str) -> QikiChatRequestV1:
        freshness = TelemetryFreshness.FRESH if self._telemetry else TelemetryFreshness.UNKNOWN
        return QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(time.time() * 1000),
            mode_hint=QikiMode.FACTORY,
            input=QikiChatInput(text=text, lang_hint="auto"),
            ui_context=UiContext(
                screen=self.LEVEL_META[self._current_level]["label"],
                selection=SelectionContext(
                    kind="incident" if self._selected_incident_id else "none",
                    id=self._selected_incident_id,
                ),
            ),
            system_context=SystemContext(telemetry_freshness=freshness),
        )

    async def _publish_qiki_intent(self, text: str) -> None:
        normalized_text = " ".join(str(text or "").strip().lower().split())
        follow_up = self._observation_follow_up_contract(self._active_observation_objective)
        if (
            follow_up is not None
            and follow_up["status"] == "hold_for_recheck"
            and normalized_text.startswith(("safe observation", "slow observation"))
        ):
            target_designator = str((self._active_observation_objective or {}).get("target_designator") or "").strip()
            target_suffix = f" for {target_designator}" if target_designator else ""
            self._set_help_text(
                "Observation contour is still on hold_for_recheck: issue resume observation before the next "
                f"observation command{target_suffix}."
            )
            return
        req = self._build_qiki_chat_request(text)
        self._qiki_pending[str(req.request_id)] = (time.time(), text)
        self._set_last_command_loop_state("awaiting_qiki", f"QIKI intent sent: {text}")
        self._set_help_text(f"QIKI intent отправлен: {text}")
        try:
            await self._nats_client.publish_command(QIKI_INTENTS, req.model_dump(mode="json"))
        except Exception:
            logger.debug("orion_v_publish_qiki_intent_failed", exc_info=True)
            self._qiki_pending.pop(str(req.request_id), None)
            self._set_last_command_loop_state("failed", "QIKI intent publish failed")
            self._set_help_text("QIKI intent: ошибка публикации")

    def _extract_qiki_pending_action(self, response: QikiChatResponseV1) -> dict[str, Any] | None:
        for proposal in response.proposals:
            for action in proposal.proposed_actions:
                return {
                    "action_kind": action.kind,
                    "proposal_id": proposal.proposal_id,
                    "title_ru": proposal.title.ru,
                    "title_en": proposal.title.en,
                    "subject": action.subject,
                    "name": action.name,
                    "parameters": dict(action.parameters or {}),
                    "dry_run": bool(action.dry_run),
                }
        return None

    def _build_qiki_plan_preview_lines(self) -> list[str]:
        action = self._qiki_pending_action
        if action is None:
            return []
        if str(action.get("action_kind") or "") != "ORION_PROCEDURE":
            return []
        definition = self._procedure_engine.get(str(action.get("name") or "").strip())
        if definition is None:
            return []
        return [
            f"{idx}. {self._format_procedure_step(step.command, step.parameters)} -> ack {step.expected_ack}"
            for idx, step in enumerate(definition.steps, start=1)
        ]

    @staticmethod
    def _format_procedure_step(command: str, parameters: dict[str, Any] | None) -> str:
        if not isinstance(parameters, dict) or not parameters:
            return command
        rendered_params = " ".join(f"{key}={value}" for key, value in sorted(parameters.items()))
        return f"{command} {rendered_params}".strip()

    def _cancel_qiki_pending_action(self) -> None:
        if self._qiki_pending_action is None:
            self._set_help_text("QIKI: нет ожидающего подтверждения")
            return
        self._qiki_pending_action = None
        self._set_last_command_loop_state("cancelled", "Pending QIKI action cancelled by operator")
        asyncio.create_task(
            self._publish_observation_objective_update(
                status="cancelled",
                summary_en="The prepared observation objective was cancelled by the operator.",
                summary_ru="Подготовленная observation-цель отменена оператором.",
                reason_code="OBJECTIVE_CANCELLED_BY_OPERATOR",
            )
        )
        if self._qiki_last_response is not None:
            self._qiki_last_response = self._qiki_last_response.model_copy(
                update={
                    "consequence": QikiConsequenceV1(
                        status="not_sent",
                        summary=BilingualText(
                            en="The prepared QIKI action was cancelled by the operator.",
                            ru="Подготовленное действие QIKI отменено оператором.",
                        ),
                        telemetry_confirmation=BilingualText(
                            en="No control-bus command was emitted after the cancellation.",
                            ru="После отмены команда на control bus не отправлялась.",
                        ),
                    ),
                    "proposals": [],
                }
            )
        self._set_help_text("QIKI: подтверждение действия снято")
        self._request_refresh_ui()

    def _matching_active_observation_objective(self, procedure_name: str | None = None) -> dict[str, Any] | None:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            return None
        if str(objective.get("objective_type") or "observation").strip().lower() != "observation":
            return None
        if procedure_name is not None:
            current_procedure = str(objective.get("procedure_name") or "").strip()
            follow_up_status = str(objective.get("follow_up_status") or "").strip().lower()
            if current_procedure and current_procedure != procedure_name and not (
                follow_up_status == "resume_observation"
                and current_procedure == "safe_pause_slow_resume"
                and procedure_name == "safe_pause_resume"
            ):
                return None
        return objective

    def _objective_identity_values(self, objective: dict[str, Any] | None) -> set[str]:
        if not isinstance(objective, dict):
            return set()
        primary = {
            value
            for value in (
                str(objective.get("objective_id") or "").strip(),
                str(objective.get("proposal_id") or "").strip(),
                str(objective.get("request_id") or "").strip(),
            )
            if value
        }
        if primary:
            return primary
        return {
            value
            for value in (
                str(objective.get("procedure_name") or "").strip(),
                str(objective.get("target_designator") or "").strip(),
            )
            if value
        }

    def _event_identity_values(self, payload: dict[str, Any] | None) -> set[str]:
        if not isinstance(payload, dict):
            return set()
        primary = {
            value
            for value in (
                str(payload.get("objective_id") or "").strip(),
                str(payload.get("proposal_id") or "").strip(),
                str(payload.get("request_id") or payload.get("requestId") or "").strip(),
            )
            if value
        }
        if primary:
            return primary
        return {
            value
            for value in (
                str(payload.get("procedure_name") or payload.get("procedure") or "").strip(),
                str(payload.get("target_designator") or payload.get("target") or "").strip(),
            )
            if value
        }

    def _matching_observation_hidden_event(
        self,
        objective: dict[str, Any] | None,
        source_store: BoundedEventsStore | None = None,
    ) -> dict[str, Any] | None:
        identities = self._objective_identity_values(objective)
        if not identities:
            return None
        store = source_store or self._events_store
        for event in reversed(store.last(40)):
            if not isinstance(event, dict):
                continue
            if str(event.get("subject") or "").strip() != EVENTS_AUDIT:
                continue
            payload = event.get("data")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("event_type") or "").strip() != "HIDDEN_EVENT_REVEALED":
                continue
            if identities.intersection(self._event_identity_values(payload)):
                return payload
        return None

    def _matching_observation_review_ack(
        self,
        objective: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        identities = self._objective_identity_values(objective)
        if not identities:
            return None
        for store in (self._audit_store, self._events_store):
            for event in reversed(store.last(40)):
                if not isinstance(event, dict):
                    continue
                payload = event.get("data")
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("event_type") or "").strip() != "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED":
                    continue
                if identities.intersection(self._event_identity_values(payload)):
                    return payload
        return None

    def _matching_observation_post_review_hold(
        self,
        objective: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        identities = self._objective_identity_values(objective)
        if not identities:
            return None
        for store in (self._audit_store, self._events_store):
            for event in reversed(store.last(40)):
                if not isinstance(event, dict):
                    continue
                payload = event.get("data")
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("event_type") or "").strip() != "HIDDEN_EVENT_RECHECK_HOLD_SELECTED":
                    continue
                if identities.intersection(self._event_identity_values(payload)):
                    return payload
        return None

    def _observation_follow_up_contract(self, objective: dict[str, Any] | None) -> dict[str, str] | None:
        if not isinstance(objective, dict):
            return None
        status = str(objective.get("follow_up_status") or "").strip().lower()
        if not status:
            return None
        reason_code = str(objective.get("follow_up_reason_code") or "").strip()
        event_type = str(objective.get("follow_up_event_type") or "").strip()
        summary_en = str(objective.get("follow_up_summary_en") or "").strip()
        summary_ru = str(objective.get("follow_up_summary_ru") or "").strip()
        allowed_when_en = str(objective.get("follow_up_allowed_when_en") or "").strip()
        allowed_when_ru = str(objective.get("follow_up_allowed_when_ru") or "").strip()
        if not all((reason_code, event_type, summary_en, summary_ru, allowed_when_en, allowed_when_ru)):
            return None
        return {
            "status": status,
            "reason_code": reason_code,
            "event_type": event_type,
            "summary_en": summary_en,
            "summary_ru": summary_ru,
            "allowed_when_en": allowed_when_en,
            "allowed_when_ru": allowed_when_ru,
        }

    def _observation_result_contract(self, objective: dict[str, Any] | None) -> dict[str, str] | None:
        if not isinstance(objective, dict):
            return None
        status = str(objective.get("observation_result_status") or "").strip().lower()
        reason_code = str(objective.get("observation_result_reason_code") or "").strip()
        summary_en = str(objective.get("observation_result_summary_en") or "").strip()
        summary_ru = str(objective.get("observation_result_summary_ru") or "").strip()
        if not all((status, reason_code, summary_en, summary_ru)):
            return None
        return {
            "status": status,
            "reason_code": reason_code,
            "summary_en": summary_en,
            "summary_ru": summary_ru,
        }

    def _coerce_observation_track_snapshot(self, parameters: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(parameters, dict):
            return None
        track_id = str(parameters.get("observation_track_id") or "").strip()
        track_label = str(parameters.get("observation_track_label") or "").strip()
        public_track_id = str(parameters.get("public_track_id") or "").strip()
        public_track_label = str(parameters.get("public_track_label") or "").strip()
        if not any((track_id, track_label, public_track_id, public_track_label)):
            return None
        snapshot: dict[str, Any] = {
            "track_id": track_id or None,
            "track_label": track_label or None,
            "public_track_id": public_track_id or None,
            "public_track_label": public_track_label or None,
        }
        track_range_m = parameters.get("observation_track_range_m")
        if isinstance(track_range_m, (int, float)):
            snapshot["track_range_m"] = float(track_range_m)
        track_quality = parameters.get("observation_track_quality")
        if isinstance(track_quality, (int, float)):
            snapshot["track_quality"] = float(track_quality)
        return snapshot

    @staticmethod
    def _track_public_label(track: dict[str, Any] | None) -> str:
        if not isinstance(track, dict):
            return ""
        return str(track.get("transponder_id") or track.get("id") or track.get("callsign") or "").strip()

    def _find_live_public_track(
        self,
        *,
        qcore_track_id: str | None = None,
        public_track_id: str | None = None,
        target_designator: str | None = None,
        fallback_label: str | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        qcore_id = str(qcore_track_id or "").strip()
        if qcore_id:
            qcore_track = self._latest_radar_tracks.get(qcore_id)
            if isinstance(qcore_track, dict):
                return qcore_id, qcore_track

        preferred_id = str(public_track_id or "").strip()
        if preferred_id:
            preferred_track = self._latest_radar_tracks.get(preferred_id)
            if isinstance(preferred_track, dict):
                return preferred_id, preferred_track

        needles = {
            str(target_designator or "").strip().upper(),
            str(fallback_label or "").strip().upper(),
        }
        needles.discard("")
        if not needles:
            return "", None

        for track_id, track in self._latest_radar_tracks.items():
            if not isinstance(track, dict):
                continue
            if self._track_public_label(track).upper() in needles:
                return str(track_id), track
        return "", None

    def _enrich_active_observation_with_live_public_track(self) -> None:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            return
        public_track_id, live_track = self._find_live_public_track(
            qcore_track_id=str(objective.get("track_id") or "").strip(),
            public_track_id=str(objective.get("public_track_id") or "").strip(),
            target_designator=str(objective.get("target_designator") or "").strip(),
            fallback_label=str(objective.get("track_label") or "").strip(),
        )
        if not public_track_id or not isinstance(live_track, dict):
            return

        updated_objective = dict(objective)
        updated_objective["public_track_id"] = public_track_id
        public_track_label = self._track_public_label(live_track)
        updated_objective["track_visible"] = True
        if public_track_label:
            updated_objective["public_track_label"] = public_track_label
            follow_up_status = str(objective.get("follow_up_status") or "").strip().lower()
            if follow_up_status != "resume_observation" or not str(objective.get("track_label") or "").strip():
                updated_objective["track_label"] = public_track_label
        track_range_m = live_track.get("range_m")
        if isinstance(track_range_m, (int, float)) and not isinstance(track_range_m, bool):
            updated_objective["track_range_m"] = float(track_range_m)
        track_quality = live_track.get("quality")
        if isinstance(track_quality, (int, float)) and not isinstance(track_quality, bool):
            updated_objective["track_quality"] = float(track_quality)
        self._active_observation_objective = updated_objective

        if isinstance(self._qiki_pending_action, dict):
            parameters = dict(self._qiki_pending_action.get("parameters") or {})
            parameters["public_track_id"] = public_track_id
            if public_track_label:
                parameters["public_track_label"] = public_track_label
            self._qiki_pending_action = {**self._qiki_pending_action, "parameters": parameters}

    def _live_observation_track_snapshot(
        self,
        objective: dict[str, Any] | None,
        *,
        fallback_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        fallback_snapshot = self._coerce_observation_track_snapshot(fallback_parameters)
        objective_id = str((objective or {}).get("objective_id") or "").strip() if isinstance(objective, dict) else ""
        request_id = str((objective or {}).get("request_id") or "").strip() if isinstance(objective, dict) else ""
        target_designator = (
            str((objective or {}).get("target_designator") or "").strip() if isinstance(objective, dict) else ""
        )
        objective_track_id = str((objective or {}).get("track_id") or "").strip() if isinstance(objective, dict) else ""
        objective_track_label = (
            str((objective or {}).get("track_label") or "").strip() if isinstance(objective, dict) else ""
        )
        objective_public_track_id = (
            str((objective or {}).get("public_track_id") or "").strip() if isinstance(objective, dict) else ""
        )
        objective_public_track_label = (
            str((objective or {}).get("public_track_label") or "").strip() if isinstance(objective, dict) else ""
        )
        fallback_track_id = str((fallback_snapshot or {}).get("track_id") or "").strip()
        fallback_track_label = str((fallback_snapshot or {}).get("track_label") or "").strip()
        fallback_public_track_id = str((fallback_snapshot or {}).get("public_track_id") or "").strip()
        fallback_public_track_label = str((fallback_snapshot or {}).get("public_track_label") or "").strip()
        qcore_track_id = objective_track_id or fallback_track_id
        qcore_track_label = objective_track_label or fallback_track_label
        public_track_id, live_track = self._find_live_public_track(
            qcore_track_id=qcore_track_id,
            public_track_id=objective_public_track_id or fallback_public_track_id,
            target_designator=target_designator,
            fallback_label=qcore_track_label or objective_public_track_label or fallback_public_track_label,
        )
        if not qcore_track_id and not public_track_id:
            logger.info(
                "Resume live snapshot: objective_id=%s request_id=%s target=%s previous_track_id=%s previous_label=%s "
                "qcore_track_id=%s qcore_label=%s public_track_id=%s public_label=%s "
                "live_track_id= missing live_label= missing source=fallback_missing_track_id "
                "source_ts= missing freshness_s= missing label_source=fallback_parameters",
                objective_id,
                request_id,
                target_designator,
                objective_track_id,
                objective_track_label,
                fallback_track_id,
                fallback_track_label,
                fallback_public_track_id,
                fallback_public_track_label,
            )
            return fallback_snapshot
        if not isinstance(live_track, dict):
            logger.info(
                "Resume live snapshot: objective_id=%s request_id=%s target=%s previous_track_id=%s previous_label=%s "
                "qcore_track_id=%s qcore_label=%s public_track_id=%s public_label=%s "
                "live_track_id=%s live_label= missing source=fallback_live_track_missing "
                "source_ts= missing freshness_s= missing label_source=fallback_parameters",
                objective_id,
                request_id,
                target_designator,
                objective_track_id,
                objective_track_label,
                fallback_track_id,
                fallback_track_label,
                objective_public_track_id or fallback_public_track_id,
                objective_public_track_label or fallback_public_track_label,
                public_track_id or qcore_track_id,
            )
            return fallback_snapshot
        track_label = self._track_public_label(live_track)
        source_timestamp = live_track.get("_orion_source_timestamp_unix_s")
        if not isinstance(source_timestamp, (int, float)) or isinstance(source_timestamp, bool):
            source_timestamp = _extract_event_timestamp(live_track, None)
        freshness_seconds = None
        if isinstance(source_timestamp, (int, float)) and not isinstance(source_timestamp, bool):
            freshness_seconds = max(0.0, time.time() - float(source_timestamp))
        label_source = "live_cache"
        if not track_label:
            label_source = "fallback_parameters"
        snapshot: dict[str, Any] = {
            "track_id": qcore_track_id or public_track_id or None,
            "track_label": track_label or qcore_track_label or None,
            "public_track_id": public_track_id or None,
            "public_track_label": track_label or objective_public_track_label or fallback_public_track_label or None,
            "source": "live_cache",
            "label_source": label_source,
        }
        track_range_m = live_track.get("range_m")
        if isinstance(track_range_m, (int, float)):
            snapshot["track_range_m"] = float(track_range_m)
        elif isinstance(fallback_snapshot, dict) and "track_range_m" in fallback_snapshot:
            snapshot["track_range_m"] = fallback_snapshot["track_range_m"]
        track_quality = live_track.get("quality")
        if isinstance(track_quality, (int, float)):
            snapshot["track_quality"] = float(track_quality)
        elif isinstance(fallback_snapshot, dict) and "track_quality" in fallback_snapshot:
            snapshot["track_quality"] = fallback_snapshot["track_quality"]
        if isinstance(source_timestamp, (int, float)) and not isinstance(source_timestamp, bool):
            snapshot["source_timestamp_unix_s"] = float(source_timestamp)
        if isinstance(freshness_seconds, (int, float)):
            snapshot["freshness_s"] = float(freshness_seconds)
        logger.info(
            "Resume live snapshot: objective_id=%s request_id=%s target=%s previous_track_id=%s previous_label=%s "
            "qcore_track_id=%s qcore_label=%s public_track_id=%s public_label=%s "
            "live_track_id=%s live_label=%s source=live_cache source_ts=%s "
            "freshness_s=%s label_source=%s",
            objective_id,
            request_id,
            target_designator,
            objective_track_id,
            objective_track_label,
            qcore_track_id,
            qcore_track_label,
            public_track_id or objective_public_track_id or fallback_public_track_id,
            track_label or objective_public_track_label or fallback_public_track_label,
            public_track_id or qcore_track_id,
            track_label,
            (
                f"{float(source_timestamp):.3f}"
                if isinstance(source_timestamp, (int, float)) and not isinstance(source_timestamp, bool)
                else "missing"
            ),
            (
                f"{float(freshness_seconds):.3f}"
                if isinstance(freshness_seconds, (int, float))
                else "missing"
            ),
            label_source,
        )
        return snapshot

    def _build_resume_observation_result(
        self,
        objective: dict[str, Any] | None,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, str] | None:
        if not isinstance(objective, dict):
            return None
        if str(objective.get("follow_up_status") or "").strip().lower() != "resume_observation":
            return None
        target_text = str(objective.get("target_designator") or "").strip() or "observation target"
        previous_track_id = str(objective.get("track_id") or "").strip()
        previous_track_label = str(objective.get("track_label") or "").strip()
        previous_public_track_id = str(objective.get("public_track_id") or "").strip()
        previous_public_track_label = str(objective.get("public_track_label") or "").strip()
        resumed_track = self._coerce_observation_track_snapshot(parameters)
        resumed_track_id = str((resumed_track or {}).get("track_id") or "").strip()
        resumed_track_label = str((resumed_track or {}).get("track_label") or "").strip()
        resumed_public_track_id = str((resumed_track or {}).get("public_track_id") or "").strip()
        resumed_public_track_label = str((resumed_track or {}).get("public_track_label") or "").strip()
        comparison_source = str((resumed_track or {}).get("source") or "parameters").strip() or "parameters"
        comparison_label_source = str((resumed_track or {}).get("label_source") or comparison_source).strip()
        comparison_source_timestamp = (resumed_track or {}).get("source_timestamp_unix_s")
        comparison_freshness = (resumed_track or {}).get("freshness_s")
        if (
            previous_track_id
            and resumed_track_id
            and previous_track_id == resumed_track_id
            and previous_track_label
            and resumed_track_label
            and previous_track_label != resumed_track_label
        ):
            result_candidate = "signature_changed"
            fallback_reason = "not_applicable"
        elif not previous_track_id:
            result_candidate = "reconfirmed"
            fallback_reason = "missing_previous_track_id"
        elif not resumed_track_id:
            result_candidate = "reconfirmed"
            fallback_reason = "missing_comparison_track_id"
        elif previous_track_id != resumed_track_id:
            result_candidate = "reconfirmed"
            fallback_reason = "track_id_mismatch"
        elif not previous_track_label:
            result_candidate = "reconfirmed"
            fallback_reason = "missing_previous_label"
        elif not resumed_track_label:
            result_candidate = "reconfirmed"
            fallback_reason = "missing_comparison_label"
        else:
            result_candidate = "reconfirmed"
            fallback_reason = "label_unchanged"
        logger.info(
            "Resume comparison: objective_id=%s request_id=%s target=%s previous_track_id=%s previous_label=%s "
            "previous_public_track_id=%s previous_public_label=%s comparison_track_id=%s comparison_label=%s "
            "comparison_public_track_id=%s comparison_public_label=%s comparison_source=%s comparison_label_source=%s "
            "comparison_source_ts=%s comparison_freshness_s=%s result_candidate=%s fallback_reason=%s",
            str(objective.get("objective_id") or "").strip(),
            str(objective.get("request_id") or "").strip(),
            target_text,
            previous_track_id,
            previous_track_label,
            previous_public_track_id,
            previous_public_track_label,
            resumed_track_id,
            resumed_track_label,
            resumed_public_track_id,
            resumed_public_track_label,
            comparison_source,
            comparison_label_source,
            (
                f"{float(comparison_source_timestamp):.3f}"
                if isinstance(comparison_source_timestamp, (int, float))
                and not isinstance(comparison_source_timestamp, bool)
                else "missing"
            ),
            (
                f"{float(comparison_freshness):.3f}"
                if isinstance(comparison_freshness, (int, float)) and not isinstance(comparison_freshness, bool)
                else "missing"
            ),
            result_candidate,
            fallback_reason,
        )
        if (
            previous_track_id
            and resumed_track_id
            and previous_track_id == resumed_track_id
            and previous_track_label
            and resumed_track_label
            and previous_track_label != resumed_track_label
        ):
            return {
                "status": "signature_changed",
                "reason_code": "OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED",
                "summary_en": (
                    f"Observation continuation outcome confirmed: {target_text} remains the same tracked contact, "
                    f"but its live signature changed from {previous_track_label} to {resumed_track_label} after "
                    "resume_observation on the same objective contour."
                ),
                "summary_ru": (
                    f"Observation continuation outcome подтверждён: {target_text} остаётся тем же track contact, "
                    f"но его live signature сменилась с {previous_track_label} на {resumed_track_label} после "
                    "resume_observation на том же objective contour."
                ),
                "allowed_when_en": (
                    f"The continuation result for {target_text} is recorded on the same objective contour; the "
                    "contact signature changed, so continue with the next observation objective using the updated "
                    "signature."
                ),
                "allowed_when_ru": (
                    f"Continuation-result для {target_text} зафиксирован на том же objective contour; signature "
                    "изменилась, поэтому дальше используйте обновлённую signature в следующей observation-цели."
                ),
            }
        return {
            "status": "reconfirmed",
            "reason_code": "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED",
            "summary_en": (
                f"Observation continuation outcome confirmed: {target_text} was safely reconfirmed after "
                "resume_observation on the same objective contour."
            ),
            "summary_ru": (
                f"Observation continuation outcome подтверждён: цель {target_text} безопасно reconfirmed после "
                "resume_observation на том же objective contour."
            ),
            "allowed_when_en": (
                f"The continuation result for {target_text} is recorded on the same objective contour; you may "
                "proceed to the next observation objective."
            ),
            "allowed_when_ru": (
                f"Continuation-result для {target_text} зафиксирован на том же objective contour; можно "
                "переходить к следующей observation-цели."
            ),
        }

    def _apply_observation_result_to_qiki(self, result: dict[str, str] | None) -> None:
        if self._qiki_last_response is None or result is None:
            return
        legality = self._qiki_last_response.legality
        if legality is not None:
            legality = legality.model_copy(
                update={
                    "allowed_when": BilingualText(
                        en=result["allowed_when_en"],
                        ru=result["allowed_when_ru"],
                    )
                }
            )
        telemetry_confirmation = None
        if self._qiki_last_response.consequence is not None:
            telemetry_confirmation = self._qiki_last_response.consequence.telemetry_confirmation
        self._qiki_last_response = self._qiki_last_response.model_copy(
            update={
                "consequence": QikiConsequenceV1(
                    status="confirmed",
                    summary=BilingualText(
                        en=result["summary_en"],
                        ru=result["summary_ru"],
                    ),
                    telemetry_confirmation=telemetry_confirmation,
                ),
                "legality": legality,
                "proposals": [],
            }
        )

    async def _publish_observation_objective_update(
        self,
        *,
        status: str,
        summary_en: str,
        summary_ru: str,
        reason_code: str,
        procedure_name: str | None = None,
        observation_result: dict[str, str] | None = None,
        track_snapshot: dict[str, Any] | None = None,
    ) -> None:
        objective = self._matching_active_observation_objective(procedure_name)
        if objective is None:
            return
        now = datetime.now(tz=timezone.utc)
        payload = dict(objective)
        follow_up = (
            self._observation_follow_up_contract(objective)
            if status == "confirmed" and observation_result is None
            else None
        )
        payload.update(
            {
                "event_schema_version": 1,
                "source": "orion_v",
                "subject": OPERATOR_OBJECTIVES,
                "timestamp": now.isoformat(),
                "ts_epoch": now.timestamp(),
                "kind": "observation_objective_update",
                "status": status,
                "summary_en": summary_en,
                "summary_ru": summary_ru,
                "reason_code": reason_code,
            }
        )
        if follow_up is not None:
            payload.update(
                {
                    "follow_up_status": follow_up["status"],
                    "follow_up_reason_code": follow_up["reason_code"],
                    "follow_up_event_type": follow_up["event_type"],
                    "follow_up_summary_en": follow_up["summary_en"],
                    "follow_up_summary_ru": follow_up["summary_ru"],
                    "follow_up_allowed_when_en": follow_up["allowed_when_en"],
                    "follow_up_allowed_when_ru": follow_up["allowed_when_ru"],
                }
            )
        else:
            for key in (
                "follow_up_status",
                "follow_up_reason_code",
                "follow_up_event_type",
                "follow_up_summary_en",
                "follow_up_summary_ru",
                "follow_up_allowed_when_en",
                "follow_up_allowed_when_ru",
            ):
                payload.pop(key, None)
        if observation_result is not None:
            payload.update(
                {
                    "observation_result_status": observation_result["status"],
                    "observation_result_reason_code": observation_result["reason_code"],
                    "observation_result_summary_en": observation_result["summary_en"],
                    "observation_result_summary_ru": observation_result["summary_ru"],
                }
            )
        else:
            for key in (
                "observation_result_status",
                "observation_result_reason_code",
                "observation_result_summary_en",
                "observation_result_summary_ru",
            ):
                payload.pop(key, None)
        if isinstance(track_snapshot, dict):
            for key in (
                "track_id",
                "track_label",
                "track_range_m",
                "track_quality",
                "public_track_id",
                "public_track_label",
            ):
                if key in track_snapshot:
                    payload[key] = track_snapshot[key]
        self._active_observation_objective = dict(payload)
        await self._publish_operator_event(OPERATOR_OBJECTIVES, payload)
        self._request_refresh_ui()

    def _confirm_qiki_pending_action(self) -> None:
        action = self._qiki_pending_action
        if action is None:
            self._set_help_text("QIKI: нет действия для подтверждения")
            return
        title_ru = str(action.get("title_ru") or "выполнить действие QIKI")
        self._set_last_command_loop_state("awaiting_confirm", f"Awaiting operator confirm: {title_ru}")
        self.push_screen(
            ConfirmDialog(f"Подтвердить: {title_ru}?"),
            lambda confirmed: self._run_after_confirm(
                confirmed,
                lambda: asyncio.create_task(self._execute_qiki_pending_action()),
            ),
        )

    async def _wait_for_qiki_effect(self, command_name: str, timeout_s: float) -> BilingualText | None:
        deadline = time.monotonic() + timeout_s
        command = command_name.strip().lower()
        while time.monotonic() < deadline:
            if command == "sim.dock.release":
                docking = self._snapshot.get("docking")
                if isinstance(docking, dict):
                    state = str(docking.get("state") or "").strip().lower()
                    connected = bool(docking.get("connected"))
                    port = str(docking.get("port") or "").strip() or "?"
                    if state == "undocked" and not connected:
                        return BilingualText(
                            en=f"Docking telemetry confirms undocked state on port {port}.",
                            ru=f"Телеметрия стыковки подтверждает состояние отстыковки на порту {port}.",
                        )
            await asyncio.sleep(0.1)
        return None

    @staticmethod
    def _procedure_expected_sim_state(definition: ProcedureDefinition) -> dict[str, Any] | None:
        expected: dict[str, Any] | None = None
        for step in definition.steps:
            command = step.command.strip().lower()
            if command == "sim.start":
                expected = {
                    "fsm_state": "RUNNING",
                    "paused": False,
                    "speed": float(step.parameters.get("speed", 1.0) or 1.0),
                }
            elif command == "sim.rcs.fire":
                expected = {
                    "effect_kind": "rcs_fire",
                    "pct": float(step.parameters.get("pct", step.parameters.get("percent", 0.0)) or 0.0),
                }
        return expected

    async def _wait_for_procedure_effect(
        self, definition: ProcedureDefinition, timeout_s: float
    ) -> BilingualText | None:
        expected = self._procedure_expected_sim_state(definition)
        if expected is None:
            return None

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if expected.get("effect_kind") == "rcs_fire":
                propulsion = self._snapshot.get("propulsion")
                rcs = propulsion.get("rcs") if isinstance(propulsion, dict) else None
                if isinstance(rcs, dict):
                    try:
                        command_pct = float(rcs.get("command_pct") or 0.0)
                        time_left_s = float(rcs.get("time_left_s") or 0.0)
                    except Exception:
                        command_pct = 0.0
                        time_left_s = 0.0
                    if command_pct >= float(expected.get("pct") or 0.0) and time_left_s > 0.0:
                        rcs_confirmation = (
                            f"propulsion.rcs command_pct={command_pct:.1f}, "
                            f"time_left_s={time_left_s:.2f}"
                        )
                        return BilingualText(
                            en=rcs_confirmation,
                            ru=rcs_confirmation,
                        )
            else:
                sim_state = self._telemetry.get("sim_state")
                if isinstance(sim_state, dict):
                    state_name = str(sim_state.get("fsm_state") or "").strip().upper()
                    paused = bool(sim_state.get("paused"))
                    try:
                        speed = float(sim_state.get("speed") or 0.0)
                    except Exception:
                        speed = 0.0
                    if (
                        state_name == str(expected["fsm_state"]).upper()
                        and paused is bool(expected["paused"])
                        and abs(speed - float(expected["speed"])) < 1e-6
                    ):
                        return BilingualText(
                            en=f"sim_state={state_name}, paused={paused}, speed={speed:.2f}",
                            ru=f"sim_state={state_name}, paused={paused}, speed={speed:.2f}",
                        )
            await asyncio.sleep(0.1)
        return None

    async def _execute_qiki_pending_action(self) -> None:
        action = self._qiki_pending_action
        if action is None:
            self._set_help_text("QIKI: нет действия для исполнения")
            return
        if self._replay_mode:
            self._set_help_text("РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО")
            return

        action_kind = str(action.get("action_kind") or "NATS_COMMAND").strip()
        subject = str(action.get("subject") or "").strip()
        command_name = str(action.get("name") or "").strip()
        parameters = action.get("parameters")
        if action_kind == "ORION_PROCEDURE":
            await self._execute_qiki_pending_procedure(command_name)
            return
        if subject != COMMANDS_CONTROL or not command_name:
            self._set_help_text("QIKI: неподдерживаемый тип исполняемого действия")
            return

        await self._publish_sim_command(command_name, parameters if isinstance(parameters, dict) else {})
        ack_ok = await self._wait_for_ack(command_name, 2.0)
        if not ack_ok:
            if self._qiki_last_response is not None:
                self._qiki_last_response = self._qiki_last_response.model_copy(
                    update={
                        "consequence": QikiConsequenceV1(
                            status="failed",
                            summary=BilingualText(
                                en="The control command did not receive a matching acknowledgement in time.",
                                ru="Команда управления не получила подтверждение вовремя.",
                            ),
                            telemetry_confirmation=BilingualText(
                                en="Execution state could not be confirmed from the control response channel.",
                                ru="Состояние исполнения не удалось подтвердить по каналу control response.",
                            ),
                        ),
                        "proposals": [],
                    }
                )
            self._qiki_pending_action = None
            self._set_last_command_loop_state("failed", f"Ack timeout for {command_name}")
            self._set_help_text(f"QIKI execution failed: нет ack для {command_name}")
            self._request_refresh_ui()
            return

        confirmation = await self._wait_for_qiki_effect(command_name, 2.0)
        if confirmation is None:
            if self._qiki_last_response is not None:
                self._qiki_last_response = self._qiki_last_response.model_copy(
                    update={
                        "consequence": QikiConsequenceV1(
                            status="pending",
                            summary=BilingualText(
                                en=(
                                    "The command acknowledgement arrived, "
                                    "but telemetry has not confirmed the effect yet."
                                ),
                                ru="Подтверждение команды получено, но телеметрия ещё не подтвердила эффект.",
                            ),
                            telemetry_confirmation=BilingualText(
                                en="ORION is still waiting for the post-command state transition.",
                                ru="ORION всё ещё ждёт послекомандного перехода состояния.",
                            ),
                        )
                    }
                )
            self._qiki_pending_action = None
            self._set_last_command_loop_state(
                "acknowledged",
                f"Ack received for {command_name}; awaiting telemetry effect",
            )
            self._set_help_text(f"QIKI execution pending: ack получен для {command_name}, ждём телеметрию")
            self._request_refresh_ui()
            return

        if self._qiki_last_response is not None:
            self._qiki_last_response = self._qiki_last_response.model_copy(
                update={
                    "consequence": QikiConsequenceV1(
                        status="confirmed",
                        summary=BilingualText(
                            en="The control command was applied and the telemetry effect is confirmed.",
                            ru="Команда управления применена, и телеметрический эффект подтверждён.",
                        ),
                        telemetry_confirmation=confirmation,
                    ),
                    "proposals": [],
                }
            )
        self._qiki_pending_action = None
        self._set_last_command_loop_state("confirmed", f"Telemetry confirmed: {command_name}")
        self._set_help_text(f"QIKI execution confirmed: {command_name}")
        self._request_refresh_ui()

    async def _wait_for_procedure_completion(self, name: str, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._procedure_task is not None and self._procedure_task.done():
                return (
                    self._procedure_engine.state.procedure_name == name
                    and self._procedure_engine.state.status == "ok"
                )
            await asyncio.sleep(0.1)
        return False

    async def _execute_qiki_pending_procedure(self, procedure_name: str) -> None:
        action = self._qiki_pending_action if isinstance(self._qiki_pending_action, dict) else None
        action_parameters = dict(action.get("parameters") or {}) if isinstance(action, dict) else {}
        definition = self._procedure_engine.get(procedure_name)
        if definition is None:
            self._set_help_text(f"QIKI: неизвестная процедура {procedure_name}")
            return
        if self._procedure_task and not self._procedure_task.done():
            self._set_help_text("Процедура уже выполняется")
            return

        self._last_proc_start_mono = time.monotonic()
        self._procedure_task = asyncio.create_task(self._run_procedure(definition.name))
        self._request_refresh_ui()
        ok = await self._wait_for_procedure_completion(definition.name, 6.0)
        if not ok:
            await self._publish_observation_objective_update(
                status="failed",
                summary_en="The observation objective failed because the ORION procedure did not finish successfully.",
                summary_ru="Observation-цель завершилась неуспешно: процедура ORION не завершилась успешно.",
                reason_code="OBJECTIVE_PROCEDURE_FAILED",
                procedure_name=procedure_name,
            )
            if self._qiki_last_response is not None:
                self._qiki_last_response = self._qiki_last_response.model_copy(
                    update={
                        "consequence": QikiConsequenceV1(
                            status="failed",
                            summary=BilingualText(
                                en="The prepared ORION procedure did not finish successfully.",
                                ru="Подготовленная процедура ORION не завершилась успешно.",
                            ),
                            telemetry_confirmation=BilingualText(
                                en=f"Procedure state={self._procedure_engine.state.status}.",
                                ru=f"Состояние процедуры={self._procedure_engine.state.status}.",
                            ),
                        ),
                        "proposals": [],
                    }
                )
            self._qiki_pending_action = None
            self._set_help_text(f"QIKI execution failed: процедура {procedure_name}")
            self._request_refresh_ui()
            return

        confirmation = await self._wait_for_procedure_effect(definition, 3.0)
        if confirmation is None:
            if self._qiki_last_response is not None:
                self._qiki_last_response = self._qiki_last_response.model_copy(
                    update={
                        "consequence": QikiConsequenceV1(
                            status="pending",
                            summary=BilingualText(
                                en=(
                                    "The ORION procedure finished, "
                                    "but the expected telemetry effect is not confirmed yet."
                                ),
                                ru=(
                                    "Процедура ORION завершилась, "
                                    "но ожидаемый телеметрический эффект ещё не подтверждён."
                                ),
                            ),
                            telemetry_confirmation=BilingualText(
                                en=(
                                    f"Procedure state={self._procedure_engine.state.status}; "
                                    "telemetry confirmation pending."
                                ),
                                ru=(
                                    f"Состояние процедуры={self._procedure_engine.state.status}; "
                                    "подтверждение по телеметрии ожидается."
                                ),
                            ),
                        ),
                        "proposals": [],
                    }
                )
            self._qiki_pending_action = None
            self._set_help_text(f"QIKI execution pending: процедура {procedure_name}, ждём телеметрию")
            self._request_refresh_ui()
            return

        current_objective = self._matching_active_observation_objective(procedure_name)
        track_snapshot = self._live_observation_track_snapshot(
            current_objective,
            fallback_parameters=action_parameters,
        )
        result_parameters = dict(action_parameters)
        if isinstance(track_snapshot, dict):
            result_parameters.update(
                {
                    "observation_track_id": track_snapshot.get("track_id"),
                    "observation_track_label": track_snapshot.get("track_label"),
                    "observation_track_range_m": track_snapshot.get("track_range_m"),
                    "observation_track_quality": track_snapshot.get("track_quality"),
                }
            )
        observation_result = self._build_resume_observation_result(current_objective, parameters=result_parameters)
        await self._publish_observation_objective_update(
            status="confirmed",
            summary_en=(
                observation_result["summary_en"]
                if observation_result is not None
                else "The observation objective completed and its telemetry consequence is confirmed."
            ),
            summary_ru=(
                observation_result["summary_ru"]
                if observation_result is not None
                else "Observation-цель завершена, и её телеметрический эффект подтверждён."
            ),
            reason_code=(
                observation_result["reason_code"] if observation_result is not None else "OBJECTIVE_CONFIRMED"
            ),
            procedure_name=procedure_name,
            observation_result=observation_result,
            track_snapshot=track_snapshot,
        )
        updated_objective = self._active_observation_objective
        follow_up = self._observation_follow_up_contract(updated_objective)
        recorded_result = self._observation_result_contract(updated_objective)
        if self._qiki_last_response is not None:
            legality = self._qiki_last_response.legality
            summary = BilingualText(
                en="The prepared ORION procedure completed and the telemetry effect is confirmed.",
                ru="Подготовленная процедура ORION завершена, и телеметрический эффект подтверждён.",
            )
            consequence_status = "confirmed"
            sim_state = self._telemetry.get("sim_state")
            if follow_up is not None:
                summary = BilingualText(
                    en=follow_up["summary_en"],
                    ru=follow_up["summary_ru"],
                )
                consequence_status = "pending"
                if legality is not None:
                    legality = legality.model_copy(
                        update={
                            "allowed_when": BilingualText(
                                en=follow_up["allowed_when_en"],
                                ru=follow_up["allowed_when_ru"],
                            )
                        }
                    )
            elif recorded_result is not None:
                summary = BilingualText(
                    en=recorded_result["summary_en"],
                    ru=recorded_result["summary_ru"],
                )
                if legality is not None and observation_result is not None:
                    legality = legality.model_copy(
                        update={
                            "allowed_when": BilingualText(
                                en=observation_result["allowed_when_en"],
                                ru=observation_result["allowed_when_ru"],
                            )
                        }
                    )
            elif isinstance(sim_state, dict):
                speed = float(sim_state.get("speed") or 1.0)
                summary = BilingualText(
                    en=(
                        "The ORION procedure completed and the simulation entered the prepared running state "
                        f"at speed x{speed:.2f}."
                    ),
                    ru=(
                        "Процедура ORION завершена, и симуляция перешла в подготовленное состояние выполнения "
                        f"на скорости x{speed:.2f}."
                    ),
                )
            self._qiki_last_response = self._qiki_last_response.model_copy(
                update={
                    "consequence": QikiConsequenceV1(
                        status=consequence_status,
                        summary=summary,
                        telemetry_confirmation=confirmation,
                    ),
                    "legality": legality,
                    "proposals": [],
                }
            )
        combat_event = self._build_combat_consequence_event(procedure_name, confirmation)
        if combat_event is not None:
            await self._publish_operator_event(OPERATOR_COMBAT, combat_event)
        self._qiki_pending_action = None
        self._set_help_text(f"QIKI execution confirmed: процедура {procedure_name}")
        self._request_refresh_ui()

    async def _on_qiki_response(self, envelope: dict[str, Any]) -> None:
        payload = envelope.get("data", {}) if isinstance(envelope, dict) else {}
        if not isinstance(payload, dict):
            return
        try:
            response = QikiChatResponseV1.model_validate(payload)
        except Exception:
            logger.debug("orion_v_decode_qiki_response_failed", exc_info=True)
            self._set_help_text("QIKI response: ошибка декодирования")
            return

        self._qiki_pending.pop(str(response.request_id), None)
        self._qiki_last_response = response
        self._qiki_pending_action = self._extract_qiki_pending_action(response)
        self._enrich_active_observation_with_live_public_track()
        if self._qiki_pending_action is not None:
            pending_title = str(
                self._qiki_pending_action.get("title_ru")
                or self._qiki_pending_action.get("title_en")
                or "QIKI action"
            ).strip()
            self._set_last_command_loop_state("awaiting_confirm", pending_title)
        elif response.legality is not None and response.legality.status != "allowed":
            self._set_last_command_loop_state(
                "blocked",
                f"QIKI legality: {response.legality.status} [{response.legality.reason_code}]",
            )
        elif response.reply is not None:
            reply_body = str(response.reply.body.ru or response.reply.body.en or "").strip() or "QIKI reply ready"
            self._set_last_command_loop_state("reply_ready", reply_body)
        else:
            self._set_last_command_loop_state("reply_ready", "QIKI response received")
        if response.legality is not None:
            help_text = (
                "QIKI "
                f"{response.legality.status}: {response.legality.reason.ru} [{response.legality.reason_code}]"
            )
            if self._qiki_pending_action is not None:
                help_text += " | q confirm"
            self._set_help_text(help_text)
        elif response.reply is not None:
            self._set_help_text(f"QIKI: {response.reply.body.ru}")
        else:
            self._set_help_text("QIKI: ответ получен")
        self._request_refresh_ui()

    def _refresh_visible_level(self) -> None:
        for key, meta in self.LEVEL_META.items():
            widget = self.query_one(f"#{meta['widget_id']}", Static)
            if key == self._current_level:
                widget.remove_class("hidden")
            else:
                widget.add_class("hidden")

    def _shift_incident_selection(self, *, step: int) -> None:
        source_store = self._replay_store if self._replay_mode else self._events_store
        incidents = source_store.active_incidents()
        if not incidents:
            self._selected_incident_id = None
            self._request_refresh_ui()
            return

        ids = [inc["id"] for inc in incidents]
        if self._selected_incident_id not in ids:
            self._selected_incident_id = ids[0]
            self._request_refresh_ui()
            return

        idx = ids.index(self._selected_incident_id)
        next_idx = (idx + step) % len(ids)
        self._selected_incident_id = ids[next_idx]
        self._request_refresh_ui()

    def _ack_incident(self, incident_id: str) -> None:
        if not self._events_store.mark_acknowledged(incident_id):
            self._set_help_text(f"Инцидент не найден или уже подтвержден: {incident_id}")
            return

        ack_started = datetime.now(tz=timezone.utc).timestamp()
        created_ts = self._incident_first_seen.get(incident_id)
        ack_time_ms = 0.0
        if created_ts is not None:
            ack_time_ms = max(0.0, (ack_started - created_ts) * 1000.0)
            self._metrics["ack_time_ms"] = ack_time_ms
        payload = {
            "kind": "incident_ack",
            "action_type": "incidents",
            "incident_id": incident_id,
            "operator": "orion_v",
            "ok": True,
            "ack_time_ms": ack_time_ms,
        }
        self._incident_first_seen.pop(incident_id, None)
        asyncio.create_task(self._publish_audit_event(OPERATOR_INCIDENTS, payload))
        self._set_help_text(f"Подтверждено: {incident_id}")
        self._refresh_ui()

    def _clear_acknowledged_incidents(self) -> None:
        acked_ids = {
            _incident_id_from_payload(record.get("data"))
            for record in self._events_store.snapshot()
            if isinstance(record, dict)
            and isinstance(record.get("data"), dict)
            and _coerce_bool(record.get("data", {}).get("acked"))
        }
        cleared = self._events_store.clear_acknowledged()
        payload = {
            "kind": "incident_clear",
            "action_type": "incidents",
            "cleared_count": int(cleared),
            "operator": "orion_v",
            "ok": True,
        }
        for incident_id in acked_ids:
            if incident_id:
                self._incident_first_seen.pop(incident_id, None)
        asyncio.create_task(self._publish_audit_event(OPERATOR_INCIDENTS, payload))
        self._set_help_text(f"Снято подтвержденных инцидентов: {cleared}")
        self._refresh_ui()

    async def _publish_operator_action(self, payload: dict[str, Any]) -> None:
        await self._publish_audit_event(OPERATOR_ACTIONS, payload)

    async def _publish_procedure_audit(self, payload: dict[str, Any]) -> None:
        event = dict(payload)
        event.setdefault("action_type", "procedures")
        event.setdefault("operator", "orion_v")
        await self._publish_audit_event(OPERATOR_PROCEDURES, event)

    def _build_combat_consequence_event(
        self,
        procedure_name: str,
        confirmation: BilingualText,
    ) -> dict[str, Any] | None:
        if procedure_name != "hostile_rcs_intercept_burst":
            return None
        propulsion = self._snapshot.get("propulsion")
        rcs = propulsion.get("rcs") if isinstance(propulsion, dict) else None
        if not isinstance(rcs, dict):
            return None
        axis = str(rcs.get("axis") or "unknown")
        command_pct = float(rcs.get("command_pct") or 0.0)
        time_left_s = float(rcs.get("time_left_s") or 0.0)
        return {
            "action_type": "combat",
            "subsystem": "combat",
            "event_type": "COMBAT_ENTRY_CONFIRMED",
            "severity": "INFO",
            "type": "combat_entry_consequence",
            "reason_code": "COMBAT_EVENT_INTERCEPT_BURST_CONFIRMED",
            "procedure": procedure_name,
            "message": (
                "Подтверждён боевой импульс входа в бой: "
                f"RCS {axis} {command_pct:.1f}% на {time_left_s:.2f} с."
            ),
            "target": "UNBT9999",
            "axis": axis,
            "command_pct": command_pct,
            "time_left_s": time_left_s,
            "telemetry_confirmation_ru": confirmation.ru,
            "telemetry_confirmation_en": confirmation.en,
        }

    async def _publish_operator_event(self, subject: str, payload: dict[str, Any]) -> None:
        event = dict(payload)
        event.setdefault("operator", "orion_v")
        event.setdefault("timestamp", datetime.now(tz=timezone.utc).isoformat())
        if self._nats_client.nc and self._nats_client.nc.is_connected:
            try:
                await self._nats_client.publish_command(subject, event)
            except Exception:
                logger.debug("orion_v_publish_operator_event_failed subject=%s", subject, exc_info=True)
            return
        await self._on_event(
            {
                "stream": "EVENTS",
                "timestamp": event["timestamp"],
                "subject": subject,
                "data": event,
            }
        )

    async def _publish_audit_event(self, subject: str, payload: dict[str, Any]) -> None:
        event = dict(payload)
        event.setdefault("operator", "orion_v")
        event.setdefault("timestamp", datetime.now(tz=timezone.utc).isoformat())
        record = {
            "stream": "AUDIT",
            "timestamp": event["timestamp"],
            "subject": subject,
            "data": event,
        }
        self._audit_store.append(record)
        self._event_timestamps.append(time.monotonic())
        nc = getattr(self._nats_client, "nc", None)
        if not (nc and nc.is_connected):
            await self._on_event(
                {
                    "stream": "EVENTS",
                    "timestamp": event["timestamp"],
                    "subject": subject,
                    "data": event,
                }
            )
        try:
            await self._nats_client.publish_command(subject, event)
        except Exception:
            logger.debug("orion_v_publish_operator_action_failed", exc_info=True)

    def _build_objective_timeline_lines(self, source_store: BoundedEventsStore) -> list[str]:
        objective = self._active_observation_objective
        if not isinstance(objective, dict):
            return []

        identities = self._objective_identity_values(objective)
        if not identities:
            return []

        lines: list[str] = []
        for event in reversed(source_store.last(40)):
            if not isinstance(event, dict):
                continue
            payload = event.get("data")
            if not isinstance(payload, dict):
                continue
            if not identities.intersection(self._event_identity_values(payload)):
                continue

            subject = str(event.get("subject") or "events")
            subject_tail = subject.split(".")[-1] if subject else "events"
            status = str(payload.get("status") or payload.get("event_type") or payload.get("type") or "fact").strip()
            summary = (
                str(payload.get("summary_ru") or "").strip()
                or str(payload.get("message") or "").strip()
                or str(payload.get("description") or "").strip()
                or str(payload.get("reason_code") or "").strip()
                or "событие без краткого описания"
            )
            line = f"{subject_tail} | {status} | {summary}"
            if line not in lines:
                lines.append(line)
            if len(lines) >= 4:
                break
        return lines

    def _refresh_ui(self) -> None:
        if not self.is_mounted:
            return
        try:
            self.query_one("#orionv-cockpit", OrionVCockpitScreen)
        except NoMatches:
            return
        try:
            self._refresh_visible_level()
        except NoMatches:
            return
        source_store = self._replay_store if self._replay_mode else self._events_store

        active_incidents = source_store.active_incidents()
        active_ids = {inc["id"] for inc in active_incidents}
        if self._selected_incident_id not in active_ids:
            self._selected_incident_id = active_incidents[0]["id"] if active_incidents else None

        level_label = self.LEVEL_META[self._current_level]["label"]
        self._operator_shell_state = build_operator_shell_state(
            hardware_model=self.hardware_model,
            telemetry=self._telemetry,
            safe_mode=self._safe_mode_state,
            observation_objective=self._active_observation_objective,
            incidents=active_incidents,
            radar_tracks=self._latest_radar_tracks,
            qiki_response=self._qiki_last_response,
            qiki_pending_action_title=(
                str(
                    self._qiki_pending_action.get("title_ru")
                    or self._qiki_pending_action.get("title_en")
                    or ""
                ).strip()
                if self._qiki_pending_action is not None
                else None
            ),
            qiki_pending_action=self._qiki_pending_action,
            selected_incident_id=self._selected_incident_id,
            selected_subsystem=self._selected_system_module_slug,
            nats_state=self._nats_state,
            replay_mode=self._replay_mode,
            current_level=self._current_level,
            level_label=level_label + (" [АНАЛИЗ]" if self._replay_mode else ""),
            events_count=source_store.count(),
            last_telemetry_received_wall=self._last_telemetry_received_wall,
            help_text=self._help_text,
            command_mode_open=self._command_mode_open,
            qiki_pending_count=len(self._qiki_pending),
            procedure_running=self._procedure_task is not None and not self._procedure_task.done(),
            ack_pending=self._pending_ack_command_id is not None,
            last_command_status=self._last_command_status,
            last_command_summary=self._last_command_summary,
            console_lines=tuple(list(self._console_history)[-5:]),
        )
        self.query_one("#orionv-overlay", OrionVAlertsOverlay).set_state(self._operator_shell_state)
        self.query_one("#orionv-actions", OrionVActionBar).set_state(self._operator_shell_state)
        self.query_one("#orionv-bars", OrionVStatusBars).set_state(self._operator_shell_state)
        self.query_one("#orionv-header", OrionVHeader).set_state(self._operator_shell_state)

        self.query_one("#orionv-cockpit", OrionVCockpitScreen).set_state(
            telemetry=self._telemetry,
            nats_connected=self._nats_state == "connected",
            active_incidents=len(active_incidents),
            incidents=active_incidents,
            safe_mode=self._safe_mode_state,
            observation_objective=self._active_observation_objective,
            objective_event_lines=self._build_objective_timeline_lines(source_store),
            qiki_response=self._qiki_last_response,
            qiki_plan_preview_lines=self._build_qiki_plan_preview_lines(),
            qiki_procedure_status=(
                self._procedure_status_line()
                if self._procedure_engine.state.running or self._procedure_engine.state.status in {"ok", "failed"}
                else None
            ),
            qiki_pending_action_title=(
                str(
                    self._qiki_pending_action.get("title_ru")
                    or self._qiki_pending_action.get("title_en")
                    or ""
                ).strip()
                if self._qiki_pending_action is not None
                else None
            ),
            operator_shell_state=self._operator_shell_state,
            active_left_mfd_page=self._active_mfd_left_page,
            active_right_mfd_page=self._active_mfd_right_page,
            playable_loop_state=self._f1_playable_loop_state,
        )

        self.query_one("#orionv-systems", OrionVSystemsScreen).set_state(
            hardware_model=self.hardware_model,
            telemetry=self._telemetry,
            selected_subsystem=self._selected_system_module_slug,
            safe_mode=self._safe_mode_state,
            observation_objective=self._active_observation_objective,
            active_incidents=len(active_incidents),
            incidents=active_incidents,
            radar_tracks=self._latest_radar_tracks,
            active_left_mfd_page=self._active_mfd_left_page,
            active_right_mfd_page=self._active_mfd_right_page,
        )

        since_epoch_s = (
            now_epoch_s() - float(self._filter_window_sec) if isinstance(self._filter_window_sec, int) else None
        )
        filtered_total = source_store.query_count(
            severities=self._filter_severities or None,
            subsystem=self._filter_subsystem,
            since_epoch_s=since_epoch_s,
        )
        max_pages = max(1, (filtered_total + self._events_page_size - 1) // self._events_page_size)
        if self._events_page >= max_pages:
            self._events_page = max_pages - 1

        events_page = source_store.query(
            limit=self._events_page_size,
            offset=self._events_page * self._events_page_size,
            severities=self._filter_severities or None,
            subsystem=self._filter_subsystem,
            since_epoch_s=since_epoch_s,
        )

        deep_lines: list[str] = []
        for event in events_page:
            data = event.get("data") if isinstance(event, dict) else None
            severity = ""
            if isinstance(data, dict):
                severity = str(data.get("severity", ""))
            subject = str(event.get("subject", "events"))
            message = ""
            if isinstance(data, dict):
                message = str(data.get("message") or data.get("description") or data.get("type") or "")
            deep_lines.append(f"{severity or '-'} | {subject} | {message or 'degraded: нет сообщения'}")

        filters: list[str] = []
        if self._filter_severities:
            filters.append(f"sev={','.join(sorted(self._filter_severities))}")
        if self._filter_subsystem:
            filters.append(f"subsys={self._filter_subsystem}")
        if self._filter_window_sec is not None:
            filters.append(f"range={self._filter_window_sec}s")
        filter_summary = (
            f"{' '.join(filters) if filters else 'все'} | "
            f"страница {self._events_page + 1}/{max_pages} | всего {filtered_total}"
        )

        self.query_one("#orionv-deep", OrionVDeepDiveScreen).set_state(
            lines=deep_lines,
            incidents=active_incidents,
            selected_incident_id=self._selected_incident_id,
            filter_summary=f"{filter_summary} | {self._procedure_status_line()}",
            safe_mode=self._safe_mode_state,
        )

        console_lines = ["Последние действия и ответы/Recent operator messages:"]
        if self._console_history:
            console_lines.extend(f"- {entry}" for entry in list(self._console_history)[-24:])
        else:
            console_lines.append("- История пока пуста")
        console_lines.extend(
            [
                "",
                "Контекст/Context:",
                f"- Активный экран/Active level: {level_label}",
                f"- События на странице/Events on page: {len(events_page)} из {filtered_total}",
                f"- Выбранная подсистема/Selected subsystem: {self._selected_system_module_slug or 'нет'}",
                f"- Выбранный инцидент/Selected incident: {self._selected_incident_id or 'нет'}",
            ]
        )
        self.query_one("#orionv-raw", OrionVRawScreen).set_text("\n".join(console_lines))
        evidence_screen = self.query_one("#orionv-evidence", OrionVEvidenceScreen)
        evidence_screen.update_snapshot(self._snapshot)

        audit_entries = self._audit_store.last(self._audit_store.count())
        if self._audit_filter_type:
            audit_entries = [entry for entry in audit_entries if _matches_audit_filter(entry, self._audit_filter_type)]
        audit_total = len(audit_entries)
        audit_pages = max(1, (audit_total + self._audit_page_size - 1) // self._audit_page_size)
        if self._audit_page >= audit_pages:
            self._audit_page = audit_pages - 1
        start = self._audit_page * self._audit_page_size
        end = start + self._audit_page_size
        audit_page = audit_entries[start:end]
        audit_lines = []
        for entry in audit_page:
            data = entry.get("data") if isinstance(entry, dict) else None
            kind = str(data.get("kind", "-")) if isinstance(data, dict) else "-"
            action_type = str(data.get("action_type", "-")) if isinstance(data, dict) else "-"
            status = str(data.get("status") or data.get("ok") or "-") if isinstance(data, dict) else "-"
            subject = str(entry.get("subject", "-"))
            audit_lines.append(f"{action_type} | {kind} | status={status} | {subject}")
        self.query_one("#orionv-audit", OrionVAuditScreen).set_state(
            lines=audit_lines,
            summary=(
                f"тип={self._audit_filter_type or 'все'} "
                f"страница {self._audit_page + 1}/{audit_pages} всего {audit_total}"
            ),
        )
        self.query_one("#orionv-health", OrionVSystemHealthScreen).set_state(dict(self._metrics))

    def _mission_mode_label(self) -> str:
        if self._replay_mode:
            return "REPLAY"
        sim_state = self._telemetry.get("sim_state")
        if not isinstance(sim_state, dict):
            return "LIVE"
        state_name = str(sim_state.get("fsm_state") or "LIVE").strip().upper() or "LIVE"
        paused = bool(sim_state.get("paused"))
        speed = sim_state.get("speed")
        speed_text = ""
        if isinstance(speed, (int, float)) and not isinstance(speed, bool):
            speed_text = f" {float(speed):.2f}x"
        if paused:
            return f"PAUSED{speed_text}"
        return f"{state_name}{speed_text}"

    def _control_authority_label(self) -> str:
        if self._replay_mode:
            return "analysis"
        if bool(self._safe_mode_state.get("active")):
            return str(self._safe_mode_state.get("authority") or "safe-mode")[:20]
        if self._qiki_pending_action is not None:
            return "operator-confirm"
        if self._qiki_last_response is not None and self._qiki_last_response.legality is not None:
            status = str(self._qiki_last_response.legality.status or "qiki").strip().lower()
            return f"qiki-{status}"[:20]
        return "operator"

    def _link_anchor_label(self) -> str:
        anchor = self._nats_url.removeprefix("nats://")
        return anchor.split("/", 1)[0] or "nats"

    def _telemetry_freshness_seconds(self) -> float | None:
        if self._last_telemetry_received_wall is None:
            return None
        return max(0.0, time.time() - self._last_telemetry_received_wall)

    def _time_anchor_label(self) -> str | None:
        if self._last_telemetry_received_wall is None:
            return None
        return datetime.fromtimestamp(
            self._last_telemetry_received_wall,
            tz=timezone.utc,
        ).strftime("%H:%M:%SZ")

    def _action_rail_hint(self) -> str:
        if self._command_mode_open:
            return "Enter submit | Esc close | q: asks QIKI"
        if self._current_level in {"f3", "f6"}:
            return "PgUp/PgDn pages | Up/Down incident focus"
        if self._selected_incident_id is not None:
            return "A ack selected incident | X clear acknowledged"
        return "F1/F2/F3/F4/F6/F7/F8 switch shells | '/' ':' open command"

    def _update_safe_mode_from_event(self, envelope: dict[str, Any]) -> None:
        subject = str(envelope.get("subject") or "")
        payload = envelope.get("data")
        if not isinstance(payload, dict):
            return
        parsed = _parse_safe_mode_event(subject=subject, payload=payload)
        if parsed is None:
            return
        self._safe_mode_state.update(parsed)
        ts = _extract_event_timestamp(payload, envelope.get("timestamp"))
        self._safe_mode_state["updated_ts"] = ts if ts is not None else time.time()

    def _merge_snapshot(self, target: dict[str, Any], incoming: dict[str, Any]) -> None:
        for key, value in incoming.items():
            if isinstance(value, dict):
                existing = target.get(key)
                if isinstance(existing, dict):
                    self._merge_snapshot(existing, value)
                else:
                    nested: dict[str, Any] = {}
                    target[key] = nested
                    self._merge_snapshot(nested, value)
            else:
                target[key] = value

    def _build_trends(self, events: list[dict[str, Any]]) -> dict[str, str]:
        soc_points: list[float] = []
        temp_points: list[float] = []
        volt_points: list[float] = []
        for event in events:
            data = event.get("data")
            if not isinstance(data, dict):
                continue
            power = data.get("power")
            thermal = data.get("thermal")
            if isinstance(power, dict):
                soc = power.get("soc_pct")
                volt = power.get("bus_v")
                if isinstance(soc, (int, float)) and not isinstance(soc, bool):
                    soc_points.append(float(soc))
                if isinstance(volt, (int, float)) and not isinstance(volt, bool):
                    volt_points.append(float(volt))
            if isinstance(thermal, dict):
                core = thermal.get("core_c")
                if isinstance(core, (int, float)) and not isinstance(core, bool):
                    temp_points.append(float(core))
            flat_temp = data.get("temp_core_c")
            if isinstance(flat_temp, (int, float)) and not isinstance(flat_temp, bool):
                temp_points.append(float(flat_temp))
        return {
            "soc": _trend_ascii("soc", soc_points),
            "temperature": _trend_ascii("temp", temp_points),
            "voltage": _trend_ascii("volt", volt_points),
        }


def _trend_ascii(label: str, points: list[float]) -> str:
    if not points:
        return f"{label}: degraded: нет данных"
    head = points[-5:]
    compact = " ".join(f"{val:.1f}" for val in head)
    return f"{label}: n={len(points)} последние=[{compact}] мин={min(points):.1f} макс={max(points):.1f}"


def _ack_payload_success(payload: dict[str, Any]) -> bool:
    raw = payload.get("ok")
    if raw is None:
        raw = payload.get("success")
    return _coerce_bool(raw)


def _coerce_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return raw != 0
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"1", "true", "yes", "on", "ok", "success", "applied"}:
            return True
        if token in {"0", "false", "no", "off", "fail", "failed", "error", "rejected"}:
            return False
        return bool(token)
    return bool(raw)


def _incident_open_audit_payload(
    *,
    incident_id: str,
    payload: dict[str, Any],
    incident_ts: float | None,
) -> dict[str, Any] | None:
    if not incident_id:
        return None
    if _coerce_bool(payload.get("acked")):
        return None

    severity = _normalize_incident_severity(payload.get("severity"))
    if severity not in {"A", "C"}:
        return None

    audit_payload: dict[str, Any] = {
        "kind": "incident_open",
        "action_type": "incidents",
        "incident_id": incident_id,
        "rule_id": str(payload.get("rule_id") or "").strip() or None,
        "severity": severity,
        "operator": "orion_v",
        "ok": True,
    }
    if incident_ts is not None:
        audit_payload["ts_epoch"] = incident_ts
    return audit_payload


def _normalize_incident_severity(raw: Any) -> str:
    token = str(raw or "").strip().upper()
    if not token:
        return ""
    if token.startswith("C") or token in {"CRIT", "CRITICAL", "ERROR"}:
        return "C"
    if token.startswith("A") or token in {"ALARM", "WARN", "WARNING"}:
        return "A"
    return token


def _incident_id_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("incident_id") or payload.get("incident_key") or payload.get("id") or "").strip()


def _parse_safe_mode_event(subject: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    subject_l = subject.lower()
    subsystem = str(payload.get("subsystem") or "").strip().upper()
    event_type = str(payload.get("event_type") or "").strip().upper()
    action = str(payload.get("action") or "").strip().lower()
    to_state = str(
        payload.get("to_state")
        or payload.get("state")
        or payload.get("ship_state_name")
        or ""
    ).strip().upper()
    reason_raw = (
        payload.get("safe_mode_reason")
        or payload.get("reason")
        or payload.get("trigger_event")
        or payload.get("message")
        or ""
    )
    context = payload.get("context")
    if isinstance(context, dict):
        reason_raw = context.get("safe_mode_reason") or reason_raw
    reason = str(reason_raw).strip()

    looks_like_safe_mode = (
        ("safe_mode" in subject_l)
        or (subsystem == "SAFE_MODE")
        or ("SAFE_MODE" in event_type)
        or ("SAFE_MODE" in to_state)
        or ("SAFE_MODE" in reason.upper())
        or (subsystem == "FSM" and to_state == "SAFE_MODE")
    )
    if not looks_like_safe_mode:
        return None

    if action in {"exit", "off", "clear", "disable", "disabled"} or "SAFE_MODE_EXIT" in reason.upper():
        active = False
    elif to_state in {"ACTIVE", "IDLE", "NORMAL"}:
        active = False
    else:
        active = True

    return {
        "active": active,
        "reason": reason,
        "authority": "q-core-agent(events)",
    }


def _extract_event_timestamp(payload: dict[str, Any], envelope_timestamp: Any) -> float | None:
    unix_ms = payload.get("ts_unix_ms")
    if isinstance(unix_ms, (int, float)) and not isinstance(unix_ms, bool):
        return float(unix_ms) / 1000.0
    unix_s = payload.get("ts_unix_s")
    if isinstance(unix_s, (int, float)) and not isinstance(unix_s, bool):
        return float(unix_s)
    stamp = payload.get("timestamp") or envelope_timestamp
    if isinstance(stamp, str) and stamp.strip():
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        return float(stamp)
    return None


def _matches_audit_filter(entry: dict[str, Any], filter_type: str) -> bool:
    data = entry.get("data") if isinstance(entry, dict) else None
    if not isinstance(data, dict):
        return False
    action_type = str(data.get("action_type") or "").strip().lower()
    kind = str(data.get("kind") or "").strip().lower()
    if filter_type in {"actions", "procedures", "incidents"}:
        return action_type == filter_type
    if filter_type == "level":
        return kind == "level_switch"
    if filter_type == "replay":
        return kind == "replay_mode"
    return True


def _read_container_metrics() -> tuple[float, float]:
    cpu_usage_us = 0.0
    mem_mb = 0.0
    try:
        current = Path("/sys/fs/cgroup/cpu.stat")
        if current.exists():
            text = current.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("usage_usec "):
                    cpu_usage_us = float(line.split(" ", 1)[1])
                    break
        else:
            cpu_v1 = Path("/sys/fs/cgroup/cpuacct/cpuacct.usage")
            if cpu_v1.exists():
                cpu_usage_us = float(cpu_v1.read_text(encoding="utf-8").strip()) / 1000.0
        mem_current = Path("/sys/fs/cgroup/memory.current")
        if mem_current.exists():
            mem_mb = float(mem_current.read_text(encoding="utf-8").strip()) / (1024.0 * 1024.0)
        else:
            mem_v1 = Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")
            if mem_v1.exists():
                mem_mb = float(mem_v1.read_text(encoding="utf-8").strip()) / (1024.0 * 1024.0)
    except Exception:
        return (0.0, 0.0)
    return (cpu_usage_us, mem_mb)
