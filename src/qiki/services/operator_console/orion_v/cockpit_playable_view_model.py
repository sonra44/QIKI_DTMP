from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from qiki.services.operator_console.orion_v.body_physics_view_model import BodyPhysicsConsoleViewModel
from qiki.services.operator_console.orion_v.body_structure_view_model import BodyStructureConsoleViewModel
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    PowerThermalConsoleViewModel,
    format_soc_bat,
    format_soc_cap,
)
from qiki.services.operator_console.orion_v.mfd_layout import mfd_page_label, normalize_mfd_page


@dataclass(frozen=True, slots=True)
class CockpitPlayableActionVM:
    """One operator-visible F1 action in the first playable cockpit loop.

    This is a view-model contract.  It does not execute runtime commands and does not
    own physical truth; the app-level action handler owns the local state transition.
    """

    action_id: str
    label: str
    key_hint: str
    target_panel: str
    cycle_effect: str
    source_owner: str
    evidence_policy: str


@dataclass(frozen=True, slots=True)
class CockpitVisiblePanelVM:
    """One required visible F1 cockpit panel for the first playable loop.

    The panels are acceptance-facing view-model rows.  They are not runtime
    subsystems and do not create physical state.  Their job is to make F1
    visibly complete: Body, Power, Nav, Sensors, Command and Event all have
    a stable status line and source/trust boundary.
    """

    panel_id: str
    title: str
    status: str
    source: str
    trust_status: str
    summary: str


@dataclass(frozen=True, slots=True)
class CockpitEventTickerItemVM:
    """One applied F1 local-loop event visible in the cockpit event ticker.

    The ticker is local/operator-side only.  It makes repeated F1 Apply cycles
    visible without claiming runtime command execution, ACK or physical effect.
    """

    event_id: str
    action_label: str
    target_panel: str
    effect_summary: str


@dataclass(frozen=True, slots=True)
class CockpitFocusVM:
    """Current operator focus for the F1 cockpit surface.

    Focus is a UI affordance, not a runtime selection. It makes the cockpit
    playable by answering: where am I, what action is armed, what can I press,
    and where will evidence be found after Apply.
    """

    focused_panel_id: str
    focused_panel_title: str
    focused_action_id: str
    focused_action_label: str
    focus_reason: str
    can_preview: bool
    can_apply: bool
    can_open_evidence: bool
    help_visible: bool
    palette_hint: str


@dataclass(frozen=True, slots=True)
class CockpitHintVM:
    """One context-sensitive F1 hint row.

    Hints are view-model data so tests can prove the operator always sees
    available keys and the local/runtime boundary.
    """

    hint_id: str
    panel_id: str
    severity: str
    text: str
    key_hint: str
    source: str
    trust_status: str


@dataclass(frozen=True, slots=True)
class CockpitActionHelpVM:
    """Human-readable action affordance for the focused F1 action."""

    action_id: str
    action_label: str
    target_panel: str
    summary: str
    preview_text: str
    apply_text: str
    result_text: str
    runtime_claim_status: str


@dataclass(frozen=True, slots=True)
class CockpitPlayableLoopVM:
    """F1 first playable loop state.

    The loop is intentionally normal-only in this slice.  It gives the operator a
    complete visible UI cycle without introducing degradation, damage, PDU runtime,
    thermal simulation or command execution claims.
    """

    loop_status: str
    phase: str
    selected_action_id: str
    selected_action_label: str
    selected_action_index: int
    actions_count: int
    action_summary: str
    source: str
    trust_status: str
    runtime_claim_status: str
    cycle_count: int
    last_event_id: str
    last_event_summary: str
    last_action_id: str
    last_action_label: str
    last_effect_panel_id: str
    last_effect_summary: str
    action_history: tuple[CockpitEventTickerItemVM, ...]
    focused_panel_id: str
    focused_panel_title: str
    focus_reason: str
    help_visible: bool
    body_summary: str
    power_summary: str
    nav_summary: str
    sensor_summary: str
    command_summary: str
    available_actions: tuple[CockpitPlayableActionVM, ...]


