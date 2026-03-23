FROM python:3.12-slim

WORKDIR /app

# Зависимости отдельным слоем — при неизменном requirements.txt не пересобираются
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY . .

CMD ["gunicorn", "main:app", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "127.0.0.1:8000", \
     "--access-logfile", "/var/log/alltransfer/access.log", \
     "--error-logfile", "/var/log/alltransfer/error.log", \
     "--log-level", "info", \
     "--timeout", "120", \
     "--graceful-timeout", "30"]
