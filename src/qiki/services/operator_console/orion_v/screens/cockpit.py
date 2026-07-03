from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.cockpit_playable_view_model import (
    build_cockpit_playable_loop_vm,
    format_cockpit_playable_action_labels,
    format_cockpit_playable_loop_lines,
)
from qiki.services.operator_console.orion_v.body_physics_view_model import (
    format_body_physics_cockpit_line,
    get_body_physics_console_view_model,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    format_body_structure_cockpit_line,
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model_from_telemetry,
    format_power_thermal_cockpit_line,
    format_soc_bat,
    format_soc_cap,
)
from qiki.services.operator_console.orion_v.i18n_ru import body_seed_status_ru, phys_ru, state_ru, tr
from qiki.services.operator_console.orion_v.mfd_layout import (
    MFD_DEFAULT_LEFT_PAGE,
    MFD_DEFAULT_RIGHT_PAGE,
    mfd_button_class,
    mfd_button_specs,
    mfd_page_label,
    normalize_mfd_page,
    render_status_strip,
    section_lines,
    softkey_bar,
)
from qiki.services.operator_console.orion_v.thermal_evidence import thermal_to_evidence
from qiki.services.operator_console.orion_v.thermal_telemetry_adapter import thermal_records_from_snapshot
from qiki.services.operator_console.orion_v.ui_rich import semantic_update
from qiki.shared.models.qiki_chat import QikiChatResponseV1

if TYPE_CHECKING:
    from qiki.services.operator_console.orion_v.operator_state import OperatorShellState


@dataclass(frozen=True, slots=True)
class QikiLoopProjection:
    """Single derivation of the G1 operator loop (Наблюдение->Команда->Legality/Trust->
    Consequence) from the last QikiChatResponseV1 + pending state. Built ONCE: the verbose
    [QIKI LOOP] bullets (rendered by _qiki_block) and the compact F1 loop rows (rendered by
    _qiki_recommendation_rows) both come from here, so legality/trust/effect are never derived
    twice nor parsed back out of rendered strings. ADR-0014: honest missing/unknown/no-action,
    never invented.
    """

    severity: str
    active: bool
    bullets: tuple[str, ...]
    rows: tuple[tuple[str, str, str], ...]



def _extract_mfd_sections(
    lines: list[str],
    markers: tuple[str, ...],
    *,
    chunk: int,
    limit: int,
) -> list[str]:
    wanted: list[str] = []
    normalized_markers = tuple(marker.lower() for marker in markers if marker)
    for idx, line in enumerate(lines):
        lower = line.lower()
        if any(marker in lower for marker in normalized_markers):
            wanted.extend(lines[idx : idx + chunk])
        if len(wanted) >= limit:
            break
    return wanted[:limit]


def _left_mfd_page_title(page: str) -> str:
    return {
        "radar": "Radar / Situation",
        "nav": "Navigation",
        "target": "Target / Objective",
        "sector": "Sector / Hazards",
        "mission": "Mission / Process",
    }.get(page, "Mission / Navigation")


# Single source of truth for the operator "next step" line prefix. Both the
# producers (_current_process_block / _procedure_block) and the consumer
# (_pick_next_step) reference it, so a wording/localization change can't make the
# picker silently miss the line and fall back to the default.
_NEXT_STEP_PREFIX = "Следующий шаг/Next:"


