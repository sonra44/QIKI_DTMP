"""Единая точка auth-кредов NATS (M2, F5 design §6).

Креды живут ТОЛЬКО в окружении (NATS_USER/NATS_PASSWORD или NATS_TOKEN)
и передаются отдельными kwargs в nats.connect()/NatsBroker().
В NATS_URL креды не кладём никогда: URL попадает в логи и UI консоли.

Пустое окружение -> пустой dict -> поведение идентично доб-M2 (auth off).
"""

from __future__ import annotations

import os
from typing import Any


def nats_auth_kwargs() -> dict[str, Any]:
    """Auth-kwargs для nats.connect()/NatsBroker() из окружения.

    Приоритет: NATS_TOKEN, затем пара NATS_USER+NATS_PASSWORD.
    Неполная пара (только user или только password) игнорируется.
    """
    token = os.getenv("NATS_TOKEN", "").strip()
    if token:
        return {"token": token}
    user = os.getenv("NATS_USER", "").strip()
    password = os.getenv("NATS_PASSWORD", "").strip()
    if user and password:
        return {"user": user, "password": password}
    return {}
