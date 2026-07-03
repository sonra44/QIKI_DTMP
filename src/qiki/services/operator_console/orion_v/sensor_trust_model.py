from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from qiki.shared.sensor_trust import build_sensor_trust_snapshot as _shared_build_sensor_trust_snapshot

try:
    from qiki.services.operator_console.orion_v.ui_truth import TruthKind, truth_badge
except Exception:  # pragma: no cover - keeps the pure model importable in minimal tooling.
    class TruthKind(StrEnum):
        DERIVED = "DERIVED"

    def truth_badge(kind: TruthKind | str, path: str = "", note: str = "") -> str:
        kind_text = str(getattr(kind, "value", kind)).upper()
        source = f" {path}" if str(path or "").strip() else ""
        suffix = f"; {note}" if note else ""
        return f"[{kind_text}{source}{suffix}]"


class SensorTrustState(StrEnum):
    TRUSTED = "trusted"
    DEGRADED = "degraded"
    CONFLICTING = "conflicting"
    LOTTERY = "lottery"
    BLIND = "blind"


class SensorTrustOverride(StrEnum):
    AUTO = "auto"
    TRUSTED = "trusted"
    DEGRADED = "degraded"
    CONFLICTING = "conflicting"
    LOTTERY = "lottery"
    BLIND = "blind"


_STATE_RU: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "сенсоры достоверны",
    SensorTrustState.DEGRADED: "сенсоры деградируют",
    SensorTrustState.CONFLICTING: "сенсоры противоречат",
    SensorTrustState.LOTTERY: "телеметрия-лотерея",
    SensorTrustState.BLIND: "слепой режим",
}

_STATE_SEVERITY: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "normal",
    SensorTrustState.DEGRADED: "warning",
    SensorTrustState.CONFLICTING: "warning",
    SensorTrustState.LOTTERY: "critical",
    SensorTrustState.BLIND: "warning",
}

_STATE_F2_SEVERITY: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "ok",
    SensorTrustState.DEGRADED: "warn",
    SensorTrustState.CONFLICTING: "warn",
    SensorTrustState.LOTTERY: "crit",
    SensorTrustState.BLIND: "warn",
}

_STATE_NEXT_STEP: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "можно использовать сенсорную картину, сверяя свежесть данных",
    SensorTrustState.DEGRADED: "открыть F2/F3 и проверить, какие сенсоры потеряли качество",
    SensorTrustState.CONFLICTING: "сравнить evidence в F3; не подтверждать рискованные действия без проверки",
    SensorTrustState.LOTTERY: "считать внешнюю картину недостоверной; перейти к корпусной телеметрии и ручному подтверждению",
    SensorTrustState.BLIND: "не полагаться на внешнее восприятие; использовать body-only телеметрию и короткие шаги",
}

_EXPLICIT_STATE_ALIASES: dict[str, SensorTrustState] = {
    "trusted": SensorTrustState.TRUSTED,
    "healthy": SensorTrustState.TRUSTED,
    "ok": SensorTrustState.TRUSTED,
    "normal": SensorTrustState.TRUSTED,
    "nominal": SensorTrustState.TRUSTED,
    "degraded": SensorTrustState.DEGRADED,
    "degrade": SensorTrustState.DEGRADED,
    "warn": SensorTrustState.DEGRADED,
    "warning": SensorTrustState.DEGRADED,
    "conflicting": SensorTrustState.CONFLICTING,
    "conflict": SensorTrustState.CONFLICTING,
    "contradiction": SensorTrustState.CONFLICTING,
    "contradictory": SensorTrustState.CONFLICTING,
    "lottery": SensorTrustState.LOTTERY,
    "chaos": SensorTrustState.LOTTERY,
    "uncertain": SensorTrustState.LOTTERY,
    "uncertainty": SensorTrustState.LOTTERY,
    "anomaly": SensorTrustState.LOTTERY,
    "blind": SensorTrustState.BLIND,
    "body_only": SensorTrustState.BLIND,
    "body-only": SensorTrustState.BLIND,
    "body telemetry only": SensorTrustState.BLIND,
    "external_off": SensorTrustState.BLIND,
}

