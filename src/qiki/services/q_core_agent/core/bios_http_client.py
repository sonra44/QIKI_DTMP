from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import urlopen

from qiki.services.q_core_agent.core.agent_logger import logger
from qiki.shared.models.core import BiosStatus


def fetch_bios_status() -> BiosStatus:
    base = (os.getenv("BIOS_URL", "http://q-bios-service:8080") or "").rstrip("/")
    url = f"{base}/bios/status"
    timeout_s = float(os.getenv("BIOS_HTTP_TIMEOUT_SEC", "2.0"))
    try:
        with urlopen(url, timeout=timeout_s) as resp:
            raw = resp.read()
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict):
            return BiosStatus.model_validate(payload)
        raise ValueError("BIOS payload is not a JSON object")
    except Exception as e:
        logger.warning("BIOS unavailable (%s): %s", url, e)
        return BiosStatus(bios_version="unavailable", firmware_version="unavailable", post_results=[])

