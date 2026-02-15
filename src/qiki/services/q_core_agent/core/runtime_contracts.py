"""Shared runtime contract helpers for strict mode and event envelopes."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

EVENT_SCHEMA_VERSION = 1
TRUTH_STATES = frozenset({"OK", "NO_DATA", "FALLBACK", "INVALID"})
EXPORT_ENVELOPE_KEYS = (
    "schema_version",
    "ts",
    "subsystem",
    "event_type",
    "truth_state",
    "reason",
    "payload",
    "session_id",
)


def is_enabled(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def resolve_strict_mode(
    env: Mapping[str, str],
    *,
    legacy_keys: tuple[str, ...] = (),
    default: bool = False,
) -> bool:
    if "QIKI_STRICT_MODE" in env:
        return is_enabled(env.get("QIKI_STRICT_MODE"), default=default)
    for key in legacy_keys:
        if key in env:
            return is_enabled(env.get(key), default=default)
    return default


def normalize_truth_state(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in TRUTH_STATES:
        return normalized
    return "INVALID"


def build_export_envelope(
    *,
    ts: Any,
    subsystem: Any,
    event_type: Any,
    truth_state: Any,
    reason: Any,
    payload: Any,
    session_id: Any = "",
) -> dict[str, Any]:
    return {
        "schema_version": int(EVENT_SCHEMA_VERSION),
        "ts": float(ts),
        "subsystem": str(subsystem),
        "event_type": str(event_type),
        "truth_state": normalize_truth_state(truth_state),
        "reason": str(reason or ""),
        "payload": payload if isinstance(payload, dict) else {},
        "session_id": str(session_id or ""),
    }


def validate_export_envelope(envelope: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in EXPORT_ENVELOPE_KEYS:
        if key not in envelope:
            errors.append(f"missing key: {key}")

    schema_version = envelope.get("schema_version")
    if schema_version != EVENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EVENT_SCHEMA_VERSION}")

    ts = envelope.get("ts")
    if not isinstance(ts, (int, float)):
        errors.append("ts must be numeric")

    for key in ("subsystem", "event_type", "reason", "session_id"):
        value = envelope.get(key)
        if not isinstance(value, str):
            errors.append(f"{key} must be string")

    truth_state = envelope.get("truth_state")
    if normalize_truth_state(truth_state) != str(truth_state or "").strip().upper():
        errors.append(f"truth_state must be one of {sorted(TRUTH_STATES)}")

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        errors.append("payload must be object")
    return errors


def ensure_truth_reason(envelope: MutableMapping[str, Any]) -> None:
    truth_state = str(envelope.get("truth_state", "")).upper()
    reason = str(envelope.get("reason", "")).strip()
    if truth_state in {"NO_DATA", "FALLBACK", "INVALID"} and not reason:
        envelope["reason"] = truth_state