_ACTIONS: tuple[CockpitPlayableActionVM, ...] = (
    CockpitPlayableActionVM(
        action_id="body_self_check",
        label="BODY SELF-CHECK",
        key_hint="B / APPLY",
        target_panel="BODY",
        cycle_effect="register visible body-structure seed if not already attached",
        source_owner="qiki.body_structure.run_attach_pipeline",
        evidence_policy="audit-backed body evidence",
    ),
    CockpitPlayableActionVM(
        action_id="power_refresh",
        label="POWER REFRESH",
        key_hint="APPLY",
        target_panel="POWER",
        cycle_effect="refresh power/accumulator projection from the current view-model snapshot",
        source_owner="orion.power_thermal_view_model",
        evidence_policy="telemetry/view-model projection; no full PDU runtime claim",
    ),
    CockpitPlayableActionVM(
        action_id="nav_cycle",
        label="NAV PAGE CYCLE",
        key_hint="APPLY",
        target_panel="LEFT MFD",
        cycle_effect="cycle left MFD situation page and redraw F1",
        source_owner="orion.mfd_page_state",
        evidence_policy="UI state event; no navigation runtime command",
    ),
    CockpitPlayableActionVM(
        action_id="sensor_focus",
        label="SENSOR FOCUS",
        key_hint="APPLY",
        target_panel="RIGHT MFD",
        cycle_effect="focus sensors page as a read-only projection",
        source_owner="orion.mfd_page_state",
        evidence_policy="UI state event; no sensor activation",
    ),
    CockpitPlayableActionVM(
        action_id="command_preview",
        label="COMMAND PREVIEW",
        key_hint="PREVIEW / APPLY",
        target_panel="COMMAND STRIP",
        cycle_effect="show request→validation→event loop without publishing a runtime command",
        source_owner="orion.f1_playable_loop",
        evidence_policy="local operator audit event only",
    ),
)

_ACTION_BY_ID = {action.action_id: action for action in _ACTIONS}

_EFFECT_PANEL_BY_ACTION_ID: dict[str, str] = {
    "body_self_check": "body",
    "power_refresh": "power",
    "nav_cycle": "nav",
    "sensor_focus": "sensors",
    "command_preview": "command",
}

_PANEL_TITLE_BY_ID: dict[str, str] = {
    "body": "BODY",
    "power": "POWER",
    "nav": "NAV",
    "sensors": "SENSORS",
    "command": "COMMAND",
    "event": "EVENT",
}

_COCKPIT_FOCUS_PANEL_ORDER: tuple[str, ...] = (
    "body",
    "power",
    "nav",
    "sensors",
    "command",
    "event",
)

_COCKPIT_PANEL_HINTS: dict[str, str] = {
    "body": "Body shows the current attach seed and runtime_ready boundary.",
    "power": "Power refresh reads the current projection; it does not enable PDU runtime.",
    "nav": "Navigation cycles the left MFD page; it does not publish a maneuver command.",
    "sensors": "Sensor focus opens the read-only sensor projection; it does not activate a scan.",
    "command": "Command preview rehearses request semantics; it does not publish to runtime.",
    "event": "Event keeps local cockpit history and points to evidence hints.",
}

_COCKPIT_EVENT_HISTORY_LIMIT = 5


def cockpit_playable_action_ids() -> tuple[str, ...]:
    """Stable action IDs for app-level selection and tests."""

    return tuple(action.action_id for action in _ACTIONS)


def normalize_cockpit_playable_action_id(value: str | None) -> str:
    """Return a known F1 action id; fail closed to the first action."""

    action_id = str(value or "").strip().lower()
    return action_id if action_id in _ACTION_BY_ID else _ACTIONS[0].action_id


