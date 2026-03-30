from __future__ import annotations

from typing import Any

from .types import HardwareViewModel, ViewStatus


def compute_field_coverage(model: HardwareViewModel) -> dict[str, tuple[int, int]]:
    coverage: dict[str, tuple[int, int]] = {}
    for subsystem_id, subsystem in model.subsystems.items():
        total = len(subsystem.fields)
        filled = sum(1 for field in subsystem.fields if field.status is not ViewStatus.NO_DATA)
        coverage[subsystem_id] = (filled, total)
    return coverage


def compute_missing_keys(
    snapshot_canon: dict[str, Any], subsystem_keysets: dict[str, set[str]]
) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for subsystem, keys in subsystem_keysets.items():
        missing[subsystem] = sorted(
            key for key in keys if _get_value(snapshot_canon, key) is None
        )
    return missing


def format_coverage_line(coverage: dict[str, tuple[int, int]]) -> str:
    payload = " ".join(
        f"{subsystem_id} {filled}/{total}"
        for subsystem_id, (filled, total) in sorted(coverage.items())
    )
    return f"HWM coverage: {payload}"


def format_missing_line(subsystem: str, missing_keys: list[str]) -> str:
    if not missing_keys:
        return f"HWM missing({subsystem}): -"
    return f"HWM missing({subsystem}): {', '.join(missing_keys)}"


def _get_value(snapshot: dict[str, Any], dotted_key: str) -> Any:
    if dotted_key in snapshot:
        return snapshot[dotted_key]
    current: Any = snapshot
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