_BAD_STATUSES = {
    "failed",
    "fail",
    "fault",
    "faulted",
    "degraded",
    "unstable",
    "corrupt",
    "corrupted",
    "stale",
    "lost",
    "missing",
    "нет данных",
    "нет_данных",
    "ошибка",
    "сбой",
    "деградация",
    "поврежден",
    "повреждён",
}
_OFF_STATUSES = {"off", "disabled", "configured_disabled", "отключен", "отключён", "выключен"}
_GOOD_STATUSES = {"ok", "healthy", "nominal", "locked", "online", "active", "норма", "готов", "готово"}


@dataclass(frozen=True, slots=True)
class SensorTrustSnapshot:
    state: SensorTrustState
    confidence: float
    reason_ru: str
    evidence: tuple[str, ...]
    source_path: str = "sensor_trust_model"

    @property
    def label_ru(self) -> str:
        return _STATE_RU[self.state]

    @property
    def severity(self) -> str:
        return _STATE_SEVERITY[self.state]

    @property
    def f2_severity(self) -> str:
        return _STATE_F2_SEVERITY[self.state]

    @property
    def next_step_ru(self) -> str:
        return _STATE_NEXT_STEP[self.state]

    @property
    def truth_badge(self) -> str:
        return truth_badge(TruthKind.DERIVED, self.source_path, "sensor confidence; not runtime truth")

    @property
    def short_chip(self) -> str:
        return f"{self.state.value} {self.confidence:.2f}"

    @property
    def status_key(self) -> str:
        return self.state.value

    @property
    def operator_effect_ru(self) -> str:
        return self.reason_ru


def normalize_sensor_trust_override(value: str | None) -> SensorTrustOverride:
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "": SensorTrustOverride.AUTO,
        "auto": SensorTrustOverride.AUTO,
        "clear": SensorTrustOverride.AUTO,
        "reset": SensorTrustOverride.AUTO,
        "trusted": SensorTrustOverride.TRUSTED,
        "trust": SensorTrustOverride.TRUSTED,
        "ok": SensorTrustOverride.TRUSTED,
        "degraded": SensorTrustOverride.DEGRADED,
        "degrade": SensorTrustOverride.DEGRADED,
        "warn": SensorTrustOverride.DEGRADED,
        "conflicting": SensorTrustOverride.CONFLICTING,
        "conflict": SensorTrustOverride.CONFLICTING,
        "lottery": SensorTrustOverride.LOTTERY,
        "uncertain": SensorTrustOverride.LOTTERY,
        "anomaly": SensorTrustOverride.LOTTERY,
        "blind": SensorTrustOverride.BLIND,
        "body-only": SensorTrustOverride.BLIND,
        "bodyonly": SensorTrustOverride.BLIND,
    }
    return aliases.get(text, SensorTrustOverride.AUTO)


def assess_sensor_trust(
    *,
    hardware_model: Any | None,
    telemetry: Mapping[str, Any] | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None = None,
    observation_objective: Mapping[str, Any] | None = None,
    operator_override: SensorTrustOverride | str | None = None,
) -> SensorTrustSnapshot:
    override = operator_override if isinstance(operator_override, SensorTrustOverride) else normalize_sensor_trust_override(str(operator_override or ""))
    if override is not SensorTrustOverride.AUTO:
        state = SensorTrustState(override.value)
        return _snapshot(
            state,
            evidence=["LOCAL operator override; runtime telemetry not changed"],
            reason_ru=f"оператор локально пометил сенсоры как {state.value}; это UI/decision hint, не runtime truth",
            confidence={
                SensorTrustState.TRUSTED: 0.75,
                SensorTrustState.DEGRADED: 0.52,
                SensorTrustState.CONFLICTING: 0.35,
                SensorTrustState.LOTTERY: 0.18,
                SensorTrustState.BLIND: 0.12,
            }[state],
            source_path="LOCAL operator sensor trust override",
        )
    _ = observation_objective
    return build_sensor_trust_snapshot(
        telemetry=telemetry,
        radar_tracks=radar_tracks,
        hardware_model=hardware_model,
        incidents=None,
    )


