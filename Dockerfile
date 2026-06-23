FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 8000 9000

CMD ["uvicorn", "iot_app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]