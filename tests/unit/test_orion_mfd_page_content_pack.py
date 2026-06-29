from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)
from qiki.services.operator_console.orion_v.mfd_page_content import (
    render_left_mfd_page,
    render_right_mfd_page,
)


def _body_vm() -> SimpleNamespace:
    return SimpleNamespace(
        faces=(
            SimpleNamespace(
                face_id="F00",
                role="bayonet",
                occupancy="free",
                module_id=None,
                selected=False,
            ),
            SimpleNamespace(
                face_id="F06",
                role="mission",
                occupancy="occupied",
                module_id="test_sensor_module_001",
                selected=True,
            ),
        ),
        selected_face_id="F06",
        selected_face_role="mission",
        selected_face_occupancy="occupied",
        selected_face_module_id="test_sensor_module_001",
        attached_modules_count=1,
        last_decision="attached",
        evidence_card_type="BODY_MODULE_ATTACH_REGISTERED",
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport_status="validated",
        runtime_ready=False,
        capability_status="inactive",
    )


def _physics_vm() -> SimpleNamespace:
    return SimpleNamespace(
        evidence_card_type="BODY_PHYSICAL_CONSEQUENCE_SEED_PENDING",
        mass_state="pending",
        com_delta_class="unknown / requires mass+geometry",
        inertia_class="unknown / requires inertia model",
        thrust_map_status="TBD",
        torque_map_status="TBD",
    )


def _power_vm(*, battery_soc_pct: int | None = 84, supercap_soc_pct: int | None = 61) -> SimpleNamespace:
    node = SimpleNamespace(
        node_id="T_supercap",
        thermal_class="yellow",
        temperature_c=None,
        blocked_commands=("boost",),
    )
    return SimpleNamespace(
        battery_soc_pct=battery_soc_pct,
        supercap_soc_pct=supercap_soc_pct,
        bus_state="nominal",
        peak_readiness="limited",
        source="local_power_thermal_seed",
        runtime_conformance="not claimed",
        thermal_status="green",
        thermal_nodes=(node,),
        blocked_commands=("boost", "high-power scan"),
    )


def _cards() -> list[SimpleNamespace]:
    def card(subsystem_id: str, title: str, current_status: str) -> SimpleNamespace:
        return SimpleNamespace(
            subsystem_id=subsystem_id,
            title=title,
            current_status=current_status,
            severity="stable",
            summary=f"{title} summary from existing system card",
            operational_effect=f"{title} effect remains read-only",
            next_attention=f"{title} next attention",
        )

    return [
        card("sensors", "Sensors / Radar / Observation", "radar picture live"),
        card("comms", "Comms / Link / Protocol", "link available"),
        card("propulsion", "Propulsion / Motion", "free-flight reference"),
        card("docking", "Docking / Dock Interface", "not in docking contour"),
        card("safety", "Safety / Integrity / Hazard", "integrity stable"),
        card("power", "Power / Charge", "self-powered stable"),
    ]


def test_left_mfd_pages_render_distinct_source_backed_content() -> None:
    body = _body_vm()
    tracks = {
        "trk-1": {
            "track_label": "TGT-1",
            "range_m": 1200,
            "bearing_deg": 42,
            "quality": 0.91,
        }
    }
    objective = {
        "target_designator": "TGT-1",
        "route_role": "observation",
        "status": "active",
        "summary": "observe target",
    }

    radar = render_left_mfd_page(page="radar", body_vm=body, radar_tracks=tracks)
    target = render_left_mfd_page(
        page="target",
        body_vm=body,
        radar_tracks=tracks,
        observation_objective=objective,
    )
    sector = render_left_mfd_page(
        page="sector",
        body_vm=body,
        incidents=({"id": "inc-1", "severity": "WARN", "message": "thermal watch"},),
        safe_mode={"active": False},
    )

    assert "LEFT MFD / РАДАР" in radar
    assert "TGT-1" in radar
    assert "LEFT MFD / ЦЕЛЬ" in target
    assert "observe target" in target
    assert "LEFT MFD / СЕКТОР" in sector
    assert "inc-1" in sector
    assert "read-only projection" in radar