def build_sensor_trust_snapshot(
    *,
    telemetry: Mapping[str, Any] | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None = None,
    hardware_model: Any | None = None,
    incidents: Sequence[Mapping[str, Any]] | None = None,
) -> SensorTrustSnapshot:
    tel = telemetry or {}
    try:
        shared_snapshot = _shared_build_sensor_trust_snapshot(
            telemetry=tel,
            radar_tracks=radar_tracks,
            hardware_model=hardware_model,
            incidents=incidents,
        )
        return _snapshot(
            SensorTrustState(shared_snapshot.state.value),
            evidence=list(shared_snapshot.evidence),
            reason_ru=shared_snapshot.reason_ru,
            confidence=shared_snapshot.confidence,
            source_path=shared_snapshot.source_path,
        )
    except Exception:
        # ORION keeps its older local heuristic as a defensive fallback, but the
        # preferred runtime contract is qiki.shared.sensor_trust.
        pass
    evidence: list[str] = []

    explicit = _explicit_state(tel)
    if explicit is not None:
        reason = _pick_text(tel, ("sensor_trust", "reason"), ("sensor_trust", "reason_ru"), ("sensor_reason",))
        evidence.append(f"explicit state={explicit.value}")
        source = _pick_text(tel, ("sensor_trust", "source"), ("sensor_trust_source",)) or "qiki.telemetry.sensor_trust"
        return _snapshot(
            explicit,
            evidence=evidence,
            reason_ru=reason or _reason_for_state(explicit),
            source_path=source,
            confidence=_explicit_confidence(tel, explicit),
        )

    track_count = _track_count(radar_tracks)
    sensor_plane = _as_mapping(tel.get("sensor_plane"))
    sensors_subsystem = _subsystem(hardware_model, "sensors")
    sensor_fields_present = _subsystem_has_values(sensors_subsystem)
    if track_count:
        evidence.append(f"radar tracks={track_count}")
    if sensor_plane:
        evidence.append("sensor_plane present")
    if sensor_fields_present:
        evidence.append("hardware_view_model.sensors has values")

    radiation_usvh = _first_number(
        _get(sensor_plane, "radiation", "background_usvh"),
        _get(sensor_plane, "radiation", "background_uSv_h"),
        _get(tel, "radiation", "background_usvh"),
        _get(tel, "radiation_usvh"),
    )
    radiation_status = _status_text(_get(sensor_plane, "radiation", "status"), _get(tel, "radiation", "status"))
    if radiation_usvh is not None:
        evidence.append(f"radiation={radiation_usvh:g} uSv/h")
    if radiation_status:
        evidence.append(f"radiation status={radiation_status}")

    if _looks_lottery_from_events_or_text(tel, incidents) or _is_lottery_radiation(radiation_usvh, radiation_status):
        return _snapshot(
            SensorTrustState.LOTTERY,
            evidence=evidence or ["anomaly/radiation marker present"],
            reason_ru="радиация/аномалия делает синтаксически валидные данные недостоверными",
            confidence=0.18,
        )

    proximity_contacts = _first_number(
        _get(sensor_plane, "proximity", "contacts"),
        _get(tel, "proximity", "contacts"),
        _get(tel, "docking", "contacts"),
    )
    proximity_range_m = _first_number(
        _get(sensor_plane, "proximity", "min_range_m"),
        _get(tel, "proximity", "min_range_m"),
        _get(tel, "docking", "distance_m"),
    )
    if proximity_contacts is not None:
        evidence.append(f"proximity contacts={proximity_contacts:g}")
    if proximity_range_m is not None:
        evidence.append(f"proximity range={proximity_range_m:g}m")

    conflict_markers = _conflict_markers(tel, sensor_plane=sensor_plane, track_count=track_count)
    if proximity_contacts is not None and proximity_contacts > 0 and track_count == 0:
        conflict_markers.append("proximity sees contact but radar has no tracks")
    if proximity_range_m is not None and 0 <= proximity_range_m <= 250 and track_count == 0:
        conflict_markers.append("close range contact without radar track")
    if conflict_markers:
        return _snapshot(
            SensorTrustState.CONFLICTING,
            evidence=[*evidence, *conflict_markers],
            reason_ru="сенсорные источники дают несовместимую картину",
            confidence=0.34,
        )

    status_markers = _sensor_status_markers(sensor_plane, sensors_subsystem)
    bad_markers = status_markers["bad"]
    off_markers = status_markers["off"]
    good_markers = status_markers["good"]
    if bad_markers:
        return _snapshot(
            SensorTrustState.DEGRADED,
            evidence=[*evidence, *bad_markers[:5]],
            reason_ru="часть сенсорного контура сообщает деградацию или устаревшие данные",
            confidence=0.52,
        )

    if _body_only_mode(tel, off_markers=off_markers) or (off_markers and not track_count and not good_markers):
        return _snapshot(
            SensorTrustState.BLIND,
            evidence=[*evidence, *off_markers[:5]] or ["external sensors disabled/off"],
            reason_ru="внешнее восприятие выключено или недоступно; остаётся корпусная телеметрия",
            confidence=0.40,
        )

    if not track_count and not sensor_plane and not sensor_fields_present:
        return _snapshot(
            SensorTrustState.DEGRADED,
            evidence=["no live radar/sensor_plane/hardware sensor evidence"],
            reason_ru="нет доказанного live sensor-source; доверие понижено",
            confidence=0.45,
        )

    confidence_values = _confidence_values(tel, sensor_plane, sensors_subsystem)
    if confidence_values:
        min_conf = min(confidence_values)
        evidence.append(f"min confidence={min_conf:.2f}")
        if min_conf < 0.25:
            return _snapshot(
                SensorTrustState.DEGRADED,
                evidence=evidence,
                reason_ru="сенсорный контур сообщает низкую confidence",
                confidence=max(0.25, min_conf),
            )

    return _snapshot(
        SensorTrustState.TRUSTED,
        evidence=evidence or ["sensor contour has no conflict markers"],
        reason_ru="нет признаков конфликта, lottery-mode или blind-mode",
        confidence=_average_confidence(confidence_values, fallback=0.82),
    )


