from __future__ import annotations

from datetime import datetime, timezone
from collections import deque
from typing import Any, Deque


class BoundedEventsStore:
    """Keep only the most recent N events for ORION V views."""

    def __init__(self, max_events: int = 500) -> None:
        self._max_events = max(1, int(max_events))
        self._events: Deque[dict[str, Any]] = deque(maxlen=self._max_events)

    @property
    def max_events(self) -> int:
        return self._max_events

    def append(self, event: dict[str, Any]) -> None:
        self._events.append(event)

    def last(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return list(self._events)[-limit:]

    def count(self) -> int:
        return len(self._events)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._events)

    def query(
        self,
        *,
        limit: int,
        offset: int = 0,
        severities: set[str] | None = None,
        subsystem: str | None = None,
        since_epoch_s: float | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        if offset < 0:
            offset = 0

        filtered: list[dict[str, Any]] = []
        skipped = 0
        subsystem_norm = (subsystem or "").strip().lower()
        severities_norm = {sev.upper() for sev in severities} if severities else set()

        for event in reversed(self._events):
            if severities_norm:
                event_severity = _normalize_severity(_event_payload(event).get("severity"))
                if event_severity not in severities_norm:
                    continue
            if subsystem_norm:
                event_subsystem = _event_subsystem(event)
                if event_subsystem != subsystem_norm:
                    continue
            if since_epoch_s is not None:
                event_epoch_s = _event_timestamp_s(event)
                if event_epoch_s is None or event_epoch_s < since_epoch_s:
                    continue

            if skipped < offset:
                skipped += 1
                continue
            filtered.append(event)
            if len(filtered) >= limit:
                break

        return filtered

    def query_count(
        self,
        *,
        severities: set[str] | None = None,
        subsystem: str | None = None,
        since_epoch_s: float | None = None,
    ) -> int:
        total = 0
        subsystem_norm = (subsystem or "").strip().lower()
        severities_norm = {sev.upper() for sev in severities} if severities else set()
        for event in self._events:
            if severities_norm:
                event_severity = _normalize_severity(_event_payload(event).get("severity"))
                if event_severity not in severities_norm:
                    continue
            if subsystem_norm and _event_subsystem(event) != subsystem_norm:
                continue
            if since_epoch_s is not None:
                event_epoch_s = _event_timestamp_s(event)
                if event_epoch_s is None or event_epoch_s < since_epoch_s:
                    continue
            total += 1
        return total

    def active_incidents(self) -> list[dict[str, str]]:
        latest_by_id: dict[str, dict[str, str]] = {}
        for event in reversed(self._events):
            payload = _event_payload(event)
            if not isinstance(payload, dict):
                continue
            if bool(payload.get("acked", False)):
                continue
            sev = _normalize_severity(payload.get("severity"))
            if sev not in {"C", "A"}:
                continue
            incident_id = str(
                payload.get("incident_id")
                or payload.get("incident_key")
                or payload.get("id")
                or event.get("subject")
                or "incident"
            )
            description = str(
                payload.get("description")
                or payload.get("message")
                or payload.get("title")
                or payload.get("type")
                or "Без описания"
            )
            if incident_id not in latest_by_id:
                latest_by_id[incident_id] = {"severity": sev, "id": incident_id, "description": description}
        return list(latest_by_id.values())

    def mark_acknowledged(self, incident_id: str) -> bool:
        target = incident_id.strip()
        if not target:
            return False
        changed = False
        updated_events: list[dict[str, Any]] = []
        for event in self._events:
            payload = event.get("data") if isinstance(event, dict) else None
            event_id = _incident_id_from_event(event)
            if isinstance(payload, dict) and event_id == target and not bool(payload.get("acked", False)):
                payload_copy = dict(payload)
                payload_copy["acked"] = True
                event_copy = dict(event)
                event_copy["data"] = payload_copy
                updated_events.append(event_copy)
                changed = True
                continue
            updated_events.append(event)
        if changed:
            self._events = deque(updated_events, maxlen=self._max_events)
        return changed

    def clear_acknowledged(self) -> int:
        kept_events: list[dict[str, Any]] = []
        cleared_incidents: set[str] = set()
        for event in self._events:
            payload = event.get("data") if isinstance(event, dict) else None
            event_id = _incident_id_from_event(event)
            if isinstance(payload, dict) and bool(payload.get("acked", False)) and event_id:
                cleared_incidents.add(event_id)
                continue
            kept_events.append(event)
        if cleared_incidents:
            self._events = deque(kept_events, maxlen=self._max_events)
        return len(cleared_incidents)


def _normalize_severity(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if not text:
        return ""
    if text.startswith("C") or text in {"CRIT", "CRITICAL", "ERROR"}:
        return "C"
    if text.startswith("A") or text in {"ALARM", "WARN", "WARNING"}:
        return "A"
    return text


def _incident_id_from_event(event: dict[str, Any]) -> str:
    payload = _event_payload(event)
    if not isinstance(payload, dict):
        return ""
    return str(
        payload.get("incident_id") or payload.get("incident_key") or payload.get("id") or event.get("subject") or ""
    )


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("data") if isinstance(event, dict) else None
    if isinstance(payload, dict):
        return payload
    return {}


def _event_subsystem(event: dict[str, Any]) -> str:
    payload = _event_payload(event)
    subsystem = payload.get("subsystem")
    if isinstance(subsystem, str) and subsystem.strip():
        return subsystem.strip().lower()
    subject = str(event.get("subject") or "").strip().lower()
    if not subject:
        return ""
    if subject.startswith("qiki.events.v1."):
        remainder = subject[len("qiki.events.v1.") :]
        return remainder.split(".", 1)[0]
    return subject.split(".", 1)[0]


def _event_timestamp_s(event: dict[str, Any]) -> float | None:
    payload = _event_payload(event)

    for key in ("ts_unix_s", "timestamp_unix_s"):
        val = payload.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
    for key in ("ts_unix_ms", "timestamp_unix_ms"):
        val = payload.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val) / 1000.0

    stamp = payload.get("timestamp") or event.get("timestamp")
    if isinstance(stamp, str) and stamp.strip():
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        return float(stamp)
    return None


def now_epoch_s() -> float:
    return datetime.now(tz=timezone.utc).timestamp()
