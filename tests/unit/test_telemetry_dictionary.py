import re
from pathlib import Path
from typing import Any

import yaml

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Unit as ProtoUnit
from qiki.services.q_sim_service.core.world_model import WorldModel
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.telemetry import TelemetrySnapshotModel

RCS_PORT_ID = "e03efa3e-5735-5a82-8f5c-9a9d9dfff351"


DICT_PATH = Path("docs/design/operator_console/TELEMETRY_DICTIONARY.yaml")
ORION_PATH = Path("src/qiki/services/operator_console/main_orion.py")


def _load_dictionary() -> dict[str, Any]:
    data = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _collect_dictionary_paths(d: dict[str, Any]) -> set[str]:
    subsystems = d.get("subsystems")
    assert isinstance(subsystems, dict) and subsystems

    paths: set[str] = set()
    for subsystem in subsystems.values():
        if not isinstance(subsystem, dict):
            continue
        fields = subsystem.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            if not isinstance(field, dict):
                continue
            p = field.get("path")
            if isinstance(p, str) and p.strip():
                paths.add(p.strip())
            dims = field.get("dimensions")
            if isinstance(dims, dict):
                dk = dims.get("key")
                if isinstance(dk, str) and dk.strip():
                    paths.add(dk.strip())
            related = field.get("related")
            if isinstance(related, list):
                for rel in related:
                    if isinstance(rel, str) and rel.strip():
                        paths.add(rel.strip())
    return paths


def _canonicalize_orion_source_key(key: str) -> str:
    s = str(key)
    # Convert dimensioned selectors into dictionary wildcard form.
    # Examples:
    # - thermal.nodes[id=core].temp_c -> thermal.nodes[*].temp_c
    # - propulsion.rcs.thrusters[index=3].duty_pct -> propulsion.rcs.thrusters[*].duty_pct
    s = re.sub(r"\[[a-zA-Z_]+=[^\]]+\]", "[*]", s)
    return s


def _extract_orion_provenance_source_keys() -> set[str]:
    text = ORION_PATH.read_text(encoding="utf-8")

    # Only keys that ORION exposes in Inspector provenance for the telemetry-backed
    # tables (Power/Thermal/Sensors/Propulsion). Restrict to those render methods to
    # avoid false positives from unrelated command strings.
    method_names = [
        "_render_power_table",
        "_render_thermal_table",
        "_render_sensors_table",
        "_render_propulsion_table",
    ]

    blocks: list[str] = []
    for name in method_names:
        m = re.search(rf"(^|\n)    def {re.escape(name)}\b", text)
        if m is None:
            continue
        start = m.start(0)
        n = re.search(r"\n    def [a-zA-Z_]", text[m.end(0) :])
        end = len(text) if n is None else (m.end(0) + n.start(0))
        blocks.append(text[start:end])

    merged = "\n".join(blocks)
    rx = re.compile(
        r"[\"'](battery|hardware_profile_hash|(?:sim_state|power|docking|thermal|propulsion|sensor_plane|comms)\.[A-Za-z0-9_.\[\]=\*\{\}]+)[\"']"
    )
    return {m.group(1) for m in rx.finditer(merged)}


def _bidi_label_ok(label: str) -> bool:
    if not isinstance(label, str) or not label.strip():
        return False
    # Project rule: bilingual strings are EN/RU with no spaces around '/'.
    if " /" in label or "/ " in label:
        return False
    return bool(re.match(r"^[^/]+/[^/]+$", label))


def _optional_bidi_ok(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    return _bidi_label_ok(value)


def _build_payload_base() -> dict[str, Any]:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    return TelemetrySnapshotModel.normalize_payload(payload)


def _build_payload_thrusters_active() -> dict[str, Any]:
    # Purpose: guarantee propulsion.rcs.thrusters[*] is present and non-empty.
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
            "propulsion_plane": {
                "enabled": True,
                "thrusters_path": "config/propulsion/thrusters.json",
                "propellant_kg_init": 1.0,
                "isp_s": 60.0,
                "rcs_power_w_at_100pct": 80.0,
                "heat_fraction_to_hull": 0.0,
                "pulse_window_s": 0.25,
                "ztt_torque_tol_nm": 25.0,
            },
            "actuators": [
                {"id": RCS_PORT_ID, "role": "rcs_port", "type": "rcs_thruster"},
            ],
        }
    }

    wm = WorldModel(bot_config=bot_config)
    cmd = ActuatorCommand()
    cmd.actuator_id.value = RCS_PORT_ID
    cmd.command_type = ActuatorCommand.CommandType.SET_VELOCITY
    cmd.float_value = 100.0
    cmd.unit = ProtoUnit.PERCENT
    cmd.timeout_ms = 2000
    wm.update(cmd)
    wm.step(0.25)

    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    qsim._bot_config = bot_config
    qsim.world_model = wm
    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    normalized = TelemetrySnapshotModel.normalize_payload(payload)
    return normalized


