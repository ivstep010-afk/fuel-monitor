# Используем официальный slim‑образ для arm32v7 (ARMv7)
FROM arm32v7/python:3.11-slim

# Set working directory
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        # При необходимости добавить другие библиотеки, например:
        # libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ ./src/
COPY run.py .


# Default command: run the monitor (can be overridden)
ENTRYPOINT ["python", "run.py"]