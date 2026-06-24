"""IF-BLACKBOX-001 (§21) read-only ORION recovery surface of a blackbox record.

§21.6 target-only: the canon explicitly states "describing blackbox relevance does not mean
blackbox already writes". REQ (P0): ORION must mark target-only/not-implemented, never present
as runtime-ready. So a detected trigger is never shown as recorded unless a real store record
exists. Read-only; never writes, stores, or persists anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Reasons that mean nothing was actually persisted -> a recorded claim cannot be honored.
_NOT_RECORDED_REASONS = ("BLACKBOX_NOT_RECORDED", "BLACKBOX_TARGET_ONLY")
_ABSENT = ("", "missing", "target-only", "not_recorded", "none")
_SNAPSHOT_FIELDS = (
    "body_state_snapshot",
    "power_snapshot",
    "thermal_snapshot",
    "motion_snapshot",
    "sensor_snapshot",
)


@dataclass(frozen=True, slots=True)
class BlackboxEvidence:
    record_id: str
    trigger_event: str
    severity: str
    recorded_state: str
    is_recorded: bool
    trigger_detected: bool
    available_snapshots: tuple[str, ...]
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) > 0
    return str(value).strip().lower() not in _ABSENT


def blackbox_to_evidence(record: Any) -> BlackboxEvidence:
    """Read-only ORION projection of one BlackboxRecord (§21)."""
    recorded_state = _text(record.recorded_state, "not_recorded")
    trigger_event = _text(record.trigger_event, "missing")
    reason_codes = tuple(record.reason_codes or ())
    trigger_detected = trigger_event.lower() not in _ABSENT
    # Defensive: honor "recorded" only with a real recorded_state and no not-recorded reason.
    is_recorded = recorded_state == "recorded" and not any(r in _NOT_RECORDED_REASONS for r in reason_codes)
    available_snapshots = tuple(
        name for name in _SNAPSHOT_FIELDS if _present(getattr(record, name, None))
    )
    if is_recorded:
        operator_text = f"blackbox: trigger '{trigger_event}' recorded (severity {_text(record.severity)})"
    elif trigger_detected:
        operator_text = f"blackbox: trigger '{trigger_event}' detected — NOT recorded (target-only, no store)"
    else:
        operator_text = "blackbox: no trigger (target-only, not recorded)"
    return BlackboxEvidence(
        record_id=str(record.record_id or "missing"),
        trigger_event=trigger_event,
        severity=_text(record.severity),
        recorded_state=recorded_state,
        is_recorded=is_recorded,
        trigger_detected=trigger_detected,
        available_snapshots=available_snapshots,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )
