from __future__ import annotations

import json
from hashlib import sha256
from typing import Any


def _stable_json_bytes(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return raw.encode("utf-8")


def canonical_hardware_profile_payload(bot_config: dict[str, Any]) -> dict[str, Any]:
    """
    Return the canonical payload used for `hardware_profile_hash`.

    Policy (no duplicates):
    - hash only the "hardware profile" subset of bot_config.json (not runtime noise).
    - currently includes:
      - hardware_profile
      - hardware_manifest
    """

    hp = bot_config.get("hardware_profile") if isinstance(bot_config, dict) else None
    manifest = bot_config.get("hardware_manifest") if isinstance(bot_config, dict) else None
    return {
        "hardware_profile": hp if isinstance(hp, dict) else {},
        "hardware_manifest": manifest if isinstance(manifest, (dict, list)) else {},
    }


def compute_hardware_profile_hash(bot_config: dict[str, Any]) -> str:
    """
    Compute deterministic hardware profile hash.

    Format: sha256:<64 hex>
    """

    payload = canonical_hardware_profile_payload(bot_config)
    digest = sha256(_stable_json_bytes(payload)).hexdigest()
    return f"sha256:{digest}"