def _assert_path_exists(payload: dict[str, Any], path: str) -> None:
    assert isinstance(path, str) and path.strip(), "path must be a non-empty string"
    cur: Any = payload
    parts = [p for p in path.split(".") if p]
    for part in parts:
        if part.endswith("[*]"):
            key = part[:-3]
            assert isinstance(cur, dict) and key in cur, f"missing key: {key} (path={path})"
            cur = cur[key]
            assert isinstance(cur, list), f"expected list at {key} (path={path})"
            assert cur, f"list is empty at {key} (path={path})"
            cur = cur[0]
            continue

        assert isinstance(cur, dict) and part in cur, f"missing key: {part} (path={path})"
        cur = cur[part]


def test_telemetry_dictionary_is_self_consistent_and_matches_real_payloads() -> None:
    d = _load_dictionary()
    assert d.get("schema_version") == 1
    subsystems = d.get("subsystems")
    assert isinstance(subsystems, dict) and subsystems

    payload_base = _build_payload_base()
    payload_thrusters = _build_payload_thrusters_active()

    for subsystem_id, subsystem in subsystems.items():
        assert isinstance(subsystem_id, str) and subsystem_id.strip()
        assert isinstance(subsystem, dict)
        fields = subsystem.get("fields")
        assert isinstance(fields, list) and fields, f"subsystem {subsystem_id} has no fields"

        for field in fields:
            assert isinstance(field, dict)

            label = field.get("label")
            assert isinstance(label, str) and _bidi_label_ok(label), f"invalid bilingual label: {label!r}"

            why_operator = field.get("why_operator")
            if why_operator is not None:
                assert _optional_bidi_ok(why_operator), f"invalid bilingual why_operator: {why_operator!r}"

            actions_hint = field.get("actions_hint")
            if actions_hint is not None:
                assert _optional_bidi_ok(actions_hint), f"invalid bilingual actions_hint: {actions_hint!r}"

            path = field.get("path")
            assert isinstance(path, str) and path.strip(), f"missing path in field: {field}"

            # Validate the path against real telemetry payloads.
            presence = field.get("presence")
            use_thrusters_payload = bool(
                (isinstance(presence, str) and presence.strip().lower() == "state-dependent")
                or ("thrusters[*]" in path)
            )
            payload = payload_thrusters if use_thrusters_payload else payload_base
            _assert_path_exists(payload, path)

            dims = field.get("dimensions")
            if isinstance(dims, dict) and isinstance(dims.get("key"), str):
                dim_key = str(dims.get("key"))
                payload = payload_thrusters if use_thrusters_payload or "thrusters[*]" in dim_key else payload_base
                _assert_path_exists(payload, dim_key)

            related = field.get("related")
            if isinstance(related, list):
                for rel in related:
                    if not isinstance(rel, str):
                        continue
                    payload = payload_thrusters if "thrusters[*]" in rel else payload_base
                    _assert_path_exists(payload, rel)


def test_orion_inspector_provenance_keys_are_covered_by_dictionary() -> None:
    d = _load_dictionary()
    dict_paths = _collect_dictionary_paths(d)

    keys = _extract_orion_provenance_source_keys()
    assert keys, "no provenance keys extracted from ORION"
    assert "battery" not in keys, "ORION must not consume legacy alias key 'battery'; use power.soc_pct"

    missing: list[str] = []
    for key in sorted(keys):
        canon = _canonicalize_orion_source_key(key)
        if canon not in dict_paths:
            missing.append(f"{key} -> {canon}")

    assert not missing, "ORION provenance keys missing in dictionary:\n" + "\n".join(missing)
