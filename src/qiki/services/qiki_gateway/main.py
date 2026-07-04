"""QIKI Gateway service bootstrap (M3). Паттерн ThreadingHTTPServer как q_bios."""

from __future__ import annotations

import logging
import os
from http.server import ThreadingHTTPServer

from qiki.services.qiki_gateway.core import GatewayConfig
from qiki.services.qiki_gateway.handler import GatewayState, make_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("qiki_gateway")


def main() -> None:
    config = GatewayConfig.from_env()
    host = os.getenv("QIKI_GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("QIKI_GATEWAY_PORT", "8090"))

    if not config.is_serviceable():
        # Fail-closed на старте: без реального ключа/vkeys gateway бесполезен и опасен.
        logger.error("gateway not serviceable: real key present=%s, vkeys=%d — обслуживание отключено",
                     bool(config.real_api_key), len(config.virtual_keys))

    state = GatewayState()
    handler = make_handler(config, state)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info("QIKI Gateway listening on %s:%d mode=%s serviceable=%s",
                host, port, config.mode, config.is_serviceable())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