def next_cockpit_playable_action_id(current: str | None, *, delta: int = 1) -> str:
    """Cycle through the F1 actions without mutating any runtime state."""

    ids = cockpit_playable_action_ids()
    current_id = normalize_cockpit_playable_action_id(current)
    try:
        index = ids.index(current_id)
    except ValueError:
        index = 0
    return ids[(index + int(delta)) % len(ids)]


def cockpit_playable_action_by_id(action_id: str | None) -> CockpitPlayableActionVM:
    """Return the action VM for a stable id."""

    return _ACTION_BY_ID[normalize_cockpit_playable_action_id(action_id)]


def cockpit_playable_effect_panel_id(action_id: str | None) -> str:
    """Return the visible F1 panel that must change for an action effect."""

    return _EFFECT_PANEL_BY_ACTION_ID.get(normalize_cockpit_playable_action_id(action_id), "command")


def normalize_cockpit_focus_panel_id(value: str | None, *, selected_action_id: str | None = None) -> str:
    """Return a known focus panel id, defaulting to the selected action target."""

    panel_id = str(value or "").strip().lower()
    if panel_id in _PANEL_TITLE_BY_ID:
        return panel_id
    return cockpit_playable_effect_panel_id(selected_action_id)


def next_cockpit_focus_panel_id(current: str | None, *, delta: int = 1) -> str:
    """Cycle through F1 panels without changing runtime state."""

    current_id = normalize_cockpit_focus_panel_id(current)
    try:
        index = _COCKPIT_FOCUS_PANEL_ORDER.index(current_id)
    except ValueError:
        index = 0
    return _COCKPIT_FOCUS_PANEL_ORDER[(index + int(delta)) % len(_COCKPIT_FOCUS_PANEL_ORDER)]


def _normalize_cockpit_effect_panel_id(value: str | None) -> str:
    panel_id = str(value or "").strip().lower()
    if panel_id in _PANEL_TITLE_BY_ID:
        return panel_id
    return ""


def build_cockpit_event_history_item(
    *,
    event_id: str | None,
    action_label: str | None,
    target_panel_id: str | None,
    effect_summary: str | None,
) -> dict[str, str]:
    """Build a serializable F1 event ticker item for app state."""

    panel_id = _normalize_cockpit_effect_panel_id(target_panel_id)
    return {
        "event_id": str(event_id or "none").strip() or "none",
        "action_label": str(action_label or "none").strip() or "none",
        "target_panel": _PANEL_TITLE_BY_ID.get(panel_id, "none"),
        "effect_summary": str(effect_summary or "none").strip() or "none",
    }


def _normalize_cockpit_event_history(
    value: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, str], ...]:
    """Normalize and bound the local F1 event ticker state."""

    items: list[dict[str, str]] = []
    for raw in value or ():
        if not isinstance(raw, Mapping):
            continue
        item = build_cockpit_event_history_item(
            event_id=raw.get("event_id"),
            action_label=raw.get("action_label"),
            target_panel_id=str(raw.get("target_panel") or "").lower(),
            effect_summary=raw.get("effect_summary"),
        )
        if item["event_id"] == "none":
            continue
        items.append(item)
    return tuple(items[-_COCKPIT_EVENT_HISTORY_LIMIT:])


def _build_cockpit_event_ticker_vms(
    value: Sequence[Mapping[str, Any]] | None,
) -> tuple[CockpitEventTickerItemVM, ...]:
    return tuple(CockpitEventTickerItemVM(**item) for item in _normalize_cockpit_event_history(value))


