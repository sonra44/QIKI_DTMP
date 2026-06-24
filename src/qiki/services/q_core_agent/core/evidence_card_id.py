"""Shared ORION evidence-card id contract.

This module lives in core so runtime decisions can reference the id format
without importing the operator-console projection layer.
"""

from __future__ import annotations

EVIDENCE_CARD_ID_FORMAT = "card:{event_id}"


def make_evidence_card_id(event_id: str) -> str:
    return EVIDENCE_CARD_ID_FORMAT.format(event_id=str(event_id or ""))
