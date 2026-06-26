from __future__ import annotations

import logging
import os
import time
from collections import Counter
from math import sqrt
from typing import Any

from .diagnostics import (
    compute_field_coverage,
    compute_missing_keys,
    format_coverage_line,
    format_missing_line,
)
from .key_aliases import SUBSYSTEM_KEYSETS, canonicalize_snapshot
from .thresholds import (
    COMMS_AGE_CRIT_S,
    COMMS_AGE_WARN_S,
    COMMS_LAT_CRIT_MS,
    COMMS_LAT_WARN_MS,
    COMMS_LOSS_CRIT_PCT,
    COMMS_LOSS_WARN_PCT,
    COMPUTE_CPU_CRIT_PCT,
    COMPUTE_CPU_WARN_PCT,
    COMPUTE_HEARTBEAT_CRIT_S,
    COMPUTE_HEARTBEAT_WARN_S,
    COMPUTE_RAM_CRIT_PCT,
    COMPUTE_RAM_WARN_PCT,
    COMPUTE_TEMP_CRIT_C,
    COMPUTE_TEMP_WARN_C,
    DOCK_MAX_ALIGN_CRIT_DEG,
    DOCK_MAX_ALIGN_WARN_DEG,
    DOCK_MAX_SPEED_CRIT_MPS,
    DOCK_MAX_SPEED_WARN_MPS,
    DOCK_MIN_DISTANCE_CAPTURE_M,
    DEFAULT_BATTERY_CAPACITY_WH,
    EPSILON_POWER_W,
    DEFAULT_FUEL_TOTAL_G,
    PROPULSION_BURN_CRIT_MIN,
    PROPULSION_BURN_WARN_MIN,
    PROPULSION_FUEL_CRIT_PCT,
    PROPULSION_FUEL_WARN_PCT,
    PROPULSION_MOTOR_TEMP_CRIT_C,
    PROPULSION_MOTOR_TEMP_WARN_C,
    NAV_CONFIDENCE_CRIT,
    NAV_CONFIDENCE_LOW,
    NAV_CONFIDENCE_WARN,
    HULL_INTEGRITY_WARN_PCT,
    HULL_INTEGRITY_CRIT_PCT,
    HULL_SECTOR_DAMAGE_WARN_PCT,
    HULL_SECTOR_DAMAGE_CRIT_PCT,
    HULL_STRESS_WARN,
    HULL_STRESS_CRIT,
    SHIELDS_LEVEL_WARN_PCT,
    SHIELDS_LEVEL_CRIT_PCT,
    POWER_BUS_CRIT_V,
    POWER_BUS_WARN_V,
    POWER_RUNTIME_CRIT_MIN,
    POWER_RUNTIME_WARN_MIN,
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
    THERMAL_CORE_CRIT_C,
    THERMAL_CORE_WARN_C,
    THERMAL_DELTA_CRIT_C,
    THERMAL_DELTA_WARN_C,
    status_by_max,
    status_by_min,
)
from .types import HardwareViewModel, SubsystemView, TelemetryField, ViewStatus
from .utils import fmt_duration_seconds, merge_status, mk_field, normalize_sensor_status, presence_evidence, safe_float

LOGGER = logging.getLogger(__name__)


