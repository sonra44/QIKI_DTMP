from __future__ import annotations

import asyncio
import logging
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from typing import Any, Optional

from qiki.services.q_bios_service.bios_engine import BiosPostInputs, build_bios_status
from qiki.services.q_bios_service.config import BiosConfig
from qiki.services.q_bios_service.handlers import BiosHttpHandler
from qiki.services.q_bios_service.health_checker import check_qsim_health
from qiki.services.q_bios_service.nats_publisher import NatsJsonPublisher


logger = logging.getLogger("q_bios_service")


class BiosService:
    def __init__(self, config: BiosConfig) -> None:
        self._cfg = config
        self._last_payload: Optional[dict[str, Any]] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._publisher_thread: Optional[threading.Thread] = None

    def _compute_payload(self) -> dict[str, Any]:
        sim_health = check_qsim_health(
            host=self._cfg.sim_grpc_host,
            port=self._cfg.sim_grpc_port,
            timeout_s=self._cfg.sim_health_check_timeout_s,
        )
        status = build_bios_status(
            BiosPostInputs(bot_config_path=self._cfg.bot_config_path, sim_health=sim_health)
        )
        payload = status.model_dump(mode="json")
        payload["event_schema_version"] = 1
        payload["source"] = "q-bios-service"
        payload["subject"] = self._cfg.nats_subject
        return payload

    def get_status_payload(self) -> dict[str, Any]:
        with self._lock:
            if self._last_payload is not None:
                return dict(self._last_payload)
        payload = self._compute_payload()
        with self._lock:
            self._last_payload = dict(payload)
        return payload

    def get_component_payload(self, device_id: str) -> dict[str, Any]:
        payload = self.get_status_payload()
        rows = payload.get("post_results")
        if not isinstance(rows, list):
            return {"ok": False, "error": "bios_status_missing_post_results"}
        for row in rows:
            if isinstance(row, dict) and row.get("device_id") == device_id:
                return {
                    "ok": True,
                    "device": row,
                    "timestamp": payload.get("timestamp"),
                    "bios_version": payload.get("bios_version"),
                    "hardware_profile_hash": payload.get("hardware_profile_hash"),
                }
        return {"ok": False, "error": "component_not_found", "device_id": device_id}

    def reload_config(self) -> dict[str, Any]:
        with self._lock:
            self._last_payload = None
        return {"ok": True, "reloaded": True}

    async def _publisher_loop(self) -> None:
        interval = max(0.2, float(self._cfg.publish_interval_s))
        publisher = NatsJsonPublisher(nats_url=self._cfg.nats_url)
        had_errors = False
        try:
            while not self._stop.is_set():
                try:
                    payload = self._compute_payload()
                    with self._lock:
                        self._last_payload = dict(payload)
                    try:
                        await publisher.publish_json(subject=self._cfg.nats_subject, payload=payload)
                        if had_errors:
                            logger.info("NATS publish recovered (url=%s)", self._cfg.nats_url)
                        had_errors = False
                    except Exception as e:
                        had_errors = True
                        logger.warning(
                            "NATS publish failed (url=%s subject=%s): %s",
                            self._cfg.nats_url,
                            self._cfg.nats_subject,
                            e,
                        )
                except Exception as e:
                    logger.warning("BIOS compute failed: %s", e)
                await asyncio.sleep(interval)
        finally:
            await publisher.close()

    def start_publisher(self) -> None:
        if not self._cfg.publish_enabled:
            logger.info("BIOS publisher disabled (BIOS_PUBLISH_ENABLED=0)")
            return

        def _run() -> None:
            asyncio.run(self._publisher_loop())

        self._publisher_thread = threading.Thread(target=_run, name="bios-publisher", daemon=True)
        self._publisher_thread.start()

    def stop(self) -> None:
        self._stop.set()


def main() -> None:
    cfg = BiosConfig()
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))
    logger.info("Starting q-bios-service on %s:%s", cfg.listen_host, cfg.listen_port)

    svc = BiosService(cfg)
    svc.start_publisher()

    handler_factory = partial(
        BiosHttpHandler,
        get_status_payload=svc.get_status_payload,
        get_component_payload=svc.get_component_payload,
        reload_config=svc.reload_config,
    )
    server = ThreadingHTTPServer((cfg.listen_host, cfg.listen_port), handler_factory)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        svc.stop()
        try:
            server.shutdown()
        except Exception:
            pass
        server.server_close()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