class OrionVCockpitScreen(Static):
    """Operator cockpit (F1): status-first layout for 3-5s situation awareness."""

    DEFAULT_CSS = """
    OrionVCockpitScreen {
        layout: vertical;
        height: 1fr;
    }

    #orionv-mfd-root {
        height: 1fr;
        layout: vertical;
    }

    #orionv-mfd-status {
        height: auto;
        max-height: 5;
        border: round #4f747c;
        border-title-color: #7de3f2;
        background: #10181b;
        color: #dce4dc;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #orionv-mfd-main {
        height: 1fr;
        min-height: 12;
        layout: horizontal;
    }

    #orionv-mfd-left-buttons,
    #orionv-mfd-right-buttons {
        width: 12;
        height: 1fr;
        layout: vertical;
        background: #070d10;
        padding: 0 1;
    }

    #orionv-mfd-left-buttons {
        margin: 0 1 0 0;
    }

    #orionv-mfd-right-buttons {
        margin: 0 0 0 1;
    }

    #orionv-mfd-left-buttons Button,
    #orionv-mfd-right-buttons Button {
        width: 10;
        min-width: 10;
        height: 1;
        min-height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: #0d1518;
        color: #aebabb;
        text-style: bold;
    }

    #orionv-mfd-left-buttons Button.mfd-active,
    #orionv-mfd-right-buttons Button.mfd-active {
        text-style: bold;
        border: none;
        background: #16343a;
        color: #f0f7f2;
    }

    #orionv-mfd-left-screen,
    #orionv-mfd-right-screen {
        width: 1fr;
        height: 1fr;
        border: round #3a8294;
        border-title-color: #64c7d8;
        background: #0d1417;
        color: #d8ded8;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    #orionv-mfd-right-screen {
        border: round #5f8a4a;
        border-title-color: #8fbf78;
    }

    #orionv-cockpit-actions {
        height: auto;
        max-height: 8;
        layout: vertical;
        border: round #617078;
        background: #0f1518;
        color: #d8ded8;
        padding: 0 1;
        margin: 1 0 0 0;
    }

    OrionVCockpitScreen .orionv-cockpit-action-row {
        height: auto;
        layout: horizontal;
    }

    OrionVCockpitScreen Button {
        min-width: 10;
        margin: 0 1 0 0;
        background: #121a1e;
        color: #d8ded8;
    }

    #orionv-mfd-qiki {
        height: auto;
        min-height: 5;
        max-height: 16;
        overflow-y: auto;
        border: round #9a7c3f;
        border-title-color: #d6b35f;
        background: #12140f;
        color: #ded9c8;
        padding: 0 1;
        margin: 1 0 0 0;
    }

    #orionv-cockpit-body,
    #orionv-cockpit-intervention {
        display: none;
        height: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._telemetry: dict[str, Any] = {}
        self._nats_connected = False
        self._active_incidents = 0
        self._incidents: list[dict[str, str]] = []
        self._safe_mode: dict[str, Any] = {}
        self._observation_objective: dict[str, Any] | None = None
        self._objective_event_lines: list[str] = []
        self._qiki_response: QikiChatResponseV1 | None = None
        self._qiki_pending_action_title: str | None = None
        self._qiki_plan_preview_lines: list[str] = []
        self._qiki_procedure_status: str | None = None
        self._prev_core_temp_c: float | None = None
        self._operator_shell_state: Any | None = None
        self._fallback_body_text = ""
        self._fallback_intervention_text = ""
        self._active_left_mfd_page = MFD_DEFAULT_LEFT_PAGE
        self._active_right_mfd_page = MFD_DEFAULT_RIGHT_PAGE
        self._playable_loop_state: dict[str, Any] = {}
        self._last_playable_loop_vm = None

    def compose(self) -> ComposeResult:
        with Container(id="orionv-mfd-root"):
            yield Static("", id="orionv-mfd-status")
            with Container(id="orionv-mfd-main"):
                with Container(id="orionv-mfd-left-buttons"):
                    for spec in mfd_button_specs("left"):
                        yield Button(spec.label, id=spec.button_id, compact=True)
                yield Static("", id="orionv-mfd-left-screen")
                yield Static("", id="orionv-mfd-right-screen")
                with Container(id="orionv-mfd-right-buttons"):
                    for spec in mfd_button_specs("right"):
                        yield Button(spec.label, id=spec.button_id, compact=True)
            with Container(id="orionv-cockpit-actions"):
                with Container(classes="orionv-cockpit-action-row"):
                    yield Button("", id="orionv-cockpit-jump-navigation", compact=True)
                    yield Button("", id="orionv-cockpit-jump-docking", compact=True)
                    yield Button("", id="orionv-cockpit-jump-power", compact=True)
                    yield Button("", id="orionv-cockpit-jump-thermal", compact=True)
                with Container(classes="orionv-cockpit-action-row"):
                    yield Button("", id="orionv-cockpit-jump-comms", compact=True)
                    yield Button("", id="orionv-cockpit-jump-incidents", compact=True)
                    yield Button("", id="orionv-cockpit-jump-procedures", compact=True)
                    yield Button("", id="orionv-cockpit-qiki-confirm", variant="primary", compact=True)
                    yield Button("", id="orionv-cockpit-qiki-cancel", compact=True)
                with Container(classes="orionv-cockpit-action-row"):
                    yield Button("", id="orionv-cockpit-loop-prev", compact=True)
                    yield Button("", id="orionv-cockpit-loop-preview", compact=True)
                    yield Button("", id="orionv-cockpit-loop-apply", variant="primary", compact=True)
                    yield Button("", id="orionv-cockpit-loop-next", compact=True)
                with Container(classes="orionv-cockpit-action-row"):
                    yield Button("Panel ▲", id="orionv-cockpit-focus-prev", compact=True)
                    yield Button("Help", id="orionv-cockpit-help-toggle", compact=True)
                    yield Button("Panel ▼", id="orionv-cockpit-focus-next", compact=True)
            yield Static("", id="orionv-mfd-qiki")
            yield Static("", id="orionv-cockpit-body")
            yield Static("", id="orionv-cockpit-intervention")

    def on_mount(self) -> None:
        for selector, title, subtitle in (
            ("#orionv-mfd-status", "ORION MFD / ГЛАВНЫЙ ЭКРАН", "правда | контекст | готовность"),
            ("#orionv-mfd-left-screen", "ЛЕВЫЙ MFD", "внешний мир | радар | навигация"),
            ("#orionv-mfd-right-screen", "ПРАВЫЙ MFD", "тело QIKI | системы | улики"),
            ("#orionv-mfd-qiki", "QIKI / ОПЕРАТОР", "решение | подтверждение | доказательства"),
        ):
            try:
                panel = self.query_one(selector, Static)
                panel.border_title = title
                panel.border_subtitle = subtitle
            except NoMatches:
                pass
        try:
            actions = self.query_one("#orionv-cockpit-actions", Container)
            actions.border_title = "SOFTKEYS / ПЕРЕХОДЫ"
            actions.border_subtitle = "left/right MFD restored"
        except NoMatches:
            pass
        for selector, title, subtitle in (
            ("#orionv-cockpit-body", "LEGACY F1 ANCHOR", "hidden compatibility surface"),
            ("#orionv-cockpit-intervention", "LEGACY QIKI ANCHOR", "hidden compatibility surface"),
        ):
            try:
                panel = self.query_one(selector, Static)
                panel.border_title = title
                panel.border_subtitle = subtitle
            except NoMatches:
                pass
        self._set_mfd_button_classes()
        self._refresh_text()

    def set_state(
        self,
        *,
        telemetry: dict[str, Any],
        nats_connected: bool,
        active_incidents: int,
        incidents: list[dict[str, str]] | None = None,
        safe_mode: dict[str, Any] | None = None,
        observation_objective: dict[str, Any] | None = None,
        objective_event_lines: list[str] | None = None,
        qiki_response: QikiChatResponseV1 | None = None,
        qiki_pending_action_title: str | None = None,
        qiki_plan_preview_lines: list[str] | None = None,
        qiki_procedure_status: str | None = None,
        operator_shell_state: "OperatorShellState | None" = None,
        active_left_mfd_page: str | None = None,
        active_right_mfd_page: str | None = None,
        playable_loop_state: dict[str, Any] | None = None,
    ) -> None:
        self._prev_core_temp_c = self._pick_core_temp_c(self._telemetry)
        self._telemetry = telemetry
        self._nats_connected = nats_connected
        self._active_incidents = active_incidents
        self._incidents = incidents or []
        self._safe_mode = safe_mode or {}
        self._observation_objective = dict(observation_objective or {}) or None
        self._objective_event_lines = list(objective_event_lines or [])
        self._qiki_response = qiki_response
        self._qiki_pending_action_title = qiki_pending_action_title
        self._qiki_plan_preview_lines = list(qiki_plan_preview_lines or [])
        self._qiki_procedure_status = qiki_procedure_status
        self._operator_shell_state = operator_shell_state
        self._active_left_mfd_page = normalize_mfd_page("left", active_left_mfd_page or self._active_left_mfd_page)
        self._active_right_mfd_page = normalize_mfd_page("right", active_right_mfd_page or self._active_right_mfd_page)
        self._playable_loop_state = dict(playable_loop_state or self._playable_loop_state or {})
        self._refresh_text()

    def _refresh_text(self) -> None:
        tel = self._telemetry
        shell_state = self._operator_shell_state
        always_on = getattr(shell_state, "always_on", None)
        derived_state = getattr(shell_state, "derived", None)
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        energy_sev, energy_lines = self._energy_block(tel)
        motion_sev, motion_lines = self._motion_block(tel)
        comms_sev, comms_lines = self._comms_block(tel)
        thermal_sev, thermal_lines = self._thermal_block(tel)
        safety_sev, safety_lines = self._safety_block()
        objective_sev, objective_lines = self._objective_block()
        objective_facts_sev, objective_facts_lines = self._objective_facts_block()
        incidents_sev, incidents_lines = self._incidents_block()
        procedure_sev, procedure_lines = self._procedure_block(tel)
        qiki_sev, qiki_lines = self._qiki_block()
        docking_quick_sev = self._docking_quick_severity(tel)

        global_sev, global_reason = self._global_status(
            energy_sev=energy_sev,
            motion_sev=motion_sev,
            comms_sev=comms_sev,
            thermal_sev=thermal_sev,
            safety_sev=safety_sev,
            incidents_sev=incidents_sev,
            procedure_sev=procedure_sev,
            qiki_sev=qiki_sev,
        )
        scene_profile = self._resolve_scene_profile(tel)
        mode_sev, mode_lines = self._mode_context_block(
            scene_profile=scene_profile,
            global_sev=global_sev,
            global_reason=global_reason,
            objective_sev=objective_sev,
        )
        actions_sev, action_lines = self._available_actions_block(
            scene_profile=scene_profile,
            telemetry=tel,
            objective_severity=objective_sev,
            qiki_severity=qiki_sev,
            procedure_severity=procedure_sev,
            incidents_severity=incidents_sev,
        )
        process_sev, process_lines = self._current_process_block(
            procedure_severity=procedure_sev,
            objective_severity=objective_sev,
            objective_facts_severity=objective_facts_sev,
            procedure_lines=procedure_lines,
            objective_lines=objective_lines,
            objective_facts_lines=objective_facts_lines,
        )
        spatial_sev, spatial_lines = self._spatial_telemetry_block(
            telemetry=tel,
            motion_severity=motion_sev,
            motion_lines=motion_lines,
        )
        route_sev, route_lines = self._route_intent_block(
            scene_profile=scene_profile,
            objective_severity=objective_sev,
            objective_lines=objective_lines,
            objective_facts_lines=objective_facts_lines,
        )
        qiki_interp_sev, qiki_interp_lines = self._qiki_interpretation_block(
            qiki_severity=qiki_sev,
            qiki_lines=qiki_lines,
        )
        mission_sev, mission_lines = self._mission_context_block(
            scene_profile=scene_profile,
            global_sev=global_sev,
            global_reason=global_reason,
            objective_sev=objective_sev,
            objective_lines=objective_lines,
        )
        guidance_sev, guidance_lines = self._guidance_context_block(
            telemetry=tel,
            motion_severity=motion_sev,
            motion_lines=motion_lines,
        )
        incident_focus_sev, incident_focus_lines = self._mission_incident_block()
        support_sev, support_lines = self._mission_support_block(
            energy_severity=energy_sev,
            energy_lines=energy_lines,
            motion_severity=motion_sev,
            motion_lines=motion_lines,
            comms_severity=comms_sev,
            comms_lines=comms_lines,
            thermal_severity=thermal_sev,
            thermal_lines=thermal_lines,
            safety_severity=safety_sev,
            safety_lines=safety_lines,
            objective_facts_severity=objective_facts_sev,
            objective_facts_lines=objective_facts_lines,
        )
        body_structure_vm = get_body_structure_console_view_model()
        body_structure_line = format_body_structure_cockpit_line(body_structure_vm)
        body_physics_vm = get_body_physics_console_view_model(body_structure_vm)
        body_physics_line = format_body_physics_cockpit_line(body_physics_vm)
        power_thermal_vm = build_power_thermal_console_view_model_from_telemetry(self._telemetry)
        power_thermal_line = format_power_thermal_cockpit_line(power_thermal_vm)
        playable_loop_vm = build_cockpit_playable_loop_vm(
            loop_state=self._playable_loop_state,
            body_vm=body_structure_vm,
            body_physics_vm=body_physics_vm,
            power_vm=power_thermal_vm,
            active_left_mfd_page=self._active_left_mfd_page,
            active_right_mfd_page=self._active_right_mfd_page,
            nats_connected=self._nats_connected,
            active_incidents=self._active_incidents,
        )
        self._last_playable_loop_vm = playable_loop_vm
        playable_loop_lines = list(format_cockpit_playable_loop_lines(playable_loop_vm))
        qiki_reco_sev, qiki_reco_lines = self._qiki_recommendation_block(
            qiki_severity=qiki_sev,
            qiki_lines=qiki_lines,
            qiki_interpretation_lines=qiki_interp_lines,
        )
        intervention_sev, intervention_lines = self._operator_intervention_block(
            action_lines=action_lines,
            process_lines=process_lines,
            procedure_lines=procedure_lines,
            qiki_lines=qiki_lines,
            incidents_lines=incidents_lines,
        )

        body_text = "\n".join(
            [
                self._overview_line(global_sev, global_reason),
                body_structure_line,
                body_physics_line,
                power_thermal_line,
                self._section_divider(),
                *self._panel_block(
                    "Общий статус",
                    self._global_state_rows(
                        scene_profile=scene_profile,
                        global_severity=global_sev,
                        objective=objective,
                    ),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Контекст миссии",
                    self._mission_context_rows(
                        always_on=always_on,
                        objective=objective,
                        scene_profile=scene_profile,
                    ),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Наведение",
                    self._guidance_rows(
                        telemetry=tel,
                        guidance_severity=guidance_sev,
                        derived_state=derived_state,
                    ),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Инциденты",
                    self._incident_rows(incident_focus_severity=incident_focus_sev),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Маршрут и цель",
                    self._route_rows(
                        objective=objective,
                        route_severity=route_sev,
                        scene_profile=scene_profile,
                    ),
                ),
                self._section_divider(),
                *self._dim_block(
                    self._section_title(
                        "Краткие факты",
                        _merge_severity(objective_sev, support_sev),
                    ),
                    [
                        *objective_lines[:2],
                        *objective_facts_lines[:1],
                        self._quick_fact_row(
                            "SAFETY",
                            safety_sev,
                            self._compact_fact_detail(safety_lines[0], "Статус: "),
                            self._compact_fact_detail(safety_lines[1], "Причина: "),
                        ),
                        self._quick_fact_row(
                            "ENERGY",
                            energy_sev,
                            self._compact_fact_detail(energy_lines[0], "Заряд/SOC: "),
                            self._compact_fact_detail(energy_lines[1], "Шина/Bus: "),
                        ),
                        self._quick_fact_row(
                            "THERMAL",
                            thermal_sev,
                            self._compact_fact_detail(thermal_lines[0], "Core: "),
                            self._compact_fact_detail(thermal_lines[1], "Radiator/Sink: "),
                        ),
                        self._compact_fact_detail(
                            next((ln for ln in thermal_lines if ln.startswith("• Core:")), "")
                        ),
                        self._compact_fact_detail(
                            next((ln for ln in thermal_lines if ln.startswith("• TRIP nodes:")), "")
                        ),
                        *(
                            self._compact_fact_detail(ln)
                            for ln in thermal_lines
                            if ln.startswith("• Узлы/Nodes") or ln.lstrip().startswith("▪")
                        ),
                        self._compact_fact_detail(
                            next((ln for ln in energy_lines if ln.startswith("• Причины сброса:")), "")
                        ),
                    ],
                ),
            ]
        )
        fallback_body_text = "\n".join(
            [
                body_text,
                self._section_divider(),
                *self._dim_block(
                    self._section_title(
                        "Краткие факты",
                        _merge_severity(objective_sev, support_sev),
                    ),
                    [
                        "Body Structure:",
                        body_structure_line,
                        "Body Physics:",
                        body_physics_line,
                        "Power / Thermal:",
                        power_thermal_line,
                        "Цель наблюдения:",
                        *objective_lines,
                        "Связанные факты:",
                        *objective_facts_lines,
                        *spatial_lines,
                        *support_lines,
                        *safety_lines,
                        *mode_lines,
                        *route_lines,
                        *mission_lines,
                        *guidance_lines,
                        *incident_focus_lines,
                    ],
                ),
            ]
        )
        intervention_text = "\n".join(
            [
                *self._panel_block(
                    "F1 / Первый живой цикл",
                    playable_loop_lines,
                ),
                self._section_divider(),
                *self._panel_block(
                    "QIKI / Решение",
                    self._qiki_recommendation_rows(
                        qiki_severity=qiki_reco_sev,
                        qiki_lines=qiki_reco_lines,
                    ),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Оператор / Действие",
                    self._operator_intervention_rows(
                        next_step=self._pick_next_step(qiki_lines, procedure_lines, process_lines),
                    ),
                ),
                self._section_divider(),
                *self._panel_block(
                    "Процесс / Контур",
                    self._process_state_rows(
                        process_severity=process_sev,
                        procedure_status=self._qiki_procedure_status,
                        scene_profile=scene_profile,
                    ),
                    extras=None,
                ),
            ]
        )
        fallback_intervention_text = "\n".join(
            [
                "QIKI, действие, контур.",
                self._section_divider(),
                intervention_text,
                self._section_divider(),
                *self._dim_block(
                    self._section_title(
                        "Контекст решения",
                        _merge_severity(process_sev, qiki_interp_sev),
                    ),
                    [
                        *process_lines,
                        "Процедура:",
                        *qiki_interp_lines,
                        *procedure_lines,
                        *intervention_lines,
                        *qiki_reco_lines,
                        *action_lines,
                    ],
                ),
            ]
        )
        self._set_panel_texts(
            body_text=body_text,
            intervention_text=intervention_text,
            fallback_body_text=fallback_body_text,
            fallback_intervention_text=fallback_intervention_text,
        )
        self._refresh_actions(
            energy_sev=energy_sev,
            motion_sev=motion_sev,
            docking_sev=docking_quick_sev,
            comms_sev=comms_sev,
            thermal_sev=thermal_sev,
            incidents_sev=incidents_sev,
            procedure_sev=procedure_sev,
            qiki_sev=qiki_sev,
        )
        self._refresh_playable_loop_buttons(playable_loop_vm)

    def _set_panel_texts(
        self,
        *,
        body_text: str,
        intervention_text: str,
        fallback_body_text: str | None = None,
        fallback_intervention_text: str | None = None,
    ) -> None:
        self._fallback_body_text = fallback_body_text or body_text
        self._fallback_intervention_text = fallback_intervention_text or intervention_text

        # Hidden legacy anchors are kept for app/test compatibility, but the visible
        # cockpit is again a left/right MFD shell.  The MFD panes are display-only
        # projections of already-derived view-model text; they do not create state.
        self._set_body_text(body_text)
        self._set_static_text("#orionv-cockpit-intervention", intervention_text)
        self._set_static_text("#orionv-mfd-status", self._compose_mfd_status_text(body_text))
        self._set_static_text("#orionv-mfd-left-screen", self._compose_left_mfd_text(body_text))
        self._set_static_text("#orionv-mfd-right-screen", self._compose_right_mfd_text(body_text))
        self._set_static_text("#orionv-mfd-qiki", self._compose_mfd_qiki_text(intervention_text))

    def _set_static_text(self, selector: str, text: str) -> None:
        try:
            semantic_update(
                self.query_one(selector, Static),
                text,
                domain=self._visual_domain(selector),
            )
        except NoMatches:
            if selector == "#orionv-cockpit-body":
                combined = "\n\n".join(
                    part for part in [self._fallback_body_text or text, self._fallback_intervention_text] if part
                )
                self.update(combined)

    @staticmethod
    def _visual_domain(selector: str) -> str:
        if "left" in selector:
            return "left"
        if "right" in selector:
            return "right"
        if "qiki" in selector or "intervention" in selector:
            return "qiki"
        return "status"

    def _set_body_text(self, text: str) -> None:
        self._set_static_text("#orionv-cockpit-body", text)

    def _compose_mfd_status_text(self, body_text: str) -> str:
        body_vm = get_body_structure_console_view_model()
        physics_vm = get_body_physics_console_view_model(body_vm)
        power_vm = build_power_thermal_console_view_model_from_telemetry(self._telemetry)
        status = render_status_strip(
            mode="КОКПИТ",
            body=f"{body_seed_status_ru(body_vm.seed_status, body_vm.runtime_ready)} | модулей: {body_vm.attached_modules_count}",
            evidence=body_vm.trust_status or "missing",
            source="аудит/локальный посев",
        )
        lines = [status]
        # full body/physics/power lines only when the right MFD does not already
        # show them (page "systems" carries all three sections); default view
        # keeps the status box to the one-line delta strip
        if normalize_mfd_page("right", self._active_right_mfd_page) != "systems":
            lines.append(format_body_structure_cockpit_line(body_vm))
            lines.append(format_body_physics_cockpit_line(physics_vm))
            lines.append(format_power_thermal_cockpit_line(power_vm))
        return "\n".join(lines)

    def _compose_left_mfd_text(self, body_text: str) -> str:
        page = normalize_mfd_page("left", self._active_left_mfd_page)
        page_label = mfd_page_label("left", page)
        lines = body_text.splitlines()
        marker_map: dict[str, tuple[str, ...]] = {
            "radar": ("Общий статус", "Сенсоры", "Инциденты"),
            "nav": ("Наведение", "Маршрут и цель", "Текущий процесс"),
            "target": ("Маршрут и цель", "Контекст миссии", "Цель"),
            "sector": ("Контекст миссии", "Поддержка миссии", "Инциденты"),
            "mission": ("Контекст миссии", "Текущий процесс", "Доступные действия"),
        }
        wanted = _extract_mfd_sections(lines, marker_map.get(page, ()), chunk=6, limit=18)
        if not wanted:
            wanted = lines[:18]
        return "\n".join(
            [
                f"ЛЕВЫЙ MFD / {page_label}",
                "источник: телеметрия/цель/оболочка | фактов не выдумываем",
                *section_lines(_left_mfd_page_title(page), wanted, limit=18),
            ]
        )

    def _compose_right_mfd_text(self, body_text: str) -> str:
        page = normalize_mfd_page("right", self._active_right_mfd_page)
        page_label = mfd_page_label("right", page)
        body_vm = get_body_structure_console_view_model()
        physics_vm = get_body_physics_console_view_model(body_vm)
        power_vm = build_power_thermal_console_view_model_from_telemetry(self._telemetry)
        module = body_vm.module_id or "none"
        body_rows = [
            f"Корпус: {body_seed_status_ru(body_vm.seed_status, body_vm.runtime_ready)} | граней: {body_vm.faces_total} | выбрана: {body_vm.selected_face_id}",
            f"Модуль: {module} | гнездо: {body_vm.mount_point} | решение: {state_ru(body_vm.last_decision)}",
            f"Паспорт: {state_ru(body_vm.passport_status)} | способность: {state_ru(body_vm.capability_status)} | "
            f"готов к работе: {'да' if body_vm.runtime_ready else 'нет'}",
            f"Улика: {body_vm.evidence_card_type or 'нет'} | доверие: {body_vm.trust_status}",
        ]
        physics_rows = [
            f"Физика: {physics_vm.evidence_card_type}",
            f"масса: {phys_ru(physics_vm.mass_state)} | ЦМ: {phys_ru(physics_vm.com_delta_class)} | инерция: {phys_ru(physics_vm.inertia_class)}",
            f"карта тяги: {phys_ru(physics_vm.thrust_map_status)} | карта момента: {phys_ru(physics_vm.torque_map_status)}",
            f"доверие: {physics_vm.trust_status} | runtime: {physics_vm.runtime_conformance}",
        ]
        power_rows = [
            f"Power({power_vm.source}): SoC_bat={format_soc_bat(power_vm.battery_soc_pct)} | "
            f"SoC_cap={format_soc_cap(power_vm.supercap_soc_pct)} | bus={power_vm.bus_state}",
            f"Пик: {state_ru(power_vm.peak_readiness)} | тепло: {state_ru(power_vm.thermal_status)}",
            f"Заблокировано: {', '.join(power_vm.blocked_commands) if power_vm.blocked_commands else 'нет'}",
            f"Runtime: {power_vm.runtime_conformance} | источник: {power_vm.source}",
        ]
        thermal_rows = [
            f"Thermal status: {power_vm.thermal_status}",
            *(
                f"{node.node_id}: {node.thermal_class} | "
                f"blocked={', '.join(node.blocked_commands) if node.blocked_commands else 'none'}"
                for node in power_vm.thermal_nodes
            ),
            f"Runtime: {power_vm.runtime_conformance}",
        ]
        body_lines = body_text.splitlines()
        subsystem_sections: dict[str, list[str]] = {
            "systems": [
                *section_lines("Корпус / Структура", body_rows, limit=8),
                "",
                *section_lines("Физические последствия", physics_rows, limit=8),
                "",
                *section_lines("Питание / Тепло", power_rows, limit=8),
            ],
            "sensors": [
                *section_lines(
                    "Sensors / Trust",
                    _extract_mfd_sections(body_lines, ("Сенсоры", "sensor", "Observation"), chunk=5, limit=14),
                    limit=14,
                ),
                "sensor page is a projection; no sensor truth is invented by MFD",
            ],
            "power": [*section_lines("Power", power_rows, limit=10)],
            "thermal": [*section_lines("Thermal", thermal_rows, limit=12)],
            "comms": [
                *section_lines(
                    "Comms",
                    _extract_mfd_sections(body_lines, ("Связь", "comms", "link"), chunk=5, limit=14),
                    limit=14,
                ),
                "normal comms and NBL remain separate evidence domains",
            ],
            "propulsion": [
                *section_lines(
                    "Propulsion / Motion",
                    _extract_mfd_sections(body_lines, ("Движение", "Наведение", "motion"), chunk=5, limit=14),
                    limit=14,
                ),
                *section_lines("Физика корпуса (ожидается)", physics_rows, limit=6),
            ],
            "docking": [
                *section_lines(
                    "Docking",
                    _extract_mfd_sections(body_lines, ("Стыков", "Dock", "док"), chunk=5, limit=14),
                    limit=14,
                ),
                "bridge/power/data remain gated; MFD does not enable docking runtime",
            ],
            "journal": [
                "Journal / Audit",
                "audit/evidence detail lives on F8",
                "ACK is not effect confirmation",
                "current page is read-only cockpit projection",
            ],
            "procedures": [
                "Procedures",
                "procedure execution remains command-lifecycle gated",
                "use F6/F8 for audit/evidence history",
                "MFD page selection does not execute procedures",
            ],
        }
        return "\n".join(
            [
                f"ПРАВЫЙ MFD / {page_label}",
                "станция улик: только чтение, не источник истины",
                *subsystem_sections.get(page, subsystem_sections["systems"]),
            ]
        )

    def _compose_mfd_qiki_text(self, intervention_text: str) -> str:
        return "\n".join(
            [
                softkey_bar(),
                "─" * 48,
                *intervention_text.splitlines()[:26],
            ]
        )

    def _set_mfd_button_classes(self) -> None:
        for spec in (*mfd_button_specs("left"), *mfd_button_specs("right")):
            try:
                button = self.query_one(f"#{spec.button_id}", Button)
            except NoMatches:
                continue
            button.set_classes(
                mfd_button_class(
                    spec,
                    active_left=self._active_left_mfd_page,
                    active_right=self._active_right_mfd_page,
                )
            )

    def _refresh_actions(
        self,
        *,
        energy_sev: str,
        motion_sev: str,
        docking_sev: str,
        comms_sev: str,
        thermal_sev: str,
        incidents_sev: str,
        procedure_sev: str,
        qiki_sev: str,
    ) -> None:
        button_specs = (
            ("#orionv-cockpit-jump-navigation", "Маршрут", motion_sev, "F2"),
            ("#orionv-cockpit-jump-docking", "Стыковка", docking_sev, "F2"),
            ("#orionv-cockpit-jump-power", "Питание", energy_sev, "F2"),
            ("#orionv-cockpit-jump-comms", "Связь", comms_sev, "F2"),
            ("#orionv-cockpit-jump-thermal", "Тепло", thermal_sev, "F2"),
            ("#orionv-cockpit-jump-incidents", "Инциденты", incidents_sev, "F3"),
            ("#orionv-cockpit-jump-procedures", "Процедуры", procedure_sev, "F6"),
        )
        for selector, title, severity, target in button_specs:
            try:
                button = self.query_one(selector, Button)
            except NoMatches:
                continue
            button.label = f"{title} {self._button_state_label(severity)} · {target}"
            button.variant = self._button_variant(severity)
            button.disabled = False

        confirm_enabled = self._qiki_pending_action_title is not None
        for selector, enabled_label, disabled_label in (
            (
                "#orionv-cockpit-qiki-confirm",
                "Подтвердить QIKI",
                "Подтвердить QIKI",
            ),
            (
                "#orionv-cockpit-qiki-cancel",
                "Отменить QIKI",
                "Отменить QIKI",
            ),
        ):
            try:
                button = self.query_one(selector, Button)
            except NoMatches:
                continue
            button.display = confirm_enabled
            button.disabled = not confirm_enabled
            button.variant = self._button_variant(qiki_sev) if confirm_enabled else "default"
            button.label = enabled_label if confirm_enabled else disabled_label

        self._set_mfd_button_classes()

    def _refresh_playable_loop_buttons(self, playable_loop_vm) -> None:
        for suffix, label, highlighted in format_cockpit_playable_action_labels(playable_loop_vm):
            try:
                button = self.query_one(f"#orionv-cockpit-loop-{suffix}", Button)
            except NoMatches:
                continue
            button.label = label
            button.disabled = False
            button.variant = "primary" if highlighted else "default"
        focus_buttons = (
            ("#orionv-cockpit-focus-prev", "Panel ▲"),
            ("#orionv-cockpit-help-toggle", "Help · ON" if playable_loop_vm.help_visible else "Help · OFF"),
            ("#orionv-cockpit-focus-next", "Panel ▼"),
        )
        for selector, label in focus_buttons:
            try:
                button = self.query_one(selector, Button)
            except NoMatches:
                continue
            button.label = label
            button.disabled = False
            button.variant = (
                "primary"
                if selector.endswith("help-toggle") and playable_loop_vm.help_visible
                else "default"
            )

    def _mission_context_block(
        self,
        *,
        scene_profile: str,
        global_sev: str,
        global_reason: str,
        objective_sev: str,
        objective_lines: list[str],
    ) -> tuple[str, list[str]]:
        state = self._operator_shell_state
        always_on = getattr(state, "always_on", None)
        derived = getattr(state, "derived", None)
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        target = (
            str(
                objective.get("public_track_label")
                or objective.get("track_label")
                or objective.get("target_designator")
                or ""
            ).strip()
            or "нет активной цели"
        )
        objective_title = (
            str(objective.get("title_ru") or objective.get("summary_ru") or "").strip()
            or "mission intent не объявлен"
        )
        route_role = str(objective.get("route_role") or "").strip().lower() or "none"
        follow_up = str(objective.get("follow_up_status") or "").strip().lower() or "none"
        result_status = str(objective.get("observation_result_status") or "").strip().lower() or "none"
        lines = [
            (
                "Mission phase: "
                f"{getattr(always_on, 'mission_phase', None) or 'partial: runtime-derived'} "
                f"| scene={scene_profile}"
            ),
            f"Objective / intent: {objective_title}",
            f"Target / route context: {target} | route_role={route_role} | follow_up={follow_up}",
            (
                "Mission risk / authority: "
                f"{getattr(derived, 'mission_risk_state', None) or 'partial'} | "
                f"{getattr(always_on, 'control_authority', None) or 'нет'}"
            ),
            f"Mission flow: {global_reason}",
        ]
        if result_status != "none":
            lines.append(f"Observation result: {result_status}")
        if objective_lines:
            meaning = next((line for line in objective_lines if line.startswith("Смысл/Meaning: ")), None)
            if meaning is not None:
                lines.append(meaning)
        lines.append(
            "Truth note: dedicated mission-phase/guidance contract is still partial; "
            "F1 uses the current shell contract and objective truth only."
        )
        return _merge_severity(global_sev, objective_sev), lines

    def _guidance_context_block(
        self,
        *,
        telemetry: dict[str, Any],
        motion_severity: str,
        motion_lines: list[str],
    ) -> tuple[str, list[str]]:
        state = self._operator_shell_state
        always_on = getattr(state, "always_on", None)
        derived = getattr(state, "derived", None)
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        track_distance = objective.get("track_range_m")
        if not isinstance(track_distance, (int, float)):
            track_distance = _pick_num(telemetry, ["docking", "distance_m"])
        closing_rate = _pick_num(telemetry, ["docking", "approach_mps"])
        if closing_rate is None:
            closing_rate = _pick_num(telemetry, ["docking", "rel_speed_mps"])
        guidance_state = (
            getattr(always_on, "autopilot_mode", None)
            or getattr(always_on, "autopilot_status", None)
            or _pick_text(telemetry, ["guidance", "state"])
            or _pick_text(telemetry, ["docking", "state"])
            or getattr(always_on, "vehicle_mode", None)
            or "partial: no dedicated guidance state"
        )
        target_distance_text = (
            _fmt_unit(float(track_distance), "м", ".1f")
            if isinstance(track_distance, (int, float))
            else "partial: no target distance"
        )
        lines = [
            f"Target distance: {target_distance_text}",
            (
                "ETA / closing rate: "
                f"{getattr(derived, 'eta_to_target', None) or 'partial: no ETA'} | "
                f"{_fmt_unit(closing_rate, 'м/с', '.2f')}"
            ),
            f"Guidance state: {guidance_state}",
            (
                "Attitude / maneuver: "
                f"{getattr(derived, 'attitude_stability', None) or 'partial'} | "
                f"maneuver={getattr(derived, 'maneuver_feasibility', None) or 'partial'}"
            ),
            (
                "Route deviation / commandability: "
                f"{getattr(derived, 'trajectory_deviation', None) or 'partial'} | "
                f"{getattr(derived, 'commandability_state', None) or 'partial'}"
            ),
        ]
        if getattr(always_on, "unavailable_fields", ()) or getattr(derived, "unavailable_fields", ()):
            missing = sorted(
                {
                    field
                    for field in (
                        *getattr(always_on, "unavailable_fields", ()),
                        *getattr(derived, "unavailable_fields", ()),
                    )
                    if field in {"autopilot_status", "autopilot_mode", "collision_imminent", "fuel_margin_to_plan"}
                }
            )
            if missing:
                lines.append(f"Known guidance gaps: {', '.join(missing)}")
        lines.extend(motion_lines[:3])
        return motion_severity, lines

    def _mission_incident_block(self) -> tuple[str, list[str]]:
        state = self._operator_shell_state
        alert_summary = getattr(getattr(state, "always_on", None), "alert_summary", None)
        focus_alert = getattr(alert_summary, "selected_critical_alert", None) or getattr(
            alert_summary, "focus_alert", None
        )
        if focus_alert is not None:
            lines = [
                f"Focused alert: {focus_alert.title} | sev={focus_alert.severity}",
                f"Mission effect: {focus_alert.operator_effect}",
                f"Next hint: {focus_alert.next_action_hint or 'monitor and keep command path clear'}",
            ]
            if focus_alert.incident_id:
                lines.append(f"Linked incident: {focus_alert.incident_id}")
            return {
                "critical": "crit",
                "warning": "warn",
                "attention": "degraded",
            }.get(focus_alert.severity, "ok"), lines
        severity, incident_lines = self._incidents_block()
        return severity, [
            "No selected mission-blocking alert inside the shell summary.",
            *incident_lines,
        ]

    def _mission_support_block(
        self,
        *,
        energy_severity: str,
        energy_lines: list[str],
        motion_severity: str,
        motion_lines: list[str],
        comms_severity: str,
        comms_lines: list[str],
        thermal_severity: str,
        thermal_lines: list[str],
        safety_severity: str,
        safety_lines: list[str],
        objective_facts_severity: str,
        objective_facts_lines: list[str],
    ) -> tuple[str, list[str]]:
        severity = _merge_severity(energy_severity, comms_severity)
        severity = _merge_severity(severity, motion_severity)
        severity = _merge_severity(severity, thermal_severity)
        severity = _merge_severity(severity, safety_severity)
        severity = _merge_severity(severity, objective_facts_severity)
        return severity, [
            "Энергия:",
            *energy_lines,
            "Движение и навигация:",
            *motion_lines,
            "Связь:",
            *comms_lines,
            "Температура:",
            *thermal_lines,
            f"Безопасность: {self._severity_markup(safety_severity)}",
            *safety_lines,
            "Связанные факты:",
            *objective_facts_lines,
        ]

    def _qiki_recommendation_block(
        self,
        *,
        qiki_severity: str,
        qiki_lines: list[str],
        qiki_interpretation_lines: list[str],
    ) -> tuple[str, list[str]]:
        if self._qiki_response is None and not self._qiki_pending_action_title and not self._qiki_plan_preview_lines:
            return qiki_severity, [
                "QIKI:",
                "Статус/Status: idle",
                "Следующий шаг/Next: q: <команда>",
            ]
        state = self._operator_shell_state
        always_on = getattr(state, "always_on", None)
        derived = getattr(state, "derived", None)
        lines = [
            "QIKI:",
            (
                "Autonomy confidence: "
                f"{getattr(derived, 'autonomy_confidence', None) or 'partial'} | "
                f"qiki_assist={getattr(always_on, 'qiki_assist_status', None) or 'partial'}"
            ),
            (
                "Human acknowledgement required: "
                f"{'yes' if getattr(always_on, 'human_ack_required', False) else 'no'} | "
                f"intervention_required={'yes' if getattr(derived, 'intervention_required', False) else 'no'}"
            ),
        ]
        lines.extend(qiki_lines)
        if qiki_interpretation_lines:
            lines.append("Interpretation:")
            lines.extend(qiki_interpretation_lines)
        return qiki_severity, lines

    def _operator_intervention_block(
        self,
        *,
        action_lines: list[str],
        process_lines: list[str],
        procedure_lines: list[str],
        qiki_lines: list[str],
        incidents_lines: list[str],
    ) -> tuple[str, list[str]]:
        state = self._operator_shell_state
        loop = getattr(state, "operator_loop", None)
        next_step = self._pick_next_step(qiki_lines, procedure_lines, process_lines)
        lines = [
            (
                "Контур команды: "
                f"{getattr(loop, 'last_command_status', 'idle')} | "
                f"pending={getattr(loop, 'pending_command_count', 0)} | "
                f"mode={getattr(loop, 'command_mode_state', 'standby')}"
            ),
            f"Последняя команда: {getattr(loop, 'last_command_summary', 'Команда ещё не подавалась')}",
            f"Требуется действие: {'да' if getattr(loop, 'operator_action_required', False) else 'нет'}",
            f"Контекст команд: {getattr(loop, 'status_text', 'Команды: help')}",
            f"Горячие клавиши: {getattr(loop, 'hotkey_context', 'F1/F2/F3/F4/F6/F7 переключают уровни')}",
            f"Следующий шаг: {next_step}",
        ]
        if getattr(loop, "selected_incident_id", None):
            lines.append(f"Выбранный инцидент: {getattr(loop, 'selected_incident_id')}")
        if getattr(loop, "selected_subsystem", None):
            lines.append(f"Выбранная подсистема: {getattr(loop, 'selected_subsystem')}")
        if incidents_lines:
            lines.append(incidents_lines[-1])
        return (
            "crit" if getattr(loop, "operator_action_required", False) else "ok",
            lines,
        )

    def _pick_next_step(self, *blocks: list[str]) -> str:
        for block in blocks:
            for line in block:
                if line.startswith(_NEXT_STEP_PREFIX):
                    return line.removeprefix(_NEXT_STEP_PREFIX).strip()
        return "держите контур под контролем и готовьте следующую команду"

    @staticmethod
    def _button_variant(severity: str) -> str:
        return {
            "crit": "error",
            "warn": "warning",
            "degraded": "warning",
            "ok": "success",
        }.get(severity, "default")

    @staticmethod
    def _button_state_label(severity: str) -> str:
        return {
            "crit": "КРИТ",
            "warn": "ВНИМ",
            "degraded": "ПАУЗА",
            "ok": "OK",
        }.get(severity, "INFO")

    def _resolve_scene_profile(self, tel: dict[str, Any]) -> str:
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        route_role = str(objective.get("route_role") or "").strip().lower()
        objective_status = str(objective.get("status") or "").strip().lower()
        procedure_name = str(objective.get("procedure_name") or "").strip().lower()
        docking_state = _pick_text(tel, ["docking", "state"]).strip().lower()
        docking_connected = _pick_bool(tel, ["docking", "connected"]) is True
        orbit_state = _pick_text(tel, ["orbit", "state"]).strip().lower()

        if route_role in {"official", "deviation"} or procedure_name in {
            "safe_pause_resume",
            "safe_pause_slow_resume",
            "hostile_rcs_intercept_burst",
        }:
            return "route_transit"
        if docking_connected or docking_state in {"docked", "capture", "approach", "charging", "undocking"}:
            return "docked"
        if orbit_state in {"hold", "orbital_hold", "orbit_hold", "stable_orbit"}:
            return "orbital_hold"
        if objective_status in {"prepared", "confirmed"} and procedure_name:
            return "route_transit"
        return "free_flight"

    def _mode_context_block(
        self,
        *,
        scene_profile: str,
        global_sev: str,
        global_reason: str,
        objective_sev: str,
    ) -> tuple[str, list[str]]:
        profile_titles = {
            "docked": "Docked / Station",
            "free_flight": "Free Flight",
            "orbital_hold": "Orbital Hold / Maneuver",
            "route_transit": "Route Transit",
        }
        mode_title = profile_titles.get(scene_profile, "Free Flight")
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        objective_status = str(objective.get("status") or "none").strip().lower() or "none"
        follow_up_status = str(objective.get("follow_up_status") or "none").strip().lower() or "none"
        lines = [
            f"Профиль сцены/Scene profile: {scene_profile} ({mode_title})",
            "Режимы каркаса/F1 profiles: docked | free_flight | orbital_hold | route_transit",
            f"Контекст системы/System context: {global_reason}",
            f"Цель/Objective context: status={objective_status} | follow_up={follow_up_status}",
        ]
        return _merge_severity(global_sev, objective_sev), lines

    def _available_actions_block(
        self,
        *,
        scene_profile: str,
        telemetry: dict[str, Any],
        objective_severity: str,
        qiki_severity: str,
        procedure_severity: str,
        incidents_severity: str,
    ) -> tuple[str, list[str]]:
        docking_state = _pick_text(telemetry, ["docking", "state"]).strip().lower()
        link_state = _pick_text(telemetry, ["comms", "link"]).strip().lower()
        orbit_state = _pick_text(telemetry, ["orbit", "state"]).strip().lower()
        pending_title = (self._qiki_pending_action_title or "").strip()
        profile_defaults: dict[str, list[tuple[str, bool, str, str, str]]] = {
            "docked": [
                (
                    "Запросить отстыковку/Request undock",
                    docking_state in {"docked", "capture", "charging"},
                    f"docking.state={docking_state or 'unknown'}",
                    "medium",
                    "Переход в free_flight при подтверждении",
                ),
                (
                    "Диагностика/Diagnostics",
                    True,
                    "Доступно всегда",
                    "low",
                    "Переход в F2 системные детали",
                ),
                (
                    "Завершить зарядку/Finish charging",
                    docking_state in {"docked", "charging"},
                    f"docking.state={docking_state or 'unknown'}",
                    "low",
                    "Снятие station power limits",
                ),
                (
                    "Открыть канал/Hail station",
                    link_state in {"online", "up"},
                    f"comms.link={link_state or 'unknown'}",
                    "low",
                    "Подтверждение station protocol",
                ),
            ],
            "free_flight": [
                (
                    "Стабилизация/Attitude hold",
                    True,
                    "IMU/trust проверяются QIKI в рантайме",
                    "low",
                    "Удержание ориентации для безопасного манёвра",
                ),
                (
                    "Запуск маршрута/Start route transit",
                    True,
                    "Требуется цель и QIKI intent",
                    "medium",
                    "Переход в route_transit контур",
                ),
            ],
            "orbital_hold": [
                (
                    "Коррекция орбиты/Orbit correction",
                    orbit_state not in {"", "off", "failed"},
                    f"orbit.state={orbit_state or 'unknown'}",
                    "medium",
                    "Стабилизация orbital hold параметров",
                ),
                (
                    "Удержание орбиты/Hold orbit",
                    True,
                    "Базовый режим orbital safety",
                    "low",
                    "Снижение drift и расхода",
                ),
            ],
            "route_transit": [
                (
                    "Продолжить маршрут/Continue route",
                    True,
                    "Контур активен",
                    "medium",
                    "Движение к destination по текущему профилю",
                ),
                (
                    "Режим hold/Hold for review",
                    True,
                    "Доступен через follow-up path",
                    "medium",
                    "Пауза контекста для проверки риска",
                ),
                (
                    "Возобновить/Resume",
                    True,
                    "Доступен после hold/review",
                    "medium",
                    "Возврат в route_transit/safe observation",
                ),
            ],
        }
        cards = list(profile_defaults.get(scene_profile, profile_defaults["free_flight"]))
        qiki_allowed = bool(pending_title)
        cards.insert(
            0,
            (
                f"QIKI confirm ({pending_title or 'нет action'})",
                qiki_allowed,
                "Есть pending action от QIKI" if qiki_allowed else "Нет pending action",
                "high" if qiki_allowed else "low",
                "Подтверждённое исполнение QIKI plan" if qiki_allowed else "Ожидание новой QIKI команды",
            ),
        )
        cards.insert(
            1,
            (
                "QIKI cancel",
                qiki_allowed,
                "Можно снять pending action" if qiki_allowed else "Нет action для отмены",
                "low",
                "Снятие подготовленного действия",
            ),
        )
        lines = [
            (
                f"• card: label={label} | {'allowed' if allowed else 'blocked'} | "
                f"reason={reason} | risk={risk} | expected={expected}"
            )
            for label, allowed, reason, risk, expected in cards[:5]
        ]
        severity = _merge_severity(objective_severity, qiki_severity)
        severity = _merge_severity(severity, procedure_severity)
        severity = _merge_severity(severity, incidents_severity)
        return severity, lines

    def _current_process_block(
        self,
        *,
        procedure_severity: str,
        objective_severity: str,
        objective_facts_severity: str,
        procedure_lines: list[str],
        objective_lines: list[str],
        objective_facts_lines: list[str],
    ) -> tuple[str, list[str]]:
        lines: list[str] = []
        lines.extend(procedure_lines[:4])
        if procedure_lines:
            lines.extend(objective_lines[:3])
        if objective_facts_lines:
            lines.append("Linked facts:")
            lines.extend(f"  {line}" for line in objective_facts_lines[:2])
        if not lines:
            lines = ["Статус/Status: процесс не активен", f"{_NEXT_STEP_PREFIX} задайте QIKI intent"]
        severity = _merge_severity(procedure_severity, objective_severity)
        severity = _merge_severity(severity, objective_facts_severity)
        return severity, lines

    def _spatial_telemetry_block(
        self,
        *,
        telemetry: dict[str, Any],
        motion_severity: str,
        motion_lines: list[str],
    ) -> tuple[str, list[str]]:
        lines: list[str] = []
        pos_x = _pick_num(telemetry, ["position", "x"])
        pos_y = _pick_num(telemetry, ["position", "y"])
        pos_z = _pick_num(telemetry, ["position", "z"])
        speed = _pick_num(telemetry, ["speed_m_s"])
        if speed is None:
            speed = _pick_num(telemetry, ["velocity"])
        target_distance = _pick_num(telemetry, ["docking", "distance_m"])
        target_name = _pick_text(telemetry, ["docking", "target_id"]) or "Нет данных"
        lines.append(
            "Позиция/Sector: "
            f"x={_fmt_unit(pos_x, 'м', '.1f')} | y={_fmt_unit(pos_y, 'м', '.1f')} | z={_fmt_unit(pos_z, 'м', '.1f')}"
        )
        lines.append(f"Скорость/Speed: {_fmt_unit(speed, 'м/с', '.2f')}")
        lines.append(
            "Дистанция до цели/Target distance: "
            f"{_fmt_unit(target_distance, 'м', '.1f')} | target={target_name}"
        )
        lines.extend(motion_lines[:3])
        return motion_severity, lines

    def _route_intent_block(
        self,
        *,
        scene_profile: str,
        objective_severity: str,
        objective_lines: list[str],
        objective_facts_lines: list[str],
    ) -> tuple[str, list[str]]:
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        route_style = str(objective.get("observation_style") or "safe").strip().lower() or "safe"
        route_role = str(objective.get("route_role") or "none").strip().lower() or "none"
        destination = str(objective.get("target_designator") or "не задана").strip() or "не задана"
        procedure_name = str(objective.get("procedure_name") or "—").strip() or "—"
        summary = str(objective.get("summary_ru") or "").strip() or "контур не описан"
        lines = [
            f"Destination: {destination}",
            "ETA: truth source не вычисляет единый ETA в F1 (используйте F2/F6 при необходимости)",
            f"Route mode: {route_style} | role={route_role} | scene={scene_profile}",
            f"Threat/Risk: {_severity_label(objective_severity).lower()}",
            f"Why this route: {summary}",
            f"Procedure contour: {procedure_name}",
        ]
        if objective_lines:
            lines.append(f"Route detail: {objective_lines[0]}")
        if objective_facts_lines:
            lines.append(f"Latest fact: {objective_facts_lines[0]}")
        return objective_severity, lines

    def _qiki_interpretation_block(self, *, qiki_severity: str, qiki_lines: list[str]) -> tuple[str, list[str]]:
        if not qiki_lines:
            return qiki_severity, ["Статус/Status: QIKI interpretation не получен"]
        if self._qiki_response is None and not self._qiki_pending_action_title:
            return qiki_severity, qiki_lines[:2]
        return qiki_severity, qiki_lines[:10]

    def _qiki_loop_projection(self) -> QikiLoopProjection:
        # Single derivation of the G1 operator loop from the last QikiChatResponseV1 + pending
        # state. Produces BOTH the verbose [QIKI LOOP] bullets and the compact F1 rows so the
        # two never drift. ADR-0014: honest missing/unknown/no-action, never invented.
        resp = self._qiki_response
        pending_title = self._qiki_pending_action_title
        if pending_title is None and resp is not None:
            for proposal in resp.proposals[:1]:
                pending_title = proposal.title.ru or proposal.title.en
        active = resp is not None or bool(pending_title)
        severity = "ok"

        # Намерение/Intent — no invention
        if resp is None:
            intent = "—"
        elif pending_title:
            intent = f"derived: {pending_title}"
        else:
            intent = "unknown"

        # QIKI head row
        if pending_title:
            qiki_state, qiki_detail = "УДЕРЖАНИЕ", "нужно подтверждение"
        elif resp is None:
            qiki_state, qiki_detail = "ГОТОВ", "q: <команда>"
        else:
            head_legality = resp.legality
            qiki_state = state_ru((head_legality.status if head_legality is not None else "ГОТОВ").strip()).upper()
            qiki_detail = (
                head_legality.reason_code if head_legality is not None and head_legality.reason_code else "review"
            ).strip().lower() or "review"

        # Допуск/Legality (+ domain) — §1
        legality = resp.legality if resp is not None else None
        if legality is not None:
            legality_bullet = (
                f"{legality.status} [{legality.domain}] {legality.reason_code} — {legality.reason.ru}"
            )
            legality_state_row = legality.status.strip().upper()
            legality_detail_row = f"[{legality.domain}] {legality.reason_code}".strip()
            if legality.status in {"blocked", "unsafe"}:
                severity = "warn"
            elif legality.status == "deferred":
                severity = "degraded"
        else:
            legality_bullet = "нет данных/missing"
            legality_state_row, legality_detail_row = "MISSING", "нет данных"

        # Доверие/Trust — §2 (verbose [:2]; primary signal for the compact row)
        trust_bullets: list[str] = []
        if resp is not None and resp.trust_signals:
            for signal in resp.trust_signals[:2]:
                trust_bullets.append(
                    f"{signal.state} | {signal.label.ru}/{signal.label.en} | "
                    f"conf={signal.confidence:.2f} | src={signal.source}"
                )
            primary = resp.trust_signals[0]
            trust_state_row = (primary.state or "PARTIAL").strip().upper()
            trust_detail_row = f"{primary.label.ru} conf={primary.confidence:.2f}"
        else:
            trust_state_row, trust_detail_row = "PARTIAL", "явных сигналов нет"

        # Ожидает/Pending
        if pending_title:
            pending_bullet = f"confirm needed — {pending_title}"
            pending_state_row, pending_detail_row = "CONFIRM", pending_title
        else:
            pending_bullet = "no action"
            pending_state_row, pending_detail_row = "NONE", "no action"

        # Эффект/Last — §3 (ACK != effect confirmation)
        consequence = resp.consequence if resp is not None else None
        if consequence is not None:
            effect_bullet = f"{consequence.status} | {consequence.summary.ru}"
            if consequence.telemetry_confirmation is not None:
                # §19.6 / ADR-0015: ACK/QIKI-claim != independent effect confirmation.
                # This text comes from the QIKI response, so attribute it to QIKI —
                # do not present it as an ORION-verified telemetry confirmation.
                effect_bullet += f" | подтв.(со слов QIKI): {consequence.telemetry_confirmation.ru}"
            effect_state_row = consequence.status.strip().upper()
            effect_detail_row = consequence.summary.ru
        else:
            effect_bullet = "no effect yet"
            effect_state_row, effect_detail_row = "NONE", "no effect yet"

        # Дальше/Next
        if pending_title:
            next_text, next_state_row = "подтвердить (кнопка / q confirm)", "CONFIRM"
        elif legality is not None and legality.allowed_when is not None:
            next_text, next_state_row = legality.allowed_when.ru, "WAIT"
        elif resp is None:
            next_text, next_state_row = "введите q: <команда>", "INPUT"
        else:
            next_text, next_state_row = "уточните команду / inspect F2 / open F3", "REVIEW"

        # Verbose [QIKI LOOP] bullets
        bullets = [
            "[QIKI LOOP] — операторский контур",
            f"• Намерение/Intent: {intent}",
            f"• Допуск/Legality: {legality_bullet}",
        ]
        if trust_bullets:
            bullets.extend(f"• Доверие/Trust: {body}" for body in trust_bullets)
        else:
            bullets.append("• Доверие/Trust: явных сигналов нет/missing")
        bullets.append(f"• Ожидает/Pending: {pending_bullet}")
        bullets.append(f"• Эффект/Last: {effect_bullet}")
        bullets.append(f"• Дальше/Next: {next_text}")
        if resp is not None and resp.reply is not None:
            bullets.append(f"Ответ/Reply: {resp.reply.body.ru}")
        if self._qiki_plan_preview_lines:
            bullets.append("План/Plan:")
            bullets.extend(f"  {item}" for item in self._qiki_plan_preview_lines)
        if self._qiki_procedure_status is not None:
            bullets.append(f"Исполнение/Execution: {self._qiki_procedure_status}")
        if resp is not None:
            for proposal in resp.proposals[:1]:
                for action in proposal.proposed_actions[:1]:
                    action_target = action.name
                    if action.kind == "ORION_PROCEDURE":
                        action_target = f"proc run {action.name}"
                    bullets.append(
                        f"Действие/Action: {proposal.title.ru}/{proposal.title.en} -> {action_target}"
                    )

        # Compact loop rows for the PRIMARY F1 panel: QIKI head always; full loop when active.
        # PENDING and EFFECT are shown ALWAYS when active (honest NONE / "no effect yet"), not
        # conditionally — G1 §3 requires the consequence state / absence of silent failure to be
        # visible on the main panel, not hidden when consequence is None.
        rows: list[tuple[str, str, str]] = [("QIKI", qiki_state, qiki_detail)]
        if active:
            rows.append(("LEGALITY", legality_state_row, legality_detail_row))
            rows.append(("TRUST", trust_state_row, trust_detail_row))
            rows.append(("PENDING", pending_state_row, pending_detail_row))
            rows.append(("EFFECT", effect_state_row, effect_detail_row))
            rows.append(("NEXT", next_state_row, next_text))

        return QikiLoopProjection(
            severity=severity,
            active=active,
            bullets=tuple(bullets),
            rows=tuple(rows),
        )

    def _qiki_block(self) -> tuple[str, list[str]]:
        # [QIKI LOOP] verbose view — bullets from the single loop projection. The compact F1
        # rows come from the SAME projection (_qiki_recommendation_rows), so they never drift.
        projection = self._qiki_loop_projection()
        return projection.severity, list(projection.bullets)

    def _procedure_block(self, tel: dict[str, Any]) -> tuple[str, list[str]]:
        lines: list[str] = []
        severity = "ok"

        pending_title = (self._qiki_pending_action_title or "").strip()
        if pending_title:
            severity = "warn"
            lines.append(f"Подготовлено/Prepared: {pending_title}")
            lines.append(f"{_NEXT_STEP_PREFIX} click QIKI подтвердить/Confirm or use q confirm.")
        else:
            lines.append("Подготовлено/Prepared: нет ожидающей процедуры")

        if self._qiki_plan_preview_lines:
            lines.append("План/Plan:")
            lines.extend(f"  {item}" for item in self._qiki_plan_preview_lines)

        if self._qiki_procedure_status is not None:
            lines.append(f"Исполнение/Execution: {self._qiki_procedure_status}")
            status_text = self._qiki_procedure_status.lower()
            if "ошибка" in status_text or "failed" in status_text:
                severity = "crit"
            elif "выполняется" in status_text or "running" in status_text:
                severity = _merge_severity(severity, "warn")

        sim_state = tel.get("sim_state")
        if isinstance(sim_state, dict):
            fsm_state = str(sim_state.get("fsm_state") or "UNKNOWN").strip().upper() or "UNKNOWN"
            paused = bool(sim_state.get("paused"))
            speed = sim_state.get("speed")
            speed_text = f"{float(speed):.2f}x" if isinstance(speed, (int, float)) else "—"
            lines.append(
                f"Время/Time: sim_state={fsm_state} | paused={'ДА' if paused else 'НЕТ'} | speed={speed_text}"
            )
        else:
            lines.append("Время/Time: sim_state отсутствует")

        lines.append("Журнал/Journal: click Процедуры/Procedures -> F6 for procedure audit trail.")
        return severity, lines

    def _objective_block(self) -> tuple[str, list[str]]:
        objective = self._observation_objective
        if not isinstance(objective, dict):
            return "ok", [
                "OBJECTIVE    | NONE       | standby",
                "NEXT         | SAFE OBS   | q: safe observation <target>",
            ]

        status = str(objective.get("status") or "prepared").strip().lower() or "prepared"
        style = str(objective.get("observation_style") or "safe").strip().lower() or "safe"
        procedure_name = str(objective.get("procedure_name") or "—").strip() or "—"
        target_designator = str(objective.get("target_designator") or "").strip()
        track_visible = bool(objective.get("track_visible"))
        track_label = str(objective.get("track_label") or target_designator or "").strip()
        track_id = str(objective.get("track_id") or "").strip()
        track_range_m = objective.get("track_range_m")
        track_quality = objective.get("track_quality")
        summary_ru = str(objective.get("summary_ru") or "").strip()
        title_ru = str(objective.get("title_ru") or "").strip()
        objective_id = str(objective.get("objective_id") or "—").strip() or "—"
        proposal_id = str(objective.get("proposal_id") or "").strip()
        request_id = str(objective.get("request_id") or "").strip()
        route_role = str(objective.get("route_role") or "").strip().lower()
        follow_up_status = str(objective.get("follow_up_status") or "").strip().lower()
        follow_up_reason_code = str(objective.get("follow_up_reason_code") or "").strip()
        follow_up_event_type = str(objective.get("follow_up_event_type") or "").strip()
        follow_up_summary_ru = str(objective.get("follow_up_summary_ru") or "").strip()
        observation_result_status = str(objective.get("observation_result_status") or "").strip().lower()
        observation_result_reason_code = str(objective.get("observation_result_reason_code") or "").strip()
        observation_result_summary_ru = str(objective.get("observation_result_summary_ru") or "").strip()
        objective_kind = (
            str(objective.get("kind") or "observation_objective_seed").strip() or "observation_objective_seed"
        )

        severity = {
            "prepared": "warn",
            "confirmed": "ok",
            "cancelled": "degraded",
            "failed": "crit",
        }.get(status, "ok")
        style_ru = "медленный" if style == "slow" else "безопасный"
        style_en = "slow" if style == "slow" else "safe"
        target_text = target_designator if target_designator else "без явной цели"
        lines = [
            f"Статус/Status: {status} | profile={style_ru}",
            f"Цель/Target: {target_text}",
            f"Контур/Loop: {title_ru or 'Observation objective'}",
            f"Маршрут/Route: {style_ru} ({style_en})",
            f"Процедура/Procedure: {procedure_name}",
            f"Route contour: style={style_en} | procedure={procedure_name}",
            f"Идентификатор/Objective ID: {objective_id}",
        ]
        if route_role in {"official", "deviation"}:
            lines.append(f"Route role: {route_role}")
        if proposal_id:
            lines.append(f"Proposal ID: {proposal_id}")
        if request_id:
            lines.append(f"Request ID: {request_id}")
        lines.append(f"Контракт/Contract: kind={objective_kind}")
        if follow_up_status in {"review_required", "review_completed", "hold_for_recheck", "resume_observation"}:
            if follow_up_status != "resume_observation":
                severity = _merge_severity(severity, "warn")
            constraint_parts = [f"status={follow_up_status}"]
            if follow_up_event_type:
                constraint_parts.append(f"source={follow_up_event_type}")
            if follow_up_reason_code:
                constraint_parts.append(f"reason={follow_up_reason_code}")
            lines.append(f"Ограничение/Constraint: {' | '.join(constraint_parts)}")
            if follow_up_summary_ru:
                lines.append(f"Follow-up: {follow_up_summary_ru}")
        if track_visible:
            range_text = f"{float(track_range_m):.0f} м" if isinstance(track_range_m, (int, float)) else "—"
            quality_text = f"{float(track_quality):.2f}" if isinstance(track_quality, (int, float)) else "—"
            lines.append(
                f"Радар/Track: visible | {track_label or 'target'} | range={range_text} | quality={quality_text}"
            )
            if track_id:
                lines.append(f"Track ID: {track_id}")
        elif target_designator:
            lines.append(f"Радар/Track: target {target_designator} not visible yet")
        if observation_result_status:
            result_parts = [f"status={observation_result_status}"]
            if observation_result_reason_code:
                result_parts.append(f"reason={observation_result_reason_code}")
            lines.append(f"Результат/Outcome: {' | '.join(result_parts)}")
            if observation_result_summary_ru:
                lines.append(f"Outcome: {observation_result_summary_ru}")
        if summary_ru:
            lines.append(f"Смысл/Meaning: {summary_ru}")
        if status == "prepared":
            lines.append("Следующий шаг/Next: подтвердите QIKI action, затем следите за процедурой и телеметрией.")
        elif status == "confirmed":
            if follow_up_status == "review_required":
                lines.append(
                    "Следующий шаг/Next: сначала проверьте linked hidden fact и "
                    "подтвердите review командой review confirm, "
                    "затем переходите к следующей observation-цели."
                )
            elif follow_up_status == "review_completed":
                lines.append(
                    "Следующий шаг/Next: review closure подтверждён; выберите "
                    "post-review follow-up командой follow-up hold."
                )
            elif follow_up_status == "hold_for_recheck":
                lines.append(
                    "Следующий шаг/Next: post-review hold выбран; выполните осторожный safe recheck для той же цели "
                    "перед следующей observation-целью."
                )
            elif follow_up_status == "resume_observation":
                lines.append(
                    "Следующий шаг/Next: resume observation подтверждён; задайте один cautious safe observation "
                    "для той же цели, чтобы продолжить contour."
                )
            elif observation_result_status == "reconfirmed":
                lines.append(
                    "Следующий шаг/Next: continuation-result зафиксирован; та же цель reconfirmed, можно "
                    "переходить к следующей observation-цели."
                )
            elif observation_result_status == "signature_changed":
                lines.append(
                    "Следующий шаг/Next: continuation-result зафиксирован; тот же contact сохранился, но его "
                    "signature изменилась, поэтому дальше используйте обновлённую identity."
                )
            else:
                lines.append("Следующий шаг/Next: objective closure подтверждён, можно переходить к следующей цели.")
        elif status == "cancelled":
            lines.append("Следующий шаг/Next: objective снят; задайте новую observation-цель при необходимости.")
        elif status == "failed":
            lines.append("Следующий шаг/Next: objective не закрыт; проверьте procedure/audit/telemetry path.")
        else:
            lines.append("Следующий шаг/Next: следите за objective lifecycle и процедурой.")
        return severity, lines

    def _objective_facts_block(self) -> tuple[str, list[str]]:
        if not self._objective_event_lines:
            return "ok", ["FACTS        | IDLE       | linked events idle"]
        lines = ["Таймлайн/Timeline:"]
        lines.extend(f"  {line}" for line in self._objective_event_lines[:4])
        return "warn", lines

    def _docking_quick_severity(self, tel: dict[str, Any]) -> str:
        docking_state = _pick_text(tel, ["docking", "state"]).lower()
        align_err = _pick_num(tel, ["docking", "alignment_error_deg"])
        if docking_state in {"approach", "capture", "docked"}:
            if align_err is not None and align_err >= 15.0:
                return "crit"
            if align_err is not None and align_err >= 8.0:
                return "warn"
            return "ok"
        if align_err is not None and align_err >= 15.0:
            return "crit"
        if align_err is not None and align_err >= 8.0:
            return "warn"
        return "ok"

    def _energy_block(self, tel: dict[str, Any]) -> tuple[str, list[str]]:
        soc = _pick_num(tel, ["power", "soc_pct"])
        if soc is None:
            soc = _pick_num(tel, ["battery", "soc_pct"])
        if soc is None:
            soc = _pick_num(tel, ["battery"])
        bus_v = _pick_num(tel, ["power", "bus_v"])
        bus_a = _pick_num(tel, ["power", "bus_a"])
        limit_mode = _pick_text(tel, ["power", "limit_mode"])
        load_shedding = _pick_bool(tel, ["power", "load_shedding"])
        shed_reasons = _pick_str_list(tel, ["power", "shed_reasons"])

        severity = "ok"
        if soc is not None and soc < 15.0:
            severity = "crit"
        elif soc is not None and soc < 20.0:
            severity = "warn"
        if load_shedding is True:
            severity = _merge_severity(severity, "warn")
        # §19.6 / ADR-0014: no confident green without source. If battery SOC is
        # unknown, ORION cannot claim energy nominal — flag it (as _safety_block
        # already does for missing safe-mode data). The detail line shows "Нет данных".
        if severity == "ok" and soc is None:
            severity = "warn"

        eta = _pick_num(tel, ["power", "eta_discharge_s"])
        if eta is None:
            eta = _pick_num(tel, ["power", "time_to_empty_s"])
        if eta is None:
            eta_min = _pick_num(tel, ["power", "time_to_empty_min"])
            if eta_min is not None:
                eta = eta_min * 60.0
        if eta is None:
            capacity_wh = _pick_num(tel, ["power", "battery_capacity_wh"])
            discharge_w = _pick_num(tel, ["power", "battery_discharge_w"])
            if (
                soc is not None
                and capacity_wh is not None
                and capacity_wh > 0.0
                and discharge_w is not None
                and discharge_w > 0.0
            ):
                eta = (soc / 100.0) * capacity_wh / discharge_w * 3600.0

        lines = [
            f"• Заряд/SOC: {_fmt_pct(soc)} | crit < 15%",
            f"• Шина/Bus: {_fmt_unit(bus_v, 'В', '.2f')} | {_fmt_unit(bus_a, 'А', '.2f')}",
            f"• Лимит/Limit: {limit_mode or 'Нет данных'}",
            f"• Аварийное отключение нагрузки: {_bool_on_off_text(load_shedding)}",
            f"• Причины сброса: {_shed_reasons_text(load_shedding, shed_reasons)}",
            f"• ETA разрядки/Drain: {_fmt_duration(eta)}",
        ]
        return severity, lines

    def _motion_block(self, tel: dict[str, Any]) -> tuple[str, list[str]]:
        velocity = _pick_num(tel, ["speed_m_s"])
        if velocity is None:
            velocity = _pick_num(tel, ["velocity"])
        heading = _pick_num(tel, ["heading"])
        orbit_apo = _pick_num(tel, ["orbit", "apoapsis_km"])
        orbit_peri = _pick_num(tel, ["orbit", "periapsis_km"])
        orbit_conf = _pick_num(tel, ["orbit", "confidence"])
        orbit_state = _pick_text(tel, ["orbit", "state"])
        orbit_reason = _pick_text(tel, ["orbit", "reason"])

        pitch = _pick_angle_deg(tel, ["attitude", "pitch_deg"], ["attitude", "pitch_rad"], ["pitch"])
        yaw = _pick_angle_deg(tel, ["attitude", "yaw_deg"], ["attitude", "yaw_rad"], ["yaw"])
        roll = _pick_angle_deg(tel, ["attitude", "roll_deg"], ["attitude", "roll_rad"], ["roll"])

        docking_state = _pick_text(tel, ["docking", "state"]).lower()
        docking_target = _pick_text(tel, ["docking", "target_id"])
        docking_distance = _pick_num(tel, ["docking", "distance_m"])
        rel_speed = _pick_num(tel, ["docking", "rel_speed_mps"])
        align_err = _pick_num(tel, ["docking", "alignment_error_deg"])

        severity = "ok"
        if align_err is not None and align_err >= 15.0:
            severity = "crit"
        elif align_err is not None and align_err >= 8.0:
            severity = "warn"
        # §19.6 / ADR-0014: no confident green without source. With no velocity,
        # heading, attitude or orbit state there is no motion truth to verify — do
        # not show nominal (this feeds guidance_severity and the global status).
        if (
            severity == "ok"
            and velocity is None
            and heading is None
            and pitch is None
            and yaw is None
            and roll is None
            and not orbit_state
        ):
            severity = "warn"

        lines = [
            (
                "Навигация/Nav: "
                f"speed {_fmt_unit(velocity, 'м/с', '.2f')} | "
                f"heading {_fmt_unit(heading, '°', '.1f')}"
            ),
            (
                "Ориентация/Attitude: "
                f"P {_fmt_unit(pitch, '°', '.1f')} | "
                f"Y {_fmt_unit(yaw, '°', '.1f')} | "
                f"R {_fmt_unit(roll, '°', '.1f')}"
            ),
            (
                "Орбита/Orbit: "
                f"{orbit_state or 'Нет данных'} | conf={_fmt_unit(orbit_conf, '', '.2f')} | "
                f"Apo {_fmt_unit(orbit_apo, 'км', '.2f')} | Peri {_fmt_unit(orbit_peri, 'км', '.2f')}"
            ),
        ]

        if orbit_reason:
            lines.append(f"Причина/Reason: {orbit_reason}")

        if docking_state not in {"", "none", "undocked"}:
            lines.extend(
                [
                    (
                        "Сближение/Approach: "
                        f"{docking_state or 'Нет данных'} | target {docking_target or 'Нет данных'} | "
                        f"dist {_fmt_unit(docking_distance, 'м', '.2f')}"
                    ),
                ]
            )
            if severity == "crit":
                lines.append(
                    "Следующий шаг/Next: "
                    f"исправьте выравнивание ({_fmt_unit(align_err, '°', '.2f')}) перед продолжением стыковки"
                )
            elif severity == "warn":
                lines.append(
                    "Следующий шаг/Next: "
                    f"сократите ошибку выравнивания ({_fmt_unit(align_err, '°', '.2f')}) и подтвердите курс"
                )
            elif rel_speed is not None:
                lines.append(
                    "Следующий шаг/Next: "
                    "держите сближение под контролем, "
                    f"текущая относительная скорость {_fmt_unit(rel_speed, 'м/с', '.3f')}"
                )
        else:
            lines.append("Следующий шаг/Next: откройте F2 для навигации или стыковки, если нужен детальный разбор")
        return severity, lines

    def _comms_block(self, tel: dict[str, Any]) -> tuple[str, list[str]]:
        link = _pick_text(tel, ["comms", "link"]).lower()
        if not link:
            link = _pick_text(tel, ["comms", "link_state"]).lower()
        latency = _pick_num(tel, ["comms", "latency_ms"])
        packet_loss = _pick_num(tel, ["comms", "packet_loss_pct"])
        rssi = _pick_num(tel, ["comms", "rssi_dbm"])
        snr = _pick_num(tel, ["comms", "snr_db"])
        tx_power = _pick_num(tel, ["comms", "tx_power_w"])
        data_rate = _pick_num(tel, ["comms", "data_rate_kbps"])
        antenna_status = _pick_text(tel, ["comms", "antenna_status"])

        if not self._nats_connected or link in {"down", "offline", "lost"}:
            severity = "crit"
        elif (latency is not None and latency > 500.0) or (
            packet_loss is not None and packet_loss > 5.0
        ):
            severity = "warn"
        else:
            severity = "ok"

        if not self._nats_connected:
            link_text = tr("offline")
        elif link in {"up", "online"}:
            link_text = tr("online")
        elif link in {"reconnect", "reconnecting"}:
            link_text = tr("reconnecting")
        elif link in {"down", "offline", "lost"}:
            link_text = tr("offline")
        else:
            link_text = "Нет данных"

        lines = [
            f"• Канал/Link: {link_text}",
            f"• Задержка/Latency: {_fmt_unit(latency, 'мс', '.0f')} | norm <= 500",
            f"• Потери/Loss: {_fmt_unit(packet_loss, '%', '.2f')} | norm <= 5%",
            f"• {tr('rssi')}: {_fmt_unit(rssi, 'dBm', '.1f')}",
            f"• SNR: {_fmt_unit(snr, 'dB', '.1f')}",
            f"• TX Power: {_fmt_unit(tx_power, 'Вт', '.1f')}",
            f"• Data Rate: {_fmt_unit(data_rate, 'kbps', '.1f')}",
            f"• Antenna: {antenna_status or 'Нет данных'}",
        ]
        return severity, lines

    def _thermal_block(self, tel: dict[str, Any]) -> tuple[str, list[str]]:
        thermal = tel.get("thermal")
        thermal_nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
        if isinstance(thermal_nodes, list):
            nodes: list[dict[str, Any]] = [item for item in thermal_nodes if isinstance(item, dict)]
        else:
            nodes = []
        core_node = next((node for node in nodes if str(node.get("id") or "").strip().lower() == "core"), None)

        core = self._pick_core_temp_c(tel)
        if core is None and isinstance(core_node, dict):
            core = _pick_num(core_node, ["temp_c"])
        radiator = _pick_num(tel, ["thermal", "radiator_c"])
        if radiator is None:
            radiator = _pick_num(tel, ["temp_external_c"])
        sink = _pick_num(tel, ["thermal", "sink_c"])
        thermal_warning = _pick_text(tel, ["thermal", "warning"]).lower()

        warn_nodes: list[str] = []
        trip_nodes: list[str] = []
        for node in nodes:
            node_id = str(node.get("id") or "").strip()
            if not node_id:
                continue
            if bool(node.get("tripped")):
                trip_nodes.append(node_id)
            elif bool(node.get("warned")):
                warn_nodes.append(node_id)
        warn_nodes = list(dict.fromkeys(warn_nodes))
        trip_nodes = list(dict.fromkeys(trip_nodes))

        if isinstance(core_node, dict) and "warned" in core_node:
            core_warned = bool(core_node.get("warned"))
        else:
            core_warned = None
        if isinstance(core_node, dict) and "tripped" in core_node:
            core_tripped = bool(core_node.get("tripped"))
        else:
            core_tripped = None
        core_warn_c = _pick_num(core_node, ["warn_c"]) if isinstance(core_node, dict) else None
        core_trip_c = _pick_num(core_node, ["trip_c"]) if isinstance(core_node, dict) else None
        core_hys_c = _pick_num(core_node, ["hys_c"]) if isinstance(core_node, dict) else None

        severity = "ok"
        if (
            core_tripped is True
            or bool(trip_nodes)
            or (core is not None and core >= 90.0)
            or ("crit" in thermal_warning)
            or ("trip" in thermal_warning)
        ):
            severity = "crit"
        elif (
            core_warned is True
            or bool(warn_nodes)
            or (core is not None and core >= 80.0)
            or ("warn" in thermal_warning)
            or ("alarm" in thermal_warning)
        ):
            severity = "warn"
        # §19.6 / ADR-0014: no confident green without source. With no core temp,
        # no node telemetry and no warning text there is nothing to verify — do not
        # show nominal green (the thermal-evidence line already marks it missing).
        if severity == "ok" and core is None and not nodes and not thermal_warning:
            severity = "warn"

        trend = "стабильно"
        if core is not None and self._prev_core_temp_c is not None:
            delta = core - self._prev_core_temp_c
            if delta > 0.5:
                trend = "растет"
            elif delta < -0.5:
                trend = "падает"

        recommendation = "Рекомендация: охлаждение в норме."
        if severity == "crit":
            recommendation = "Рекомендация: снизить нагрузку и проверить контур охлаждения."
        elif severity == "warn":
            recommendation = "Рекомендация: наблюдать терморежим и подготовить снижение нагрузки."

        if core_tripped is True:
            core_state = "TRIP"
        elif core_warned is True:
            core_state = "WARN"
        elif core_warned is False and core_tripped is False and core is not None:
            core_state = "OK"
        else:
            core_state = "Нет данных"

        if nodes:
            warn_nodes_text = ", ".join(warn_nodes) if warn_nodes else "—"
            trip_nodes_text = ", ".join(trip_nodes) if trip_nodes else "—"
        else:
            warn_nodes_text = "Нет данных"
            trip_nodes_text = "Нет данных"

        lines = [
            f"• Core: {_fmt_unit(core, '°C', '.1f')} | limit 90°C | state={core_state}",
            f"• Radiator/Sink: {_fmt_unit(radiator, '°C', '.1f')} | {_fmt_unit(sink, '°C', '.1f')}",
            f"• WARN nodes: {warn_nodes_text}",
            f"• TRIP nodes: {trip_nodes_text}",
            (
                "• Core limits: "
                f"warn {_fmt_unit(core_warn_c, '°C', '.1f')} | "
                f"trip {_fmt_unit(core_trip_c, '°C', '.1f')} | "
                f"hys {_fmt_unit(core_hys_c, '°C', '.1f')}"
            ),
            f"• Тренд: {trend}",
            f"• Advice: {recommendation}",
        ]
        lines.extend(self._thermal_node_detail_lines(tel))
        lines.append(self._thermal_evidence_line(tel))
        return severity, lines

    def _thermal_node_detail_lines(self, tel: dict[str, Any]) -> list[str]:
        """§13.7 per-node thermal evidence (id / temp / state / reason / blocked commands).

        Makes the per-node surface visible — not just the aggregate Core/WARN/TRIP summary
        above. Honest: absent node temp stays "missing", absent state stays "unknown".
        """
        thermal = tel.get("thermal") if isinstance(tel, dict) else None
        evidence = thermal_to_evidence(
            thermal_records_from_snapshot(thermal if isinstance(thermal, dict) else {})
        )
        rows: list[str] = []
        for node in evidence.nodes[:8]:
            if node.node_id == "missing":
                continue
            detail = f"  ▪ {node.node_id}: {node.temp_label} | {node.state_label} | cooldown: {node.cooldown_label}"
            if node.reason_codes:
                detail += f" | {','.join(node.reason_codes)}"
            if node.blocked_commands:
                detail += f" | блок/blocked: {','.join(node.blocked_commands)}"
            rows.append(detail)
        return ["• Узлы/Nodes (§13.7):", *rows] if rows else []

    def _thermal_evidence_line(self, tel: dict[str, Any]) -> str:
        """ADR-0014 evidence line for thermal — per-node trust/source/reason via
        the bounded-temp console adapter (equivalence-guarded mirror of q_sim);
        staleness is derived console-side. Closes the F1 "confident state without
        source" gap so the operator never sees a bare OK without provenance.
        """
        thermal = tel.get("thermal") if isinstance(tel, dict) else None
        records = thermal_records_from_snapshot(thermal if isinstance(thermal, dict) else {})
        evidence = thermal_to_evidence(records)
        age_s = _pick_num(tel, ["thermal", "age_s"])
        stale = age_s is not None and age_s > 30.0
        trusts = [node.trust_status for node in evidence.nodes]
        if "missing" in trusts:
            trust = "missing"
        elif stale or "degraded" in trusts:
            trust = "degraded"
        else:
            trust = "trusted"
        reasons = sorted({rc for node in evidence.nodes for rc in node.reason_codes})
        if stale:
            reasons = sorted(set(reasons) | {"THERMAL_TELEM_STALE"})
        stale_mark = " [УСТАРЕЛО]" if stale else ""
        miss_mark = " [НЕТ ИСТОЧНИКА]" if trust == "missing" else ""
        line = (
            f"• Доказательность тепла: {evidence.operator_text}{stale_mark}{miss_mark}"
            f" | trust={trust} | src=thermal.nodes"
        )
        if reasons:
            line += f" | reason={','.join(reasons)}"
        return line

    def _incidents_block(self) -> tuple[str, list[str]]:
        total = self._active_incidents
        crit_items = [inc for inc in self._incidents if str(inc.get("severity", "")).upper().startswith("C")]
        crit_count = len(crit_items)

        if crit_count > 0:
            severity = "crit"
        elif total > 0:
            severity = "warn"
        else:
            severity = "ok"

        latest_crit = crit_items[0] if crit_items else None
        latest_crit_text = "Нет данных"
        if latest_crit:
            incident_id = str(latest_crit.get("id") or "incident")
            description = str(latest_crit.get("description") or "Без описания")
            latest_crit_text = f"{incident_id}: {description}"

        lines = [
            f"• Активные инциденты: {total}",
            f"• Критические инциденты: {crit_count}",
            f"• Последний критический/Last critical: {latest_crit_text}",
        ]
        return severity, lines

    def _safety_block(self) -> tuple[str, list[str]]:
        active = self._safe_mode.get("active")
        reason = str(self._safe_mode.get("reason") or "").strip()
        authority = str(self._safe_mode.get("authority") or "q-core-agent(events)")
        updated_ts = self._safe_mode.get("updated_ts")
        always_on = getattr(self._operator_shell_state, "always_on", None)
        safe_envelope_state = getattr(always_on, "safe_envelope_state", None)

        if active is True:
            severity = "crit"
            state_text = "SAFE MODE: ВКЛЮЧЕН"
        elif active is False:
            severity = "ok"
            state_text = "SAFE MODE: OFF"
        elif safe_envelope_state == "nominal" and self._nats_connected:
            severity = "ok"
            state_text = "SAFE MODE: OFF"
            if not reason:
                reason = "signal clear"
        else:
            severity = "warn"
            state_text = "SAFE MODE: нет данных"

        updated_text = "Нет данных"
        if isinstance(updated_ts, (int, float)) and not isinstance(updated_ts, bool):
            updated_text = datetime.fromtimestamp(float(updated_ts), tz=timezone.utc).strftime("%H:%M:%S UTC")

        lines = [
            f"• Статус: {state_text}",
            f"• Причина: {reason or 'Нет данных'}",
            f"• Authority: {authority}",
            f"• Обновлено: {updated_text}",
        ]
        return severity, lines

    def _global_status(
        self,
        *,
        energy_sev: str,
        motion_sev: str,
        comms_sev: str,
        thermal_sev: str,
        safety_sev: str,
        incidents_sev: str,
        procedure_sev: str,
        qiki_sev: str,
    ) -> tuple[str, str]:
        status = "ok"
        status = _merge_severity(status, energy_sev)
        status = _merge_severity(status, motion_sev)
        status = _merge_severity(status, comms_sev)
        status = _merge_severity(status, thermal_sev)
        status = _merge_severity(status, safety_sev)
        status = _merge_severity(status, incidents_sev)
        status = _merge_severity(status, procedure_sev)
        status = _merge_severity(status, qiki_sev)

        if safety_sev == "crit":
            return status, "SAFE MODE активирован authoritative сигналом Q-Core."
        if incidents_sev == "crit":
            return status, "Есть критические инциденты, требуется немедленное подтверждение."
        if thermal_sev == "crit":
            return status, "Обнаружен перегрев подсистемы Thermal."
        if comms_sev == "crit":
            return status, "Потеряна связь с контуром управления."
        if energy_sev == "crit":
            return status, "Критически низкий заряд или ограничение питания."
        if procedure_sev == "crit":
            return status, "Процедура ORION завершилась с ошибкой и требует разбора."
        if procedure_sev == "warn":
            return status, "Процедура ORION подготовлена или выполняется; нужен операторский контроль."
        if qiki_sev == "warn":
            return status, "Контур QIKI заблокирован политикой или требует подтверждаемого исполнения."
        if status == "warn":
            return status, "Есть предупреждения, требуется наблюдение."
        return status, "Активных критических инцидентов нет."

    def _pick_core_temp_c(self, tel: dict[str, Any]) -> float | None:
        core = _pick_num(tel, ["thermal", "core_c"])
        if core is None:
            core = _pick_num(tel, ["temp_core_c"])
        return core

    def _overview_line(self, severity: str, reason: str) -> str:
        return f"СИСТЕМА: {self._severity_markup(severity)} | Контекст: {reason}"

    def _panel_block(
        self,
        title: str,
        rows: list[tuple[str, str, str]] | list[str],
        *,
        extras: list[str] | None = None,
    ) -> list[str]:
        lines = [f"> {title}"]
        for row in rows:
            if isinstance(row, str):
                lines.append(row)
                continue
            label, state, detail = row
            lines.append(self._panel_row(label, state, detail))
        if extras:
            lines.extend(f"[dim]{line}[/dim]" for line in extras if line)
        return lines

    @staticmethod
    def _panel_row(label: str, state: str, detail: str) -> str:
        left = f"{label:<12}"
        mid = f"{state:<11}"
        right = detail or "—"
        return f"{left} | {mid} | {right}"

    @staticmethod
    def _compact_fact_detail(line: str, prefix: str = "") -> str:
        text = line.strip()
        if text.startswith("• "):
            text = text[2:]
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :]
        return text.strip() or "—"

    def _quick_fact_row(self, label: str, severity: str, *details: str) -> str:
        detail = " | ".join(part for part in details if part and part != "—") or "—"
        return self._panel_row(label, self._compact_severity(severity), detail)

    @staticmethod
    def _dim_block(title: str, lines: list[str]) -> list[str]:
        return [f"[dim]{title}[/dim]", *[f"[dim]{line}[/dim]" for line in lines if line]]

    @staticmethod
    def _extra_lines(lines: list[str], limit: int) -> list[str]:
        return [line for line in lines if line][:limit]

    def _global_state_rows(
        self,
        *,
        scene_profile: str,
        global_severity: str,
        objective: dict[str, Any],
    ) -> list[tuple[str, str, str]]:
        objective_state = str(objective.get("status") or "none").strip().upper() or "NONE"
        target = (
            str(objective.get("target_designator") or objective.get("track_label") or "").strip() or "undefined"
        )
        return [
            ("КОНТЕКСТ", self._compact_severity(global_severity), scene_profile),
            ("ЦЕЛЬ", objective_state, target),
        ]

    def _mission_context_rows(
        self,
        *,
        always_on: Any,
        objective: dict[str, Any],
        scene_profile: str,
    ) -> list[tuple[str, str, str]]:
        phase = str(getattr(always_on, "mission_phase", None) or "UNKNOWN").strip()
        intent = str(objective.get("follow_up_status") or objective.get("status") or "none").strip().upper() or "NONE"
        # honest: no docking telemetry → mark partial; do not present the scene
        # profile as if it were a real docking state (scene stays in the detail).
        docking_state = _pick_text(self._telemetry, ["docking", "state"]).strip().upper() or "PARTIAL"
        return [
            ("ФАЗА", phase, f"scene={scene_profile}"),
            ("НАМЕРЕНИЕ", intent, f"scene={scene_profile}"),
            ("СТЫКОВКА", docking_state, scene_profile),
        ]

    def _guidance_rows(
        self,
        *,
        telemetry: dict[str, Any],
        guidance_severity: str,
        derived_state: Any,
    ) -> list[tuple[str, str, str]]:
        # compact must not read more confident than the verbose _guidance_context_block:
        # when guidance telemetry/derived state is absent, mark it "partial" (the same
        # honest marker the verbose block uses), never a healthy default.
        guidance_state = (
            _pick_text(telemetry, ["guidance", "state"])
            or _pick_text(telemetry, ["docking", "state"])
            or "partial"
        )
        route_dev = str(getattr(derived_state, "trajectory_deviation", None) or "partial").strip()
        maneuver = str(getattr(derived_state, "maneuver_feasibility", None) or "partial").strip()
        return [
            ("НАВЕДЕНИЕ", self._compact_severity(guidance_severity), guidance_state),
            ("ОТКЛОН", route_dev.upper(), str(getattr(derived_state, "commandability_state", None) or "partial")),
            ("МАНЁВР", maneuver.upper(), str(getattr(derived_state, "attitude_stability", None) or "partial")),
        ]

    def _incident_rows(self, *, incident_focus_severity: str) -> list[tuple[str, str, str]]:
        total = self._active_incidents
        crit_count = len([inc for inc in self._incidents if str(inc.get("severity", "")).upper().startswith("C")])
        latest = "clean"
        if crit_count:
            latest_inc = next(
                (
                    inc
                    for inc in self._incidents
                    if str(inc.get("severity", "")).upper().startswith("C")
                ),
                None,
            )
            if latest_inc is not None:
                latest = str(latest_inc.get("id") or "critical").strip()
        return [
            ("КРИТ", str(crit_count), self._compact_severity(incident_focus_severity)),
            ("ТРЕВОГА", str(total), "чисто" if total == 0 else "активно"),
            ("ПОСЛ.КРИТ", latest.upper() if latest != "clean" else "НЕТ", "чисто" if total == 0 else latest),
        ]

    def _route_rows(
        self,
        *,
        objective: dict[str, Any],
        route_severity: str,
        scene_profile: str,
    ) -> list[tuple[str, str, str]]:
        route_role = str(objective.get("route_role") or "unset").strip().upper() or "UNSET"
        target = str(objective.get("target_designator") or "unset").strip().upper() or "UNSET"
        return [
            ("МАРШРУТ", route_role, scene_profile),
            ("ЦЕЛЬ", target, str(objective.get("track_label") or "undefined").strip() or "undefined"),
        ]

    def _qiki_recommendation_rows(
        self,
        *,
        qiki_severity: str,
        qiki_lines: list[str],
    ) -> list[tuple[str, str, str]]:
        # Compact loop rows for the PRIMARY "QIKI / Решение" F1 panel — from the SAME loop
        # projection as the verbose [QIKI LOOP] block. No second derivation, no parsing of
        # rendered strings (the coupling that silently broke trust before). ACK is app-state.
        projection = self._qiki_loop_projection()
        rows = list(projection.rows)
        if projection.active:
            always_on = getattr(self._operator_shell_state, "always_on", None)
            ack_state = "OPEN" if getattr(always_on, "human_ack_required", False) else "CLEAR"
            rows.append(("ACK", ack_state, f"assist={getattr(always_on, 'qiki_assist_status', None) or 'partial'}"))
        return rows

    def _operator_intervention_rows(self, *, next_step: str) -> list[tuple[str, str, str]]:
        # single owner per fact: read the operator loop directly (same source as
        # _operator_intervention_block) instead of parsing that block's rendered
        # lines. The old render->parse coupling silently broke when the block's RU
        # prefixes changed — and it already mislabeled the empty state as "ЕСТЬ".
        loop = getattr(self._operator_shell_state, "operator_loop", None)
        loop_state = str(getattr(loop, "last_command_status", None) or "idle").strip()
        mode = str(getattr(loop, "command_mode_state", None) or "standby").strip()
        pending_count = getattr(loop, "pending_command_count", 0)
        last_summary = str(getattr(loop, "last_command_summary", None) or "").strip()
        no_command = not last_summary or last_summary == "Команда ещё не подавалась"
        return [
            ("ДЕЙСТВИЕ", "УДЕРЖАНИЕ" if self._qiki_pending_action_title else state_ru(loop_state).upper(), next_step),
            ("ВВОД", state_ru(mode).upper(), f"в очереди: {pending_count}"),
            ("ПОСЛЕДНЯЯ", "ПУСТО" if no_command else "ЕСТЬ", last_summary or "Команда ещё не подавалась"),
        ]

    def _process_state_rows(
        self,
        *,
        process_severity: str,
        procedure_status: str | None,
        scene_profile: str,
    ) -> list[tuple[str, str, str]]:
        objective = self._observation_objective if isinstance(self._observation_objective, dict) else {}
        proc_state = "ACTIVE" if procedure_status else "IDLE"
        detail = procedure_status or scene_profile.replace("_", " ").title()
        focus_state = str(objective.get("status") or "none").strip().upper() if objective else "NONE"
        focus_detail = (
            str(objective.get("target_designator") or objective.get("track_label") or "no active contour").strip()
            or "no active contour"
        )
        return [
            ("PROCESS", proc_state, detail),
            ("FOCUS", focus_state, focus_detail),
        ]

    @staticmethod
    def _compact_severity(severity: str) -> str:
        return {"ok": "NOMINAL", "warn": "WARN", "crit": "CRITICAL", "degraded": "HOLD"}.get(severity, "PARTIAL")

    def _section_title(self, title: str, severity: str) -> str:
        return f"{title}: {self._severity_markup(severity)}"

    @staticmethod
    def _section_divider() -> str:
        # plain text: this string also flows into plain-rendered MFD panes,
        # where rich markup would leak to the operator as literal [dim] tags
        return "· · ·"

    def _severity_markup(self, severity: str) -> str:
        label = _severity_label(severity)
        color = {"ok": "#7fb26f", "warn": "#d6a65b", "crit": "#d06b4d"}.get(severity, "#d7ddd7")
        return f"[bold {color}]{label}[/]"

def _severity_label(severity: str) -> str:
    if severity == "crit":
        return "КРИТИЧНО"
    if severity == "warn":
        return "ПРЕДУПРЕЖДЕНИЕ"
    return "НОРМА"


def _merge_severity(left: str, right: str) -> str:
    rank = {"ok": 0, "warn": 1, "crit": 2}
    return right if rank.get(right, 0) > rank.get(left, 0) else left


def _pick_num(payload: dict[str, Any], path: list[str]) -> float | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return float(value)
    return None


def _pick_text(payload: dict[str, Any], path: list[str]) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return ""
        value = value[key]
    if isinstance(value, str):
        return value.strip()
    return ""


def _pick_bool(payload: dict[str, Any], path: list[str]) -> bool | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes", "active", "enabled"}:
            return True
        if normalized in {"0", "false", "off", "no", "inactive", "disabled"}:
            return False
    return None


def _pick_str_list(payload: dict[str, Any], path: list[str]) -> list[str]:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return []
        value = value[key]
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    return list(dict.fromkeys(items))


def _pick_angle_deg(payload: dict[str, Any], *paths: list[str]) -> float | None:
    for path in paths:
        value = _pick_num(payload, path)
        if value is None:
            continue
        if path[-1].endswith("_rad"):
            return math.degrees(value)
        return value
    return None


def _fmt_unit(value: float | None, unit: str, precision: str) -> str:
    if value is None:
        return "Нет данных"
    return f"{value:{precision}} {unit}".strip()


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "Нет данных"
    return f"{value:.1f}%"


def _mfd_pct_text(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value}%"


def _bool_on_off_text(value: bool | None) -> str:
    if value is None:
        return "Нет данных"
    return "ВКЛ" if value else "ВЫКЛ"


def _shed_reasons_text(load_shedding: bool | None, reasons: list[str]) -> str:
    if reasons:
        return ", ".join(reasons)
    if load_shedding is True:
        return "degraded: нет данных"
    if load_shedding is False:
        return "—"
    return "Нет данных"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds <= 0.0:
        return "Нет данных"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def _telemetry_age_seconds(payload: dict[str, Any]) -> float | None:
    unix_ms = payload.get("ts_unix_ms")
    if isinstance(unix_ms, (int, float)):
        return max(0.0, (datetime.now(tz=timezone.utc).timestamp() * 1000.0 - float(unix_ms)) / 1000.0)

    stamp = payload.get("timestamp")
    if isinstance(stamp, str) and stamp:
        try:
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            return max(0.0, datetime.now(tz=timezone.utc).timestamp() - ts.timestamp())
        except ValueError:
            return None
    return None
