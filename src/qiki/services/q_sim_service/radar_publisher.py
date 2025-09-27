from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional, List

from qiki.shared.events import build_cloudevent_headers

try:
    import nats
except Exception:
    nats = None

from qiki.shared.models.radar import RadarFrameModel, RadarDetectionModel, RangeBand

logger = logging.getLogger(__name__)

LR_SUBJECT = "qiki.radar.v1.frames.lr"
SR_SUBJECT = "qiki.radar.v1.tracks.sr"
UNION_FRAME_SUBJECT = "qiki.radar.v1.frames"

def compute_band(distance_m: float, sr_threshold_m: float) -> RangeBand:
    return RangeBand.RR_SR if distance_m <= sr_threshold_m else RangeBand.RR_LR

class RadarNatsPublisher:
    def __init__(self, nats_url: str, sr_threshold_m: float, subject: str = UNION_FRAME_SUBJECT) -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._sr_threshold_m = sr_threshold_m
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._nc: Optional[nats.NATS] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def build_payload(frame: RadarFrameModel, *, detections: Optional[List[RadarDetectionModel]] = None) -> bytes:
        payload = frame.model_dump(mode="json")
        if detections is not None:
            payload["detections"] = [det.model_dump(mode="json") for det in detections]
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def build_headers(frame: RadarFrameModel, band: RangeBand) -> dict:
        band_name = band.name.replace("RR_", "")
        headers = build_cloudevent_headers(
            event_id=str(frame.frame_id),
            event_type=f"qiki.radar.v1.{band_name}Frame",
            source="urn:qiki:q-sim-service:radar",
            event_time=frame.timestamp,
        )
        headers["Nats-Msg-Id"] = str(frame.frame_id)
        headers["x-range-band"] = band.name
        return headers

    def _ensure_loop(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    async def _async_connect(self) -> None:
        if nats is None:
            return
        if self._nc is None:
            try:
                self._nc = await nats.connect(self._nats_url)
            except Exception as exc:
                logger.warning(f"Failed to connect to NATS {self._nats_url}: {exc}")

    def _ensure_connection(self) -> None:
        self._ensure_loop()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(self._async_connect(), self._loop)
        try:
            fut.result(timeout=2.0)
        except Exception as exc:
            logger.debug(f"NATS connect result: {exc}")

    async def _async_publish(self, subject: str, data: bytes, headers: dict | None = None) -> None:
        if self._nc is None:
            return
        try:
            await self._nc.publish(subject, data, headers=headers)
        except Exception as exc:
            logger.debug(f"NATS publish failed: {exc}")

    def publish_frame(self, frame: RadarFrameModel) -> None:
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return

        lr_dets: List[RadarDetectionModel] = []
        sr_dets: List[RadarDetectionModel] = []

        for det in frame.detections:
            band = compute_band(det.range_m, self._sr_threshold_m)
            det.range_band = band
            if band == RangeBand.RR_LR:
                det.transponder_id = None
                det.id_present = False
                lr_dets.append(det)
            else:
                det.id_present = bool(det.transponder_id)
                sr_dets.append(det)

        if lr_dets:
            lr_payload = self.build_payload(frame, detections=lr_dets)
            lr_headers = self.build_headers(frame, RangeBand.RR_LR)
            asyncio.run_coroutine_threadsafe(self._async_publish(LR_SUBJECT, lr_payload, headers=lr_headers), self._loop)

        if sr_dets:
            sr_payload = self.build_payload(frame, detections=sr_dets)
            sr_headers = self.build_headers(frame, RangeBand.RR_SR)
            asyncio.run_coroutine_threadsafe(self._async_publish(SR_SUBJECT, sr_payload, headers=sr_headers), self._loop)

        union_payload = self.build_payload(frame)
        union_headers = self.build_headers(frame, RangeBand.RR_UNSPECIFIED)
        asyncio.run_coroutine_threadsafe(self._async_publish(UNION_FRAME_SUBJECT, union_payload, headers=union_headers), self._loop)
