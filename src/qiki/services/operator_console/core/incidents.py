from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Optional

from qiki.services.operator_console.core.incident_rules import IncidentRulesConfig, IncidentRule


@dataclass
class Incident:
    incident_id: str
    rule_id: str
    title: str
    description: Optional[str]
    key: str
    type: Optional[str]
    source: Optional[str]
    subject: Optional[str]
    severity: str
    state: str
    first_seen: float
    last_seen: float
    count: int
    acked: bool = False
    peak_value: Optional[float] = None
    cleared_at: Optional[float] = None


@dataclass
class PendingIncident:
    first_seen: float
    last_seen: float


class IncidentStore:
    def __init__(self, config: IncidentRulesConfig, *, max_incidents: Optional[int] = None) -> None:
        self._config = config
        self._incidents: dict[str, Incident] = {}
        self._pending: dict[str, PendingIncident] = {}
        self._cooldowns: dict[str, float] = {}
        self._max_incidents = int(max_incidents) if max_incidents is not None else None

    def ingest(self, event: dict[str, Any]) -> list[Incident]:
        matched: list[Incident] = []
        for rule in self._config.rules:
            if not rule.enabled:
                continue
            if not self._match_rule(rule, event):
                continue
            incident = self._apply_rule(rule, event)
            if incident is not None:
                matched.append(incident)
        self._enforce_max_incidents()
        return matched

    def ack(self, incident_id: str) -> bool:
        inc = self._incidents.get(incident_id)
        if not inc:
            return False
        inc.acked = True
        return True

    def get(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def clear(self, incident_id: str) -> bool:
        inc = self._incidents.get(incident_id)
        if not inc:
            return False
        inc.state = "cleared"
        inc.cleared_at = time.time()
        cooldown_s = self._rule_cooldown_s(inc.rule_id)
        if cooldown_s:
            self._cooldowns[inc.key] = time.time() + cooldown_s
        return True

    def clear_acked_cleared(self) -> int:
        removed = 0
        for key in list(self._incidents.keys()):
            inc = self._incidents[key]
            if inc.acked and inc.state == "cleared":
                del self._incidents[key]
                removed += 1
        return removed

    def refresh(self, now: Optional[float] = None) -> None:
        ts = time.time() if now is None else float(now)
        for inc in list(self._incidents.values()):
            rule = self._rule_by_id(inc.rule_id)
            if rule is None:
                continue
            cooldown_s = rule.threshold.cooldown_s if rule.threshold else None
            if rule.auto_clear and cooldown_s:
                if ts - inc.last_seen >= float(cooldown_s):
                    inc.state = "cleared"
                    inc.cleared_at = ts

    def list_incidents(self) -> list[Incident]:
        return list(self._incidents.values())

    def _enforce_max_incidents(self) -> None:
        limit = self._max_incidents
        if limit is None or limit <= 0:
            return
        if len(self._incidents) <= limit:
            return

        # Eviction policy (deterministic):
        # 1) Drop acked+cleared first
        # 2) Then cleared
        # 3) Then acked
        # 4) Finally, oldest by last_seen
        def rank(inc: Incident) -> tuple[int, float]:
            acked = bool(getattr(inc, "acked", False))
            cleared = getattr(inc, "state", "") == "cleared"
            if acked and cleared:
                bucket = 0
            elif cleared:
                bucket = 1
            elif acked:
                bucket = 2
            else:
                bucket = 3
            last_seen = float(getattr(inc, "last_seen", 0.0) or 0.0)
            return (bucket, last_seen)

        to_remove = len(self._incidents) - limit
        candidates = sorted(self._incidents.values(), key=rank)
        for inc in candidates[:to_remove]:
            self._incidents.pop(inc.incident_id, None)

    def _apply_rule(self, rule: IncidentRule, event: dict[str, Any]) -> Optional[Incident]:
        ts = self._event_ts(event)
        key = self._incident_key(rule, event)

        cooldown_until = self._cooldowns.get(key)
        if cooldown_until and ts < cooldown_until:
            return None

        if rule.threshold and rule.threshold.min_duration_s:
            pending = self._pending.get(key)
            if pending is None:
                self._pending[key] = PendingIncident(first_seen=ts, last_seen=ts)
                return None
            if ts - pending.last_seen > float(rule.threshold.min_duration_s):
                self._pending[key] = PendingIncident(first_seen=ts, last_seen=ts)
                return None
            pending.last_seen = ts
            if ts - pending.first_seen < float(rule.threshold.min_duration_s):
                return None
            # promote pending to incident
            first_seen = pending.first_seen
            del self._pending[key]
        else:
            first_seen = ts

        inc = self._incidents.get(key)
        if inc is None:
            inc = Incident(
                incident_id=key,
                rule_id=rule.id,
                title=rule.title,
                description=rule.description,
                key=key,
                type=event.get("type"),
                source=event.get("source"),
                subject=event.get("subject"),
                severity=rule.severity,
                state="active",
                first_seen=first_seen,
                last_seen=ts,
                count=1,
                acked=False,
                peak_value=self._extract_peak(rule, event),
            )
            self._incidents[key] = inc
        else:
            inc.last_seen = ts
            inc.count += 1
            if inc.acked:
                inc.acked = False
            peak = self._extract_peak(rule, event)
            if peak is not None:
                if inc.peak_value is None or peak > inc.peak_value:
                    inc.peak_value = peak
        return inc

    @staticmethod
    def _event_ts(event: dict[str, Any]) -> float:
        ts = event.get("ts_epoch")
        if isinstance(ts, (int, float)):
            return float(ts)
        return time.time()

    @staticmethod
    def _norm(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        token = str(value).strip().lower()
        return token or None

    def _match_rule(self, rule: IncidentRule, event: dict[str, Any]) -> bool:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        def matches(expected: Optional[str], actual: Optional[str]) -> bool:
            if expected is None:
                return True
            return self._norm(expected) == self._norm(actual)

        if not matches(rule.match.type, event.get("type")):
            return False
        if not matches(rule.match.source, event.get("source")):
            return False
        if not matches(rule.match.subject, event.get("subject")):
            return False

        if rule.match.field:
            value = payload.get(rule.match.field)
            if rule.threshold:
                return self._compare(rule.threshold.op, value, rule.threshold.value)
            return value is not None

        if rule.threshold:
            return self._compare(rule.threshold.op, payload.get("value"), rule.threshold.value)

        return True

    @staticmethod
    def _compare(op: str, actual: Any, expected: float) -> bool:
        if not isinstance(actual, (int, float)):
            return False
        value = float(actual)
        if op == ">":
            return value > expected
        if op == ">=":
            return value >= expected
        if op == "<":
            return value < expected
        if op == "<=":
            return value <= expected
        if op == "=":
            return value == expected
        if op == "!=":
            return value != expected
        return False

    def _incident_key(self, rule: IncidentRule, event: dict[str, Any]) -> str:
        parts = [rule.id]
        for key in ("type", "source", "subject"):
            value = event.get(key)
            if value is None:
                continue
            token = str(value).strip()
            if token:
                parts.append(token)
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if isinstance(payload, dict):
            optional_code = payload.get("code") or payload.get("id")
            if optional_code:
                parts.append(str(optional_code).strip())
        return "|".join(parts)

    def _extract_peak(self, rule: IncidentRule, event: dict[str, Any]) -> Optional[float]:
        if not rule.match.field:
            return None
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if not isinstance(payload, dict):
            return None
        value = payload.get(rule.match.field)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _rule_by_id(self, rule_id: str) -> Optional[IncidentRule]:
        for rule in self._config.rules:
            if rule.id == rule_id:
                return rule
        return None

    def _rule_cooldown_s(self, rule_id: str) -> Optional[float]:
        rule = self._rule_by_id(rule_id)
        if rule and rule.threshold:
            return rule.threshold.cooldown_s
        return None
