# /workspace/tmp/verify_fix.py
import sys
import os
from pathlib import Path

# Настройка путей, как в реальном приложении
ROOT_DIR = os.path.abspath(os.path.join('/workspace'))
sys.path.append(ROOT_DIR)

print(f"ROOT_DIR: {ROOT_DIR}")
print(f"sys.path: {sys.path}")

try:
    from services.q_sim_service.main import QSimService
    from UP.config_models import QSimServiceConfig, load_config
    from services.q_sim_service.logger import logger

    print("Imports successful.")

    # 1. Загружаем конфиг с помощью правильной функции
    config_path = Path('services/q_sim_service/config.yaml')
    print(f"Attempting to load config from: {config_path.resolve()}")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Test script could not find config at {config_path.resolve()}")

    pydantic_config = load_config(config_path, QSimServiceConfig)
    print(f"Config loaded successfully: {pydantic_config}")

    # 2. Инициализируем сервис с Pydantic-конфигом
    service = QSimService(pydantic_config)
    print("QSimService initialized successfully with Pydantic config.")

    # 3. Вызываем проблемный метод
    sensor_data = service.generate_sensor_data()
    print("generate_sensor_data() executed successfully.")
    print(f"Result: {sensor_data}")

    print("\n--- VERIFICATION SUCCESSFUL ---")
    print("The proposed fix is correct.")

except Exception as e:
    print(f"\n--- VERIFICATION FAILED ---")
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()
