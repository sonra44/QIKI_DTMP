"""CloudEvents helper utilities for NATS/JetStream publishing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def format_rfc3339(ts: datetime) -> str:
    """Return timestamp formatted per RFC3339 with trailing Z for UTC."""

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    # Use timespec=milliseconds for compactness, drop trailing +00:00
    return ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_cloudevent_headers(
    *,
    event_id: str,
    event_type: str,
    source: str,
    event_time: datetime,
    datacontenttype: str = "application/json",
) -> Dict[str, str]:
    """Construct minimal set of CloudEvents 1.0 headers."""

    return {
        "ce_specversion": "1.0",
        "ce_id": event_id,
        "ce_type": event_type,
        "ce_source": source,
        "ce_time": format_rfc3339(event_time),
        "ce_datacontenttype": datacontenttype,
    }
