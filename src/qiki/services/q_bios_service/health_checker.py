from __future__ import annotations

from dataclasses import dataclass

import grpc

from generated.q_sim_api_pb2 import HealthCheckRequest
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub


@dataclass(frozen=True, slots=True)
class SimHealthResult:
    ok: bool
    message: str


def check_qsim_health(*, host: str, port: int, timeout_s: float) -> SimHealthResult:
    address = f"{host}:{int(port)}"
    try:
        channel = grpc.insecure_channel(address)
        stub = QSimAPIServiceStub(channel)
        resp = stub.HealthCheck(HealthCheckRequest(), timeout=float(timeout_s))
        return SimHealthResult(ok=True, message=str(getattr(resp, "message", "") or "ok"))
    except Exception as e:
        return SimHealthResult(ok=False, message=str(e))