def render_sensor_trust_summary_lines(snapshot: SensorTrustSnapshot) -> list[str]:
    return [
        f"Sensor Trust: {snapshot.state.value.upper()} / {snapshot.label_ru} {snapshot.truth_badge}",
        f"Reason: {snapshot.reason_ru}",
        f"Confidence: {snapshot.confidence:.2f}",
        f"Next: {snapshot.next_step_ru}",
    ]


def sensor_trust_status_line(snapshot: SensorTrustSnapshot) -> str:
    return f"SENSOR TRUST: {snapshot.state.value.upper()} | {snapshot.label_ru} | confidence={snapshot.confidence:.2f}"


def sensor_trust_f2_lines(snapshot: SensorTrustSnapshot) -> list[str]:
    return [
        f"Trust: {snapshot.label_ru} ({snapshot.state.value}, {snapshot.confidence:.2f})",
        f"Effect: {snapshot.reason_ru}",
        f"Next: {snapshot.next_step_ru}",
    ]


def render_sensor_trust_evidence_lines(snapshot: SensorTrustSnapshot, *, limit: int = 6) -> list[str]:
    lines = [
        f"Достоверность сенсоров: {snapshot.state.value.upper()} / {snapshot.label_ru}",
        f"Источник: {snapshot.truth_badge}",
        f"Причина: {snapshot.reason_ru}",
        f"Следующее действие: {snapshot.next_step_ru}",
        "Evidence:",
    ]
    evidence = list(snapshot.evidence[: max(0, limit)]) or ["нет детальных evidence; состояние вычислено как derived summary"]
    lines.extend(f"- {item}" for item in evidence)
    return lines


def sensor_trust_provider_context_lines(snapshot: SensorTrustSnapshot) -> list[str]:
    return [
        f"sensor_trust.state={snapshot.state.value}",
        f"sensor_trust.confidence={snapshot.confidence:.2f}",
        f"sensor_trust.reason={snapshot.reason_ru}",
        "sensor_trust.authority=derived_operator_hint_not_runtime_truth",
    ]


def sensor_trust_evidence_lines(snapshot: SensorTrustSnapshot, *, limit: int = 6) -> list[str]:
    return render_sensor_trust_evidence_lines(snapshot, limit=limit)


def sensor_trust_qiki_reaction_lines(snapshot: SensorTrustSnapshot) -> list[str]:
    return [sensor_trust_qiki_hint(snapshot)]


def sensor_trust_qiki_hint(snapshot: SensorTrustSnapshot) -> str:
    if snapshot.state is SensorTrustState.TRUSTED:
        return "QIKI: сенсорная картина выглядит согласованной; всё равно сверяйте свежесть telemetry."
    if snapshot.state is SensorTrustState.DEGRADED:
        return "QIKI: часть сенсоров деградирует. Я могу объяснить, какие источники слабые, перед действием нужен осторожный контекст."
    if snapshot.state is SensorTrustState.CONFLICTING:
        return "QIKI: сенсоры противоречат друг другу. Рекомендую F3 evidence и не подтверждать рискованные действия вслепую."
    if snapshot.state is SensorTrustState.LOTTERY:
        return "QIKI: текущая телеметрия похожа на лотерею. Считать внешние сенсоры недостоверными; опираться на корпусные признаки и ручное подтверждение."
    return "QIKI: внешний сенсорный контур слепой. Использовать body-only телеметрию и короткие шаги до восстановления картины."


def sensor_trust_command_help_lines() -> list[str]:
    return [
        "sensor trust | qiki sensor trust — показать derived доверие к сенсорам",
        "qiki distrust sensors / sensor lottery — локально пометить сенсоры как lottery",
        "qiki body telemetry only / sensor blind — локально перейти к body-only/blind posture",
        "sensor trust auto / qiki trust sensors — снять локальный override",
    ]


def parse_sensor_trust_command(raw_command: str) -> SensorTrustOverride | None:
    command = str(raw_command or "").strip().lower()
    command_map = {
        "qiki distrust sensors": SensorTrustOverride.LOTTERY,
        "distrust sensors": SensorTrustOverride.LOTTERY,
        "sensor lottery": SensorTrustOverride.LOTTERY,
        "qiki sensor lottery": SensorTrustOverride.LOTTERY,
        "qiki body telemetry only": SensorTrustOverride.BLIND,
        "body telemetry only": SensorTrustOverride.BLIND,
        "sensor blind": SensorTrustOverride.BLIND,
        "qiki blind sensors": SensorTrustOverride.BLIND,
        "qiki trust sensors": SensorTrustOverride.AUTO,
        "trust sensors": SensorTrustOverride.AUTO,
        "sensor trust auto": SensorTrustOverride.AUTO,
        "sensor trust clear": SensorTrustOverride.AUTO,
        "sensor trust reset": SensorTrustOverride.AUTO,
    }
    if command in command_map:
        return command_map[command]
    for prefix in ("sensor trust ", "qiki sensor trust "):
        if command.startswith(prefix):
            value = command.removeprefix(prefix).strip()
            if value in {"", "status", "state", "map", "help"}:
                return None
            return normalize_sensor_trust_override(value)
    return None


def is_sensor_trust_status_command(raw_command: str) -> bool:
    command = str(raw_command or "").strip().lower()
    return command in {"sensor trust", "sensors trust", "qiki sensor trust", "qiki sensors trust", "sensor evidence"}


def _snapshot(
    state: SensorTrustState,
    *,
    evidence: list[str],
    reason_ru: str,
    confidence: float,
    source_path: str = "sensor_trust_model",
) -> SensorTrustSnapshot:
    normalized_conf = min(1.0, max(0.0, float(confidence)))
    compact_evidence = tuple(str(item).strip() for item in evidence if str(item).strip())
    return SensorTrustSnapshot(
        state=state,
        confidence=normalized_conf,
        reason_ru=reason_ru,
        evidence=compact_evidence,
        source_path=source_path,
    )


def _reason_for_state(state: SensorTrustState) -> str:
    return {
        SensorTrustState.TRUSTED: "runtime явно пометил сенсорный контур как trusted",
        SensorTrustState.DEGRADED: "runtime явно пометил сенсорный контур как degraded",
        SensorTrustState.CONFLICTING: "runtime явно пометил сенсорный контур как conflicting",
        SensorTrustState.LOTTERY: "runtime/anomaly явно пометил сенсорный контур как lottery",
        SensorTrustState.BLIND: "runtime явно пометил контур как blind/body-only",
    }[state]


