from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List


try:
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore

try:
    from nats.js.api import AckPolicy, DeliverPolicy, ReplayPolicy, ConsumerConfig
except Exception:  # pragma: no cover - optional dependency resolution at runtime
    AckPolicy = DeliverPolicy = ReplayPolicy = ConsumerConfig = None  # type: ignore


@dataclass
class JsConfig:
    nats_url: str
    stream: str
    subjects: List[str]
    duplicate_window_sec: int
    max_bytes: int
    max_age_sec: int


@dataclass
class JsConsumerConfig:
    stream: str
    durable_name: str
    filter_subject: str
    ack_wait_sec: int
    max_deliver: int
    max_ack_pending: int


def _parse_env() -> JsConfig:
    url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    stream = os.getenv("RADAR_STREAM", "QIKI_RADAR_V1")
    subjects_s = os.getenv("RADAR_SUBJECTS", "qiki.radar.v1.*")
    dup = int(os.getenv("RADAR_DUPLICATE_WINDOW_SEC", "120"))
    max_bytes = int(os.getenv("RADAR_MAX_BYTES", str(10 * 1024 * 1024)))
    max_age = int(os.getenv("RADAR_MAX_AGE_SEC", "3600"))
    subjects = [s.strip() for s in subjects_s.split(",") if s.strip()]
    return JsConfig(url, stream, subjects, dup, max_bytes, max_age)


def _parse_consumer_env(stream: str) -> List[JsConsumerConfig]:
    ack_wait = int(os.getenv("RADAR_CONSUMER_ACK_WAIT_SEC", "30"))
    max_deliver = int(os.getenv("RADAR_CONSUMER_MAX_DELIVER", "5"))
    max_ack_pending = int(os.getenv("RADAR_CONSUMER_MAX_ACK_PENDING", "256"))
    frames_subject = os.getenv("RADAR_FRAMES_SUBJECT", "qiki.radar.v1.frames")
    tracks_subject = os.getenv("RADAR_TRACKS_SUBJECT", "qiki.radar.v1.tracks")
    frames_durable = os.getenv("RADAR_FRAMES_DURABLE", "radar_frames_pull")
    tracks_durable = os.getenv("RADAR_TRACKS_DURABLE", "radar_tracks_pull")

    return [
        JsConsumerConfig(
            stream=stream,
            durable_name=frames_durable,
            filter_subject=frames_subject,
            ack_wait_sec=ack_wait,
            max_deliver=max_deliver,
            max_ack_pending=max_ack_pending,
        ),
        JsConsumerConfig(
            stream=stream,
            durable_name=tracks_durable,
            filter_subject=tracks_subject,
            ack_wait_sec=ack_wait,
            max_deliver=max_deliver,
            max_ack_pending=max_ack_pending,
        ),
    ]


def build_stream_params(cfg: JsConfig):
    return dict(
        name=cfg.stream,
        subjects=cfg.subjects,
        duplicate_window=cfg.duplicate_window_sec,
        max_bytes=cfg.max_bytes,
        max_age=cfg.max_age_sec,
        storage="file",
    )


def build_consumer_params(consumer: JsConsumerConfig):
    return dict(
        durable_name=consumer.durable_name,
        ack_policy=AckPolicy.EXPLICIT,
        deliver_policy=DeliverPolicy.NEW,
        replay_policy=ReplayPolicy.INSTANT,
        filter_subject=consumer.filter_subject,
        ack_wait=consumer.ack_wait_sec,
        max_deliver=consumer.max_deliver,
        max_ack_pending=consumer.max_ack_pending,
    )


async def _ensure_stream(cfg: JsConfig) -> int:
    if nats is None:  # pragma: no cover
        raise RuntimeError("nats-py is not installed")
    nc = await nats.connect(cfg.nats_url)
    try:
        js = nc.jetstream()
        params = build_stream_params(cfg)
        try:
            await js.add_stream(**params)
            return 1  # created
        except Exception:
            # Stream exists; try to update config
            await js.update_stream(**params)
            return 0  # updated
    finally:
        await nc.close()


async def _ensure_consumers(cfg: JsConfig, consumers: List[JsConsumerConfig]) -> List[int]:
    if nats is None or ConsumerConfig is None:  # pragma: no cover
        raise RuntimeError("nats-py with JetStream support is required")

    nc = await nats.connect(cfg.nats_url)
    results: List[int] = []
    try:
        js = nc.jetstream()
        for consumer in consumers:
            params = build_consumer_params(consumer)
            consumer_cfg = ConsumerConfig(**params)
            try:
                await js.add_consumer(stream=consumer.stream, config=consumer_cfg)
                results.append(1)
            except Exception:
                # Consumer уже существует; проверяем состояние и считаем как обновлённый
                await js.consumer_info(consumer.stream, consumer.durable_name)
                results.append(0)
    finally:
        await nc.close()
    return results


def main() -> int:  # pragma: no cover - run in container
    cfg = _parse_env()
    consumers = _parse_consumer_env(cfg.stream)
    stream_result = asyncio.run(_ensure_stream(cfg))
    consumer_results = asyncio.run(_ensure_consumers(cfg, consumers))
    # Return sum of creations for observability
    return stream_result + sum(consumer_results)


if __name__ == "__main__":  # pragma: no cover
    code = main()
    print("JetStream stream ", "created" if code == 1 else "updated")
    raise SystemExit(0)
