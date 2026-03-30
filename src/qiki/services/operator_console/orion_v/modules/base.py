from __future__ import annotations

from typing import Any, Protocol


class SubsystemModule(Protocol):
    """Contract for pluggable subsystem views in ORION V."""

    slug: str
    title: str

    def render_summary(self, state: dict[str, Any]) -> str:
        """Return one-line summary used by F2 Systems list."""

    def render_details(self, state: dict[str, Any]) -> str:
        """Return multiline details for focused subsystem."""

    def sources_of_truth(self) -> tuple[str, ...]:
        """Return telemetry keys/paths used by this module."""
