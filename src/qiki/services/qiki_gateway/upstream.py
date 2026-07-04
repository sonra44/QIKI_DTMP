"""Форвард к реальному провайдеру. Вынесено отдельно для подмены в тестах."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict

# Тип форвардера: (url, headers, body_bytes, timeout_s) -> (status, response_bytes)
Forwarder = Callable[[str, Dict[str, str], bytes, float], "tuple[int, bytes]"]


def http_forward(url: str, headers: Dict[str, str], body: bytes, timeout_s: float) -> "tuple[int, bytes]":
    request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def as_json(body: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