def _explicit_confidence(tel: Mapping[str, Any], state: SensorTrustState) -> float:
    value = _first_number(_get(tel, "sensor_trust", "confidence"), _get(tel, "sensor_confidence"))
    if value is not None:
        return value
    return {
        SensorTrustState.TRUSTED: 0.9,
        SensorTrustState.DEGRADED: 0.55,
        SensorTrustState.CONFLICTING: 0.35,
        SensorTrustState.LOTTERY: 0.18,
        SensorTrustState.BLIND: 0.40,
    }[state]


def _explicit_state(tel: Mapping[str, Any]) -> SensorTrustState | None:
    raw = _pick_text(
        tel,
        ("sensor_trust", "state"),
        ("sensor_trust", "mode"),
        ("sensor_trust", "trust"),
        ("sensor_trust_state",),
        ("sensor_mode",),
        ("anomaly", "sensor_trust"),
    )
    if not raw:
        return None
    normalized = raw.strip().lower().replace(" ", "_")
    return _EXPLICIT_STATE_ALIASES.get(normalized)


def _looks_lottery_from_events_or_text(
    tel: Mapping[str, Any],
    incidents: Sequence[Mapping[str, Any]] | None,
) -> bool:
    fields = [
        _pick_text(tel, ("anomaly", "state"), ("anomaly", "kind"), ("environment", "anomaly")),
        _pick_text(tel, ("sim_state", "anomaly"), ("sim_state", "causality")),
    ]
    for item in fields:
        if _contains_any(item, ("lottery", "uncertain", "causal", "anomaly", "jet", "radiation storm")):
            return True
    for incident in incidents or ():
        joined = " ".join(str(value) for value in incident.values())
        if _contains_any(joined, ("lottery", "sensor trust", "сенсоры", "radiation", "джет", "causal")):
            return True
    return False


def _is_lottery_radiation(radiation_usvh: float | None, radiation_status: str) -> bool:
    if radiation_usvh is not None and radiation_usvh >= 5000.0:
        return True
    return _contains_any(radiation_status, ("critical", "crit", "severe", "storm", "anomaly", "крит", "шторм"))


def _conflict_markers(tel: Mapping[str, Any], *, sensor_plane: Mapping[str, Any], track_count: int) -> list[str]:
    explicit = _pick_text(
        tel,
        ("sensor_conflict",),
        ("sensor_plane", "conflict"),
        ("sensor_plane", "contradiction"),
    )
    markers: list[str] = []
    if explicit and explicit.lower() not in {"false", "0", "none", "no"}:
        markers.append(f"explicit conflict={explicit}")

    star_locked = _first_bool(_get(sensor_plane, "star_tracker", "locked"), _get(sensor_plane, "star_tracker", "ok"))
    attitude_present = _get(tel, "attitude") is not None or _get(sensor_plane, "imu") is not None
    if star_locked is False and attitude_present:
        markers.append("attitude present while star tracker reports unlocked")

    radar_status = _status_text(_get(sensor_plane, "radar_360", "status"), _get(tel, "radar", "status"))
    if track_count and radar_status and _status_is_bad(radar_status):
        markers.append("radar has tracks while radar status is bad")
    return markers


def _sensor_status_markers(sensor_plane: Mapping[str, Any], subsystem: Any) -> dict[str, list[str]]:
    markers = {"bad": [], "off": [], "good": []}
    for sensor_id, sensor_data in sensor_plane.items():
        if not isinstance(sensor_data, Mapping):
            continue
        status = _status_text(sensor_data.get("status"), sensor_data.get("state"), sensor_data.get("mode"))
        _add_status_marker(markers, f"sensor_plane.{sensor_id}", status)
    for field in getattr(subsystem, "fields", ()) or ():
        key = str(getattr(field, "key", ""))
        if not (key.startswith("sensors.") and key.endswith(".status")):
            continue
        status = _status_text(getattr(field, "value", None))
        _add_status_marker(markers, key, status)
    return markers


def _add_status_marker(markers: dict[str, list[str]], label: str, status: str) -> None:
    if not status:
        return
    if _status_is_off(status):
        markers["off"].append(f"{label}={status}")
    elif _status_is_bad(status):
        markers["bad"].append(f"{label}={status}")
    elif _status_is_good(status):
        markers["good"].append(f"{label}={status}")


