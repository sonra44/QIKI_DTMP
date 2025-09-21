# Dockerfile для сервиса FastStream Bridge
FROM python:3.12-slim

WORKDIR /workspace

# Copy ruff.toml and set environment variable for RUFF config
COPY ruff.toml /app/ruff.toml
ENV RUFF_CONFIG=/app/ruff.toml

# Устанавливаем PYTHONPATH, чтобы включить корень проекта
ENV PYTHONPATH=/workspace/src:/workspace

# Копируем и устанавливаем зависимости
COPY requirements.txt .
COPY requirements-faststream.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-faststream.txt && \
    pip install --no-cache-dir ruff

# Копируем весь код проекта
COPY . . 

# Запускаем FastStream приложение
CMD ["faststream", "run", "qiki.services.faststream_bridge.app:app"]