def build_cockpit_playable_state(
    *,
    selected_action_id: str | None = None,
    phase: str = "selected",
    cycle_count: int = 0,
    last_event_id: str | None = None,
    last_event_summary: str | None = None,
    last_action_id: str | None = None,
    last_effect_panel_id: str | None = None,
    last_effect_summary: str | None = None,
    action_history: Sequence[Mapping[str, Any]] | None = None,
    focused_panel_id: str | None = None,
    focus_reason: str | None = None,
    help_visible: bool | None = None,
) -> dict[str, Any]:
    """Build a serializable app-state dictionary for the F1 loop."""

    return {
        "selected_action_id": normalize_cockpit_playable_action_id(selected_action_id),
        "phase": normalize_cockpit_playable_phase(phase),
        "cycle_count": max(0, int(cycle_count or 0)),
        "last_event_id": str(last_event_id or "").strip(),
        "last_event_summary": str(last_event_summary or "").strip(),
        "last_action_id": (
            normalize_cockpit_playable_action_id(last_action_id)
            if str(last_action_id or "").strip()
            else ""
        ),
        "last_effect_panel_id": _normalize_cockpit_effect_panel_id(last_effect_panel_id),
        "last_effect_summary": str(last_effect_summary or "").strip(),
        "action_history": _normalize_cockpit_event_history(action_history),
        "focused_panel_id": normalize_cockpit_focus_panel_id(
            focused_panel_id, selected_action_id=selected_action_id
        ),
        "focus_reason": str(focus_reason or "default").strip() or "default",
        "help_visible": bool(help_visible) if help_visible is not None else True,
    }


def normalize_cockpit_playable_phase(value: str | None) -> str:
    phase = str(value or "").strip().lower()
    if phase in {"idle", "selected", "preview", "requested", "applied", "event_recorded", "evidence_visible"}:
        return phase
    return "selected"


