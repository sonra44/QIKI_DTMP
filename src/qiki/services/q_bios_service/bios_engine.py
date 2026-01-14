from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from qiki.shared.models.core import BiosStatus, DeviceStatus, DeviceStatusEnum

from qiki.services.q_bios_service.health_checker import SimHealthResult


@dataclass(frozen=True, slots=True)
class BiosPostInputs:
    bot_config_path: str
    sim_health: SimHealthResult


def _flatten_manifest(manifest: Any) -> Iterable[dict[str, Any]]:
    if isinstance(manifest, dict):
        if "id" in manifest and "type" in manifest and isinstance(manifest.get("id"), str):
            yield manifest  # single device-like dict
        for v in manifest.values():
            yield from _flatten_manifest(v)
    elif isinstance(manifest, list):
        for v in manifest:
            yield from _flatten_manifest(v)


def _device_rows_from_bot_config(bot_config: dict[str, Any]) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []

    hp = bot_config.get("hardware_profile") if isinstance(bot_config, dict) else None
    if isinstance(hp, dict):
        for key in ("sensors", "actuators"):
            items = hp.get(key)
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    did = item.get("id")
                    dtype = item.get("type")
                    if isinstance(did, str) and did.strip() and isinstance(dtype, str) and dtype.strip():
                        devices.append((did.strip(), dtype.strip()))

    manifest = bot_config.get("hardware_manifest") if isinstance(bot_config, dict) else None
    for item in _flatten_manifest(manifest):
        did = item.get("id")
        dtype = item.get("type")
        if isinstance(did, str) and did.strip() and isinstance(dtype, str) and dtype.strip():
            devices.append((did.strip(), dtype.strip()))

    # Deduplicate while keeping order
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for row in devices:
        if row in seen:
            continue
        seen.add(row)
        out.append(row)
    return out


def build_bios_status(inputs: BiosPostInputs) -> BiosStatus:
    path = Path(inputs.bot_config_path)
    try:
        raw = path.read_text(encoding="utf-8")
        bot_config = json.loads(raw)
    except Exception as e:
        # No-mocks: don't fabricate devices; emit a single explicit error row.
        return BiosStatus(
            bios_version="virtual_bios_mvp",
            firmware_version="virtual_bios_mvp",
            post_results=[
                DeviceStatus(
                    device_id="bot_config",
                    device_name="bot_config.json",
                    status=DeviceStatusEnum.ERROR,
                    status_message=f"Cannot read/parse bot_config.json: {e}",
                )
            ],
        )

    rows = _device_rows_from_bot_config(bot_config if isinstance(bot_config, dict) else {})
    post_results: list[DeviceStatus] = []

    # If simulation health is down, reflect it explicitly (no-mocks).
    if not inputs.sim_health.ok:
        post_results.append(
            DeviceStatus(
                device_id="q-sim-service",
                device_name="Q-Sim Service",
                status=DeviceStatusEnum.ERROR,
                status_message=f"HealthCheck failed: {inputs.sim_health.message}",
            )
        )

    if not rows:
        post_results.append(
            DeviceStatus(
                device_id="hardware_profile",
                device_name="hardware profile",
                status=DeviceStatusEnum.ERROR,
                status_message="No devices found in bot_config.json (hardware_profile/hardware_manifest).",
            )
        )
    else:
        degraded = not inputs.sim_health.ok
        for device_id, device_type in rows:
            post_results.append(
                DeviceStatus(
                    device_id=device_id,
                    device_name=device_type,
                    status=DeviceStatusEnum.DEGRADED if degraded else DeviceStatusEnum.OK,
                    status_message="Simulation health degraded" if degraded else "OK",
                )
            )

    return BiosStatus(
        bios_version=str(bot_config.get("schema_version") or "virtual_bios_mvp"),
        firmware_version="virtual_bios_mvp",
        post_results=post_results,
    )

