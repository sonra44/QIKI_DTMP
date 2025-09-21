"""JetStream consumer lag monitoring for Prometheus."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from qiki.services.faststream_bridge.metrics import set_consumer_lag

try:  # pragma: no cover - optional dependency resolved at runtime
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumerTarget:
    durable: str
    label: str


class JetStreamLagMonitor:
    """Periodically polls JetStream consumer info and updates Prometheus gauge."""

    def __init__(
        self,
        *,
        nats_url: str,
        stream: str,
        consumers: Iterable[ConsumerTarget],
        interval_sec: float = 5.0,
    ) -> None:
        self._nats_url = nats_url
        self._stream = stream
        self._consumers = list(consumers)
        self._interval = interval_sec
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._nc: Optional["nats.NATS"] = None  # type: ignore
        self._js = None

    async def start(self) -> None:
        if nats is None:  # pragma: no cover
            logger.warning("nats-py is not available; JetStream lag monitoring disabled")
            return

        if self._task is not None:
            return

        self._nc = await nats.connect(self._nats_url)  # type: ignore
        self._js = self._nc.jetstream()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "JetStream lag monitor started for stream %s consumers=%s",
            self._stream,
            [c.durable for c in self._consumers],
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None
        if self._nc is not None:
            await self._nc.close()
            self._nc = None
            self._js = None
        logger.info("JetStream lag monitor stopped")

    async def _run(self) -> None:
        assert self._js is not None
        try:
            while not self._stop_event.is_set():
                await self._poll_once()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._interval
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:  # pragma: no cover
            logger.debug("Lag monitor task cancelled")
        except Exception as exc:  # pragma: no cover
            logger.warning("Lag monitor error: %s", exc)
        finally:
            self._stop_event.set()

    async def _poll_once(self) -> None:
        assert self._js is not None
        for target in self._consumers:
            try:
                info = await self._js.consumer_info(self._stream, target.durable)
                pending = getattr(info, "num_pending", 0)
                set_consumer_lag(target.label, int(pending))
            except Exception as exc:  # pragma: no cover
                logger.debug(
                    "Failed to fetch consumer info for %s: %s", target.durable, exc
                )
                set_consumer_lag(target.label, 0)