def _state_int(state: Mapping[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(state.get(key, default))
    except Exception:
        return default


def _state_text(state: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(state.get(key, default) or "").strip()


def build_cockpit_playable_loop_vm(
    *,
    loop_state: Mapping[str, Any] | None,
    body_vm: BodyStructureConsoleViewModel,
    body_physics_vm: BodyPhysicsConsoleViewModel,
    power_vm: PowerThermalConsoleViewModel,
    active_left_mfd_page: str,
    active_right_mfd_page: str,
    nats_connected: bool,
    active_incidents: int,
) -> CockpitPlayableLoopVM:
    """Derive one visible F1 playable cockpit loop from existing view-models.

    The VM is deliberately a projection: it summarizes already-derived body/power/MFD
    state and a local F1 loop state. It does not authorize or execute runtime commands.
    """

    state = loop_state or {}
    selected_action_id = normalize_cockpit_playable_action_id(_state_text(state, "selected_action_id"))
    selected_action = cockpit_playable_action_by_id(selected_action_id)
    ids = cockpit_playable_action_ids()
    selected_index = ids.index(selected_action_id)
    phase = normalize_cockpit_playable_phase(_state_text(state, "phase", "selected"))
    left_page = normalize_mfd_page("left", active_left_mfd_page)
    right_page = normalize_mfd_page("right", active_right_mfd_page)
    last_event_id = _state_text(state, "last_event_id") or "none"
    last_event_summary = _state_text(state, "last_event_summary") or "none"
    last_action_id = _state_text(state, "last_action_id")
    if last_action_id:
        last_action_id = normalize_cockpit_playable_action_id(last_action_id)
        last_action_label = cockpit_playable_action_by_id(last_action_id).label
    else:
        last_action_id = "none"
        last_action_label = "none"
    last_effect_panel_id = _normalize_cockpit_effect_panel_id(_state_text(state, "last_effect_panel_id"))
    last_effect_summary = _state_text(state, "last_effect_summary") or "none"
    cycle_count = max(0, _state_int(state, "cycle_count"))
    focused_panel_id = normalize_cockpit_focus_panel_id(
        _state_text(state, "focused_panel_id"), selected_action_id=selected_action_id
    )
    focused_panel_title = _PANEL_TITLE_BY_ID.get(focused_panel_id, "COMMAND")
    focus_reason = _state_text(state, "focus_reason", "default") or "default"
    help_visible = bool(state.get("help_visible", True))
    raw_history = state.get("action_history")
    if isinstance(raw_history, Sequence) and not isinstance(raw_history, (str, bytes)):
        action_history = _build_cockpit_event_ticker_vms(raw_history)
    else:
        action_history = ()

    module_text = body_vm.module_id or "none"
    selected_face = body_vm.selected_face_id or "unknown"
    body_summary = (
        f"BODY: {body_vm.seed_status} | face={selected_face} | module={module_text} | "
        f"ready={str(body_vm.runtime_ready).lower()}"
    )
    power_summary = (
        f"POWER: SoC_bat={format_soc_bat(power_vm.battery_soc_pct)} | "
        f"SoC_cap={format_soc_cap(power_vm.supercap_soc_pct)} | peak={power_vm.peak_readiness}"
    )
    nav_summary = (
        f"MFD: left={mfd_page_label('left', left_page)}/{left_page} | "
        f"right={mfd_page_label('right', right_page)}/{right_page}"
    )
    sensor_summary = "SENSORS: read-only projection | no active scan in F1 slice"
    command_summary = (
        "COMMAND: preview/request/event loop only | "
        "no publish/ACK/effect claim in this slice"
    )
    if nats_connected:
        source = "orion app state + telemetry adapters"
    else:
        source = "orion local state + missing/partial telemetry"
    if active_incidents > 0:
        loop_status = "attention"
    else:
        loop_status = "online"

    return CockpitPlayableLoopVM(
        loop_status=loop_status,
        phase=phase,
        selected_action_id=selected_action_id,
        selected_action_label=selected_action.label,
        selected_action_index=selected_index,
        actions_count=len(_ACTIONS),
        action_summary=selected_action.cycle_effect,
        source=source,
        trust_status="view_model_backed",
        runtime_claim_status="local_ui_loop_no_runtime_command",
        cycle_count=cycle_count,
        last_event_id=last_event_id,
        last_event_summary=last_event_summary,
        last_action_id=last_action_id,
        last_action_label=last_action_label,
        last_effect_panel_id=last_effect_panel_id,
        last_effect_summary=last_effect_summary,
        action_history=action_history,
        focused_panel_id=focused_panel_id,
        focused_panel_title=focused_panel_title,
        focus_reason=focus_reason,
        help_visible=help_visible,
        body_summary=body_summary,
        power_summary=power_summary,
        nav_summary=nav_summary,
        sensor_summary=sensor_summary,
        command_summary=command_summary,
        available_actions=_ACTIONS,
    )


def build_cockpit_focus_vm(vm: CockpitPlayableLoopVM) -> CockpitFocusVM:
    """Build the current F1 focus affordance from the playable loop VM."""

    return CockpitFocusVM(
        focused_panel_id=vm.focused_panel_id,
        focused_panel_title=vm.focused_panel_title,
        focused_action_id=vm.selected_action_id,
        focused_action_label=vm.selected_action_label,
        focus_reason=vm.focus_reason,
        can_preview=True,
        can_apply=True,
        can_open_evidence=vm.last_event_id != "none",
        help_visible=vm.help_visible,
        palette_hint="Ctrl+P command palette enabled; type body/power/nav/sensor/command",
    )


def build_cockpit_hint_vms(vm: CockpitPlayableLoopVM) -> tuple[CockpitHintVM, ...]:
    """Build context-sensitive F1 hints for the focused panel."""

    panel_hint = _COCKPIT_PANEL_HINTS.get(vm.focused_panel_id, _COCKPIT_PANEL_HINTS["command"])
    hints = [
        CockpitHintVM(
            hint_id="f1_keys",
            panel_id=vm.focused_panel_id,
            severity="info",
            text="←/→ action | ↑/↓ panel | SPACE preview | ENTER apply | E evidence | H help",
            key_hint="keyboard",
            source="orion.f1_focus_view_model",
            trust_status="view_model_backed",
        ),
        CockpitHintVM(
            hint_id="f1_panel",
            panel_id=vm.focused_panel_id,
            severity="info",
            text=panel_hint,
            key_hint=vm.focused_panel_title,
            source="orion.f1_focus_view_model",
            trust_status="view_model_backed",
        ),
    ]
    if vm.last_event_id != "none":
        hints.append(
            CockpitHintVM(
                hint_id="f1_evidence",
                panel_id="event",
                severity="info",
                text=f"Latest local event {vm.last_event_id}; press E to inspect evidence surface.",
                key_hint="E",
                source="f1_playable_loop_audit_marker",
                trust_status="local_event_backed",
            )
        )
    else:
        hints.append(
            CockpitHintVM(
                hint_id="f1_evidence_pending",
                panel_id="event",
                severity="info",
                text="No local event yet; press SPACE then ENTER to produce an evidence hint.",
                key_hint="SPACE→ENTER",
                source="orion.f1_focus_view_model",
                trust_status="view_model_backed",
            )
        )
    return tuple(hints)


def build_cockpit_action_help_vm(vm: CockpitPlayableLoopVM) -> CockpitActionHelpVM:
    """Build the selected action help/preview contract."""

    action = cockpit_playable_action_by_id(vm.selected_action_id)
    target_panel = _PANEL_TITLE_BY_ID.get(cockpit_playable_effect_panel_id(action.action_id), "COMMAND")
    return CockpitActionHelpVM(
        action_id=action.action_id,
        action_label=action.label,
        target_panel=target_panel,
        summary=action.cycle_effect,
        preview_text=f"Preview {action.label}: {action.cycle_effect}.",
        apply_text=f"Apply records a local cockpit event for {target_panel}; no runtime command is published.",
        result_text=f"Result target: {target_panel}; evidence policy: {action.evidence_policy}.",
        runtime_claim_status="local_ui_loop_no_runtime_command",
    )


def format_cockpit_focus_hint_lines(vm: CockpitPlayableLoopVM) -> tuple[str, ...]:
    """Return visible focus/help/palette rows for F1."""

    focus = build_cockpit_focus_vm(vm)
    action_help = build_cockpit_action_help_vm(vm)
    preview_line = (
        "F1 PREVIEW | "
        f"target={action_help.target_panel} | expected_effect={action_help.summary} | runtime_command=no"
    )
    result_line = (
        "F1 RESULT | "
        f"applied={vm.last_action_label} | target={_PANEL_TITLE_BY_ID.get(vm.last_effect_panel_id, 'none')} | "
        f"event={vm.last_event_id} | evidence_hint={'available' if vm.last_event_id != 'none' else 'pending'}"
    )
    lines = [
        (
            "F1 FOCUS | "
            f"panel={focus.focused_panel_title} | action={focus.focused_action_label} | "
            f"can_preview={'yes' if focus.can_preview else 'no'} | "
            f"can_apply={'yes' if focus.can_apply else 'no'} | "
            f"evidence={'yes' if focus.can_open_evidence else 'pending'} | "
            f"reason={focus.focus_reason}"
        ),
        (
            "F1 HINT | "
            "←/→ action | ↑/↓ panel | SPACE preview | ENTER apply | "
            "E evidence | H help | Ctrl+P palette"
        ),
        (
            "F1 HELP | "
            f"{action_help.action_label} → {action_help.summary}; "
            "no runtime command published"
        ),
        (
            "F1 PALETTE | Ctrl+P | fuzzy search: body / power / nav / sensors / command | "
            "discoverability=enabled"
        ),
    ]
    if vm.help_visible:
        for hint in build_cockpit_hint_vms(vm):
            lines.append(
                f"F1 CONTEXT | {hint.panel_id.upper()} | severity={hint.severity} | "
                f"key={hint.key_hint} | {hint.text} | trust={hint.trust_status}"
            )
    else:
        lines.append("F1 CONTEXT | hidden | press H to show help")
    lines.extend([preview_line, result_line])
    return tuple(lines)


def build_cockpit_visible_panel_vms(vm: CockpitPlayableLoopVM) -> tuple[CockpitVisiblePanelVM, ...]:
    """Build the six mandatory F1 panels for visible acceptance.

    This is intentionally derived from the already-built playable loop VM, so
    F1 cannot show a different body/power/nav/sensor/command/event story in
    separate places.  The event panel is considered visible even before an event
    exists; it reports ``none`` rather than inventing an event.
    """

    event_status = "recorded" if vm.last_event_id != "none" else "ready"

    def _with_effect(panel_id: str, summary: str) -> str:
        if panel_id == vm.last_effect_panel_id and vm.last_effect_summary != "none":
            return f"{summary} | last_effect={vm.last_effect_summary}"
        return f"{summary} | last_effect=none"

    return (
        CockpitVisiblePanelVM(
            panel_id="body",
            title="BODY",
            status="shown",
            source="body_structure_view_model",
            trust_status="view_model_backed",
            summary=_with_effect("body", vm.body_summary),
        ),
        CockpitVisiblePanelVM(
            panel_id="power",
            title="POWER",
            status="shown",
            source="power_thermal_view_model",
            trust_status="view_model_backed",
            summary=_with_effect("power", vm.power_summary),
        ),
        CockpitVisiblePanelVM(
            panel_id="nav",
            title="NAV",
            status="shown",
            source="mfd_page_state",
            trust_status="ui_state_backed",
            summary=_with_effect("nav", vm.nav_summary),
        ),
        CockpitVisiblePanelVM(
            panel_id="sensors",
            title="SENSORS",
            status="shown",
            source="sensor_projection_placeholder",
            trust_status="view_model_backed",
            summary=_with_effect("sensors", vm.sensor_summary),
        ),
        CockpitVisiblePanelVM(
            panel_id="command",
            title="COMMAND",
            status="shown",
            source="f1_playable_loop",
            trust_status="local_loop_backed",
            summary=_with_effect("command", vm.command_summary),
        ),
        CockpitVisiblePanelVM(
            panel_id="event",
            title="EVENT",
            status=event_status,
            source="f1_playable_loop_audit_marker",
            trust_status="local_event_backed",
            summary=(
                f"EVENT: last_event={vm.last_event_id} | {vm.last_event_summary} | "
                f"applied_action={vm.last_action_label} | "
                f"target={_PANEL_TITLE_BY_ID.get(vm.last_effect_panel_id, 'none')} | "
                f"history={len(vm.action_history)}"
            ),
        ),
    )


def format_cockpit_event_ticker_lines(vm: CockpitPlayableLoopVM) -> tuple[str, ...]:
    """Return the local F1 event history visible in cockpit.

    This is a visible acceptance layer: after repeated Apply operations the
    operator can see that the cockpit loop is accumulating local events.
    """

    if not vm.action_history:
        return (
            "F1 EVENT TICKER | entries=0 | latest=none",
            "event_history: none",
        )
    latest = vm.action_history[-1]
    lines = [
        (
            "F1 EVENT TICKER | "
            f"entries={len(vm.action_history)} | latest={latest.event_id} | "
            f"action={latest.action_label} | target={latest.target_panel}"
        )
    ]
    for index, item in enumerate(reversed(vm.action_history), start=1):
        lines.append(
            f"event[{index}]: {item.event_id} | {item.action_label} -> "
            f"{item.target_panel} | {item.effect_summary}"
        )
    return tuple(lines)


def format_cockpit_visible_acceptance_lines(vm: CockpitPlayableLoopVM) -> tuple[str, ...]:
    """Return a stable visible-acceptance section for F1.

    Acceptance is deliberately about visible, deterministic UI completion.  It
    does not mean the underlying QIKI Body runtime is complete.
    """

    panels = build_cockpit_visible_panel_vms(vm)
    ready_count = sum(1 for panel in panels if panel.status in {"shown", "ready", "recorded"})
    panel_flags = " | ".join(f"{panel.title}=yes" for panel in panels)
    lines = [
        f"F1 PANELS | visible_acceptance=ready | panels={ready_count}/{len(panels)}",
        panel_flags,
        f"EVENT: status={'recorded' if vm.last_event_id != 'none' else 'ready'} | "
        f"event={vm.last_event_id} | history={len(vm.action_history)}",
    ]
    for panel in panels:
        lines.append(
            f"{panel.title}: status={panel.status} | source={panel.source} | "
            f"trust={panel.trust_status} | {panel.summary}"
        )
    lines.append(f"visible_acceptance: {panel_flags}")
    target_title = _PANEL_TITLE_BY_ID.get(vm.last_effect_panel_id, "none")
    lines.append(
        "F1 ACTION EFFECT | "
        f"applied={vm.last_action_label} | target={target_title} | "
        f"effect={vm.last_effect_summary} | event={vm.last_event_id}"
    )
    lines.append(
        "action_effect_targets: "
        "BODY SELF-CHECK→BODY | POWER REFRESH→POWER | NAV PAGE CYCLE→NAV | "
        "SENSOR FOCUS→SENSORS | COMMAND PREVIEW→COMMAND"
    )
    return tuple(lines)


def format_cockpit_playable_loop_lines(vm: CockpitPlayableLoopVM) -> tuple[str, ...]:
    """Compact F1 cockpit text block for the visible QIKI/operator MFD panel."""

    return (
        (
            "F1 PLAYABLE LOOP | "
            f"{vm.loop_status} | phase={vm.phase} | "
            f"selected={vm.selected_action_label} ({vm.selected_action_index + 1}/{vm.actions_count})"
        ),
        "cycle: snapshot → display → preview → request → applied → event → evidence",
        f"source: {vm.source} | trust={vm.trust_status}",
        f"runtime_claim_status: {vm.runtime_claim_status}",
        *format_cockpit_focus_hint_lines(vm),
        f"{vm.body_summary}",
        f"{vm.power_summary}",
        f"{vm.nav_summary}",
        f"{vm.sensor_summary}",
        f"{vm.command_summary}",
        f"action_effect: {vm.action_summary}",
        f"last_event: {vm.last_event_id} | {vm.last_event_summary}",
        *format_cockpit_event_ticker_lines(vm),
        *format_cockpit_visible_acceptance_lines(vm),
        "keys: ◀/▶ select | SPACE preview | ENTER apply | B body | R reset | E evidence",
    )


def format_cockpit_playable_action_labels(vm: CockpitPlayableLoopVM) -> tuple[tuple[str, str, bool], ...]:
    """Return button labels for the F1 local action strip.

    Tuple: (button_id_suffix, label, highlighted).
    """

    return (
        ("prev", "◀ Action", False),
        ("preview", f"Preview · {vm.selected_action_label}", vm.phase == "preview"),
        ("apply", f"Apply · {vm.selected_action_label}", vm.phase in {"applied", "event_recorded", "evidence_visible"}),
        ("next", "Action ▶", False),
    )


__all__ = [
    "CockpitActionHelpVM",
    "CockpitEventTickerItemVM",
    "CockpitFocusVM",
    "CockpitHintVM",
    "CockpitPlayableActionVM",
    "CockpitPlayableLoopVM",
    "CockpitVisiblePanelVM",
    "build_cockpit_action_help_vm",
    "build_cockpit_focus_vm",
    "build_cockpit_hint_vms",
    "build_cockpit_playable_loop_vm",
    "build_cockpit_visible_panel_vms",
    "build_cockpit_event_history_item",
    "build_cockpit_playable_state",
    "cockpit_playable_action_by_id",
    "cockpit_playable_action_ids",
    "cockpit_playable_effect_panel_id",
    "format_cockpit_playable_action_labels",
    "format_cockpit_event_ticker_lines",
    "format_cockpit_focus_hint_lines",
    "format_cockpit_playable_loop_lines",
    "format_cockpit_visible_acceptance_lines",
    "next_cockpit_focus_panel_id",
    "next_cockpit_playable_action_id",
    "normalize_cockpit_focus_panel_id",
    "normalize_cockpit_playable_action_id",
    "normalize_cockpit_playable_phase",
]
