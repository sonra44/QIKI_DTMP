from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any


def _is_nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_bios_status_payload(payload: dict[str, Any], expected_subject: str) -> tuple[bool, str]:
    if payload.get("event_schema_version") != 1:
        return False, f"event_schema_version != 1: {payload.get('event_schema_version')}"

    if not _is_nonempty_str(payload.get("source")):
        return False, f"missing/invalid source: {payload.get('source')}"

    if payload.get("subject") != expected_subject:
        return False, f"subject mismatch: expected={expected_subject!r} got={payload.get('subject')!r}"

    if not _is_nonempty_str(payload.get("timestamp")):
        return False, f"missing/invalid timestamp: {payload.get('timestamp')}"

    if not _is_nonempty_str(payload.get("bios_version")):
        return False, f"missing/invalid bios_version: {payload.get('bios_version')}"

    if not _is_nonempty_str(payload.get("firmware_version")):
        return False, f"missing/invalid firmware_version: {payload.get('firmware_version')}"

    hp = payload.get("hardware_profile_hash")
    if hp is not None and not _is_nonempty_str(hp):
        return False, f"invalid hardware_profile_hash: {hp}"

    rows = payload.get("post_results")
    if not isinstance(rows, list):
        return False, f"missing/invalid post_results list: {rows}"

    statuses: list[int] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"post_results[{idx}] is not an object: {row}"
        if not _is_nonempty_str(row.get("device_id")):
            return False, f"post_results[{idx}] missing/invalid device_id: {row.get('device_id')}"
        if not _is_nonempty_str(row.get("device_name")):
            return False, f"post_results[{idx}] missing/invalid device_name: {row.get('device_name')}"
        status = row.get("status")
        if not isinstance(status, int) or status not in (0, 1, 2, 3):
            return False, f"post_results[{idx}] invalid status (expected 0..3 int): {status}"
        statuses.append(status)
        sm = row.get("status_message")
        if sm is not None and not isinstance(sm, str):
            return False, f"post_results[{idx}] invalid status_message (expected str|null): {sm}"

    # Consistency check if all_systems_go присутствует в payload.
    asg = payload.get("all_systems_go")
    if asg is not None:
        if not isinstance(asg, bool):
            return False, f"invalid all_systems_go (expected bool): {asg}"
        computed = bool(statuses) and all(s == 1 for s in statuses)
        if asg != computed:
            return False, f"all_systems_go mismatch: got={asg} computed={computed}"

    return True, "ok"


async def main() -> int:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    subject = os.getenv("BIOS_STATUS_SUBJECT", "qiki.events.v1.bios_status")
    timeout_s = float(os.getenv("BIOS_STATUS_SMOKE_TIMEOUT_SEC", "5.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=5)
    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            got.set_result(json.loads(msg.data.decode("utf-8")))
        except Exception:
            got.set_result({"raw": msg.data.decode("utf-8", errors="replace")})

    sub = await nc.subscribe(subject, cb=handler)
    try:
        payload = await asyncio.wait_for(got, timeout=timeout_s)
        if not isinstance(payload, dict):
            print(f"BAD: bios status payload is not a dict on {subject}: {payload}")
            return 1
        ok, reason = _validate_bios_status_payload(payload, expected_subject=subject)
        if not ok:
            print(f"BAD: bios status contract violation on {subject}: {reason}; payload={payload}")
            return 1
        print(f"OK: received bios status on {subject}: {payload}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no bios status on {subject} within {timeout_s}s")
        return 1
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            print("WARN: bios_status_smoke unsubscribe failed", file=sys.stderr)
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