def _body_only_mode(tel: Mapping[str, Any], *, off_markers: Sequence[str]) -> bool:
    raw = _pick_text(tel, ("sensor_mode",), ("sensor_plane", "mode"), ("guidance", "sensor_mode"))
    if _contains_any(raw, ("body_only", "body-only", "blind", "external_off", "корпус")):
        return True
    return bool(off_markers) and _contains_any(" ".join(off_markers), ("external", "radar", "lidar", "star_tracker"))


def _confidence_values(tel: Mapping[str, Any], sensor_plane: Mapping[str, Any], subsystem: Any) -> list[float]:
    values: list[float] = []
    for path in (
        ("radar", "confidence"),
        ("sensor_trust", "confidence"),
        ("sensor_confidence",),
    ):
        value = _first_number(_get(tel, *path))
        if value is not None:
            values.append(value)
    for sensor_data in sensor_plane.values():
        if not isinstance(sensor_data, Mapping):
            continue
        value = _first_number(sensor_data.get("confidence"), sensor_data.get("quality"))
        if value is not None:
            values.append(value)
    for field in getattr(subsystem, "fields", ()) or ():
        key = str(getattr(field, "key", ""))
        if key.endswith(".confidence") or key.endswith(".quality"):
            value = _first_number(getattr(field, "value", None))
            if value is not None:
                values.append(value)
    return [value for value in values if 0.0 <= value <= 1.0]


def _average_confidence(values: Sequence[float], *, fallback: float) -> float:
    if not values:
        return fallback
    return sum(values) / len(values)


def _track_count(radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None) -> int:
    if radar_tracks is None:
        return 0
    if isinstance(radar_tracks, Mapping):
        return len(radar_tracks)
    if isinstance(radar_tracks, Sequence) and not isinstance(radar_tracks, (str, bytes)):
        return len(radar_tracks)
    return 0


def _subsystem(hardware_model: Any | None, subsystem_id: str) -> Any | None:
    subsystems = getattr(hardware_model, "subsystems", None)
    if isinstance(subsystems, Mapping):
        return subsystems.get(subsystem_id)
    return None


def _subsystem_has_values(subsystem: Any | None) -> bool:
    if subsystem is None:
        return False
    for field in getattr(subsystem, "fields", ()) or ():
        value = getattr(field, "value", None)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text and text not in {"нет данных", "none", "null", "unknown", "n/a"}:
            return True
    return False


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(source: Any, *path: str) -> Any:
    current = source
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _pick_text(source: Mapping[str, Any], *paths: tuple[str, ...]) -> str:
    for path in paths:
        value = _get(source, *path)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _status_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip().lower()
        if text:
            return text
    return ""


def _status_is_bad(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in _BAD_STATUSES or any(token in normalized for token in _BAD_STATUSES)


def _status_is_off(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in _OFF_STATUSES or any(token in normalized for token in _OFF_STATUSES)


def _status_is_good(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in _GOOD_STATUSES or any(token in normalized for token in _GOOD_STATUSES)


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    normalized = str(text or "").strip().lower()
    return any(str(needle).lower() in normalized for needle in needles)


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            continue
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
        if value is None:
            continue
        text = str(value).strip().lower()
        if text in {"true", "yes", "1", "locked", "ok", "healthy"}:
            return True
        if text in {"false", "no", "0", "unlocked", "lost", "failed"}:
            return False
    return None


__all__ = [
    "SensorTrustOverride",
    "SensorTrustSnapshot",
    "SensorTrustState",
    "assess_sensor_trust",
    "build_sensor_trust_snapshot",
    "is_sensor_trust_status_command",
    "parse_sensor_trust_command",
    "render_sensor_trust_evidence_lines",
    "render_sensor_trust_summary_lines",
    "sensor_trust_command_help_lines",
    "sensor_trust_evidence_lines",
    "sensor_trust_f2_lines",
    "sensor_trust_provider_context_lines",
    "sensor_trust_qiki_hint",
    "sensor_trust_qiki_reaction_lines",
    "sensor_trust_status_line",
]
