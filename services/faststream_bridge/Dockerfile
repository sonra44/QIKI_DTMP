# Dockerfile для сервиса FastStream Bridge
FROM python:3.12-slim

WORKDIR /workspace

# Устанавливаем PYTHONPATH, чтобы включить корень проекта
ENV PYTHONPATH=.

# Копируем и устанавливаем зависимости
COPY requirements.txt .
COPY requirements-faststream.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-faststream.txt

# Копируем весь код проекта
COPY . . 

# Запускаем FastStream приложение
CMD ["faststream", "run", "services.faststream_bridge.app:app"]
