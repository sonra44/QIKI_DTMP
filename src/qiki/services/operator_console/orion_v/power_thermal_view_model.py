"""Visible Power / Thermal view-model for ORION V.

This module is the first visible operator-console bridge for the QIKI power and
thermal canon. Until a live telemetry transport is wired in, the default ORION
path reports unknown power/thermal values instead of fixture numbers. Explicit
test/seed callers may pass values into the builder; those remain marked as
local/direct and do not claim full QIKI Body runtime conformance.

Canonical boundary:
    source -> battery -> bus -> supercap -> peak consumers

Current terminology:
    SoC_bat  = long-duration battery reserve.
    SoC_cap  = supercap / peak-buffer readiness for short peak actions.
    PDU      = allowance / denial gate for loads; not implemented here.

This module does not execute boost, invoke PDU runtime, simulate heat, or enable
module capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from qiki.services.operator_console.orion_v.evidence_card_vm import EvidenceCardVM
from qiki.shared.supercap_gate import classify_cap_gate

POWER_THERMAL_MODE = "console-visible power/thermal seed"
POWER_THERMAL_SOURCE = "local_power_thermal_seed_fixture"
POWER_THERMAL_TRANSPORT = "direct in-process adapter"
POWER_THERMAL_TRUST = "fixture_only"
POWER_THERMAL_CARD_TYPE = "POWER_THERMAL_STATUS"
POWER_THERMAL_CHAIN = "source -> battery -> bus -> supercap -> peak consumers"
POWER_TERMINOLOGY_NOTE = "SoC_bat=long-duration reserve; SoC_cap=supercap peak-action readiness"
PDU_RUNTIME_BOUNDARY = "target-only; no full PDU runtime in this patch"
THERMAL_RUNTIME_BOUNDARY = "seed-only; no thermal simulation in this patch"
COMMAND_GATING_BOUNDARY = "target-only unless runtime evidence exists"

_DEFAULT_BLOCKED_COMMANDS_FOR_LOW_CAP = (
    "boost",
    "high-power scan",
    "NBL emergency packet",
    "active field",
)
_DEFAULT_BLOCKED_COMMANDS_FOR_LIMITED_PEAK = (
    "boost",
    "high-power scan",
)
_DEFAULT_BLOCKED_COMMANDS_FOR_UNKNOWN_CAP = _DEFAULT_BLOCKED_COMMANDS_FOR_LOW_CAP


@dataclass(frozen=True, slots=True)
class ThermalNodeView:
    node_id: str
    thermal_class: str
    temperature_c: float | None
    blocked_commands: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    trust_status: str = POWER_THERMAL_TRUST


@dataclass(frozen=True, slots=True)
class PowerThermalConsoleViewModel:
    mode: str
    source: str
    transport: str
    trust_status: str
    battery_soc_pct: int | None
    supercap_soc_pct: int | None
    bus_state: str
    pdu_state: str
    peak_ready: bool
    peak_readiness: str
    thermal_status: str
    thermal_nodes: tuple[ThermalNodeView, ...]
    blocked_commands: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evidence_card_type: str
    evidence_card_id: str
    read_only: bool
    runtime_conformance: str
    operator_summary: str
    telemetry_freshness: str = "unknown"
    source_generation_w: float | None = None
    bus_voltage_v: float | None = None
    bus_current_a: float | None = None
    loads_w: tuple[tuple[str, float], ...] = ()


# Compatibility alias for code/tests that use the current power terminology.
PowerAccumulatorConsoleViewModel = PowerThermalConsoleViewModel


def get_power_thermal_console_view_model() -> PowerThermalConsoleViewModel:
    """Return the default visible Power / Thermal placeholder for ORION screens."""
    return build_power_thermal_console_view_model()


def build_power_thermal_console_view_model_from_telemetry(
    telemetry: Mapping[str, Any] | None,
    *,
    freshness: str | None = None,
) -> PowerThermalConsoleViewModel:
    """Build an ORION Power / Accumulator VM from an existing telemetry snapshot."""
    telemetry_map = dict(telemetry or {})
    power = _extract_power_block(telemetry_map)
    if not power:
        return _missing_power_telemetry_vm()

    battery_soc = _first_number(power, "soc_pct", "battery_soc_pct")
    supercap_soc = _first_number(power, "supercap_soc_pct", "supercap_soc")
    bus_v = _first_number(power, "bus_v", "bus_voltage_V", "bus_voltage_v")
    bus_a = _first_number(power, "bus_a", "bus_current_A", "bus_current_a")
    loads_w = _numeric_pairs(power.get("loads_w"))
    sources_w = dict(_numeric_pairs(power.get("sources_w")))
    source_generation_w = _source_generation_w(sources_w, power)
    bus_state = _bus_state(power, bus_v, bus_a)
    pdu_state = _pdu_state(power, bus_state)
    thermal_nodes = _thermal_nodes_from_snapshot(telemetry_map)

    vm = build_power_thermal_console_view_model(
        battery_soc_pct=battery_soc,
        supercap_soc_pct=supercap_soc,
        bus_state=bus_state,
        pdu_state=pdu_state,
        thermal_nodes=thermal_nodes,
    )
    telemetry_freshness = freshness or _freshness_from_snapshot(telemetry_map)
    extra_reasons = _telemetry_reason_codes(
        power,
        freshness=telemetry_freshness,
        battery_soc_pct=battery_soc,
        bus_voltage_v=bus_v,
        bus_current_a=bus_a,
        source_generation_w=source_generation_w,
    )
    reasons = _stable_unique((*vm.reason_codes, *extra_reasons))
    trust = _telemetry_trust_status(reasons, telemetry_freshness)
    source = str(power.get("source") or telemetry_map.get("source") or "q_sim_service.world_model.power")
    evidence_suffix = (
        "telemetry_ok" if not reasons else "telemetry_" + "_".join(reason.lower() for reason in reasons)
    )
    summary = _operator_summary(
        battery_soc_pct=vm.battery_soc_pct,
        supercap_soc_pct=vm.supercap_soc_pct,
        bus_state=bus_state,
        peak_readiness=vm.peak_readiness,
        thermal_status=vm.thermal_status,
        reason_codes=reasons,
    )
    return replace(
        vm,
        mode="console-visible power telemetry adapter",
        source=source,
        transport="orion telemetry snapshot adapter",
        trust_status=trust,
        reason_codes=reasons,
        evidence_card_id=f"power-telemetry:{evidence_suffix}",
        runtime_conformance="telemetry adapter; full PDU runtime not claimed",
        operator_summary=summary,
        telemetry_freshness=telemetry_freshness,
        source_generation_w=source_generation_w,
        bus_voltage_v=bus_v,
        bus_current_a=bus_a,
        loads_w=loads_w,
    )


def build_power_thermal_console_view_model(
    *,
    battery_soc_pct: int | float | str | None = None,
    supercap_soc_pct: int | float | str | None = None,
    bus_state: str = "unknown",
    pdu_state: str = "unknown",
    thermal_nodes: Iterable[ThermalNodeView] | None = None,
) -> PowerThermalConsoleViewModel:
    """Build a deterministic local power/thermal view-model.

    This helper keeps tests explicit and future telemetry replacement simple: live
    telemetry can feed the same fields later without changing the Textual widgets.
    """
    battery_soc = _soc_int_or_none(battery_soc_pct)
    supercap_soc = _soc_int_or_none(supercap_soc_pct)
    nodes = tuple(thermal_nodes or default_thermal_nodes())
    peak_ready, peak_readiness, blocked_commands, reason_codes = _peak_state(supercap_soc)
    thermal_status, thermal_blocked, thermal_reasons = _thermal_state(nodes)
    if thermal_reasons and peak_ready:
        peak_ready = False
        peak_readiness = "blocked"
    blocked = _stable_unique((*blocked_commands, *thermal_blocked))
    reasons = _stable_unique((*reason_codes, *thermal_reasons))
    summary = _operator_summary(
        battery_soc_pct=battery_soc,
        supercap_soc_pct=supercap_soc,
        bus_state=bus_state,
        peak_readiness=peak_readiness,
        thermal_status=thermal_status,
        reason_codes=reasons,
    )
    if not reasons:
        evidence_suffix = "ok"
    elif any(reason in {"POWER_TELEM_MISSING", "NO_LIVE_POWER_SOURCE"} for reason in reasons):
        evidence_suffix = "missing_" + "_".join(reason.lower() for reason in reasons)
    else:
        evidence_suffix = "blocked_" + "_".join(reason.lower() for reason in reasons)
    return PowerThermalConsoleViewModel(
        mode=POWER_THERMAL_MODE,
        source=POWER_THERMAL_SOURCE,
        transport=POWER_THERMAL_TRANSPORT,
        trust_status=POWER_THERMAL_TRUST,
        battery_soc_pct=battery_soc,
        supercap_soc_pct=supercap_soc,
        bus_state=bus_state,
        pdu_state=pdu_state,
        peak_ready=peak_ready,
        peak_readiness=peak_readiness,
        thermal_status=thermal_status,
        thermal_nodes=nodes,
        blocked_commands=blocked,
        reason_codes=reasons,
        evidence_card_type=POWER_THERMAL_CARD_TYPE,
        evidence_card_id=f"power-thermal-seed:{evidence_suffix}",
        read_only=True,
        runtime_conformance="not claimed",
        operator_summary=summary,
        telemetry_freshness="seed",
    )


def default_thermal_nodes() -> tuple[ThermalNodeView, ...]:
    """Minimal visible node list from the QIKI Body thermal canon."""
    return (
        ThermalNodeView("T_battery", "unknown", None),
        ThermalNodeView("T_supercap", "unknown", None),
        ThermalNodeView("T_pdu", "unknown", None),
        ThermalNodeView("T_sensor_head", "unknown", None),
        ThermalNodeView("T_comms", "unknown", None),
        ThermalNodeView("T_core", "unknown", None),
    )


def format_soc_bat(value: Any) -> str:
    """Render SoC_bat using unknown-safe percent formatting."""
    return _pct_text(value)


def format_soc_cap(value: Any) -> str:
    """Render SoC_cap using unknown-safe percent formatting."""
    return _pct_text(value)


def format_power_thermal_cockpit_line(vm: PowerThermalConsoleViewModel | None = None) -> str:
    """Compact F1 line. It must remain glanceable, not a table."""
    vm = vm or get_power_thermal_console_view_model()
    reason_codes = tuple(_vm_get(vm, "reason_codes", ()) or ())
    # §19.6 / ADR-0014: the glanceable F1 line must carry data freshness, not just
    # source. This is the power subsystem's own freshness (single-owner safe) —
    # global snapshot freshness belongs to the mission-control АКТУАЛ element.
    freshness = str(_vm_get(vm, "telemetry_freshness", "unknown"))
    stale_mark = " [УСТАРЕЛО]" if freshness.lower() == "stale" else ""
    base = (
        f"POWER({_vm_get(vm, 'source', POWER_THERMAL_SOURCE)}) | "
        f"SoC_bat={format_soc_bat(_vm_get(vm, 'battery_soc_pct'))} | "
        f"SoC_cap={format_soc_cap(_vm_get(vm, 'supercap_soc_pct'))} | "
        f"bus={_vm_get(vm, 'bus_state', 'unknown')} | "
        f"peak={_vm_get(vm, 'peak_readiness', 'unknown')} | "
        f"thermal={_vm_get(vm, 'thermal_status', 'unknown')} | "
        f"freshness={freshness}{stale_mark}"
    )
    if reason_codes:
        return f"{base} | reason={reason_codes[0]}"
    return base


def format_power_accumulator_mfd_lines(
    vm: PowerThermalConsoleViewModel | None = None,
) -> tuple[str, ...]:
    """Return the Power / Accumulator MFD page lines.

    This is a display contract, not PDU runtime. It uses SoC_bat / SoC_cap /
    supercap / peak buffer instead of a single generic energy gauge.
    """
    vm = vm or get_power_thermal_console_view_model()
    blocked_commands = tuple(_vm_get(vm, "blocked_commands", ()) or ())
    reason_codes = tuple(_vm_get(vm, "reason_codes", ()) or ())
    blocked = ", ".join(blocked_commands) if blocked_commands else "none"
    reasons = ", ".join(reason_codes) if reason_codes else "none"
    return (
        "Power / Thermal / Accumulator",
        f"canonical_chain: {POWER_THERMAL_CHAIN}",
        f"source: {_vm_get(vm, 'source', POWER_THERMAL_SOURCE)}",
        f"transport: {_vm_get(vm, 'transport', POWER_THERMAL_TRANSPORT)}",
        f"runtime_conformance: {_vm_get(vm, 'runtime_conformance', 'not claimed')}",
        "",
        "Battery / Long-duration reserve",
        f"SoC_bat: {format_soc_bat(_vm_get(vm, 'battery_soc_pct'))}",
        "role: long-duration reserve, not immediate peak permission",
        "",
        "Supercap / Peak buffer",
        f"SoC_cap: {format_soc_cap(_vm_get(vm, 'supercap_soc_pct'))}",
        "role: peak-action readiness for short peak actions",
        f"peak_ready: {str(_vm_get(vm, 'peak_ready', False)).lower()}",
        f"peak_readiness: {_vm_get(vm, 'peak_readiness', 'unknown')}",
        f"blocked_peak_commands: {blocked}",
        f"reason_codes: {reasons}",
        "",
        "PDU / Thermal boundary",
        f"bus_state: {_vm_get(vm, 'bus_state', 'unknown')}",
        f"PDU_state: {_vm_get(vm, 'pdu_state', 'unknown')}",
        f"PDU_boundary: {PDU_RUNTIME_BOUNDARY}",
        f"thermal_clearance: {THERMAL_RUNTIME_BOUNDARY}",
        f"command_gating: {COMMAND_GATING_BOUNDARY}",
        "",
        "Telemetry / Runtime fields",
        f"freshness: {_vm_get(vm, 'telemetry_freshness', 'unknown')}",
        f"source_generation_W: {_watts_text(_vm_get(vm, 'source_generation_w'))}",
        f"bus_voltage_V: {_volts_text(_vm_get(vm, 'bus_voltage_v'))}",
        f"bus_current_A: {_amps_text(_vm_get(vm, 'bus_current_a'))}",
        f"loads_W: {_loads_text(_vm_get(vm, 'loads_w', ()))}",
    )


def format_power_thermal_system_summary(vm: PowerThermalConsoleViewModel | None = None) -> str:
    """F2 textual fallback/summary for the Power / Thermal card."""
    vm = vm or get_power_thermal_console_view_model()
    lines = list(format_power_accumulator_mfd_lines(vm))
    lines.append("")
    lines.append("Thermal Nodes")
    for node in _vm_get(vm, "thermal_nodes", ()) or ():
        blocked_node = ", ".join(node.blocked_commands) if node.blocked_commands else "none"
        lines.append(f"  {node.node_id:<16} {node.thermal_class:<7} blocked={blocked_node}")
    evidence_type = _vm_get(vm, "evidence_card_type", POWER_THERMAL_CARD_TYPE)
    evidence_id = _vm_get(vm, "evidence_card_id", "power-thermal-seed:unknown")
    lines.extend(
        [
            f"Evidence: {evidence_type} / {evidence_id}",
            "Boundary: local power/thermal seed fixture, not full PDU runtime",
        ]
    )
    return "\n".join(lines)


def build_power_thermal_evidence_card_vms(
    vm: PowerThermalConsoleViewModel | None = None,
) -> list[EvidenceCardVM]:
    """Return read-only Evidence Card VM for F8."""
    vm = vm or get_power_thermal_console_view_model()
    reason_codes = tuple(_vm_get(vm, "reason_codes", ()) or ())
    reason_text = ", ".join(reason_codes)
    if "POWER_TELEM_MISSING" in reason_codes or "NO_LIVE_POWER_SOURCE" in reason_codes:
        state_key = "missing"
    else:
        state_key = "blocked" if reason_codes else "ok"
    blocked_commands = tuple(_vm_get(vm, "blocked_commands", ()) or ())
    blocked_text = ", ".join(blocked_commands) if blocked_commands else "none"
    return [
        EvidenceCardVM(
            subsystem="ПИТАНИЕ/НАКОПИТЕЛИ",
            state_key=state_key,
            headline=(
                f"{_vm_get(vm, 'evidence_card_type', POWER_THERMAL_CARD_TYPE)} | "
                f"peak={_vm_get(vm, 'peak_readiness', 'unknown')} | "
                f"thermal={_vm_get(vm, 'thermal_status', 'unknown')}"
            ),
            reason_text=reason_text,
            detail_lines=(
                f"canonical_chain: {POWER_THERMAL_CHAIN}",
                f"SoC_bat: {format_soc_bat(_vm_get(vm, 'battery_soc_pct'))}",
                f"SoC_cap: {format_soc_cap(_vm_get(vm, 'supercap_soc_pct'))}",
                "SoC_bat_role: long-duration reserve",
                "SoC_cap_role: supercap / peak-action readiness",
                f"bus_state: {_vm_get(vm, 'bus_state', 'unknown')}",
                f"PDU_state: {_vm_get(vm, 'pdu_state', 'unknown')}",
                f"blocked_peak_commands: {blocked_text}",
                f"source: {_vm_get(vm, 'source', POWER_THERMAL_SOURCE)}",
                f"transport: {_vm_get(vm, 'transport', POWER_THERMAL_TRANSPORT)}",
                f"freshness: {_vm_get(vm, 'telemetry_freshness', 'unknown')}",
                f"source_generation_W: {_watts_text(_vm_get(vm, 'source_generation_w'))}",
                f"bus_voltage_V: {_volts_text(_vm_get(vm, 'bus_voltage_v'))}",
                f"bus_current_A: {_amps_text(_vm_get(vm, 'bus_current_a'))}",
                f"trust: {_vm_get(vm, 'trust_status', POWER_THERMAL_TRUST)}",
                f"read_only: {str(_vm_get(vm, 'read_only', True)).lower()}",
                f"runtime_conformance: {_vm_get(vm, 'runtime_conformance', 'not claimed')}",
                f"PDU_boundary: {PDU_RUNTIME_BOUNDARY}",
                f"thermal_boundary: {THERMAL_RUNTIME_BOUNDARY}",
                f"evidence_card_id: {_vm_get(vm, 'evidence_card_id', 'power-thermal-seed:unknown')}",
            ),
        )
    ]


def _peak_state(supercap_soc_pct: int | None) -> tuple[bool, str, tuple[str, ...], tuple[str, ...]]:
    # C5: шкала готовности выводится из владельца (shared/supercap_gate,
    # T_boost/T_hold) — были локальные 20/70, и при SoC_cap 61-69% чип PWR
    # говорил ▸БУСТ, а карточка F2 — limited.
    gate = classify_cap_gate(supercap_soc_pct)
    if gate == "boost":
        return True, "ready", (), ()
    if gate == "hold":
        return False, "limited", _DEFAULT_BLOCKED_COMMANDS_FOR_LIMITED_PEAK, ("PEAK_LIMITED",)
    if gate == "stab":
        return False, "blocked", _DEFAULT_BLOCKED_COMMANDS_FOR_LOW_CAP, ("CAP_LOW",)
    return False, "unknown", _DEFAULT_BLOCKED_COMMANDS_FOR_UNKNOWN_CAP, ("POWER_TELEM_MISSING",)


def _thermal_state(nodes: tuple[ThermalNodeView, ...]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    blocked: list[str] = []
    reasons: list[str] = []
    if nodes and all(node.thermal_class == "unknown" for node in nodes):
        status = "unknown"
    elif any(node.thermal_class in {"red", "black"} for node in nodes):
        status = "critical"
    elif any(node.thermal_class == "orange" for node in nodes):
        status = "orange"
    elif any(node.thermal_class in {"unknown", "missing"} for node in nodes):
        status = "unknown"
    else:
        status = "green"
    for node in nodes:
        if node.thermal_class in {"orange", "red", "black"}:
            blocked.extend(node.blocked_commands or ("peak actions",))
            reasons.extend(node.reason_codes or ("THERMAL_BLOCK",))
    return status, tuple(blocked), tuple(reasons)


def _operator_summary(
    *,
    battery_soc_pct: int | None,
    supercap_soc_pct: int | None,
    bus_state: str,
    peak_readiness: str,
    thermal_status: str,
    reason_codes: tuple[str, ...],
) -> str:
    reasons = ", ".join(reason_codes) if reason_codes else "none"
    return (
        f"SoC_bat={format_soc_bat(battery_soc_pct)}; "
        f"SoC_cap={format_soc_cap(supercap_soc_pct)}; bus={bus_state}; "
        f"peak={peak_readiness}; thermal={thermal_status}; reasons={reasons}"
    )


def _vm_get(vm: Any, name: str, default: Any = None) -> Any:
    if isinstance(vm, dict):
        return vm.get(name, default)
    return getattr(vm, name, default)


def _pct_text(value: Any) -> str:
    soc = _soc_int_or_none(value)
    if soc is None:
        return "unknown"
    return f"{soc}%"


def _soc_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {
        "",
        "none",
        "null",
        "n/a",
        "unknown",
        "-",
    }:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _telemetry_trust_status(reason_codes: tuple[str, ...], freshness: str) -> str:
    """Return source/data trust vocabulary for ORION evidence surfaces."""
    if "POWER_TELEM_MISSING" in reason_codes:
        return "missing"
    if "POWER_TELEM_STALE" in reason_codes or str(freshness or "").lower() == "stale":
        return "stale"
    conflicting = {"BUS_UNSTABLE", "SOURCE_UNAVAILABLE", "LOAD_SHED_ACTIVE"}
    if any(reason in conflicting for reason in reason_codes):
        return "conflicting"
    return "trusted"


def _missing_power_telemetry_vm() -> PowerThermalConsoleViewModel:
    vm = build_power_thermal_console_view_model(
        battery_soc_pct=None,
        supercap_soc_pct=None,
        bus_state="unknown",
        pdu_state="unknown",
        thermal_nodes=_unknown_thermal_nodes(),
    )
    reasons = _stable_unique((*vm.reason_codes, "POWER_TELEM_MISSING"))
    summary = _operator_summary(
        battery_soc_pct=None,
        supercap_soc_pct=None,
        bus_state="unknown",
        peak_readiness=vm.peak_readiness,
        thermal_status=vm.thermal_status,
        reason_codes=reasons,
    )
    return replace(
        vm,
        mode="console-visible power telemetry adapter",
        source="missing_power_telemetry",
        transport="orion telemetry snapshot adapter",
        trust_status="missing",
        reason_codes=reasons,
        evidence_card_id="power-telemetry:missing",
        runtime_conformance="telemetry adapter; full PDU runtime not claimed",
        operator_summary=summary,
        telemetry_freshness="missing",
    )


def _extract_power_block(telemetry: Mapping[str, Any]) -> dict[str, Any]:
    power = telemetry.get("power")
    if isinstance(power, Mapping):
        return dict(power)
    if any(key in telemetry for key in ("soc_pct", "supercap_soc_pct", "bus_v", "loads_w")):
        return dict(telemetry)
    return {}


def _first_number(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in mapping:
            continue
        value = _num_or_none(mapping.get(key))
        if value is not None:
            return value
    return None


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_pairs(value: Any) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Mapping):
        return ()
    pairs: list[tuple[str, float]] = []
    for key, raw in value.items():
        number = _num_or_none(raw)
        if number is not None:
            pairs.append((str(key), number))
    return tuple(pairs)


def _source_generation_w(sources_w: Mapping[str, float], power: Mapping[str, Any]) -> float | None:
    if sources_w:
        return sum(value for key, value in sources_w.items() if key != "supercap_discharge")
    return _num_or_none(power.get("power_in_w"))


def _freshness_from_snapshot(telemetry: Mapping[str, Any]) -> str:
    for key in ("freshness", "power_freshness", "telemetry_freshness"):
        text = str(telemetry.get(key) or "").strip().lower()
        if text:
            return text
    return "fresh"


def _string_items(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _bus_state(power: Mapping[str, Any], bus_v: float | None, bus_a: float | None) -> str:
    faults = set(_string_items(power.get("faults")))
    bus_v_min = _num_or_none(power.get("bus_v_min"))
    max_bus_a = _num_or_none(power.get("max_bus_a"))
    if bus_v is None and bus_a is None:
        return "unknown"
    if any(str(fault).startswith("BUS_") for fault in faults) or bus_v == 0.0:
        return "unstable"
    if bus_v is not None and bus_v_min is not None and bus_v_min > 0 and bus_v < bus_v_min:
        return "unstable"
    if bus_a is not None and max_bus_a is not None and max_bus_a > 0 and bus_a > max_bus_a:
        return "unstable"
    return "nominal"


def _pdu_state(power: Mapping[str, Any], bus_state: str) -> str:
    faults = set(_string_items(power.get("faults")))
    shed_loads = _string_items(power.get("shed_loads"))
    if bus_state == "unstable":
        return "bus_unstable"
    if "PDU_OVERCURRENT" in faults:
        return "overcurrent"
    if bool(power.get("pdu_throttled")):
        return "throttling"
    if bool(power.get("load_shedding")) or shed_loads:
        return "load_shedding"
    if bus_state == "unknown":
        return "unknown"
    return "allowing baseline loads"


def _telemetry_reason_codes(
    power: Mapping[str, Any],
    *,
    freshness: str,
    battery_soc_pct: float | None,
    bus_voltage_v: float | None,
    bus_current_a: float | None,
    source_generation_w: float | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    required = ("soc_pct", "supercap_soc_pct", "bus_v", "bus_a", "loads_w")
    if any(key not in power for key in required):
        reasons.append("POWER_TELEM_MISSING")
    if str(freshness or "").lower() not in {"fresh", "seed"}:
        reasons.append("POWER_TELEM_STALE")
    shed_reasons = set(_string_items(power.get("shed_reasons")))
    soc_low = _num_or_none(power.get("soc_shed_low_pct"))
    if "low_soc" in shed_reasons or (
        battery_soc_pct is not None and soc_low is not None and battery_soc_pct <= soc_low
    ):
        reasons.append("BAT_LOW")
    faults = set(_string_items(power.get("faults")))
    bus_v_min = _num_or_none(power.get("bus_v_min"))
    max_bus_a = _num_or_none(power.get("max_bus_a"))
    if (
        any(str(fault).startswith("BUS_") for fault in faults)
        or bus_voltage_v == 0.0
        or (bus_voltage_v is not None and bus_v_min is not None and bus_v_min > 0 and bus_voltage_v < bus_v_min)
        or (bus_current_a is not None and max_bus_a is not None and max_bus_a > 0 and bus_current_a > max_bus_a)
    ):
        reasons.append("BUS_UNSTABLE")
    if source_generation_w is not None and source_generation_w <= 0.0:
        reasons.append("SOURCE_UNAVAILABLE")
    if bool(power.get("load_shedding")) or _string_items(power.get("shed_loads")):
        reasons.append("LOAD_SHED_ACTIVE")
    battery_temp = str(power.get("battery_temp_state") or "").lower()
    if battery_temp in {"hot", "critical"}:
        reasons.append("BAT_HOT")
    supercap_temp = str(power.get("supercap_temp_state") or "").lower()
    if supercap_temp in {"hot", "critical"}:
        reasons.append("CAP_HOT")
    return tuple(dict.fromkeys(reasons))


def _thermal_nodes_from_snapshot(telemetry: Mapping[str, Any]) -> tuple[ThermalNodeView, ...]:
    thermal = telemetry.get("thermal")
    nodes = thermal.get("nodes") if isinstance(thermal, Mapping) else None
    if not isinstance(nodes, list) or not nodes:
        return _unknown_thermal_nodes()
    out: list[ThermalNodeView] = []
    for raw in nodes:
        if not isinstance(raw, Mapping):
            continue
        node_id = str(raw.get("id") or raw.get("node_id") or "thermal_node").strip()
        temp = _num_or_none(raw.get("temp_c") or raw.get("temperature_c"))
        if raw.get("tripped") is True:
            state = "red"
        elif raw.get("warned") is True:
            state = "orange"
        else:
            state = "green" if temp is not None else "unknown"
        reason_codes = ("THERMAL_BLOCK",) if state in {"orange", "red"} else ()
        blocked = ("peak actions",) if state in {"orange", "red"} else ()
        out.append(
            ThermalNodeView(
                node_id=f"T_{node_id}" if not node_id.startswith("T_") else node_id,
                thermal_class=state,
                temperature_c=temp,
                blocked_commands=blocked,
                reason_codes=reason_codes,
                trust_status="trusted",
            )
        )
    return tuple(out) or _unknown_thermal_nodes()


def _unknown_thermal_nodes() -> tuple[ThermalNodeView, ...]:
    return (
        ThermalNodeView("T_battery", "unknown", None, trust_status="missing"),
        ThermalNodeView("T_supercap", "unknown", None, trust_status="missing"),
        ThermalNodeView("T_pdu", "unknown", None, trust_status="missing"),
        ThermalNodeView("T_core", "unknown", None, trust_status="missing"),
    )


def _watts_text(value: Any) -> str:
    number = _num_or_none(value)
    return "unknown" if number is None else f"{number:.1f}"


def _volts_text(value: Any) -> str:
    number = _num_or_none(value)
    return "unknown" if number is None else f"{number:.2f}"


def _amps_text(value: Any) -> str:
    number = _num_or_none(value)
    return "unknown" if number is None else f"{number:.2f}"


def _loads_text(value: Any) -> str:
    if not value:
        return "unknown"
    pairs: Iterable[tuple[str, float]]
    if isinstance(value, Mapping):
        pairs = _numeric_pairs(value)
    else:
        pairs = value
    rows = []
    for key, raw in pairs:
        number = _num_or_none(raw)
        if number is not None:
            rows.append(f"{key}={number:.1f}")
    return ", ".join(rows) if rows else "unknown"


def _stable_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)
