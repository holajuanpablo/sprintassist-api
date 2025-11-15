FROM python:3.11-slim

# Make sure logs are not buffered
ENV PYTHONUNBUFFERED=True

WORKDIR /app

# COPY requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# COPY the rest of the application
COPY . .

# --- Optional: Build-time checks (can be kept or removed) ---
RUN echo "--- Listing /app contents after COPY ---"
RUN ls -lR /app
# --- End Optional: Build-time checks ---

# --- Run the application using Gunicorn ---
# Reduced to 1 worker for simplicity, increased timeout, added access log
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--log-level", "debug", "--timeout", "120", "--access-logfile", "-", "app:app"]
