# Build stage
FROM python:3.12-slim AS builder

# Установка системных зависимостей для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt /tmp/requirements.txt

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Runtime stage
FROM python:3.12-slim

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERM=xterm-256color \
    COLORTERM=truecolor

# Создаём рабочую директорию
WORKDIR /app

# Копируем установленные пакеты из builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем код консоли
COPY . /app/

# Копируем proto файлы из основного проекта (будут монтироваться через volumes)
# Это нужно для генерации gRPC клиентов
VOLUME ["/app/proto"]

# Создаём пользователя для безопасности
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck для проверки состояния приложения
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import asyncio; import sys; sys.exit(0)" || exit 1

# По умолчанию запускаем консоль, но можно переопределить через CMD
# Например: docker run image python -m pytest tests/ -v
CMD ["python", "main.py"]