class HardwareCollector:
    """Collects raw telemetry snapshot into a stable hardware view model."""

    _SUBSYSTEM_TITLES: dict[str, str] = {
        "power": "Энергия",
        "thermal": "Температура",
        "comms": "Связь",
        "docking": "Стыковка",
        "navigation": "Навигация",
        "compute": "Вычисления",
        "sensors": "Сенсоры",
        "hull": "Корпус",
        "shields": "Щиты",
        "propulsion": "Движение",
    }

    def __init__(self) -> None:
        self._diag_last_log_monotonic = 0.0
        self._missing_key_counts: dict[str, Counter[str]] = {
            subsystem: Counter() for subsystem in SUBSYSTEM_KEYSETS
        }
        self._prev_values: dict[str, float] = {}

    def update(self, snapshot: dict[str, Any], *, now_ts: float | None = None) -> HardwareViewModel:
        now = now_ts if now_ts is not None else time.time()
        snap = canonicalize_snapshot(snapshot)
        subsystems = {
            "power": self.build_power(snap),
            "thermal": self.build_thermal(snap, now_ts=now),
            "comms": self.build_comms(snap, now_ts=now),
            "docking": self.build_docking(snap),
            "navigation": self.build_navigation(snap),
            "compute": self.build_compute(snap, now_ts=now),
            "sensors": self.build_sensors(snap),
            "hull": self.build_hull(snap),
            "shields": self.build_shields(snap),
            "propulsion": self.build_propulsion(snap),
        }
        statuses = [item.status for item in subsystems.values()]
        known = [item for item in statuses if item is not ViewStatus.NO_DATA]
        if not known:
            system_status = ViewStatus.NO_DATA
        else:
            system_status = known[0]
            for status in known[1:]:
                system_status = merge_status(system_status, status)
        model = HardwareViewModel(system_status=system_status, subsystems=subsystems, generated_at=now)
        self._log_diagnostics_if_enabled(model=model, snapshot_canon=snap)
        return model

    def build_power(self, snapshot: dict[str, Any]) -> SubsystemView:
        soc = self._v(snapshot, "power.soc", "power.soc_pct", "eps.soc")
        supercap_soc = self._v(snapshot, "power.supercap_soc_pct", "power.supercap_soc")
        bus_v = self._v(snapshot, "power.bus_v", "power.bus_voltage_v", "eps.bus_v")
        bus_a = self._v(snapshot, "power.bus_a", "power.bus_current_a", "eps.bus_a")
        draw_w = self._v(snapshot, "power.draw_w", "power.power_w", "eps.draw_w")
        available_w = self._v(snapshot, "power.available_w", "eps.available_w")
        capacity_wh = self._v(snapshot, "power.battery_wh", "battery.capacity_wh", "eps.capacity_wh")
        load_shedding = self._bool(snapshot, "power.load_shedding", "power.load_shedding_active")
        shed_reasons = self._extract_reasons(snapshot, "power.shed_reasons")
        limit_mode = self._bool(snapshot, "power.limit_mode", "power.limits_active")
        dock_bridge = self._state_text(self._raw(snapshot, "dock_power_bridge.state", "power.dock_bridge_state"))
        budgeter = self._state_text(self._raw(snapshot, "nbl_power_budgeter.state", "power_budgeter.state"))
        pdu = self._state_text(self._raw(snapshot, "pdu.state", "pdu.health"))

        derived_draw_w = False
        if draw_w is None and bus_v is not None and bus_a is not None:
            draw_w = bus_v * bus_a
            derived_draw_w = True

        runtime_min, runtime_hint = self._runtime_minutes(soc=soc, power_w=draw_w, capacity_wh=capacity_wh)

        soc_status = status_by_min(soc, POWER_SOC_WARN_PCT, POWER_SOC_CRIT_PCT)
        supercap_soc_status = status_by_min(supercap_soc, POWER_SOC_WARN_PCT, POWER_SOC_CRIT_PCT)
        # Evidence metadata (ADR-0014 / IF-POWER-TELEM): missing => POWER_TELEM_MISSING,
        # present-but-old => POWER_TELEM_STALE. telemetry_age from snapshot ts vs wall clock;
        # COMMS_AGE_CRIT_S keeps power staleness consistent with _data_freshness_state
        # (console-side threshold, no power-specific canon SLA).
        ts_ms = snapshot.get("ts_unix_ms")
        telemetry_age_s = (time.time() - ts_ms / 1000.0) if isinstance(ts_ms, (int, float)) else None
        battery_ev = presence_evidence(soc, telemetry_age_s, COMMS_AGE_CRIT_S)
        supercap_ev = presence_evidence(supercap_soc, telemetry_age_s, COMMS_AGE_CRIT_S)
        bus_status = status_by_min(bus_v, POWER_BUS_WARN_V, POWER_BUS_CRIT_V)
        runtime_status = status_by_min(runtime_min, POWER_RUNTIME_WARN_MIN, POWER_RUNTIME_CRIT_MIN)
        load_status = self._load_shedding_status(load_shedding, soc_status)
        shed_reasons_value, shed_reasons_status = self._shed_reasons_value(
            load_shedding=load_shedding,
            load_status=load_status,
            reasons=shed_reasons,
        )
        limit_status = self._binary_status(limit_mode)

        fields = [
            mk_field(
                "power.soc",
                "Заряд батареи",
                soc,
                "%",
                soc_status,
                "battery, раздельно с supercap (ADR-0003); предупр < 20%, критично < 15%",
                i18n_key="soc",
                **battery_ev,
            ),
            mk_field(
                "power.supercap_soc",
                "Заряд суперкапа",
                supercap_soc,
                "%",
                supercap_soc_status,
                "supercap, раздельно с battery (ADR-0003)",
                **supercap_ev,
            ),
            mk_field(
                "power.bus_v",
                "Напряжение шины",
                bus_v,
                "В",
                bus_status,
                "норма около 24В",
                i18n_key="bus_voltage",
            ),
            mk_field(
                "power.bus_a",
                "Ток шины",
                bus_a,
                "А",
                ViewStatus.OK if bus_a is not None else ViewStatus.NO_DATA,
                i18n_key="bus_current",
            ),
            mk_field(
                "power.draw_w",
                "Потребление",
                draw_w,
                "Вт",
                ViewStatus.OK if draw_w is not None else ViewStatus.NO_DATA,
                "расчет по U*I" if derived_draw_w else "прямое значение",
            ),
            mk_field(
                "power.runtime_min",
                "Осталось до разрядки",
                runtime_min,
                "мин",
                runtime_status,
                runtime_hint,
            ),
            mk_field(
                "power.limit_mode",
                "Режим ограничения",
                self._on_off_text(limit_mode),
                status=limit_status,
                i18n_key="limit_mode",
            ),
            mk_field(
                "power.load_shedding",
                "Аварийное отключение нагрузки",
                self._on_off_text(load_shedding),
                status=load_status,
                i18n_key="load_shedding",
            ),
            mk_field(
                "power.shed_reasons",
                "Причины сброса",
                shed_reasons_value,
                status=shed_reasons_status,
                i18n_key="shed_reasons",
            ),
            mk_field(
                "power.dock_bridge_state", "Dock power bridge", dock_bridge, status=self._string_status(dock_bridge)
            ),
            mk_field("power_budgeter.state", "Power budgeter", budgeter, status=self._string_status(budgeter)),
            mk_field("pdu.state", "PDU", pdu, status=self._string_status(pdu)),
            mk_field(
                "power.available_w",
                "Доступная мощность",
                available_w,
                "Вт",
                status=ViewStatus.OK if available_w is not None else ViewStatus.NO_DATA,
            ),
        ]

        summary = self._power_summary(soc=soc, bus_v=bus_v, runtime_min=runtime_min)
        return self._subsystem("power", fields, "энергетический контур", summary=summary)

    def build_thermal(self, snapshot: dict[str, Any], *, now_ts: float | None = None) -> SubsystemView:
        now = now_ts if now_ts is not None else time.time()
        thermal_nodes = self._thermal_nodes(snapshot)
        core_node = self._thermal_node(thermal_nodes, "core")
        core = self._v(snapshot, "thermal.core_c")
        if core is None:
            core = self._node_num(core_node, "temp_c")
        radiator = self._v(snapshot, "thermal.radiator_c")
        ambient = self._v(snapshot, "temp_external_c")
        radiator_display = radiator if radiator is not None else ambient
        delta = round(core - radiator, 1) if core is not None and radiator is not None else None
        trend_text = self._thermal_trend(core)
        warn_nodes = self._flagged_nodes(thermal_nodes, "warned")
        trip_nodes = self._flagged_nodes(thermal_nodes, "tripped")
        core_warned = self._node_bool(core_node, "warned")
        core_tripped = self._node_bool(core_node, "tripped")
        core_warn_c = self._node_num(core_node, "warn_c")
        core_trip_c = self._node_num(core_node, "trip_c")
        core_hys_c = self._node_num(core_node, "hys_c")
        core_state, core_state_status = self._thermal_core_state(
            core=core,
            warned=core_warned,
            tripped=core_tripped,
        )
        age = self._age_seconds(
            snapshot=snapshot,
            now_ts=now,
            last_seen_keys=("thermal.last_seen_ts",),
            age_keys=("thermal.age_s",),
        )

        core_status = status_by_max(core, THERMAL_CORE_WARN_C, THERMAL_CORE_CRIT_C)
        if core_tripped is True:
            core_status = ViewStatus.CRIT
        elif core_warned is True:
            core_status = merge_status(core_status, ViewStatus.WARN)
        delta_status = status_by_max(delta, THERMAL_DELTA_WARN_C, THERMAL_DELTA_CRIT_C)
        trend_status = ViewStatus.OK if trend_text != "Нет данных" else ViewStatus.NO_DATA
        warn_nodes_text, warn_nodes_status = self._thermal_nodes_text(
            nodes=thermal_nodes,
            flagged=warn_nodes,
            flagged_status=ViewStatus.WARN,
        )
        trip_nodes_text, trip_nodes_status = self._thermal_nodes_text(
            nodes=thermal_nodes,
            flagged=trip_nodes,
            flagged_status=ViewStatus.CRIT,
        )
        age_status = ViewStatus.OK if age is not None else ViewStatus.NO_DATA

        fields = [
            mk_field(
                "thermal.core_c",
                "Температура ядра",
                core,
                "°C",
                core_status,
                f"предупр >= {THERMAL_CORE_WARN_C:.0f}°C, критично >= {THERMAL_CORE_CRIT_C:.0f}°C",
                i18n_key="core_temp",
            ),
            mk_field(
                "thermal.radiator_c",
                "Температура радиатора/среды",
                radiator_display,
                "°C",
                ViewStatus.OK if radiator_display is not None else ViewStatus.NO_DATA,
                i18n_key="radiator_temp",
            ),
            mk_field(
                "thermal.delta_c",
                "ΔT",
                delta,
                "°C",
                delta_status,
                f"предупр >= {THERMAL_DELTA_WARN_C:.0f}°C, критично >= {THERMAL_DELTA_CRIT_C:.0f}°C",
            ),
            mk_field(
                "thermal.trend",
                "Тренд",
                trend_text,
                "",
                trend_status,
                "по правилу current-prev",
            ),
            mk_field(
                "thermal.core_state",
                "Состояние core",
                core_state,
                "",
                core_state_status,
            ),
            mk_field(
                "thermal.warn_nodes",
                "Узлы WARN",
                warn_nodes_text,
                "",
                warn_nodes_status,
            ),
            mk_field(
                "thermal.trip_nodes",
                "Узлы TRIP",
                trip_nodes_text,
                "",
                trip_nodes_status,
            ),
            mk_field(
                "thermal.core_warn_c",
                "Порог warn core",
                core_warn_c,
                "°C",
                ViewStatus.OK if core_warn_c is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "thermal.core_trip_c",
                "Порог trip core",
                core_trip_c,
                "°C",
                ViewStatus.OK if core_trip_c is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "thermal.core_hys_c",
                "Гистерезис core",
                core_hys_c,
                "°C",
                ViewStatus.OK if core_hys_c is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "thermal.age_s",
                "Возраст данных",
                age,
                "с",
                age_status,
            ),
        ]
        summary = self._thermal_summary(
            core=core,
            delta=delta,
            trend_text=trend_text,
            core_state=core_state,
            trip_nodes=trip_nodes,
            warn_nodes=warn_nodes,
        )
        return self._subsystem("thermal", fields, "температурный контур", summary=summary)

    def build_comms(self, snapshot: dict[str, Any], *, now_ts: float | None = None) -> SubsystemView:
        now = now_ts if now_ts is not None else time.time()
        link_state_raw = self._raw(snapshot, "comms.link_state")
        link_state_text, link_state_status = self._comms_link_state(link_state_raw)

        latency = self._v(snapshot, "comms.latency_ms")
        loss = self._v(snapshot, "comms.packet_loss_pct")
        rssi = self._v(snapshot, "comms.rssi_dbm")
        snr = self._v(snapshot, "comms.snr_db")
        tx_power = self._v(snapshot, "comms.tx_power_w")
        data_rate = self._v(snapshot, "comms.data_rate_kbps")
        antenna_status_text = self._state_text(self._raw(snapshot, "comms.antenna_status"))
        age = self._comms_age_seconds(snapshot=snapshot, now_ts=now)

        plane_enabled = self._bool(snapshot, "comms.plane_enabled")
        plane_profile = self._state_text(self._raw(snapshot, "comms.plane_profile"))

        latency_status = status_by_max(latency, COMMS_LAT_WARN_MS, COMMS_LAT_CRIT_MS)
        loss_status = status_by_max(loss, COMMS_LOSS_WARN_PCT, COMMS_LOSS_CRIT_PCT)
        age_status = status_by_max(age, COMMS_AGE_WARN_S, COMMS_AGE_CRIT_S)
        quality_text, quality_status = self._comms_quality(
            latency_status=latency_status,
            loss_status=loss_status,
            age_status=age_status,
            has_any_metrics=any(value is not None for value in (latency, loss, age)),
        )

        fields = [
            mk_field(
                "comms.link_state",
                "Состояние канала",
                link_state_text,
                "",
                link_state_status,
            ),
            mk_field(
                "comms.latency_ms",
                "Задержка",
                latency,
                "мс",
                latency_status,
                f"предупр >= {COMMS_LAT_WARN_MS:.0f} мс, критично >= {COMMS_LAT_CRIT_MS:.0f} мс",
                i18n_key="latency",
            ),
            mk_field(
                "comms.packet_loss_pct",
                "Потери",
                loss,
                "%",
                loss_status,
                f"предупр >= {COMMS_LOSS_WARN_PCT:.1f}%, критично >= {COMMS_LOSS_CRIT_PCT:.1f}%",
                i18n_key="packet_loss",
            ),
            mk_field(
                "comms.rssi_dbm",
                "Уровень сигнала",
                rssi,
                "dBm",
                ViewStatus.OK if rssi is not None else ViewStatus.NO_DATA,
                i18n_key="rssi",
            ),
            mk_field(
                "comms.snr_db",
                "SNR",
                snr,
                "dB",
                ViewStatus.OK if snr is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "comms.tx_power_w",
                "Мощность TX",
                tx_power,
                "Вт",
                ViewStatus.OK if tx_power is not None else ViewStatus.NO_DATA,
                i18n_key="tx_power",
            ),
            mk_field(
                "comms.data_rate_kbps",
                "Скорость передачи",
                data_rate,
                "kbps",
                ViewStatus.OK if data_rate is not None else ViewStatus.NO_DATA,
                i18n_key="data_rate",
            ),
            mk_field(
                "comms.antenna_status",
                "Статус антенны",
                antenna_status_text,
                "",
                self._string_status(antenna_status_text),
                i18n_key="antenna_status",
            ),
            mk_field(
                "comms.age_s",
                "Возраст данных",
                age,
                "с",
                age_status,
                f"предупр >= {COMMS_AGE_WARN_S:.0f} c, критично >= {COMMS_AGE_CRIT_S:.0f} c",
                i18n_key="last_rx",
            ),
            mk_field(
                "comms.quality",
                "Качество канала",
                quality_text,
                "",
                quality_status,
            ),
            mk_field(
                "comms.plane_enabled",
                "Comms plane",
                self._on_off_text(plane_enabled),
                "",
                ViewStatus.OK if plane_enabled is True else ViewStatus.WARN if plane_enabled is False else ViewStatus.NO_DATA,
            ),
            mk_field(
                "comms.plane_profile",
                "Профиль связи",
                plane_profile,
                "",
                ViewStatus.OK if plane_profile is not None else ViewStatus.NO_DATA,
            ),
        ]

        summary = self._comms_summary(
            link_state_text=link_state_text,
            latency_ms=latency,
            loss_pct=loss,
            age_s=age,
            quality_text=quality_text,
            has_any_key=any(value is not None for value in (link_state_raw, latency, loss, age)),
        )
        return self._subsystem("comms", fields, "канал и стабильность", summary=summary)

    def build_docking(self, snapshot: dict[str, Any]) -> SubsystemView:
        state_raw = self._raw(snapshot, "docking.state", "docking.phase", "dock.state")
        state = self._state_text(state_raw)
        state_norm = str(state_raw).strip().lower() if state_raw is not None else ""
        target = self._state_text(self._raw(snapshot, "docking.target", "docking.target_id", "dock.target"))
        distance = self._v(snapshot, "docking.distance_m", "dock.distance_m", "sensor_docking.distance_m")
        approach = self._v(snapshot, "docking.approach_mps", "docking.relative_speed_mps", "dock.rel_speed_mps")
        alignment = self._v(
            snapshot,
            "docking.alignment_error_deg",
            "dock.align_err_deg",
            "sensor_docking.alignment_error_deg",
        )
        lock_state = self._state_text(self._raw(snapshot, "docking.lock_state", "docking.latch_state"))
        locked_bool = self._bool(snapshot, "dock.locked")
        capture = self._bool(snapshot, "docking.capture")

        sensor_status_norm, sensor_status_text, _ = self._sensor_status(snapshot, ("sensor_docking",))
        sensor_status = self._sensor_status_to_view_status(sensor_status_norm)

        align_status = status_by_max(alignment, DOCK_MAX_ALIGN_WARN_DEG, DOCK_MAX_ALIGN_CRIT_DEG)
        speed_status = status_by_max(approach, DOCK_MAX_SPEED_WARN_MPS, DOCK_MAX_SPEED_CRIT_MPS)

        eta_sec, eta_hint = self._docking_eta(distance_m=distance, approach_mps=approach)
        eta_display = fmt_duration_seconds(eta_sec)

        lock_status = self._docking_lock_status(lock_state=lock_state, locked_bool=locked_bool, capture=capture)
        if lock_status is ViewStatus.OK:
            align_status = ViewStatus.OK if alignment is not None else align_status
            speed_status = ViewStatus.OK if approach is not None else speed_status

        state_status = ViewStatus.OK if state is not None else ViewStatus.NO_DATA
        active_state = state_norm in {"approach", "align", "capture"}
        if active_state and sensor_status_norm == "OFFLINE":
            state_status = merge_status(state_status, ViewStatus.WARN)

        process_missing = active_state and any(value is None for value in (distance, approach, alignment))
        if process_missing:
            state_status = merge_status(state_status, ViewStatus.WARN)

        fields = [
            mk_field("docking.state", "Состояние стыковки", state, status=state_status),
            mk_field(
                "docking.target", "Цель", target, status=ViewStatus.OK if target is not None else ViewStatus.NO_DATA
            ),
            mk_field(
                "docking.distance_m",
                "Дистанция до цели",
                distance,
                "м",
                status=ViewStatus.OK if distance is not None else ViewStatus.NO_DATA,
                hint=f"зона захвата < {DOCK_MIN_DISTANCE_CAPTURE_M:.1f} м",
            ),
            mk_field(
                "docking.approach_mps",
                "Скорость сближения",
                approach,
                "м/с",
                status=speed_status,
                hint=f"предупр > {DOCK_MAX_SPEED_WARN_MPS:.2f}, критично > {DOCK_MAX_SPEED_CRIT_MPS:.2f}",
            ),
            mk_field(
                "docking.alignment_error_deg",
                "Ошибка выравнивания",
                alignment,
                "°",
                status=align_status,
                hint=f"предупр > {DOCK_MAX_ALIGN_WARN_DEG:.0f}°, критично > {DOCK_MAX_ALIGN_CRIT_DEG:.0f}°",
                i18n_key="alignment_error",
            ),
            mk_field(
                "docking.eta_contact",
                "До контакта",
                eta_display if eta_sec is not None else None,
                "",
                status=ViewStatus.OK if eta_sec is not None else ViewStatus.NO_DATA,
                hint=eta_hint,
            ),
            mk_field(
                "docking.capture",
                "Захват",
                self._on_off_text(capture),
                status=self._binary_status(capture),
            ),
            mk_field(
                "docking.lock",
                "Замки",
                self._lock_display(lock_state=lock_state, locked_bool=locked_bool),
                status=lock_status,
            ),
            mk_field(
                "sensor_docking.status",
                "Датчик стыковки",
                sensor_status_text,
                status=sensor_status,
            ),
        ]

        summary = self._docking_summary(
            state=state,
            distance=distance,
            approach=approach,
            alignment=alignment,
            lock_state=lock_state,
            locked_bool=locked_bool,
        )
        return self._subsystem("docking", fields, "процесс стыковки", summary=summary)

    def build_navigation(self, snapshot: dict[str, Any]) -> SubsystemView:
        pos_x = self._v(snapshot, "navigation.pos_x", "navigation.x", "nav.x")
        pos_y = self._v(snapshot, "navigation.pos_y", "navigation.y", "nav.y")
        pos_z = self._v(snapshot, "navigation.pos_z", "navigation.z", "nav.z")
        position_raw = self._raw(snapshot, "navigation.position")
        vector_position = self._parse_xyz_vector(position_raw)
        if vector_position is not None:
            if pos_x is None:
                pos_x = vector_position[0]
            if pos_y is None:
                pos_y = vector_position[1]
            if pos_z is None:
                pos_z = vector_position[2]

        vel_x = self._v(snapshot, "navigation.vel_x", "nav.vx")
        vel_y = self._v(snapshot, "navigation.vel_y", "nav.vy")
        vel_z = self._v(snapshot, "navigation.vel_z", "nav.vz")
        speed = self._v(snapshot, "navigation.speed_mps", "nav.speed_mps", "velocity")
        derived_speed = False
        if speed is None and vel_x is not None and vel_y is not None and vel_z is not None:
            speed = round(sqrt((vel_x**2) + (vel_y**2) + (vel_z**2)), 3)
            derived_speed = True

        heading = self._v(snapshot, "navigation.heading_deg", "nav.heading_deg", "heading")
        pitch = self._v(snapshot, "navigation.pitch_deg", "nav.pitch_deg")
        yaw = self._v(snapshot, "navigation.yaw_deg", "nav.yaw_deg")
        roll = self._v(snapshot, "navigation.roll_deg", "nav.roll_deg")
        p_rate = self._v(snapshot, "navigation.p_rate_dps", "nav.p_rate_dps")
        y_rate = self._v(snapshot, "navigation.y_rate_dps", "nav.y_rate_dps")
        r_rate = self._v(snapshot, "navigation.r_rate_dps", "nav.r_rate_dps")

        mode_raw = self._raw(snapshot, "navigation.mode", "nav.mode")
        mode = self._state_text(mode_raw)
        star_status_raw = self._raw(snapshot, "sensor_star_tracker.status", "navigation.star_tracker_status")
        star_status = self._state_text(star_status_raw)
        confidence = self._v(snapshot, "navigation.confidence", "nav.confidence")
        confidence_status = self._navigation_confidence_status(confidence)
        nav_quality = self._navigation_quality(confidence=confidence, star_status_raw=star_status_raw)
        nav_quality_status = (
            confidence_status
            if confidence is not None
            else (ViewStatus.WARN if nav_quality == "Низкое" else ViewStatus.NO_DATA)
        )

        mode_status = ViewStatus.OK if mode is not None else ViewStatus.NO_DATA
        if self._is_imu_only_and_star_offline(mode_raw=mode_raw, star_status_raw=star_status_raw):
            mode_status = ViewStatus.WARN

        fields = [
            mk_field(
                "navigation.pos_x",
                "Позиция X",
                pos_x,
                "ед.",
                ViewStatus.OK if pos_x is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.pos_y",
                "Позиция Y",
                pos_y,
                "ед.",
                ViewStatus.OK if pos_y is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.pos_z",
                "Позиция Z",
                pos_z,
                "ед.",
                ViewStatus.OK if pos_z is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.speed_mps",
                "Скорость",
                speed,
                "м/с",
                ViewStatus.OK if speed is not None else ViewStatus.NO_DATA,
                "расчет по Vx/Vy/Vz" if derived_speed else "прямое значение",
                i18n_key="speed",
            ),
            mk_field(
                "navigation.vel_x", "Vx", vel_x, "м/с", ViewStatus.OK if vel_x is not None else ViewStatus.NO_DATA
            ),
            mk_field(
                "navigation.vel_y", "Vy", vel_y, "м/с", ViewStatus.OK if vel_y is not None else ViewStatus.NO_DATA
            ),
            mk_field(
                "navigation.vel_z", "Vz", vel_z, "м/с", ViewStatus.OK if vel_z is not None else ViewStatus.NO_DATA
            ),
            mk_field(
                "navigation.heading_deg",
                "Курс",
                heading,
                "°",
                ViewStatus.OK if heading is not None else ViewStatus.NO_DATA,
                i18n_key="heading",
            ),
            mk_field(
                "navigation.pitch_deg", "Pitch", pitch, "°", ViewStatus.OK if pitch is not None else ViewStatus.NO_DATA
            ),
            mk_field("navigation.yaw_deg", "Yaw", yaw, "°", ViewStatus.OK if yaw is not None else ViewStatus.NO_DATA),
            mk_field(
                "navigation.roll_deg", "Roll", roll, "°", ViewStatus.OK if roll is not None else ViewStatus.NO_DATA
            ),
            mk_field(
                "navigation.p_rate_dps",
                "Угловая скорость P",
                p_rate,
                "°/с",
                ViewStatus.OK if p_rate is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.y_rate_dps",
                "Угловая скорость Y",
                y_rate,
                "°/с",
                ViewStatus.OK if y_rate is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.r_rate_dps",
                "Угловая скорость R",
                r_rate,
                "°/с",
                ViewStatus.OK if r_rate is not None else ViewStatus.NO_DATA,
            ),
            mk_field("navigation.mode", "Режим навигации", mode, status=mode_status),
            mk_field(
                "navigation.star_tracker_status",
                "Star tracker",
                star_status,
                status=ViewStatus.OK if star_status is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "navigation.confidence",
                "Доверие",
                confidence,
                "",
                confidence_status,
                "низкое < 0.5, критично < 0.2",
            ),
            mk_field(
                "navigation.quality",
                "Качество навигации",
                nav_quality,
                "",
                nav_quality_status,
            ),
        ]

        summary = self._navigation_summary(speed=speed, heading=heading, pitch=pitch, yaw=yaw, roll=roll)
        return self._subsystem("navigation", fields, "движение и курс", summary=summary)

    def build_compute(self, snapshot: dict[str, Any], *, now_ts: float | None = None) -> SubsystemView:
        now = now_ts if now_ts is not None else time.time()
        heartbeat_age = self._age_seconds(
            snapshot=snapshot,
            now_ts=now,
            last_seen_keys=("compute.last_seen_ts",),
            age_keys=("compute.heartbeat_age_s",),
        )
        cpu = self._v(snapshot, "compute.cpu_pct")
        ram = self._v(snapshot, "compute.ram_pct")
        temp = self._v(snapshot, "compute.temp_c")
        protocol_errors = self._v(snapshot, "compute.protocol_errors")

        heartbeat_status = status_by_max(
            heartbeat_age,
            COMPUTE_HEARTBEAT_WARN_S,
            COMPUTE_HEARTBEAT_CRIT_S,
        )
        cpu_status = status_by_max(cpu, COMPUTE_CPU_WARN_PCT, COMPUTE_CPU_CRIT_PCT)
        ram_status = status_by_max(ram, COMPUTE_RAM_WARN_PCT, COMPUTE_RAM_CRIT_PCT)
        temp_status = status_by_max(temp, COMPUTE_TEMP_WARN_C, COMPUTE_TEMP_CRIT_C)
        proto_status = status_by_max(protocol_errors, 1.0, 5.0)

        fields = [
            mk_field(
                "compute.heartbeat_age_s",
                "Heartbeat возраст",
                heartbeat_age,
                "с",
                heartbeat_status,
                (
                    f"предупр >= {COMPUTE_HEARTBEAT_WARN_S:.0f}с, "
                    f"критично >= {COMPUTE_HEARTBEAT_CRIT_S:.0f}с"
                ),
            ),
            mk_field(
                "compute.cpu_pct",
                "CPU",
                cpu,
                "%",
                cpu_status,
                f"предупр >= {COMPUTE_CPU_WARN_PCT:.0f}%, критично >= {COMPUTE_CPU_CRIT_PCT:.0f}%",
                i18n_key="cpu_usage",
            ),
            mk_field(
                "compute.ram_pct",
                "RAM",
                ram,
                "%",
                ram_status,
                f"предупр >= {COMPUTE_RAM_WARN_PCT:.0f}%, критично >= {COMPUTE_RAM_CRIT_PCT:.0f}%",
                i18n_key="memory_usage",
            ),
            mk_field(
                "compute.temp_c",
                "Температура",
                temp,
                "°C",
                temp_status,
                f"предупр >= {COMPUTE_TEMP_WARN_C:.0f}°C, критично >= {COMPUTE_TEMP_CRIT_C:.0f}°C",
            ),
            mk_field(
                "compute.protocol_errors",
                "Ошибки протоколов",
                protocol_errors,
                "",
                proto_status,
            ),
        ]

        subsystem = self._subsystem("compute", fields, "нагрузка вычислителя", summary=self._compute_summary(
            heartbeat_age=heartbeat_age,
            cpu=cpu,
            heartbeat_status=heartbeat_status,
        ))
        if heartbeat_status is not ViewStatus.NO_DATA:
            subsystem.status = merge_status(subsystem.status, heartbeat_status)
        return subsystem

    def build_sensors(self, snapshot: dict[str, Any]) -> SubsystemView:
        registry: list[dict[str, Any]] = [
            {
                "id": "radar_360",
                "title": "Радар 360",
                "critical": True,
                "primary_label": "Ближайшая цель",
                "primary_keys": ("radar_360.closest_m",),
                "primary_unit": "м",
                "fallback_keys": ("radar_360.targets",),
            },
            {
                "id": "lidar_front",
                "title": "Лидар фронт",
                "critical": True,
                "primary_label": "Ближайшее препятствие",
                "primary_keys": ("lidar_front.closest_m",),
                "primary_unit": "м",
            },
            {
                "id": "lidar",
                "title": "Лидар",
                "critical": False,
                "primary_label": "Ближайшее препятствие",
                "primary_keys": ("lidar.closest_m",),
                "primary_unit": "м",
                "fallback_keys": ("lidar.points",),
            },
            {
                "id": "imu_main",
                "title": "IMU",
                "critical": True,
                "status_aliases": ("imu_main", "sensor_imu", "imu"),
                "primary_label": "Ускорение",
                "primary_keys": ("imu_main.accel_mps2", "sensor_imu.accel_mps2", "sensor_plane.imu.roll_rate_rps"),
                "primary_unit": "м/с²",
                "fallback_keys": ("imu_main.gyro_dps", "sensor_imu.gyro_dps", "sensor_plane.imu.pitch_rate_rps"),
            },
            {
                "id": "sensor_thermal",
                "title": "Тепловой сенсор",
                "critical": False,
                "primary_label": "Температура",
                "primary_keys": ("sensor_thermal.temp_c",),
                "primary_unit": "°C",
            },
            {
                "id": "sensor_radiation",
                "title": "Радиационный сенсор",
                "critical": True,
                "status_aliases": ("sensor_radiation", "radiation"),
                "primary_label": "Радиация",
                "primary_keys": (
                    "sensor_radiation.level",
                    "radiation.uSv_h",
                    "sensor_plane.radiation.background_usvh",
                ),
                "primary_unit": "µSv/h",
            },
            {
                "id": "sensor_proximity",
                "title": "Сенсор сближения",
                "critical": False,
                "status_aliases": ("sensor_proximity", "proximity"),
                "primary_label": "Ближайший объект",
                "primary_keys": ("sensor_proximity.closest_m", "sensor_plane.proximity.min_range_m"),
                "primary_unit": "м",
            },
            {
                "id": "sensor_solar",
                "title": "Солнечный сенсор",
                "critical": False,
                "status_aliases": ("sensor_solar", "solar"),
                "primary_label": "Генерация",
                "primary_keys": (
                    "sensor_solar.watts",
                    "sensor_solar.irradiance",
                    "sensor_plane.solar.illumination_pct",
                ),
                "primary_unit": "Вт",
            },
            {
                "id": "sensor_star_tracker",
                "title": "Star tracker",
                "critical": True,
                "status_aliases": ("sensor_star_tracker", "star_tracker"),
                "primary_label": "Звезд в треке",
                "primary_keys": ("sensor_star_tracker.stars_tracked",),
                "primary_unit": "",
                "fallback_keys": ("sensor_star_tracker.locked", "sensor_plane.star_tracker.locked"),
                "extra_fields": (
                    {
                        "suffix": "attitude_err",
                        "label": "Ошибка ориентации",
                        "keys": ("sensor_plane.star_tracker.attitude_err_deg",),
                        "unit": "°",
                    },
                ),
            },
            {
                "id": "spectrometer",
                "title": "Спектрометр",
                "critical": False,
                "primary_label": "Последний пик",
                "primary_keys": ("spectrometer.last_peak",),
                "primary_unit": "",
                "fallback_keys": ("spectrometer.active",),
            },
            {
                "id": "magnetometer",
                "title": "Магнитометр",
                "critical": False,
                "primary_label": "Магнитное поле",
                "primary_keys": ("magnetometer.uT", "sensor_plane.magnetometer.field_ut"),
                "primary_unit": "µT",
                "fallback_keys": ("magnetometer.vector",),
            },
        ]

        fields: list[TelemetryField] = []
        online = 0
        degraded = 0
        offline = 0
        critical_offline = 0
        any_data = False

        for item in registry:
            sensor_id = item["id"]
            status_aliases = item.get("status_aliases", (sensor_id,))
            status_norm, status_text, status_state = self._sensor_status(snapshot, status_aliases)
            intentionally_disabled = status_norm == "OFFLINE" and status_state == "enabled"
            if status_norm == "ONLINE":
                online += 1
            elif status_norm == "DEGRADED":
                degraded += 1
            elif status_norm == "OFFLINE":
                offline += 1
                if item["critical"] and not intentionally_disabled:
                    critical_offline += 1

            status_view = (
                ViewStatus.OK if intentionally_disabled else self._sensor_status_to_view_status(status_norm)
            )
            fields.append(
                mk_field(
                    f"sensors.{sensor_id}.status",
                    f"{item['title']}: статус",
                    status_text,
                    status=status_view,
                )
            )
            if status_view is not ViewStatus.NO_DATA:
                any_data = True

            primary_value = self._raw(snapshot, *item["primary_keys"])
            primary_label = item["primary_label"]
            primary_unit = item.get("primary_unit", "")
            if primary_value is None:
                fallback_keys = item.get("fallback_keys", ())
                primary_value = self._raw(snapshot, *fallback_keys) if fallback_keys else None
            fields.append(
                mk_field(
                    f"sensors.{sensor_id}.value",
                    f"{item['title']}: {primary_label}",
                    primary_value,
                    primary_unit,
                    status=ViewStatus.OK if primary_value is not None else ViewStatus.NO_DATA,
                )
            )
            if primary_value is not None:
                any_data = True

            confidence = self._v(
                snapshot,
                f"sensor.{sensor_id}.confidence",
                f"{sensor_id}.confidence",
                f"sensor.{sensor_id}.quality",
            )
            confidence_status = self._sensor_confidence_status(confidence)
            fields.append(
                mk_field(
                    f"sensors.{sensor_id}.confidence",
                    f"{item['title']}: доверие",
                    confidence,
                    "",
                    confidence_status,
                    "warn < 0.5, crit < 0.2",
                )
            )
            if confidence is not None:
                any_data = True

            age_s = self._v(snapshot, f"{sensor_id}.age_s")
            if age_s is None:
                ts = self._v(snapshot, f"sensor.{sensor_id}.ts", f"sensor.{sensor_id}.last_update_ts")
                if ts is not None:
                    age_s = max(round(time.time() - ts, 1), 0.0)
            fields.append(
                mk_field(
                    f"sensors.{sensor_id}.age_s",
                    f"{item['title']}: возраст данных",
                    age_s,
                    "с",
                    status=ViewStatus.OK if age_s is not None else ViewStatus.NO_DATA,
                )
            )
            if age_s is not None:
                any_data = True

            # Additive per-sensor extra evidence fields (e.g. star tracker attitude error).
            # Surfaced only from real keys; absent source degrades to NO_DATA, never fabricated.
            for extra in item.get("extra_fields", ()):
                extra_value = self._raw(snapshot, *extra["keys"])
                fields.append(
                    mk_field(
                        f"sensors.{sensor_id}.{extra['suffix']}",
                        f"{item['title']}: {extra['label']}",
                        extra_value,
                        extra.get("unit", ""),
                        status=ViewStatus.OK if extra_value is not None else ViewStatus.NO_DATA,
                    )
                )
                if extra_value is not None:
                    any_data = True

        summary = (
            "Нет данных"
            if not any_data
            else (f"Сенсоры: {online} в работе, {degraded} деградации, {offline} отключены")
        )

        subsystem = self._subsystem("sensors", fields, "контроль сенсорного контура", summary=summary)
        subsystem_status = subsystem.status
        if critical_offline >= 2:
            subsystem_status = merge_status(subsystem_status, ViewStatus.CRIT)
        elif critical_offline >= 1:
            subsystem_status = merge_status(subsystem_status, ViewStatus.WARN)
        subsystem.status = subsystem_status
        return subsystem

    def build_hull(self, snapshot: dict[str, Any]) -> SubsystemView:
        integrity = self._v(snapshot, "hull.integrity_pct", "hull.integrity", "hull.hp_pct")
        hp = self._v(snapshot, "hull.hp")
        hp_max = self._v(snapshot, "hull.hp_max")
        if integrity is None and hp is not None and hp_max is not None and hp_max > 0:
            integrity = round((hp / hp_max) * 100.0, 1)

        sector_damage = self._collect_sector_damage(snapshot)
        worst_sector = None
        worst_damage = None
        if sector_damage:
            worst_sector, worst_damage = max(sector_damage.items(), key=lambda item: item[1])
        sectors_top3 = self._format_sector_top3(sector_damage)

        stress = self._v(snapshot, "hull.stress", "hull.structural_stress", "hull.g_load")

        integrity_status = status_by_min(integrity, HULL_INTEGRITY_WARN_PCT, HULL_INTEGRITY_CRIT_PCT)
        sector_status = status_by_max(
            worst_damage,
            HULL_SECTOR_DAMAGE_WARN_PCT,
            HULL_SECTOR_DAMAGE_CRIT_PCT,
        )
        stress_status = status_by_max(stress, HULL_STRESS_WARN, HULL_STRESS_CRIT)

        fields = [
            mk_field(
                "hull.integrity_pct",
                "Целостность корпуса",
                integrity,
                "%",
                integrity_status,
                "предупр < 70%, критично < 40%",
            ),
            mk_field(
                "hull.worst_sector",
                "Худший сектор",
                self._worst_sector_text(worst_sector, worst_damage),
                "",
                sector_status,
                "по проценту повреждения",
            ),
            mk_field(
                "hull.sector_damage",
                "Повреждения по секторам",
                sectors_top3,
                "",
                sector_status,
                "топ-3 по повреждению",
            ),
            mk_field(
                "hull.stress",
                "Нагрузка/стресс",
                stress,
                "ед.",
                stress_status,
                "оценка: warn/crit по внутреннему порогу",
            ),
        ]
        summary = self._hull_summary(integrity=integrity, worst_sector=worst_sector, worst_damage=worst_damage)
        return self._subsystem("hull", fields, "механическая целостность", summary=summary)

    def build_shields(self, snapshot: dict[str, Any]) -> SubsystemView:
        level = self._v(snapshot, "shields.level_pct", "shields.level", "shield.pct")
        hp = self._v(snapshot, "shields.hp")
        hp_max = self._v(snapshot, "shields.hp_max")
        if level is None and hp is not None and hp_max is not None and hp_max > 0:
            level = round((hp / hp_max) * 100.0, 1)

        state_raw = self._raw(snapshot, "shields.state", "shields.active", "shields.mode")
        state = self._state_text(state_raw)
        draw_w = self._v(snapshot, "shields.draw_w", "shields.consumption_w", "shield.power_w")
        recharge_w = self._v(snapshot, "shields.recharge_w", "shields.recharge_rate_w")
        recharge_pct_s = self._v(snapshot, "shields.recharge_pct_s")
        shield_energy = self._v(snapshot, "shields.energy_wh", "shield.energy_wh", "shields.energy_j")

        recharge_value = recharge_w if recharge_w is not None else recharge_pct_s
        recharge_unit = "Вт" if recharge_w is not None else ("%/с" if recharge_pct_s is not None else "")

        level_status = status_by_min(level, SHIELDS_LEVEL_WARN_PCT, SHIELDS_LEVEL_CRIT_PCT)
        state_status = self._shield_state_status(state_raw)

        fields = [
            mk_field(
                "shields.level_pct",
                "Уровень щита",
                level,
                "%",
                level_status,
                "предупр < 30%, критично < 10%",
            ),
            mk_field(
                "shields.state",
                "Режим/состояние",
                state,
                "",
                state_status,
            ),
            mk_field(
                "shields.draw_w",
                "Потребление щита",
                draw_w,
                "Вт",
                ViewStatus.OK if draw_w is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "shields.recharge",
                "Восстановление щита",
                recharge_value,
                recharge_unit,
                ViewStatus.OK if recharge_value is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "shields.energy",
                "Энергия на щит",
                shield_energy,
                "Вт·ч",
                ViewStatus.OK if shield_energy is not None else ViewStatus.NO_DATA,
            ),
        ]
        summary = self._shields_summary(level=level, draw_w=draw_w)
        return self._subsystem("shields", fields, "защитный контур", summary=summary)

    def build_propulsion(self, snapshot: dict[str, Any]) -> SubsystemView:
        fuel_pct = self._v(snapshot, "propulsion.fuel_pct", "propulsion.fuel_percent", "rcs.fuel_pct", "fuel.pct")
        fuel_total_g = self._v(snapshot, "propulsion.fuel_total_g", "fuel.total_g", "fuel.capacity_g")
        fuel_rate_gs = self._v(snapshot, "propulsion.fuel_rate_gs", "rcs.fuel_rate_gs", "fuel.rate_gs")

        fuel_status = status_by_min(fuel_pct, PROPULSION_FUEL_WARN_PCT, PROPULSION_FUEL_CRIT_PCT)
        remaining_fuel_g, remaining_hint = self._remaining_fuel_grams(fuel_pct=fuel_pct, fuel_total_g=fuel_total_g)
        burn_min, burn_hint = self._burn_time_minutes(
            fuel_pct=fuel_pct, fuel_total_g=fuel_total_g, fuel_rate_gs=fuel_rate_gs
        )
        burn_status = status_by_min(burn_min, PROPULSION_BURN_WARN_MIN, PROPULSION_BURN_CRIT_MIN)

        aliases: dict[str, tuple[str, ...]] = {
            "total_thrust_n": ("rcs.total_thrust_n", "propulsion.total_thrust_n"),
            "active_count": ("rcs.active_count",),
            "left_rpm": ("motor_left.rpm", "motor_left.speed_rpm"),
            "right_rpm": ("motor_right.rpm", "motor_right.speed_rpm"),
            "left_current": ("motor_left.current_a",),
            "right_current": ("motor_right.current_a",),
            "left_temp": ("motor_left.temp_c",),
            "right_temp": ("motor_right.temp_c",),
            "left_fault": ("motor_left.fault",),
            "right_fault": ("motor_right.fault",),
        }

        thruster_names = {
            "forward": "РСУ Вперед",
            "aft": "РСУ Назад",
            "port": "РСУ Левый борт",
            "starboard": "РСУ Правый борт",
            "up": "РСУ Вверх",
            "down": "РСУ Вниз",
        }

        thruster_fields: list[TelemetryField] = []
        thruster_thrust_values: list[float] = []
        for name, label in thruster_names.items():
            state = self._bool(
                snapshot,
                f"rcs.{name}.state",
                f"propulsion.rcs.{name}.state",
                f"thrusters.{name}.state",
            )
            thrust_n = self._v(
                snapshot,
                f"rcs.{name}.thrust_n",
                f"thrusters.{name}.thrust_n",
            )
            throttle_pct = self._v(snapshot, f"rcs.{name}.throttle")
            stuck = self._bool(snapshot, f"rcs.{name}.stuck")
            leak = self._bool(snapshot, f"rcs.{name}.leak")
            fault = self._bool(snapshot, f"rcs.{name}.fault")

            if thrust_n is not None:
                thruster_thrust_values.append(thrust_n)

            thruster_status = self._thruster_status(
                state=state,
                thrust_n=thrust_n,
                throttle_pct=throttle_pct,
                stuck=stuck,
                leak=leak,
                fault=fault,
            )
            thruster_text = self._thruster_compact_text(
                state=state,
                thrust_n=thrust_n,
                throttle_pct=throttle_pct,
                stuck=stuck,
                leak=leak,
                fault=fault,
            )
            thruster_fields.append(
                mk_field(
                    f"propulsion.thruster.{name}",
                    label,
                    thruster_text,
                    status=thruster_status,
                    hint="статус/тяга/диагностика РСУ",
                )
            )

        total_thrust_n = self._v(snapshot, *aliases["total_thrust_n"])
        if total_thrust_n is None and thruster_thrust_values:
            total_thrust_n = round(sum(thruster_thrust_values), 2)
        active_count = self._v(snapshot, *aliases["active_count"])

        left_rpm = self._v(snapshot, *aliases["left_rpm"])
        right_rpm = self._v(snapshot, *aliases["right_rpm"])
        left_current = self._v(snapshot, *aliases["left_current"])
        right_current = self._v(snapshot, *aliases["right_current"])
        left_temp = self._v(snapshot, *aliases["left_temp"])
        right_temp = self._v(snapshot, *aliases["right_temp"])
        left_fault = self._bool(snapshot, *aliases["left_fault"])
        right_fault = self._bool(snapshot, *aliases["right_fault"])

        left_temp_status = status_by_max(left_temp, PROPULSION_MOTOR_TEMP_WARN_C, PROPULSION_MOTOR_TEMP_CRIT_C)
        right_temp_status = status_by_max(right_temp, PROPULSION_MOTOR_TEMP_WARN_C, PROPULSION_MOTOR_TEMP_CRIT_C)
        left_fault_status = self._binary_status(left_fault)
        right_fault_status = self._binary_status(right_fault)
        if left_fault_status is ViewStatus.WARN:
            left_fault_status = ViewStatus.CRIT
        if right_fault_status is ViewStatus.WARN:
            right_fault_status = ViewStatus.CRIT
        motor_left_status = merge_status(left_temp_status, left_fault_status)
        motor_right_status = merge_status(right_temp_status, right_fault_status)

        fields: list[TelemetryField] = [
            mk_field(
                "propulsion.fuel_pct",
                "Топливо",
                fuel_pct,
                "%",
                fuel_status,
                "предупр < 20%, критично < 10%",
            ),
            mk_field(
                "propulsion.fuel_rate_gs",
                "Расход топлива",
                fuel_rate_gs,
                "г/с",
                ViewStatus.OK if fuel_rate_gs is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "propulsion.remaining_fuel_g",
                "Осталось топлива",
                remaining_fuel_g,
                "г",
                ViewStatus.OK if remaining_fuel_g is not None else ViewStatus.NO_DATA,
                remaining_hint,
            ),
            mk_field(
                "propulsion.burn_time_min",
                "Осталось до исчерпания",
                burn_min,
                "мин",
                burn_status,
                burn_hint,
            ),
            mk_field(
                "propulsion.total_thrust_n",
                "Суммарная тяга",
                total_thrust_n,
                "Н",
                ViewStatus.OK if total_thrust_n is not None else ViewStatus.NO_DATA,
            ),
            mk_field(
                "propulsion.rcs_active_count",
                "Активных РСУ",
                active_count,
                "",
                ViewStatus.OK if active_count is not None else ViewStatus.NO_DATA,
            ),
        ]
        fields.extend(thruster_fields)
        fields.extend(
            [
                mk_field("motor_left.rpm", "Мотор левый RPM", left_rpm, "RPM", status=motor_left_status),
                mk_field("motor_left.current_a", "Мотор левый ток", left_current, "А", status=motor_left_status),
                mk_field("motor_left.temp_c", "Мотор левый температура", left_temp, "°C", status=left_temp_status),
                mk_field(
                    "motor_left.fault",
                    "Мотор левый авария",
                    self._on_off_text(left_fault),
                    status=left_fault_status,
                ),
                mk_field("motor_right.rpm", "Мотор правый RPM", right_rpm, "RPM", status=motor_right_status),
                mk_field("motor_right.current_a", "Мотор правый ток", right_current, "А", status=motor_right_status),
                mk_field("motor_right.temp_c", "Мотор правый температура", right_temp, "°C", status=right_temp_status),
                mk_field(
                    "motor_right.fault",
                    "Мотор правый авария",
                    self._on_off_text(right_fault),
                    status=right_fault_status,
                ),
            ]
        )

        summary = self._propulsion_summary(
            fuel_pct=fuel_pct, total_thrust_n=total_thrust_n, left_rpm=left_rpm, right_rpm=right_rpm
        )
        return self._subsystem("propulsion", fields, "исполнительный контур", summary=summary)

    def compute_coverage(self, model: HardwareViewModel) -> dict[str, tuple[int, int]]:
        return compute_field_coverage(model)

    def _log_diagnostics_if_enabled(
        self,
        *,
        model: HardwareViewModel,
        snapshot_canon: dict[str, Any],
        monotonic_now: float | None = None,
    ) -> None:
        if os.getenv("ORIONV_HWM_DIAG", "0") != "1":
            return
        period_s = self._diag_period_seconds()
        now_mono = monotonic_now if monotonic_now is not None else time.monotonic()
        if now_mono - self._diag_last_log_monotonic < period_s:
            return
        coverage = compute_field_coverage(model)
        LOGGER.info("%s", format_coverage_line(coverage))

        missing_now = compute_missing_keys(snapshot_canon, SUBSYSTEM_KEYSETS)
        for subsystem, keys in missing_now.items():
            if not keys:
                continue
            self._missing_key_counts.setdefault(subsystem, Counter()).update(keys)

        max_subsystems = 2
        top_n = self._diag_top_n()
        ranked_subsystems = sorted(
            missing_now.keys(),
            key=lambda subsystem: sum(self._missing_key_counts.get(subsystem, Counter()).values()),
            reverse=True,
        )
        for subsystem in ranked_subsystems[:max_subsystems]:
            counts = self._missing_key_counts.get(subsystem, Counter())
            if not counts:
                continue
            top_keys = [f"{key}({count})" for key, count in counts.most_common(top_n)]
            LOGGER.info("%s", format_missing_line(subsystem, top_keys))

        self._diag_last_log_monotonic = now_mono

    def _diag_period_seconds(self) -> float:
        raw = os.getenv("ORIONV_HWM_DIAG_PERIOD_S", "10")
        try:
            value = float(raw)
        except ValueError:
            return 10.0
        return max(1.0, value)

    def _diag_top_n(self) -> int:
        raw = os.getenv("ORIONV_HWM_DIAG_TOP_N", "3")
        try:
            value = int(raw)
        except ValueError:
            return 3
        return max(1, min(value, 10))

    def _comms_link_state(self, state_raw: Any) -> tuple[str | None, ViewStatus]:
        if state_raw is None:
            return None, ViewStatus.NO_DATA
        normalized = normalize_sensor_status(state_raw)
        mapping = {
            "ONLINE": ("В РАБОТЕ", ViewStatus.OK),
            "DEGRADED": ("ДЕГРАДАЦИЯ", ViewStatus.WARN),
            "OFFLINE": ("НЕТ ДАННЫХ", ViewStatus.WARN),
            "UNKNOWN": (None, ViewStatus.NO_DATA),
        }
        text, status = mapping.get(normalized, (str(state_raw), ViewStatus.NO_DATA))
        return text, status

    def _comms_age_seconds(self, snapshot: dict[str, Any], now_ts: float) -> float | None:
        return self._age_seconds(
            snapshot=snapshot,
            now_ts=now_ts,
            last_seen_keys=("comms.last_seen_ts",),
            age_keys=("comms.age_s",),
        )

    def _comms_quality(
        self,
        *,
        latency_status: ViewStatus,
        loss_status: ViewStatus,
        age_status: ViewStatus,
        has_any_metrics: bool,
    ) -> tuple[str | None, ViewStatus]:
        if not has_any_metrics:
            return None, ViewStatus.NO_DATA
        status = merge_status(merge_status(latency_status, loss_status), age_status)
        if status is ViewStatus.CRIT:
            return "КРИТИЧНО", ViewStatus.CRIT
        if status is ViewStatus.WARN:
            return "ПЛОХО", ViewStatus.WARN
        return "НОРМА", ViewStatus.OK

    def _comms_summary(
        self,
        *,
        link_state_text: str | None,
        latency_ms: float | None,
        loss_pct: float | None,
        age_s: float | None,
        quality_text: str | None,
        has_any_key: bool,
    ) -> str:
        if not has_any_key:
            return "Нет данных"
        if latency_ms is not None and loss_pct is not None:
            age_part = f", age {age_s:.0f}с" if age_s is not None else ""
            quality = quality_text or "НОРМА"
            return f"Связь: {quality}, {latency_ms:.0f}мс, loss {loss_pct:.1f}%{age_part}"
        if link_state_text is not None:
            return f"Связь: {link_state_text}"
        return "Нет данных"

    def _age_seconds(
        self,
        *,
        snapshot: dict[str, Any],
        now_ts: float,
        last_seen_keys: tuple[str, ...],
        age_keys: tuple[str, ...],
    ) -> float | None:
        last_seen_ts = self._v(snapshot, *last_seen_keys)
        if last_seen_ts is not None:
            return max(round(now_ts - last_seen_ts, 1), 0.0)
        age_s = self._v(snapshot, *age_keys)
        return round(age_s, 1) if age_s is not None else None

    def _thermal_trend(self, core: float | None) -> str:
        if core is None:
            return "Нет данных"
        prev_core = self._prev_values.get("thermal.core_c")
        self._prev_values["thermal.core_c"] = core
        if prev_core is None:
            return "Нет данных"
        diff = core - prev_core
        if diff > 0.2:
            return "растёт"
        if diff < -0.2:
            return "падает"
        return "стабильно"

    def _thermal_summary(
        self,
        *,
        core: float | None,
        delta: float | None,
        trend_text: str,
        core_state: str | None,
        trip_nodes: list[str],
        warn_nodes: list[str],
    ) -> str:
        if core is None and delta is None:
            return "Нет данных"
        parts = [f"Тепло: {core:.0f}°C"] if core is not None else ["Тепло: Нет данных"]
        if core_state is not None:
            parts.append(f"core {core_state}")
        if delta is not None:
            parts.append(f"ΔT {delta:.0f}°C")
        if trip_nodes:
            parts.append(f"TRIP: {', '.join(trip_nodes)}")
        elif warn_nodes:
            parts.append(f"WARN: {', '.join(warn_nodes)}")
        if trend_text != "Нет данных":
            parts.append(f"({trend_text})")
        return ", ".join(parts)

    def _thermal_nodes(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        raw = self._raw(snapshot, "thermal.nodes")
        if not isinstance(raw, list):
            return []
        nodes: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                nodes.append(item)
        return nodes

    def _thermal_node(self, nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
        needle = node_id.strip().lower()
        if not needle:
            return None
        for node in nodes:
            if str(node.get("id") or "").strip().lower() == needle:
                return node
        return None

    def _node_num(self, node: dict[str, Any] | None, key: str) -> float | None:
        if not isinstance(node, dict):
            return None
        return safe_float(node.get(key))

    def _node_bool(self, node: dict[str, Any] | None, key: str) -> bool | None:
        if not isinstance(node, dict):
            return None
        value = node.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value)
        return None

    def _flagged_nodes(self, nodes: list[dict[str, Any]], flag_key: str) -> list[str]:
        flagged: list[str] = []
        for node in nodes:
            node_id = str(node.get("id") or "").strip()
            if not node_id:
                continue
            if self._node_bool(node, flag_key) is True:
                flagged.append(node_id)
        return list(dict.fromkeys(flagged))

    def _thermal_core_state(
        self,
        *,
        core: float | None,
        warned: bool | None,
        tripped: bool | None,
    ) -> tuple[str | None, ViewStatus]:
        if tripped is True:
            return "TRIP", ViewStatus.CRIT
        if warned is True:
            return "WARN", ViewStatus.WARN
        if warned is False and tripped is False and core is not None:
            return "OK", ViewStatus.OK
        return None, ViewStatus.NO_DATA

    def _thermal_nodes_text(
        self,
        *,
        nodes: list[dict[str, Any]],
        flagged: list[str],
        flagged_status: ViewStatus,
    ) -> tuple[str | None, ViewStatus]:
        if not nodes:
            return None, ViewStatus.NO_DATA
        if flagged:
            return ", ".join(flagged), flagged_status
        return "—", ViewStatus.OK

    def _compute_summary(self, heartbeat_age: float | None, cpu: float | None, heartbeat_status: ViewStatus) -> str:
        if heartbeat_age is None and cpu is None:
            return "Нет данных"
        if heartbeat_age is not None and heartbeat_status is ViewStatus.CRIT:
            return f"Compute: heartbeat {heartbeat_age:.0f}с (КРИТИЧНО)"
        parts: list[str] = []
        if heartbeat_age is not None:
            parts.append(f"heartbeat {heartbeat_age:.0f}с")
        if cpu is not None:
            parts.append(f"CPU {cpu:.0f}%")
        if parts:
            return "Compute: " + ", ".join(parts)
        return "Нет данных"

    def _subsystem(
        self, subsystem_id: str, fields: list[TelemetryField], summary_tail: str, summary: str | None = None
    ) -> SubsystemView:
        status = ViewStatus.NO_DATA
        has_data = False
        for field in fields:
            status = merge_status(status, field.status)
            has_data = has_data or field.status is not ViewStatus.NO_DATA
        if not has_data:
            status = ViewStatus.NO_DATA
        title = self._SUBSYSTEM_TITLES[subsystem_id]
        summary = summary if summary is not None else f"{status} | {summary_tail}"
        return SubsystemView(id=subsystem_id, title=title, status=status, fields=fields, summary=summary)

    def _v(self, snapshot: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = self._get_value(snapshot, key)
            parsed = safe_float(value)
            if parsed is not None:
                return parsed
        return None

    def _raw(self, snapshot: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = self._get_value(snapshot, key)
            if value is not None:
                return value
        return None

    def _bool(self, snapshot: dict[str, Any], *keys: str) -> bool | None:
        value = self._raw(snapshot, *keys)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "on", "yes", "active", "enabled", "warn", "limited", "online", "up"}:
                return True
            if normalized in {"0", "false", "off", "no", "inactive", "disabled", "normal", "ok", "offline", "down"}:
                return False
        return None

    def _on_off_text(self, value: bool | None) -> str | None:
        if value is None:
            return None
        return "ВКЛ" if value else "ВЫКЛ"

    def _state_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return self._on_off_text(value)
        return str(value)

    def _binary_status(self, value: bool | None) -> ViewStatus:
        if value is None:
            return ViewStatus.NO_DATA
        return ViewStatus.WARN if value else ViewStatus.OK

    def _string_status(self, value: str | None) -> ViewStatus:
        return ViewStatus.OK if value is not None else ViewStatus.NO_DATA

    def _load_shedding_status(self, active: bool | None, soc_status: ViewStatus) -> ViewStatus:
        if active is None:
            return ViewStatus.NO_DATA
        if not active:
            return ViewStatus.OK
        if soc_status in {ViewStatus.WARN, ViewStatus.CRIT}:
            return ViewStatus.CRIT
        return ViewStatus.WARN

    def _extract_reasons(self, snapshot: dict[str, Any], *keys: str) -> list[str]:
        value = self._raw(snapshot, *keys)
        if isinstance(value, list):
            normalized = [str(item).strip() for item in value if str(item).strip()]
            return list(dict.fromkeys(normalized))
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        return []

    def _shed_reasons_value(
        self,
        *,
        load_shedding: bool | None,
        load_status: ViewStatus,
        reasons: list[str],
    ) -> tuple[str | None, ViewStatus]:
        if reasons:
            if load_shedding is False:
                return ", ".join(reasons), ViewStatus.WARN
            return ", ".join(reasons), load_status
        if load_shedding is True:
            return "degraded: нет данных", ViewStatus.WARN
        if load_shedding is False:
            return "—", ViewStatus.OK
        return None, ViewStatus.NO_DATA

    def _runtime_minutes(
        self, soc: float | None, power_w: float | None, capacity_wh: float | None
    ) -> tuple[float | None, str]:
        if soc is None:
            return None, "требуются SoC и потребление"
        battery_wh = capacity_wh if capacity_wh is not None else DEFAULT_BATTERY_CAPACITY_WH
        estimated = capacity_wh is None
        if battery_wh <= 0:
            return None, "емкость батареи некорректна"
        if power_w is None or power_w <= EPSILON_POWER_W:
            return None, "расчет недоступен при нулевом/отрицательном потреблении"
        remaining_wh = battery_wh * soc / 100.0
        runtime_min = (remaining_wh / max(power_w, EPSILON_POWER_W)) * 60.0
        hint = "оценочно (емкость по умолчанию 500Wh)" if estimated else "расчет по SoC и текущему потреблению"
        return round(runtime_min, 1), hint

    def _power_summary(self, soc: float | None, bus_v: float | None, runtime_min: float | None) -> str:
        if soc is None and bus_v is None and runtime_min is None:
            return "Нет данных"
        parts: list[str] = []
        if soc is not None:
            parts.append(f"Заряд {soc:.0f}%")
        if bus_v is not None:
            parts.append(f"{bus_v:.1f}В")
        if runtime_min is not None:
            parts.append(f"~{runtime_min:.0f} мин")
        return ", ".join(parts) if parts else "Нет данных"

    def _remaining_fuel_grams(self, fuel_pct: float | None, fuel_total_g: float | None) -> tuple[float | None, str]:
        if fuel_pct is None:
            return None, "требуется уровень топлива"
        total = fuel_total_g if fuel_total_g is not None else DEFAULT_FUEL_TOTAL_G
        estimated = fuel_total_g is None
        if total <= 0:
            return None, "общий запас топлива некорректен"
        remaining = total * fuel_pct / 100.0
        hint = "оценка (запас по умолчанию)" if estimated else "расчет по уровню и емкости"
        return round(remaining, 1), hint

    def _burn_time_minutes(
        self, fuel_pct: float | None, fuel_total_g: float | None, fuel_rate_gs: float | None
    ) -> tuple[float | None, str]:
        if fuel_rate_gs is None:
            return None, "нет данных по расходу топлива"
        if fuel_rate_gs <= EPSILON_POWER_W:
            return None, "расход нулевой/отрицательный"
        remaining_g, remaining_hint = self._remaining_fuel_grams(fuel_pct=fuel_pct, fuel_total_g=fuel_total_g)
        if remaining_g is None:
            return None, remaining_hint
        burn_sec = remaining_g / max(fuel_rate_gs, EPSILON_POWER_W)
        burn_min = burn_sec / 60.0
        hint = "оценка по умолчанию" if fuel_total_g is None else "расчет по уровню и расходу"
        return round(burn_min, 1), hint

    def _thruster_status(
        self,
        *,
        state: bool | None,
        thrust_n: float | None,
        throttle_pct: float | None,
        stuck: bool | None,
        leak: bool | None,
        fault: bool | None,
    ) -> ViewStatus:
        has_any_data = any(value is not None for value in (state, thrust_n, throttle_pct, stuck, leak, fault))
        if not has_any_data:
            return ViewStatus.NO_DATA
        status = ViewStatus.OK
        if fault:
            status = ViewStatus.WARN
        if stuck or leak:
            status = ViewStatus.CRIT
        return status

    def _thruster_compact_text(
        self,
        *,
        state: bool | None,
        thrust_n: float | None,
        throttle_pct: float | None,
        stuck: bool | None,
        leak: bool | None,
        fault: bool | None,
    ) -> str | None:
        parts: list[str] = []
        if state is not None:
            parts.append(self._on_off_text(state) or "")
        if thrust_n is not None:
            parts.append(f"{thrust_n:.1f} Н")
        elif throttle_pct is not None:
            parts.append(f"{throttle_pct:.0f}%")
        alerts: list[str] = []
        if stuck:
            alerts.append("застрял")
        if leak:
            alerts.append("утечка")
        if fault:
            alerts.append("fault")
        if alerts:
            parts.append(f"АВАРИЯ: {', '.join(alerts)}")
        return ", ".join(part for part in parts if part) if parts else None

    def _propulsion_summary(
        self, fuel_pct: float | None, total_thrust_n: float | None, left_rpm: float | None, right_rpm: float | None
    ) -> str:
        if fuel_pct is None and total_thrust_n is None and left_rpm is None and right_rpm is None:
            return "Нет данных"
        parts: list[str] = []
        if fuel_pct is not None:
            parts.append(f"Топливо {fuel_pct:.0f}%")
        if total_thrust_n is not None:
            parts.append(f"тяга {total_thrust_n:.0f} Н")
        if left_rpm is not None and right_rpm is not None:
            parts.append(f"мот(L/R) {left_rpm:.0f}/{right_rpm:.0f} RPM")
        return ", ".join(parts) if parts else "Нет данных"

    def _collect_sector_damage(self, snapshot: dict[str, Any]) -> dict[str, float]:
        sectors: dict[str, float] = {}
        for key in ("hull.sector_damage", "hull.damage_sectors", "sensor_mounts.damage"):
            raw = self._raw(snapshot, key)
            if isinstance(raw, dict):
                for name, value in raw.items():
                    parsed = safe_float(value)
                    if parsed is not None:
                        sectors[str(name)] = parsed

        for key, value in snapshot.items():
            if not isinstance(key, str):
                continue
            if key.startswith("hull.sector_") and key.endswith("_pct"):
                parsed = safe_float(value)
                if parsed is None:
                    continue
                sector_name = key[len("hull.sector_") : -len("_pct")]
                sectors[sector_name.replace("_", " ")] = parsed
        return sectors

    def _worst_sector_text(self, sector_name: str | None, damage_pct: float | None) -> str | None:
        if sector_name is None or damage_pct is None:
            return None
        return f"{sector_name} ({damage_pct:.0f}%)"

    def _format_sector_top3(self, sector_damage: dict[str, float]) -> str | None:
        if not sector_damage:
            return None
        top = sorted(sector_damage.items(), key=lambda item: item[1], reverse=True)[:3]
        return ", ".join(f"{name} {damage:.0f}%" for name, damage in top)

    def _hull_summary(self, integrity: float | None, worst_sector: str | None, worst_damage: float | None) -> str:
        if integrity is None and worst_sector is None and worst_damage is None:
            return "Нет данных"
        parts: list[str] = []
        if integrity is not None:
            parts.append(f"Корпус {integrity:.0f}%")
        if worst_sector is not None and worst_damage is not None:
            parts.append(f"худший сектор: {worst_sector} {worst_damage:.0f}%")
        return ", ".join(parts) if parts else "Нет данных"

    def _shield_state_status(self, state_raw: Any) -> ViewStatus:
        if state_raw is None:
            return ViewStatus.NO_DATA
        normalized = normalize_sensor_status(state_raw)
        if normalized == "UNKNOWN":
            text = str(state_raw).strip().lower()
            if "fault" in text:
                return ViewStatus.CRIT
            if text in {"offline", "down", "lost"}:
                return ViewStatus.WARN
            return ViewStatus.OK
        if normalized == "OFFLINE":
            return ViewStatus.WARN
        if normalized == "DEGRADED":
            return ViewStatus.WARN
        return ViewStatus.OK

    def _shields_summary(self, level: float | None, draw_w: float | None) -> str:
        if level is None and draw_w is None:
            return "Нет данных"
        parts: list[str] = []
        if level is not None:
            parts.append(f"Щит {level:.0f}%")
        if draw_w is not None:
            parts.append(f"расход {draw_w:.0f} Вт")
        return ", ".join(parts) if parts else "Нет данных"

    def _docking_eta(self, distance_m: float | None, approach_mps: float | None) -> tuple[float | None, str]:
        if distance_m is None or approach_mps is None:
            return None, "требуются дистанция и скорость сближения"
        if approach_mps <= 0:
            return None, "скорость ≤ 0"
        eta = distance_m / approach_mps
        return round(eta, 2), "оценка по текущей скорости"

    def _docking_lock_status(
        self, lock_state: str | None, locked_bool: bool | None, capture: bool | None
    ) -> ViewStatus:
        if locked_bool is True:
            return ViewStatus.OK
        if lock_state is None and capture is None and locked_bool is None:
            return ViewStatus.NO_DATA
        lock_norm = str(lock_state).strip().lower() if lock_state is not None else ""
        if lock_norm == "locked":
            return ViewStatus.OK
        if capture is True:
            return ViewStatus.WARN
        return ViewStatus.WARN

    def _lock_display(self, lock_state: str | None, locked_bool: bool | None) -> str | None:
        if locked_bool is True:
            return "ВКЛ"
        if locked_bool is False:
            return "ВЫКЛ"
        return lock_state

    def _docking_summary(
        self,
        *,
        state: str | None,
        distance: float | None,
        approach: float | None,
        alignment: float | None,
        lock_state: str | None,
        locked_bool: bool | None,
    ) -> str:
        lock_norm = str(lock_state).strip().lower() if lock_state is not None else ""
        if locked_bool is True or lock_norm == "locked":
            return "Стыковка: ЗАФИКСИРОВАНО"
        if state is None and distance is None and approach is None and alignment is None:
            return "Нет данных"
        parts: list[str] = []
        if state is not None:
            parts.append(f"Стыковка: {state}")
        if distance is not None:
            parts.append(f"{distance:.1f} м")
        if approach is not None:
            parts.append(f"{approach:.2f} м/с")
        if alignment is not None:
            parts.append(f"{alignment:.1f}°")
        return ", ".join(parts) if parts else "Нет данных"

    def _navigation_confidence_status(self, confidence: float | None) -> ViewStatus:
        if confidence is None:
            return ViewStatus.NO_DATA
        if confidence < NAV_CONFIDENCE_CRIT:
            return ViewStatus.CRIT
        if confidence < NAV_CONFIDENCE_WARN:
            return ViewStatus.WARN
        return ViewStatus.OK

    def _navigation_quality(self, confidence: float | None, star_status_raw: Any) -> str | None:
        if confidence is not None:
            if confidence >= NAV_CONFIDENCE_WARN:
                return "Высокое"
            if confidence >= NAV_CONFIDENCE_LOW:
                return "Среднее"
            return "Низкое"
        if self._status_is_offline(star_status_raw):
            return "Низкое"
        return None

    def _status_is_offline(self, raw_value: Any) -> bool:
        if raw_value is None:
            return False
        if isinstance(raw_value, bool):
            return raw_value is False
        normalized = str(raw_value).strip().lower()
        return normalized in {"offline", "off", "down", "lost", "disconnected", "0", "false"}

    def _is_imu_only_and_star_offline(self, mode_raw: Any, star_status_raw: Any) -> bool:
        if mode_raw is None:
            return False
        mode_norm = str(mode_raw).strip().upper()
        return mode_norm == "IMU_ONLY" and self._status_is_offline(star_status_raw)

    def _navigation_summary(
        self, speed: float | None, heading: float | None, pitch: float | None, yaw: float | None, roll: float | None
    ) -> str:
        if speed is None and heading is None and pitch is None and yaw is None and roll is None:
            return "Нет данных"
        parts: list[str] = []
        if speed is not None:
            parts.append(f"Скорость {speed:.1f} м/с")
        if heading is not None:
            parts.append(f"курс {heading:.0f}°")
        if pitch is not None and yaw is not None and roll is not None:
            parts.append(f"P/Y/R {pitch:.0f}/{yaw:.0f}/{roll:.0f}°")
        return ", ".join(parts) if parts else "Нет данных"

    def _sensor_confidence_status(self, confidence: float | None) -> ViewStatus:
        if confidence is None:
            return ViewStatus.NO_DATA
        if confidence < 0.2:
            return ViewStatus.CRIT
        if confidence < 0.5:
            return ViewStatus.WARN
        return ViewStatus.OK

    def _sensor_status(
        self, snapshot: dict[str, Any], aliases: tuple[str, ...] | list[str]
    ) -> tuple[str, str | None, str]:
        for alias in aliases:
            # Real q-sim sensor status lives under sensor_plane.<alias>.status; it MUST be read
            # before the .enabled fallback, otherwise an enabled-but-degraded sensor is masked
            # as OK (a dishonest perception surface). REQ-SENSOR / IF-SENSOR-TELEM §15.
            status_raw = self._raw(
                snapshot, f"sensor.{alias}.status", f"{alias}.status", f"sensor_plane.{alias}.status"
            )
            if status_raw is not None:
                normalized = normalize_sensor_status(status_raw)
                # An UNKNOWN-normalizing status (e.g. "na", "") is not informative; fall through to
                # the .enabled signal so a deliberately-disabled sensor still reads "Отключен"
                # rather than "Нет данных".
                if normalized != "UNKNOWN":
                    return normalized, self._sensor_status_text(normalized), "status"

            enabled_raw = self._raw(snapshot, f"sensor_plane.{alias}.enabled")
            if enabled_raw is not None:
                normalized = normalize_sensor_status(enabled_raw)
                text = "Отключен" if normalized == "OFFLINE" else self._sensor_status_text(normalized)
                return normalized, text, "enabled"

            online_raw = self._raw(snapshot, f"{alias}.online")
            if online_raw is not None:
                normalized = normalize_sensor_status(online_raw)
                text = "Нет данных" if normalized == "OFFLINE" else self._sensor_status_text(normalized)
                return normalized, text, "online"

        return "UNKNOWN", None, "none"

    def _sensor_status_text(self, status_norm: str) -> str | None:
        mapping = {
            "ONLINE": "В работе",
            "DEGRADED": "Снижение качества",
            "OFFLINE": "Нет данных",
            "UNKNOWN": None,
        }
        return mapping.get(status_norm)

    def _sensor_status_to_view_status(self, status_norm: str) -> ViewStatus:
        if status_norm == "ONLINE":
            return ViewStatus.OK
        if status_norm == "DEGRADED":
            return ViewStatus.WARN
        if status_norm == "OFFLINE":
            return ViewStatus.WARN
        return ViewStatus.NO_DATA

    def _parse_xyz_vector(self, value: Any) -> tuple[float, float, float] | None:
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            x = safe_float(value[0])
            y = safe_float(value[1])
            z = safe_float(value[2])
            if x is not None and y is not None and z is not None:
                return (x, y, z)
        if isinstance(value, dict):
            x = safe_float(value.get("x"))
            y = safe_float(value.get("y"))
            z = safe_float(value.get("z"))
            if x is not None and y is not None and z is not None:
                return (x, y, z)
        return None

    def _get_value(self, snapshot: dict[str, Any], dotted_key: str) -> Any:
        if dotted_key in snapshot:
            return snapshot[dotted_key]
        current: Any = snapshot
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
