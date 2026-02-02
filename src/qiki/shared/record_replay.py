from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal


RecordLineType = Literal["telemetry", "event", "unknown"]


@dataclass(frozen=True)
class RecordLine:
    schema_version: int
    type: RecordLineType
    ts_epoch: float
    subject: str
    data: Any

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": int(self.schema_version),
                "type": self.type,
                "ts_epoch": float(self.ts_epoch),
                "subject": self.subject,
                "data": self.data,
            },
            ensure_ascii=False,
        )


def _infer_type(subject: str) -> RecordLineType:
    s = str(subject or "")
    if s == "qiki.telemetry":
        return "telemetry"
    if s.startswith("qiki.events.v1."):
        return "event"
    return "unknown"


def _extract_ts_epoch(subject: str, payload: Any) -> float:
    if isinstance(payload, dict) and payload.get("ts_epoch") is not None:
        try:
            return float(payload.get("ts_epoch"))
        except Exception:
            return float(time.time())

    if subject == "qiki.telemetry" and isinstance(payload, dict) and payload.get("ts_unix_ms") is not None:
        try:
            return float(payload.get("ts_unix_ms")) / 1000.0
        except Exception:
            return float(time.time())

    return float(time.time())


async def record_jsonl(
    *,
    nats_url: str,
    subjects: Iterable[str],
    duration_s: float,
    output_path: str | Path,
) -> dict[str, Any]:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"nats import failed: {exc}") from exc

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nc = await nats.connect(servers=[nats_url], connect_timeout=2)
    started = asyncio.get_running_loop().time()

    counts = {"telemetry": 0, "event": 0, "unknown": 0, "total": 0}

    fh = out_path.open("w", encoding="utf-8")

    async def handler(msg) -> None:
        subject = str(getattr(msg, "subject", "") or "")
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            payload = {"raw": msg.data.decode("utf-8", errors="replace")}

        ts_epoch = _extract_ts_epoch(subject, payload)
        kind = _infer_type(subject)
        counts[kind] = int(counts.get(kind, 0)) + 1
        counts["total"] = int(counts.get("total", 0)) + 1

        fh.write(
            RecordLine(
                schema_version=1,
                type=kind,
                ts_epoch=ts_epoch,
                subject=subject,
                data=payload,
            ).to_json()
            + "\n"
        )

    subs = []
    try:
        for raw in subjects:
            subj = str(raw or "").strip()
            if not subj:
                continue
            subs.append(await nc.subscribe(subj, cb=handler))

        deadline = started + max(0.0, float(duration_s))
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        return {
            "path": str(out_path),
            "duration_s": float(duration_s),
            "counts": dict(counts),
        }
    finally:
        try:
            fh.flush()
        except Exception:
            pass
        try:
            fh.close()
        except Exception:
            pass
        for sub in subs:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        await nc.drain()
        await nc.close()


async def replay_jsonl(
    *,
    nats_url: str,
    input_path: str | Path,
    speed: float = 1.0,
    subject_prefix: str | None = None,
    no_timing: bool = False,
) -> dict[str, Any]:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"nats import failed: {exc}") from exc

    if float(speed) <= 0.0:
        raise ValueError("speed must be > 0")

    in_path = Path(input_path)
    lines = [ln.strip() for ln in in_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    parsed: list[RecordLine] = []
    for ln in lines:
        raw = json.loads(ln)
        if not isinstance(raw, dict):
            continue
        parsed.append(
            RecordLine(
                schema_version=int(raw.get("schema_version", 1)),
                type=str(raw.get("type", "unknown")),  # type: ignore[arg-type]
                ts_epoch=float(raw.get("ts_epoch", 0.0)),
                subject=str(raw.get("subject", "")),
                data=raw.get("data"),
            )
        )
    if not parsed:
        return {"published": 0, "input_path": str(in_path)}

    base_ts = min(float(x.ts_epoch) for x in parsed)
    started = asyncio.get_running_loop().time()

    nc = await nats.connect(servers=[nats_url], connect_timeout=2)
    published = 0
    try:
        for row in parsed:
            if not no_timing:
                offset = max(0.0, float(row.ts_epoch) - base_ts)
                target = started + (offset / float(speed))
                while asyncio.get_running_loop().time() < target:
                    await asyncio.sleep(0.01)

            subject = row.subject
            if subject_prefix:
                prefix = str(subject_prefix).strip().strip(".")
                if prefix:
                    subject = f"{prefix}.{subject}"
            payload = row.data
            try:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except Exception:
                data = json.dumps({"raw": str(payload)}, ensure_ascii=False).encode("utf-8")
            await nc.publish(subject, data)
            published += 1
        await nc.flush(timeout=2)
        return {"published": int(published), "input_path": str(in_path)}
    finally:
        await nc.drain()
        await nc.close()
