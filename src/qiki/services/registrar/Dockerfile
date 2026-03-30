# Dockerfile for Registrar Service
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-faststream.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-faststream.txt

# Copy application code
COPY . .

# Expose port for HTTP metrics (if needed)
EXPOSE 8000

# Command to run the service
CMD ["python", "src/qiki/services/registrar/main.py"]