def test_right_mfd_pages_are_content_pages_not_placeholders() -> None:
    body = _body_vm()
    physics = _physics_vm()
    power = _power_vm()
    cards = _cards()

    sensors = render_right_mfd_page(
        page="sensors",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
        radar_tracks={"trk-1": {"track_label": "TGT-1"}},
    )
    propulsion = render_right_mfd_page(
        page="propulsion",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
    )
    docking = render_right_mfd_page(
        page="docking",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
    )
    procedures = render_right_mfd_page(
        page="procedures",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
        safe_mode={"active": True, "reason": "CAP_LOW"},
    )

    for rendered in (sensors, propulsion, docking, procedures):
        assert "Selected page is a read-only systems projection" not in rendered
        assert "No runtime action is executed by MFD page selection" not in rendered
        assert "read-only projection, not source of truth" in rendered

    assert "Sensor Trust / Radar" in sensors
    assert "TGT-1" in sensors
    assert "Thrust Map: TBD" in propulsion
    assert "Torque Map: TBD" in propulsion
    assert "does not activate bridge" in docking
    assert "request → validation" in procedures
    assert "CAP_LOW" in procedures


def test_power_and_thermal_pages_preserve_seed_boundary() -> None:
    body = _body_vm()
    physics = _physics_vm()
    power = _power_vm()
    cards = _cards()

    power_page = render_right_mfd_page(
        page="power",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
    )
    thermal_page = render_right_mfd_page(
        page="thermal",
        cards=cards,
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
    )

    assert "Power / Accumulator" in power_page
    assert "canonical_chain: source -> battery -> bus -> supercap -> peak consumers" in power_page
    assert "SoC_bat: 84%" in power_page
    assert "SoC_cap: 61%" in power_page
    assert "PDU_boundary: target-only; no full PDU runtime in this patch" in power_page
    assert "runtime_conformance: not claimed" in power_page
    assert "T_supercap" in thermal_page
    assert "blocked=boost" in thermal_page
    assert "runtime: not claimed" in thermal_page


def test_nullable_power_values_render_unknown_without_percent_garbage() -> None:
    body = _body_vm()
    physics = _physics_vm()
    power = _power_vm(battery_soc_pct=None, supercap_soc_pct=None)

    power_page = render_right_mfd_page(
        page="power",
        cards=_cards(),
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
    )

    assert "SoC_bat: unknown" in power_page
    assert "SoC_cap: unknown" in power_page
    assert "SoC_bat=unknown" in power_page
    assert "SoC_cap=unknown" in power_page
    assert "None%" not in power_page
    assert "-%" not in power_page


def test_right_mfd_renderer_preserves_inspector_block() -> None:
    body = _body_vm()
    physics = _physics_vm()
    power = _power_vm()
    power_view = SubsystemView(
        id="power",
        title="Power / Charge",
        status=ViewStatus.WARN,
        fields=[
            TelemetryField(
                key="power.soc",
                label="Battery SoC",
                value=42,
                unit="%",
                status=ViewStatus.WARN,
                hint="low reserve",
                freshness="fresh",
                trust_status="trusted",
            )
        ],
        summary="battery margin reduced",
    )
    hardware_model = HardwareViewModel(
        system_status=ViewStatus.WARN,
        subsystems={"power": power_view},
        generated_at=0.0,
    )
    inspector_lines = [
        "ИНСПЕКТОР/INSPECTOR — Power / Charge [ПРЕДУПРЕЖДЕНИЕ]",
        "◆ power.soc [ПРЕДУПРЕЖДЕНИЕ]",
        "Battery SoC",
    ]

    rendered = render_right_mfd_page(
        page="power",
        cards=_cards(),
        body_structure_vm=body,
        body_physics_vm=physics,
        power_thermal_vm=power,
        selected_subsystem="power",
        inspector_lines=inspector_lines,
    )

    assert hardware_model.subsystems["power"].title == "Power / Charge"
    assert "Inspector" in rendered
    assert "ИНСПЕКТОР/INSPECTOR — Power / Charge" in rendered
    assert "Battery SoC" in rendered


def test_systems_screen_wires_inspector_into_right_mfd_renderer() -> None:
    systems_source = Path(
        "src/qiki/services/operator_console/orion_v/screens/systems.py"
    ).read_text()

    assert "inspector_lines=format_subsystem_inspector(selected_view)" in systems_source
    assert "render_right_mfd_page(" in systems_source
