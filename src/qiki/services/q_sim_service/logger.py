import logging
import logging.config
import yaml
import os


def setup_logging(
    default_path="config.yaml", default_level=logging.INFO, env_key="LOG_CFG"
):
    """
    Setup logging configuration for Q-Sim Service
    Standalone logger - NO dependencies on q_core_agent
    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, "rt") as f:
            try:
                config = yaml.safe_load(f.read())
                # Ищем logging config в YAML, если есть
                if "logging" in config:
                    logging.config.dictConfig(config["logging"])
                else:
                    # Если нет logging секции, используем default
                    logging.basicConfig(
                        level=default_level,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    )
            except Exception as e:
                print(f"Error in Logging Configuration: {e}")
                print("Using default configs")
                logging.basicConfig(
                    level=default_level,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                )
    else:
        print(f"Configuration file not found: {path}. Using default configs")
        logging.basicConfig(
            level=default_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


# Получаем логгер для Q-Sim Service
logger = logging.getLogger("q_sim_service")
