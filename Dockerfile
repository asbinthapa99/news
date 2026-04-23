FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source
COPY . .

EXPOSE 8080

ENV PORT=8080

# Single worker + 4 threads keeps APScheduler running in exactly one process.
# Multiple workers would each spawn their own scheduler and cause duplicate scrapes.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "app:app"]
