from __future__ import annotations

from pathlib import Path

from qiki.services.q_sim_service.logger import setup_logging
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig, load_config


def main() -> None:
    app_config_path = Path(__file__).resolve().parent / "config.yaml"
    config = load_config(app_config_path, QSimServiceConfig)
    sim_service = QSimService(config)
    sim_service.run()


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[4]
    logging_config_path = project_root / "logging_config.yaml"
    setup_logging(default_path=str(logging_config_path))
    main()

