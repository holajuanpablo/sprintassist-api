FROM python:3.11-slim

# Make sure logs are not buffered
ENV PYTHONUNBUFFERED=True

WORKDIR /app

# COPY requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# COPY the rest of the application
COPY . .

# --- Optional: Build-time checks ---
RUN echo "--- Listing /app contents after COPY ---"
RUN ls -lR /app
# --- End Optional: Build-time checks ---

# --- Run the application using Gunicorn ---
# Increased timeout to 120 seconds, workers=2, debug logging, access logs
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--log-level", "debug", "--timeout", "120", "--access-logfile", "-", "app:app"]
